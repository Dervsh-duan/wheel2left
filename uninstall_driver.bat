@echo off
chcp 65001 >nul
title Wheel2Left 驱动卸载

echo ============================================
echo   Wheel2Left 驱动卸载
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

echo [1/3] 停止并删除驱动服务...
for %%S in (mouse keyboard) do (
    sc stop %%S >nul 2>&1
    sc delete %%S >nul 2>&1
    if errorlevel 1 (
        echo       %%S 服务不存在或已在删除队列中。
    ) else (
        echo       %%S 服务已标记删除。
    )
)

echo.
echo [2/3] 备份并清理类过滤注册...
set "HERE=%~dp0"
set "MCLS=HKLM\SYSTEM\CurrentControlSet\Control\Class\{4D36E96F-E325-11CE-BFC1-08002BE10318}"
set "KCLS=HKLM\SYSTEM\CurrentControlSet\Control\Class\{4D36E96B-E325-11CE-BFC1-08002BE10318}"
reg export "%MCLS%" "%HERE%backup_mouse_class.reg" /y >nul 2>&1
reg export "%KCLS%" "%HERE%backup_keyboard_class.reg" /y >nul 2>&1
reg add "%MCLS%" /v UpperFilters /t REG_MULTI_SZ /d "mouclass" /f >nul 2>&1
reg add "%KCLS%" /v UpperFilters /t REG_MULTI_SZ /d "kbdclass" /f >nul 2>&1
echo       已恢复为系统默认值 mouclass / kbdclass。
echo       原设置已备份到本目录的 backup_*.reg。
echo       如果之前有厂商过滤驱动，双击对应 .reg 可还原。

echo.
echo [3/3] 完成。
echo.
echo   请重启电脑。
echo   如果你另外装过鼠标厂商的过滤驱动（罗技、雷蛇等），
echo   它们会被一并清掉，需要重装厂商驱动。
echo.
pause
