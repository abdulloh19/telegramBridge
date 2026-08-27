import os
import uuid
import asyncio
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.media_downloader_service import MediaDownloaderService, VIDEOS_DIR, DOWNLOADS_DIR
from services.account_cleaner_service import AccountCleanerService
from services.ai_video_service import AIVideoService
from services.fast_telethon import FastTelethon
from keyboards.inline import cleaner_login_methods_keyboard
from utils.helpers import escape_html, format_bytes, format_speed, format_eta
from utils.logger import logger

router = Router()

# AI tahlili uchun video/audio xotirasi (token -> dict)
_AI_MEDIA_CACHE: dict[str, dict] = {}
_MAX_AI_CACHE = 200


def _save_ai_media_token(data: dict) -> str:
    """Vaqtincha media tokenni saqlaydi (Callback_data 64-bayt chegarasi uchun)."""
    global _AI_MEDIA_CACHE
    if len(_AI_MEDIA_CACHE) > _MAX_AI_CACHE:
        _AI_MEDIA_CACHE.clear()
    token = uuid.uuid4().hex[:10]
    _AI_MEDIA_CACHE[token] = data
    return token


class DownloaderStates(StatesGroup):
    waiting_for_media_link = State()
    waiting_for_ai_link = State()


# =====================================================================
# 1. Buyruqlar: /dl, /ai, /konspekt, /interview va menyu tugmalari
# =====================================================================

@router.message(Command("dl"), StateFilter("*"))
@router.message(Command("download_media"), StateFilter("*"))
@router.message(F.text == "📥 Video Yuklash", StateFilter("*"))
async def cmd_download_media(message: Message, state: FSMContext, bot: Bot):
    """Yopiq yoki ochiq Telegram kanallardan video yuklab olish."""
    await state.clear()
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and "t.me/" in args[1]:
        await _process_media_download(message, args[1].strip(), bot, auto_ai=False)
        return

    await state.set_state(DownloaderStates.waiting_for_media_link)
    await message.answer(
        "📥 <b>Telegram Private & Public Video Tezkor Yuklovchi ⚡</b>\n\n"
        "Yopiq (Private) yoki ochiq kanaldagi video xabar havolasini (link) yuboring:\n\n"
        "<b>Misollar:</b>\n"
        "• Bitta video: <code>https://t.me/c/1234567890/45</code>\n"
        "• Ketma-ket bir nechta video: <code>https://t.me/c/1234567890/45-50</code>\n"
        "• Ommaviy kanal: <code>https://t.me/kanal_nomi/123</code>\n\n"
        "<i>⚡ Multi-stream 8-oqimli tezkor yuklash yoqilgan! Bekor qilish: /cancel</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(Command("ai"), StateFilter("*"))
@router.message(Command("konspekt"), StateFilter("*"))
@router.message(Command("interview"), StateFilter("*"))
@router.message(F.text == "🧠 AI Video Konspekt", StateFilter("*"))
async def cmd_ai_video_konspekt(message: Message, state: FSMContext, bot: Bot):
    """Videoni yuklab, undan interview savollari va konspektini chiqarish."""
    await state.clear()
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and "t.me/" in args[1]:
        await _process_media_download(message, args[1].strip(), bot, auto_ai=True)
        return

    await state.set_state(DownloaderStates.waiting_for_ai_link)
    await message.answer(
        "🧠 <b>AI Video Konspekt & Interview Tahlilchisi (Gemini 3.6 Flash) ⚡</b>\n\n"
        "Video havolasini (link) yuboring. Bot videoni yuklab, quyidagilarni tayyorlab beradi:\n"
        "• 📋 <b>Barcha Interview Savollari & Javoblari</b> (aniq taym-kodlar bilan)\n"
        "• 📝 <b>Eng Muhim Joylari Konspekti</b> (asosiy tushunchalar, qoidalar va formulalar)\n"
        "• 💡 <b>Xulosa va Amaliy Maslahatlar</b>\n\n"
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
    if "t.me/" not in link:
        await message.answer("❌ <b>Noto'g'ri havola!</b>\nIltimos, <code>https://t.me/c/...</code> formatidagi link yuboring:", parse_mode="HTML")
        return

    await state.clear()
    await _process_media_download(message, link, bot, auto_ai=False)


@router.message(DownloaderStates.waiting_for_ai_link)
async def handle_ai_link_input(message: Message, state: FSMContext, bot: Bot):
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ AI tahlil bekor qilindi.")
        return

    link = message.text.strip()
    if "t.me/" not in link:
        await message.answer("❌ <b>Noto'g'ri havola!</b>\nIltimos, Telegram video linkini yuboring:", parse_mode="HTML")
        return

    await state.clear()
    await _process_media_download(message, link, bot, auto_ai=True)


@router.message(F.text.regexp(r'https?://t\.me/(c/\d+|[a-zA-Z0-9_]+)/\d+'), StateFilter(None))
async def handle_direct_telegram_link(message: Message, state: FSMContext, bot: Bot):
    """Foydalanuvchi shunchaki video link tashlaganida ham yuklash."""
    await _process_media_download(message, message.text.strip(), bot, auto_ai=False)


# =====================================================================
# 2. Asosiy Video Yuklash & AI Integratsiyasi
# =====================================================================

async def _process_media_download(message: Message, link: str, bot: Bot, auto_ai: bool = False):
    """Video yuklash, yuborish va AI konspekt opsiyasini taqdim etish."""
    user_id = message.from_user.id
    status_msg = await message.answer("⚡ <b>Video tekshirilmoqda...</b>", parse_mode="HTML")

    is_auth = await AccountCleanerService.is_authorized(user_id)
    if not is_auth:
        await status_msg.edit_text(
            "🔑 <b>Avval Telegram hisobingizga kirishingiz kerak!</b>\n\n"
            "Yopiq va ommaviy kanallardan video olish uchun /cleaner buyrug'i orqali akkauntingizni ulang.",
            parse_mode="HTML"
        )
        return

    client = await AccountCleanerService.get_client(user_id)
    ch_peer, msg_ids = MediaDownloaderService.parse_telegram_link(link)

    # 1-BOSQICH: INSTANT DIRECT CLOUD TRANSFER (0.1 soniyada srazi forward)
    try:
        all_sent_instantly = True
        instant_msgs = []
        for msg_id in msg_ids:
            msg = await client.get_messages(ch_peer, ids=msg_id)
            if not msg or not msg.media:
                all_sent_instantly = False
                break

            direct_sent = False
            try:
                await client.forward_messages(user_id, msg)
                try:
                    await client.forward_messages('me', msg)
                except Exception:
                    pass
                direct_sent = True
            except Exception:
                try:
                    fn = getattr(msg.file, 'name', None) or f"video_{ch_peer}_{msg_id}.mp4"
                    caption = f"🎬 <b>{escape_html(fn)}</b>\n⚡ <i>Tezkor uzatish (Instant Cloud)</i>"
                    await client.send_file(user_id, file=msg.media, caption=caption, parse_mode="html", supports_streaming=True)
                    try:
                        await client.send_file('me', file=msg.media, caption=caption, parse_mode="html", supports_streaming=True)
                    except Exception:
                        pass
                    direct_sent = True
                except Exception:
                    direct_sent = False

            if direct_sent:
                instant_msgs.append((msg, getattr(msg.file, 'name', None) or f"video_{msg_id}.mp4"))
            else:
                all_sent_instantly = False
                break

        if all_sent_instantly and instant_msgs:
            # Agar auto_ai yoqilgan bo'lsa, birinchi videoning konspektini tayyorlash
            if auto_ai:
                await status_msg.edit_text("⚡ Video yetkazildi! Endi AI konspekt va interview savollari tayyorlanmoqda...", parse_mode="HTML")
                raw_msg, raw_title = instant_msgs[0]
                await _download_and_analyze_msg(status_msg, client, raw_msg, raw_title, user_id)
            else:
                raw_msg, raw_title = instant_msgs[0]
                token = _save_ai_media_token({
                    "type": "telegram_msg",
                    "msg": raw_msg,
                    "title": raw_title
                })
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🧠 AI Interview Savollari & Konspekt", callback_data=f"ai_anlz:{token}")
                ]])
                await status_msg.edit_text(
                    "⚡ <b>Video srazi (bir zumda) yetkazildi!</b>\n\n"
                    "💡 <i>Ushbu videodagi interview savollari va konspektni olishni xohlaysizmi?</i>",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            return
    except Exception as direct_err:
        logger.info(f"Direct cloud transfer mumkin bo'lmadi (Protected channel): {direct_err}")

    # 2-BOSQICH: PROTECTED KANAL UCHUN 8-STREAM PARALLEL TURBO YUKLASH
    last_edit_time = 0

    def _on_progress(current, total, filename, percent, speed, eta):
        nonlocal last_edit_time
        import time
        now = time.time()
        if now - last_edit_time >= 2.0 or current == total:
            last_edit_time = now
            bar_len = 10
            filled = int(percent / 10)
            bar = "█" * filled + "░" * (bar_len - filled)
            cur_str = format_bytes(current)
            tot_str = format_bytes(total)
            speed_str = format_speed(speed) if speed else "—"
            eta_str = format_eta(eta) if eta else "—"
            text = (
                f"⚡ <b>Video yuklanmoqda (Maksimal Turbo Tezlik 🚀)...</b>\n\n"
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
                "Iltimos, havola to'g'riligini va hisobingiz kanalda borligini tekshiring.",
                parse_mode="HTML"
            )
            return

        await status_msg.edit_text(f"✅ <b>{len(results)} ta video yuklab olindi!</b>\nTelegramga uzatilmoqda...", parse_mode="HTML")

        for item in results:
            file_path = Path(item["path"])
            file_size_mb = item["size_bytes"] / (1024 * 1024)

            caption = (
                f"🎬 <b>{escape_html(item['filename'])}</b>\n"
                f"📊 <b>Hajmi:</b> {item['size_formatted']}\n"
                f"⭐️ <b>Izbrannoe (Saqlangan xabarlar)</b> ga joylandi"
            )

            token = _save_ai_media_token({
                "type": "local_file",
                "path": str(file_path),
                "title": item["filename"]
            })
            ai_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🧠 AI Interview Savollari & Konspekt", callback_data=f"ai_anlz:{token}")
            ]])

            if file_size_mb <= 49.5:
                try:
                    video_file = FSInputFile(str(file_path), filename=item["filename"])
                    await message.answer_video(video_file, caption=caption, reply_markup=ai_kb, parse_mode="HTML")
                except Exception:
                    doc_file = FSInputFile(str(file_path), filename=item["filename"])
                    await message.answer_document(doc_file, caption=caption, reply_markup=ai_kb, parse_mode="HTML")
            else:
                sent_via_telethon = False
                if client:
                    upload_notice = await message.answer(f"📤 <b>{escape_html(item['filename'])}</b> chatga uzatilmoqda...")
                    try:
                        uploaded_input_file = await FastTelethon.upload_file(
                            client=client,
                            file_path=file_path,
                            workers=8
                        )
                        await client.send_file(
                            user_id,
                            file=uploaded_input_file,
                            caption=caption,
                            parse_mode="html",
                            supports_streaming=True
                        )
                        try:
                            await upload_notice.delete()
                        except Exception:
                            pass
                        sent_via_telethon = True
                        await message.answer(
                            f"🎬 <b>{escape_html(item['filename'])}</b> muvaffaqiyatli yetkazildi!",
                            reply_markup=ai_kb,
                            parse_mode="HTML"
                        )
                    except Exception as telethon_err:
                        logger.warning(f"Telethon upload xatosi: {telethon_err}")
                        try:
                            await upload_notice.delete()
                        except Exception:
                            pass

                if not sent_via_telethon:
                    await message.answer(
                        f"📁 <b>{escape_html(item['filename'])}</b> ({item['size_formatted']})\n"
                        f"Serverda saqlandi: <code>{escape_html(str(file_path))}</code>",
                        reply_markup=ai_kb,
                        parse_mode="HTML"
                    )

            # Auto AI rejimi
            if auto_ai:
                await status_msg.edit_text("🧠 Video yetkazildi! Endi AI konspekt va interview savollari tahlil qilinmoqda...", parse_mode="HTML")
                await _run_ai_analysis_from_path(status_msg, file_path, item["filename"], user_id)
                return

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Video yuklashda xatolik: {e}")
        err_str = str(e)
        await status_msg.edit_text(f"❌ <b>Yuklab olishda xatolik:</b> {escape_html(err_str)}", parse_mode="HTML")


# =====================================================================
# 3. AI Tahlilchi Callback & Helper Funksiyalar
# =====================================================================

@router.callback_query(F.data.startswith("ai_anlz:"))
async def cb_ai_analyze_video(callback: CallbackQuery):
    """Tugma bosilganda videoni AI orqali tahlil qilish."""
    await callback.answer("🧠 AI tahlili boshlanmoqda...")
    token = callback.data.split(":", 1)[1]
    cached = _AI_MEDIA_CACHE.get(token)

    if not cached:
        await callback.message.answer("⚠️ Video ma'lumotlari keshdan eskirgan. Iltimos, video linkini qayta tashlang.")
        return

    status_msg = await callback.message.answer("🧠 <b>Gemini 3.6 Flash AI video tahlilini boshladi...</b>", parse_mode="HTML")
    user_id = callback.from_user.id

    if cached["type"] == "local_file":
        file_path = Path(cached["path"])
        await _run_ai_analysis_from_path(status_msg, file_path, cached.get("title", "video.mp4"), user_id)
    elif cached["type"] == "telegram_msg":
        client = await AccountCleanerService.get_client(user_id)
        raw_msg = cached["msg"]
        title = cached.get("title", "video.mp4")
        await _download_and_analyze_msg(status_msg, client, raw_msg, title, user_id)


async def _download_and_analyze_msg(status_msg: Message, client, msg, title: str, user_id: int):
    """Bulutdagi xabarni yuklab, AI bilan tahlil qilish."""
    try:
        await status_msg.edit_text("⏳ <b>AI tahlili uchun audio/video yuklanmoqda...</b>", parse_mode="HTML")
        temp_dir = VIDEOS_DIR / "ai_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / f"ai_{title}"

        actual_path = await FastTelethon.download_media(
            client=client,
            media_or_msg=msg,
            out_path=local_path,
            workers=8
        )
        await _run_ai_analysis_from_path(status_msg, Path(actual_path), title, user_id)
    except Exception as e:
        logger.error(f"AI yuklashda xatolik: {e}")
        await status_msg.edit_text(f"❌ <b>AI tahlilida xatolik:</b> {escape_html(str(e))}", parse_mode="HTML")


async def _run_ai_analysis_from_path(status_msg: Message, file_path: Path, title: str, user_id: int):
    """Fayl yo'li orqali AIVideoService ni chaqirish va natijani chiroyli yetkazish."""
    try:
        def _prog(txt):
            asyncio.create_task(status_msg.edit_text(f"<b>{escape_html(txt)}</b>", parse_mode="HTML"))

        result_text = await AIVideoService.analyze_video(file_path, progress_callback=_prog)

        header = f"🎓 <b>VIDEO KONSEPKTI VA INTERVIEW SAVOLLARI</b>\n🎬 <b>Fayl:</b> <code>{escape_html(title)}</code>\n\n"

        # Agar natija bitta xabarga sig'sa (<= 3800 belgi)
        if len(result_text) + len(header) <= 3800:
            try:
                await status_msg.edit_text(header + result_text, parse_mode="Markdown")
            except Exception:
                await status_msg.edit_text(header + result_text, parse_mode="HTML")
        else:
            # Uzun bo'lsa, qismlarga bo'lib yuborish
            await status_msg.edit_text(header, parse_mode="HTML")
            chunks = _split_long_text(result_text, 3500)
            for part in chunks:
                try:
                    await status_msg.answer(part, parse_mode="Markdown")
                except Exception:
                    await status_msg.answer(part)
                await asyncio.sleep(0.5)

            # Qo'shimcha ravishda to'liq konspektni .md fayl sifatida yuborish
            clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()
            md_file = BufferedInputFile(
                result_text.encode('utf-8'),
                filename=f"konspekt_{clean_title}.md"
            )
            await status_msg.answer_document(
                md_file,
                caption=f"📄 <b>{escape_html(title)}</b> ning to'liq AI konspekt fayli (.md)",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"AI video tahlilida xatolik: {e}")
        await status_msg.edit_text(f"❌ <b>AI tahlilida xatolik yuz berdi:</b> {escape_html(str(e))}", parse_mode="HTML")


def _split_long_text(text: str, max_size: int = 3500) -> list[str]:
    """Uzun matnni paragraflar bo'yicha toza bo'lib beradi."""
    parts = []
    lines = text.split("\n")
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > max_size:
            if current:
                parts.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        parts.append(current.strip())
    return parts
