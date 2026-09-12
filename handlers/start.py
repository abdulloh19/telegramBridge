import asyncio
from aiogram import Router, F, Bot
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
        "🚀 <b>Universal Video & MP3 Downloader & Super Ilova Botiga Xush Kelibsiz!</b>\n\n"
        f"{profile_line}\n"
        "✨ <b>Asosiy Imkoniyatlar:</b>\n"
        "• 🚀 <b>Super Ilova & So'zlar:</b> Rus va Ingliz tili mnemonikasi, 25 ta dars so'zi, audio va o'yinlar (/app, /words)\n"
        "• 📥 <b>Universal Video Yuklash:</b> Telegram (yopiq/ochiq kanallar), YouTube, Instagram Reels, TikTok (suv belgisiz), Pinterest va hk. (/dl)\n"
        "• 🎵 <b>Yuqori Sifatli MP3:</b> Istalgan videodan 320kbps stereo musiqani 1 soniyada ajratish va to'g'ridan-to'g'ri MP3 yuklash (/mp3)\n"
        "• 🧹 <b>Hisobni Tozalash:</b> 'Deleted Account' chatlar, nofaol kanallarni tozalash (/cleaner)\n\n"
        "<i>Quyidagi tugmalardan birini tanlang yoki to'g'ridan-to'g'ri video havolasini yuboring:</i>"
    )

    # Menyu tugmasini yangilash
    try:
        from aiogram.types import MenuButtonWebApp, WebAppInfo
        from config import WEBAPP_URL
        await message.bot.set_chat_menu_button(
            chat_id=user_id,
            menu_button=MenuButtonWebApp(text="Super ilova", web_app=WebAppInfo(url=WEBAPP_URL))
        )
    except Exception as e:
        logger.warning(f"Set menu button error: {e}")

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


@router.message(Command("app", "words", "sozlar"), StateFilter("*"))
@router.message(F.text.in_({"🚀 Super Ilova (25 ta so'z)", "🚀 Super ilova", "📚 So'zlar"}), StateFilter("*"))
async def cmd_super_app(message: Message, state: FSMContext):
    """Super Ilova va so'zlar hisoblagichi haqida ma'lumot va ochish tugmasi."""
    await state.clear()
    from config import WEBAPP_URL
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

    text = (
        "🚀 <b>Mnemonic Super Ilova & So'zlar Tizimi</b>\n\n"
        "✨ <b>Joriy So'zlar Tahlili (Dinamik):</b>\n"
        "• 🇷🇺 <b>Rus tili:</b> 19 ta o'zlashtirilgan / 25 ta dars so'zi\n"
        "• 🇬🇧 <b>Ingliz tili:</b> 10 ta o'zlashtirilgan / 25 ta dars so'zi\n"
        "• 🎮 <b>O'yinlar:</b> 3D Flashcards, Juftlikni top, So'z yig'ish, Grammatika saralash\n"
        "• 🗣️ <b>Jonli Dialoglar:</b> Taksi, Kafe, Supermarket audio replikalari bilan\n\n"
        "👇 <i>Quyidagi tugma orqali bevosita Telegram ichida oching:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 Super Ilovani Ochish (25 ta so'z)", web_app=WebAppInfo(url=WEBAPP_URL))
        ],
        [
            InlineKeyboardButton(text="🌐 Brauzerda ochish", url=WEBAPP_URL)
        ]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


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


@router.callback_query(F.data == "btn_quick_restart")
async def cb_quick_restart(callback: CallbackQuery, state: FSMContext):
    await callback.answer("🚀 Bot yangilanmoqda...")
    await cmd_start(callback.message, state)


@router.callback_query(F.data == "btn_quick_dl")
async def cb_quick_dl(callback: CallbackQuery, state: FSMContext):
    from handlers.media_downloader import cmd_download_media
    await callback.answer()
    await cmd_download_media(callback.message, state, callback.bot)


@router.callback_query(F.data == "btn_quick_mp3")
async def cb_quick_mp3(callback: CallbackQuery, state: FSMContext):
    from handlers.media_downloader import cmd_download_mp3
    await callback.answer()
    await cmd_download_mp3(callback.message, state, callback.bot)


@router.message(Command("broadcast", "elon", "xabar"), StateFilter("*"))
async def cmd_broadcast(message: Message, state: FSMContext, bot: Bot):
    """
    Faqat adminlar uchun: Barcha foydalanuvchilarga ommaviy xabarnoma (broadcast) yuborish.
    Foydalanish:
      /broadcast            -> Standart /start bosish talab qiluvchi yangilanish xabari
      /broadcast <matn>     -> Maxsus kiritilgan matnli xabarnoma
    """
    from config import is_admin
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("❌ Bu buyruq faqat bot adminlari uchun ochiq.")
        return

    # Maxsus matn kiritilganligini tekshirish
    parts = message.text.split(maxsplit=1)
    custom_text = parts[1].strip() if len(parts) > 1 else None

    from services.broadcast_service import BroadcastService
    status_msg = await message.answer(
        "🚀 <b>Ommaviy xabarnoma (broadcast) boshlanmoqda...</b>\n\n"
        "<i>Foydalanuvchilar bazasi tekshirilmoqda, iltimos kuting...</i>",
        parse_mode="HTML"
    )

    try:
        res = await BroadcastService.send_broadcast_to_all(
            bot=bot,
            custom_text=custom_text
        )

        report_text = (
            "✅ <b>Ommaviy Xabarnoma Muvaffaqiyatli Yakunlandi!</b>\n\n"
            "📊 <b>Natijalar Hisoboti:</b>\n"
            f"• 👥 <b>Jami foydalanuvchilar:</b> {res['total']} ta\n"
            f"• 🟢 <b>Yetkazildi (Muvaffaqiyatli):</b> {res['sent']} ta\n"
            f"• 🚫 <b>Botni bloklaganlar:</b> {res['blocked']} ta\n"
            f"• ⚠️ <b>Xatoliklar:</b> {res['failed']} ta\n"
            f"• ⏱ <b>Sarflangan vaqt:</b> {res['duration_sec']} soniya\n\n"
            "✨ <i>Barcha foydalanuvchilarga /start bosish talab qilingan xabarnoma yetkazildi.</i>"
        )
        await status_msg.edit_text(report_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Broadcast xatoligi: {e}")
        await status_msg.edit_text(f"❌ <b>Xabarnoma yuborishda xatolik yuz berdi:</b> {escape_html(str(e))}", parse_mode="HTML")
