import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


def is_keep_configured() -> bool:
    """Google Keep ma'lumotlari sozlanganligini tekshiradi."""
    email = os.getenv("GOOGLE_KEEP_EMAIL", "").strip()
    token = os.getenv("GOOGLE_KEEP_MASTER_TOKEN", "").strip()
    if not email or not token or email == "your_email@gmail.com":
        return False
    return True


async def save_to_google_keep(text, title=None, labels=None, pinned=False):
    """Matni Google Keep ga yangi eslatma sifatida saqlaydi (agar sozlangan bo'lsa)."""
    if not is_keep_configured():
        return {"success": False, "error": "not_configured"}

    email = os.getenv("GOOGLE_KEEP_EMAIL", "").strip()
    token = os.getenv("GOOGLE_KEEP_MASTER_TOKEN", "").strip()

    try:
        import gkeepapi
        keep = gkeepapi.Keep()
        await asyncio.to_thread(keep.resume, email, token)
        if not title:
            now = datetime.now()
            title = "Telegram Eslatma " + now.strftime("%d.%m.%Y %H:%M")
        note = keep.createNote(title, text)
        note.pinned = pinned
        if labels:
            for lname in labels:
                lb = keep.findLabel(lname) or keep.createLabel(lname)
                note.labels.add(lb)
        await asyncio.to_thread(keep.sync)
        url = "https://keep.google.com/#NOTE/" + note.id
        logger.info("Keep note yaratildi: " + note.id)
        return {"success": True, "note_id": note.id, "url": url, "title": title}
    except ImportError:
        logger.warning("gkeepapi kutubxonasi topilmadi.")
        return {"success": False, "error": "gkeepapi_missing"}
    except Exception as e:
        logger.warning("Google Keep saqlashda xatolik: " + str(e))
        return {"success": False, "error": str(e)}


async def save_voice_and_transcription(
    audio_path, transcription, sender_name="Foydalanuvchi", pinned=False
):
    """Ovozli xabar transkripsiyasini Google Keep ga saqlaydi."""
    if not is_keep_configured():
        return {"success": False, "error": "not_configured"}

    now = datetime.now()
    ts = now.strftime("%d.%m.%Y %H:%M:%S")
    title = "Ovozli Xabar - " + sender_name + " - " + now.strftime("%d.%m.%Y %H:%M")
    body = (
        "Yuborildi: " + ts + "\n"
        "Foydalanuvchi: " + sender_name + "\n"
        "Audio fayl: " + str(audio_path) + "\n\n"
        + transcription
    )
    return await save_to_google_keep(
        body, title=title, labels=["Telegram", "Ovozli"], pinned=pinned
    )
