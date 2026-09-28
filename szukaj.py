#!/usr/bin/env python3
"""
Wyszukiwarka historii promocji (używana przez Claude'a i do ręcznego użytku).

  python szukaj.py "masło ekstra"                   # statystyki + ostatnie oferty
  python szukaj.py "masło -roślinne" --sklep lidl   # wykluczanie słów, filtr sklepu
  python szukaj.py "kawa lavazza" --cena 39.99      # ocena podanej ceny vs historia
  python szukaj.py "pieluchy" --src gazetki.xlsx    # źródło: plik Excela zamiast data/oferty
  python szukaj.py --teraz --sklep biedronka        # co jest teraz w promocji (bez frazy)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from analiza import load_offers, norm, product_stats, search

ROOT = Path(__file__).resolve().parent


def fmt_price(v) -> str:
    return "—" if v is None or pd.isna(v) else f"{v:.2f}".replace(".", ",")


def fmt_date(v) -> str:
    return "" if v is None or pd.isna(v) else f"{v:%Y-%m-%d}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fraza", nargs="?", default="", help="słowa w nazwie/marce; -słowo wyklucza")
    ap.add_argument("--sklep", help="biedronka / lidl / kaufland")
    ap.add_argument("--cena", type=lambda s: float(s.replace(",", ".")), help="cena do oceny")
    ap.add_argument("--src", default=str(ROOT / "data" / "oferty"), help="katalog CSV albo plik .xlsx")
    ap.add_argument("--teraz", action="store_true", help="tylko oferty obowiązujące dziś lub przyszłe")
    ap.add_argument("--limit", type=int, default=25, help="ile ostatnich ofert pokazać")
    a = ap.parse_args(argv)

    df = load_offers(a.src)
    if df.empty:
        print("Brak danych.")
        return 1
    today = pd.Timestamp(date.today())
    print(f"Dane: {len(df)} ofert, od {fmt_date(df['oferta_od'].min())} do {fmt_date(df['oferta_od'].max())}")

    if a.sklep:
        df = df[df["sklep"].map(norm) == norm(a.sklep)]
    hits = search(df, a.fraza) if a.fraza else df
    if a.teraz:
        hits = hits[hits["oferta_do"] >= today]
    if hits.empty:
        print(f"Nic nie znaleziono dla: {a.fraza!r}")
        return 0

    stats = product_stats(hits, today.date())
    print(f"\n## Produkty pasujące do {a.fraza!r}: {len(stats)} (ofert: {len(hits)})\n")
    print("| Sklep | Produkt | Promocji | Co ile dni | Ostatnia | Ost. cena | Min | Mediana | Max | Teraz |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in stats.head(40).iterrows():
        gap = "" if pd.isna(r["Średnio co ile dni"]) else f"{r['Średnio co ile dni']:.0f}"
        print(f"| {r['Sklep']} | {r['Produkt']} | {r['Liczba promocji']} | {gap} | "
              f"{fmt_date(r['Ostatnia promocja'])} | {fmt_price(r['Ostatnia cena'])} | "
              f"{fmt_price(r['Cena min'])} | {fmt_price(r['Cena mediana'])} | {fmt_price(r['Cena max'])} | {r['Teraz']} |")
    if len(stats) > 40:
        print(f"... i {len(stats) - 40} kolejnych — zawęź frazę.")

    if a.cena is not None:
        print(f"\n## Ocena ceny {fmt_price(a.cena)} zł\n")
        dd = hits.drop_duplicates(["sklep", "klucz", "oferta_od", "oferta_do", "cena"]).dropna(subset=["cena"])
        if dd.empty:
            print("Brak historycznych cen liczbowych dla tych produktów.")
        else:
            for (sklep, klucz), g in dd.groupby(["sklep", "klucz"]):
                p = g["cena"]
                cheaper = (p < a.cena).mean() * 100
                print(f"- {sklep} / {g['produkt'].iloc[-1]}: n={len(p)}, min {fmt_price(p.min())}, "
                      f"mediana {fmt_price(p.median())}, max {fmt_price(p.max())} → "
                      f"{cheaper:.0f}% historycznych promocji było tańszych")

    recent = hits.drop_duplicates(["sklep", "klucz", "oferta_od", "oferta_do", "cena"]) \
                 .sort_values(["oferta_od", "sklep"], ascending=[False, True]).head(a.limit)
    print(f"\n## Ostatnie oferty (max {a.limit})\n")
    print("| Od | Do | Sklep | Produkt | Cena | Gazetka | Link |")
    print("|---|---|---|---|---|---|---|")
    for _, r in recent.iterrows():
        extra = f" (-{int(r['rabat_proc'])}%)" if pd.notna(r["rabat_proc"]) and r["rabat_proc"] else ""
        print(f"| {fmt_date(r['oferta_od'])} | {fmt_date(r['oferta_do'])} | {r['sklep']} | {r['produkt']} | "
              f"{fmt_price(r['cena'])}{extra} | {r['gazetka_nazwa']} | {r['link']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
