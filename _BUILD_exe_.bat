@echo off
cd /d "%~dp0"
chcp 1251 > nul

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
)

REM 2.5. Check and set up UPX if missing
if not exist "upx-win64" (
    echo.
    echo ========================================================
    echo  UPX compiler not found. Downloading UPX v5.2.0...
    echo ========================================================
    powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/upx/upx/releases/download/v5.2.0/upx-5.2.0-win64.zip' -OutFile 'upx.zip'"
    if errorlevel 1 (
        echo.
        echo [WARNING] Failed to download UPX. Compilation will proceed without UPX compression.
        echo.
    ) else (
        echo Extracting UPX...
        powershell -Command "Expand-Archive -Path 'upx.zip' -DestinationPath '.'"
        if exist "upx-5.2.0-win64" (
            ren "upx-5.2.0-win64" "upx-win64"
            echo UPX installed successfully.
        ) else (
            echo.
            echo [WARNING] Extraction folder not found. Compilation will proceed without UPX.
            echo.
        )
        if exist "upx.zip" del /f /q "upx.zip"
    )
)

echo.
echo ========================================================
echo  Starting compilation...
echo ========================================================
echo.

REM 3. Compile with PyInstaller using the spec file
".venv\Scripts\python.exe" -m PyInstaller --upx-dir="upx-win64" UkrRadioOnline.spec

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
echo Cleanup complete.
echo.
pause
