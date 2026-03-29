@echo off
setlocal

REM Build DEKT GUI for Windows with PyInstaller.
cd /d %~dp0

if not exist .venv (
  py -3 -m venv .venv
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :error

python -m pip install --upgrade pip
if errorlevel 1 goto :error

pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --windowed --name DEKT-GUI --paths . main.py
if errorlevel 1 goto :error

echo.
echo Build completed.
echo App folder: dist\DEKT-GUI
echo Executable: dist\DEKT-GUI\DEKT-GUI.exe
goto :eof

:error
echo.
echo Build failed.
exit /b 1
