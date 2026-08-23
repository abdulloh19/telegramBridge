from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from keyboards.reply import get_main_reply_keyboard
from keyboards.inline import start_main_inline_keyboard
from config import get_user_cwd
from utils.helpers import escape_html

router = Router()


@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    """Bot boshlang'ich salomlashuv xabari."""
    await state.clear()
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)

    from services.account_cleaner_service import AccountCleanerService
    profile = AccountCleanerService.get_cached_profile(user_id)
    profile_line = ""
    if profile:
        p_name = escape_html(profile.get("name", "Foydalanuvchi"))
        p_uname = f" ({profile.get('username')})" if profile.get("username") else ""
        profile_line = f"👤 <b>Ulangan Telegram hisob:</b> 🟢 <b>{p_name}</b>{p_uname}\n"
    else:
        asyncio.create_task(AccountCleanerService.get_or_fetch_profile(user_id))

    welcome_text = (
        "🚀 <b>Telegram Dev Bridge & AI Agent ga xush kelibsiz!</b>\n\n"
        f"{profile_line}"
        f"📂 <b>Joriy ishchi papka:</b>\n<code>{escape_html(str(cwd))}</code>\n\n"
        "✨ <b>Asosiy Imkoniyatlar:</b>\n"
        "• 📁 <b>Fayllar Menejeri:</b> Fayllarni ko'rish, tahrirlash, yuklab olish\n"
        "• 💻 <b>Terminal:</b> Masofadan buyruqlarni bajarish (/sh yoki 💻 Terminal)\n"
        "• 🤖 <b>AI Agent:</b> Xatolarni tuzatish (/fix), avtonom kod yozish (/agent)\n"
        "• 📥 <b>Video Yuklash:</b> Yopiq (Private) va ochiq kanallardan video olish (/dl)\n"
        "• 🧹 <b>Hisobni Tozalash:</b> 'Deleted Account' va nofaol kanallarni tozalash (/cleaner)\n"
        "• 📊 <b>Monitoring & Skrinshot:</b> CPU, RAM va monitor ekrani\n\n"
        "<i>Quyidagi tugmalardan birini tanlang yoki buyruq yuboring:</i>"
    )

    # Pastki doimiy klaviaturani majburiy yangilash
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard()
    )
    # Qo'shimcha interaktiv inline menyuni yuborish
    await message.answer(
        "⚡ <b>Tezkor menyu:</b>",
        parse_mode="HTML",
        reply_markup=start_main_inline_keyboard()
    )


@router.message(Command("help"), StateFilter("*"))
async def cmd_help(message: Message, state: FSMContext):
    """Barcha mavjud buyruqlar va qo'llanma."""
    await state.clear()
    help_text = (
        "📖 <b>Telegram Dev Bridge — Buyruqlar Qo'llanmasi</b>\n\n"
        "📁 <b>Fayl Boshqaruvi:</b>\n"
        "• <code>/ls</code> yoki <code>/files</code> — Fayllar brauzerini ochish\n"
        "• <code>/cd &lt;yo'l&gt;</code> — Boshqa papkaga o'tish\n"
        "• <code>/view &lt;fayl&gt;</code> — Fayl kodini ko'rish\n"
        "• <code>/edit &lt;fayl&gt;</code> — Faylni tahrirlash\n"
        "• <code>/create &lt;fayl&gt;</code> — Yangi fayl yaratish\n"
        "• <code>/mkdir &lt;papka&gt;</code> — Yangi papka ochish\n"
        "• <code>/rm &lt;yo'l&gt;</code> — Fayl yoki papkani o'chirish\n"
        "• <code>/download &lt;fayl&gt;</code> — Faylni kompyuterdan telefonga yuklab olish\n"
        "• <code>/search &lt;kod&gt;</code> — Loyiha ichidan matn/kod qidirish\n\n"
        "💻 <b>Terminal va Shell:</b>\n"
        "• <code>/sh &lt;buyruq&gt;</code> — Terminal buyrug'ini bajarish (masalan: <code>/sh dir</code> yoki <code>/sh git status</code>)\n"
        "• <code>/terminal</code> yoki <code>💻 Terminal</code> tugmasi — Interaktiv terminal rejimi\n\n"
        "🤖 <b>Sun'iy Intellekt (AI Agent):</b>\n"
        "• <code>/agent &lt;vazifa&gt;</code> — Avtonom AI agentiga vazifa berish\n"
        "• <code>/fix &lt;fayl&gt; &lt;muammo&gt;</code> — Fayldagi xatolikni avtomatik tuzatish\n"
        "• <code>/explain &lt;fayl&gt;</code> — Fayl kodi ishlashini tushuntirish\n"
        "• <code>/review &lt;fayl&gt;</code> — Kodni tozalik va xavfsizlikka tekshirish\n"
        "• <code>/ai &lt;savol&gt;</code> — AI dan to'g'ridan-to'g'ri maslahat olish\n\n"
        "📥 <b>Telegram Media / Video Yuklovchi:</b>\n"
        "• <code>/dl &lt;link&gt;</code> — Yopiq (Private) yoki ommaviy kanaldan video yuklab olish\n"
        "• <code>📥 Video Yuklash</code> — Interaktiv video yuklash menyusi\n\n"
        "🧹 <b>Telegram Hisobni Tozalash (Account Cleaner):</b>\n"
        "• <code>/cleaner</code> — Tozalash boshqaruv panelini ochish\n"
        "• <code>/clean_deleted</code> — O'chib ketgan ('Deleted Account') chatlarni tozalash\n"
        "• <code>/clean_channels [kun]</code> — Nofaol kanallar va guruhlardan chiqish\n"
        "• <code>/clean_old [kun]</code> — Eski yozishmalarni tozalash\n"
        "• <code>/set_api</code> — Telegram API_ID va API_HASH ni kiritish\n"
        "• <code>/cleaner_logout</code> — Telethon hisobidan chiqish\n\n"
        "📊 <b>Tizim va Kompyuter:</b>\n"
        "• <code>/status</code> — CPU, RAM, Disk, Batareya statistikasi\n"
        "• <code>/screenshot</code> — Kompyuter monitoridan skrinshot olish\n"
        "• <code>/processes</code> — Ishlayotgan jarayonlar (Top RAM/CPU)\n"
        "• <code>/kill &lt;pid&gt;</code> — Jarayonni to'xtatish\n"
        "• <code>/lock</code> — Kompyuter ekranini bloklash"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.text == "⚙️ Sozlamalar / Yordam", StateFilter("*"))
async def btn_settings_help(message: Message, state: FSMContext):
    await cmd_help(message, state)


@router.callback_query(F.data == "open_help")
async def cb_open_help(callback: CallbackQuery, state: FSMContext):
    await cmd_help(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "open_files")
async def cb_open_files(callback: CallbackQuery, state: FSMContext):
    from handlers.files import cmd_files
    await cmd_files(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "open_terminal")
async def cb_open_terminal(callback: CallbackQuery, state: FSMContext):
    from handlers.terminal import cmd_interactive_terminal
    await cmd_interactive_terminal(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "open_ai")
async def cb_open_ai(callback: CallbackQuery, state: FSMContext):
    from handlers.ai_agent import cmd_agent_interactive
    await cmd_agent_interactive(callback.message, state)
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
    """Hech narsa qilmaydigan indikator tugma."""
    await callback.answer()

