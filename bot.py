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

from config import BOT_TOKEN, ADMIN_IDS, DEFAULT_WORKING_DIR
from middlewares.auth import AuthMiddleware
from handlers import start, files, terminal, system, ai_agent, cleaner, media_downloader
from utils.logger import logger
from utils.helpers import escape_html


BANNER = r"""
================================================================
  _______   _                               _____             
 |__   __| | |                             |  __ \            
    | | ___| | ___  __ _ _ __ __ _ _ __ ___ | |  | | _____   __
    | |/ _ \ |/ _ \/ _` | '__/ _` | '_ ` _ \| |  | |/ _ \ \ / /
    | |  __/ |  __/ (_| | | | (_| | | | | | | |__| |  __/\ V / 
    |_|\___|_|\___|\__, |_|  \__,_|_| |_| |_|_____/ \___| \_/  
                    __/ |   B R I D G E  &  A I  A G E N T     
                   |___/                                        
================================================================
"""


async def setup_bot_commands(bot: Bot):
    """Telegram ilovasida menyu buyruqlarini ro'yxatdan o'tkazish."""
    commands = [
        BotCommand(command="start", description="🚀 Bosh menyuni ochish"),
        BotCommand(command="files", description="📁 Fayllar brauzeri"),
        BotCommand(command="sh", description="💻 Terminal buyrug'ini bajarish"),
        BotCommand(command="agent", description="🤖 Avtonom AI dasturchi"),
        BotCommand(command="dl", description="📥 Video yuklash (Private/Public)"),
        BotCommand(command="broadcast", description="📢 Barcha a'zolarga xabar tarqatish"),
        BotCommand(command="send", description="📨 Userga botdan xabar yuborish"),
        BotCommand(command="dm", description="👤 Shaxsiy hisobdan (Userbot) yozish"),
        BotCommand(command="status", description="📊 Tizim holati (CPU, RAM, Disk)"),
        BotCommand(command="screenshot", description="📸 Kompyuter ekrani skrinshoti"),
        BotCommand(command="cleaner", description="🧹 Telegram hisobni tozalash"),
        BotCommand(command="help", description="📖 To'liq qo'llanma"),
    ]
    await bot.set_my_commands(commands)


async def notify_admins_on_startup(bot: Bot):
    """Bot ishga tushganda adminlarga xabar yuborish."""
    if not ADMIN_IDS:
        logger.warning(
            "DIQQAT: .env faylida ADMIN_IDS ko'rsatilmagan! Bot faqat adminlar uchun ishlaydi."
        )
        return

    text = (
        "🟢 <b>Telegram Dev Bridge ishga tushdi!</b>\n\n"
        f"📍 <b>Boshlang'ich katalog:</b> <code>{escape_html(str(DEFAULT_WORKING_DIR))}</code>\n"
        "⚡ Kompyuteringiz boshqaruvga tayyor. Menyuni ko'rish uchun /start bosing."
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Admin ({admin_id}) ga bildirishnoma yuborilmadi: {e}")


async def main():
    print(BANNER)
    logger.info("Bot ishga tushirilmoqda...")

    # 1. Render.com bepul Web Service ($0) portini birinchi navbatda ishga tushirish (Crash bo'lmasligi uchun)
    import os
    port_str = os.getenv("PORT")
    if port_str:
        try:
            from aiohttp import web
            port = int(port_str)
            app = web.Application()
            async def _health_handler(req):
                return web.Response(text="🟢 Telegram Dev Bridge 24/7 faol!", content_type="text/plain")
            app.router.add_get("/", _health_handler)
            app.router.add_get("/health", _health_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            logger.info(f"Render Free Web Service serveri 0.0.0.0:{port} da muvaffaqiyatli ishga tushdi.")
        except Exception as web_err:
            logger.warning(f"Web serverni ishga tushirishda xatolik (zararsiz): {web_err}")

    # 2. BOT_TOKEN mavjudligini tekshirish
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "❌ XATOLIK: BOT_TOKEN topilmadi!\n"
            "Iltimos, Render Dashboard -> Environment bo'limiga kiring va BOT_TOKEN o'zgaruvchisini qo'shing."
        )
        if port_str:
            logger.info("Web server xizmati faol saqlanmoqda. Token kiritilgach qayta ishga tushadi.")
            while True:
                await asyncio.sleep(3600)
        sys.exit(1)

    # 3. PythonAnywhere va boshqa serverlar uchun proksi tekshiruvi
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

    # Xavfsizlik Middleware sini o'rnatish
    auth_middleware = AuthMiddleware()
    dp.message.middleware(auth_middleware)
    dp.callback_query.middleware(auth_middleware)

    # Handler routerlarini ulash
    dp.include_router(start.router)
    dp.include_router(files.router)
    dp.include_router(terminal.router)
    dp.include_router(system.router)
    dp.include_router(ai_agent.router)
    dp.include_router(cleaner.router)
    dp.include_router(media_downloader.router)

    # Buyruqlar menyusi va xabarnoma
    await setup_bot_commands(bot)
    await notify_admins_on_startup(bot)

    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
    logger.info(f"Ruxsat berilgan Admin ID lar: {list(ADMIN_IDS)}")
    logger.info(f"Boshlang'ich papka: {DEFAULT_WORKING_DIR}")
    logger.info("Bot Telegram xabarlarini tinglamoqda...")

    try:
        # Polling rejimida xabarlarni tinglash
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
