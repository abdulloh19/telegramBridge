"""
Ovozli Xabar Handleri (Voice Handler)
====================================
1. Voice/audio xabar qabul qilinadi
2. Gemini 3.6 Flash orqali matnga o'giriladi
3. Bitta xabardagi barcha turli vaqtlar (Multiple Reminders) avtomatik ajratiladi
4. Foydalanuvchi tasdiqlasa, barcha vaqtlar bo'yicha mustaqil eslatmalar (notifications) o'rnatiladi
"""

import os
import logging
import tempfile

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.notes_service import NotesService
from services.reminder_service import ReminderService
from services.reminder_parser import parse_multiple_reminders, format_reminders_summary
from services.google_keep_service import is_keep_configured, save_voice_and_transcription

logger = logging.getLogger(__name__)

router = Router()

# Vaqtincha xabar ma'lumotlarini saqlash (chat_id -> dict)
_pending_transcriptions: dict = {}


class VoiceFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.voice is not None or message.audio is not None


def _build_voice_action_keyboard(chat_id: int, reminder_count: int = 0) -> InlineKeyboardMarkup:
    """Eslatmalarni yoqish / oddiy saqlash tugmalari."""
    buttons = []
    if reminder_count > 0:
        buttons.append([
            InlineKeyboardButton(
                text=f"⏰ Barcha eslatmalarni yoqish ({reminder_count} ta)",
                callback_data=f"rem_enable_{chat_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="💾 Faqat matnni saqlash", callback_data=f"note_save_{chat_id}"),
        InlineKeyboardButton(text="❌ O'tkazib yuborish", callback_data=f"note_skip_{chat_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(VoiceFilter())
async def handle_voice_message(message: Message):
    """Ovozli yoki audio xabarni qayta ishlaydi."""
    try:
        from services.stt_service import transcribe_voice

        user = message.from_user
        sender = user.first_name or user.username or ("ID" + str(user.id))
        chat_id = message.chat.id

        processing_msg = await message.answer(
            "<b>🎤 Ovozli xabar qabul qilindi!</b>\n"
            "⏳ <i>Gemini AI orqali matnga aylantirilmoqda...</i>",
            parse_mode="HTML",
        )

        # Audio faylni yuklab olish
        voice = message.voice or message.audio
        file = await message.bot.get_file(voice.file_id)

        suffix = ".ogg"
        if message.audio and message.audio.mime_type:
            ext_map = {
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
                "audio/ogg": ".ogg",
                "audio/wav": ".wav",
            }
            suffix = ext_map.get(message.audio.mime_type, ".ogg")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        await message.bot.download_file(file.file_path, tmp_path)

        # 1. STT — Gemini 3.6 Flash
        transcription = await transcribe_voice(tmp_path)
        is_failed = transcription.startswith("Ovozli xabarni matnga")

        if is_failed:
            await processing_msg.edit_text(
                "<b>⚠️ Transkripsiya muvaffaqiyatsiz:</b>\n" + transcription,
                parse_mode="HTML",
            )
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return

        # 2. Ko'p vaqtli eslatmalarni ajratish (Multiple Timestamps)
        detected_reminders = await parse_multiple_reminders(transcription)

        # Transkripsiyani vaqtincha saqlaymiz
        _pending_transcriptions[chat_id] = {
            "text": transcription,
            "audio_path": tmp_path,
            "sender": sender,
            "user_id": user.id,
            "reminders": detected_reminders,
        }

        rem_summary = ""
        prompt_text = "<b>💾 Buni eslatmalarga saqlaysizmi?</b>"

        if detected_reminders:
            rem_list = format_reminders_summary(detected_reminders)
            rem_summary = (
                f"\n\n⏰ <b>Aniqlangan vaqtlar ({len(detected_reminders)} ta):</b>\n"
                f"{rem_list}\n\n"
                f"<i>Belgilangan har bir vaqtda bot sizga ogohlantirish yuborishi mumkin.</i>"
            )
            prompt_text = "<b>Quyidagi amalni tanlang:</b>"

        # Foydalanuvchiga natija + tugmalar
        await processing_msg.edit_text(
            "<b>📝 Transkripsiya natijasi:</b>\n\n"
            + f"<i>\"{transcription}\"</i>"
            + rem_summary
            + f"\n\n{prompt_text}",
            parse_mode="HTML",
            reply_markup=_build_voice_action_keyboard(chat_id, len(detected_reminders)),
        )

    except Exception as e:
        logger.error(f"Ovozli xabar handleri xatosi: {e}")
        try:
            await message.answer("❌ Ovozli xabarni qayta ishlashda xatolik yuz berdi.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("rem_enable_"))
async def callback_rem_enable(callback: CallbackQuery):
    """Foydalanuvchi barcha aniqlangan eslatmalarni yoqishni tanladi."""
    await callback.answer()
    chat_id = callback.message.chat.id
    pending = _pending_transcriptions.pop(chat_id, None)

    if not pending:
        await callback.message.edit_text("⚠️ Saqlash muddati tugadi. Ovozni qayta yuboring.")
        return

    transcription = pending["text"]
    audio_path = pending.get("audio_path", "")
    user_id = pending.get("user_id", callback.from_user.id)
    reminders = pending.get("reminders", [])

    await callback.message.edit_reply_markup(reply_markup=None)

    # 1. Barcha eslatmalarni Scheduler'ga kiritish
    created = ReminderService.add_multiple_reminders(
        user_id=user_id,
        chat_id=chat_id,
        items=reminders,
        source="voice"
    )

    # 2. Shuningdek matnni NotesService'ga ham saqlash
    NotesService.save_note(user_id=user_id, text=transcription, source="voice")

    rem_summary = format_reminders_summary(reminders)

    msg = (
        f"✅ <b>{len(created)} ta eslatma muvaffaqiyatli o'rnatildi! 🔔</b>\n\n"
        f"{rem_summary}\n\n"
        "⚡ <i>Har bir vaqt yetib kelganida bot sizga alohida xabar yuboradi.</i>\n\n"
        "📋 Eslatmalaringizni ko'rish: <b>/reminders</b>"
    )

    await callback.message.answer(msg, parse_mode="HTML")

    try:
        if audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)
    except Exception:
        pass


@router.callback_query(F.data.startswith("note_save_") | F.data.startswith("keep_save_"))
async def callback_note_save(callback: CallbackQuery):
    """Foydalanuvchi faqat matnni saqlashni bosdi."""
    await callback.answer()
    chat_id = callback.message.chat.id
    pending = _pending_transcriptions.pop(chat_id, None)

    if not pending:
        await callback.message.edit_text("⚠️ Saqlash muddati tugadi. Ovozni qayta yuboring.")
        return

    transcription = pending["text"]
    audio_path = pending.get("audio_path", "")
    sender = pending.get("sender", "Foydalanuvchi")
    user_id = pending.get("user_id", callback.from_user.id)

    await callback.message.edit_reply_markup(reply_markup=None)

    # 1. Botning ichki eslatmalariga saqlash
    note = NotesService.save_note(
        user_id=user_id,
        text=transcription,
        source="voice"
    )

    keep_info = ""
    if is_keep_configured():
        try:
            keep_res = await save_voice_and_transcription(
                audio_path=audio_path,
                transcription=transcription,
                sender_name=sender,
            )
            if keep_res.get("success"):
                keep_url = keep_res.get("url", "#")
                keep_info = f'\n🔗 <a href="{keep_url}">Google Keep\'da ochish</a>'
        except Exception as ke:
            logger.warning(f"Google Keep sync xatosi: {ke}")

    success_msg = (
        "<b>✅ Eslatmalaringizga muvaffaqiyatli saqlandi!</b>\n\n"
        f"📌 <b>Sarlavha:</b> {note.get('title')}\n"
        f"🕒 <b>Vaqt:</b> {note.get('created_at')}"
        f"{keep_info}\n\n"
        "👉 Barcha qaydlarni ko'rish uchun <b>/notes</b> bosing."
    )

    await callback.message.answer(
        success_msg,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    try:
        if audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)
    except Exception:
        pass


@router.callback_query(F.data.startswith("note_skip_") | F.data.startswith("keep_skip_"))
async def callback_note_skip(callback: CallbackQuery):
    """Foydalanuvchi 'O'tkazib yuborish' ni bosdi."""
    await callback.answer("Saqlanmadi.")
    chat_id = callback.message.chat.id
    pending = _pending_transcriptions.pop(chat_id, None)

    if pending and pending.get("audio_path"):
        try:
            os.unlink(pending["audio_path"])
        except Exception:
            pass

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Tushunildi. Xabar saqlanmadi.")
