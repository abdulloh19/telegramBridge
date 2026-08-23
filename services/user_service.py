import json
from pathlib import Path
from typing import Optional
from utils.logger import logger

USERS_FILE = Path(__file__).resolve().parent.parent / "sessions" / "registered_users.json"


class UserService:
    """Bot foydalanuvchilarini doimiy saqlash va boshqarish xizmati."""

    @staticmethod
    def _load_users() -> dict:
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Foydalanuvchilarni o'qishda xatolik: {e}")
        return {}

    @staticmethod
    def _save_users(data: dict):
        try:
            USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Foydalanuvchilarni saqlashda xatolik: {e}")

    @classmethod
    def register_user(cls, user_id: int, username: Optional[str] = "", full_name: Optional[str] = ""):
        """Yangi foydalanuvchini bazaga qo'shish yoki ma'lumotlarini yangilash."""
        try:
            users = cls._load_users()
            users[str(user_id)] = {
                "id": user_id,
                "username": username or "",
                "full_name": full_name or ""
            }
            cls._save_users(users)
        except Exception as e:
            logger.warning(f"Foydalanuvchini ro'yxatga olishda xatolik: {e}")

    @classmethod
    def get_all_user_ids(cls) -> list[int]:
        """Barcha ro'yxatdan o'tgan foydalanuvchilar va adminlar ID larini qaytaradi."""
        from config import ADMIN_IDS
        users = cls._load_users()
        ids = set(ADMIN_IDS)
        for uid in users.keys():
            if uid.isdigit():
                ids.add(int(uid))
        return list(ids)

    @classmethod
    def get_users_count(cls) -> int:
        """Jami foydalanuvchilar soni."""
        return len(cls.get_all_user_ids())
