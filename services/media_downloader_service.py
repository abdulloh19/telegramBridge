import os
import re
import asyncio
import time
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple
from config import BASE_DIR
from services.account_cleaner_service import AccountCleanerService
from services.fast_telethon import FastTelethon
from utils.helpers import format_bytes, escape_html, format_speed, format_eta
from utils.logger import logger

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

VIDEOS_DIR = BASE_DIR / "videolar"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = VIDEOS_DIR
AUDIO_DIR = VIDEOS_DIR / "audios"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


class MediaDownloaderService:
    """Telegram kanallar hamda tashqi platformalardan (YouTube, Instagram, TikTok, Pinterest va hk.)
    video va yuqori sifatli MP3 larni yuklab olish xizmati."""

    @staticmethod
    def parse_link(link: str) -> Dict[str, Any]:
        """
        Kiritilgan havolani tahlil qilib, uning turi va parametrlarini aniqlaydi:
        - Telegram: Yopiq kanal, ochiq kanal, xabarlar oralig'i, topic/forum havolalari
        - Tashqi: YouTube, Instagram, TikTok, Pinterest, Facebook, Twitter/X, to'g'ridan-to'g'ri video link
        """
        link = link.strip()

        # 1. TELEGRAM HAVOLALARI
        if "t.me/" in link or "telegram.me/" in link:
            clean_link = link.split("?")[0].split("#")[0].strip()

            # 1.1 Yopiq kanal topic oralig'i: t.me/c/123456789/999/10-15
            m_priv_topic_range = re.search(r't\.me/c/(\d+)/\d+/(\d+)-(\d+)', clean_link)
            if m_priv_topic_range:
                ch_id = int("-100" + m_priv_topic_range.group(1))
                start_id = int(m_priv_topic_range.group(2))
                end_id = int(m_priv_topic_range.group(3))
                msg_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
                return {"type": "telegram", "peer": ch_id, "msg_ids": msg_ids, "is_private": True, "raw": link}

            # 1.2 Yopiq kanal topic bitta xabar: t.me/c/123456789/999/10
            m_priv_topic = re.search(r't\.me/c/(\d+)/\d+/(\d+)', clean_link)
            if m_priv_topic:
                ch_id = int("-100" + m_priv_topic.group(1))
                return {"type": "telegram", "peer": ch_id, "msg_ids": [int(m_priv_topic.group(2))], "is_private": True, "raw": link}

            # 1.3 Yopiq kanal oralig'i: t.me/c/123456789/10-15
            m_priv_range = re.search(r't\.me/c/(\d+)/(\d+)-(\d+)', clean_link)
            if m_priv_range:
                ch_id = int("-100" + m_priv_range.group(1))
                start_id = int(m_priv_range.group(2))
                end_id = int(m_priv_range.group(3))
                msg_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
                return {"type": "telegram", "peer": ch_id, "msg_ids": msg_ids, "is_private": True, "raw": link}

            # 1.4 Yopiq kanal bitta xabar: t.me/c/123456789/10
            m_priv = re.search(r't\.me/c/(\d+)/(\d+)', clean_link)
            if m_priv:
                ch_id = int("-100" + m_priv.group(1))
                return {"type": "telegram", "peer": ch_id, "msg_ids": [int(m_priv.group(2))], "is_private": True, "raw": link}

            # 1.5 Ommaviy kanal topic oralig'i: t.me/channel/999/10-15
            m_pub_topic_range = re.search(r't\.me/([a-zA-Z0-9_]+)/\d+/(\d+)-(\d+)', clean_link)
            if m_pub_topic_range:
                username = m_pub_topic_range.group(1)
                start_id = int(m_pub_topic_range.group(2))
                end_id = int(m_pub_topic_range.group(3))
                msg_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
                return {"type": "telegram", "peer": username, "msg_ids": msg_ids, "is_private": False, "raw": link}

            # 1.6 Ommaviy kanal topic bitta xabar: t.me/channel/999/10
            m_pub_topic = re.search(r't\.me/([a-zA-Z0-9_]+)/\d+/(\d+)', clean_link)
            if m_pub_topic:
                username = m_pub_topic.group(1)
                return {"type": "telegram", "peer": username, "msg_ids": [int(m_pub_topic.group(2))], "is_private": False, "raw": link}

            # 1.7 Ommaviy kanal oralig'i: t.me/channel/10-15
            m_pub_range = re.search(r't\.me/([a-zA-Z0-9_]+)/(\d+)-(\d+)', clean_link)
            if m_pub_range:
                username = m_pub_range.group(1)
                start_id = int(m_pub_range.group(2))
                end_id = int(m_pub_range.group(3))
                msg_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
                return {"type": "telegram", "peer": username, "msg_ids": msg_ids, "is_private": False, "raw": link}

            # 1.8 Ommaviy kanal bitta xabar: t.me/channel/10
            m_pub = re.search(r't\.me/([a-zA-Z0-9_]+)/(\d+)', clean_link)
            if m_pub:
                username = m_pub.group(1)
                return {"type": "telegram", "peer": username, "msg_ids": [int(m_pub.group(2))], "is_private": False, "raw": link}

        # 2. TASHQI MEDIA PLATFORMALAR
        platform = "other"
        low_link = link.lower()
        if "youtube.com" in low_link or "youtu.be" in low_link:
            platform = "youtube"
        elif "instagram.com" in low_link:
            platform = "instagram"
        elif "tiktok.com" in low_link:
            platform = "tiktok"
        elif "pinterest.com" in low_link or "pin.it" in low_link:
            platform = "pinterest"
        elif "facebook.com" in low_link or "fb.watch" in low_link:
            platform = "facebook"
        elif "twitter.com" in low_link or "x.com" in low_link:
            platform = "twitter"

        return {
            "type": "external",
            "platform": platform,
            "url": link,
            "raw": link
        }

    @staticmethod
    def parse_telegram_link(link: str) -> tuple[int | str | None, list[int]]:
        """Eski kodlar bilan to'liq orqaga moslik (Backward compatibility)."""
        parsed = MediaDownloaderService.parse_link(link)
        if parsed.get("type") == "telegram":
            return parsed.get("peer"), parsed.get("msg_ids", [])
        return None, []

    @staticmethod
    def get_ffmpeg_path() -> str:
        """Tizimdagi yoki imageio_ffmpeg kutubxonasidagi ffmpeg fayl yo'lini topadi."""
        import shutil
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            return sys_ffmpeg
        if imageio_ffmpeg:
            try:
                exe = imageio_ffmpeg.get_ffmpeg_exe()
                if exe and Path(exe).exists():
                    return str(exe)
            except Exception:
                pass
        return "ffmpeg"

    @classmethod
    async def extract_high_quality_mp3(
        cls,
        video_path: Path | str,
        output_audio_path: Optional[Path | str] = None,
        title: Optional[str] = None,
        artist: Optional[str] = "Telegram Dev Bridge"
    ) -> Path:
        """
        Har qanday videodan 320kbps yuqori sifatli audio (MP3/M4A) ni 0.1-2 soniyada ajratib oladi.
        Direct stream copy va VBR/CBR MP3 texnologiyalari bilan ta'minlangan.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video fayl topilmadi: {video_path}")

        clean_stem = "".join(c for c in video_path.stem if c.isalnum() or c in (' ', '_', '-')).strip() or 'audio'
        if not output_audio_path:
            output_audio_path = AUDIO_DIR / f"{clean_stem}.mp3"
        else:
            output_audio_path = Path(output_audio_path)

        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_exe = cls.get_ffmpeg_path()

        logger.info(f"Audio ajratish boshlandi: {video_path.name}")

        # 1-USUL: ULTRA-TEZKOR DIRECT STREAM COPY (0.1 soniyada - 100% original sifat)
        # MP4 ichidagi AAC streamni to'g'ridan-to'g'ri .m4a qilib olish CPU sarflamaydi
        m4a_path = output_audio_path.with_suffix(".m4a")
        cmd_copy = [
            ffmpeg_exe,
            "-nostdin",
            "-y",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vn", "-sn", "-dn",
            "-c:a", "copy",
            "-map", "0:a:0?",
        ]
        if title:
            cmd_copy.extend(["-metadata", f"title={title}"])
        if artist:
            cmd_copy.extend(["-metadata", f"artist={artist}"])
        cmd_copy.append(str(m4a_path))

        try:
            proc_copy = await asyncio.create_subprocess_exec(
                *cmd_copy,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, _ = await asyncio.wait_for(proc_copy.communicate(), timeout=30)
            if proc_copy.returncode == 0 and m4a_path.exists() and m4a_path.stat().st_size > 1000:
                logger.info(f"Direct stream audio ajratildi (0.1s): {m4a_path.name} ({format_bytes(m4a_path.stat().st_size)})")
                return m4a_path
        except Exception as copy_err:
            logger.debug(f"Stream copy urinishi o'tmadi: {copy_err}")

        # 2-USUL: FAST MULTI-THREAD VBR MP3 (2-5 soniyada 320kbps ekvivalent)
        cmd_vbr = [
            ffmpeg_exe,
            "-nostdin",
            "-y",
            "-loglevel", "error",
            "-threads", "0",
            "-i", str(video_path),
            "-vn", "-sn", "-dn",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            "-map", "0:a:0?",
        ]
        if title:
            cmd_vbr.extend(["-metadata", f"title={title}"])
        if artist:
            cmd_vbr.extend(["-metadata", f"artist={artist}"])
        cmd_vbr.append(str(output_audio_path))

        try:
            proc_vbr = await asyncio.create_subprocess_exec(
                *cmd_vbr,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, _ = await asyncio.wait_for(proc_vbr.communicate(), timeout=600)
            if proc_vbr.returncode == 0 and output_audio_path.exists() and output_audio_path.stat().st_size > 1000:
                logger.info(f"VBR MP3 tayyorlandi: {output_audio_path.name} ({format_bytes(output_audio_path.stat().st_size)})")
                return output_audio_path
        except Exception as vbr_err:
            logger.debug(f"VBR MP3 urinishi: {vbr_err}")

        # 3-USUL: STANDART MP3 CODEC FALLBACK
        cmd_fallback = [
            ffmpeg_exe,
            "-nostdin",
            "-y",
            "-loglevel", "error",
            "-threads", "0",
            "-i", str(video_path),
            "-vn", "-sn", "-dn",
            "-b:a", "192k",
            "-map", "0:a:0?",
            str(output_audio_path)
        ]
        try:
            proc_fb = await asyncio.create_subprocess_exec(
                *cmd_fallback,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr_fb = await asyncio.wait_for(proc_fb.communicate(), timeout=600)
            if proc_fb.returncode == 0 and output_audio_path.exists() and output_audio_path.stat().st_size > 0:
                logger.info(f"MP3 tayyorlandi (Fallback): {output_audio_path.name}")
                return output_audio_path
        except Exception as fb_err:
            logger.warning(f"Fallback MP3 konvertatsiyada xatolik: {fb_err}")

        raise RuntimeError("Videodan audio ajratib bo'lmadi. Videoda audio yo'q yoki format qo'llab-quvvatlanmaydi.")

    @classmethod
    async def download_external_media(
        cls,
        url: str,
        audio_only: bool = False,
        save_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, float, float, float], None]] = None
    ) -> Dict[str, Any]:
        """
        YouTube, Instagram, TikTok, Pinterest, Facebook va boshqa tarmoqlardan video yoki
        yuqori sifatli MP3 ni yt-dlp orqali maksimal tezlikda yuklab oladi.
        """
        if yt_dlp is None:
            raise RuntimeError("yt-dlp moduli o'rnatilmagan. Iltimos: pip install yt-dlp")

        target_dir = save_dir or (AUDIO_DIR if audio_only else VIDEOS_DIR)
        target_dir.mkdir(parents=True, exist_ok=True)

        ffmpeg_location = cls.get_ffmpeg_path()
        last_progress_time = 0

        def _yt_progress_hook(d):
            nonlocal last_progress_time
            now = time.time()
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                speed = d.get('speed') or 0
                eta = d.get('eta') or 0
                percent = (downloaded / total) * 100 if total else 0
                filename = Path(d.get('filename', 'media')).name

                if progress_callback and (now - last_progress_time >= 1.0 or downloaded >= total):
                    last_progress_time = now
                    try:
                        progress_callback(downloaded, total, filename, percent, speed, eta)
                    except Exception:
                        pass

        out_template = str(target_dir / "%(title).80s_%(id)s.%(ext)s")

        ydl_opts: Dict[str, Any] = {
            'outtmpl': out_template,
            'progress_hooks': [_yt_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_location,
            'noplaylist': True,
        }

        if audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        def _run_ydl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info

        loop = asyncio.get_running_loop()
        info_dict = await loop.run_in_executor(None, _run_ydl)

        title = info_dict.get('title') or 'Media'
        duration = int(info_dict.get('duration') or 0)
        artist = info_dict.get('uploader') or info_dict.get('channel') or 'Online Media'
        thumb = info_dict.get('thumbnail')

        expected_ext = "mp3" if audio_only else "mp4"
        found_file = None

        if 'requested_downloads' in info_dict and info_dict['requested_downloads']:
            req = info_dict['requested_downloads'][0]
            if 'filepath' in req and Path(req['filepath']).exists():
                found_file = Path(req['filepath'])

        if not found_file:
            candidates = list(target_dir.glob(f"*.{expected_ext}"))
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                found_file = candidates[0]

        if not found_file or not found_file.exists():
            raise FileNotFoundError("Yuklangan fayl diskda topilmadi!")

        file_size = found_file.stat().st_size

        return {
            "path": str(found_file),
            "filename": found_file.name,
            "title": title,
            "duration": duration,
            "artist": artist,
            "thumbnail": thumb,
            "size_bytes": file_size,
            "size_formatted": format_bytes(file_size),
            "is_audio": audio_only,
        }

    @staticmethod
    async def download_videos_from_link(
        user_id: int,
        link: str,
        save_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, float, float, float], None]] = None
    ) -> list[dict]:
        """
        Telegram kanallardan (yopiq va ommaviy) videolarni parallel oqimlarda yuklab oladi.
        """
        parsed = MediaDownloaderService.parse_link(link)
        if parsed.get("type") != "telegram":
            raise ValueError("Berilgan havola Telegram havolasi emas!")

        ch_peer = parsed.get("peer")
        msg_ids = parsed.get("msg_ids", [])
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

        # Entity ni oldindan tekshirish va keshga olish
        try:
            entity = await client.get_entity(ch_peer)
        except Exception:
            entity = ch_peer

        for msg_id in msg_ids:
            try:
                msg = await client.get_messages(entity, ids=msg_id)
                if not msg or not msg.media:
                    continue

                loc, dc_id, file_size, extracted_name = FastTelethon.extract_file_info(msg)

                # Media turi va nomini aniqlash
                filename = extracted_name or f"video_{ch_peer}_{msg_id}.mp4"
                if hasattr(msg, "file") and msg.file and msg.file.name:
                    filename = msg.file.name
                elif hasattr(msg, "video") and msg.video:
                    filename = f"video_{ch_peer}_{msg_id}.mp4"

                out_path = target_dir / filename

                def _telethon_progress(current, total, speed, eta):
                    percent = (current / total) * 100 if total else 0
                    if progress_callback:
                        try:
                            progress_callback(current, total, filename, percent, speed, eta)
                        except Exception:
                            pass

                # Yuqori tezlikda parallel yuklab olish (avtomatik fallback bilan)
                actual_path = await FastTelethon.download_media(
                    client=client,
                    media_or_msg=msg,
                    out_path=out_path,
                    workers=8,
                    progress_callback=_telethon_progress
                )

                if actual_path and Path(actual_path).exists():
                    actual_size = Path(actual_path).stat().st_size
                    downloaded_files.append({
                        "msg_id": msg_id,
                        "msg": msg,
                        "path": str(actual_path),
                        "filename": Path(actual_path).name,
                        "size_bytes": actual_size,
                        "size_formatted": format_bytes(actual_size),
                    })

            except Exception as e:
                logger.error(f"Xabar #{msg_id} ni yuklab olishda xatolik: {e}")

        # RAM xotirani zudlik bilan tozalash
        import gc
        gc.collect()

        return downloaded_files

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
