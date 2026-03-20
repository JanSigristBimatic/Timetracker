@echo off
chcp 65001 >nul
title TimeTracker - Installation

echo ============================================
echo        TimeTracker - Installation
echo ============================================
echo.

:: Check for Python installation
echo [1/3] Pruefe Python-Installation...
py --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo FEHLER: Python wurde nicht gefunden!
    echo Bitte installieren Sie Python von https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('py --version 2^>^&1') do set PYTHON_VERSION=%%i
echo       Python %PYTHON_VERSION% gefunden.
echo.

:: Upgrade pip
echo [2/3] Aktualisiere pip...
py -m pip install --upgrade pip --quiet
echo       pip aktualisiert.
echo.

:: Install requirements
echo [3/3] Installiere Abhaengigkeiten...
echo.
echo       Dies kann einige Minuten dauern...
echo.

py -m pip install -r "%~dp0requirements.txt"

if errorlevel 1 (
    echo.
    echo ============================================
    echo FEHLER: Installation fehlgeschlagen!
    echo Bitte ueberpruefen Sie die Fehlermeldungen.
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo    Installation erfolgreich abgeschlossen!
echo ============================================
echo.

:: Ask to start TimeTracker
set /p START_APP="Moechten Sie TimeTracker jetzt starten? (j/n): "

if /i "%START_APP%"=="j" (
    echo.
    echo Starte TimeTracker...
    cd /d "%~dp0"
    py src/main.py
) else if /i "%START_APP%"=="ja" (
    echo.
    echo Starte TimeTracker...
    cd /d "%~dp0"
    py src/main.py
) else (
    echo.
    echo Sie koennen TimeTracker spaeter mit 'start.bat' oder 'py src/main.py' starten.
    echo.
    pause
)
