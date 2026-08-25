import os
import asyncio
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.media_downloader_service import MediaDownloaderService, VIDEOS_DIR, DOWNLOADS_DIR
from services.account_cleaner_service import AccountCleanerService
from services.fast_telethon import FastTelethon
from keyboards.inline import cleaner_login_methods_keyboard
from utils.helpers import escape_html, format_bytes, format_speed, format_eta
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
        "📥 <b>Telegram Private & Public Video Tezkor Yuklovchi ⚡</b>\n\n"
        "Yopiq (Private) yoki ochiq kanaldagi video xabar havolasini (link) yuboring:\n\n"
        "<b>Misollar:</b>\n"
        "• Bitta video: <code>https://t.me/c/1234567890/45</code>\n"
        "• Ketma-ket bir nechta video: <code>https://t.me/c/1234567890/45-50</code>\n"
        "• Ommaviy kanal: <code>https://t.me/kanal_nomi/123</code>\n\n"
        "<i>⚡ Multi-stream tezkor yuklash texnologiyasi yoqilgan (10-20x tezroq!). Bekor qilish: /cancel</i>",
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
    """Yuklab olish jarayoni va progressni Telegramda ko'rsatish (Maksimal turbo tezlikda)."""
    user_id = message.from_user.id
    status_msg = await message.answer("⚡ <b>Video tekshirilmoqda...</b>", parse_mode="HTML")

    is_auth = await AccountCleanerService.is_authorized(user_id)
    if not is_auth:
        await status_msg.edit_text(
            "🔑 <b>Avval Telegram hisobingizga kirishingiz kerak!</b>\n\n"
            "Yopiq va ommaviy kanallardan video yuklash uchun /cleaner buyrug'i orqali akkauntingizni ulang.",
            parse_mode="HTML"
        )
        return

    client = await AccountCleanerService.get_client(user_id)
    ch_peer, msg_ids = MediaDownloaderService.parse_telegram_link(link)

    # 1-BOSQICH: INSTANT DIRECT CLOUD TRANSFER (0.1 soniyada srazi yuborish ⚡)
    try:
        all_sent_instantly = True
        for msg_id in msg_ids:
            msg = await client.get_messages(ch_peer, ids=msg_id)
            if not msg or not msg.media:
                all_sent_instantly = False
                break

            direct_sent = False
            # 1.1 To'g'ridan-to'g'ri forward qilish (0.1s)
            try:
                await client.forward_messages(user_id, msg)
                try:
                    await client.forward_messages('me', msg)
                except Exception:
                    pass
                direct_sent = True
            except Exception:
                # 1.2 Agar forward taqiqlangan bo'lsa, cloud send_file (0.2s)
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

            if not direct_sent:
                all_sent_instantly = False
                break

        if all_sent_instantly:
            await status_msg.edit_text("⚡ <b>Video srazi (bir zumda) yuborildi!</b>", parse_mode="HTML")
            return
    except Exception as direct_err:
        logger.info(f"Direct cloud transfer mumkin bo'lmadi (Protected channel): {direct_err}")

    # 2-BOSQICH: PROTECTED CONTENT UCHUN MAKSIMAL 8-STREAM PARALLEL TURBO YUKLASH
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
                "Iltimos, havolani to'g'ri nusxalaganingizni va akkauntingiz ushbu kanalda borligini tekshiring.",
                parse_mode="HTML"
            )
            return

        await status_msg.edit_text(f"✅ <b>{len(results)} ta video yuklab olindi!</b>\nTelegramga va Saqlangan xabarlarga uzatilmoqda...", parse_mode="HTML")

        for item in results:
            file_path = Path(item["path"])
            file_size_mb = item["size_bytes"] / (1024 * 1024)

            caption = (
                f"🎬 <b>{escape_html(item['filename'])}</b>\n"
                f"📊 <b>Hajmi:</b> {item['size_formatted']}\n"
                f"⭐️ <b>Izbrannoe (Saqlangan xabarlar)</b> ga joylandi"
            )

            uploaded_input_file = None

            # 1. Bot chatiga yuborish
            if file_size_mb <= 49.5:
                try:
                    video_file = FSInputFile(str(file_path), filename=item["filename"])
                    await message.answer_video(video_file, caption=caption, parse_mode="HTML")
                except Exception as send_err:
                    logger.warning(f"Video yuborishda xato, fayl qilib yuborilmoqda: {send_err}")
                    doc_file = FSInputFile(str(file_path), filename=item["filename"])
                    await message.answer_document(doc_file, caption=caption, parse_mode="HTML")
            else:
                # 50 MB dan katta bo'lsa (2 GB gacha), 8 ta parallel oqimda upload
                sent_via_telethon = False
                if client:
                    upload_notice = await message.answer(f"📤 <b>{escape_html(item['filename'])}</b> ({item['size_formatted']}) chatga tezkor uzatilmoqda...")
                    last_up_time = 0

                    def _on_up_progress(cur, tot, spd, eta):
                        nonlocal last_up_time
                        import time
                        now = time.time()
                        if now - last_up_time >= 2.0 or cur == tot:
                            last_up_time = now
                            percent = (cur / tot) * 100 if tot else 0
                            bar_len = 10
                            filled = int(percent / 10)
                            bar = "█" * filled + "░" * (bar_len - filled)
                            spd_str = format_speed(spd) if spd else "—"
                            eta_str = format_eta(eta) if eta else "—"
                            up_text = (
                                f"📤 <b>Chatga yuborilmoqda (Tezkor Upload ⚡)...</b>\n\n"
                                f"🎬 <b>Fayl:</b> <code>{escape_html(item['filename'])}</code>\n"
                                f"[{bar}] <b>{percent:.1f}%</b>\n"
                                f"📊 <b>Hajm:</b> {format_bytes(cur)} / {format_bytes(tot)}\n"
                                f"🚀 <b>Tezlik:</b> {spd_str} | ⏱ <b>Qolgan:</b> {eta_str}"
                            )
                            asyncio.create_task(upload_notice.edit_text(up_text, parse_mode="HTML"))

                    try:
                        uploaded_input_file = await FastTelethon.upload_file(
                            client=client,
                            file_path=file_path,
                            workers=8,
                            progress_callback=_on_up_progress
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
                    except Exception as telethon_err:
                        logger.warning(f"Telethon parallel upload xato: {telethon_err}")
                        try:
                            await upload_notice.delete()
                        except Exception:
                            pass


                if not sent_via_telethon:
                    await message.answer(
                        f"📁 <b>{escape_html(item['filename'])}</b> ({item['size_formatted']})\n\n"
                        f"📍 Fayl serverda saqlandi: <code>{escape_html(str(file_path))}</code>\n"
                        f"Uni /files bo'limidan boshqarishingiz mumkin.",
                        parse_mode="HTML"
                    )

            # 2. Avtomatik tarzda shaxsiy "Saqlangan xabarlar" (Избранное / Saved Messages) ga yuborish
            if client:
                saved_to_me = False
                raw_msg = item.get("msg")
                # Birinchi urinish: Tezkor forward (0 soniya)
                if raw_msg:
                    try:
                        await client.forward_messages('me', raw_msg)
                        saved_to_me = True
                    except Exception:
                        pass

                # Agar kanal protected bo'lsa yoki forward ishlamasa:
                if not saved_to_me:
                    try:
                        saved_caption = (
                            f"🎬 <b>{escape_html(item['filename'])}</b>\n"
                            f"📊 <b>Hajmi:</b> {item['size_formatted']}\n"
                            f"📁 <b>Loyiha papkasi:</b> <code>videolar/{file_path.name}</code>"
                        )
                        # Agar oldingi qadamda fayl allaqachon upload qilingan bo'lsa, qayta yuklamaymiz!
                        send_target = uploaded_input_file if uploaded_input_file else str(file_path)
                        await client.send_file(
                            'me',
                            file=send_target,
                            caption=saved_caption,
                            parse_mode="html",
                            supports_streaming=True
                        )
                    except Exception as me_err:
                        logger.warning(f"Izbrannoega video yuborishda xato: {me_err}")

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Video yuklashda xatolik: {e}")
        err_str = str(e)
        if "Two-steps verification" in err_str or "2FA" in err_str or "password is required" in err_str:
            err_msg = (
                "🔒 <b>Ikki bosqichli parol (2FA / Облачный пароль) talab qilinadi!</b>\n\n"
                "Ushbu Telegram akkauntingizda 2FA paroli yoqilgan.\n"
                "Iltimos, botda /cleaner buyrug'ini bosing va parolingizni kiritib ulanishni to'liq yakunlang."
            )
        elif "ChannelPrivateError" in err_str or "ChatAdminRequiredError" in err_str:
            err_msg = (
                "⛔ <b>Kanalga kirish huquqi yo'q!</b>\n\n"
                "Botga ulangan Telegram akkaunt ushbu yopiq/pulli kanalga a'zo emas.\n"
                "Iltimos, pulli kanal bor akkauntni /cleaner orqali ulang."
            )
        else:
            err_msg = f"❌ <b>Yuklab olishda xatolik:</b> {escape_html(err_str)}"

        await status_msg.edit_text(err_msg, parse_mode="HTML")

    finally:
        # RAM xotiradagi vaqtincha buferlarni tozalash (Garbage Collector)
        import gc
        gc.collect()

