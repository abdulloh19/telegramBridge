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
        "🚀 <b>Telegram Video Downloader & AI Assistant Botiga Xush Kelibsiz!</b>\n\n"
        f"{profile_line}\n"
        "✨ <b>Asosiy Imkoniyatlar:</b>\n"
        "• 📥 <b>Video Yuklash:</b> Yopiq va ommaviy kanallardagi 45+ minutli videolarni maksimal yuqori tezlikda yuklash (/dl).\n"
        "• 🧠 <b>AI Konspekt & Interview:</b> Videodagi interview savollarini taym-kodlar bilan ajratish va mukammal konspekt olish (/ai).\n"
        "• 🧹 <b>Hisobni Tozalash:</b> 'Deleted Account' chatlar, nofaol kanallar va eski yozishmalarni tozalash (/cleaner).\n\n"
        "<i>Quyidagi tugmalardan birini tanlang yoki video havolasini yuboring:</i>"
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
        "📖 <b>Telegram Video Downloader & AI Qo'llanmasi</b>\n\n"
        "📥 <b>1. Video Yuklash (Private & Public):</b>\n"
        "• <code>/dl &lt;link&gt;</code> — Yopiq yoki ommaviy kanaldan video yuklash\n"
        "• <b>Misol:</b> <code>https://t.me/c/1234567890/45</code>\n"
        "• <i>Shunchaki linkni tashlasangiz ham avtomatik yuklaydi.</i>\n\n"
        "🧠 <b>2. AI Video Konspekt & Interview Savollari:</b>\n"
        "• <code>/ai &lt;link&gt;</code> — Videoni yuklab, undagi barcha intervyu savollarini va konspektini chiqarib beradi.\n"
        "• Video yuklangach, tagidagi <b>[ 🧠 AI Konspekt & Interview ]</b> tugmasini bossangiz ham yetarli.\n\n"
        "🧹 <b>3. Telegram Hisobni Tozalash:</b>\n"
        "• <code>/cleaner</code> — Tozalash boshqaruv panelini ochish\n"
        "• <code>/clean_deleted</code> — O'chgan hisoblar ('Deleted Accounts') bilan chatlarni o'chirish\n"
        "• <code>/clean_channels [kun]</code> — Nofaol kanal va guruhlardan chiqish\n\n"
        "🔒 <b>4. Akkaunt Sessiyasi Xavfsizligi:</b>\n"
        "• Ulangan hisobingiz <b>data/sessions_registry.json</b> orqali doimiy saqlanadi. Server qayta yoqilsa ham hisobingiz hech qachon o'chib ketmaydi."
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


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
