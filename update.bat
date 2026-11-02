@echo off
chcp 65001 > nul
echo =====================================
echo  Утрау — Обновление дашборда
echo =====================================
echo.
rem 02.11.2026: полный прогон без публикации - скачать, собрать, проверить свежесть, зашифровать для сайта
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\auto_update.ps1" -NoPush
echo.
echo Готово! Данные обновлены и зашифрованы (data\enc). На сайт их отправит конвейер в 10:00.
pause
