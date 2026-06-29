@echo off
chcp 65001 > nul
echo =====================================
echo  Утрау — Обновление дашборда
echo =====================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\download.ps1"
echo.
echo Готово! Откройте finance.html в браузере.
pause
