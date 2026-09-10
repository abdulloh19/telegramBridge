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
        """Yangi foydalanuvchini bazaga faqat bir marta unikal qo'shish (UPSERT / INSERT OR IGNORE)."""
        try:
            users = cls._load_users()
            uid_str = str(user_id)
            if uid_str in users:
                # Mavjud foydalanuvchi: faqat username/ism yangilanadi, yangi dublikat qo'shilmaydi
                existing = users[uid_str]
                if username and username != existing.get("username"):
                    existing["username"] = username
                if full_name and full_name != existing.get("full_name"):
                    existing["full_name"] = full_name
                users[uid_str] = existing
            else:
                # Birinchi marta kirgan yangi foydalanuvchi
                users[uid_str] = {
                    "id": user_id,
                    "username": username or "",
                    "full_name": full_name or ""
                }
            cls._save_users(users)
        except Exception as e:
            logger.warning(f"Foydalanuvchini ro'yxatga olishda xatolik: {e}")

    @classmethod
    def get_all_user_ids(cls) -> list[int]:
        """Barcha ro'yxatdan o'tgan foydalanuvchilar va adminlar ID larini unikal to'plam qilib qaytaradi."""
        from config import ADMIN_IDS, BASE_DIR
        ids = set(ADMIN_IDS)

        # 1. sessions/registered_users.json
        users = cls._load_users()
        for uid in users.keys():
            if str(uid).isdigit():
                ids.add(int(uid))

        # 2. sessions_registry.json
        sess_file = BASE_DIR / "data" / "sessions_registry.json"
        if sess_file.exists():
            try:
                with open(sess_file, "r", encoding="utf-8") as f:
                    reg_data = json.load(f)
                    for uid in reg_data.keys():
                        if str(uid).isdigit():
                            ids.add(int(uid))
            except Exception:
                pass

        # 3. tgbot/data/users.json yoki data/users.json
        for users_p in [
            BASE_DIR / "data" / "users.json",
            BASE_DIR.parent / "tgbot" / "data" / "users.json",
            BASE_DIR.parent / "mnemonic-webapp" / "data" / "users.json",
        ]:
            if users_p.exists():
                try:
                    with open(users_p, "r", encoding="utf-8") as f:
                        t_data = json.load(f)
                        for uid in t_data.keys():
                            if str(uid).isdigit():
                                ids.add(int(uid))
                except Exception:
                    pass

        # 4. Asosiy ma'lum bot foydalanuvchilari zaxirasi
        ids.add(5787141744)
        ids.add(6767933010)
        ids.add(5049524803)

        return sorted(list(ids))

    @classmethod
    def get_users_count(cls) -> int:
        """Jami unikal foydalanuvchilar soni."""
        return len(cls.get_all_user_ids())
