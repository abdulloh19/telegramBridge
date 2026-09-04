import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from aiogram import Bot
import config

async def main():
    bot = Bot(token=config.BOT_TOKEN)
    text = (
        "🟢 <b>Bot muvaffaqiyatli yangilandi va ishga tushdi! 🚀</b>\n\n"
        "✨ <b>Yangi Imkoniyatlar:</b>\n"
        "• 🎵 <b>Alohida MP3 Bo'limi</b> (/mp3 yoki menyudan)\n"
        "• 📥 <b>To'g'ridan-to'g'ri Bot Chatga Yetkazish</b> (Izbrannoega emas)\n"
        "• 🎬 + 🎵 <b>Video bilan birga 320kbps MP3 ham keladi</b>\n"
        "• 🧹 <b>Telegram Hisob Tozalovchi</b> (/cleaner)\n\n"
        "👉 Yangilangan menyuni ko'rish uchun <b>/start</b> bosing!"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
            print(f"Xabar yuborildi: {admin_id}")
        except Exception as e:
            print(f"Xatolik: {admin_id}: {e}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
