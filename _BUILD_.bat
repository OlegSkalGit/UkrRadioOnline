@echo off
cd /d "%~dp0"

title UkrRadioOnline Compiler
echo ========================================================
echo  Packaging UkrRadioOnline into standalone EXE
echo ========================================================
echo.

REM 1. Check virtual environment
if not exist ".venv" (
    echo [ERROR] Virtual environment .venv not found.
    echo Please run _START_.bat first to set up the project.
    pause
    exit /b 1
)

REM 2. Check and install PyInstaller inside .venv
echo Checking PyInstaller...
".venv\Scripts\python.exe" -m pip show pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Installing PyInstaller in virtual environment...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo PyInstaller is already installed.
)

echo.
echo ========================================================
echo  Starting compilation...
echo ========================================================
echo.

REM 3. Compile with PyInstaller
".venv\Scripts\pyinstaller" --onefile --windowed --name="UkrRadioOnline" --upx-dir="upx-win64" --exclude-module PyQt6.QtWebEngineCore --exclude-module PyQt6.QtWebEngineWidgets --exclude-module PyQt6.QtSql --exclude-module PyQt6.QtXml --exclude-module PyQt6.Qt3D --exclude-module PyQt6.QtDesigner main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Compilation failed.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Compilation completed successfully!
echo ========================================================
echo.
echo Executable is located at: dist\UkrRadioOnline.exe
echo.
echo Cleaning temporary build files...
if exist "build" rd /s /q "build"
if exist "UkrRadioOnline.spec" del /f /q "UkrRadioOnline.spec"
echo Cleanup complete.
echo.
pause
