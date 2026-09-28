"""Buduje out/gazetki.xlsx: Oferty (pełna historia), Produkty (statystyki), Gazetki, Info."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from analiza import CSV_TO_XLSX, load_offers, product_stats

EXCEL_MAX_ROWS = 1_000_000

OFFER_SHEET_COLS = [  # kolejność kolumn w arkuszu "Oferty"
    "sklep", "produkt", "marka", "cena", "rabat_proc", "oferta_od", "oferta_do",
    "gazetka_nazwa", "gazetka_od", "gazetka_do", "strona", "link", "pobrano",
    "gazetka_id", "oferta_id",
]
WIDTHS = {
    "Sklep": 11, "Produkt": 48, "Marka": 18, "Cena [zł]": 10, "Rabat %": 8,
    "Oferta od": 11, "Oferta do": 11, "Gazetka": 30, "Gazetka od": 11, "Gazetka do": 11,
    "Strona": 7, "Link": 20, "Pobrano": 11, "ID gazetki": 10, "ID oferty": 12,
    "Liczba promocji": 10, "Pierwsza promocja": 12, "Ostatnia promocja": 12,
    "Średnio co ile dni": 11, "Ostatnia cena": 10, "Cena min": 10, "Cena mediana": 10,
    "Cena max": 10, "Teraz": 9, "Nazwa": 34, "Od": 11, "Do": 11, "Strony": 8,
    "Liczba ofert": 10, "Pierwsze pobranie": 12, "Ostatnie pobranie": 12, "URL": 45,
}
DATE_COLS = {"Oferta od", "Oferta do", "Gazetka od", "Gazetka do", "Pobrano",
             "Pierwsza promocja", "Ostatnia promocja", "Od", "Do",
             "Pierwsze pobranie", "Ostatnie pobranie"}
PRICE_COLS = {"Cena [zł]", "Ostatnia cena", "Cena min", "Cena mediana", "Cena max"}


def _write_table(wb, name: str, df: pd.DataFrame, fmt: dict, style="Table Style Medium 2"):
    ws = wb.add_worksheet(name)
    cols = list(df.columns)
    nrows = len(df)
    for ci, col in enumerate(cols):
        f = fmt["date"] if col in DATE_COLS else fmt["price"] if col in PRICE_COLS else None
        ws.set_column(ci, ci, WIDTHS.get(col, 12), f)
    # dane
    values = df.astype(object).where(df.notna(), None).values.tolist()
    for ri, row in enumerate(values, start=1):
        for ci, v in enumerate(row):
            if v is None or v == "":
                continue
            if isinstance(v, pd.Timestamp):
                ws.write_datetime(ri, ci, v.to_pydatetime(), fmt["date"])
            elif isinstance(v, (int, float)):
                ws.write_number(ri, ci, v)
            else:
                ws.write_string(ri, ci, str(v))
    ws.add_table(0, 0, max(nrows, 1), len(cols) - 1, {
        "name": name.replace(" ", "_"),
        "columns": [{"header": c} for c in cols],
        "style": style,
    })
    ws.freeze_panes(1, 0)
    return ws


def build_excel(offers_dir: Path, leaflets_csv: Path, out: Path, now: datetime) -> int:
    df = load_offers(offers_dir)
    total = len(df)
    df = df.sort_values(["oferta_od", "sklep", "produkt"], ascending=[False, True, True])
    stats = product_stats(df, now.date()).drop(columns=["klucz"], errors="ignore")

    offers_sheet = df[OFFER_SHEET_COLS].rename(columns=CSV_TO_XLSX)
    truncated = total > EXCEL_MAX_ROWS
    if truncated:
        offers_sheet = offers_sheet.head(EXCEL_MAX_ROWS)

    leaf = pd.read_csv(leaflets_csv, dtype=str, keep_default_na=False) if leaflets_csv.exists() \
        else pd.DataFrame(columns=["gazetka_id", "sklep", "nazwa", "od", "do", "strony",
                                   "liczba_ofert", "pierwsze_pobranie", "ostatnie_pobranie", "url"])
    for c in ("od", "do", "pierwsze_pobranie", "ostatnie_pobranie"):
        leaf[c] = pd.to_datetime(leaf[c], errors="coerce")
    for c in ("strony", "liczba_ofert"):
        leaf[c] = pd.to_numeric(leaf[c], errors="coerce")
    leaf = leaf.rename(columns={
        "gazetka_id": "ID gazetki", "sklep": "Sklep", "nazwa": "Nazwa", "od": "Od", "do": "Do",
        "strony": "Strony", "liczba_ofert": "Liczba ofert", "pierwsze_pobranie": "Pierwsze pobranie",
        "ostatnie_pobranie": "Ostatnie pobranie", "url": "URL"})

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.xlsx")
    import xlsxwriter

    wb = xlsxwriter.Workbook(str(tmp), {"strings_to_urls": False, "strings_to_numbers": False})
    fmt = {
        "date": wb.add_format({"num_format": "yyyy-mm-dd"}),
        "price": wb.add_format({"num_format": "0.00"}),
        "h1": wb.add_format({"bold": True, "font_size": 14}),
        "b": wb.add_format({"bold": True}),
        "wrap": wb.add_format({"text_wrap": True, "valign": "top"}),
    }

    info = wb.add_worksheet("Info")
    _write_table(wb, "Oferty", offers_sheet, fmt)
    _write_table(wb, "Produkty", stats, fmt, style="Table Style Medium 9")
    _write_table(wb, "Gazetki", leaf, fmt, style="Table Style Medium 4")

    info.set_column(0, 0, 26)
    info.set_column(1, 1, 90, fmt["wrap"])
    info.write(0, 0, "Gazetki: Biedronka, Lidl, Kaufland", fmt["h1"])
    dmin, dmax = df["oferta_od"].min(), df["oferta_od"].max()
    lines = [
        ("Ostatnia aktualizacja", now.strftime("%Y-%m-%d %H:%M")),
        ("Ofert w historii", f"{total:,}".replace(",", " ")
         + (f"  (w arkuszu Oferty najnowsze {EXCEL_MAX_ROWS:,}; pełna historia w CSV)" if truncated else "")),
        ("Produktów (sklep+nazwa)", f"{len(stats):,}".replace(",", " ")),
        ("Gazetek", str(len(leaf))),
        ("Zakres dat ofert", f"{dmin:%Y-%m-%d} – {dmax:%Y-%m-%d}" if pd.notna(dmin) else "–"),
        ("", ""),
        ("Oferty", "Każdy produkt z każdej pobranej gazetki. Szukanie: filtr w kolumnie Produkt "
                   "→ Filtry tekstu → Zawiera… Pusta cena = promocja bez jednej ceny (np. -40%, 1+1, 2 za 1)."),
        ("Produkty", "Statystyki per sklep + nazwa produktu. 'Liczba promocji' liczy osobne okresy "
                     "(nakładające się gazetki scalone). 'Średnio co ile dni' = średni odstęp między "
                     "początkami promocji. 'Teraz' = TAK gdy oferta trwa dziś, WKRÓTCE gdy zaczyna się później."),
        ("Gazetki", "Rejestr pobranych gazetek z datami obowiązywania i liczbą ofert."),
        ("Źródło", "blix.pl – dane o produktach blix udostępnia tylko dla aktualnych gazetek, "
                   "dlatego historia rośnie od dnia uruchomienia zbierania."),
    ]
    for i, (k, v) in enumerate(lines, start=2):
        info.write(i, 0, k, fmt["b"])
        info.write(i, 1, v)
    info.activate()
    wb.close()
    tmp.replace(out)
    return total


if __name__ == "__main__":
    from zoneinfo import ZoneInfo

    root = Path(__file__).resolve().parent
    n = build_excel(root / "data" / "oferty", root / "data" / "gazetki.csv",
                    root / "out" / "gazetki.xlsx", datetime.now(ZoneInfo("Europe/Warsaw")))
    print(n)
