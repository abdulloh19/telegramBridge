import asyncio
import time
from typing import Optional, Dict, Any, List
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

from services.user_service import UserService
from config import ADMIN_IDS
from utils.logger import logger
from utils.helpers import escape_html


DEFAULT_BROADCAST_MESSAGE = (
    "🔔 <b>MUHIM XABARNOMA: Bot Yangilandi! 🚀</b>\n\n"
    "Hurmatli foydalanuvchi! Botimizga katta yangilanishlar va yangi imkoniyatlar kiritildi:\n\n"
    "✨ <b>Yangi Imkoniyatlar:</b>\n"
    "• 🚀 <b>YouTube Video Yuklashda MB Cheklovi Butunlay Olib Tashlandi!</b>\n"
    "  Endi istalgan hajmdagi (50MB dan 2000MB gacha va undan katta) videolarni 1080p/2K/4K sifatda cheklovsiz yuklab olishingiz mumkin.\n"
    "• 🎵 <b>Yuqori Sifatli MP3 (320kbps):</b> Har bir video bilan birga toza studio audio ham yetkaziladi.\n"
    "• ⚡ <b>Turbo 8-Stream Parallel Yuklash:</b> Yuklash va jo'natish tezligi 3 baravarga oshirildi.\n"
    "• 🧹 <b>Telegram Hisob Tozalovchi:</b> O'chgan akkauntlar va nofaol chatlarni 1 soniyada tozalash (/cleaner).\n\n"
    "⚠️ <b>DIQQAT: Yangi funksiyalar to'g'ri va xatosiz ishlashi uchun barcha foydalanuvchilar botni qayta ishga tushirishi (/start bosishi) shart!</b>\n\n"
    "👇 <i>Quyidagi tugmani bosing va botni darhol yangilang:</i>"
)


def get_broadcast_inline_keyboard(bot_username: Optional[str] = None) -> InlineKeyboardMarkup:
    """Foydalanuvchini darhol /start bosishga undovchi interaktiv tugmalar."""
    start_url = f"https://t.me/{bot_username}?start=updated" if bot_username else None

    buttons = []
    if start_url:
        buttons.append([
            InlineKeyboardButton(text="🚀 /start Bosish va Yangilash", url=start_url)
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🚀 /start Bosish va Yangilash", callback_data="btn_quick_restart")
        ])

    buttons.append([
        InlineKeyboardButton(text="📥 Video Yuklash (/dl)", callback_data="btn_quick_dl"),
        InlineKeyboardButton(text="🎵 MP3 Yuklash (/mp3)", callback_data="btn_quick_mp3")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


class BroadcastService:
    """Barcha bot foydalanuvchilariga ommaviy xabarnoma (broadcast) yuborish xizmati."""

    @classmethod
    async def send_broadcast_to_all(
        cls,
        bot: Bot,
        custom_text: Optional[str] = None,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Barcha foydalanuvchilarga xavfsiz va FloodWait cheklovlariga rioya qilgan holda
        ommaviy xabar yuboradi.
        """
        # 1. Barcha user ID larni yig'ish
        user_ids = set(UserService.get_all_user_ids())
        user_ids.update(ADMIN_IDS)

        # sessions_registry.json dagi foydalanuvchilarni ham qo'shish
        try:
            import json
            from pathlib import Path
            from config import BASE_DIR
            sess_file = BASE_DIR / "data" / "sessions_registry.json"
            if sess_file.exists():
                with open(sess_file, "r", encoding="utf-8") as f:
                    reg_data = json.load(f)
                    for uid in reg_data.keys():
                        if uid.isdigit():
                            user_ids.add(int(uid))
        except Exception as e:
            logger.warning(f"sessions_registry dan userlarni o'qishda xatolik: {e}")

        total_users = len(user_ids)
        if total_users == 0:
            return {
                "total": 0,
                "sent": 0,
                "blocked": 0,
                "failed": 0,
                "duration_sec": 0
            }

        # 2. Bot usernamesini aniqlash
        bot_username = None
        try:
            bot_me = await bot.get_me()
            bot_username = bot_me.username
        except Exception:
            pass

        text_to_send = custom_text if custom_text else DEFAULT_BROADCAST_MESSAGE
        markup_to_send = keyboard if keyboard is not None else get_broadcast_inline_keyboard(bot_username)

        sent_count = 0
        blocked_count = 0
        failed_count = 0
        start_time = time.time()

        logger.info(f"Ommaviy xabarnoma boshlandi: {total_users} ta foydalanuvchiga...")

        # 3. Ketma-ket, tezkor va xavfsiz yuborish (Telegram API limiti: ~30 msg/sec)
        for idx, user_id in enumerate(user_ids, 1):
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text_to_send,
                    parse_mode="HTML",
                    reply_markup=markup_to_send,
                    disable_web_page_preview=True
                )
                sent_count += 1
            except TelegramForbiddenError:
                # Foydalanuvchi botni bloklagan
                blocked_count += 1
                logger.info(f"User {user_id} botni bloklagan.")
            except TelegramRetryAfter as flood:
                # Telegram flood wait so'rasa, kutib qayta urinish
                logger.warning(f"Telegram FloodWait: {flood.retry_after} soniya kutilmoqda...")
                await asyncio.sleep(flood.retry_after + 1)
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text_to_send,
                        parse_mode="HTML",
                        reply_markup=markup_to_send,
                        disable_web_page_preview=True
                    )
                    sent_count += 1
                except Exception as retry_err:
                    failed_count += 1
                    logger.warning(f"Qayta urinishda xatolik ({user_id}): {retry_err}")
            except TelegramBadRequest as bad_req:
                failed_count += 1
                logger.warning(f"Noto'g'ri so'rov ({user_id}): {bad_req}")
            except Exception as other_err:
                failed_count += 1
                logger.warning(f"Xabar yuborishda xatolik ({user_id}): {other_err}")

            # Telegram serverlariga ortiqcha yuk tushmasligi uchun kichik pauza (25-30 msg/sec)
            await asyncio.sleep(0.04)

            # Progress callback
            if progress_callback and (idx % 10 == 0 or idx == total_users):
                try:
                    progress_callback(idx, total_users, sent_count, blocked_count, failed_count)
                except Exception:
                    pass

        elapsed = round(time.time() - start_time, 2)
        logger.info(
            f"Ommaviy xabarnoma yakunlandi! "
            f"Jami: {total_users}, Yetib bordi: {sent_count}, Bloklagan: {blocked_count}, Xato: {failed_count} ({elapsed}s)"
        )

        return {
            "total": total_users,
            "sent": sent_count,
            "blocked": blocked_count,
            "failed": failed_count,
            "duration_sec": elapsed
        }
