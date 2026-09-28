@echo off
chcp 65001 >nul
set "URL=https://github.com/LivingMummy/gazetki/raw/excel/gazetki.xlsx"
set "DEST=%~dp0gazetki.xlsx"
echo Pobieram najnowszy Excel z GitHuba...
curl -L -f -s -S -o "%DEST%.part" "%URL%"
if errorlevel 1 (
  echo.
  echo Nie udalo sie pobrac pliku. Sprawdz internet albo czy automat na GitHubie juz dzialal.
  del "%DEST%.part" 2>nul
  pause
  exit /b 1
)
move /y "%DEST%.part" "%DEST%" >nul
if errorlevel 1 (
  echo Zamknij gazetki.xlsx w Excelu i uruchom ponownie.
  pause
  exit /b 1
)
echo Zapisano: %DEST%
start "" "%DEST%"
