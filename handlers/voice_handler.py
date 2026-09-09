"""
Ovozli Xabar Handleri
======================
Foydalanuvchi yuborgan voice/audio xabarlarni qabul qilib:
  1. Matnga aylantiradi (STT)
  2. Google Keep ga saqlaydi
  3. Agar vaqt/sana bo'lsa, Google Calendar ga event qo'shadi
  4. Foydalanuvchiga transkripsiyani qaytaradi
"""

import os
import logging
import tempfile

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


class VoiceFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.voice is not None or message.audio is not None


@router.message(VoiceFilter())
async def handle_voice_message(message: Message):
    """Ovozli yoki audio xabarni qayta ishlaydi."""
    try:
        from services.stt_service import transcribe_voice, extract_datetime_from_text
        from services.google_keep_service import save_voice_and_transcription
        from services.google_calendar_service import create_event_from_text_info

        # Foydalanuvchi ma'lumotlari
        user = message.from_user
        sender = user.first_name or user.username or ("ID" + str(user.id))
        sender_mention = user.mention_html() if hasattr(user, "mention_html") else sender

        # Jarayonni xabari
        processing_msg = await message.answer(
            "🎤 <b>Ovozli xabar qabul qilindi!</b>\n"
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
        is_success = not transcription.startswith("Ovozli xabarni matnga")

        # Foydalanuvchiga natija
        if is_success:
            resp_text = (
                "\U0001f4DD <b>Transkripsiya natijasi:</b>\n\n"
                + transcription
                + "\n\n"
            )
        else:
            resp_text = (
                "\u26a0\ufe0f <b>Transkripsiya muvaffaqiyatsiz:</b>\n"
                + transcription
            )

        await processing_msg.edit_text(resp_text, parse_mode="HTML")

        if not is_success:
            # Vaqtinchalik faylni o'chirish
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return

        # Google Keep ga saqlash
        keep_result = await save_voice_and_transcription(
            audio_path=tmp_path,
            transcription=transcription,
            sender_name=sender,
        )

        keep_info = ""
        if keep_result.get("success"):
            keep_info = (
                "\n\U0001f4D2 <b>Google Keep ga saqlandi:</b> "
                + "<a href=\"" + keep_result.get("url", "#") + "\">Keep'da ochish</a>"
            )
        else:
            keep_info = "\n\u26a0\ufe0f Google Keep ga saqlab bo'lmadi (" + keep_result.get("error", "?") + ")"

        # Vaqt/sana aniqlash va Calendar event
        dt_info = extract_datetime_from_text(transcription)
        cal_info = ""
        if dt_info:
            cal_result = await create_event_from_text_info(dt_info)
            if cal_result.get("success"):
                cal_info = (
                    "\n\U0001f4C5 <b>Google Calendar ga qo'shildi:</b> "
                    + dt_info.get("date", "") + " " + dt_info.get("time", "")
                    + " — " + "<a href=\"" + cal_result.get("link", "#") + "\">Calendar'da ko'rish</a>"
                )
            else:
                if "credentials" in cal_result.get("error", "") or "library" in cal_result.get("error", ""):
                    cal_info = ""  # sozlanmagan — jim o'tkazish
                else:
                    cal_info = "\n\u26a0\ufe0f Calendar event qo'sholmadi: " + cal_result.get("error", "")

        # Yakuniy xabar
        if keep_info or cal_info:
            await message.answer(
                keep_info + cal_info,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

        # Vaqtinchalik faylni o'chirish
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    except Exception as e:
        logger.error("Ovozli xabar handleri xatosi: " + str(e))
        try:
            await message.answer(
                "\u274c Ovozli xabarni qayta ishlashda xatolik yuz berdi."
            )
        except Exception:
            pass
