@echo off
setlocal enabledelayedexpansion

echo.
echo  ====================================================
echo   vigil -- Windows EXE builder
echo  ====================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install Python 3.11+ and add it to PATH.
    pause & exit /b 1
)

:: Install / upgrade build deps
echo  [1/4] Installing build dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet ".[windows]"
python -m pip install --quiet "pyinstaller>=6.0"

:: Clean previous build
echo  [2/4] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

:: Build
echo  [3/4] Building vigil.exe  (this takes ~60 seconds)...
python -m PyInstaller vigil.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo  [ERROR] PyInstaller failed. See output above.
    pause & exit /b 1
)

:: Verify
if not exist "dist\vigil.exe" (
    echo  [ERROR] dist\vigil.exe not created -- build may have failed silently.
    pause & exit /b 1
)

echo  [4/4] Done!
echo.
echo  Output:  dist\vigil.exe
echo.
echo  Run it:
echo    dist\vigil.exe
echo    dist\vigil.exe --config
echo    dist\vigil.exe --log
echo    dist\vigil.exe --version
echo.
echo  NOTE: For accurate CPU wattage on Windows, run
echo        LibreHardwareMonitor as Administrator first.
echo.
pause
