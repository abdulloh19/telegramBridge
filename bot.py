import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, ADMIN_IDS
from middlewares.auth import AuthMiddleware
from handlers import start, cleaner, media_downloader
from utils.logger import logger
from utils.helpers import escape_html


BANNER = r"""
================================================================
  _______ _____    ____   ______   _____  ______  _      
 |__   __|  __ \  |  _ \ / __ \ \ / /   \|  ____|| |     
    | |  | |  | | | |_) | |  | \ V /| |\ | |__   | |     
    | |  | |  | | |  _ <| |  | |> < | |/ |  __|  | |     
    | |  | |__| | | |_) | |__| / . \|  \ | |____ | |____ 
    |_|  |_____/  |____/ \____/_/ \_\___/|______||______|
         V I D E O   D O W N L O A D E R   &   C L E A N E R
================================================================
"""


async def setup_bot_commands(bot: Bot):
    """Telegram ilovasida menyu buyruqlarini ro'yxatdan o'tkazish."""
    commands = [
        BotCommand(command="start", description="🚀 Bosh menyuni ochish"),
        BotCommand(command="dl", description="📥 Video & MP3 yuklash (Telegram, YouTube, Insta, TikTok)"),
        BotCommand(command="mp3", description="🎵 Faqat MP3 Audio yuklash (320kbps)"),
        BotCommand(command="cleaner", description="🧹 Telegram hisobni tozalash"),
        BotCommand(command="help", description="📖 To'liq qo'llanma"),
    ]

    await bot.set_my_commands(commands)


async def notify_admins_on_startup(bot: Bot):
    """Bot ishga tushganda adminlarga xabar yuborish."""
    if not ADMIN_IDS:
        logger.warning("DIQQAT: .env faylida ADMIN_IDS ko'rsatilmagan! Bot faqat adminlar uchun ishlaydi.")
        return

    text = (
        "🟢 <b>Bot muvaffaqiyatli yangilandi va ishga tushdi! 🚀</b>\n\n"
        "✨ <b>Yangi Imkoniyatlar:</b>\n"
        "• 🎵 <b>Alohida MP3 Bo'limi</b> (/mp3 yoki menyudan)\n"
        "• 📥 <b>To'g'ridan-to'g'ri Bot Chatga Yetkazish</b> (Izbrannoega emas)\n"
        "• 🎬 + 🎵 <b>Video bilan birga 320kbps MP3 ham keladi</b>\n"
        "• 🧹 <b>Telegram Hisob Tozalovchi</b> (/cleaner)\n\n"
        "👉 Yangilangan menyuni ko'rish uchun <b>/start</b> bosing!"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Admin ({admin_id}) ga bildirishnoma yuborilmadi: {e}")


async def main():
    print(BANNER)
    logger.info("Bot ishga tushirilmoqda...")

    # 1. Render.com bepul Web Service portini ishga tushirish
    import os
    port_str = os.getenv("PORT")
    if port_str:
        try:
            from aiohttp import web
            port = int(port_str)
            app = web.Application()
            async def _health_handler(req):
                return web.Response(text="🟢 Telegram Downloader & Cleaner 24/7 faol!", content_type="text/plain")
            app.router.add_get("/", _health_handler)
            app.router.add_get("/health", _health_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            logger.info(f"Render Web Service serveri 0.0.0.0:{port} da ishga tushdi.")
        except Exception as web_err:
            logger.warning(f"Web server xatosi (zararsiz): {web_err}")

    # 2. BOT_TOKEN mavjudligini tekshirish
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("❌ XATOLIK: BOT_TOKEN topilmadi!")
        if port_str:
            while True:
                await asyncio.sleep(3600)
        sys.exit(1)

    # 3. Proksi tekshiruvi (PythonAnywhere va boshqalar)
    import platform
    from pathlib import Path
    from aiogram.client.session.aiohttp import AiohttpSession

    proxy_url = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or os.getenv("HTTPS_PROXY")
    if not proxy_url:
        is_pa = any([
            "PYTHONANYWHERE_DOMAIN" in os.environ,
            "PYTHONANYWHERE_SITE" in os.environ,
            os.path.exists("/var/log/pythonanywhere"),
            "pythonanywhere" in os.environ.get("HOME", "").lower(),
            "zubayr" in str(Path.home()),
            "pythonanywhere" in platform.node().lower()
        ])
        if is_pa:
            proxy_url = "http://proxy.server:3128"
            logger.info("PythonAnywhere proksi ulandi: http://proxy.server:3128")

    session = AiohttpSession(proxy=proxy_url) if proxy_url else None

    # 4. Bot va Dispatcher yaratish
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    # Xavfsizlik Middleware
    auth_middleware = AuthMiddleware()
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)

    # Faqat 3 ta router: start, cleaner, media_downloader
    dp.include_router(start.router)
    dp.include_router(cleaner.router)
    dp.include_router(media_downloader.router)

    # Buyruqlar menyusi va xabarnoma
    await setup_bot_commands(bot)
    await notify_admins_on_startup(bot)

    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
    logger.info(f"Ruxsat berilgan Admin ID lar: {list(ADMIN_IDS)}")
    logger.info("Bot Telegram xabarlarini tinglamoqda...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
