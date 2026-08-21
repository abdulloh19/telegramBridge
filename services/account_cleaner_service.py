import asyncio
import os
import platform
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, BASE_DIR
from utils.logger import logger

SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_telethon_proxy() -> Optional[dict]:
    """Tizim yoki muhitdan (masalan: PythonAnywhere, .env) mos proksi sozlamasini oladi."""
    proxy_str = (
        os.getenv("TELEGRAM_PROXY")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
    )
    if not proxy_str:
        # PythonAnywhere serveri tekshiruvi
        is_pa = any([
            "PYTHONANYWHERE_DOMAIN" in os.environ,
            "PYTHONANYWHERE_SITE" in os.environ,
            os.path.exists("/var/log/pythonanywhere"),
            "pythonanywhere" in os.environ.get("HOME", "").lower(),
            "zubayr" in str(Path.home()),
            "pythonanywhere" in platform.node().lower()
        ])
        if is_pa:
            proxy_str = "http://proxy.server:3128"
            logger.info("PythonAnywhere proksi (Telethon) aniqlandi: http://proxy.server:3128")

    if not proxy_str:
        return None

    try:
        parsed = urlparse(proxy_str)
        scheme = (parsed.scheme or "http").lower()
        proxy_type = "http"
        if "socks5" in scheme:
            proxy_type = "socks5"
        elif "socks4" in scheme:
            proxy_type = "socks4"

        proxy_dict = {
            "proxy_type": proxy_type,
            "addr": parsed.hostname or "127.0.0.1",
            "port": parsed.port or (1080 if "socks" in scheme else 8080),
        }
        if parsed.username:
            proxy_dict["username"] = parsed.username
        if parsed.password:
            proxy_dict["password"] = parsed.password
        return proxy_dict
    except Exception as e:
        logger.warning(f"Telethon proksi manzilini formatlashda xatolik: {e}")
        return None


def format_seconds(seconds: int) -> str:
    """Saniyalarni chiroyli o'zbekcha vaqt formatiga o'tkazadi."""
    if seconds < 60:
        return f"{seconds} soniya"
    minutes = seconds // 60
    rem_sec = seconds % 60
    if minutes < 60:
        return f"{minutes} daqiqa {rem_sec} soniya" if rem_sec else f"{minutes} daqiqa"
    hours = minutes // 60
    rem_min = minutes % 60
    return f"{hours} soat {rem_min} daqiqa"


AUTH_INFO_FILE = SESSIONS_DIR / "auth_info.json"


def _load_auth_info() -> dict:
    try:
        if AUTH_INFO_FILE.exists():
            import json
            with open(AUTH_INFO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_auth_info(data: dict):
    try:
        import json
        with open(AUTH_INFO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class AccountCleanerService:
    """Ko'p foydalanuvchili Telegram hisobini tozalash xizmati."""

    _clients: dict[int, object] = {}
    _phone_hashes: dict[int, str] = {}

    @staticmethod
    def is_configured() -> bool:
        """API_ID va API_HASH mavjudligini tekshiradi."""
        import config
        return bool(config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH and str(config.TELEGRAM_API_ID).isdigit())

    @staticmethod
    def get_cached_profile(user_id: int) -> Optional[dict]:
        info = _load_auth_info()
        return info.get(str(user_id))

    @staticmethod
    def save_profile(user_id: int, profile: dict):
        info = _load_auth_info()
        info[str(user_id)] = profile
        _save_auth_info(info)

    @staticmethod
    def remove_profile(user_id: int):
        info = _load_auth_info()
        info.pop(str(user_id), None)
        _save_auth_info(info)

    @staticmethod
    async def get_client(user_id: int):
        """Har bir foydalanuvchi uchun alohida Telethon mijozini asinxron tarzda qaytaradi."""
        import config
        if not AccountCleanerService.is_configured():
            raise ValueError(
                "Telegram API_ID va API_HASH kiritilmagan!\n"
                "Iltimos, botdagi '⚙️ API_ID va API_HASH kiritish' tugmasi orqali kiriting yoki .env faylini to'ldiring."
            )

        from telethon import TelegramClient

        session_path = str(SESSIONS_DIR / f"user_session_{user_id}")

        if user_id not in AccountCleanerService._clients:
            proxy = get_telethon_proxy()
            client = TelegramClient(
                session_path,
                int(config.TELEGRAM_API_ID),
                config.TELEGRAM_API_HASH,
                proxy=proxy,
                connection_retries=10,
                timeout=25,
                retry_delay=2,
                auto_reconnect=True,
                use_ipv6=False,
            )
            AccountCleanerService._clients[user_id] = client

        client = AccountCleanerService._clients[user_id]
        if not client.is_connected():
            await client.connect()

        return client

    @staticmethod
    async def is_authorized(user_id: int) -> bool:
        """Foydalanuvchi akkauntiga allaqachon kirilganmi tekshiradi (hech qachon osilib qolmaydi)."""
        import config
        if not AccountCleanerService.is_configured():
            return False

        session_file = SESSIONS_DIR / f"user_session_{user_id}.session"
        if not session_file.exists():
            return False

        cached = AccountCleanerService.get_cached_profile(user_id)

        try:
            async def _check():
                client = await AccountCleanerService.get_client(user_id)
                auth = await client.is_user_authorized()
                if auth:
                    me = await client.get_me()
                    first_name = getattr(me, 'first_name', '') or 'Foydalanuvchi'
                    username = f"@{me.username}" if getattr(me, 'username', None) else ""
                    phone = getattr(me, 'phone', '') or ''
                    AccountCleanerService.save_profile(user_id, {
                        "id": me.id,
                        "name": first_name,
                        "username": username,
                        "phone": phone
                    })
                return auth

            return await asyncio.wait_for(_check(), timeout=3.0)
        except Exception as e:
            logger.warning(f"Avtorizatsiyani tekshirishda xatolik/timeout ({user_id}): {e}")
            return bool(cached and session_file.exists())

    @staticmethod
    async def logout(user_id: int) -> bool:
        """Foydalanuvchi sessiyasini uzadi va sessiya fayllarini tozalaydi."""
        try:
            AccountCleanerService.remove_profile(user_id)
            if user_id in AccountCleanerService._clients:
                client = AccountCleanerService._clients[user_id]
                try:
                    if client.is_connected():
                        await client.log_out()
                except Exception:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                AccountCleanerService._clients.pop(user_id, None)

            AccountCleanerService._phone_hashes.pop(user_id, None)

            session_file = SESSIONS_DIR / f"user_session_{user_id}.session"
            if session_file.exists():
                session_file.unlink(missing_ok=True)
            journal_file = SESSIONS_DIR / f"user_session_{user_id}.session-journal"
            if journal_file.exists():
                journal_file.unlink(missing_ok=True)

            return True
        except Exception as e:
            logger.error(f"Sessiyadan chiqishda xatolik ({user_id}): {e}")
            return False

    @staticmethod
    async def reset_unauthorized_session(user_id: int):
        """Agar sessiya to'liq kirmagan yoki buzilgan bo'lsa, uni tozalab yangidan yaratadi."""
        try:
            if user_id in AccountCleanerService._clients:
                client = AccountCleanerService._clients[user_id]
                try:
                    if client.is_connected():
                        await client.disconnect()
                except Exception:
                    pass
                AccountCleanerService._clients.pop(user_id, None)

            AccountCleanerService._phone_hashes.pop(user_id, None)

            session_file = SESSIONS_DIR / f"user_session_{user_id}.session"
            if session_file.exists():
                session_file.unlink(missing_ok=True)
            journal_file = SESSIONS_DIR / f"user_session_{user_id}.session-journal"
            if journal_file.exists():
                journal_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Sessiyani tozalashda xatolik: {e}")

    @staticmethod
    async def create_qr_login(user_id: int):
        """QR kod orqali kirishni boshlaydi va (qr_login_ob'ekti, qrcode_image_bytes) qaytaradi."""
        import qrcode
        import io

        # Agar avval kirmagan bo'lsa, toza yangi sessiya bilan boshlash
        if not await AccountCleanerService.is_authorized(user_id):
            await AccountCleanerService.reset_unauthorized_session(user_id)

        client = await AccountCleanerService.get_client(user_id)
        if not client.is_connected():
            await client.connect()

        qr = await client.qr_login()
        img = qrcode.make(qr.url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return qr, buf

    @staticmethod
    async def wait_for_qr_login(user_id: int, qr_obj, password: Optional[str] = None) -> tuple[bool, str]:
        """QR kod skanerlanishini yoki 2FA parolini tekshiradi."""
        from telethon.errors import (
            SessionPasswordNeededError,
            PasswordHashInvalidError,
            FloodWaitError
        )

        client = await AccountCleanerService.get_client(user_id)
        try:
            if password:
                try:
                    await client.sign_in(password=password)
                    me = await client.get_me()
                    first_name = getattr(me, 'first_name', '') or 'Foydalanuvchi'
                    username = f"@{me.username}" if getattr(me, 'username', None) else f"ID: {me.id}"
                    phone = getattr(me, 'phone', '') or ''
                    AccountCleanerService.save_profile(user_id, {
                        "id": me.id,
                        "name": first_name,
                        "username": username,
                        "phone": phone
                    })
                    return True, f"✅ Muvaffaqiyatli ulandi: {first_name} ({username})"
                except PasswordHashInvalidError:
                    return False, "❌ 2FA paroli noto'g'ri kiritildi!"
                except FloodWaitError as fe:
                    time_str = format_seconds(fe.seconds)
                    return False, f"⏳ Telegram cheklovi (FloodWait): Iltimos, {time_str} kuting."
                except Exception as err:
                    return False, f"2FA bilan kirishda xatolik: {str(err)}"

            await qr_obj.wait(timeout=45)
            me = await client.get_me()
            first_name = getattr(me, 'first_name', '') or 'Foydalanuvchi'
            username = f"@{me.username}" if getattr(me, 'username', None) else f"ID: {me.id}"
            phone = getattr(me, 'phone', '') or ''
            AccountCleanerService.save_profile(user_id, {
                "id": me.id,
                "name": first_name,
                "username": username,
                "phone": phone
            })
            return True, f"✅ Muvaffaqiyatli ulandi: {first_name} ({username})"
        except SessionPasswordNeededError:
            return False, "2FA_REQUIRED"
        except asyncio.TimeoutError:
            return False, "TIMEOUT"
        except Exception as e:
            err_text = str(e)
            if "SessionPasswordNeededError" in err_text:
                return False, "2FA_REQUIRED"
            return False, f"Kirishda xatolik: {err_text}"

    @staticmethod
    async def send_auth_code(user_id: int, phone: str) -> tuple[str, str]:
        """Telefon raqamga Telegram tasdiqlash kodini yuboradi va kod qayerga yuborilgani haqida ma'lumot beradi."""
        from telethon.errors import (
            FloodWaitError,
            PhoneNumberInvalidError,
            PhoneNumberBannedError,
        )

        # Yangi urinish uchun eski nofaol ulanishni tozalash
        if not await AccountCleanerService.is_authorized(user_id):
            await AccountCleanerService.reset_unauthorized_session(user_id)

        client = await AccountCleanerService.get_client(user_id)
        if not client.is_connected():
            try:
                await client.connect()
            except Exception as conn_err:
                err_text = str(conn_err)
                if "403" in err_text or "forbidden" in err_text.lower():
                    raise RuntimeError(
                        "PythonAnywhere (bepul tarif) Telegram MTProto to'g'ridan-to'g'ri ulanishini cheklaydi (403 Forbidden). "
                        "Telegram hisobni tozalash (Cleaner) funksiyasi ishlashi uchun botni kompyuteringizda (run.bat) "
                        "yoki cheklovsiz VPS serverda ishga tushiring."
                    )
                raise conn_err

        def _get_delivery_info(sent_type) -> str:
            type_name = type(sent_type).__name__.lower()
            if "app" in type_name:
                return (
                    "📲 <b>Kod Telegram ilovangiz ichidagi rasmiy «Telegram» (Service Notifications) chatiga yuborildi!</b>\n\n"
                    "⚠️ <i>Diqqat: Kod oddiy SMS ga EMAS, aynan Telegram ilovangiz ichiga keldi.</i>\n"
                    "Telegram ilovasidagi chatlar ro'yxatidan <b>Telegram</b> chatini oching va 5 xonali kodni oling."
                )
            elif "sms" in type_name:
                return "📩 <b>Kod telefoningizga oddiy SMS xabar orqali yuborildi.</b>"
            elif "call" in type_name:
                return "📞 <b>Telegram telefoningizga qo'ng'iroq qilib kodni aytadi.</b>"
            return "📩 <b>Kod Telegram orqali yuborildi (Telegram chatini yoki SMS ni tekshiring).</b>"

        try:
            result = await client.send_code_request(phone)
            AccountCleanerService._phone_hashes[user_id] = result.phone_code_hash
            delivery_text = _get_delivery_info(result.type)
            return result.phone_code_hash, delivery_text
        except FloodWaitError as e:
            time_str = format_seconds(e.seconds)
            raise RuntimeError(
                f"Telegram cheklovi (FloodWait)! Juda ko'p kod so'ralgani uchun Telegram vaqtincha blokladi. "
                f"Iltimos, {time_str} kuting yoki QR Kod orqali kiring."
            )
        except PhoneNumberInvalidError:
            raise ValueError("Telefon raqam noto'g'ri kiritildi! Masalan: +998901234567")
        except PhoneNumberBannedError:
            raise PermissionError("Ushbu telefon raqam Telegram tomonidan bloklangan!")
        except Exception as e:
            err_text = str(e)
            if "403" in err_text or "forbidden" in err_text.lower():
                raise RuntimeError(
                    "PythonAnywhere (bepul tarif) Telegram MTProto ulanishini cheklaydi (403 Forbidden). "
                    "Cleaner to'liq ishlashi uchun botni o'zingizning kompyuteringizda (run.bat) ishga tushiring."
                )
            if "ResendCodeRequest" in err_text or "all available options" in err_text:
                # Kod allaqachon yuborilgan bo'lsa, xatolik chiqarmaydi
                saved_hash = AccountCleanerService._phone_hashes.get(user_id, "")
                return (
                    saved_hash,
                    "📲 <b>Telegram ilovangizga allaqachon kod yuborilgan!</b>\n\n"
                    "Telegram ilovasidagi rasmiy «Telegram» (Service Notifications) chatini oching va kelgan 5 xonali kodni yozing."
                )

            logger.warning(f"Telegram bilan ulanishda xato, qayta ulanmoqda: {e}")
            try:
                await client.connect()
                result = await client.send_code_request(phone)
                AccountCleanerService._phone_hashes[user_id] = result.phone_code_hash
                delivery_text = _get_delivery_info(result.type)
                return result.phone_code_hash, delivery_text
            except FloodWaitError as fe:
                time_str = format_seconds(fe.seconds)
                raise RuntimeError(f"Telegram cheklovi (FloodWait)! Iltimos, {time_str} kuting.")
            except Exception as e2:
                err2_text = str(e2)
                if "403" in err2_text or "forbidden" in err2_text.lower():
                    raise RuntimeError(
                        "PythonAnywhere bepul tarifida 403 Forbidden cheklovi mavjud. "
                        "Botni o'z kompyuteringizda ishga tushiring."
                    )
                if "ResendCodeRequest" in err2_text or "all available options" in err2_text:
                    saved_hash = AccountCleanerService._phone_hashes.get(user_id, "")
                    return (
                        saved_hash,
                        "📲 <b>Telegram ilovangizga allaqachon kod yuborilgan!</b>\n\n"
                        "Telegram ilovasidagi rasmiy «Telegram» chatini oching va 5 xonali kodni yozing."
                    )
                raise e2

    @staticmethod
    async def complete_sign_in(user_id: int, phone: str, code: str, password: Optional[str] = None) -> tuple[bool, str]:
        """Tasdiqlash kodi va (agar bor bo'lsa 2FA parol) orqali tizimga kirish."""
        client = await AccountCleanerService.get_client(user_id)
        if not client.is_connected():
            await client.connect()

        from telethon.errors import (
            SessionPasswordNeededError,
            PhoneCodeInvalidError,
            PhoneCodeExpiredError,
            PasswordHashInvalidError,
            FloodWaitError,
        )

        try:
            # Agar 2FA parol yuborilgan bo'lsa, kodni qayta kiritmasdan to'g'ridan-to'g'ri parol orqali kiriladi
            if password:
                try:
                    await client.sign_in(password=password)
                    me = await client.get_me()
                    first_name = getattr(me, 'first_name', '') or 'Foydalanuvchi'
                    username = f"@{me.username}" if getattr(me, 'username', None) else f"ID: {me.id}"
                    phone_val = getattr(me, 'phone', '') or phone
                    AccountCleanerService.save_profile(user_id, {
                        "id": me.id,
                        "name": first_name,
                        "username": username,
                        "phone": phone_val
                    })
                    return True, f"✅ Muvaffaqiyatli ulandi: {first_name} ({username})"
                except PasswordHashInvalidError:
                    return False, "❌ 2FA paroli noto'g'ri kiritildi!"
                except FloodWaitError as fe:
                    time_str = format_seconds(fe.seconds)
                    return False, f"⏳ Telegram cheklovi (FloodWait): Iltimos, {time_str} kuting."
                except Exception as err:
                    return False, f"2FA bilan kirishda xatolik: {str(err)}"

            # 1-bosqich: Telefon raqam va kod orqali kirish
            phone_code_hash = AccountCleanerService._phone_hashes.get(user_id)
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            me = await client.get_me()
            first_name = getattr(me, 'first_name', '') or 'Foydalanuvchi'
            username = f"@{me.username}" if getattr(me, 'username', None) else f"ID: {me.id}"
            phone_val = getattr(me, 'phone', '') or phone
            AccountCleanerService.save_profile(user_id, {
                "id": me.id,
                "name": first_name,
                "username": username,
                "phone": phone_val
            })
            return True, f"✅ Muvaffaqiyatli ulandi: {first_name} ({username})"

        except SessionPasswordNeededError:
            return False, "2FA_REQUIRED"
        except PhoneCodeInvalidError:
            return False, "❌ Tasdiqlash kodi noto'g'ri kiritildi!"
        except PhoneCodeExpiredError:
            return False, "❌ Tasdiqlash kodi muddati o'tgan! Iltimos, qaytadan kod so'rang."
        except FloodWaitError as fe:
            time_str = format_seconds(fe.seconds)
            return False, f"⏳ Telegram cheklovi (FloodWait): Iltimos, {time_str} kuting."
        except Exception as e:
            return False, f"Kirishda xatolik: {str(e)}"

    @staticmethod
    async def scan_deleted_accounts(user_id: int) -> list[dict]:
        """O'chib ketgan (Deleted Account) hisoblarni aniqlaydi."""
        client = await AccountCleanerService.get_client(user_id)
        deleted_dialogs = []

        dialogs = await client.get_dialogs()
        for d in dialogs:
            if d.is_user and d.entity:
                entity = d.entity
                is_self = getattr(entity, 'is_self', False) or getattr(entity, 'self', False)
                if is_self or d.id == 777000 or getattr(entity, 'support', False):
                    continue

                is_deleted = getattr(entity, 'deleted', False)
                first_name = (getattr(entity, 'first_name', '') or '').lower()
                dialog_name = (d.name or '').lower()

                if is_deleted or "deleted account" in first_name or "deleted account" in dialog_name:
                    deleted_dialogs.append({
                        "id": d.id,
                        "title": d.name or "Deleted Account",
                        "unread_count": d.unread_count,
                    })

        return deleted_dialogs

    @staticmethod
    async def remove_deleted_accounts(user_id: int) -> int:
        """Barcha 'Deleted Account' bo'lib qolgan chatlarni o'chiradi."""
        from telethon.errors import FloodWaitError

        client = await AccountCleanerService.get_client(user_id)
        deleted_list = await AccountCleanerService.scan_deleted_accounts(user_id)
        count = 0

        for item in deleted_list:
            try:
                await client.delete_dialog(item["id"], revoke=False)
                count += 1
                await asyncio.sleep(0.3)  # Telegram Flood limitidan saqlanish
            except FloodWaitError as fe:
                if fe.seconds <= 15:
                    await asyncio.sleep(fe.seconds + 1)
                    try:
                        await client.delete_dialog(item["id"], revoke=False)
                        count += 1
                    except Exception:
                        pass
                else:
                    logger.warning(f"Katta FloodWait ({fe.seconds}s), to'xtatildi")
                    break
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

                if dialog_date is None or dialog_date < cutoff_date:
                    days_ago = (datetime.now(timezone.utc) - dialog_date).days if dialog_date else "Noma'lum"
                    last_active = dialog_date.strftime("%Y-%m-%d") if dialog_date else "Xabar yo'q"
                    inactive_list.append({
                        "id": d.id,
                        "title": d.name or "Noma'lum kanal/guruh",
                        "is_channel": d.is_channel,
                        "is_group": d.is_group,
                        "days_ago": days_ago,
                        "last_active": last_active,
                    })

        return inactive_list

    @staticmethod
    async def leave_inactive_channels(user_id: int, channel_ids: list[int]) -> int:
        """Ko'rsatilgan faol bo'lmagan kanallar va guruhlardan chiqib ketadi (Leave Chat)."""
        from telethon.errors import FloodWaitError

        client = await AccountCleanerService.get_client(user_id)
        left_count = 0

        for ch_id in channel_ids:
            try:
                await client.delete_dialog(ch_id)
                left_count += 1
                await asyncio.sleep(0.4)
            except FloodWaitError as fe:
                if fe.seconds <= 15:
                    await asyncio.sleep(fe.seconds + 1)
                    try:
                        await client.delete_dialog(ch_id)
                        left_count += 1
                    except Exception:
                        pass
                else:
                    logger.warning(f"Katta FloodWait ({fe.seconds}s), to'xtatildi")
                    break
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
            if d.is_user and d.entity:
                entity = d.entity
                is_self = getattr(entity, 'is_self', False) or getattr(entity, 'self', False)
                # Saqlangan xabarlar (Saved Messages), Telegram rasmiy xabarlari (777000) va qadalgan chatlarni o'tkazib yuborish
                if is_self or d.id == 777000 or getattr(entity, 'support', False) or getattr(entity, 'verified', False):
                    continue
                if getattr(d, 'pinned', False):
                    continue

                dialog_date = d.date
                if dialog_date and dialog_date.tzinfo is None:
                    dialog_date = dialog_date.replace(tzinfo=timezone.utc)

                if dialog_date is not None and dialog_date < cutoff_date:
                    days_ago = (datetime.now(timezone.utc) - dialog_date).days
                    title = d.name or getattr(entity, 'first_name', '') or 'Foydalanuvchi'
                    old_dialogs.append({
                        "id": d.id,
                        "title": title,
                        "days_ago": days_ago,
                        "last_active": dialog_date.strftime("%Y-%m-%d"),
                    })
                elif dialog_date is None:
                    title = d.name or getattr(entity, 'first_name', '') or 'Bo\'sh chat'
                    old_dialogs.append({
                        "id": d.id,
                        "title": title,
                        "days_ago": "Noma'lum",
                        "last_active": "Xabar yo'q",
                    })

        return old_dialogs

    @staticmethod
    async def delete_old_dialogs(user_id: int, dialog_ids: list[int]) -> int:
        """Eski dialoglarni tozalaydi."""
        from telethon.errors import FloodWaitError

        client = await AccountCleanerService.get_client(user_id)
        deleted_count = 0

        for d_id in dialog_ids:
            try:
                await client.delete_dialog(d_id, revoke=False)
                deleted_count += 1
                await asyncio.sleep(0.3)
            except FloodWaitError as fe:
                if fe.seconds <= 15:
                    await asyncio.sleep(fe.seconds + 1)
                    try:
                        await client.delete_dialog(d_id, revoke=False)
                        deleted_count += 1
                    except Exception:
                        pass
                else:
                    logger.warning(f"Katta FloodWait ({fe.seconds}s), to'xtatildi")
                    break
            except Exception as e:
                logger.warning(f"Dialogni o'chirishda xatolik ({d_id}): {e}")

        return deleted_count
