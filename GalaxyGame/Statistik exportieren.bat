@echo off
setlocal EnableExtensions
title Galaxy Attack - Statistik exportieren
color 0B

echo.
echo   ========================================================
echo      GALAXY ATTACK  -  Statistik exportieren
echo   ========================================================
echo.
echo   Diese Datei macht aus deiner Statistik-Datenbank eine
echo   normale Textdatei, die du anhaengen und verschicken kannst.
echo.

rem ---------------------------------------------------------------
rem  space_shooter.py suchen: erst neben dieser Datei, dann im
rem  installierten Spielordner auf dem Desktop.
rem ---------------------------------------------------------------
set "SRC="
if exist "%~dp0space_shooter.py" set "SRC=%~dp0space_shooter.py"
if not defined SRC if exist "%USERPROFILE%\Desktop\Galaxy Attack\space_shooter.py" (
    set "SRC=%USERPROFILE%\Desktop\Galaxy Attack\space_shooter.py"
)
if not defined SRC if exist "%USERPROFILE%\OneDrive\Desktop\Galaxy Attack\space_shooter.py" (
    set "SRC=%USERPROFILE%\OneDrive\Desktop\Galaxy Attack\space_shooter.py"
)

if not defined SRC (
    echo   [!] space_shooter.py wurde nicht gefunden.
    echo.
    echo       Lege diese Datei in denselben Ordner wie das Spiel
    echo       und starte sie noch einmal.
    echo.
    pause
    exit /b 1
)

echo   Spiel gefunden:
echo      %SRC%
echo.

rem ---------------------------------------------------------------
rem  Python finden - erst python im Pfad, sonst der py-Launcher.
rem ---------------------------------------------------------------
rem  Dasselbe Muster wie in "Galaxy Attack einrichten.bat" - es liefert den
rem  vollen Pfad und funktioniert auch dort, wo "where" mehrere Treffer hat.
set "PY="
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY (
    for /f "delims=" %%i in ('where py 2^>nul') do if not defined PY set "PY=%%i"
)

if not defined PY (
    echo   [!] Python wurde nicht gefunden.
    echo       Installiere Python von https://www.python.org/downloads/
    echo       und setze dabei den Haken bei "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo   Exportiere ...
echo.
"%PY%" "%SRC%" --export
echo.

rem ---------------------------------------------------------------
rem  Ordner mit der fertigen Datei oeffnen, damit man sie gleich
rem  in den Chat ziehen kann.
rem ---------------------------------------------------------------
for %%F in ("%SRC%") do set "GAMEDIR=%%~dpF"
if exist "%GAMEDIR%galaxy_attack_export.txt" (
    echo   Fertig. Der Ordner oeffnet sich jetzt - zieh die Datei
    echo      galaxy_attack_export.txt
    echo   einfach in den Chat.
    echo.
    explorer /select,"%GAMEDIR%galaxy_attack_export.txt"
) else (
    echo   [!] Es wurde keine Exportdatei erzeugt. Vermutlich hast du
    echo       auf diesem Rechner noch keine Partie gespielt.
)

echo.
pause
