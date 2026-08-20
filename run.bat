@echo off
chcp 65001 > nul
title Telegram Dev Bridge - AI Agent

echo ===================================================
echo   Telegram Dev Bridge Ishga Tushirilmoqda...
echo ===================================================
echo.

if not exist .env (
    echo [OGOHLANTIRISH] .env fayli topilmadi!
    echo .env.example dan nusxa olinmoqda...
    copy .env.example .env
    echo.
    echo Iltimos, avval .env faylini ochib, BOT_TOKEN va ADMIN_IDS ni kiriting!
    notepad .env
    pause
    exit /b 1
)

python bot.py

if %errorlevel% neq 0 (
    echo.
    echo [XATO] Bot to'xtadi yoki xatolik yuz berdi.
    pause
)
