import os
import re
import asyncio
import time
from pathlib import Path
from typing import Optional, Callable
from config import BASE_DIR, get_user_cwd
from services.account_cleaner_service import AccountCleanerService
from utils.helpers import format_bytes, escape_html
from utils.logger import logger

VIDEOS_DIR = BASE_DIR / "videolar"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = VIDEOS_DIR


class MediaDownloaderService:
    """Telegram kanallar (jumladan yopiq/private kanallar)dan video va medialarni yuklab olish xizmati."""

    @staticmethod
    def parse_telegram_link(link: str) -> tuple[int | str | None, list[int]]:
        """
        Telegram havola (link) matnidan kanal ID va xabar ID(lar)ini ajratib oladi.
        Qo'llab-quvvatlanadi:
        - https://t.me/c/1234567890/45 (Yopiq kanal)
        - https://t.me/c/1234567890/45-50 (Yopiq kanal xabarlar oralig'i)
        - https://t.me/channel_name/45 (Ommaviy kanal)
        - https://t.me/channel_name/45-50 (Ommaviy kanal oralig'i)
        """
        link = link.strip()

        # 1. Yopiq kanal oralig'i: t.me/c/123456789/10-15
        m_priv_range = re.search(r't\.me/c/(\d+)/(\d+)-(\d+)', link)
        if m_priv_range:
            ch_id = int("-100" + m_priv_range.group(1))
            start_id = int(m_priv_range.group(2))
            end_id = int(m_priv_range.group(3))
            msg_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
            return ch_id, msg_ids

        # 2. Yopiq kanal bitta xabar: t.me/c/123456789/10
        m_priv = re.search(r't\.me/c/(\d+)/(\d+)', link)
        if m_priv:
            ch_id = int("-100" + m_priv.group(1))
            return ch_id, [int(m_priv.group(2))]

        # 3. Ommaviy kanal oralig'i: t.me/channel/10-15
        m_pub_range = re.search(r't\.me/([a-zA-Z0-9_]+)/(\d+)-(\d+)', link)
        if m_pub_range:
            username = m_pub_range.group(1)
            start_id = int(m_pub_range.group(2))
            end_id = int(m_pub_range.group(3))
            msg_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
            return username, msg_ids

        # 4. Ommaviy kanal bitta xabar: t.me/channel/10
        m_pub = re.search(r't\.me/([a-zA-Z0-9_]+)/(\d+)', link)
        if m_pub:
            username = m_pub.group(1)
            return username, [int(m_pub.group(2))]

        return None, []

    @staticmethod
    async def get_user_channels(user_id: int) -> list[dict]:
        """Foydalanuvchi a'zo bo'lgan barcha kanallar va guruhlar ro'yxatini oladi."""
        client = await AccountCleanerService.get_client(user_id)
        channels = []
        dialogs = await client.get_dialogs()
        for d in dialogs:
            if d.is_channel or d.is_group:
                channels.append({
                    "id": d.id,
                    "title": d.name or "Noma'lum kanal",
                    "is_channel": d.is_channel,
                    "is_group": d.is_group,
                    "username": getattr(d.entity, "username", None),
                })
        return channels

    @staticmethod
    async def download_videos_from_link(
        user_id: int,
        link: str,
        save_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, float], None]] = None
    ) -> list[dict]:
        """
        Berilgan link orqali yopiq yoki ochiq kanaldan videolarni yuklab oladi.
        """
        ch_peer, msg_ids = MediaDownloaderService.parse_telegram_link(link)
        if not ch_peer or not msg_ids:
            raise ValueError(
                "Noto'g'ri Telegram havolasi!\n"
                "To'g'ri formatlar:\n"
                "• Yopiq kanal: <code>https://t.me/c/1234567890/45</code>\n"
                "• Yopiq kanal oralig'i: <code>https://t.me/c/1234567890/45-50</code>\n"
                "• Ommaviy kanal: <code>https://t.me/channel_name/45</code>"
            )

        if not await AccountCleanerService.is_authorized(user_id):
            raise PermissionError(
                "Yopiq kanaldan video yuklash uchun avval botda Telegram hisobingizga kirishingiz kerak.\n"
                "Buning uchun /cleaner buyrug'ini bosing va '📷 QR Kod orqali kirish' orqali ulaning."
            )

        client = await AccountCleanerService.get_client(user_id)
        target_dir = save_dir or DOWNLOADS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files = []
        last_progress_time = 0

        for msg_id in msg_ids:
            try:
                msg = await client.get_messages(ch_peer, ids=msg_id)
                if not msg or not msg.media:
                    continue

                # Media turi va nomini aniqlash
                filename = f"video_{ch_peer}_{msg_id}.mp4"
                if hasattr(msg, "file") and msg.file and msg.file.name:
                    filename = msg.file.name
                elif hasattr(msg, "video") and msg.video:
                    filename = f"video_{ch_peer}_{msg_id}.mp4"
                elif hasattr(msg, "document") and msg.document:
                    filename = getattr(msg.file, 'name', None) or f"doc_{ch_peer}_{msg_id}.bin"

                out_path = target_dir / filename

                def _telethon_progress(current, total):
                    nonlocal last_progress_time
                    now = time.time()
                    if now - last_progress_time >= 1.5 or current == total:
                        last_progress_time = now
                        percent = (current / total) * 100 if total else 0
                        if progress_callback:
                            try:
                                progress_callback(current, total, filename, percent)
                            except Exception:
                                pass

                # Yuklab olish
                actual_path = await client.download_media(
                    msg,
                    file=str(out_path),
                    progress_callback=_telethon_progress
                )

                if actual_path and Path(actual_path).exists():
                    file_size = Path(actual_path).stat().st_size
                    downloaded_files.append({
                        "msg_id": msg_id,
                        "path": str(actual_path),
                        "filename": Path(actual_path).name,
                        "size_bytes": file_size,
                        "size_formatted": format_bytes(file_size),
                    })

            except Exception as e:
                logger.error(f"Xabar #{msg_id} ni yuklab olishda xatolik: {e}")

        return downloaded_files

    @staticmethod
    async def scan_and_download_channel_videos(
        user_id: int,
        channel_id: int | str,
        limit: int = 10,
        save_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, float], None]] = None
    ) -> list[dict]:
        """
        Kanal ichidagi oxirgi N ta videoni avtomatik qidirib yuklab oladi.
        """
        if not await AccountCleanerService.is_authorized(user_id):
            raise PermissionError("Avval hisobingizga kiring (/cleaner).")

        client = await AccountCleanerService.get_client(user_id)
        target_dir = save_dir or DOWNLOADS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        downloaded_files = []
        last_progress_time = 0

        count = 0
        async for msg in client.iter_messages(channel_id):
            if count >= limit:
                break
            if msg.video or (msg.document and "video" in getattr(msg.document, 'mime_type', '')):
                count += 1
                filename = f"video_{channel_id}_{msg.id}.mp4"
                if hasattr(msg, "file") and msg.file and msg.file.name:
                    filename = msg.file.name

                out_path = target_dir / filename

                def _telethon_progress(current, total):
                    nonlocal last_progress_time
                    now = time.time()
                    if now - last_progress_time >= 1.5 or current == total:
                        last_progress_time = now
                        percent = (current / total) * 100 if total else 0
                        if progress_callback:
                            try:
                                progress_callback(current, total, filename, percent)
                            except Exception:
                                pass

                try:
                    actual_path = await client.download_media(
                        msg,
                        file=str(out_path),
                        progress_callback=_telethon_progress
                    )
                    if actual_path and Path(actual_path).exists():
                        file_size = Path(actual_path).stat().st_size
                        downloaded_files.append({
                            "msg_id": msg.id,
                            "path": str(actual_path),
                            "filename": Path(actual_path).name,
                            "size_bytes": file_size,
                            "size_formatted": format_bytes(file_size),
                        })
                except Exception as dl_err:
                    logger.error(f"Videoni yuklab olishda xatolik ({msg.id}): {dl_err}")

        return downloaded_files
