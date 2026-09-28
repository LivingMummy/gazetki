"""Wspólna logika: wczytanie historii, normalizacja nazw, statystyki cen, wyszukiwanie."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

# Mapowanie nagłówków arkusza "Oferty" w Excelu -> nazwy kolumn w CSV
XLSX_TO_CSV = {
    "Sklep": "sklep", "Produkt": "produkt", "Marka": "marka", "Cena [zł]": "cena",
    "Rabat %": "rabat_proc", "Oferta od": "oferta_od", "Oferta do": "oferta_do",
    "Gazetka": "gazetka_nazwa", "Gazetka od": "gazetka_od", "Gazetka do": "gazetka_do",
    "Strona": "strona", "Link": "link", "Pobrano": "pobrano", "ID gazetki": "gazetka_id",
    "ID oferty": "oferta_id",
}
CSV_TO_XLSX = {v: k for k, v in XLSX_TO_CSV.items()}


def norm(s: str) -> str:
    """'Masło EKSTRA  Łaciate' -> 'maslo ekstra laciate'"""
    s = (s or "").casefold().replace("ł", "l")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w%,.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_offers(source: str | Path) -> pd.DataFrame:
    """Wczytuje historię z katalogu CSV (data/oferty) albo z pliku gazetki.xlsx."""
    source = Path(source)
    if source.is_dir():
        files = sorted(source.glob("*.csv"))
        if not files:
            return _typed(pd.DataFrame(columns=list(XLSX_TO_CSV.values())))
        df = pd.concat((pd.read_csv(f, dtype=str, keep_default_na=False) for f in files),
                       ignore_index=True)
    else:
        df = pd.read_excel(source, sheet_name="Oferty", dtype=str).fillna("")
        df = df.rename(columns=XLSX_TO_CSV)
    return _typed(df)


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cena"] = pd.to_numeric(df.get("cena"), errors="coerce")
    df["rabat_proc"] = pd.to_numeric(df.get("rabat_proc"), errors="coerce")
    df["strona"] = pd.to_numeric(df.get("strona"), errors="coerce").astype("Int64")
    for c in ("oferta_od", "oferta_do", "gazetka_od", "gazetka_do", "pobrano"):
        df[c] = pd.to_datetime(df.get(c), errors="coerce").dt.normalize()
    df["klucz"] = df["produkt"].map(norm)
    return df



def product_stats(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Statystyki per (sklep, produkt). Duplikaty tej samej oferty z kilku wersji gazetki
    (np. 'Z ladą tradycyjną') liczone są raz."""
    today = pd.Timestamp(today or date.today())
    if df.empty:
        return pd.DataFrame()
    keys = ["sklep", "klucz"]
    d = (df.dropna(subset=["oferta_od"])
           .drop_duplicates(["sklep", "klucz", "oferta_od", "oferta_do", "cena"])
           .sort_values(keys + ["oferta_od", "oferta_do"])
           .reset_index(drop=True))
    if d.empty:
        return pd.DataFrame()
    d["oferta_do"] = d["oferta_do"].fillna(d["oferta_od"])
    g = d.groupby(keys, sort=False)
    # epizod = ciąg nakładających się / stykających się okien promocji
    prev_end = g["oferta_do"].cummax().groupby([d["sklep"], d["klucz"]]).shift()
    d["nowy"] = prev_end.isna() | (d["oferta_od"] > prev_end + pd.Timedelta(days=1))
    d["aktywna"] = (d["oferta_od"] <= today) & (d["oferta_do"] >= today)
    d["przyszla"] = d["oferta_od"] > today
    starts = d[d["nowy"]].groupby(keys, sort=False)["oferta_od"]

    out = pd.DataFrame({
        "Produkt": g["produkt"].last(),
        "Marka": g["marka"].last(),
        "Liczba promocji": starts.size(),
        "Pierwsza promocja": starts.min(),
        "Ostatnia promocja": starts.max(),
        "Ostatnia cena": g["cena"].last(),  # last() pomija puste ceny
        "Cena min": g["cena"].min(),
        "Cena mediana": g["cena"].median(),
        "Cena max": g["cena"].max(),
        "_akt": g["aktywna"].any(),
        "_przysz": g["przyszla"].any(),
    })
    n = out["Liczba promocji"]
    span = (out["Ostatnia promocja"] - out["Pierwsza promocja"]).dt.days
    out["Średnio co ile dni"] = (span / (n - 1)).where(n > 1).round(1)
    out["Teraz"] = out["_akt"].map({True: "TAK"}).fillna(out["_przysz"].map({True: "WKRÓTCE"})).fillna("")
    out = out.reset_index()
    out = out.rename(columns={"sklep": "Sklep"})[[
        "Sklep", "Produkt", "Marka", "Liczba promocji", "Pierwsza promocja", "Ostatnia promocja",
        "Średnio co ile dni", "Ostatnia cena", "Cena min", "Cena mediana", "Cena max", "Teraz", "klucz"]]
    return out.sort_values(["Liczba promocji", "Sklep", "Produkt"],
                           ascending=[False, True, True]).reset_index(drop=True)


def search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Wszystkie słowa zapytania muszą wystąpić w nazwie lub marce (bez polskich znaków,
    bez wielkości liter). Słowa zaczynające się od '-' wykluczają."""
    inc, exc = [], []
    for tok in (query or "").split():
        neg = tok.startswith("-") and len(tok) > 1
        (exc if neg else inc).extend(norm(tok[1:] if neg else tok).split())
    hay = df["klucz"] + " " + df["marka"].map(norm)
    mask = pd.Series(True, index=df.index)
    for w in inc:
        mask &= hay.str.contains(re.escape(w), regex=True)
    for w in exc:
        mask &= ~hay.str.contains(re.escape(w), regex=True)
    return df[mask]
