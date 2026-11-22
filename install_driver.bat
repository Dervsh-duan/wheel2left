@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Wheel2Left 驱动安装

echo ============================================
echo   Wheel2Left 驱动安装
echo ============================================
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 需要管理员权限。
    echo        请右键本文件，选择「以管理员身份运行」。
    echo.
    pause
    exit /b 1
)

set "HERE=%~dp0"
set "INST=%HERE%Interception\command line installer\install-interception.exe"
if not exist "%INST%" (
    echo [错误] 找不到 Interception 安装器：
    echo        %INST%
    echo.
    echo        请确认解压后的文件夹里包含 Interception 目录。
    pause
    exit /b 1
)

echo [1/4] 运行 Interception 安装器...
"%INST%" /install
timeout /t 3 /nobreak >nul

echo.
echo [2/4] 检查驱动服务...
sc query mouse | find "RUNNING" >nul
if not errorlevel 1 goto mouse_ok

echo       服务未运行，尝试修复...
sc query mouse >nul 2>&1
if errorlevel 1 (
    sc create mouse type= kernel start= demand error= normal ^
        binPath= "\SystemRoot\System32\drivers\mouse.sys" ^
        DisplayName= "Mouse Upper Filter Driver" >nul
)
sc start mouse >nul 2>&1
sc query mouse | find "RUNNING" >nul
if errorlevel 1 (
    echo       [警告] mouse 服务仍未运行，请重启后再试一次。
) else (
    echo       mouse 服务已启动。
)
goto check_filters

:mouse_ok
echo       mouse 服务已在运行。

:check_filters
echo.
echo [3/4] 检查类过滤注册...
set "MCLS=HKLM\SYSTEM\CurrentControlSet\Control\Class\{4D36E96F-E325-11CE-BFC1-08002BE10318}"
reg query "%MCLS%" /v UpperFilters 2>nul | find /i "mouse" >nul
if errorlevel 1 (
    echo       写入 Mouse UpperFilters...
    reg add "%MCLS%" /v UpperFilters /t REG_MULTI_SZ /d "mouse\0mouclass" /f >nul
) else (
    echo       UpperFilters 已包含 mouse。
)

echo.
echo [4/4] 完成。
echo.
echo   *** 必须重启电脑，驱动才会挂到鼠标上 ***
echo.
echo   重启后双击 Wheel2Left.exe（UAC 点「是」）即可使用。
echo.
pause
endlocal
