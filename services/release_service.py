"""
Bot Versiya va Yangiliklar Xizmati (Release Service)
===================================================
Har safar bot qayta o't olganda bir xil eski xabarni takrorlashni oldini oladi.
Faqat yangi yangilanish bo'lganda, aynan o'sha versiyada kiritilgan
haqiqiy yangiliklar ro'yxatini yuboradi.
"""

import logging
from pathlib import Path
from typing import Optional, List
from aiogram import Bot

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VERSION_FILE = DATA_DIR / "last_announced_version.txt"

CURRENT_VERSION = "2.4.0"
RELEASE_DATE = "10.09.2026"

# AYNAN USHBU VERSIYADA KIRITILGAN HAQIQIY YANGILIKLAR RO'YXATI
CURRENT_CHANGES: List[str] = [
    "🎤 <b>Kengaytirilgan Ovozli Xabarlar (STT):</b> Google Gemini 3.6 Flash orqali qisqa va bir necha daqiqalik uzun ovozli xabarlar aniq va xatosiz matnga o'giriladi.",
    "📝 <b>Ichki Eslatmalar Tizimi (/notes):</b> Ovozli transkripsiyalar va qaydlar bot xotirasida saqlanadi. <code>/notes</code> orqali istalgan paytda ko'rish mumkin.",
    "🗣️ <b>5 ta Hayotiy Kundalik Dialog:</b> Taksi, Sayohat, Bozor, Kafe va Dorixona mavzulari bo'yicha interaktiv dialog mashqlari.",
    "📊 <b>Progress & Ketma-ketlik:</b> Dialoglar va so'zlarda to'xtagan bosqichingiz xotirada to'liq saqlanib, qayta boshidan boshlanmaydi.",
    "🔄 <b>Aqlli Qayta Topshirish:</b> Test natijasi 40% dan past bo'lganda, xatolarni bartaraf qilish uchun qayta ishlash imkoniyati.",
    "🛠️ <b>Google Keep xatoligi bartaraf etildi:</b> Endi .env sozlamalarisiz ham barcha eslatmalar botning o'zida ishonchli saqlanadi."
]


def get_latest_update_message() -> str:
    """Aynan yangi kiritilgan imkoniyatlarni chiroyli xabar qilib beradi."""
    features_text = "\n".join([f"• {item}" for item in CURRENT_CHANGES])

    return (
        f"🟢 <b>Yangi Yangilanish Kiritildi! (v{CURRENT_VERSION}) 🚀</b>\n"
        f"📅 <i>Sana: {RELEASE_DATE}</i>\n\n"
        "✨ <b>Ushbu yangilanishda kiritilgan yangiliklar:</b>\n"
        f"{features_text}\n\n"
        "👉 Yangilangan menyuni ko'rish uchun <b>/start</b> bosing!"
    )


def should_announce_update() -> bool:
    """Ushbu versiya xabari avval yuborilganmi yoki yo'qligini tekshiradi."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not VERSION_FILE.exists():
            return True
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            last_version = f.read().strip()
        return last_version != CURRENT_VERSION
    except Exception as e:
        logger.warning(f"Versiya tekshirishda xatolik: {e}")
        return True


def mark_update_announced():
    """Joriy versiya e'lon qilingan deb belgilash."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(CURRENT_VERSION)
    except Exception as e:
        logger.warning(f"Versiyani saqlashda xatolik: {e}")


async def notify_admins_of_new_release(bot: Bot, admin_ids: list, force: bool = False):
    """
    Faqat yangi versiya bo'lganda yoki majburiy (force=True) chaqirilganda
    adminlarga yangi imkoniyatlar ro'yxatini yuboradi.
    """
    if not admin_ids:
        return

    if not force and not should_announce_update():
        logger.info(f"v{CURRENT_VERSION} yangiliklari allaqachon yuborilgan. Qayta takrorlanmadi.")
        return

    text = get_latest_update_message()

    sent_count = 0
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
            sent_count += 1
        except Exception as e:
            logger.warning(f"Admin ({admin_id}) ga yangilanish xabari yetmadi: {e}")

    if sent_count > 0:
        mark_update_announced()
        logger.info(f"v{CURRENT_VERSION} yangiliklari {sent_count} ta adminga muvaffaqiyatli yuborildi.")
