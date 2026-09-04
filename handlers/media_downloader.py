import os
import uuid
import asyncio
import time
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.media_downloader_service import (
    MediaDownloaderService,
    VIDEOS_DIR,
    DOWNLOADS_DIR,
    AUDIO_DIR
)
from services.account_cleaner_service import AccountCleanerService
from services.fast_telethon import FastTelethon
from keyboards.inline import (
    cleaner_login_methods_keyboard,
    media_format_choice_keyboard,
    media_action_keyboard
)
from utils.helpers import escape_html, format_bytes, format_speed, format_eta
from utils.logger import logger

router = Router()

# Media xotirasi (token -> dict)
_MEDIA_CACHE: dict[str, dict] = {}
_MAX_MEDIA_CACHE = 300


def _save_media_token(data: dict) -> str:
    """Vaqtincha media tokenni saqlaydi (Callback_data 64-bayt chegarasi uchun)."""
    global _MEDIA_CACHE
    if len(_MEDIA_CACHE) > _MAX_MEDIA_CACHE:
        _MEDIA_CACHE.clear()
    token = uuid.uuid4().hex[:10]
    _MEDIA_CACHE[token] = data
    return token


class DownloaderStates(StatesGroup):
    waiting_for_media_link = State()
    waiting_for_mp3_link = State()


# =====================================================================
# 1. Buyruqlar: /dl, /mp3 va menyu tugmalari
# =====================================================================

@router.message(Command("dl"), StateFilter("*"))
@router.message(Command("download_media"), StateFilter("*"))
@router.message(F.text == "📥 Video Yuklash", StateFilter("*"))
@router.message(F.text == "📥 Video & MP3 Yuklash (Universal)", StateFilter("*"))
async def cmd_download_media(message: Message, state: FSMContext, bot: Bot):
    """Universal video va MP3 yuklash (Telegram, YouTube, Instagram, TikTok, Pinterest va hk.)."""
    await state.clear()
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and ("t.me/" in args[1] or "http://" in args[1] or "https://" in args[1]):
        await _process_media_download(message, args[1].strip(), bot, force_mp3=False)
        return

    await state.set_state(DownloaderStates.waiting_for_media_link)
    await message.answer(
        "📥 <b>Universal Video & MP3 Tezkor Yuklovchi ⚡</b>\n\n"
        "Istalgan video yoki musiqa havolasini (link) yuboring:\n\n"
        "<b>Qo'llab-quvvatlanadi:</b>\n"
        "• 📱 <b>Telegram:</b> Yopiq/ochiq kanallar, darsliklar (<code>https://t.me/c/...</code>)\n"
        "• ▶️ <b>YouTube:</b> Videolar, Shorts va Musiqalar\n"
        "• 📸 <b>Instagram:</b> Reels, Post va Videolar\n"
        "• 🎵 <b>TikTok:</b> Suv belgisiz (No Watermark) videolar\n"
        "• 📌 <b>Pinterest:</b> Barcha video va animatsiyalar\n"
        "• 🌐 <b>Boshqa:</b> Facebook, Twitter/X va to'g'ridan-to'g'ri MP4 linklar\n\n"
        "<i>⚡ Video bilan birga avtomatik 320kbps MP3 audio ham yuboriladi! (Bekor qilish: /cancel)</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(Command("mp3"), StateFilter("*"))
@router.message(Command("audio"), StateFilter("*"))
@router.message(F.text == "🎵 MP3 Yuklash", StateFilter("*"))
async def cmd_download_mp3(message: Message, state: FSMContext, bot: Bot):
    """To'g'ridan-to'g'ri faqat MP3 audio yuklash bo'limi."""
    await state.clear()
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and ("t.me/" in args[1] or "http://" in args[1] or "https://" in args[1]):
        await _process_media_download(message, args[1].strip(), bot, force_mp3=True)
        return

    await state.set_state(DownloaderStates.waiting_for_mp3_link)
    await message.answer(
        "🎵 <b>Tezkor MP3 Audio Yuklovchi (320kbps Stereo) ⚡</b>\n\n"
        "Istalgan video yoki musiqa havolasini yuboring. Bot videoni yuklab o'tirmasdan, "
        "to'g'ridan-to'g'ri yuqori sifatli 320kbps MP3 musiqasini yetkazib beradi:\n\n"
        "• 📱 <b>Telegram:</b> Ochiq va yopiq kanallardagi videolar / audolar\n"
        "• ▶️ <b>YouTube:</b> Video, Shorts va Musiqalar\n"
        "• 📸 <b>Instagram:</b> Reels va Videolar\n"
        "• 🎵 <b>TikTok:</b> Audio treklar va musiqalar\n"
        "• 📌 <b>Pinterest, Facebook va boshqalar</b>\n\n"
        "<i>Havolani yuboring (Bekor qilish: /cancel):</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(DownloaderStates.waiting_for_media_link)
async def handle_media_link_input(message: Message, state: FSMContext, bot: Bot):
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Video yuklash bekor qilindi.")
        return

    link = message.text.strip()
    if not link.startswith("http://") and not link.startswith("https://") and "t.me/" not in link:
        await message.answer("❌ <b>Noto'g'ri havola!</b>\nIltimos, video havolasini (link) yuboring:", parse_mode="HTML")
        return

    await state.clear()
    await _process_media_download(message, link, bot, force_mp3=False)


@router.message(DownloaderStates.waiting_for_mp3_link)
async def handle_mp3_link_input(message: Message, state: FSMContext, bot: Bot):
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ MP3 yuklash bekor qilindi.")
        return

    link = message.text.strip()
    if not link.startswith("http://") and not link.startswith("https://") and "t.me/" not in link:
        await message.answer("❌ <b>Noto'g'ri havola!</b>\nIltimos, havola yuboring:", parse_mode="HTML")
        return

    await state.clear()
    await _process_media_download(message, link, bot, force_mp3=True)


# =====================================================================
# 2. To'g'ridan-to'g'ri havolalar va Video xabarlarni tutish
# =====================================================================

@router.message(F.text.regexp(r'https?://[^\s]+'), StateFilter(None))
async def handle_direct_link_message(message: Message, state: FSMContext, bot: Bot):
    """Foydalanuvchi chatga shunchaki havola tashlaganida ham avtomatik yuklash."""
    link = message.text.strip()
    await _process_media_download(message, link, bot, force_mp3=False)


@router.message(F.video | F.video_note | F.audio | (F.document & F.document.mime_type.contains("video")), StateFilter(None))
async def handle_user_uploaded_media(message: Message, bot: Bot):
    """Foydalanuvchi botga to'g'ridan-to'g'ri video/audio yuborganida darhol 320kbps MP3 ga aylantirish."""
    media_obj = message.video or message.video_note or message.audio or message.document
    file_id = media_obj.file_id
    file_name = getattr(media_obj, 'file_name', None) or f"video_{message.message_id}.mp4"
    file_size_mb = getattr(media_obj, 'file_size', 0) / (1024 * 1024)

    # Agar fayl 45MB dan kichik bo'lsa darhol MP3 qilish
    if file_size_mb <= 45:
        status_msg = await message.reply("⏳ <b>Video qabul qilindi, 🎵 320kbps MP3 ga aylantirilmoqda...</b>", parse_mode="HTML")
        try:
            temp_dir = VIDEOS_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            bot_file = await bot.get_file(file_id)
            local_path = temp_dir / f"bot_{file_name}"
            await bot.download_file(bot_file.file_path, local_path)

            mp3_path = await MediaDownloaderService.extract_high_quality_mp3(local_path, title=file_name)
            token = _save_media_token({
                "type": "local_file",
                "path": str(mp3_path),
                "title": file_name
            })

            audio_input = FSInputFile(str(mp3_path), filename=mp3_path.name)
            await message.reply_audio(
                audio_input,
                title=file_name,
                performer="Telegram Dev Bridge",
                caption=f"🎵 <b>{escape_html(file_name)}</b>\n⚡ <i>320kbps Yuqori Sifatli Stereo MP3</i>",
                reply_markup=media_action_keyboard(token),
                parse_mode="HTML"
            )
            await status_msg.delete()
            return
        except Exception as e:
            logger.error(f"Faylni MP3 qilishda xato: {e}")
            try:
                await status_msg.delete()
            except Exception:
                pass

    token = _save_media_token({
        "type": "telegram_bot_file",
        "file_id": file_id,
        "title": file_name,
        "size_mb": file_size_mb
    })

    caption = (
        f"🎬 <b>Qabul qilindi:</b> <code>{escape_html(file_name)}</code> ({file_size_mb:.1f} MB)\n\n"
        f"<i>Quyidagi tugma orqali 320kbps MP3 ajratib olishingiz mumkin:</i>"
    )

    await message.reply(caption, reply_markup=media_action_keyboard(token), parse_mode="HTML")


# =====================================================================
# 3. Asosiy Video & MP3 Yuklash Mantiqi
# =====================================================================

async def _process_media_download(message: Message, link: str, bot: Bot, force_mp3: bool = False):
    """Universal video va MP3 yuklash protsessi (To'g'ridan-to'g'ri bot chatga yetkazadi)."""
    user_id = message.from_user.id
    status_msg = await message.answer("⚡ <b>Havola tekshirilmoqda...</b>", parse_mode="HTML")

    parsed = MediaDownloaderService.parse_link(link)

    # -------------------------------------------------------------
    # VARIANT A: TASHQI HAVOLA (YouTube, Instagram, TikTok, Pinterest va hk.)
    # -------------------------------------------------------------
    if parsed.get("type") == "external":
        platform = parsed.get("platform", "online")
        platform_names = {
            "youtube": "YouTube ▶️",
            "instagram": "Instagram 📸",
            "tiktok": "TikTok 🎵",
            "pinterest": "Pinterest 📌",
            "facebook": "Facebook 👥",
            "twitter": "Twitter / X 🐦",
            "other": "Web Video 🌐"
        }
        p_name = platform_names.get(platform, "Online")

        await status_msg.edit_text(f"🚀 <b>{p_name} orqali yuklanmoqda...</b>", parse_mode="HTML")

        last_edit_time = 0
        def _ext_progress(current, total, filename, percent, speed, eta):
            nonlocal last_edit_time
            now = time.time()
            if now - last_edit_time >= 2.0 or (total and current >= total):
                last_edit_time = now
                bar_len = 10
                filled = int(percent / 10) if percent <= 100 else 10
                bar = "█" * filled + "░" * (bar_len - filled)
                cur_str = format_bytes(current)
                tot_str = format_bytes(total) if total else "—"
                speed_str = format_speed(speed) if speed else "—"
                eta_str = format_eta(eta) if eta else "—"
                text = (
                    f"⚡ <b>{p_name} yuklanmoqda...</b>\n\n"
                    f"🎬 <b>Nomi:</b> <code>{escape_html(filename[:40])}</code>\n"
                    f"[{bar}] <b>{percent:.1f}%</b>\n"
                    f"📊 <b>Hajm:</b> {cur_str} / {tot_str}\n"
                    f"🚀 <b>Tezlik:</b> {speed_str} | ⏱ <b>Qolgan:</b> {eta_str}"
                )
                asyncio.create_task(status_msg.edit_text(text, parse_mode="HTML"))

        try:
            res_data = await MediaDownloaderService.download_external_media(
                url=link,
                audio_only=force_mp3,
                progress_callback=_ext_progress
            )

            file_path = Path(res_data["path"])
            title = res_data.get("title", "media")
            artist = res_data.get("artist", p_name)
            duration = res_data.get("duration", 0)

            token = _save_media_token({
                "type": "local_file",
                "path": str(file_path),
                "title": title
            })

            # Agar faqat MP3 so'ralgan bo'lsa
            if force_mp3 or res_data.get("is_audio"):
                await status_msg.edit_text("🎵 <b>Audio bot chatga yetkazilmoqda...</b>", parse_mode="HTML")
                audio_input = FSInputFile(str(file_path), filename=file_path.name)
                await message.answer_audio(
                    audio_input,
                    title=title,
                    performer=artist,
                    duration=duration,
                    caption=f"🎵 <b>{escape_html(title)}</b>\n⚡ <i>320kbps Yuqori Sifatli Audio</i>",
                    reply_markup=media_action_keyboard(token),
                    parse_mode="HTML"
                )
                await status_msg.delete()
                return

            # Video va 320kbps MP3 ni BIRGALIKDA botga yuborish
            await status_msg.edit_text("🎬 <b>Video va 🎵 320kbps MP3 tayyorlanmoqda...</b>", parse_mode="HTML")
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            caption = (
                f"🎬 <b>{escape_html(title)}</b>\n"
                f"📊 <b>Hajmi:</b> {res_data['size_formatted']} | ⏱ <b>Davomiyligi:</b> {duration // 60}:{duration % 60:02d}\n"
                f"🌐 <b>Manba:</b> {p_name}"
            )

            # 1. Videoni to'g'ridan-to'g'ri bot chatga yuborish
            send_video_path = file_path
            if file_size_mb > 49.5:
                await status_msg.edit_text("⚡ <b>Video bot chatga jo'natish uchun tayyorlanmoqda (Optimal sifat)...</b>", parse_mode="HTML")
                send_video_path = await MediaDownloaderService.compress_video_to_size(file_path, target_mb=48.0)

            video_input = FSInputFile(str(send_video_path), filename=send_video_path.name)
            try:
                await message.answer_video(
                    video_input,
                    caption=caption,
                    duration=duration,
                    reply_markup=media_action_keyboard(token),
                    parse_mode="HTML",
                    supports_streaming=True
                )
            except Exception as vid_err:
                logger.warning(f"Video jo'natishda xatolik, hujjat sifatida yuborilmoqda: {vid_err}")
                doc_input = FSInputFile(str(send_video_path), filename=send_video_path.name)
                await message.answer_document(
                    doc_input,
                    caption=caption,
                    reply_markup=media_action_keyboard(token),
                    parse_mode="HTML"
                )

            # 2. Qo'shimcha 320kbps MP3 Musiqasini DARHOL bot chatga yuborish
            try:
                mp3_path = await MediaDownloaderService.extract_high_quality_mp3(
                    file_path,
                    title=title,
                    artist=artist
                )
                if mp3_path and mp3_path.exists():
                    mp3_input = FSInputFile(str(mp3_path), filename=mp3_path.name)
                    mp3_token = _save_media_token({
                        "type": "local_file",
                        "path": str(mp3_path),
                        "title": title
                    })
                    await message.answer_audio(
                        mp3_input,
                        title=title,
                        performer=artist,
                        duration=duration,
                        caption=f"🎵 <b>{escape_html(title)}</b>\n⚡ <i>320kbps Yuqori Sifatli MP3</i>",
                        reply_markup=media_action_keyboard(mp3_token),
                        parse_mode="HTML"
                    )
            except Exception as mp3_err:
                logger.warning(f"Avtomatik MP3 ajratishda xatolik: {mp3_err}")

            await status_msg.delete()
            return

        except Exception as ext_err:
            logger.error(f"Tashqi video yuklashda xatolik ({link}): {ext_err}")
            await status_msg.edit_text(f"❌ <b>Yuklab olishda xatolik:</b> {escape_html(str(ext_err))}", parse_mode="HTML")
            return

    # -------------------------------------------------------------
    # VARIANT B: TELEGRAM HAVOLASI (Yopiq / Ochiq Kanallar)
    # -------------------------------------------------------------
    is_auth = await AccountCleanerService.is_authorized(user_id)
    if not is_auth:
        await status_msg.edit_text(
            "🔑 <b>Yopiq kanallardan video olish uchun Telegram hisobingizga kiring!</b>\n\n"
            "Darsliklar va yopiq kanallarni yuklash uchun /cleaner buyrug'i orqali hisobingizni ulang "
            "(📷 <i>QR Kod orqali 1 soniyada ulanish mumkin</i>).",
            parse_mode="HTML",
            reply_markup=cleaner_login_methods_keyboard()
        )
        return

    client = await AccountCleanerService.get_client(user_id)

    # 8-STREAM PARALLEL TURBO YUKLASH
    last_edit_time = 0

    def _on_progress(current, total, filename, percent, speed, eta):
        nonlocal last_edit_time
        now = time.time()
        if now - last_edit_time >= 2.0 or current == total:
            last_edit_time = now
            bar_len = 10
            filled = int(percent / 10) if percent <= 100 else 10
            bar = "█" * filled + "░" * (bar_len - filled)
            cur_str = format_bytes(current)
            tot_str = format_bytes(total) if total else "—"
            speed_str = format_speed(speed) if speed else "—"
            eta_str = format_eta(eta) if eta else "—"
            text = (
                f"⚡ <b>Telegram video yuklanmoqda (Turbo Tezlik 🚀)...</b>\n\n"
                f"🎬 <b>Fayl:</b> <code>{escape_html(filename)}</code>\n"
                f"[{bar}] <b>{percent:.1f}%</b>\n"
                f"📊 <b>Hajm:</b> {cur_str} / {tot_str}\n"
                f"🚀 <b>Tezlik:</b> {speed_str} | ⏱ <b>Qolgan:</b> {eta_str}"
            )
            asyncio.create_task(status_msg.edit_text(text, parse_mode="HTML"))

    try:
        results = await MediaDownloaderService.download_videos_from_link(
            user_id=user_id,
            link=link,
            save_dir=VIDEOS_DIR,
            progress_callback=_on_progress
        )

        if not results:
            await status_msg.edit_text(
                "❌ <b>Ko'rsatilgan havolada video yoki media topilmadi!</b>\n"
                "Iltimos, havola to'g'riligini va hisobingiz ushbu kanalda a'zo ekanligini tekshiring.",
                parse_mode="HTML"
            )
            return

        await status_msg.edit_text(f"✅ <b>{len(results)} ta media yuklab olindi!</b>\nTo'g'ridan-to'g'ri bot chatga yuborilmoqda...", parse_mode="HTML")

        for item in results:
            file_path = Path(item["path"])
            file_size_mb = item["size_bytes"] / (1024 * 1024)

            # Agar faqat MP3 so'ralgan bo'lsa, zudlik bilan 320kbps MP3 ga aylantirish
            if force_mp3:
                mp3_path = await MediaDownloaderService.extract_high_quality_mp3(file_path, title=item["filename"])
                mp3_file = FSInputFile(str(mp3_path), filename=mp3_path.name)
                token = _save_media_token({
                    "type": "local_file",
                    "path": str(mp3_path),
                    "title": item["filename"]
                })
                await message.answer_audio(
                    mp3_file,
                    title=item["filename"],
                    caption=f"🎵 <b>{escape_html(item['filename'])}</b>\n⚡ <i>320kbps Yuqori Sifatli Audio</i>",
                    reply_markup=media_action_keyboard(token),
                    parse_mode="HTML"
                )
                continue

            caption = (
                f"🎬 <b>{escape_html(item['filename'])}</b>\n"
                f"📊 <b>Hajmi:</b> {item['size_formatted']}\n"
                f"⚡ <i>Tezkor yuklandi</i>"
            )

            token = _save_media_token({
                "type": "local_file",
                "path": str(file_path),
                "title": item["filename"]
            })

            # 1. Videoni to'g'ridan-to'g'ri bot chatga jo'natish
            send_video_path = file_path
            if file_size_mb > 49.5:
                await status_msg.edit_text("⚡ <b>Video bot chatga jo'natish uchun tayyorlanmoqda (Optimal sifat)...</b>", parse_mode="HTML")
                send_video_path = await MediaDownloaderService.compress_video_to_size(file_path, target_mb=48.0)

            cur_mb = send_video_path.stat().st_size / (1024 * 1024)
            if cur_mb <= 49.5:
                try:
                    video_file = FSInputFile(str(send_video_path), filename=item["filename"])
                    await message.answer_video(
                        video_file,
                        caption=caption,
                        reply_markup=media_action_keyboard(token),
                        parse_mode="HTML",
                        supports_streaming=True
                    )
                except Exception as vid_err:
                    logger.warning(f"Telegram video yuborishda xatolik: {vid_err}")
                    doc_file = FSInputFile(str(send_video_path), filename=item["filename"])
                    await message.answer_document(
                        doc_file,
                        caption=caption,
                        reply_markup=media_action_keyboard(token),
                        parse_mode="HTML"
                    )
            else:
                doc_file = FSInputFile(str(send_video_path), filename=item["filename"])
                try:
                    await message.answer_document(
                        doc_file,
                        caption=caption,
                        reply_markup=media_action_keyboard(token),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            # 2. Videodan keyin avtomatik 320kbps MP3 audioni ham bot chatga yuborish
            try:
                mp3_path = await MediaDownloaderService.extract_high_quality_mp3(file_path, title=item["filename"])
                if mp3_path and mp3_path.exists():
                    mp3_file = FSInputFile(str(mp3_path), filename=mp3_path.name)
                    mp3_tok = _save_media_token({
                        "type": "local_file",
                        "path": str(mp3_path),
                        "title": item["filename"]
                    })
                    await message.answer_audio(
                        mp3_file,
                        title=item["filename"],
                        caption=f"🎵 <b>{escape_html(item['filename'])}</b>\n⚡ <i>320kbps Yuqori Sifatli Audio</i>",
                        reply_markup=media_action_keyboard(mp3_tok),
                        parse_mode="HTML"
                    )
            except Exception as mp3_err:
                logger.warning(f"Telegram videodan MP3 ajratishda xatolik: {mp3_err}")

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Video yuklashda xatolik: {e}")
        err_str = str(e)
        await status_msg.edit_text(f"❌ <b>Yuklab olishda xatolik:</b> {escape_html(err_str)}", parse_mode="HTML")


# =====================================================================
# 4. MP3 Konvertatsiya va Callback Handlerlar
# =====================================================================

@router.callback_query(F.data.startswith("conv_mp3:"))
async def cb_convert_to_mp3(callback: CallbackQuery, bot: Bot):
    """Mavjud videodan 320kbps MP3 audio ajratib yuborish."""
    await callback.answer("🎵 320kbps MP3 ajratilmoqda...")
    token = callback.data.split(":", 1)[1]
    cached = _MEDIA_CACHE.get(token)

    if not cached:
        await callback.message.answer("⚠️ Media ma'lumotlari keshdan eskirgan. Iltimos, linkni qayta yuboring.")
        return

    status_msg = await callback.message.answer("🎵 <b>Yuqori sifatli (320kbps) MP3 tayyorlanmoqda...</b>", parse_mode="HTML")
    user_id = callback.from_user.id

    try:
        file_path = None
        title = cached.get("title", "audio")

        # 1. Agar mahalliy fayl bo'lsa
        if cached["type"] == "local_file":
            file_path = Path(cached["path"])
        elif cached["type"] == "telegram_msg":
            client = await AccountCleanerService.get_client(user_id)
            temp_dir = VIDEOS_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            local_path = temp_dir / f"vid_{title}"
            actual = await FastTelethon.download_media(client, cached["msg"], local_path)
            file_path = Path(actual)
        elif cached["type"] == "telegram_bot_file":
            temp_dir = VIDEOS_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            bot_file = await bot.get_file(cached["file_id"])
            local_path = temp_dir / f"bot_{title}"
            await bot.download_file(bot_file.file_path, local_path)
            file_path = local_path

        if not file_path or not file_path.exists():
            await status_msg.edit_text("❌ Video fayl topilmadi!")
            return

        # 320kbps MP3 ajratish (1-2 soniyada)
        mp3_path = await MediaDownloaderService.extract_high_quality_mp3(file_path, title=title)

        mp3_token = _save_media_token({
            "type": "local_file",
            "path": str(mp3_path),
            "title": title
        })

        audio_input = FSInputFile(str(mp3_path), filename=mp3_path.name)
        await callback.message.answer_audio(
            audio_input,
            title=title,
            performer="Telegram Dev Bridge",
            caption=f"🎵 <b>{escape_html(title)}</b>\n⚡ <i>320kbps Yuqori Sifatli Stereo MP3</i>",
            reply_markup=media_action_keyboard(mp3_token),
            parse_mode="HTML"
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"MP3 ajratishda xatolik: {e}")
        await status_msg.edit_text(f"❌ <b>MP3 ga aylantirishda xatolik:</b> {escape_html(str(e))}", parse_mode="HTML")
