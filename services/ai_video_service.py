import os
import time
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Callable
import config
from utils.logger import logger

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


AI_TEMP_DIR = config.BASE_DIR / "videolar" / "ai_cache"
AI_TEMP_DIR.mkdir(parents=True, exist_ok=True)


class AIVideoService:
    """
    Video va audiolarni Google Gemini 3.6 Flash yordamida chuqur tahlil qilish:
    - Interview savollarini taym-kodlar bilan ajratish
    - Eng muhim joylarini mukammal konspekt qilish
    - Xulosa va tavsiyalar berish
    """

    @staticmethod
    def is_available() -> bool:
        """Gemini API kaliti sozlanganligini tekshiradi."""
        return bool(config.GEMINI_API_KEY and genai is not None)

    @staticmethod
    def extract_audio(video_path: Path, output_audio_path: Optional[Path] = None) -> Path:
        """
        Videodan 32kbps mono audio trekni 2-3 soniyada ajratib oladi (1 GB video -> ~10-15 MB audio).
        Agar ffmpeg topilmasa, videoning o'zini qaytaradi.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video fayl topilmadi: {video_path}")

        if not output_audio_path:
            output_audio_path = AI_TEMP_DIR / f"{video_path.stem}_audio.mp3"

        ffmpeg_exe = None
        if imageio_ffmpeg:
            try:
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception as e:
                logger.warning(f"imageio_ffmpeg topilmadi: {e}")

        if not ffmpeg_exe:
            # Tizim ffmpeg ini tekshirish
            ffmpeg_exe = "ffmpeg"

        try:
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", str(video_path),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-b:a", "32k",
                str(output_audio_path)
            ]
            logger.info(f"Audioni ajratib olish boshlandi: {video_path.name}")
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if res.returncode == 0 and output_audio_path.exists() and output_audio_path.stat().st_size > 0:
                logger.info(f"Audio muvaffaqiyatli ajratildi ({output_audio_path.stat().st_size / 1024 / 1024:.1f} MB)")
                return output_audio_path
        except Exception as err:
            logger.warning(f"Audioni ajratishda xatolik ({err}), videoning o'zi yuboriladi.")

        return video_path

    @classmethod
    async def analyze_video(
        cls,
        media_path: Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Video yoki audio faylni Gemini 3.6 Flash orqali to'liq tahlil qilib,
        interview savollari va konspektini o'zbek tilida qaytaradi.
        """
        if not cls.is_available():
            raise RuntimeError(
                "GEMINI_API_KEY sozlanmagan yoki google-genai kutubxonasi mavjud emas! "
                "Iltimos, .env fayliga GEMINI_API_KEY ni kiriting."
            )

        media_path = Path(media_path)
        if not media_path.exists():
            raise FileNotFoundError(f"Fayl topilmadi: {media_path}")

        if progress_callback:
            progress_callback("🎧 Videodan audio trek ajratib olinmoqda (Tezkor siqish)...")

        # 1. Tezkor audio ajratish
        audio_file = await asyncio.to_thread(cls.extract_audio, media_path)

        if progress_callback:
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            progress_callback(f"☁️ Google Gemini bulutiga yuklanmoqda ({file_size_mb:.1f} MB)...")

        client = genai.Client(api_key=config.GEMINI_API_KEY)

        # 2. Faylni Gemini File API ga yuklash
        uploaded_file = await asyncio.to_thread(client.files.upload, file=str(audio_file))

        try:
            # Agar video yoki katta audio bo'lsa, Gemini serverida faol (ACTIVE) holatga kelishini kutish
            if progress_callback:
                progress_callback("🤖 Gemini 3.6 Flash AI videoni tahlil qilmoqda (Interview savollari va konspekt)...")

            for _ in range(60):
                file_status = await asyncio.to_thread(client.files.get, name=uploaded_file.name)
                state_name = getattr(file_status, "state", None)
                if state_name is None or str(state_name).upper() == "ACTIVE":
                    break
                elif str(state_name).upper() == "FAILED":
                    raise RuntimeError("Gemini serverida faylni qayta ishlashda xatolik yuz berdi.")
                await asyncio.sleep(2)

            prompt = (
                "Sen professional IT, dasturlash va texnik suhbatlar bo'yicha yetakchi ekspert hamda konspektorsan.\n"
                "Ushbu taqdim etilgan video/audio yozuvni boshidan oxirigacha sinchkovlik bilan eshitib, "
                "quyidagi 3 ta asosiy bo'limdan iborat MUKAMMAL va O'TA ANIQ konspekt tayyorlab ber:\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📋 1. INTERVIEW SAVOLLARI VA JAVOBLARI (TAYM-KODLAR BILAN):\n"
                "- Suhbatda berilgan yoki muhokama qilingan BARCHA texnik va amaliy interview savollarini aniq ajrat.\n"
                "- Har bir savol yoniga audio/video vaqtini (masalan: ⏱ [03:45], [12:10]) yoz.\n"
                "- Savolga videoda berilgan javobni to'liq, ravshan va mukammal texnik izohi bilan yoz.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📝 2. ENG MUHIM JOYLARI KONSPEKTI (ASOSIY MOHIYAT):\n"
                "- Videoning asosiy mavzusi va maqsadi.\n"
                "- Eng muhim tushunchalar, qoidalar, tavsiyalar va printsiplar (aniq va lo'nda punktlar bilan).\n"
                "- Dasturchilar ko'p yo'l qo'yadigan xatolar va ularni oldini olish yo'llari.\n"
                "- Muhim terminlar va texnologiyalar tahlili.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 3. XULOSA VA AMALIY MASLAHATLAR:\n"
                "- Ushbu videodan o'rganuvchi o'zi uchun olishi kerak bo'lgan eng muhim 3-5 ta amaliy xulosa.\n\n"
                "Talab: Javobni o'zbek tilida, nihoyatda chiroyli, tushunarli va professional markdown formatida yoz. "
                "Hech qanday muhim texnik detalni o'tkazib yuborma!"
            )

            # 3. Modelga tahlil so'rovini yuborish
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-3.6-flash",
                contents=[uploaded_file, prompt]
            )

            result_text = response.text if response and response.text else "Tahlil natijasi olinmadi."
            return result_text

        finally:
            # 4. Vaqtinchalik fayllarni tozalash
            try:
                await asyncio.to_thread(client.files.delete, name=uploaded_file.name)
            except Exception:
                pass
            if audio_file != media_path and audio_file.exists():
                try:
                    audio_file.unlink()
                except Exception:
                    pass
