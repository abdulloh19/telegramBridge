import os
import asyncio
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.media_downloader_service import MediaDownloaderService, DOWNLOADS_DIR
from services.account_cleaner_service import AccountCleanerService
from keyboards.inline import cleaner_login_methods_keyboard
from utils.helpers import escape_html, format_bytes
from utils.logger import logger

router = Router()


class DownloaderStates(StatesGroup):
    waiting_for_media_link = State()


@router.message(Command("dl"), StateFilter("*"))
@router.message(Command("download_media"), StateFilter("*"))
@router.message(F.text == "📥 Video Yuklash", StateFilter("*"))
async def cmd_download_media(message: Message, state: FSMContext, bot: Bot):
    """Yopiq yoki ochiq Telegram kanallardan video yuklab olish menyusi."""
    await state.clear()
    args = message.text.split(maxsplit=1)

    # 1. Agar buyruq bilan birga link yuborilgan bo'lsa: /dl https://t.me/c/...
    if len(args) > 1 and "t.me/" in args[1]:
        await _process_media_download(message, args[1].strip(), bot)
        return

    # 2. Havola so'rash
    await state.set_state(DownloaderStates.waiting_for_media_link)
    await message.answer(
        "📥 <b>Telegram Private & Public Video Yuklovchi</b>\n\n"
        "Yopiq (Private) yoki ochiq kanaldagi video xabar havolasini (link) yuboring:\n\n"
        "<b>Misollar:</b>\n"
        "• Bitta video: <code>https://t.me/c/1234567890/45</code>\n"
        "• Ketma-ket bir nechta video: <code>https://t.me/c/1234567890/45-50</code>\n"
        "• Ommaviy kanal: <code>https://t.me/kanal_nomi/123</code>\n\n"
        "<i>(Kanal havolasini olish uchun kanaldagi videoga 'Copy Link' / 'Havolani nusxalash' qiling). Bekor qilish: /cancel</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(DownloaderStates.waiting_for_media_link)
async def handle_media_link_input(message: Message, state: FSMContext, bot: Bot):
    """Foydalanuvchi yuborgan linkni qabul qilib yuklab berish."""
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Video yuklash bekor qilindi.")
        return

    link = message.text.strip()
    if "t.me/" not in link:
        await message.answer(
            "❌ <b>Noto'g'ri havola!</b>\n\n"
            "Iltimos, Telegram video havolasini yuboring:\n"
            "Masalan: <code>https://t.me/c/1234567890/45</code>\n\n"
            "<i>Bekor qilish uchun /cancel yuboring.</i>",
            parse_mode="HTML"
        )
        return

    await state.clear()
    await _process_media_download(message, link, bot)


@router.message(F.text.regexp(r'https?://t\.me/(c/\d+|[a-zA-Z0-9_]+)/\d+'), StateFilter(None))
async def handle_direct_telegram_link(message: Message, state: FSMContext, bot: Bot):
    """Foydalanuvchi to'g'ridan-to'g'ri link tashlaganida ham avtomatik yuklash."""
    await _process_media_download(message, message.text.strip(), bot)


async def _process_media_download(message: Message, link: str, bot: Bot):
    """Yuklab olish jarayoni va progressni Telegramda ko'rsatish."""
    user_id = message.from_user.id
    status_msg = await message.answer("🔍 Havola tekshirilmoqda va video qidirilmoqda...")

    last_edit_time = 0

    def _on_progress(current, total, filename, percent):
        nonlocal last_edit_time
        import time
        now = time.time()
        if now - last_edit_time >= 2.5 or current == total:
            last_edit_time = now
            bar_len = 10
            filled = int(percent / 10)
            bar = "█" * filled + "░" * (bar_len - filled)
            cur_str = format_bytes(current)
            tot_str = format_bytes(total)
            text = (
                f"📥 <b>Video yuklanmoqda...</b>\n\n"
                f"🎬 <b>Fayl:</b> <code>{escape_html(filename)}</code>\n"
                f"[{bar}] <b>{percent:.1f}%</b>\n"
                f"📊 <b>Hajm:</b> {cur_str} / {tot_str}"
            )
            asyncio.create_task(status_msg.edit_text(text, parse_mode="HTML"))

    try:
        results = await MediaDownloaderService.download_videos_from_link(
            user_id=user_id,
            link=link,
            save_dir=DOWNLOADS_DIR,
            progress_callback=_on_progress
        )

        if not results:
            await status_msg.edit_text(
                "❌ <b>Ko'rsatilgan havolada video yoki media topilmadi!</b>\n"
                "Iltimos, havolani to'g'ri nusxalaganingizni va akkauntingiz ushbu kanalda borligini tekshiring.",
                parse_mode="HTML"
            )
            return

        await status_msg.edit_text(f"✅ <b>{len(results)} ta video muvaffaqiyatli yuklab olindi!</b>\nTelegramga yuborilmoqda...", parse_mode="HTML")

        for item in results:
            file_path = Path(item["path"])
            file_size_mb = item["size_bytes"] / (1024 * 1024)

            # Agar fayl 50 MB dan kichik bo'lsa, to'g'ridan-to'g'ri Telegram chatga video qilib yuboramiz
            if file_size_mb <= 49.5:
                try:
                    video_file = FSInputFile(str(file_path), filename=item["filename"])
                    caption = (
                        f"🎬 <b>{escape_html(item['filename'])}</b>\n"
                        f"📊 Hajmi: {item['size_formatted']}\n"
                        f"💾 Saqlandi: <code>downloads/{file_path.name}</code>"
                    )
                    await message.answer_video(video_file, caption=caption, parse_mode="HTML")
                except Exception as send_err:
                    logger.warning(f"Video yuborishda xato, fayl qilib yuborilmoqda: {send_err}")
                    doc_file = FSInputFile(str(file_path), filename=item["filename"])
                    await message.answer_document(doc_file, caption=f"🎬 <b>{escape_html(item['filename'])}</b>", parse_mode="HTML")
            else:
                # 50 MB dan katta bo'lsa (2 GB gacha), Telethon orqali cheklovsiz chatga yuboramiz!
                caption = (
                    f"🎬 <b>{escape_html(item['filename'])}</b>\n"
                    f"📊 Hajmi: {item['size_formatted']} (Katta hajm)\n"
                    f"💾 Saqlandi: <code>downloads/{file_path.name}</code>"
                )
                sent_via_telethon = False
                try:
                    if await AccountCleanerService.is_authorized(user_id):
                        upload_notice = await message.answer(f"📤 <b>{escape_html(item['filename'])}</b> ({item['size_formatted']}) katta hajm bo'lgani uchun Telethon orqali chatga yuborilmoqda...")
                        client = await AccountCleanerService.get_client(user_id)
                        await client.send_file(
                            user_id,
                            file=str(file_path),
                            caption=caption,
                            parse_mode="html",
                            supports_streaming=True
                        )
                        try:
                            await upload_notice.delete()
                        except Exception:
                            pass
                        sent_via_telethon = True
                except Exception as telethon_err:
                    logger.warning(f"Telethon orqali yuborishda xato: {telethon_err}")

                if not sent_via_telethon:
                    await message.answer(
                        f"📁 <b>{escape_html(item['filename'])}</b> ({item['size_formatted']})\n\n"
                        f"📍 Fayl saqlandi: <code>{escape_html(str(file_path))}</code>\n"
                        f"Uni /files bo'limidan boshqarishingiz mumkin.",
                        parse_mode="HTML"
                    )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Video yuklashda xatolik: {e}")
        await status_msg.edit_text(
            f"❌ <b>Yuklab olishda xatolik:</b> {escape_html(str(e))}",
            parse_mode="HTML"
        )
