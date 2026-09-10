"""
Ovozli Xabar Handleri
=====================
1. Voice/audio xabar qabul qilinadi
2. Gemini 3.6 Flash orqali matnga o'giriladi (uzoq va qisqa audiolarni xatosiz qayta ishlaydi)
3. "Buni eslatmalarga saqlaysizmi?" so'rovi chiqariladi
4. Ha bosilsa => Ichki NotesService'ga saqlaydi (/notes orqali ko'rish mumkin)
   Agar Google Keep sozlangan bo'lsa, Keep'ga ham qo'shadi.
"""

import os
import logging
import tempfile

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.notes_service import NotesService
from services.google_keep_service import is_keep_configured, save_voice_and_transcription

logger = logging.getLogger(__name__)

router = Router()

# Vaqtincha xabar ma'lumotlarini saqlash (chat_id -> dict)
_pending_transcriptions: dict = {}


class VoiceFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.voice is not None or message.audio is not None


def _build_note_confirm_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Eslatmaga saqlash / O'tkazib yuborish tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 Eslatmaga saqlash", callback_data=f"note_save_{chat_id}"),
            InlineKeyboardButton(text="❌ O'tkazib yuborish", callback_data=f"note_skip_{chat_id}"),
        ]
    ])


@router.message(VoiceFilter())
async def handle_voice_message(message: Message):
    """Ovozli yoki audio xabarni qayta ishlaydi."""
    try:
        from services.stt_service import transcribe_voice, extract_datetime_from_text

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

        # STT — Gemini 3.6 Flash / chunked fallback
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

        # Transkripsiyani vaqtincha saqlaymiz
        _pending_transcriptions[chat_id] = {
            "text": transcription,
            "audio_path": tmp_path,
            "sender": sender,
            "user_id": user.id,
        }

        # Vaqt/sana aniqlash
        dt_info = extract_datetime_from_text(transcription)
        cal_note = ""
        if dt_info:
            cal_note = (
                f"\n\n<b>📅 Vaqt/sana aniqlandi:</b> {dt_info.get('date', '')} {dt_info.get('time', '')}"
            )

        # Foydalanuvchiga natija + tasdiq tugmasi
        await processing_msg.edit_text(
            "<b>📝 Transkripsiya natijasi:</b>\n\n"
            + transcription
            + cal_note
            + "\n\n<b>💾 Buni eslatmalarga saqlaysizmi?</b>",
            parse_mode="HTML",
            reply_markup=_build_note_confirm_keyboard(chat_id),
        )

    except Exception as e:
        logger.error(f"Ovozli xabar handleri xatosi: {e}")
        try:
            await message.answer("❌ Ovozli xabarni qayta ishlashda xatolik yuz berdi.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("note_save_") | F.data.startswith("keep_save_"))
async def callback_note_save(callback: CallbackQuery):
    """Foydalanuvchi 'Saqlash' ni bosdi."""
    await callback.answer()
    chat_id = callback.message.chat.id
    pending = _pending_transcriptions.pop(chat_id, None)

    if not pending:
        await callback.message.edit_text(
            "⚠️ Saqlash muddati tugadi. Ovozni qayta yuboring.",
        )
        return

    transcription = pending["text"]
    audio_path = pending.get("audio_path", "")
    sender = pending.get("sender", "Foydalanuvchi")
    user_id = pending.get("user_id", callback.from_user.id)

    # Tugmani o'chirish
    await callback.message.edit_reply_markup(reply_markup=None)

    # 1. Botning ichki eslatmalariga saqlash
    note = NotesService.save_note(
        user_id=user_id,
        text=transcription,
        source="voice"
    )

    keep_info = ""
    # 2. Agar Google Keep sozlangan bo'lsa, orqa fonda Keep'ga ham saqlash
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

    # Calendar tadbir
    cal_info = ""
    try:
        from services.stt_service import extract_datetime_from_text
        from services.google_calendar_service import create_event_from_text_info
        dt_info = extract_datetime_from_text(transcription)
        if dt_info:
            cal_result = await create_event_from_text_info(dt_info)
            if cal_result.get("success"):
                link = cal_result.get("link", "#")
                cal_info = f'\n📅 <a href="{link}">Google Calendar\'ga qo\'shildi</a>'
    except Exception:
        pass

    success_msg = (
        "<b>✅ Eslatmalaringizga muvaffaqiyatli saqlandi!</b>\n\n"
        f"📌 <b>Sarlavha:</b> {note.get('title')}\n"
        f"🕒 <b>Vaqt:</b> {note.get('created_at')}"
        f"{keep_info}"
        f"{cal_info}\n\n"
        "👉 Barcha eslatmalarni ko'rish uchun <b>/notes</b> bosing."
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
    await callback.message.answer("✅ Tushunildi. Ovoz eslatmalarga saqlanmadi.")
