#!/usr/bin/env python3
"""
Pobiera wszystkie aktualne i nadchodzące gazetki Biedronki, Lidla i Kauflandu
z blix.pl, dopisuje oferty do historii (data/*.csv) i buduje Excela
(out/gazetki.xlsx) z pełną historią + statystykami cen per produkt.

Uruchomienie:  python scraper.py            (pobranie + Excel)
               python scraper.py --only-excel  (tylko przebudowa Excela z CSV)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OFFERS_DIR = DATA / "oferty"
LEAFLETS_CSV = DATA / "gazetki.csv"
OUT_XLSX = ROOT / "out" / "gazetki.xlsx"

BASE = "https://blix.pl"
STORES = {"biedronka": "Biedronka", "lidl": "Lidl", "kaufland": "Kaufland"}
TZ = ZoneInfo("Europe/Warsaw")

OFFER_COLS = [
    "oferta_id", "sklep", "produkt", "marka", "cena", "rabat_proc",
    "oferta_od", "oferta_do", "gazetka_id", "gazetka_nazwa",
    "gazetka_od", "gazetka_do", "strona", "link", "obraz", "pobrano",
]
# Pola, które mogą się zmienić po stronie blix (np. poprawiona cena) -> aktualizujemy.
MUTABLE_OFFER_COLS = [c for c in OFFER_COLS if c not in ("oferta_id", "pobrano")]

LEAFLET_COLS = [
    "gazetka_id", "sklep", "nazwa", "od", "do", "strony", "liczba_ofert",
    "pierwsze_pobranie", "ostatnie_pobranie", "url",
]


# --------------------------------------------------------------------------- HTTP
def make_session():
    """curl_cffi udaje przeglądarkę Chrome (odporniejsze na Cloudflare); fallback: requests."""
    headers = {
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.6",
        "Referer": BASE + "/",
    }
    try:
        from curl_cffi import requests as creq  # type: ignore

        s = creq.Session(impersonate="chrome")
        s.headers.update(headers)
        return s
    except Exception:  # pragma: no cover
        import requests

        s = requests.Session()
        s.headers.update(headers | {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
        })
        return s


def fetch(session, url: str, *, want_json: bool = False, tries: int = 4):
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, timeout=40)
            if r.status_code == 404:
                return None
            if r.status_code == 200:
                if want_json:
                    return json.loads(r.text)
                return r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # sieć / JSON
            last = repr(e)
        time.sleep(3 * attempt)
    raise RuntimeError(f"Nie udało się pobrać {url}: {last}")


# ------------------------------------------------------------------ parsowanie
class _LeafletDivParser(HTMLParser):
    """Zbiera atrybuty <div ... data-leaflet-id=...> ze strony sklepu."""

    def __init__(self):
        super().__init__()
        self.items: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        a = dict(attrs)
        if a.get("data-leaflet-id"):
            self.items.append(a)


def parse_store_page(html: str, slug: str) -> list[str]:
    """Zwraca ID aktualnych i nadchodzących gazetek danego sklepu (bez archiwalnych)."""
    p = _LeafletDivParser()
    p.feed(html)
    ids: list[str] = []
    for a in p.items:
        if a.get("data-brand-slug") != slug:
            continue
        if "leaflet--archival" in (a.get("class") or ""):
            continue
        lid = a["data-leaflet-id"].strip()
        if lid.isdigit() and lid not in ids:
            ids.append(lid)
    return ids


def _d(obj) -> str:
    """{'date': '2026-09-24 00:00:00.000000', ...} -> '2026-09-24'"""
    if isinstance(obj, dict):
        obj = obj.get("date")
    return (obj or "")[:10]


def parse_leaflet_json(j: dict, slug: str, today: str):
    v = j.get("viewer") or {}
    lid = str(j.get("id") or "")
    store = (j.get("brand") or {}).get("name") or STORES.get(slug, slug)
    leaflet = {
        "gazetka_id": lid,
        "sklep": store,
        "nazwa": (v.get("leaflet_name") or "").strip(),
        "od": _d(v.get("date_start")),
        "do": _d(v.get("date_end")),
        "strony": str(len(v.get("pages") or [])),
        "liczba_ofert": str(len(j.get("productOffers") or [])),
        "pierwsze_pobranie": today,
        "ostatnie_pobranie": today,
        "url": v.get("leaflet_url") or f"{BASE}/sklep/{slug}/gazetka/{lid}/",
    }
    offers = []
    for o in j.get("productOffers") or []:
        page = int(o.get("pageNumber") or 0) + 1
        name = " ".join((o.get("name") or "").split())
        price = o.get("price")
        uid = o.get("productLeafletPageUuid") or f"{lid}-{page}-{name}-{price}"
        disc = o.get("percentDiscount") or 0
        offers.append({
            "oferta_id": uid,
            "sklep": store,
            "produkt": name,
            "marka": (o.get("brandName") or "").strip(),
            "cena": f"{price / 100:.2f}" if isinstance(price, (int, float)) else "",
            "rabat_proc": str(disc) if disc else "",
            "oferta_od": _d(o.get("dateStart")) or leaflet["od"],
            "oferta_do": _d(o.get("dateEnd")) or leaflet["do"],
            "gazetka_id": lid,
            "gazetka_nazwa": leaflet["nazwa"],
            "gazetka_od": leaflet["od"],
            "gazetka_do": leaflet["do"],
            "strona": str(page),
            "link": f"{BASE}/sklep/{slug}/gazetka/{lid}/?pageNumber={page}",
            "obraz": o.get("image") or "",
            "pobrano": today,
        })
    return leaflet, offers


# -------------------------------------------------------------------- magazyn CSV
def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def load_offer_store() -> dict[str, list[dict]]:
    """{'2026-09.csv': [wiersze...]}"""
    return {p.name: _read_csv(p) for p in sorted(OFFERS_DIR.glob("*.csv"))}


def merge_offers(store: dict[str, list[dict]], new: list[dict], today: str):
    """Upsert po oferta_id. Nowe trafiają do pliku miesiąca pobrania.
    Zwraca (liczba_nowych, liczba_zaktualizowanych, zmienione_pliki)."""
    index: dict[str, tuple[str, int]] = {}
    for fname, rows in store.items():
        for i, r in enumerate(rows):
            index[r["oferta_id"]] = (fname, i)

    month_file = f"{today[:7]}.csv"
    changed: set[str] = set()
    added = updated = 0
    for o in new:
        hit = index.get(o["oferta_id"])
        if hit is None:
            store.setdefault(month_file, []).append(o)
            index[o["oferta_id"]] = (month_file, len(store[month_file]) - 1)
            changed.add(month_file)
            added += 1
            continue
        fname, i = hit
        row = store[fname][i]
        diff = False
        for c in MUTABLE_OFFER_COLS:
            nv = o.get(c, "")
            if c == "cena" and not nv:  # nie kasujemy znanej ceny pustą
                continue
            if nv != row.get(c, ""):
                row[c] = nv
                diff = True
        if diff:
            changed.add(fname)
            updated += 1
    return added, updated, changed


def merge_leaflets(existing: list[dict], seen: list[dict]) -> list[dict]:
    by_id = {r["gazetka_id"]: r for r in existing}
    for l in seen:
        old = by_id.get(l["gazetka_id"])
        if old is None:
            by_id[l["gazetka_id"]] = l
            continue
        first = old.get("pierwsze_pobranie") or l["pierwsze_pobranie"]
        max_offers = max(int(old.get("liczba_ofert") or 0), int(l["liczba_ofert"] or 0))
        old.update(l)
        old["pierwsze_pobranie"] = first
        old["liczba_ofert"] = str(max_offers)
    return sorted(by_id.values(), key=lambda r: (r["od"], r["sklep"], r["gazetka_id"]), reverse=True)


# ------------------------------------------------------------------------- główne
def scrape(today: str) -> tuple[list[dict], list[dict], list[str]]:
    session = make_session()
    leaflets, offers, problems = [], [], []
    for slug, label in STORES.items():
        html = fetch(session, f"{BASE}/sklep/{slug}/")
        if not html:
            problems.append(f"{label}: brak strony sklepu")
            continue
        ids = parse_store_page(html, slug)
        print(f"[{label}] gazetek do sprawdzenia: {len(ids)}")
        if not ids:
            problems.append(f"{label}: nie znaleziono żadnej gazetki (zmiana struktury blix?)")
        for lid in ids:
            time.sleep(1.0)
            try:
                j = fetch(session, f"{BASE}/getleaflet/{slug}/{lid}/", want_json=True)
            except Exception as e:
                problems.append(f"{label} {lid}: {e}")
                continue
            if not j:
                continue
            leaflet, offs = parse_leaflet_json(j, slug, today)
            leaflets.append(leaflet)
            offers.extend(offs)
            print(f"   {lid} {leaflet['nazwa']!r:55} {leaflet['od']}..{leaflet['do']}  ofert: {len(offs)}")
    return leaflets, offers, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-excel", action="store_true", help="tylko przebuduj Excela z CSV")
    args = ap.parse_args(argv)

    now = datetime.now(TZ)
    today = now.date().isoformat()
    problems: list[str] = []

    if not args.only_excel:
        leaflets, offers, problems = scrape(today)
        if not leaflets:
            print("BŁĄD: nie pobrano żadnej gazetki.", *problems, sep="\n  ")
            return 2

        store = load_offer_store()
        added, updated, changed = merge_offers(store, offers, today)
        for fname in changed:
            _write_csv(OFFERS_DIR / fname, store[fname], OFFER_COLS)

        all_leaflets = merge_leaflets(_read_csv(LEAFLETS_CSV), leaflets)
        _write_csv(LEAFLETS_CSV, all_leaflets, LEAFLET_COLS)
        print(f"\nOferty: nowe {added}, zaktualizowane {updated}, pobrane w tym przebiegu {len(offers)}")

    from build_excel import build_excel  # import tu, by scraping nie wymagał pandas

    n = build_excel(OFFERS_DIR, LEAFLETS_CSV, OUT_XLSX, now)
    print(f"Excel: {OUT_XLSX} ({n} ofert w historii)")

    if problems:
        print("\nOSTRZEŻENIA:", *problems, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
