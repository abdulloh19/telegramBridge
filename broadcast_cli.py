import asyncio
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from aiogram import Bot
from config import BOT_TOKEN
from services.broadcast_service import BroadcastService


async def main():
    print("=" * 60)
    print("  OMMAVIY XABARNOMA (BROADCAST) YUBORISH TIZIMI")
    print("=" * 60)

    if not BOT_TOKEN:
        print("[XATO] BOT_TOKEN topilmadi! .env faylini tekshiring.")
        return

    bot = Bot(token=BOT_TOKEN)
    try:
        bot_info = await bot.get_me()
        print(f"[OK] Bot: @{bot_info.username} ({bot_info.first_name})")
        print("[INFO] Barcha foydalanuvchilarga xabarnoma yuborilmoqda...")

        def on_progress(idx, total, sent, blocked, failed):
            print(f"  Progress: {idx}/{total} | Yetkazildi: {sent} | Bloklagan: {blocked} | Xato: {failed}")

        res = await BroadcastService.send_broadcast_to_all(
            bot=bot,
            progress_callback=on_progress
        )

        print("\n" + "=" * 60)
        print("  XABARNOMA MUVAFFAQIYATLI YAKUNLANDI!")
        print(f"  • Jami foydalanuvchilar: {res['total']} ta")
        print(f"  • Yetkazildi:            {res['sent']} ta")
        print(f"  • Bloklaganlar:          {res['blocked']} ta")
        print(f"  • Xatoliklar:            {res['failed']} ta")
        print(f"  • Sarflangan vaqt:       {res['duration_sec']} soniya")
        print("=" * 60)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
