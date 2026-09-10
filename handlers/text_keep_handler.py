"""
Matnli Xabar Keep Handleri
============================
Foydalanuvchi oddiy matn yozganida:
  1. "Buni Google Keep'ga saqlaymizmi?" so'rovi chiqariladi
  2. Ha bosilsa Keep ga saqlaydi
  3. Yo'q bosilsa jim o'tkazadi

MUHIM: Bu handler faqat /start, /dl va boshqa buyruqlarga
tegishli bo'lmagan oddiy matnlarni ushlaydigan PASTROQ prioritetli handler.
"""

import logging

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

router = Router()

# Vaqtincha matnlarni saqlash (chat_id -> text)
_pending_texts: dict = {}

# Keep so'rovi yuboriladigan minimum matn uzunligi
MIN_TEXT_LENGTH = 10


class PlainTextFilter(BaseFilter):
    """Buyruq bo'lmagan, oddiy matn xabarlar."""
    async def __call__(self, message: Message) -> bool:
        if not message.text:
            return False
        txt = message.text.strip()
        # Buyruqlar (/ bilan boshlanadigan) yoki juda qisqa matnlar e'tiborga olinmaydi
        if txt.startswith("/"):
            return False
        if len(txt) < MIN_TEXT_LENGTH:
            return False
        return True


def _build_text_keep_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, Keep'ga saqlash", callback_data=f"textkeep_yes_{chat_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"textkeep_no_{chat_id}"),
        ]
    ])


@router.message(PlainTextFilter())
async def handle_plain_text(message: Message):
    """Matn xabar kelganda Keep saqlash taklifi."""
    chat_id = message.chat.id
    text = message.text.strip()

    # Vaqtincha saqlash
    _pending_texts[chat_id] = text

    await message.answer(
        "<b>💬 Matn qabul qilindi.</b>\n\n"
        "<i>\"" + (text[:120] + "..." if len(text) > 120 else text) + "\"</i>\n\n"
        "<b>💾 Buni Google Keep'ga saqlaymizmi?</b>",
        parse_mode="HTML",
        reply_markup=_build_text_keep_keyboard(chat_id),
    )


@router.callback_query(F.data.startswith("textkeep_yes_"))
async def callback_textkeep_yes(callback: CallbackQuery):
    """Foydalanuvchi 'Ha' ni bosdi."""
    await callback.answer()
    chat_id = callback.message.chat.id
    text = _pending_texts.pop(chat_id, None)

    await callback.message.edit_reply_markup(reply_markup=None)

    if not text:
        await callback.message.answer("⚠️ Matn topilmadi. Qayta yuboring.")
        return

    saving_msg = await callback.message.answer("⏳ Keep'ga saqlanmoqda...")

    try:
        from services.google_keep_service import save_to_google_keep
        from datetime import datetime

        user = callback.from_user
        sender = user.first_name or user.username or str(user.id)
        now = datetime.now()
        title = "Telegram Matn — " + sender + " — " + now.strftime("%d.%m.%Y %H:%M")

        result = await save_to_google_keep(text, title=title, labels=["Telegram", "Matn"])

        if result.get("success"):
            url = result.get("url", "#")
            await saving_msg.edit_text(
                "<b>✅ Google Keep'ga saqlandi!</b>\n"
                + '<a href="' + url + '">Keep\'da ochish</a>',
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            err = result.get("error", "nomalum")
            if "credentials" in err:
                await saving_msg.edit_text(
                    "⚠️ Google Keep hali sozlanmagan.\n"
                    "<i>(.env da GOOGLE_KEEP_EMAIL va GOOGLE_KEEP_MASTER_TOKEN kerak)</i>",
                    parse_mode="HTML",
                )
            else:
                await saving_msg.edit_text("❌ Saqlab bo'lmadi: " + err)

    except Exception as e:
        logger.error("Text Keep save xatosi: " + str(e))
        await saving_msg.edit_text("❌ Xatolik: " + str(e))


@router.callback_query(F.data.startswith("textkeep_no_"))
async def callback_textkeep_no(callback: CallbackQuery):
    """Foydalanuvchi 'Yo'q' ni bosdi."""
    await callback.answer("OK.")
    chat_id = callback.message.chat.id
    _pending_texts.pop(chat_id, None)
    await callback.message.edit_reply_markup(reply_markup=None)
