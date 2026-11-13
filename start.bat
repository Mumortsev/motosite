@echo off
chcp 65001 > nul
title МОТО-АЛЬЯНС КУБАНЬ — ИИ Сервер

echo ========================================================
echo   Запуск локального сервера МОТО-АЛЬЯНС КУБАНЬ
echo   (DeepInfra / DeepSeek V3/v4.1 с кэшированием)
echo ========================================================

:: Проверяем наличие py
where py >nul 2>nul
if %errorlevel% equ 0 (
    start http://localhost:8000
    py "%~dp0server.py"
    goto end
)

:: Проверяем команду python
where python >nul 2>nul
if %errorlevel% equ 0 (
    start http://localhost:8000
    python "%~dp0server.py"
    goto end
)

echo Ошибка: Python не найден в системе. Установите Python 3.
pause

:end
