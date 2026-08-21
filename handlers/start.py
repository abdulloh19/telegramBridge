from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from keyboards.reply import get_main_reply_keyboard
from config import get_user_cwd
from utils.helpers import escape_html

router = Router()


@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    """Bot boshlang'ich salomlashuv xabari."""
    await state.clear()
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)

    welcome_text = (
        "🚀 <b>Telegram Dev Bridge & AI Agent ga xush kelibsiz!</b>\n\n"
        "Ushbu bot orqali siz kompyuteringizdan uzoqda bo'lsangiz ham, "
        "smartfoningizdagi Telegram orqali loyihalaringizni to'liq boshqara olasiz.\n\n"
        f"📂 <b>Joriy ishchi papka:</b>\n<code>{escape_html(str(cwd))}</code>\n\n"
        "✨ <b>Asosiy Imkoniyatlar:</b>\n"
        "• 📁 <b>Fayllar Menejeri:</b> Fayllarni ko'rish, tahrirlash, yaratish, yuklab olish\n"
        "• 💻 <b>Terminal:</b> PowerShell/CMD buyruqlarini masofadan bajarish (/sh yoki 💻 Terminal)\n"
        "• 🤖 <b>AI Agent:</b> Koddagi xatolarni tuzatish (/fix), avtonom kod yozish (/agent)\n"
        "• 📊 <b>Monitoring:</b> CPU, RAM, Disk, Batareya va Uptime\n"
        "• 📸 <b>Skrinshot:</b> Kompyuter ekranining ayni damdagi rasmini olish\n"
        "• 🧹 <b>Hisobni Tozalash:</b> 'Deleted Account' chatlar, nofaol kanallardan chiqish va eski dialoglarni tozalash (/cleaner, /clean_old)\n\n"
        "<i>Quyidagi tezkor tugmalardan foydalanishingiz yoki /help yozishingiz mumkin.</i>"
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_reply_keyboard()
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
        "📊 <b>Tizim va Kompyuter:</b>\n"
        "• <code>/status</code> — CPU, RAM, Disk, Batareya statistikasi\n"
        "• <code>/screenshot</code> — Kompyuter monitoridan skrinshot olish\n"
        "• <code>/processes</code> — Ishlayotgan jarayonlar (Top RAM/CPU)\n"
        "• <code>/kill &lt;pid&gt;</code> — Jarayonni to'xtatish\n"
        "• <code>/lock</code> — Kompyuter ekranini bloklash (Lock)\n"
        "• <code>/notify &lt;xabar&gt;</code> — Windows ekranida bildirishnoma chiqarish\n\n"
        "🧹 <b>Telegram Hisobni Tozalash (Account Cleaner):</b>\n"
        "• <code>/cleaner</code> — Tozalash boshqaruv panelini ochish\n"
        "• <code>/clean_deleted</code> — O'chib ketgan ('Deleted Account') chatlarni tozalash\n"
        "• <code>/clean_channels [kun]</code> — Nofaol (standart 60 kun) kanallar va guruhlardan chiqish\n"
        "• <code>/clean_old [kun]</code> — Eski (standart 90 kun, masalan: <code>/clean_old 30</code>) yozishmalarni tozalash\n"
        "• <code>/cleaner_logout</code> — Telethon hisobidan chiqish"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.text == "⚙️ Sozlamalar / Yordam", StateFilter("*"))
async def btn_settings_help(message: Message, state: FSMContext):
    await cmd_help(message, state)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """Hech narsa qilmaydigan indikator tugma."""
    await callback.answer()
