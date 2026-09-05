import os
import time
import asyncio
from pathlib import Path
from typing import Optional, Callable, Union
from telethon import TelegramClient, utils
from telethon.tl.types import InputFileBig, InputFile
import config
from utils.logger import logger
from utils.helpers import format_bytes, format_speed, format_eta

DATA_DIR = config.BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SESSION_NAME = str(DATA_DIR / "bot_mtproto_session")


class BotClientService:
    """
    Telethon MTProto asosidagi Telegram Bot Mijozi.
    HTTP Bot API ning 50MB chegarasini butunlay chetlab o'tadi va
    2000MB (2GB) gacha bo'lgan videolarni to'g'ridan-to'g'ri bot nomidan chatga yetkazadi.
    """
    _client: Optional[TelegramClient] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_client(cls) -> Optional[TelegramClient]:
        if cls._client and cls._client.is_connected():
            return cls._client

        async with cls._lock:
            if cls._client and cls._client.is_connected():
                return cls._client

            if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH or not config.BOT_TOKEN:
                logger.error("BotClientService: TELEGRAM_API_ID, TELEGRAM_API_HASH yoki BOT_TOKEN topilmadi!")
                return None

            try:
                client = TelegramClient(
                    SESSION_NAME,
                    int(config.TELEGRAM_API_ID),
                    config.TELEGRAM_API_HASH,
                    device_model="Desktop (Bot MTProto)",
                    system_version="Linux / Windows",
                    app_version="5.5.0 x64"
                )
                await client.start(bot_token=config.BOT_TOKEN)
                cls._client = client
                bot_me = await client.get_me()
                logger.info(f"BotClientService (2GB MTProto) ishga tushdi: @{bot_me.username}")
                return cls._client
            except Exception as e:
                logger.error(f"BotClientService ishga tushirishda xatolik: {e}")
                return None

    @classmethod
    async def send_file_to_user(
        cls,
        user_id: int,
        file_path: Union[str, Path],
        caption: str = "",
        is_video: bool = True,
        is_audio: bool = False,
        thumb_path: Optional[Union[str, Path]] = None,
        duration: int = 0,
        progress_callback: Optional[Callable[[int, int, float, float], None]] = None
    ) -> bool:
        """
        Faylni 2000MB (2GB) gacha hajmda to'g'ridan-to'g'ri bot nomidan foydalanuvchiga yuboradi.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"send_file_to_user: Fayl topilmadi: {file_path}")
            return False

        client = await cls.get_client()
        if not client:
            logger.error("BotClientService: MTProto client mavjud emas!")
            return False

        file_size = file_path.stat().st_size
        logger.info(f"Bot MTProto orqali yuborilmoqda: {file_path.name} ({format_bytes(file_size)}) -> user {user_id}")

        start_time = time.time()
        last_time = 0

        def _prog(current, total):
            nonlocal last_time
            now = time.time()
            if progress_callback and total and (now - last_time >= 1.5 or current >= total):
                last_time = now
                elapsed = max(now - start_time, 0.001)
                speed = current / elapsed
                eta = (total - current) / speed if speed > 0 else 0
                try:
                    progress_callback(current, total, speed, eta)
                except Exception:
                    pass

        try:
            # 100MB - 2000MB fayllarni to'g'ridan-to'g'ri bot chatga uzatish
            attributes = []
            if is_video:
                from telethon.tl.types import DocumentAttributeVideo
                attributes.append(DocumentAttributeVideo(
                    duration=duration or 0,
                    w=1280,
                    h=720,
                    supports_streaming=True
                ))
            elif is_audio:
                from telethon.tl.types import DocumentAttributeAudio
                attributes.append(DocumentAttributeAudio(
                    duration=duration or 0,
                    title=file_path.stem,
                    performer="Telegram Dev Bridge"
                ))

            await client.send_file(
                entity=user_id,
                file=str(file_path),
                caption=caption,
                parse_mode="html",
                supports_streaming=True,
                attributes=attributes if attributes else None,
                thumb=str(thumb_path) if thumb_path and Path(thumb_path).exists() else None,
                progress_callback=_prog
            )
            logger.info(f"Fayl muvaffaqiyatli yetkazildi: {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Bot MTProto send_file xatoligi: {e}")
            return False
