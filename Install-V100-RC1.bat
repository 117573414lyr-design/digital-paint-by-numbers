@echo off
setlocal
chcp 65001 >nul
title 数字油画生产软件 V100 RC1 - 安装与启动

set "APPDIR=%LOCALAPPDATA%\DigitalPaintV100RC1"
set "VENV=%APPDIR%\venv"
set "PKGURL=https://github.com/117573414lyr-design/digital-paint-by-numbers/archive/refs/heads/feature/windows-v0.1.zip"

echo.
echo ============================================
echo   数字油画生产软件 V100 RC1
echo   一键安装 / 更新 / 启动
echo ============================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY=py -3.12"
    goto :python_ok
)

where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
    goto :python_ok
)

echo 未检测到 Python 3.12，尝试通过 winget 安装...
where winget >nul 2>nul
if not %errorlevel%==0 (
    echo 无法自动安装 Python，请先安装 Python 3.12 后重试。
    pause
    exit /b 1
)
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if not %errorlevel%==0 (
    echo Python 自动安装失败。
    pause
    exit /b 1
)
set "PY=py -3.12"

:python_ok
if not exist "%APPDIR%" mkdir "%APPDIR%"
if not exist "%VENV%\Scripts\python.exe" (
    echo 创建独立运行环境...
    %PY% -m venv "%VENV%"
    if not %errorlevel%==0 (
        echo 创建运行环境失败。
        pause
        exit /b 1
    )
)

echo 更新 pip...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip

echo 安装 / 更新数字油画软件 V100 RC1...
"%VENV%\Scripts\python.exe" -m pip install --upgrade --force-reinstall "%PKGURL%"
if not %errorlevel%==0 (
    echo 安装失败，请检查网络后重试。
    pause
    exit /b 1
)

echo 启动数字油画生产软件...
start "" "%VENV%\Scripts\digital-paint.exe"
exit /b 0
