import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, BASE_DIR
from utils.logger import logger

SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class AccountCleanerService:
    """Ko'p foydalanuvchili Telegram hisobini tozalash xizmati."""

    _clients: dict[int, object] = {}
    _phone_hashes: dict[int, str] = {}

    @staticmethod
    def is_configured() -> bool:
        """API_ID va API_HASH mavjudligini tekshiradi."""
        return bool(TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_API_ID.isdigit())

    @staticmethod
    async def get_client(user_id: int):
        """Har bir foydalanuvchi uchun alohida Telethon mijozini asinxron tarzda qaytaradi."""
        if not AccountCleanerService.is_configured():
            raise ValueError(
                "Telegram API_ID va API_HASH kiritilmagan!\n"
                "Iltimos, https://my.telegram.org dan olib, .env fayliga TELEGRAM_API_ID va TELEGRAM_API_HASH ni kiriting."
            )

        from telethon import TelegramClient

        session_path = str(SESSIONS_DIR / f"user_session_{user_id}")

        if user_id not in AccountCleanerService._clients:
            client = TelegramClient(
                session_path,
                int(TELEGRAM_API_ID),
                TELEGRAM_API_HASH
            )
            AccountCleanerService._clients[user_id] = client

        client = AccountCleanerService._clients[user_id]
        if not client.is_connected():
            await client.connect()

        return client

    @staticmethod
    async def is_authorized(user_id: int) -> bool:
        """Foydalanuvchi akkauntiga allaqachon kirilganmi tekshiradi."""
        if not AccountCleanerService.is_configured():
            return False
        try:
            client = await AccountCleanerService.get_client(user_id)
            return await client.is_user_authorized()
        except Exception as e:
            logger.warning(f"Avtorizatsiyani tekshirishda xatolik ({user_id}): {e}")
            return False

    @staticmethod
    async def send_auth_code(user_id: int, phone: str) -> str:
        """Telefon raqamga Telegram tasdiqlash kodini yuboradi."""
        client = await AccountCleanerService.get_client(user_id)
        result = await client.send_code_request(phone)
        AccountCleanerService._phone_hashes[user_id] = result.phone_code_hash
        return result.phone_code_hash

    @staticmethod
    async def complete_sign_in(user_id: int, phone: str, code: str, password: Optional[str] = None) -> tuple[bool, str]:
        """Tasdiqlash kodi va (agar bor bo'lsa 2FA parol) orqali tizimga kirish."""
        client = await AccountCleanerService.get_client(user_id)
        from telethon.errors import SessionPasswordNeededError

        phone_code_hash = AccountCleanerService._phone_hashes.get(user_id)
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            me = await client.get_me()
            return True, f"✅ Muvaffaqiyatli ulandi: {me.first_name} (@{me.username or me.id})"
        except SessionPasswordNeededError:
            if not password:
                return False, "2FA_REQUIRED"
            await client.sign_in(password=password)
            me = await client.get_me()
            return True, f"✅ Muvaffaqiyatli ulandi: {me.first_name} (@{me.username or me.id})"
        except Exception as e:
            return False, f"Kirishda xatolik: {str(e)}"

    @staticmethod
    async def scan_deleted_accounts(user_id: int) -> list[dict]:
        """O'chib ketgan (Deleted Account) hisoblarni aniqlaydi."""
        client = await AccountCleanerService.get_client(user_id)
        deleted_dialogs = []

        dialogs = await client.get_dialogs()
        for d in dialogs:
            if d.is_user:
                entity = d.entity
                if getattr(entity, 'deleted', False) or (entity.first_name and "deleted account" in entity.first_name.lower()):
                    deleted_dialogs.append({
                        "id": d.id,
                        "title": d.name or "Deleted Account",
                        "unread_count": d.unread_count,
                    })

        return deleted_dialogs

    @staticmethod
    async def remove_deleted_accounts(user_id: int) -> int:
        """Barcha 'Deleted Account' bo'lib qolgan chatlarni o'chiradi."""
        client = await AccountCleanerService.get_client(user_id)
        deleted_list = await AccountCleanerService.scan_deleted_accounts(user_id)
        count = 0

        for item in deleted_list:
            try:
                await client.delete_dialog(item["id"])
                count += 1
                await asyncio.sleep(0.3)  # Telegram Flood limitidan saqlanish
            except Exception as e:
                logger.warning(f"Chatni o'chirishda xatolik ({item['id']}): {e}")

        return count

    @staticmethod
    async def scan_inactive_channels(user_id: int, days: int = 60) -> list[dict]:
        """Ancha vaqtdan beri xabar kelmagan yoki faol bo'lmagan kanallar va guruhlarni aniqlaydi."""
        client = await AccountCleanerService.get_client(user_id)
        inactive_list = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        dialogs = await client.get_dialogs()
        for d in dialogs:
            if d.is_channel or d.is_group:
                dialog_date = d.date
                if dialog_date and dialog_date.tzinfo is None:
                    dialog_date = dialog_date.replace(tzinfo=timezone.utc)

                if dialog_date and dialog_date < cutoff_date:
                    days_ago = (datetime.now(timezone.utc) - dialog_date).days
                    inactive_list.append({
                        "id": d.id,
                        "title": d.name,
                        "is_channel": d.is_channel,
                        "is_group": d.is_group,
                        "days_ago": days_ago,
                        "last_active": dialog_date.strftime("%Y-%m-%d"),
                    })

        return inactive_list

    @staticmethod
    async def leave_inactive_channels(user_id: int, channel_ids: list[int]) -> int:
        """Ko'rsatilgan faol bo'lmagan kanallar va guruhlardan chiqib ketadi (Leave Chat)."""
        client = await AccountCleanerService.get_client(user_id)
        left_count = 0

        for ch_id in channel_ids:
            try:
                await client.delete_dialog(ch_id)
                left_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Kanal/guruhdan chiqishda xatolik ({ch_id}): {e}")

        return left_count

    @staticmethod
    async def scan_old_dialogs(user_id: int, days: int = 90) -> list[dict]:
        """Belgilangan kundan eski bo'lgan shaxsiy yozishmalarni qidiradi."""
        client = await AccountCleanerService.get_client(user_id)
        old_dialogs = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        dialogs = await client.get_dialogs()
        for d in dialogs:
            if d.is_user:
                dialog_date = d.date
                if dialog_date and dialog_date.tzinfo is None:
                    dialog_date = dialog_date.replace(tzinfo=timezone.utc)

                if dialog_date and dialog_date < cutoff_date:
                    days_ago = (datetime.now(timezone.utc) - dialog_date).days
                    old_dialogs.append({
                        "id": d.id,
                        "title": d.name,
                        "days_ago": days_ago,
                        "last_active": dialog_date.strftime("%Y-%m-%d"),
                    })

        return old_dialogs

    @staticmethod
    async def delete_old_dialogs(user_id: int, dialog_ids: list[int]) -> int:
        """Eski dialoglarni tozalaydi."""
        client = await AccountCleanerService.get_client(user_id)
        deleted_count = 0

        for d_id in dialog_ids:
            try:
                await client.delete_dialog(d_id)
                deleted_count += 1
                await asyncio.sleep(0.4)
            except Exception as e:
                logger.warning(f"Dialogni o'chirishda xatolik ({d_id}): {e}")

        return deleted_count
