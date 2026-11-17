@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title LAN Fighter - Windows EXE Builder

echo ==========================================
echo  LAN Fighter 3.0 - Windows EXE Builder
echo ==========================================

where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python 3.10+ not found. Install Python first.
        pause
        exit /b 1
    )
    set "PY=python"
)

%PY% -m pip install --upgrade pip
if errorlevel 1 goto :failed
%PY% -m pip install -r requirements.txt "pyinstaller>=6,<7"
if errorlevel 1 goto :failed

set "ASSET_FLAG="
if exist "assets\" set "ASSET_FLAG=--add-data assets;assets"

%PY% -m PyInstaller --noconfirm --clean ^
    --onedir ^
    --windowed ^
    --name LANFighter ^
    --collect-all pygame ^
    --hidden-import pygame._freetype ^
    --hidden-import fighter.skeleton ^
    --hidden-import fighter.characters ^
    --hidden-import fighter.attacks ^
    --hidden-import fighter.combat ^
    --hidden-import fighter.network ^
    --hidden-import fighter.config ^
    --hidden-import fighter.audio ^
    --hidden-import fighter.assets ^
    %ASSET_FLAG% ^
    main.py

if errorlevel 1 goto :failed

echo.
echo ==========================================
echo  SUCCESS: dist\LANFighter\
echo  下一步：打开 Inno Setup Compiler，加载 setup.iss，点 Compile
echo ==========================================
echo.
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Read the error messages above.
pause
exit /b 1
