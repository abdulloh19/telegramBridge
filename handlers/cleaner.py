import asyncio
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import save_telegram_api_credentials
from services.account_cleaner_service import AccountCleanerService
from keyboards.inline import (
    cleaner_main_keyboard,
    confirm_clean_keyboard,
    cleaner_login_methods_keyboard,
    cleaner_config_keyboard,
    pinpad_keyboard
)
from utils.helpers import escape_html
from utils.logger import logger

router = Router()

# Keshda topilgan elementlarni saqlash (chat_id -> list of ids)
_SCANNED_CHANNELS: dict[int, list[int]] = {}
_SCANNED_OLD_DIALOGS: dict[int, list[int]] = {}
_ACTIVE_QR_LOGINS: dict[int, object] = {}


class CleanerStates(StatesGroup):
    waiting_for_api_credentials = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_2fa = State()
    waiting_for_qr_2fa = State()


def _parse_api_credentials(text: str) -> tuple[str | None, str | None]:
    """Foydalanuvchi kiritgan matndan API_ID va API_HASH ni ajratib oladi."""
    clean_text = text.replace('=', ' ').replace(':', ' ').replace(',', ' ').replace('"', ' ').replace("'", ' ')
    tokens = clean_text.split()
    api_id, api_hash = None, None
    for t in tokens:
        if t.isdigit() and len(t) >= 5 and not api_id:
            api_id = t
        elif re.match(r'^[a-fA-F0-9]{20,40}$', t) and not api_hash:
            api_hash = t
    return api_id, api_hash


@router.message(Command("set_api"), StateFilter("*"))
async def cmd_set_api_shortcut(message: Message, state: FSMContext):
    """API ma'lumotlarini /set_api buyrug'i orqali to'g'ridan-to'g'ri kiritish."""
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        api_id, api_hash = _parse_api_credentials(args[1])
        if api_id and api_hash:
            save_telegram_api_credentials(api_id, api_hash)
            await state.clear()
            await message.answer(
                f"✅ <b>Telegram API ma'lumotlari muvaffaqiyatli saqlandi!</b>\n\n"
                f"🆔 <b>API_ID:</b> <code>{api_id}</code>\n"
                f"🔑 <b>API_HASH:</b> <code>{api_hash}</code>\n\n"
                f"Endi hisobingizga kirishingiz mumkin:",
                parse_mode="HTML",
                reply_markup=cleaner_login_methods_keyboard()
            )
            return

    await state.set_state(CleanerStates.waiting_for_api_credentials)
    await message.answer(
        "⚙️ <b>Telegram API ma'lumotlarini kiritish:</b>\n\n"
        "<a href='https://my.telegram.org'>my.telegram.org</a> saytidan olgan <b>API_ID</b> va <b>API_HASH</b> laringizni bitta xabarda yuboring:\n\n"
        "Masalan:\n"
        "<code>12345678 abcdef0123456789abcdef0123456789</code>\n\n"
        "<i>(Bot ularni avtomatik <code>.env</code> fayliga joylaydi). Bekor qilish: /cancel</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.callback_query(F.data == "cl_set_api")
async def cb_set_api(callback: CallbackQuery, state: FSMContext):
    """Inline tugma orqali API ma'lumotlarini so'rash."""
    await state.set_state(CleanerStates.waiting_for_api_credentials)
    await callback.answer()
    await callback.message.answer(
        "⚙️ <b>Telegram API ma'lumotlarini kiritish:</b>\n\n"
        "<a href='https://my.telegram.org'>my.telegram.org</a> saytidan olgan <b>API_ID</b> va <b>API_HASH</b> laringizni bitta xabarda yuboring:\n\n"
        "Masalan:\n"
        "<code>12345678 abcdef0123456789abcdef0123456789</code>\n\n"
        "<i>(Bot ularni avtomatik <code>.env</code> fayliga joylaydi). Bekor qilish: /cancel</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.message(CleanerStates.waiting_for_api_credentials)
async def handle_api_credentials_input(message: Message, state: FSMContext):
    """Foydalanuvchi yuborgan API_ID va API_HASH ni qabul qilib .env ga saqlash."""
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    api_id, api_hash = _parse_api_credentials(message.text)
    if not api_id or not api_hash:
        await message.answer(
            "❌ <b>Ma'lumotlar to'liq aniqlanmadi!</b>\n\n"
            "Iltimos, API_ID (raqamlar) va API_HASH (32 ta belgi) ni birga yuboring:\n"
            "Masalan: <code>12345678 abcdef0123456789abcdef0123456789</code>\n\n"
            "<i>Bekor qilish uchun /cancel yuboring.</i>",
            parse_mode="HTML"
        )
        return

    save_telegram_api_credentials(api_id, api_hash)
    await state.clear()
    await message.answer(
        f"✅ <b>Telegram API ma'lumotlari avtomatik .env ga saqlandi!</b>\n\n"
        f"🆔 <b>API_ID:</b> <code>{api_id}</code>\n"
        f"🔑 <b>API_HASH:</b> <code>{api_hash}</code>\n\n"
        f"<i>Endi hisobingizga to'g'ridan-to'g'ri kirishingiz mumkin:</i>",
        parse_mode="HTML",
        reply_markup=cleaner_login_methods_keyboard()
    )


@router.message(Command("cleaner"), StateFilter("*"))
@router.message(F.text == "🧹 Hisobni Tozalash", StateFilter("*"))
async def cmd_cleaner_menu(message: Message, state: FSMContext):
    """Telegram hisobini tozalash asosiy menyusi."""
    await state.clear()
    user_id = message.from_user.id
    is_conf = AccountCleanerService.is_configured()
    is_auth = await AccountCleanerService.is_authorized(user_id) if is_conf else False

    if not is_conf:
        text = (
            "🧹 <b>Telegram Hisobni Tozalash (Account Cleaner)</b>\n\n"
            "Ushbu funksiya sizning shaxsiy Telegram hisobingizdagi:\n"
            "• 🗑️ <b>O'chib ketgan hisoblar:</b> 'Deleted Account' bo'lib qolgan chatlarni tozalash\n"
            "• 🚪 <b>Faol bo'lmagan kanallar:</b> Ancha vaqt kirmagan/yopiq kanallardan chiqish (Leave)\n"
            "• ⏱️ <b>Eski dialoglar:</b> Belgilangan vaqtdan eski yozishmalarni o'chirish\n\n"
            "⚠️ <b>Ishlatish uchun:</b>\n"
            "Telegram API ma'lumotlarini (<code>TELEGRAM_API_ID</code> va <code>TELEGRAM_API_HASH</code>) "
            "to'g'ridan-to'g'ri botga kiritishingiz mumkin.\n"
            "Buning uchun quyidagi tugmani bosing:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=cleaner_config_keyboard())
        return

    if not is_auth:
        text = (
            "🧹 <b>Telegram Hisobni Tozalash (Account Cleaner)</b>\n\n"
            "Hisobingizni tozalash uchun avval Telegram akkauntingizni ulang.\n\n"
            "<i>Istalgan qulay usulni tanlang:</i>"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=cleaner_login_methods_keyboard())
        return

    profile = AccountCleanerService.get_cached_profile(user_id)
    user_str = ""
    if profile:
        name = escape_html(profile.get("name", "Foydalanuvchi"))
        uname = f" ({profile.get('username')})" if profile.get("username") else ""
        user_str = f"👤 <b>Ulangan hisob:</b> <b>{name}</b>{uname}\n🆔 <b>ID:</b> <code>{user_id}</code>\n\n"

    text = (
        f"🧹 <b>Telegram Hisobni Tozalash Markazi</b>\n\n"
        f"{user_str}"
        f"<i>Kerakli bo'limni tanlang:</i>\n"
        f"• <b>O'chgan hisoblar</b> — 'Deleted Account' bo'lib qolgan foydalanuvchilar bilan chatlarni tozalash;\n"
        f"• <b>Nofaol kanallar</b> — 60 kundan ortiq yangilik bo'lmagan kanal/guruhlardan chiqish;\n"
        f"• <b>Eski dialoglar</b> — 90 kundan eski yozishmalarni tozalash."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cleaner_main_keyboard(is_auth=True))


@router.callback_query(F.data == "cl_help_api")
async def cb_help_api(callback: CallbackQuery):
    """API olish yo'riqnomasini ko'rsatish."""
    text = (
        "📖 <b>Telegram API_ID va API_HASH olish (1 daqiqa):</b>\n\n"
        "1. Brauzerda <a href='https://my.telegram.org'>my.telegram.org</a> saytiga kiring;\n"
        "2. Telefon raqamingizni kiriting va Telegramga kelgan kodni yozing;\n"
        "3. <b>'API development tools'</b> bo'limiga kiring;\n"
        "4. Ixtiyoriy nom yozib (masalan: <code>CleanerApp</code>) tasdiqlang;\n"
        "5. Chiqqan <b>api_id</b> va <b>api_hash</b> ni nusxalab, botga <b>'⚙️ API_ID va HASH ni kiritish'</b> tugmasi orqali yuboring!"
    )
    await callback.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "cl_login_qr")
async def cb_login_qr(callback: CallbackQuery, state: FSMContext):
    """QR kod orqali tezkor kirish."""
    await state.clear()
    user_id = callback.from_user.id
    if not AccountCleanerService.is_configured():
        await callback.answer("Avval .env ga TELEGRAM_API_ID va TELEGRAM_API_HASH ni kiriting!", show_alert=True)
        return

    status_msg = await callback.message.answer("⏳ QR Kod yaratilmoqda...")
    await callback.answer()

    try:
        qr_obj, buf = await AccountCleanerService.create_qr_login(user_id)
        _ACTIVE_QR_LOGINS[user_id] = qr_obj

        caption = (
            "📷 <b>Telegram QR Kod orqali kirish:</b>\n\n"
            "1. Telefoningizda <b>Telegram</b> ilovasini oching;\n"
            "2. <b>Sozlamalar ➡️ Qurilmalar ➡️ Qurilmani ulash (Scan QR)</b> bo'limiga kiring;\n"
            "3. Kamerani ushbu QR kodga qarating!\n\n"
            "⏳ <i>QR kod 45 soniya davomida faol...</i>"
        )
        photo = BufferedInputFile(buf.getvalue(), filename="telegram_qr.png")
        qr_msg = await callback.message.answer_photo(photo, caption=caption, parse_mode="HTML")
        await status_msg.delete()

        # Orqa fonda QR skanerlanishini kutish
        async def _wait_qr():
            ok, res = await AccountCleanerService.wait_for_qr_login(user_id, qr_obj)
            if ok:
                await qr_msg.reply(
                    f"{res}\n\n🎉 <b>Hisobingiz muvaffaqiyatli ulandi!</b>",
                    reply_markup=cleaner_main_keyboard(is_auth=True),
                    parse_mode="HTML"
                )
            elif res == "2FA_REQUIRED":
                await state.set_state(CleanerStates.waiting_for_qr_2fa)
                await qr_msg.reply(
                    "🔒 <b>Akkauntingizda 2FA (ikki bosqichli parol) o'rnatilgan.</b>\n\n"
                    "Iltimos, 2FA parolingizni shu yerga yozib yuboring (Bekor qilish: /cancel):",
                    parse_mode="HTML"
                )
            elif res == "TIMEOUT":
                await qr_msg.reply(
                    "⌛ <b>QR kod muddati tugadi.</b>\nQaytadan QR olish uchun tugmani bosing:",
                    reply_markup=cleaner_login_methods_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await qr_msg.reply(f"❌ {res}", reply_markup=cleaner_login_methods_keyboard())

        asyncio.create_task(_wait_qr())

    except Exception as e:
        logger.error(f"QR kod yaratishda xatolik: {e}")
        await status_msg.edit_text(
            f"❌ <b>QR kod yaratishda xatolik:</b> {escape_html(str(e))}\n\n"
            "Iltimos, telefon raqam orqali kirishni sinab ko'ring.",
            reply_markup=cleaner_login_methods_keyboard(),
            parse_mode="HTML"
        )


@router.message(CleanerStates.waiting_for_qr_2fa)
async def handle_qr_2fa_input(message: Message, state: FSMContext):
    """QR login uchun 2FA parolini qabul qilish."""
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Kirish jarayoni bekor qilindi.")
        return

    password = message.text.strip()
    user_id = message.from_user.id
    qr_obj = _ACTIVE_QR_LOGINS.get(user_id)
    status_msg = await message.answer("⏳ 2FA paroli tekshirilmoqda...")

    ok, res = await AccountCleanerService.wait_for_qr_login(user_id, qr_obj, password=password)
    if ok:
        await state.clear()
        await status_msg.edit_text(
            f"{res}\n\n🎉 <b>Hisobingiz muvaffaqiyatli ulandi!</b>",
            reply_markup=cleaner_main_keyboard(is_auth=True),
            parse_mode="HTML"
        )
    else:
        await status_msg.edit_text(
            f"{res}\n\n<i>Qaytadan parolni kiriting yoki bekor qilish uchun /cancel yuboring:</i>",
            parse_mode="HTML"
        )


@router.callback_query(F.data.in_({"cl_start_login", "cl_login_phone"}))
async def cb_start_login(callback: CallbackQuery, state: FSMContext):
    """Telefon raqam orqali kirish jarayonini boshlash."""
    if not AccountCleanerService.is_configured():
        await callback.answer("Avval .env ga TELEGRAM_API_ID va TELEGRAM_API_HASH ni kiriting!", show_alert=True)
        return

    await state.set_state(CleanerStates.waiting_for_phone)
    await callback.answer()
    await callback.message.answer(
        "📱 <b>Telegram hisobingiz telefon raqamini xalqaro formatda yuboring:</b>\n"
        "Masalan: <code>+998901234567</code>\n\n"
        "<i>Bekor qilish uchun /cancel yuboring.</i>",
        parse_mode="HTML"
    )


@router.message(CleanerStates.waiting_for_phone)
async def handle_phone_input(message: Message, state: FSMContext):
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Kirish jarayoni bekor qilindi.")
        return

    phone = message.text.strip().replace(" ", "")
    user_id = message.from_user.id
    status_msg = await message.answer("⏳ Tasdiqlash kodi yuborilmoqda...")

    try:
        _, delivery_info = await AccountCleanerService.send_auth_code(user_id, phone)
        await state.update_data(phone=phone, pin_code="")
        await state.set_state(CleanerStates.waiting_for_code)
        await status_msg.edit_text(
            f"📱 <b>Raqam:</b> <code>{escape_html(phone)}</code>\n\n"
            f"{delivery_info}\n\n"
            f"🛡️ <b>Telegram Anti-Phishing himoyasi:</b>\n"
            f"<i>Kodni chatga yozmasdan, quyidagi tugmalar orqali bosing (shunda Telegram bloklamaydi):</i>",
            parse_mode="HTML",
            reply_markup=pinpad_keyboard("")
        )
    except Exception as e:
        logger.error(f"Kod yuborishda xatolik: {e}")
        await status_msg.edit_text(
            f"❌ <b>Kod yuborishda xatolik:</b> {escape_html(str(e))}\n\n"
            "Telefon raqamni to'g'ri kiritganingizni tekshiring.",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("cl_pin:"))
async def cb_pin_input(callback: CallbackQuery, state: FSMContext):
    """Telegram xavfsizlik filtri bloklamasligi uchun tugmalar orqali kod kiritish."""
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    current_code = data.get("pin_code", "")
    phone = data.get("phone", "")
    user_id = callback.from_user.id

    if action == "del":
        current_code = current_code[:-1]
        await state.update_data(pin_code=current_code)
        await callback.message.edit_reply_markup(reply_markup=pinpad_keyboard(current_code))
        await callback.answer()
        return

    elif action == "submit":
        if len(current_code) < 5:
            await callback.answer("Iltimos, 5 xonali kodni to'liq bosing!", show_alert=True)
            return
        code = current_code
    elif action.isdigit():
        if len(current_code) < 5:
            current_code += action
            await state.update_data(pin_code=current_code)

        if len(current_code) < 5:
            await callback.message.edit_reply_markup(reply_markup=pinpad_keyboard(current_code))
            await callback.answer()
            return
        code = current_code
    else:
        await callback.answer()
        return

    # 5 xonali kod to'lganda avtomatik kirish
    await callback.answer("Tekshirilmoqda...")
    await callback.message.edit_text("⏳ <b>Tasdiqlash kodi tekshirilmoqda...</b>", parse_mode="HTML")

    try:
        ok, res = await AccountCleanerService.complete_sign_in(user_id, phone, code)
        if not ok and res == "2FA_REQUIRED":
            await state.update_data(code=code)
            await state.set_state(CleanerStates.waiting_for_2fa)
            await callback.message.edit_text(
                "🔒 <b>Akkauntingizda 2FA (ikki bosqichli parol) o'rnatilgan.</b>\n\n"
                "Iltimos, 2FA parolingizni shu yerga yozib yuboring (Bekor qilish: /cancel):",
                parse_mode="HTML"
            )
            return

        if ok:
            await state.clear()
            profile = await AccountCleanerService.get_or_fetch_profile(user_id)
            name = escape_html(profile.get("name", "Foydalanuvchi")) if profile else "Foydalanuvchi"
            await callback.message.edit_text(
                f"{res}\n\n🎉 <b>Xush kelibsiz, {name}!</b>\nHisobingiz muvaffaqiyatli ulandi va doimiy saqlandi.",
                parse_mode="HTML",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
        else:
            await state.update_data(pin_code="")
            await callback.message.edit_text(
                f"{res}\n\n<i>Qaytadan kodni tugmalar orqali bosing:</i>",
                parse_mode="HTML",
                reply_markup=pinpad_keyboard("")
            )
    except Exception as e:
        logger.error(f"Pin tekshirishda xatolik: {e}")
        await state.update_data(pin_code="")
        await callback.message.edit_text(
            f"❌ <b>Xatolik:</b> {escape_html(str(e))}\n\n<i>Qaytadan urinib ko'ring:</i>",
            parse_mode="HTML",
            reply_markup=pinpad_keyboard("")
        )


@router.message(CleanerStates.waiting_for_code)
async def handle_code_input(message: Message, state: FSMContext):
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Kirish jarayoni bekor qilindi.")
        return

    # Telegram chat skaneri kodni ko'rib qolib bloklamasligi uchun xabarni chatdan o'chiramiz
    try:
        await message.delete()
    except Exception:
        pass

    code = message.text.strip().replace(" ", "").replace("-", "")
    user_id = message.from_user.id
    data = await state.get_data()
    phone = data.get("phone", "")

    status_msg = await message.answer("⏳ Kirish tekshirilmoqda...")

    try:
        ok, res = await AccountCleanerService.complete_sign_in(user_id, phone, code)
        if not ok and res == "2FA_REQUIRED":
            await state.update_data(code=code)
            await state.set_state(CleanerStates.waiting_for_2fa)
            await status_msg.edit_text(
                "🔒 <b>Ikki bosqichli autentifikatsiya (2FA) parolingizni kiriting:</b>\n\n"
                "<i>Bekor qilish uchun /cancel yuboring.</i>",
                parse_mode="HTML"
            )
            return

        if ok:
            await state.clear()
            profile = await AccountCleanerService.get_or_fetch_profile(user_id)
            name = escape_html(profile.get("name", "Foydalanuvchi")) if profile else "Foydalanuvchi"
            await status_msg.edit_text(
                f"{res}\n\n🎉 <b>Xush kelibsiz, {name}!</b>\nHisobingiz ulandi va doimiy saqlandi.",
                parse_mode="HTML",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
        else:
            await status_msg.edit_text(
                f"{res}\n\n<i>Iltimos, kodni quyidagi tugmalar orqali bosing:</i>",
                parse_mode="HTML",
                reply_markup=pinpad_keyboard("")
            )
    except Exception as e:
        logger.error(f"Kod tekshirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {escape_html(str(e))}")


@router.message(CleanerStates.waiting_for_2fa)
async def handle_2fa_input(message: Message, state: FSMContext):
    if message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Kirish jarayoni bekor qilindi.")
        return

    password = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    phone = data.get("phone", "")
    code = data.get("code", "")

    status_msg = await message.answer("⏳ 2FA parol tekshirilmoqda...")
    try:
        ok, res = await AccountCleanerService.complete_sign_in(user_id, phone, code, password=password)
        if ok:
            await state.clear()
            await status_msg.edit_text(
                f"{res}\n\n🎉 <b>Hisobingiz muvaffaqiyatli ulandi!</b>\nEndi hisobingizni tozalashingiz mumkin:",
                reply_markup=cleaner_main_keyboard(is_auth=True),
                parse_mode="HTML"
            )
        else:
            await status_msg.edit_text(
                f"{res}\n\n<i>Iltimos, 2FA parolingizni tekshirib qaytadan kiriting (Bekor qilish: /cancel):</i>",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"2FA tekshirishda xatolik: {e}")
        await status_msg.edit_text(
            f"❌ <b>2FA tekshirishda xatolik:</b> {escape_html(str(e))}\n\n<i>Qaytadan urinib ko'ring yoki /cancel bosing:</i>",
            parse_mode="HTML"
        )


# ==========================================
# 1. O'chib ketgan hisoblar (Deleted Accounts)
# ==========================================

@router.callback_query(F.data == "cl_scan_deleted")
@router.message(Command("clean_deleted"), StateFilter("*"))
async def scan_deleted_accounts_flow(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    target = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id

    if not AccountCleanerService.is_configured():
        await target.answer(
            "⚠️ <b>.env faylida TELEGRAM_API_ID va TELEGRAM_API_HASH kiritilmagan!</b>",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
        return

    if not await AccountCleanerService.is_authorized(user_id):
        await target.answer(
            "🔑 <b>Avval Telegram hisobingizga kirishingiz kerak:</b>",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
        return

    status_msg = await target.answer("🔍 Chatlar tekshirilmoqda ('Deleted Account' hisoblar qidirilmoqda)...")

    try:
        deleted = await AccountCleanerService.scan_deleted_accounts(user_id)
        if not deleted:
            await status_msg.edit_text(
                "✅ <b>Ajoyib!</b> Sizda birorta ham 'Deleted Account' chat topilmadi.",
                parse_mode="HTML",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
            return

        text = (
            f"🗑️ <b>O'chib ketgan hisoblar (Deleted Accounts)</b>\n\n"
            f"Jami topildi: <b>{len(deleted)}</b> ta o'chib ketgan akkaunt bilan yozishmalar.\n\n"
            f"Ularning barchasini tozalashni xohlaysizmi?"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_clean_keyboard("deleted", len(deleted)))
    except Exception as e:
        logger.error(f"Deleted accounts tekshirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Tekshirishda xatolik: {escape_html(str(e))}")


@router.callback_query(F.data == "cl_do_deleted")
async def do_delete_deleted_accounts(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer("Tozalanmoqda...")
    status_msg = await callback.message.edit_text("⏳ 'Deleted Account' chatlar o'chirilmoqda, kuting...")

    try:
        count = await AccountCleanerService.remove_deleted_accounts(user_id)
        await status_msg.edit_text(
            f"🎉 <b>Tozalash yakunlandi!</b>\n\n"
            f"Jami <b>{count}</b> ta 'Deleted Account' chatlari muvaffaqiyatli o'chirildi.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=True)
        )
    except Exception as e:
        logger.error(f"Deleted accounts o'chirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ O'chirishda xatolik: {escape_html(str(e))}")


# ==========================================
# 2. Faol bo'lmagan kanallar va guruhlar
# ==========================================

@router.callback_query(F.data == "cl_scan_channels")
@router.message(Command("clean_channels"), StateFilter("*"))
async def scan_inactive_channels_flow(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    target = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id

    if not AccountCleanerService.is_configured():
        await target.answer(
            "⚠️ <b>.env faylida TELEGRAM_API_ID va TELEGRAM_API_HASH kiritilmagan!</b>",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
        return

    if not await AccountCleanerService.is_authorized(user_id):
        await target.answer(
            "🔑 <b>Avval Telegram hisobingizga kirishingiz kerak:</b>",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
        return

    # Foydalanuvchi /clean_channels 30 deb yozsa kunni olish
    days = 60
    if isinstance(event, Message) and event.text:
        parts = event.text.strip().split()
        if len(parts) > 1 and parts[1].isdigit():
            days = max(1, int(parts[1]))

    status_msg = await target.answer(f"🔍 Kanallar va guruhlar tekshirilmoqda ({days} kundan ortiq nofaol)...")

    try:
        channels = await AccountCleanerService.scan_inactive_channels(user_id, days=days)
        if not channels:
            await status_msg.edit_text(
                f"✅ <b>Oxirgi {days} kunda nofaol kanallar topilmadi!</b>",
                parse_mode="HTML",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
            return

        chat_id = target.chat.id
        _SCANNED_CHANNELS[chat_id] = [c["id"] for c in channels]

        list_preview = ""
        for c in channels[:10]:
            list_preview += f"• {escape_html(c['title'])} (oxirgi faollik: {c['days_ago']} kun oldin)\n"

        if len(channels) > 10:
            list_preview += f"... va yana {len(channels) - 10} ta kanal.\n"

        text = (
            f"🚪 <b>Faol bo'lmagan kanallar va guruhlar:</b>\n\n"
            f"Jami topildi: <b>{len(channels)}</b> ta ({days}+ kun faol bo'lmagan)\n\n"
            f"{list_preview}\n"
            f"Ushbu barcha kanallardan chiqib ketishni (Leave) xohlaysizmi?"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_clean_keyboard("channels", len(channels)))
    except Exception as e:
        logger.error(f"Kanallarni tekshirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Tekshirishda xatolik: {escape_html(str(e))}")


@router.callback_query(F.data == "cl_do_channels")
async def do_leave_inactive_channels(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    ch_ids = _SCANNED_CHANNELS.get(chat_id, [])

    if not ch_ids:
        await callback.answer("Nofaol kanallar ro'yxati topilmadi, qaytadan skaner qiling.", show_alert=True)
        return

    await callback.answer("Kanallardan chiqilmoqda...")
    status_msg = await callback.message.edit_text(f"⏳ {len(ch_ids)} ta kanaldan chiqilmoqda, biroz kuting...")

    try:
        count = await AccountCleanerService.leave_inactive_channels(user_id, ch_ids)
        _SCANNED_CHANNELS.pop(chat_id, None)
        await status_msg.edit_text(
            f"🎉 <b>Muvaffaqiyatli!</b>\n\n"
            f"Jami <b>{count}</b> ta faol bo'lmagan kanal va guruhlardan chiqib ketildi.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=True)
        )
    except Exception as e:
        logger.error(f"Kanallardan chiqishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {escape_html(str(e))}")


# ==========================================
# 3. Eski dialoglar (Old Chats / clean_old)
# ==========================================

@router.callback_query(F.data == "cl_scan_old")
@router.message(Command("clean_old"), StateFilter("*"))
async def scan_old_dialogs_flow(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    target = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id

    if not AccountCleanerService.is_configured():
        await target.answer(
            "⚠️ <b>.env faylida TELEGRAM_API_ID va TELEGRAM_API_HASH kiritilmagan!</b>\n"
            "Iltimos, avval API kalitlarini sozlang.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
        return

    if not await AccountCleanerService.is_authorized(user_id):
        await target.answer(
            "🔑 <b>Avval Telegram hisobingizga kirishingiz kerak:</b>\n"
            "Quyidagi tugma orqali login qiling.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
        return

    # Foydalanuvchi /clean_old 30 yoki /clean_old 60 yozsa kunni olish (standart: 90 kun)
    days = 90
    if isinstance(event, Message) and event.text:
        parts = event.text.strip().split()
        if len(parts) > 1 and parts[1].isdigit():
            days = max(1, int(parts[1]))

    status_msg = await target.answer(f"🔍 Eski yozishmalar qidirilmoqda ({days} kundan ortiq xabar yozilmagan)...")

    try:
        old_dialogs = await AccountCleanerService.scan_old_dialogs(user_id, days=days)
        if not old_dialogs:
            await status_msg.edit_text(
                f"✅ <b>{days} kundan eski bo'lgan keraksiz dialoglar topilmadi.</b>",
                parse_mode="HTML",
                reply_markup=cleaner_main_keyboard(is_auth=True)
            )
            return

        chat_id = target.chat.id
        _SCANNED_OLD_DIALOGS[chat_id] = [d["id"] for d in old_dialogs]

        list_preview = ""
        for d in old_dialogs[:10]:
            list_preview += f"• {escape_html(d['title'])} ({d['days_ago']} kun oldin)\n"

        if len(old_dialogs) > 10:
            list_preview += f"... va yana {len(old_dialogs) - 10} ta dialog.\n"

        text = (
            f"⏱️ <b>Eski Dialoglar ({days}+ kun oldingi):</b>\n\n"
            f"Jami topildi: <b>{len(old_dialogs)}</b> ta yozishma.\n\n"
            f"{list_preview}\n"
            f"<i>(Eslatma: 'Saqlangan xabarlar' va qadalgan chatlarga tegilmaydi)</i>\n\n"
            f"Ushbu eski dialoglarni tozalashni xohlaysizmi?"
        )
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=confirm_clean_keyboard("old", len(old_dialogs)))
    except Exception as e:
        logger.error(f"Eski dialoglarni tekshirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Tekshirishda xatolik: {escape_html(str(e))}")


@router.callback_query(F.data == "cl_do_old")
async def do_delete_old_dialogs(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    d_ids = _SCANNED_OLD_DIALOGS.get(chat_id, [])

    if not d_ids:
        await callback.answer("Dialoglar ro'yxati topilmadi, qaytadan skaner qiling.", show_alert=True)
        return

    await callback.answer("Dialoglar tozalanmoqda...")
    status_msg = await callback.message.edit_text(f"⏳ {len(d_ids)} ta eski dialog o'chirilmoqda...")

    try:
        count = await AccountCleanerService.delete_old_dialogs(user_id, d_ids)
        _SCANNED_OLD_DIALOGS.pop(chat_id, None)
        await status_msg.edit_text(
            f"🎉 <b>Muvaffaqiyatli tozalandi!</b>\n\n"
            f"Jami <b>{count}</b> ta eski dialog o'chirildi.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=True)
        )
    except Exception as e:
        logger.error(f"Eski dialoglarni o'chirishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Xatolik: {escape_html(str(e))}")


# ==========================================
# 4. Sessiyadan chiqish (Logout)
# ==========================================

@router.callback_query(F.data == "cl_logout")
@router.message(Command("cleaner_logout"), StateFilter("*"))
async def cb_cleaner_logout(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    target = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id

    ok = await AccountCleanerService.logout(user_id)
    if isinstance(event, CallbackQuery):
        await event.answer("Hisobdan chiqildi")

    if ok:
        await target.answer(
            "🚪 <b>Telegram hisobingizdan muvaffaqiyatli chiqildi.</b>\n\n"
            "Sessiya fayllari o'chirildi. Qaytadan ishlatish uchun yana login qilishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )
    else:
        await target.answer(
            "⚠️ Chiqishda xatolik yuz berdi yoki sessiya allaqachon tozalangan.",
            reply_markup=cleaner_main_keyboard(is_auth=False)
        )


@router.callback_query(F.data == "cl_cancel")
async def cb_cancel_cleaner(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    is_auth = await AccountCleanerService.is_authorized(user_id)
    await callback.answer("Amal bekor qilindi")
    await callback.message.edit_text("❌ Tozalash bekor qilindi.", reply_markup=cleaner_main_keyboard(is_auth=is_auth))


@router.callback_query(F.data == "cl_refresh")
async def cb_refresh_cleaner(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    await callback.answer("Yangilandi")
    is_auth = await AccountCleanerService.is_authorized(user_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=cleaner_main_keyboard(is_auth=is_auth))
    except Exception:
        pass

