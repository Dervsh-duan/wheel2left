@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   构建 Wheel2Left
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 找不到 python，请先安装 Python 3.11+ 并加入 PATH。
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo 未检测到 PyInstaller，正在安装...
    python -m pip install --upgrade pyinstaller
)

if not exist "driver\Interception\library\x64\interception.dll" (
    echo [错误] 缺少 Interception 库文件。
    echo.
    echo   1. 下载 https://github.com/oblitum/Interception/releases/download/v1.0.1/Interception.zip
    echo   2. 解压，把里面的 Interception 目录整个放到 driver\ 下
    echo      正确路径：driver\Interception\library\x64\interception.dll
    echo.
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
    --name Wheel2Left --icon assets\app.ico --version-file version_info.txt ^
    --paths src src\main.py
if errorlevel 1 (
    echo [错误] 打包失败。
    pause
    exit /b 1
)

copy /y "driver\Interception\library\x64\interception.dll" "dist\" >nul

echo.
echo 构建完成：
echo   dist\Wheel2Left.exe
echo   dist\interception.dll   ^(必须与 exe 放在同一目录^)
echo.
pause
