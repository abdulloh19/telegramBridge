import os
import math
import time
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Callable, Union, Tuple
from telethon import TelegramClient, utils
from telethon.tl.functions.upload import (
    GetFileRequest,
    SaveBigFilePartRequest,
    SaveFilePartRequest
)
from telethon.tl.types import (
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    InputFileBig,
    InputFile,
    Document,
    MessageMediaDocument,
    MessageMediaPhoto,
    TypeInputFileLocation,
)
from utils.logger import logger

CHUNK_SIZE = 512 * 1024  # 512 KB (Telegram MTProto ruxsat bergan maksimal blok hajmi)
DEFAULT_WORKERS = 8       # Parallel oqimlar soni


class FastTelethon:
    """
    Telethon uchun yuqori tezlikdagi Multi-Part Parallel yuklab olish va yuklash drayveri.
    Eksport senderlarsiz to'g'ridan-to'g'ri klient orqali 512KB bloklarda parallel ishlaydi.
    """

    @staticmethod
    def extract_file_info(media_or_msg) -> Tuple[Optional[TypeInputFileLocation], Optional[int], int, str]:
        """Telegram xabari yoki media obyektidan location, dc_id, hajmi va fayl nomini aniqlaydi."""
        if hasattr(media_or_msg, "media") and media_or_msg.media:
            media = media_or_msg.media
        else:
            media = media_or_msg

        filename = "video.mp4"
        file_size = 0
        dc_id = None
        location = None

        if isinstance(media, MessageMediaDocument) and media.document:
            doc = media.document
            dc_id = doc.dc_id
            file_size = doc.size
            location = InputDocumentFileLocation(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
                thumb_size=""
            )
            for attr in getattr(doc, "attributes", []):
                if hasattr(attr, "file_name") and attr.file_name:
                    filename = attr.file_name
                    break

        elif isinstance(media, Document):
            dc_id = media.dc_id
            file_size = media.size
            location = InputDocumentFileLocation(
                id=media.id,
                access_hash=media.access_hash,
                file_reference=media.file_reference,
                thumb_size=""
            )
            for attr in getattr(media, "attributes", []):
                if hasattr(attr, "file_name") and attr.file_name:
                    filename = attr.file_name
                    break

        elif isinstance(media, MessageMediaPhoto) and media.photo:
            photo = media.photo
            dc_id = photo.dc_id
            largest = photo.sizes[-1] if photo.sizes else None
            file_size = getattr(largest, "size", 0)
            thumb_type = getattr(largest, "type", "y") if largest else "y"
            location = InputPhotoFileLocation(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference,
                thumb_size=thumb_type
            )
            filename = f"photo_{photo.id}.jpg"

        else:
            try:
                location = utils.get_input_location(media)
                dc_id = getattr(media, "dc_id", None)
                file_size = getattr(media, "size", 0)
            except Exception:
                location = None

        return location, dc_id, file_size, filename

    @classmethod
    async def download_media(
        cls,
        client: TelegramClient,
        media_or_msg,
        out_path: Union[str, Path],
        workers: int = DEFAULT_WORKERS,
        progress_callback: Optional[Callable[[int, int, float, float], None]] = None
    ) -> Path:
        """Mediani 512KB bloklarda parallel oqimlarda maksimal tezlikda yuklab oladi."""
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        location, dc_id, file_size, _ = cls.extract_file_info(media_or_msg)

        if not location or not file_size or file_size < CHUNK_SIZE * 2:
            start_time = time.time()
            def _std_cb(current, total):
                if progress_callback and total:
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    progress_callback(current, total, speed, eta)

            res = await client.download_media(media_or_msg, file=str(out_path), progress_callback=_std_cb)
            return Path(res) if res else out_path

        try:
            part_count = math.ceil(file_size / CHUNK_SIZE)
            workers_count = min(workers, part_count, 12)

            queue = asyncio.Queue()
            for i in range(part_count):
                queue.put_nowait(i)

            downloaded_bytes = 0
            lock = asyncio.Lock()
            start_time = time.time()
            last_progress_time = 0
            failed_attempts = 0

            # Fayl hajmini diskda oldindan ajratish
            with open(out_path, "wb") as f:
                f.seek(file_size - 1)
                f.write(b"\0")

            async def _worker():
                nonlocal downloaded_bytes, last_progress_time, failed_attempts
                with open(out_path, "r+b") as fp:
                    while not queue.empty():
                        try:
                            part_idx = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                        offset = part_idx * CHUNK_SIZE
                        limit = CHUNK_SIZE

                        req = GetFileRequest(
                            location=location,
                            offset=offset,
                            limit=limit,
                            precise=False,
                            cdn_supported=False
                        )

                        success = False
                        for attempt in range(3):
                            try:
                                res = await client(req)
                                data = res.bytes
                                fp.seek(offset)
                                fp.write(data)

                                async with lock:
                                    downloaded_bytes += len(data)
                                    now = time.time()
                                    if progress_callback and (now - last_progress_time >= 1.0 or downloaded_bytes >= file_size):
                                        last_progress_time = now
                                        elapsed = max(now - start_time, 0.001)
                                        speed = downloaded_bytes / elapsed
                                        eta = (file_size - downloaded_bytes) / speed if speed > 0 else 0
                                        try:
                                            progress_callback(downloaded_bytes, file_size, speed, eta)
                                        except Exception:
                                            pass
                                success = True
                                break
                            except Exception as e:
                                err_s = str(e)
                                if "FileMigrateError" in err_s or "dc" in err_s.lower():
                                    failed_attempts += 5
                                    break
                                logger.warning(f"FastTelethon Part #{part_idx} urinish #{attempt+1}: {e}")
                                await asyncio.sleep(0.3)

                        if not success:
                            failed_attempts += 1
                            if failed_attempts < 6:
                                await queue.put(part_idx)
                                await asyncio.sleep(0.5)

                        queue.task_done()

            tasks = [asyncio.create_task(_worker()) for _ in range(workers_count)]
            await queue.join()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            if failed_attempts >= 6 or not out_path.exists() or out_path.stat().st_size < file_size * 0.95:
                raise RuntimeError("FastTelethon parallel download to'liq yakunlanmadi, standart yuklashga o'tilmoqda.")

            return out_path
        except Exception as fast_err:
            logger.info(f"FastTelethon standart Telethon yuklashga o'tmoqda: {fast_err}")
            start_time = time.time()
            def _fallback_cb(current, total):
                if progress_callback and total:
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    progress_callback(current, total, speed, eta)

            res = await client.download_media(media_or_msg, file=str(out_path), progress_callback=_fallback_cb)
            return Path(res) if res else out_path

    @classmethod
    async def upload_file(
        cls,
        client: TelegramClient,
        file_path: Union[str, Path],
        workers: int = DEFAULT_WORKERS,
        progress_callback: Optional[Callable[[int, int, float, float], None]] = None
    ) -> Union[InputFileBig, InputFile]:
        """Faylni Telegram serverlariga 512KB bloklarda parallel oqimlarda maksimal tezlikda yuklaydi."""
        file_path = Path(file_path)
        file_size = file_path.stat().st_size
        file_name = file_path.name

        if file_size < CHUNK_SIZE * 2:
            start_time = time.time()
            def _std_up_cb(current, total):
                if progress_callback and total:
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    progress_callback(current, total, speed, eta)

            return await client.upload_file(str(file_path), progress_callback=_std_up_cb)

        part_count = math.ceil(file_size / CHUNK_SIZE)
        workers_count = min(workers, part_count, 12)
        is_big = file_size > 10 * 1024 * 1024
        file_id = utils.get_random_int()

        queue = asyncio.Queue()
        for i in range(part_count):
            queue.put_nowait(i)

        uploaded_bytes = 0
        lock = asyncio.Lock()
        start_time = time.time()
        last_progress_time = 0

        async def _upload_worker():
            nonlocal uploaded_bytes, last_progress_time
            with open(file_path, "rb") as fp:
                while not queue.empty():
                    try:
                        part_idx = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    offset = part_idx * CHUNK_SIZE
                    fp.seek(offset)
                    chunk_data = fp.read(CHUNK_SIZE)

                    if is_big:
                        req = SaveBigFilePartRequest(
                            file_id=file_id,
                            file_part=part_idx,
                            file_total_parts=part_count,
                            bytes=chunk_data
                        )
                    else:
                        req = SaveFilePartRequest(
                            file_id=file_id,
                            file_part=part_idx,
                            bytes=chunk_data
                        )

                    success = False
                    for attempt in range(4):
                        try:
                            await client(req)
                            async with lock:
                                uploaded_bytes += len(chunk_data)
                                now = time.time()
                                if progress_callback and (now - last_progress_time >= 1.0 or uploaded_bytes >= file_size):
                                    last_progress_time = now
                                    elapsed = max(now - start_time, 0.001)
                                    speed = uploaded_bytes / elapsed
                                    eta = (file_size - uploaded_bytes) / speed if speed > 0 else 0
                                    try:
                                        progress_callback(uploaded_bytes, file_size, speed, eta)
                                    except Exception:
                                        pass
                            success = True
                            break
                        except Exception as e:
                            logger.warning(f"FastTelethon upload part #{part_idx} urinish #{attempt+1}: {e}")
                            await asyncio.sleep(0.3)

                    if not success:
                        await queue.put(part_idx)
                        await asyncio.sleep(0.5)

                    queue.task_done()

        tasks = [asyncio.create_task(_upload_worker()) for _ in range(workers_count)]
        await queue.join()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if is_big:
            return InputFileBig(id=file_id, parts=part_count, name=file_name)
        else:
            with open(file_path, "rb") as f:
                md5_hash = hashlib.md5(f.read()).hexdigest()
            return InputFile(id=file_id, parts=part_count, name=file_name, md5_checksum=md5_hash)
