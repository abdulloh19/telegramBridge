"""
Bot Versiya va Yangiliklar Xizmati (Release Service)
===================================================
Har safar bot qayta o't olganda bir xil eski xabarni takrorlashni oldini oladi.
Faqat yangi yangilanish bo'lganda, aynan o'sha versiyada kiritilgan
haqiqiy yangiliklar ro'yxatini yuboradi.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, List
from aiogram import Bot

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VERSION_FILE = DATA_DIR / "last_announced_version.txt"

CURRENT_VERSION = "2.6.0"
RELEASE_DATE = "10.09.2026"

# AYNAN USHBU VERSIYADA KIRITILGAN HAQIQIY YANGILIKLAR RO'YXATI
CURRENT_CHANGES: List[str] = [
    "👤 <b>Unikal Foydalanuvchilar va Dashboard:</b> Foydalanuvchilar bazaga unikal tarzda yoziladi va o'rganilgan so'zlar statistikasi Web Dashboard bilan to'liq sinxronlashtirildi.",
    "📢 <b>Kafolatlangan Ommaviy Xabarnoma (Broadcast):</b> Yangilanishlar barcha foydalanuvchilarga xatosiz, tezkor va ishonchli yetkaziladi.",
    "⏰ <b>Bir Nechta Vaqtli Eslatmalar (Multiple Reminders):</b> Bitta ovozli yoki matnli xabarda bir nechta vaqt aytilsa (masalan: <i>«10:00 da majlis, 14:00 da dars»</i>), har biri alohida ajratilib, belgilangan vaqtda aniq Telegram bildirishnomasi (notification) yuboriladi.",
    "📋 <b>Eslatmalar Paneli (/reminders):</b> Barcha faol eslatmalarni qolgan daqiqalarigacha ko'rish va boshqarish imkoniyati.",
    "🎤 <b>Kengaytirilgan Ovozli Xabarlar (STT):</b> Google Gemini 3.6 Flash orqali qisqa va juda uzun audiolarni xatosiz matnga o'girish.",
    "📝 <b>Ichki Qaydlar Tizimi (/notes):</b> Transkripsiya qilingan nutq va matnlarni bot xotirasida saqlash.",
    "🗣️ <b>5 ta Hayotiy Kundalik Dialog:</b> Taksi, Sayohat, Bozor, Kafe va Dorixona mavzulari bo'yicha interaktiv dialog mashqlari.",
    "📊 <b>Progress & Ketma-ketlik:</b> Dialog va darslarda to'xtagan bosqichingiz xotirada to'liq saqlanadi."
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


async def notify_all_users_of_new_release(bot: Bot, force: bool = False):
    """
    Faqat yangi versiya bo'lganda yoki majburiy (force=True) chaqirilganda
    BARCHA bot foydalanuvchilariga yangiliklar xabarini yuboradi.
    """
    if not force and not should_announce_update():
        logger.info(f"v{CURRENT_VERSION} yangiliklari allaqachon barcha foydalanuvchilarga yuborilgan. Qayta takrorlanmadi.")
        return

    from services.user_service import UserService
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

    user_ids = UserService.get_all_user_ids()
    if not user_ids:
        logger.warning("Foydalanuvchilar topilmadi, yangiliklar yuborilmadi.")
        return

    text = get_latest_update_message()

    sent_count = 0
    blocked_count = 0
    failed_count = 0

    logger.info(f"v{CURRENT_VERSION} yangiliklari {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")

    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent_count += 1
            await asyncio.sleep(0.05)  # Telegram FloodWait cheklovidan saqlanish
        except TelegramForbiddenError:
            blocked_count += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
                sent_count += 1
            except Exception:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            logger.debug(f"User {uid} ga yangilik yuborishda xatolik: {e}")

    if sent_count > 0:
        mark_update_announced()
        logger.info(
            f"v{CURRENT_VERSION} yangiliklari muvaffaqiyatli yuborildi: "
            f"Yetkazildi: {sent_count}, Bloklagan: {blocked_count}, Xatolar: {failed_count}"
        )


async def notify_admins_of_new_release(bot: Bot, admin_ids: list = None, force: bool = False):
    """Barcha foydalanuvchilarga yangilik yuborish (orqaga moslik uchun)."""
    await notify_all_users_of_new_release(bot, force=force)
