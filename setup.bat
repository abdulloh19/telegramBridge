@echo off
chcp 65001 > nul
echo ===================================================
echo   Telegram Dev Bridge - O'rnatish Skripti
echo ===================================================
echo.

echo [1/3] Python o'rnatilganligi tekshirilmoqda...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [XATO] Python topilmadi! Iltimos, Python 3.10+ o'rnating va PATH ga qo'shing.
    pause
    exit /b 1
)

echo [2/3] Kerakli kutubxonalar o'rnatilmoqda (pip install)...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [XATO] Kutubxonalarni o'rnatishda xatolik yuz berdi!
    pause
    exit /b 1
)

echo.
echo [3/3] Konfiguratsiya (.env) tekshirilmoqda...
if not exist .env (
    copy .env.example .env
    echo [.env] fayli yaratildi! Iltimos, uni ochib BOT_TOKEN va ADMIN_IDS ni kiriting.
) else (
    echo [.env] fayli mavjud.
)

echo.
echo ===================================================
echo   O'rnatish muvaffaqiyatli yakunlandi!
echo   Botni ishga tushirish uchun run.bat ni bosing.
echo ===================================================
pause
