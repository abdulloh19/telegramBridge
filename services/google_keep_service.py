import os, logging, asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


async def save_to_google_keep(text, title=None, labels=None, pinned=False):
    """Matni Google Keep ga yangi eslatma sifatida saqlaydi."""
    email = os.getenv("GOOGLE_KEEP_EMAIL", "")
    token = os.getenv("GOOGLE_KEEP_MASTER_TOKEN", "")
    if not email or not token:
        logger.warning(
            "Google Keep credentials topilmadi! "
            ".env faylida GOOGLE_KEEP_EMAIL va GOOGLE_KEEP_MASTER_TOKEN qo'shing."
        )
        return {"success": False, "error": "credentials_missing"}
    try:
        import gkeepapi  # pip install gkeepapi
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
        logger.warning("gkeepapi topilmadi. pip install gkeepapi")
        return {"success": False, "error": "gkeepapi_missing"}
    except Exception as e:
        logger.error("Keep xatosi: " + str(e))
        return {"success": False, "error": str(e)}


async def save_voice_and_transcription(
    audio_path, transcription, sender_name="Foydalanuvchi", pinned=False
):
    """Ovozli xabar transkripsiyasini Google Keep ga saqlaydi."""
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
