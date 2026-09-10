"""
STT Xizmati (Speech-to-Text)
=============================
Foydalanuvchidan kelgan ovozli xabarni matnga aylantiradi.
1. Asosiy: Google Gemini 3.6 Flash (google-genai SDK orqali) - qisqa va istalgancha uzun audiolarni to'liq transkripsiya qiladi.
2. Zahira: speech_recognition + pydub (bo'laklarga ajratilgan holda, uzun gaplarda ham xato bermaydi).
"""

import os
import re
import logging
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _setup_ffmpeg_path():
    """pydub uchun ffmpeg yo'lini sozlash (agar tizimda bo'lmasa imageio_ffmpeg dan oladi)."""
    try:
        from pydub import AudioSegment
        import shutil
        if not shutil.which("ffmpeg"):
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            if ffmpeg_exe and os.path.exists(ffmpeg_exe):
                AudioSegment.converter = ffmpeg_exe
    except Exception as e:
        logger.debug(f"ffmpeg sozlashda eslatma: {e}")


_setup_ffmpeg_path()


async def transcribe_voice_gemini(audio_path: str):
    """
    Google Gemini 3.6 Flash orqali audio faylni to'liq matnga o'tkazadi.
    Qisqa yoki bir necha daqiqalik uzun audiolarni ham xatosiz transkripsiya qiladi.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.warning("GEMINI_API_KEY topilmadi, Gemini STT ishlatilmadi.")
            return None

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        suffix = Path(audio_path).suffix.lower()
        mime_map = {
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
            ".opus": "audio/ogg",
            ".oga": "audio/ogg",
        }
        mime_type = mime_map.get(suffix, "audio/ogg")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        if not audio_bytes:
            logger.warning("Audio fayl bo'sh!")
            return None

        prompt = (
            "Ushbu Telegram audio/ovozli xabarini to'liq, so'zma-so'z va aniq matnga o'tkazing. "
            "Faqatgina aytilgan nutqning matnini yozing, hech qanday kirish so'z, sharh yoki izoh qo'shmang. "
            "Nutq tili (o'zbek, rus, ingliz yoki boshqa) qaysi bo'lsa, o'sha tilda aniq orfografiya va tinish belgilari bilan yozing."
        )

        part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        model_name = os.getenv("AI_MODEL", "gemini-3.6-flash")
        if "1.5" in model_name or "2.5" in model_name:
            model_name = "gemini-3.6-flash"

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model_name,
            contents=[part, prompt]
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
    Mahalliy SpeechRecognition + pydub orqali audio transkripsiyasi (zahira usul).
    Uzun audiolarni 15 soniyali qismlarga bo'lib transkripsiya qiladi, xato kelib chiqmaydi.
    """
    try:
        import speech_recognition as sr
        from pydub import AudioSegment

        _setup_ffmpeg_path()
        audio = AudioSegment.from_file(audio_path)

        # 15 soniyalik bo'laklarga ajratamiz (15000 ms)
        chunk_length_ms = 15000
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]

        recognizer = sr.Recognizer()
        transcribed_parts = []

        for idx, chunk in enumerate(chunks):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                chunk_wav = tmp.name

            try:
                chunk.export(chunk_wav, format="wav")
                with sr.AudioFile(chunk_wav) as source:
                    audio_data = recognizer.record(source)

                chunk_text = ""
                for lang in ["uz-UZ", "ru-RU", "en-US"]:
                    try:
                        chunk_text = await asyncio.to_thread(
                            recognizer.recognize_google, audio_data, language=lang
                        )
                        if chunk_text:
                            break
                    except sr.UnknownValueError:
                        continue
                    except Exception:
                        break

                if chunk_text:
                    transcribed_parts.append(chunk_text.strip())
            finally:
                try:
                    if os.path.exists(chunk_wav):
                        os.unlink(chunk_wav)
                except Exception:
                    pass

        if transcribed_parts:
            full_text = " ".join(transcribed_parts)
            logger.info(f"Local STT (chunked): {len(full_text)} belgi")
            return full_text

    except Exception as e:
        logger.warning(f"Local STT xatosi: {e}")

    return None


async def transcribe_voice(audio_path: str) -> str:
    """
    Asosiy STT chaqiruvi:
    Avval Gemini 3.6 Flash (uzoq va qisqa audiolarga eng yuqori sifat),
    muvaffaqiyatsiz bo'lsa mahalliy bo'laklangan SpeechRecognition.
    """
    result = await transcribe_voice_gemini(audio_path)
    if result:
        return result

    result = await transcribe_voice_local(audio_path)
    if result:
        return result

    return "Ovozli xabarni matnga o'tkazib bo'lmadi. Iltimos, mikrofonga yaqinroq va aniqroq ovoz bilan qayta urinib ko'ring."


def extract_datetime_from_text(text: str):
    """
    Matndan sana va vaqt ma'lumotlarini ajratib oladi.
    Masalan: 'Ertaga soat 10:00 da darsga borishim kerak'
    """
    text_lower = text.lower()
    today = datetime.now()

    target_date = None
    target_time = None
    description = text.strip()

    if any(w in text_lower for w in ["bugun", "today", "сегодня"]):
        target_date = today.date()
    elif any(w in text_lower for w in ["ertaga", "tomorrow", "завтра"]):
        target_date = (today + timedelta(days=1)).date()
    elif any(w in text_lower for w in ["indin", "indinga", "послезавтра"]):
        target_date = (today + timedelta(days=2)).date()

    time_patterns = [
        r"soat\s+(\d{1,2}):(\d{2})",
        r"soat\s+(\d{1,2})",
        r"(\d{1,2}):(\d{2})\s*(?:da|de|ga)?",
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

    if target_date and target_time:
        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "time": target_time,
            "description": description,
        }

    return None
