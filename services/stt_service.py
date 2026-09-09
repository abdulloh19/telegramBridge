"""
STT Xizmati (Speech-to-Text)
=============================
Foydalanuvchidan kelgan ovozli xabarni matnga aylantiradi.
Ikkita usul:
  1. Birinchi: Google Gemini API (gemini-flash modeli orqali audio transcribe)
  2. Zahira: SpeechRecognition + pydub (local, internet shart emas)
"""

import os
import logging
import tempfile
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)


async def transcribe_voice_gemini(audio_path: str):
    """
    Google Gemini API orqali audio faylni matnga o'tkazadi.
    """
    try:
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.warning("GEMINI_API_KEY topilmadi, Gemini STT ishlamaydi.")
            return None

        genai.configure(api_key=api_key)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        suffix = Path(audio_path).suffix.lower()
        mime_map = {
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
            ".opus": "audio/ogg",
        }
        mime_type = mime_map.get(suffix, "audio/ogg")

        model = genai.GenerativeModel("gemini-1.5-flash")

        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode()

        prompt = (
            "Bu Telegram ovozli xabari. Uni to'liq va aniq matnga o'tkazing. "
            "Faqat matni yozing, boshqa hech narsa qo'shmang. "
            "Agar tilni aniqlab bo'lmasa, o'zbek, rus yoki ingliz tilida deb hisoblang."
        )

        response = await asyncio.to_thread(
            model.generate_content,
            [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },
                prompt,
            ]
        )

        if response and response.text:
            text = response.text.strip()
            logger.info(f"Gemini STT muvaffaqiyatli: {len(text)} belgi")
            return text

    except Exception as e:
        logger.warning(f"Gemini STT xatosi: {e}")

    return None


async def transcribe_voice_local(audio_path: str):
    """
    Mahalliy SpeechRecognition kutubxonasi orqali audio faylni matnga o'tkazadi.
    """
    try:
        import speech_recognition as sr
        from pydub import AudioSegment

        suffix = Path(audio_path).suffix.lower()

        if suffix in (".ogg", ".opus", ".mp3", ".m4a"):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav_path = tmp.name
            audio = AudioSegment.from_file(audio_path)
            audio.export(wav_path, format="wav")
        else:
            wav_path = audio_path

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        for lang in ["uz-UZ", "ru-RU", "en-US"]:
            try:
                text = await asyncio.to_thread(
                    recognizer.recognize_google, audio_data, language=lang
                )
                if text:
                    logger.info(f"Local STT ({lang}): {text}")
                    if wav_path != audio_path:
                        try:
                            os.unlink(wav_path)
                        except Exception:
                            pass
                    return text
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                logger.warning(f"Google Speech API xatosi ({lang}): {e}")
                break

        if wav_path != audio_path:
            try:
                os.unlink(wav_path)
            except Exception:
                pass

    except ImportError:
        logger.warning(
            "speech_recognition yoki pydub o'rnatilmagan. "
            "pip install SpeechRecognition pydub"
        )
    except Exception as e:
        logger.warning(f"Local STT xatosi: {e}")

    return None


async def transcribe_voice(audio_path: str) -> str:
    """
    Asosiy STT funksiyasi.
    Birinchi Gemini, keyin local fallback ishlatadi.
    """
    result = await transcribe_voice_gemini(audio_path)
    if result:
        return result

    result = await transcribe_voice_local(audio_path)
    if result:
        return result

    return "Ovozli xabarni matnga o'tkazib bo'lmadi. Iltimos, aniqroq ovoz bilan qayta urinib ko'ring."


def extract_datetime_from_text(text: str):
    """
    Matndan sana va vaqt ma'lumotlarini ajratib oladi.
    Misol: "Ertaga soat 10:00 da uchrashuv"
    -> {'date': '2026-09-11', 'time': '10:00', 'description': '...'}
    """
    import re
    from datetime import datetime, timedelta

    text_lower = text.lower()
    today = datetime.now()

    target_date = None
    target_time = None
    description = text.strip()

    if any(w in text_lower for w in ["bugun", "today", "сегодня"]):
        target_date = today.date()
    elif any(w in text_lower for w in ["ertaga", "tomorrow", "завтра"]):
        target_date = (today + timedelta(days=1)).date()
    elif any(w in text_lower for w in ["indin", "послезавтра"]):
        target_date = (today + timedelta(days=2)).date()

    time_patterns = [
        r"soat\s+(\d{1,2}):(\d{2})",
        r"soat\s+(\d{1,2})",
        r"(\d{1,2}):(\d{2})\s*(?:da|de|ga)",
        r"(\d{1,2}):(\d{2})",
        r"в\s+(\d{1,2}):(\d{2})",
        r"в\s+(\d{1,2})\s+часов",
        r"at\s+(\d{1,2}):(\d{2})",
        r"at\s+(\d{1,2})\s*(?:am|pm)?",
    ]

    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            hour = int(groups[0])
            minute = int(groups[1]) if len(groups) > 1 and groups[1] is not None else 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                target_time = f"{hour:02d}:{minute:02d}"
                break

    if target_time and not target_date:
        target_date = today.date()

    if target_date or target_time:
        return {
            "date": str(target_date) if target_date else str(today.date()),
            "time": target_time or "09:00",
            "description": description,
            "has_date": target_date is not None,
            "has_time": target_time is not None,
        }

    return None
