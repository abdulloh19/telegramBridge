"""
Ovozli Xabar Handleri
======================
1. Voice/audio xabar qabul qilinadi
2. STT orqali matnga o'giriladi
3. "Buni Google Keep'ga saqlaymizmi?" so'rovi chiqariladi
4. Ha bosilsa => Keep ga saqlaydi
"""

import os
import logging
import tempfile

from aiogram import Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

router = Router()

# Vaqtincha xabar matnlarini saqlash (chat_id -> transkripsiya)
# (To'liq FSM o'rniga oddiy dict ishlatamiz)
_pending_transcriptions: dict = {}


class VoiceFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.voice is not None or message.audio is not None


def _build_keep_confirm_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Ha / Yo'q tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, saqlash", callback_data=f"keep_save_{chat_id}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"keep_skip_{chat_id}"),
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
            "⏳ Matnga aylantirilmoqda...",
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

        # STT
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
        }

        # Vaqt/sana aniqlash
        from services.stt_service import extract_datetime_from_text
        dt_info = extract_datetime_from_text(transcription)
        cal_note = ""
        if dt_info:
            cal_note = (
                "\n\n<b>📅 Vaqt/sana aniqlandi:</b> "
                + dt_info.get("date", "") + " " + dt_info.get("time", "")
                + "\n<i>Keep'ga saqlanganda Calendar'ga ham qo'shiladi.</i>"
            )

        # Foydalanuvchiga natija + tasdiq tugmasi
        await processing_msg.edit_text(
            "<b>📝 Transkripsiya natijasi:</b>\n\n"
            + transcription
            + cal_note
            + "\n\n<b>💾 Buni Google Keep'ga saqlaymizmi?</b>",
            parse_mode="HTML",
            reply_markup=_build_keep_confirm_keyboard(chat_id),
        )

    except Exception as e:
        logger.error("Ovozli xabar handleri xatosi: " + str(e))
        try:
            await message.answer("❌ Ovozli xabarni qayta ishlashda xatolik yuz berdi.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("keep_save_"))
async def callback_keep_save(callback: CallbackQuery):
    """Foydalanuvchi 'Ha' ni bosdi — Keep ga saqlash."""
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

    # Editing tugmasini o'chirish
    await callback.message.edit_reply_markup(reply_markup=None)

    saving_msg = await callback.message.answer("⏳ Google Keep ga saqlanmoqda...")

    try:
        from services.google_keep_service import save_voice_and_transcription
        keep_result = await save_voice_and_transcription(
            audio_path=audio_path,
            transcription=transcription,
            sender_name=sender,
        )

        if keep_result.get("success"):
            url = keep_result.get("url", "#")
            await saving_msg.edit_text(
                "<b>✅ Google Keep'ga saqlandi!</b>\n"
                + '<a href="' + url + '">Keep\'da ochish</a>',
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            err = keep_result.get("error", "nomalum")
            if "credentials" in err:
                await saving_msg.edit_text(
                    "⚠️ Google Keep hali sozlanmagan.\n"
                    "<i>(.env faylida GOOGLE_KEEP_EMAIL va GOOGLE_KEEP_MASTER_TOKEN kerak)</i>",
                    parse_mode="HTML",
                )
            else:
                await saving_msg.edit_text(
                    "❌ Keep'ga saqlab bo'lmadi: " + err
                )

        # Calendar event
        try:
            from services.stt_service import extract_datetime_from_text
            from services.google_calendar_service import create_event_from_text_info
            dt_info = extract_datetime_from_text(transcription)
            if dt_info:
                cal_result = await create_event_from_text_info(dt_info)
                if cal_result.get("success"):
                    link = cal_result.get("link", "#")
                    await callback.message.answer(
                        "<b>📅 Google Calendar'ga ham qo'shildi:</b> "
                        + dt_info.get("date", "") + " " + dt_info.get("time", "")
                        + "\n" + '<a href="' + link + '">Calendar\'da ko\'rish</a>',
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
        except Exception:
            pass

    except Exception as e:
        logger.error("Keep save xatosi: " + str(e))
        await saving_msg.edit_text("❌ Xatolik yuz berdi: " + str(e))
    finally:
        try:
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)
        except Exception:
            pass


@router.callback_query(F.data.startswith("keep_skip_"))
async def callback_keep_skip(callback: CallbackQuery):
    """Foydalanuvchi 'Yo'q' ni bosdi."""
    await callback.answer("OK, saqlanmadi.")
    chat_id = callback.message.chat.id
    pending = _pending_transcriptions.pop(chat_id, None)

    # Audio faylni tozalash
    if pending and pending.get("audio_path"):
        try:
            os.unlink(pending["audio_path"])
        except Exception:
            pass

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Tushunildi. Xabar saqlanmadi.")
