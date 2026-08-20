from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.account_cleaner_service import AccountCleanerService
from keyboards.inline import cleaner_main_keyboard, confirm_clean_keyboard
from utils.helpers import escape_html
from utils.logger import logger

router = Router()

# Keshda topilgan elementlarni saqlash
_SCANNED_CHANNELS: dict[int, list[int]] = {}
_SCANNED_OLD_DIALOGS: dict[int, list[int]] = {}


class CleanerStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_2fa = State()


@router.message(Command("cleaner"))
@router.message(F.text == "🧹 Hisobni Tozalash")
async def cmd_cleaner_menu(message: Message, state: FSMContext):
    """Telegram hisobini tozalash asosiy menyusi."""
    await state.clear()
    is_conf = AccountCleanerService.is_configured()
    is_auth = await AccountCleanerService.is_authorized() if is_conf else False

    if not is_conf:
        text = (
            "🧹 <b>Telegram Hisobni Tozalash (Account Cleaner)</b>\n\n"
            "Ushbu funksiya sizning shaxsiy Telegram hisobingizdagi:\n"
            "• 🗑️ <b>O'chib ketgan hisoblar:</b> 'Deleted Account' bo'lib qolgan chatlarni tozalash\n"
            "• 🚪 <b>Faol bo'lmagan kanallar:</b> Ancha vaqt kirmagan/yopiq kanallardan chiqish (Leave)\n"
            "• ⏱️ <b>Eski dialoglar:</b> Belgilangan vaqtdan eski yozishmalarni o'chirish\n\n"
            "⚠️ <b>Ishlatish uchun:</b>\n"
            "Telegram hisobingizga ulanish uchun <code>.env</code> fayliga <code>TELEGRAM_API_ID</code> va <code>TELEGRAM_API_HASH</code> kiritilishi kerak.\n\n"
            "<i>(Quyidagi tugma orqali yo'riqnomani ko'rishingiz mumkin)</i>"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=cleaner_main_keyboard(is_auth=False))
        return

    if not is_auth:
        text = (
            "🧹 <b>Telegram Hisobni Tozalash</b>\n\n"
            "⚡ API kalitlar sozlangan, lekin hisobingizga hali kirilmagan.\n\n"
            "Hisobingizni tozalashni boshlash uchun <b>'Telegram Hisobiga Kirish'</b> tugmasini bosing:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=cleaner_main_keyboard(is_auth=False))
        return

    text = (
        "🧹 <b>Telegram Hisobni Tozalash Menejeri</b>\n\n"
        "🟢 <b>Hisobingiz muvaffaqiyatli ulangan!</b>\n\n"
        "Quyidagi tozalash amallaridan birini tanlang:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cleaner_main_keyboard(is_auth=True))


@router.callback_query(F.data == "cl_help_api")
async def cb_help_api(callback: CallbackQuery):
    """API_ID olish yo'riqnomasi."""
    text = (
        "📖 <b>Telegram API_ID va API_HASH olish (1 daqiqa):</b>\n\n"
        "1. Brauzerda <a href='https://my.telegram.org'>my.telegram.org</a> saytiga kiring;\n"
        "2. Telefon raqamingizni kiriting va Telegramga kelgan kodni yozing;\n"
        "3. <b>'API development tools'</b> bo'limiga kiring;\n"
        "4. Ixtiyoriy nom yozib (masalan: <code>CleanerApp</code>) tasdiqlang;\n"
        "5. Chiqqan <b>api_id</b> va <b>api_hash</b> ni loyihadagi <code>.env</code> fayliga yozing:\n\n"
        "<code>TELEGRAM_API_ID=12345678\nTELEGRAM_API_HASH=abcdef0123456789...</code>"
    )
    await callback.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "cl_start_login")
async def cb_start_login(callback: CallbackQuery, state: FSMContext):
    """Hisobga kirish jarayonini boshlash."""
    if not AccountCleanerService.is_configured():
        await callback.answer("Avval .env ga TELEGRAM_API_ID va TELEGRAM_API_HASH ni kiriting!", show_alert=True)
        return

    await state.set_state(CleanerStates.waiting_for_phone)
    await callback.answer()
    await callback.message.answer(
        "📱 <b>Telegram hisobingiz telefon raqamini xalqaro formatda yuboring:</b>\n"
        "Masalan: <code>+998901234567</code>",
        parse_mode="HTML"
    )


@router.message(CleanerStates.waiting_for_phone)
async def handle_phone_input(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "")
    status_msg = await message.answer("⏳ Tasdiqlash kodi yuborilmoqda...")

    try:
        await AccountCleanerService.send_auth_code(phone)
        await state.update_data(phone=phone)
        await state.set_state(CleanerStates.waiting_for_code)
        await status_msg.edit_text(
            f"📩 <b>{escape_html(phone)}</b> raqamiga Telegram orqali tasdiqlash kodi yuborildi!\n\n"
            "Iltimos, kelgan kodni yuboring (masalan: <code>12345</code>):",
            parse_mode="HTML"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Kod yuborishda xatolik: {str(e)}")


@router.message(CleanerStates.waiting_for_code)
async def handle_code_input(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    data = await state.get_data()
    phone = data.get("phone")

    status_msg = await message.answer("⏳ Kirish tekshirilmoqda...")

    try:
        ok, res = await AccountCleanerService.complete_sign_in(phone, code)
        if not ok and res == "2FA_REQUIRED":
            await state.update_data(code=code)
            await state.set_state(CleanerStates.waiting_for_2fa)
            await status_msg.edit_text(
                "🔒 <b>Ikki bosqichli autentifikatsiya (2FA) parolingizni kiriting:</b>",
                parse_mode="HTML"
            )
            return

        await state.clear()
        if ok:
            await status_msg.edit_text(
                f"{res}\n\nEndi hisobingizni tozalashingiz mumkin:",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
        else:
            await status_msg.edit_text(f"❌ {res}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")


@router.message(CleanerStates.waiting_for_2fa)
async def handle_2fa_input(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    phone = data.get("phone")
    code = data.get("code")
    await state.clear()

    status_msg = await message.answer("⏳ 2FA parol tekshirilmoqda...")
    try:
        ok, res = await AccountCleanerService.complete_sign_in(phone, code, password=password)
        if ok:
            await status_msg.edit_text(
                f"{res}\n\nEndi hisobingizni tozalashingiz mumkin:",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
        else:
            await status_msg.edit_text(f"❌ {res}")
    except Exception as e:
        await status_msg.edit_text(f"❌ 2FA tekshirishda xatolik: {str(e)}")


# ==========================================
# 1. O'chib ketgan hisoblar (Deleted Accounts)
# ==========================================

@router.callback_query(F.data == "cl_scan_deleted")
@router.message(Command("clean_deleted"))
async def scan_deleted_accounts_flow(event: Message | CallbackQuery):
    target = event if isinstance(event, Message) else event.message
    status_msg = await target.answer("🔍 Chatlar tekshirilmoqda ('Deleted Account' hisoblar qidirilmoqda)...")

    try:
        deleted = await AccountCleanerService.scan_deleted_accounts()
        if not deleted:
            await status_msg.edit_text("✅ <b>Ajoyib!</b> Sizda birorta ham 'Deleted Account' chat topilmadi.", parse_mode="HTML")
            return

        text = (
            f"🗑️ <b>O'chib ketgan hisoblar (Deleted Accounts)</b>\n\n"
            f"Jami topildi: <b>{len(deleted)}</b> ta o'chib ketgan akkaunt bilan yozishmalar.\n\n"
            f"Ularning barchasini tozalashni xohlaysizmi?"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_clean_keyboard("deleted", len(deleted)))
    except Exception as e:
        await status_msg.edit_text(f"❌ Tekshirishda xatolik: {str(e)}")


@router.callback_query(F.data == "cl_do_deleted")
async def do_delete_deleted_accounts(callback: CallbackQuery):
    await callback.answer("Tozalanmoqda...")
    status_msg = await callback.message.edit_text("⏳ 'Deleted Account' chatlar o'chirilmoqda, kuting...")

    try:
        count = await AccountCleanerService.remove_deleted_accounts()
        await status_msg.edit_text(
            f"🎉 <b>Tozalash yakunlandi!</b>\n\n"
            f"Jami <b>{count}</b> ta 'Deleted Account' chatlari muvaffaqiyatli o'chirildi.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=True)
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ O'chirishda xatolik: {str(e)}")


# ==========================================
# 2. Faol bo'lmagan kanallar va guruhlar
# ==========================================

@router.callback_query(F.data == "cl_scan_channels")
@router.message(Command("clean_channels"))
async def scan_inactive_channels_flow(event: Message | CallbackQuery):
    target = event if isinstance(event, Message) else event.message
    status_msg = await target.answer("🔍 Kanallar va guruhlar tekshirilmoqda (60 kundan ortiq nofaol)...")

    try:
        channels = await AccountCleanerService.scan_inactive_channels(days=60)
        if not channels:
            await status_msg.edit_text("✅ <b>Sizda nofaol kanallar topilmadi!</b>", parse_mode="HTML")
            return

        user_id = target.chat.id
        _SCANNED_CHANNELS[user_id] = [c["id"] for c in channels]

        list_preview = ""
        for c in channels[:10]:
            list_preview += f"• {escape_html(c['title'])} (oxirgi faollik: {c['days_ago']} kun oldin)\n"

        if len(channels) > 10:
            list_preview += f"... va yana {len(channels) - 10} ta kanal.\n"

        text = (
            f"🚪 <b>Faol bo'lmagan kanallar va guruhlar:</b>\n\n"
            f"Jami topildi: <b>{len(channels)}</b> ta (60+ kun faol bo'lmagan)\n\n"
            f"{list_preview}\n"
            f"Ushbu barcha kanallardan chiqib ketishni (Leave) xohlaysizmi?"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_clean_keyboard("channels", len(channels)))
    except Exception as e:
        await status_msg.edit_text(f"❌ Tekshirishda xatolik: {str(e)}")


@router.callback_query(F.data == "cl_do_channels")
async def do_leave_inactive_channels(callback: CallbackQuery):
    user_id = callback.message.chat.id
    ch_ids = _SCANNED_CHANNELS.get(user_id, [])

    if not ch_ids:
        await callback.answer("Nofaol kanallar ro'yxati topilmadi, qaytadan skaner qiling.", show_alert=True)
        return

    await callback.answer("Kanallardan chiqilmoqda...")
    status_msg = await callback.message.edit_text(f"⏳ {len(ch_ids)} ta kanaldan chiqilmoqda, biroz kuting...")

    try:
        count = await AccountCleanerService.leave_inactive_channels(ch_ids)
        _SCANNED_CHANNELS.pop(user_id, None)
        await status_msg.edit_text(
            f"🎉 <b>Muvaffaqiyatli!</b>\n\n"
            f"Jami <b>{count}</b> ta faol bo'lmagan kanal va guruhlardan chiqib ketildi.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=True)
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")


# ==========================================
# 3. Eski dialoglar (Old Chats)
# ==========================================

@router.callback_query(F.data == "cl_scan_old")
@router.message(Command("clean_old"))
async def scan_old_dialogs_flow(event: Message | CallbackQuery):
    target = event if isinstance(event, Message) else event.message
    status_msg = await target.answer("🔍 Eski yozishmalar qidirilmoqda (90 kundan ortiq xabar yozilmagan)...")

    try:
        old_dialogs = await AccountCleanerService.scan_old_dialogs(days=90)
        if not old_dialogs:
            await status_msg.edit_text("✅ <b>90 kundan eski bo'lgan keraksiz dialoglar topilmadi.</b>", parse_mode="HTML")
            return

        user_id = target.chat.id
        _SCANNED_OLD_DIALOGS[user_id] = [d["id"] for d in old_dialogs]

        list_preview = ""
        for d in old_dialogs[:10]:
            list_preview += f"• {escape_html(d['title'])} ({d['days_ago']} kun oldin)\n"

        if len(old_dialogs) > 10:
            list_preview += f"... va yana {len(old_dialogs) - 10} ta dialog.\n"

        text = (
            f"⏱️ <b>Eski Dialoglar (90+ kun oldingi):</b>\n\n"
            f"Jami topildi: <b>{len(old_dialogs)}</b> ta yozishma.\n\n"
            f"{list_preview}\n"
            f"Ushbu eski dialoglarni tozalashni xohlaysizmi?"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_clean_keyboard("old", len(old_dialogs)))
    except Exception as e:
        await status_msg.edit_text(f"❌ Tekshirishda xatolik: {str(e)}")


@router.callback_query(F.data == "cl_do_old")
async def do_delete_old_dialogs(callback: CallbackQuery):
    user_id = callback.message.chat.id
    d_ids = _SCANNED_OLD_DIALOGS.get(user_id, [])

    if not d_ids:
        await callback.answer("Dialoglar ro'yxati topilmadi, qaytadan skaner qiling.", show_alert=True)
        return

    await callback.answer("Dialoglar tozalanmoqda...")
    status_msg = await callback.message.edit_text(f"⏳ {len(d_ids)} ta eski dialog o'chirilmoqda...")

    try:
        count = await AccountCleanerService.delete_old_dialogs(d_ids)
        _SCANNED_OLD_DIALOGS.pop(user_id, None)
        await status_msg.edit_text(
            f"🎉 <b>Muvaffaqiyatli tozalandi!</b>\n\n"
            f"Jami <b>{count}</b> ta eski dialog o'chirildi.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=True)
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {str(e)}")


@router.callback_query(F.data == "cl_cancel")
async def cb_cancel_cleaner(callback: CallbackQuery):
    await callback.answer("Amal bekor qilindi")
    await callback.message.edit_text("❌ Tozalash bekor qilindi.", reply_markup=cleaner_main_keyboard(is_auth=True))


@router.callback_query(F.data == "cl_refresh")
async def cb_refresh_cleaner(callback: CallbackQuery):
    await callback.answer("Yangilandi")
    is_auth = await AccountCleanerService.is_authorized()
    await callback.message.edit_reply_markup(reply_markup=cleaner_main_keyboard(is_auth=is_auth))
