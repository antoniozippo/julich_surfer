@echo off
rem Build dist\Julich 3D Brain Surfer\Julich 3D Brain Surfer.exe (Windows, onedir).
setlocal
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required: install it from https://www.python.org
  echo and tick "Add python.exe to PATH" during setup.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install -e ".[qt,windows]"
if errorlevel 1 exit /b 1

if not exist "packaging\AppIcon.ico" (
  echo Rendering the icon from the atlas ...
  ".venv\Scripts\python.exe" packaging\make_icon.py
  if errorlevel 1 exit /b 1
)

".venv\Scripts\pyinstaller.exe" --noconfirm packaging\napari_julich_surfer_windows.spec
if errorlevel 1 exit /b 1

echo.
echo Built: %CD%\dist\Julich 3D Brain Surfer\Julich 3D Brain Surfer.exe
echo Zip that whole folder to move it to another PC; no Python is needed there.
