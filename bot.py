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
from handlers import start, cleaner, media_downloader, voice_handler, text_keep_handler, dialogue_handler
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
    from aiogram.types import MenuButtonWebApp, WebAppInfo
    from config import WEBAPP_URL

    commands = [
        BotCommand(command="start", description="🚀 Bosh menyuni ochish"),
        BotCommand(command="app", description="🚀 Super Ilova (25 ta so'z & Audio)"),
        BotCommand(command="dialogue", description="🗣️ Jonli Dialoglar (Taksi, Mehmonxona...)"),
        BotCommand(command="words", description="📚 So'zlar hisoblagichi & Lug'at"),
        BotCommand(command="reminders", description="⏰ Faol vaqtli eslatmalarni ko'rish"),
        BotCommand(command="notes", description="📋 Saqlangan matnli qaydlarni ko'rish"),
        BotCommand(command="dl", description="📥 Video & MP3 yuklash (Telegram, YouTube, Insta, TikTok)"),
        BotCommand(command="mp3", description="🎵 Faqat MP3 Audio yuklash (320kbps)"),
        BotCommand(command="cleaner", description="🧹 Telegram hisobni tozalash"),
        BotCommand(command="help", description="📖 To'liq qo'llanma"),
    ]

    await bot.set_my_commands(commands)
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Super ilova", web_app=WebAppInfo(url=WEBAPP_URL))
        )
    except Exception as e:
        logger.warning(f"Menyu tugmasini sozlash xatosi: {e}")


async def notify_users_on_startup(bot: Bot):
    """Bot ishga tushganda yangi versiya bo'lsa barcha foydalanuvchilarga yangiliklarni yuborish."""
    try:
        from services.release_service import notify_all_users_of_new_release
        await notify_all_users_of_new_release(bot)
    except Exception as e:
        logger.warning(f"Barcha foydalanuvchilarga yangilanish bildirishnomasi xatosi: {e}")


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

    # Router'lar: start, cleaner, media_downloader, voice_handler, text_keep_handler, dialogue_handler
    dp.include_router(start.router)
    dp.include_router(dialogue_handler.router)
    dp.include_router(cleaner.router)
    dp.include_router(media_downloader.router)
    dp.include_router(voice_handler.router)       # 🎤 STT + Keep + Calendar tasdiqi
    dp.include_router(text_keep_handler.router)   # 📝 Matn xabar → Keep tasdiqi

    # Buyruqlar menyusi va xabarnoma
    await setup_bot_commands(bot)
    await notify_users_on_startup(bot)

    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
    logger.info(f"Ruxsat berilgan Admin ID lar: {list(ADMIN_IDS)}")
    logger.info("Bot Telegram xabarlarini tinglamoqda...")

    # Orqa fonda ko'p vaqtli eslatmalar skeduleri (Background Scheduler)
    from services.reminder_service import start_reminder_scheduler
    scheduler_task = asyncio.create_task(start_reminder_scheduler(bot))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), drop_pending_updates=True)
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except (asyncio.CancelledError, Exception):
            pass
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
