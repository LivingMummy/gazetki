"""Testy offline na danych w formacie skopiowanym z blix.pl (28.09.2026)."""
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

import analiza  # noqa: E402
import scraper  # noqa: E402

STORE_HTML = """
<div class="leaflet section-n__item"
    data-brand-name="Lidl"
    data-brand-id="1"
    data-brand-slug="lidl"
    data-leaflet-id="526038"
    data-leaflet-name="Katalog"
    data-filtered-id="1"
        data-date-start="October 5, 2026 00:00"
    data-date-end="October 10, 2026 23:59"
     data-page-number="1">
  <a href="https://blix.pl/sklep/lidl/gazetka/526038/?pageNumber=1" class="leaflet__link">x</a></div>
<div class="leaflet section-n__item ga-leafletpage-brandlisting-suggestion"
    data-brand-name="Lidl" data-brand-id="1" data-brand-slug="lidl" data-leaflet-id="526038"
    data-leaflet-name="Katalog" data-date-start="October 5, 2026 00:00" data-date-end="October 10, 2026 23:59"></div>
<div class="leaflet section-n__item" data-brand-name="Lidl" data-brand-id="1" data-brand-slug="lidl"
    data-leaflet-id="526032" data-leaflet-name="Oferta od poniedziałku"
    data-date-start="September 28, 2026 00:00" data-date-end="September 30, 2026 23:59"></div>
<div class="leaflet section-n__item ga-brandpage-similarlisting-suggestion"
    data-brand-name="Carrefour" data-brand-id="31" data-brand-slug="carrefour" data-leaflet-id="525834"
    data-leaflet-name="Gazetka Carrefour od poniedziałku"></div>
<div class="leaflet section-n__item leaflet--archival" data-brand-name="Lidl" data-brand-id="1"
    data-brand-slug="lidl" data-leaflet-id="525828" data-leaflet-name="Oferta od czwartku"></div>
"""


def offer(uuid, name, brand, price, ds, de, page=0, lid=526032, disc=0):
    return {
        "hash": None, "name": name,
        "image": f"https://imgproxy.blix.pl/product_occurrence//{uuid}.jpg",
        "manufacturerName": None, "manufacturerUuid": None, "brandName": brand, "brandUuid": None,
        "subBrandName": None, "subBrandUuid": None, "hiperCategoryId": None, "offerSubcategoryId": None,
        "productLeafletPageUuid": uuid, "price": price, "percentDiscount": disc, "leafletId": lid,
        "pageNumber": page,
        "dateStart": {"date": f"{ds} 00:00:00.000000", "timezone_type": 3, "timezone": "Europe/Warsaw"},
        "dateEnd": {"date": f"{de} 23:59:59.000000", "timezone_type": 3, "timezone": "Europe/Warsaw"},
        "area": {"topLeftCorner": {"x": 0.03, "y": 0.31}, "bottomRightCorner": {"x": 0.56, "y": 0.48}},
        "availabilityLabel": {"message": "aktualna", "class": "lav-available"},
    }


def leaflet(lid, name, ds, de, offers, slug="lidl", brand="Lidl"):
    return {
        "viewer": {
            "leaflet_url": f"https://blix.pl/sklep/{slug}/gazetka/{lid}/", "leaflet_name": name,
            "date_start": {"date": f"{ds} 00:00:00.000000"}, "date_end": {"date": f"{de} 23:59:00.000000"},
            "pages": [{"page": i} for i in range(10)],
        },
        "brand": {"id": 1, "name": brand, "slug": slug}, "productOffers": offers, "id": str(lid),
    }


def test_parse_store_page():
    ids = scraper.parse_store_page(STORE_HTML, "lidl")
    assert ids == ["526038", "526032"], ids


def test_parse_leaflet_json():
    j = leaflet(526032, "Oferta od poniedziałku", "2026-09-28", "2026-09-30", [
        offer("u1", "Masło  Pilos 82%", "Pilos", 499, "2026-09-28", "2026-09-30", page=3),
        offer("u2", "Olej rzepakowy", "Kujawski", None, "2026-09-28", "2026-09-29", disc=40),
    ])
    lf, offs = scraper.parse_leaflet_json(j, "lidl", "2026-09-28")
    assert lf["nazwa"] == "Oferta od poniedziałku" and lf["liczba_ofert"] == "2" and lf["strony"] == "10"
    a, b = offs
    assert a["produkt"] == "Masło Pilos 82%" and a["cena"] == "4.99" and a["strona"] == "4"
    assert a["link"].endswith("/sklep/lidl/gazetka/526032/?pageNumber=4")
    assert b["cena"] == "" and b["rabat_proc"] == "40" and b["oferta_do"] == "2026-09-29"


def test_real_blix_json_fixtures():
    fx = ROOT / "tests" / "fixtures"
    j = json.loads((fx / "lidl_526038_sample.json").read_text(encoding="utf-8"))
    lf, offs = scraper.parse_leaflet_json(j, "lidl", "2026-09-28")
    assert lf["gazetka_id"] == "526038" and lf["od"] == "2026-10-05" and lf["do"] == "2026-10-10"
    assert [o["cena"] for o in offs] == ["39.99", "99.00", "", "199.00"]
    assert offs[3]["strona"] == "4" and offs[3]["link"].endswith("/526038/?pageNumber=4")
    assert offs[0]["oferta_od"] == "2026-10-08" and offs[0]["sklep"] == "Lidl"
    # gazetka z pustą datą startu (np. 'Barek Kauflandu') nie może wywrócić skryptu
    j2 = json.loads((fx / "kaufland_null_dates.json").read_text(encoding="utf-8"))
    lf2, offs2 = scraper.parse_leaflet_json(j2, "kaufland", "2026-09-28")
    assert lf2["od"] == "" and lf2["do"] == "2026-09-30" and offs2[0]["oferta_od"] == "2026-09-24"


def test_norm_and_search():
    assert analiza.norm("Masło EKSTRA  Łaciate, 200 g") == "maslo ekstra laciate, 200 g"
    df = pd.DataFrame({"produkt": ["Masło ekstra", "Masło roślinne", "Mleko"], "marka": ["A", "B", "Łaciate"]})
    df["klucz"] = df["produkt"].map(analiza.norm)
    assert list(analiza.search(df, "maslo")["produkt"]) == ["Masło ekstra", "Masło roślinne"]
    assert list(analiza.search(df, "masło -roślinne")["produkt"]) == ["Masło ekstra"]
    assert list(analiza.search(df, "laciate")["produkt"]) == ["Mleko"]


def test_end_to_end_multiple_runs():
    tmp = Path(tempfile.mkdtemp())
    try:
        scraper.OFFERS_DIR = tmp / "data" / "oferty"
        scraper.LEAFLETS_CSV = tmp / "data" / "gazetki.csv"
        scraper.OUT_XLSX = tmp / "out" / "gazetki.xlsx"

        pages = {}

        def fake_fetch(session, url, want_json=False, tries=4):
            return pages.get(url)

        scraper.fetch = fake_fetch
        scraper.make_session = lambda: None
        scraper.time.sleep = lambda s: None

        base = "https://blix.pl"
        # --- przebieg 1: 24.09 -- Biedronka: gazetka + jej wariant "Z ladą" (duplikaty ofert)
        b_html = STORE_HTML.replace('"lidl"', '"biedronka"').replace("Lidl", "Biedronka")
        for slug in ("lidl", "kaufland"):
            pages[f"{base}/sklep/{slug}/"] = "<html></html>"
        pages[f"{base}/sklep/biedronka/"] = b_html
        pages[f"{base}/getleaflet/biedronka/526032/"] = leaflet(526032, "Od czwartku", "2026-09-24", "2026-09-30", [
            offer("b1", "Masło ekstra Mlekovita", "Mlekovita", 549, "2026-09-24", "2026-09-26", lid=526032),
            offer("b2", "Kawa Lavazza Oro", "Lavazza", None, "2026-09-24", "2026-09-30", lid=526032, disc=50),
        ], slug="biedronka", brand="Biedronka")
        pages[f"{base}/getleaflet/biedronka/526038/"] = leaflet(526038, "Od czwartku, Z ladą", "2026-09-24", "2026-09-30", [
            offer("b1x", "Masło ekstra Mlekovita", "Mlekovita", 549, "2026-09-24", "2026-09-26", lid=526038),
        ], slug="biedronka", brand="Biedronka")

        orig_now = scraper.datetime

        class FakeDT(datetime):
            _now = datetime(2026, 9, 24, 7, 0, tzinfo=ZoneInfo("Europe/Warsaw"))

            @classmethod
            def now(cls, tz=None):
                return cls._now

        scraper.datetime = FakeDT
        assert scraper.main([]) == 0
        rows = pd.read_csv(scraper.OFFERS_DIR / "2026-09.csv", dtype=str, keep_default_na=False)
        assert len(rows) == 3

        # --- przebieg 2: ten sam dzień, bez zmian -> brak duplikatów
        assert scraper.main([]) == 0
        assert len(pd.read_csv(scraper.OFFERS_DIR / "2026-09.csv")) == 3

        # --- przebieg 3: 2.10 -- blix poprawił cenę kawy; nowa gazetka z masłem w innej cenie
        FakeDT._now = datetime(2026, 10, 2, 7, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        pages[f"{base}/getleaflet/biedronka/526032/"]["productOffers"][1]["price"] = 3999
        pages[f"{base}/getleaflet/biedronka/526038/"] = leaflet(526038, "Od czwartku 01.10", "2026-10-01", "2026-10-07", [
            offer("b3", "Masło Ekstra Mlekovita", "Mlekovita", 459, "2026-10-01", "2026-10-04", lid=526038),
        ], slug="biedronka", brand="Biedronka")
        assert scraper.main([]) == 0
        sep = pd.read_csv(scraper.OFFERS_DIR / "2026-09.csv", dtype=str, keep_default_na=False)
        octo = pd.read_csv(scraper.OFFERS_DIR / "2026-10.csv", dtype=str, keep_default_na=False)
        assert len(sep) == 3 and len(octo) == 1
        assert sep.set_index("oferta_id").loc["b2", "cena"] == "39.99"
        assert sep.set_index("oferta_id").loc["b2", "pobrano"] == "2026-09-24"  # data pierwszego pobrania zostaje

        # --- przebieg 4: gazetka wygasła i blix zwraca 0 ofert -> nic nie znika, cena nie jest kasowana
        pages[f"{base}/getleaflet/biedronka/526032/"]["productOffers"] = []
        assert scraper.main([]) == 0
        assert len(pd.read_csv(scraper.OFFERS_DIR / "2026-09.csv")) == 3
        leaf = pd.read_csv(scraper.LEAFLETS_CSV, dtype=str).set_index("gazetka_id")
        assert leaf.loc["526032", "liczba_ofert"] == "2"  # max widziany

        # --- statystyki
        df = analiza.load_offers(scraper.OFFERS_DIR)
        st = analiza.product_stats(df, datetime(2026, 10, 2).date()).set_index("klucz")
        m = st.loc["maslo ekstra mlekovita"]
        assert m["Liczba promocji"] == 2, m  # duplikat 'Z ladą' scalony
        assert m["Cena min"] == 4.59 and m["Cena max"] == 5.49 and m["Ostatnia cena"] == 4.59
        assert m["Średnio co ile dni"] == 7.0
        assert m["Teraz"] == "TAK"

        # --- Excel
        xl = pd.ExcelFile(scraper.OUT_XLSX)
        assert xl.sheet_names == ["Info", "Oferty", "Produkty", "Gazetki"], xl.sheet_names
        of = pd.read_excel(xl, "Oferty")
        assert len(of) == 4 and of["Cena [zł]"].notna().sum() == 4
        # szukaj.py czyta też z Excela
        df2 = analiza.load_offers(scraper.OUT_XLSX)
        assert len(analiza.search(df2, "maslo")) == 3
        scraper.datetime = orig_now
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("OK ", name)
