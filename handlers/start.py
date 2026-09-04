import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from keyboards.reply import get_main_reply_keyboard
from keyboards.inline import start_main_inline_keyboard
from services.account_cleaner_service import AccountCleanerService
from services.user_service import UserService
from utils.helpers import escape_html
from utils.logger import logger

router = Router()


@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    """Bot boshlang'ich salomlashuv xabari."""
    await state.clear()
    user_id = message.from_user.id

    UserService.register_user(
        user_id=user_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )

    profile_line = "👤 <b>Telegram hisob:</b> ⚪ <i>Ulanmagan (/cleaner)</i>\n"
    try:
        profile = AccountCleanerService.get_cached_profile(user_id)
        if not profile or not profile.get("name"):
            profile = await AccountCleanerService.get_or_fetch_profile(user_id)

        if profile and profile.get("name"):
            p_name = escape_html(profile.get("name", "Foydalanuvchi"))
            p_uname = f" ({profile.get('username')})" if profile.get("username") else ""
            profile_line = f"👤 <b>Ulangan hisob:</b> 🟢 <b>{p_name}</b>{p_uname}\n"
    except Exception as e:
        logger.warning(f"Start profile check error: {e}")



    welcome_text = (
        "🚀 <b>Universal Video & MP3 Downloader Botiga Xush Kelibsiz!</b>\n\n"
        f"{profile_line}\n"
        "✨ <b>Asosiy Imkoniyatlar:</b>\n"
        "• 📥 <b>Universal Video Yuklash:</b> Telegram (yopiq/ochiq kanallar), YouTube, Instagram Reels, TikTok (suv belgisiz), Pinterest va hk. (/dl)\n"
        "• 🎵 <b>Yuqori Sifatli MP3:</b> Istalgan videodan 320kbps stereo musiqani 1 soniyada ajratish va to'g'ridan-to'g'ri MP3 yuklash (/mp3)\n"
        "• 🧹 <b>Hisobni Tozalash:</b> 'Deleted Account' chatlar, nofaol kanallarni tozalash (/cleaner)\n\n"
        "<i>Quyidagi tugmalardan birini tanlang yoki to'g'ridan-to'g'ri video havolasini yuboring:</i>"
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard()
    )
    await message.answer(
        "⚡ <b>Tezkor menyu:</b>",
        parse_mode="HTML",
        reply_markup=start_main_inline_keyboard()
    )


@router.message(Command("help"), StateFilter("*"))
@router.message(F.text == "ℹ️ Qo'llanma / Yordam", StateFilter("*"))
async def cmd_help(message: Message, state: FSMContext):
    """Buyruqlar va to'liq qo'llanma."""
    await state.clear()
    help_text = (
        "📖 <b>Universal Video & MP3 Downloader Qo'llanmasi</b>\n\n"
        "📥 <b>1. Video Yuklash (Barcha Tarmoqlar):</b>\n"
        "• <code>/dl &lt;link&gt;</code> — Telegram (yopiq/ochiq), YouTube, Instagram, TikTok, Pinterest dan yuklash\n"
        "• <i>Havolani chatga tashlasangiz, bot Videoni ham, 320kbps MP3 ni ham birgalikda yuboradi!</i>\n\n"
        "🎵 <b>2. Faqat MP3 Yuklash:</b>\n"
        "• <code>/mp3 &lt;link&gt;</code> — Videoni yuklamasdan faqat 320kbps audio faylni tezkor yuklab olish\n"
        "• <i>Shuningdek, botga to'g'ridan-to'g'ri video fayl tashlasangiz ham uni MP3 ga aylantirib beradi.</i>\n\n"
        "🧹 <b>3. Telegram Hisobni Tozalash:</b>\n"
        "• <code>/cleaner</code> — Tozalash boshqaruv panelini ochish\n"
        "• <code>/clean_deleted</code> — O'chgan hisoblar ('Deleted Accounts') bilan chatlarni o'chirish\n"
        "• <code>/clean_channels [kun]</code> — Nofaol kanal va guruhlardan chiqish\n\n"
        "🔒 <b>4. Akkaunt Sessiyasi Xavfsizligi:</b>\n"
        "• Ulangan hisobingiz <b>data/sessions_registry.json</b> orqali doimiy saqlanadi."
    )
    await message.answer(help_text, parse_mode="HTML")



@router.callback_query(F.data == "open_help")
async def cb_open_help(callback: CallbackQuery, state: FSMContext):
    await cmd_help(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "open_cleaner")
async def cb_open_cleaner(callback: CallbackQuery, state: FSMContext):
    from handlers.cleaner import cmd_cleaner_menu
    await cmd_cleaner_menu(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "open_dl")
async def cb_open_dl(callback: CallbackQuery, state: FSMContext):
    from handlers.media_downloader import cmd_download_media
    await cmd_download_media(callback.message, state, callback.bot)
    await callback.answer()


@router.callback_query(F.data == "open_mp3")
async def cb_open_mp3(callback: CallbackQuery, state: FSMContext):
    from handlers.media_downloader import cmd_download_mp3
    await cmd_download_mp3(callback.message, state, callback.bot)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
