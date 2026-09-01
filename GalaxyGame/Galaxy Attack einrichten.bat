@echo off
setlocal EnableExtensions
title Galaxy Attack - Einrichtung
color 0B

echo.
echo   ========================================================
echo      GALAXY ATTACK  -  Einrichtung
echo   ========================================================
echo.
echo   Diese Datei legt das Spiel im Ordner
echo      Desktop\Galaxy Attack
echo   ab und erstellt eine Verknuepfung auf dem Desktop.
echo.

rem ---------------------------------------------------------------
rem  1. space_shooter.py suchen: erst neben dieser Datei, dann in
rem     den ueblichen Download-Ordnern.
rem ---------------------------------------------------------------
set "SRC="
if exist "%~dp0space_shooter.py" set "SRC=%~dp0"
if not defined SRC if exist "%USERPROFILE%\Downloads\space_shooter.py" set "SRC=%USERPROFILE%\Downloads\"
if not defined SRC if exist "%USERPROFILE%\Desktop\space_shooter.py" set "SRC=%USERPROFILE%\Desktop\"

if not defined SRC (
  echo   [Fehler] space_shooter.py wurde nicht gefunden.
  echo.
  echo   Lege diese Datei in denselben Ordner wie space_shooter.py
  echo   und starte sie dort noch einmal per Doppelklick.
  echo.
  pause
  exit /b 1
)
echo   Spieldatei gefunden in: %SRC%

rem ---------------------------------------------------------------
rem  2. Python suchen. pythonw startet ohne schwarzes Konsolenfenster.
rem ---------------------------------------------------------------
set "PYW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%i"
set "PY="
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if not defined PYW set "PYW=%PY%"
if not defined PY set "PY=%PYW%"

if not defined PYW (
  echo.
  echo   [Fehler] Python wurde nicht gefunden.
  echo   Installiere Python von python.org oder aus dem Microsoft Store
  echo   und starte diese Einrichtung danach erneut.
  echo.
  pause
  exit /b 1
)
echo   Python gefunden:        %PYW%

rem ---------------------------------------------------------------
rem  3. pygame sicherstellen
rem ---------------------------------------------------------------
echo.
echo   Pruefe pygame ...
"%PY%" -c "import pygame" 2>nul
if errorlevel 1 (
  echo   pygame fehlt - wird jetzt installiert ...
  "%PY%" -m pip install --quiet pygame
  if errorlevel 1 (
    echo   [Fehler] pygame konnte nicht installiert werden.
    pause
    exit /b 1
  )
)
echo   pygame ist bereit.

rem ---------------------------------------------------------------
rem  4. Dateien auf den Desktop kopieren
rem ---------------------------------------------------------------
set "DEST=%USERPROFILE%\Desktop\Galaxy Attack"
if not exist "%DEST%" mkdir "%DEST%"
copy /y "%SRC%space_shooter.py" "%DEST%\" >nul
if exist "%SRC%galaxy_attack.ico" copy /y "%SRC%galaxy_attack.ico" "%DEST%\" >nul
echo   Dateien kopiert nach:   %DEST%

rem Notfall-Start mit sichtbarer Konsole, falls einmal etwas klemmt
> "%DEST%\Galaxy Attack (mit Konsole).bat" echo @echo off
>>"%DEST%\Galaxy Attack (mit Konsole).bat" echo title Galaxy Attack
>>"%DEST%\Galaxy Attack (mit Konsole).bat" echo cd /d "%%~dp0"
>>"%DEST%\Galaxy Attack (mit Konsole).bat" echo python space_shooter.py
>>"%DEST%\Galaxy Attack (mit Konsole).bat" echo if errorlevel 1 pause

rem ---------------------------------------------------------------
rem  5. Desktop-Verknuepfung anlegen
rem ---------------------------------------------------------------
set "GA_PYW=%PYW%"
set "GA_DEST=%DEST%"
set "PS=%TEMP%\galaxy_attack_shortcut.ps1"

> "%PS%" echo $W = New-Object -ComObject WScript.Shell
>>"%PS%" echo $S = $W.CreateShortcut^("$env:USERPROFILE\Desktop\Galaxy Attack.lnk"^)
>>"%PS%" echo $S.TargetPath = $env:GA_PYW
>>"%PS%" echo $S.Arguments = '"' + $env:GA_DEST + '\space_shooter.py"'
>>"%PS%" echo $S.WorkingDirectory = $env:GA_DEST
>>"%PS%" echo $S.IconLocation = $env:GA_DEST + '\galaxy_attack.ico'
>>"%PS%" echo $S.Description = 'Galaxy Attack - Neon Vector Edition'
>>"%PS%" echo $S.Save^(^)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%"
if errorlevel 1 (
  echo.
  echo   [Hinweis] Die Verknuepfung konnte nicht angelegt werden.
  echo   Du kannst das Spiel trotzdem starten:
  echo   %DEST%\Galaxy Attack ^(mit Konsole^).bat
) else (
  echo   Verknuepfung erstellt:  Desktop\Galaxy Attack
)
del "%PS%" 2>nul

echo.
echo   ========================================================
echo      Fertig. Doppelklick auf "Galaxy Attack" am Desktop.
echo   ========================================================
echo.
echo   Steuerung: Pfeiltasten fliegen, Leertaste feuern,
echo              ESC pausiert, F11 schaltet auf Vollbild.
echo.
choice /c JN /n /m "   Spiel jetzt starten? [J/N] "
if errorlevel 2 goto ende
start "" "%PYW%" "%DEST%\space_shooter.py"

:ende
echo.
timeout /t 3 >nul
endlocal
