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
    InputPeerPhotoFileLocation,
    InputFileBig,
    InputFile,
    Document,
    Photo,
    MessageMediaDocument,
    MessageMediaPhoto,
    TypeInputFileLocation,
)
from utils.logger import logger

CHUNK_SIZE = 512 * 1024  # 512 KB (Telegram MTProto ruxsat bergan eng katta blok hajmi)
DEFAULT_WORKERS = 4       # Parallel oqimlar / ulanishlar soni


class FastTelethon:
    """
    Telethon uchun ko'p oqimli (Multi-part parallel) yuqori tezlikdagi fayl yuklab oluvchi va yuklovchi.
    Oddiy sequential yuklashga nisbatan tezlikni 10-20 baravargacha oshiradi.
    """

    @staticmethod
    def extract_file_info(media_or_msg) -> Tuple[Optional[TypeInputFileLocation], Optional[int], int, str]:
        """
        Telegram xabari yoki media obyektidan location, dc_id, hajmi va fayl nomini aniqlaydi.
        """
        # Agar Message obyekti berilgan bo'lsa
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
            # Fayl nomini izlash
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
        """
        Mediani parallel oqimlarda yuklab oladi.
        progress_callback: (downloaded_bytes, total_bytes, speed_bytes_per_sec, eta_seconds)
        """
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        location, dc_id, file_size, default_filename = cls.extract_file_info(media_or_msg)

        # Agar location yoki hajm aniqlanmasa, yoki juda kichik bo'lsa (1MB dan kichik), standart usulda yuklaymiz
        if not location or not file_size or file_size < CHUNK_SIZE * 2:
            start_time = time.time()
            last_bytes = 0

            def _std_cb(current, total):
                if progress_callback and total:
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    progress_callback(current, total, speed, eta)

            res = await client.download_media(media_or_msg, file=str(out_path), progress_callback=_std_cb)
            return Path(res) if res else out_path

        if not dc_id:
            dc_id = client.session.dc_id

        part_count = math.ceil(file_size / CHUNK_SIZE)
        workers_count = min(workers, part_count, 8)

        senders = []
        try:
            for _ in range(workers_count):
                sender = await client._borrow_exported_sender(dc_id)
                senders.append(sender)
        except Exception as err:
            logger.warning(f"FastTelethon sender olishda xato ({err}), standart yuklashga o'tilmoqda.")
            for s in senders:
                try:
                    await client._return_exported_sender(s)
                except Exception:
                    pass

            start_time = time.time()
            def _std_fallback_cb(current, total):
                if progress_callback and total:
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    progress_callback(current, total, speed, eta)

            res = await client.download_media(media_or_msg, file=str(out_path), progress_callback=_std_fallback_cb)
            return Path(res) if res else out_path

        queue = asyncio.Queue()
        for i in range(part_count):
            queue.put_nowait(i)

        downloaded_bytes = 0
        lock = asyncio.Lock()
        start_time = time.time()
        last_progress_time = 0

        # Fayl diskda joy ajratish
        with open(out_path, "wb") as f:
            f.seek(file_size - 1)
            f.write(b"\0")

        async def _worker(sender):
            nonlocal downloaded_bytes, last_progress_time
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
                            res = await sender.send(req)
                            data = res.bytes
                            fp.seek(offset)
                            fp.write(data)

                            async with lock:
                                downloaded_bytes += len(data)
                                now = time.time()
                                if progress_callback and (now - last_progress_time >= 1.5 or downloaded_bytes >= file_size):
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
                            logger.warning(f"FastTelethon Part #{part_idx} urinish #{attempt+1} xato: {e}")
                            await asyncio.sleep(0.5)

                    if not success:
                        logger.error(f"Part #{part_idx} yuklanmadi, qayta navbatga qo'yildi.")
                        await queue.put(part_idx)
                        await asyncio.sleep(1.0)

                    queue.task_done()

        try:
            tasks = [asyncio.create_task(_worker(s)) for s in senders]
            await queue.join()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for s in senders:
                try:
                    await client._return_exported_sender(s)
                except Exception:
                    pass

        return out_path

    @classmethod
    async def upload_file(
        cls,
        client: TelegramClient,
        file_path: Union[str, Path],
        workers: int = DEFAULT_WORKERS,
        progress_callback: Optional[Callable[[int, int, float, float], None]] = None
    ) -> Union[InputFileBig, InputFile]:
        """
        Faylni Telegram serverlariga parallel oqimlarda (512KB) yuqori tezlikda yuklaydi.
        """
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
        workers_count = min(workers, part_count, 8)
        is_big = file_size > 10 * 1024 * 1024  # 10 MB dan katta bo'lsa BigFile
        file_id = utils.get_random_int()
        dc_id = client.session.dc_id

        senders = []
        try:
            for _ in range(workers_count):
                sender = await client._borrow_exported_sender(dc_id)
                senders.append(sender)
        except Exception as e:
            logger.warning(f"FastTelethon upload sender olishda xato ({e}), standart yuklashga o'tilmoqda.")
            for s in senders:
                try:
                    await client._return_exported_sender(s)
                except Exception:
                    pass

            start_time = time.time()
            def _std_fallback_up_cb(current, total):
                if progress_callback and total:
                    elapsed = max(time.time() - start_time, 0.001)
                    speed = current / elapsed
                    eta = (total - current) / speed if speed > 0 else 0
                    progress_callback(current, total, speed, eta)

            return await client.upload_file(str(file_path), progress_callback=_std_fallback_up_cb)

        queue = asyncio.Queue()
        for i in range(part_count):
            queue.put_nowait(i)

        uploaded_bytes = 0
        lock = asyncio.Lock()
        start_time = time.time()
        last_progress_time = 0

        async def _upload_worker(sender):
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
                    for attempt in range(3):
                        try:
                            await sender.send(req)
                            async with lock:
                                uploaded_bytes += len(chunk_data)
                                now = time.time()
                                if progress_callback and (now - last_progress_time >= 1.5 or uploaded_bytes >= file_size):
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
                            logger.warning(f"FastTelethon upload part #{part_idx} urinish #{attempt+1} xato: {e}")
                            await asyncio.sleep(0.5)

                    if not success:
                        await queue.put(part_idx)
                        await asyncio.sleep(1.0)

                    queue.task_done()

        try:
            tasks = [asyncio.create_task(_upload_worker(s)) for s in senders]
            await queue.join()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for s in senders:
                try:
                    await client._return_exported_sender(s)
                except Exception:
                    pass

        if is_big:
            return InputFileBig(id=file_id, parts=part_count, name=file_name)
        else:
            with open(file_path, "rb") as f:
                md5_hash = hashlib.md5(f.read()).hexdigest()
            return InputFile(id=file_id, parts=part_count, name=file_name, md5_checksum=md5_hash)
