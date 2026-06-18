@echo off
cd /d "%~dp0"
chcp 65001 > nul

title UkrRadioOnline Compiler
echo ========================================================
echo  ПАКУВАННЯ ПРОЄКТУ В STANDALONE EXE
echo ========================================================
echo.

REM 1. Перевірка наявності віртуального середовища
if not exist ".venv" (
    echo [ПОМИЛКА] Віртуальне середовище .venv не знайдено.
    echo Запустіть спочатку _START_.bat для налаштування проєкту.
    pause
    exit /b 1
)

REM 2. Перевірка та встановлення PyInstaller у віртуальному середовищі
echo Перевірка наявності PyInstaller...
".venv\Scripts\python.exe" -m pip show pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Встановлення PyInstaller у віртуальне середовище...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo [ПОМИЛКА] Не вдалося встановити PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo PyInstaller вже встановлено у .venv.
)

echo.
echo ========================================================
echo  Запуск процесу компіляції...
echo ========================================================
echo.

REM 3. Компіляція програми через PyInstaller з оптимізацією розміру (виключаємо важкі модулі Qt та стискаємо через UPX)
".venv\Scripts\pyinstaller" --onefile --windowed --name="UkrRadioOnline" ^
    --upx-dir="upx-win64" ^
    --exclude-module PyQt6.QtWebEngineCore ^
    --exclude-module PyQt6.QtWebEngineWidgets ^
    --exclude-module PyQt6.QtSql ^
    --exclude-module PyQt6.QtXml ^
    --exclude-module PyQt6.Qt3D ^
    --exclude-module PyQt6.QtDesigner ^
    main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ПОМИЛКА] Під час компіляції сталася помилка.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Компіляцію успішно завершено!
echo ========================================================
echo.
echo Готовий файл знаходиться в папці: dist\UkrRadioOnline.exe
echo.
echo Очищення тимчасових файлів збірки (build, spec)...
if exist "build" rd /s /q "build"
if exist "UkrRadioOnline.spec" del /f /q "UkrRadioOnline.spec"
echo Очищення завершено.
echo.
pause
