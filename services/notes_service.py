import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NOTES_FILE = DATA_DIR / "user_notes.json"


def _ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def _load_all_notes() -> Dict[str, List[Dict[str, Any]]]:
    _ensure_storage()
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"user_notes.json o'qishda xatolik: {e}")
        return {}


def _save_all_notes(data: Dict[str, List[Dict[str, Any]]]):
    _ensure_storage()
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"user_notes.json saqlashda xatolik: {e}")


class NotesService:
    @classmethod
    def save_note(
        cls,
        user_id: int,
        text: str,
        title: Optional[str] = None,
        source: str = "voice"
    ) -> Dict[str, Any]:
        """Yangi eslatma saqlaydi."""
        all_data = _load_all_notes()
        uid_key = str(user_id)
        if uid_key not in all_data:
            all_data[uid_key] = []

        now = datetime.now()
        note_id = f"note_{int(time.time() * 1000)}"

        if not title:
            words = text.strip().split()
            title = " ".join(words[:5]) if words else "Yangi Eslatma"
            if len(words) > 5:
                title += "..."

        note = {
            "id": note_id,
            "title": title,
            "text": text.strip(),
            "source": source,
            "created_at": now.strftime("%d.%m.%Y %H:%M"),
            "timestamp": int(time.time())
        }

        all_data[uid_key].insert(0, note)

        if len(all_data[uid_key]) > 100:
            all_data[uid_key] = all_data[uid_key][:100]

        _save_all_notes(all_data)
        logger.info(f"User {user_id} uchun eslatma saqlandi: {note_id}")
        return note

    @classmethod
    def get_user_notes(cls, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Foydalanuvchining barcha eslatmalarini qaytaradi."""
        all_data = _load_all_notes()
        uid_key = str(user_id)
        return all_data.get(uid_key, [])[:limit]

    @classmethod
    def get_note(cls, user_id: int, note_id: str) -> Optional[Dict[str, Any]]:
        """Bitta eslatmani topadi."""
        notes = cls.get_user_notes(user_id, limit=100)
        for n in notes:
            if n.get("id") == note_id:
                return n
        return None

    @classmethod
    def delete_note(cls, user_id: int, note_id: str) -> bool:
        """Eslatmani o'chiradi."""
        all_data = _load_all_notes()
        uid_key = str(user_id)
        if uid_key not in all_data:
            return False

        orig_len = len(all_data[uid_key])
        all_data[uid_key] = [n for n in all_data[uid_key] if n.get("id") != note_id]

        if len(all_data[uid_key]) < orig_len:
            _save_all_notes(all_data)
            return True
        return False
