---
name: gazetki-promocje
description: Answer questions about grocery promotions and prices in Biedronka, Lidl or Kaufland (is a price good, how often a product is on sale, where it is cheapest, what is in this week's leaflets) using Nikodem's leaflet history from github.com/LivingMummy/gazetki.
---

# Gazetki: historia promocji Biedronka / Lidl / Kaufland

Nikodem zbiera automatycznie (GitHub Actions, 2× dziennie) wszystkie produkty z gazetek
Biedronki, Lidla i Kauflandu z blix.pl. Repo: https://github.com/LivingMummy/gazetki
- gałąź `main`: historia w `data/oferty/*.csv` + narzędzie `szukaj.py`
- gałąź `excel`: `gazetki.xlsx` (te same dane; arkusze Info, Oferty, Produkty, Gazetki)

## 1. Pobierz dane

```bash
D=/tmp/gazetki
if [ -d $D/.git ]; then git -C $D pull -q; else git clone -q --depth 1 https://github.com/LivingMummy/gazetki.git $D; fi
python3 -c "import pandas, openpyxl" 2>/dev/null || pip install -q pandas openpyxl --break-system-packages
```
- Jeśli użytkownik załączył `gazetki.xlsx`, użyj go: `--src <ścieżka do xlsx>`.
- Jeśli klonowanie się nie uda (brak sieci), poproś o załączenie Excela z
  https://github.com/LivingMummy/gazetki/raw/excel/gazetki.xlsx. Bez repo nie ma `szukaj.py`, więc
  przeanalizuj Excela pandasem: arkusz `Oferty` (każda oferta) i `Produkty` (gotowe statystyki).

## 2. Szukaj

```bash
cd /tmp/gazetki
python3 szukaj.py "<fraza>" [--sklep biedronka|lidl|kaufland] [--cena 4,99] [--teraz] [--limit 40]
```
- Wyszukiwanie to dopasowanie podciągu bez polskich znaków i wielkości liter; wszystkie słowa muszą
  wystąpić. Używaj rdzeni (`masl` łapie masło/masła, `pomidor` łapie pomidory), a `-słowo` wyklucza
  (`"maslo -roslinne"`).
- Zrób 2–3 zapytania: szerokie (np. `kawa ziarn`), potem zawężone (marka, gramatura). Nazwy tego
  samego produktu różnią się między tygodniami i sklepami, więc grupuj podobne nazwy sam.
- `--cena X` pokazuje, jaki % historycznych promocji był tańszy niż X.
- `--teraz` zostawia tylko oferty obowiązujące dziś i przyszłe („co jest teraz w gazetkach”).
- Do głębszej analizy (np. porównanie cen za kg, trend) wczytaj dane w Pythonie:
  `from analiza import load_offers, search, product_stats; df = load_offers("data/oferty")`.
  Kolumny: sklep, produkt, marka, cena, rabat_proc, oferta_od, oferta_do, gazetka_nazwa, gazetka_od,
  gazetka_do, strona, link, pobrano, gazetka_id, oferta_id, klucz (znormalizowana nazwa).

## 3. Interpretuj uczciwie

- Pierwsza linia wyniku podaje zakres dat danych. Historia zaczyna się pod koniec września 2026.
  Przy krótkiej historii (mało promocji danego produktu) mów wprost, że ocena jest wstępna.
- Jeśli najnowsze `pobrano` jest starsze niż 2 dni, uprzedź, że automat na GitHubie mógł przestać
  działać (zakładka Actions w repo).
- To są **ceny promocyjne z gazetek**, nie regularne ceny półkowe. Brak produktu w danych oznacza,
  że nie było go w gazetkach, a nie że go nie ma w sklepie.
- Pusta cena oznacza promocję bez jednej ceny (np. -40%, 1+1, „2 za”). Wtedy podaj rabat albo link.
- Uważaj na gramatury i warianty (np. 200 g vs 250 g, 5-pak vs sztuka). Porównuj ceny tylko
  porównywalnych produktów, a jeśli gramatura nie jest znana, zaznacz to.
- „Liczba promocji” liczy osobne okresy (ta sama oferta z kilku wersji gazetki i nakładające się
  okresy są scalone). „Średnio co ile dni” to średni odstęp między początkami promocji. Można z niego
  oszacować następną promocję: ostatnia promocja + średni odstęp (jako przybliżenie, nie pewnik).

## 4. Odpowiedź

Po polsku, krótko:
1. werdykt (np. „4,99 zł to dobra cena: taniej było tylko 1 z 6 razy, mediana 5,49 zł”),
2. mała tabela: sklep, produkt, liczba promocji, co ile dni, min / mediana / ostatnia cena, czy teraz,
3. gdzie jest teraz najtaniej (jeśli trwa promocja) z linkiem do strony gazetki na blix.pl,
4. jedno zdanie o ograniczeniach danych, jeśli mają znaczenie.
