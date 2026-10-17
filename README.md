# Gazetki: Biedronka · Lidl · Kaufland

Automat, który **2× dziennie** (ok. 7:20 i 18:20) pobiera z [blix.pl](https://blix.pl) wszystkie
aktualne i nadchodzące gazetki trzech sieci, wyciąga z nich każdy produkt z ceną i dopisuje do
historii. Z historii budowany jest Excel z pełnymi danymi i statystykami cen.

**Excel (zawsze najnowszy):** https://github.com/LivingMummy/gazetki/raw/excel/gazetki.xlsx
(albo dwuklik w `pobierz_excel.bat` na komputerze).

> blix pokazuje listę produktów tylko dla gazetek, które jeszcze obowiązują. Po wygaśnięciu
> gazetki dane znikają, dlatego historia rośnie od dnia uruchomienia i nie da się jej pobrać wstecz.

## Co jest w Excelu

| Arkusz | Zawartość |
|---|---|
| **Info** | data ostatniej aktualizacji, liczby ofert/gazetek, opis kolumn |
| **Oferty** | każdy produkt z każdej gazetki: sklep, produkt, marka, cena, rabat %, daty oferty, gazetka, strona, link do strony gazetki, data pobrania |
| **Produkty** | per sklep + produkt: liczba promocji, pierwsza/ostatnia, średnio co ile dni, ostatnia/min/mediana/max cena, czy trwa teraz |
| **Gazetki** | rejestr pobranych gazetek |

Pusta cena oznacza promocję bez jednej ceny, np. -40%, 1+1 albo „2 za”.

## Pierwsze uruchomienie (jednorazowo, ok. 5 minut)

1. Wejdź na https://github.com/new, wpisz **Repository name:** `gazetki`, zaznacz **Public**,
   niczego więcej nie dodawaj i kliknij **Create repository**.
2. Na stronie nowego repo kliknij link **uploading an existing file**. Otwórz folder
   `C:\01_PROJEKTY\2609_Gazetki` w Eksploratorze, zaznacz **wszystko** (Ctrl+A), razem z folderami
   `tests` i `skill`, i przeciągnij do przeglądarki. Potem kliknij **Commit changes**.
3. Harmonogram: w repo wejdź w **Add file → Create new file**. Jako nazwę wpisz dokładnie
   `.github/workflows/gazetki.yml` (ukośniki same utworzą foldery). Wklej całą zawartość pliku
   `gazetki_workflow.yml` z folderu i kliknij **Commit changes**.
4. Wejdź w zakładkę **Actions**, wybierz **Pobierz gazetki**, kliknij **Run workflow** → **Run workflow**.
   Po 2–4 minutach powinien pojawić się zielony znaczek ✓, a Excel będzie dostępny pod linkiem wyżej.
5. Od teraz działa samo. Jeśli któreś uruchomienie się nie powiedzie, GitHub wyśle Ci maila.

*Jeśli wolisz git z PyCharma/terminala zamiast kroków 2–3 (cmd):*
```
cd C:\01_PROJEKTY\2609_Gazetki
mkdir .github\workflows && copy gazetki_workflow.yml .github\workflows\gazetki.yml
git init -b main && git add . && git commit -m "Start"
git remote add origin https://github.com/LivingMummy/gazetki.git
git push -u origin main
```

## Pytanie Claude'a o produkty

Po zainstalowaniu skilla z folderu `skill/` wystarczy zapytać np.:
- „Czy masło za 5,49 w Biedronce to dobra cena?”
- „Jak często kawa Lavazza jest w promocji i gdzie była najtaniej?”
- „Co z pieluchami Pampers jest teraz w gazetkach?”

Claude pobiera to repo, uruchamia `szukaj.py` i odpowiada na podstawie całej historii.

Ręcznie (Python):
```
pip install -r requirements.txt
python szukaj.py "masło ekstra"                  # statystyki + ostatnie oferty
python szukaj.py "kawa lavazza" --cena 39,99     # ocena ceny względem historii
python szukaj.py "masło -roślinne" --sklep lidl  # wykluczanie słów, filtr sklepu
python szukaj.py "pampers" --teraz               # tylko bieżące i nadchodzące
```

## Jak to działa

- `scraper.py` pobiera listę gazetek ze stron sklepów na blix, a potem dla każdej gazetki JSON
  z produktami (`/getleaflet/<sklep>/<id>/`). Oferty są identyfikowane po ID blix, więc kolejne
  uruchomienia nie tworzą duplikatów. Poprawki cen po stronie blix są nanoszone.
- Historia: `data/oferty/RRRR-MM.csv` (miesiąc pierwszego pobrania) i `data/gazetki.csv`.
- Excel budowany jest z CSV (`build_excel.py`) i publikowany na gałęzi `excel`. Ta gałąź ma zawsze
  jeden commit, więc repo nie puchnie.
- Statystyki (`analiza.py`): ta sama oferta z kilku wersji gazetki (np. „Z ladą tradycyjną”)
  liczona jest raz, a nakładające się okresy promocji są scalane w jedną promocję.

## Gdy coś nie działa

- **Czerwony ✗ w Actions:** otwórz log kroku „Pobranie gazetek”. „HTTP 403” oznacza, że blix
  zablokował serwery GitHuba. Wtedy można uruchamiać `python scraper.py` na własnym komputerze.
- **Brak uprawnień do push:** Settings → Actions → General → Workflow permissions →
  *Read and write permissions* → Save.
- **Automat przestał się uruchamiać:** GitHub wyłącza harmonogram po 60 dniach bez aktywności
  w repo. Włączysz go ponownie w zakładce Actions (*Enable workflow*).
- **Testy:** `python tests/test_scraper.py`
