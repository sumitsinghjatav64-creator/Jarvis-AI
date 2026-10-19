@echo off
setlocal
cd /d "%~dp0"

echo Building Mark LV for Windows...
python -m PyInstaller --noconfirm MarkLV.spec

if errorlevel 1 (
    echo.
    echo Build failed. Install dependencies with: python setup.py
    echo Then install PyInstaller with: python -m pip install pyinstaller
    pause
    exit /b 1
)

echo.
echo Build complete: dist\MarkLV\MarkLV.exe
echo Copy or zip the entire dist\MarkLV folder to distribute the app.
pause