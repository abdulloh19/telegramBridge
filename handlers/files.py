import os
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import get_user_cwd, set_user_cwd
from services.file_service import FileService
from keyboards.inline import (
    file_browser_keyboard,
    file_actions_keyboard,
    confirm_delete_keyboard,
    get_path_token,
    get_path_from_token
)
from utils.helpers import escape_html, split_text_chunks, format_bytes
from utils.logger import logger

router = Router()


class FileStates(StatesGroup):
    waiting_for_edit_content = State()
    waiting_for_new_file_name = State()
    waiting_for_new_file_content = State()
    waiting_for_new_dir_name = State()
    waiting_for_search_query = State()


@router.message(Command("ls"), StateFilter("*"))
@router.message(Command("files"), StateFilter("*"))
@router.message(F.text == "📁 Fayllar", StateFilter("*"))
async def show_file_browser(message: Message, state: FSMContext):
    """Fayllar brauzerini ochish."""
    await state.clear()
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)

    try:
        items = FileService.list_directory(cwd)
        text = (
            f"📁 <b>Fayllar Menejeri</b>\n"
            f"📍 <b>Joriy papka:</b> <code>{escape_html(str(cwd))}</code>\n"
            f"📊 Jami elementlar: <b>{len(items)}</b> ta\n\n"
            f"<i>Kerakli fayl yoki papkani tanlang:</i>"
        )
        kb = file_browser_keyboard(cwd, items, page=0)
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await message.answer(f"❌ Papkani ochishda xatolik: {str(e)}")


@router.message(Command("cd"))
async def cmd_cd(message: Message):
    """Ishchi papkani o'zgartirish."""
    user_id = message.from_user.id
    current_cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            f"📍 <b>Joriy papka:</b> <code>{escape_html(str(current_cwd))}</code>\n\n"
            f"Foydalanish: <code>/cd &lt;papka_yo'li&gt;</code>\n"
            f"Masalan: <code>/cd ..</code> yoki <code>/cd src</code>",
            parse_mode="HTML"
        )
        return

    target_input = args[1].strip()
    try:
        target_path = FileService.resolve_path(current_cwd, target_input)
        new_cwd = set_user_cwd(user_id, target_path)
        items = FileService.list_directory(new_cwd)
        kb = file_browser_keyboard(new_cwd, items, page=0)
        await message.answer(
            f"✅ <b>Yangi ishchi papkaga o'tildi:</b>\n<code>{escape_html(str(new_cwd))}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"❌ Papkaga o'tib bo'lmadi: {str(e)}")


@router.message(Command("view"))
@router.message(Command("cat"))
async def cmd_view_file(message: Message):
    """Fayl kodini ko'rish buyrug'i."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Foydalanish: <code>/view &lt;fayl_nomi&gt;</code>", parse_mode="HTML")
        return

    file_path = FileService.resolve_path(cwd, args[1].strip())
    await _send_file_view(message, file_path)


async def _send_file_view(target_msg: Message, file_path: Path):
    """Fayl mazmunini chiroyli syntax formatda yuborish yordamchisi."""
    try:
        content, is_truncated = await FileService.read_file(file_path, max_length=15000)
        ext = file_path.suffix.lstrip(".").lower() or "txt"
        token = get_path_token(file_path)

        if len(content) <= 3500 and not is_truncated:
            msg_text = (
                f"📄 <b>Fayl:</b> <code>{escape_html(file_path.name)}</code>\n"
                f"📍 <code>{escape_html(str(file_path))}</code>\n\n"
                f"<pre><code class=\"language-{ext}\">{escape_html(content)}</code></pre>"
            )
            await target_msg.answer(msg_text, parse_mode="HTML", reply_markup=file_actions_keyboard(file_path))
        else:
            # Fayl katta bo'lsa qismini ko'rsatib, to'liq faylni hujjat qilib yuborish
            preview = content[:2500]
            msg_text = (
                f"📄 <b>Fayl:</b> <code>{escape_html(file_path.name)}</code> (Katta fayl)\n"
                f"📍 <code>{escape_html(str(file_path))}</code>\n\n"
                f"<b>Boshlang'ich qismi:</b>\n"
                f"<pre><code class=\"language-{ext}\">{escape_html(preview)}</code></pre>\n"
                f"<i>Fayl hajmi katta bo'lgani uchun to'liq versiya pastda hujjat sifatida yuborilmoqda.</i>"
            )
            await target_msg.answer(msg_text, parse_mode="HTML", reply_markup=file_actions_keyboard(file_path))
            # Hujjat sifatida yuborish
            doc_file = FSInputFile(str(file_path))
            await target_msg.answer_document(doc_file, caption=f"📥 {file_path.name} ({format_bytes(file_path.stat().st_size)})")

    except Exception as e:
        await target_msg.answer(f"❌ Faylni o'qishda xatolik: {str(e)}")


@router.message(Command("download"))
async def cmd_download_file(message: Message):
    """Faylni Telegram orqali yuklab olish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Foydalanish: <code>/download &lt;fayl_nomi&gt;</code>", parse_mode="HTML")
        return

    file_path = FileService.resolve_path(cwd, args[1].strip())
    if not file_path.exists() or not file_path.is_file():
        await message.answer("❌ Fayl topilmadi!")
        return

    try:
        doc = FSInputFile(str(file_path))
        await message.answer_document(doc, caption=f"📥 {file_path.name} ({format_bytes(file_path.stat().st_size)})")
    except Exception as e:
        await message.answer(f"❌ Faylni yuborishda xatolik: {str(e)}")


@router.message(Command("create"))
async def cmd_create_file(message: Message, state: FSMContext):
    """Yangi fayl yaratish buyrug'i."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await state.update_data(target_dir=str(cwd))
        await state.set_state(FileStates.waiting_for_new_file_name)
        await message.answer("✍️ Yaratmoqchi bo'lgan faylingiz nomini kiriting (masalan: <code>main.py</code> yoki <code>utils/auth.js</code>):", parse_mode="HTML")
        return

    file_name = args[1].strip()
    target_file = FileService.resolve_path(cwd, file_name)
    await state.update_data(target_file=str(target_file))
    await state.set_state(FileStates.waiting_for_new_file_content)
    await message.answer(f"📝 <code>{escape_html(target_file.name)}</code> uchun boshlang'ich kod/matnni yuboring (yoki bo'sh fayl uchun <code>-</code> yuboring):", parse_mode="HTML")


@router.message(Command("mkdir"))
async def cmd_mkdir(message: Message):
    """Yangi papka yaratish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Foydalanish: <code>/mkdir &lt;papka_nomi&gt;</code>", parse_mode="HTML")
        return

    dir_name = args[1].strip()
    try:
        new_dir = FileService.resolve_path(cwd, dir_name)
        FileService.create_directory(new_dir)
        await message.answer(f"✅ Yangi papka yaratildi: <code>{escape_html(str(new_dir))}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Papka yaratishda xatolik: {str(e)}")


@router.message(Command("rm"))
async def cmd_rm(message: Message):
    """Fayl yoki papkani o'chirish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Foydalanish: <code>/rm &lt;fayl_yoki_papka&gt;</code>", parse_mode="HTML")
        return

    target = FileService.resolve_path(cwd, args[1].strip())
    if not target.exists():
        await message.answer("❌ O'chiriladigan element topilmadi!")
        return

    kb = confirm_delete_keyboard(target)
    await message.answer(
        f"⚠️ <b>Haqiqatdan ham ushbu {('papkani' if target.is_dir() else 'faylni')} o'chirmoqchimisiz?</b>\n\n"
        f"📍 <code>{escape_html(str(target))}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    """Loyiha ichidan matn yoki kod qidirish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await state.update_data(search_dir=str(cwd))
        await state.set_state(FileStates.waiting_for_search_query)
        await message.answer("🔍 Qidirmoqchi bo'lgan so'z, funksiya yoki kod parchasini kiriting:")
        return

    query = args[1].strip()
    await _perform_search(message, cwd, query)


async def _perform_search(message: Message, search_dir: Path, query: str):
    matches = FileService.search_code(query, search_dir)
    if not matches:
        await message.answer(f"🔍 '<code>{escape_html(query)}</code>' bo'yicha hech narsa topilmadi.", parse_mode="HTML")
        return

    text_lines = [f"🔍 <b>Qidiruv natijalari:</b> '<code>{escape_html(query)}</code>'\nTopildi: {len(matches)} ta\n"]
    for m in matches[:15]:
        text_lines.append(f"📄 <b>{escape_html(m['file'])}</b> (qator {m['line']}):\n<code>{escape_html(m['content'])}</code>\n")

    await message.answer("\n".join(text_lines), parse_mode="HTML")


# ==========================================
# Callback Handlers (Inline Buttons)
# ==========================================

@router.callback_query(F.data.startswith("dir:"))
async def cb_open_dir(callback: CallbackQuery):
    """Papkani ochish va uning tarkibini ko'rsatish."""
    token = callback.data.split(":", 1)[1]
    target_dir = get_path_from_token(token)

    if not target_dir or not target_dir.exists():
        await callback.answer("❌ Papka topilmadi!", show_alert=True)
        return

    set_user_cwd(callback.from_user.id, target_dir)
    try:
        items = FileService.list_directory(target_dir)
        text = (
            f"📁 <b>Fayllar Menejeri</b>\n"
            f"📍 <b>Joriy papka:</b> <code>{escape_html(str(target_dir))}</code>\n"
            f"📊 Jami elementlar: <b>{len(items)}</b> ta\n\n"
            f"<i>Kerakli fayl yoki papkani tanlang:</i>"
        )
        kb = file_browser_keyboard(target_dir, items, page=0)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await callback.answer()
    except Exception as e:
        await callback.answer(f"Xatolik: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("page:"))
async def cb_paginate_dir(callback: CallbackQuery):
    """Fayllar sahifasini almashtirish."""
    parts = callback.data.split(":")
    token = parts[1]
    page = int(parts[2])
    target_dir = get_path_from_token(token)

    if not target_dir or not target_dir.exists():
        await callback.answer("❌ Papka topilmadi!", show_alert=True)
        return

    items = FileService.list_directory(target_dir)
    text = (
        f"📁 <b>Fayllar Menejeri</b>\n"
        f"📍 <b>Joriy papka:</b> <code>{escape_html(str(target_dir))}</code>\n"
        f"📊 Jami elementlar: <b>{len(items)}</b> ta\n\n"
        f"<i>Kerakli fayl yoki papkani tanlang:</i>"
    )
    kb = file_browser_keyboard(target_dir, items, page=page)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("file:"))
async def cb_open_file_menu(callback: CallbackQuery):
    """Fayl tanlanganda uning amallar menyusini ko'rsatish."""
    token = callback.data.split(":", 1)[1]
    target_file = get_path_from_token(token)

    if not target_file or not target_file.exists():
        await callback.answer("❌ Fayl topilmadi!", show_alert=True)
        return

    stat = target_file.stat()
    text = (
        f"📄 <b>Fayl ma'lumotlari:</b>\n\n"
        f"📌 <b>Nomi:</b> <code>{escape_html(target_file.name)}</code>\n"
        f"📍 <b>Yo'li:</b> <code>{escape_html(str(target_file))}</code>\n"
        f"💾 <b>Hajmi:</b> {format_bytes(stat.st_size)}\n\n"
        f"<i>Ushbu fayl bilan nima qilmoqchisiz?</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=file_actions_keyboard(target_file))
    await callback.answer()


@router.callback_query(F.data.startswith("view:"))
async def cb_view_file(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    target_file = get_path_from_token(token)
    if not target_file or not target_file.exists():
        await callback.answer("❌ Fayl topilmadi!", show_alert=True)
        return

    await callback.answer()
    await _send_file_view(callback.message, target_file)


@router.callback_query(F.data.startswith("down:"))
async def cb_download_file(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    target_file = get_path_from_token(token)
    if not target_file or not target_file.exists():
        await callback.answer("❌ Fayl topilmadi!", show_alert=True)
        return

    await callback.answer("Yuklanmoqda...")
    doc = FSInputFile(str(target_file))
    await callback.message.answer_document(doc, caption=f"📥 {target_file.name} ({format_bytes(target_file.stat().st_size)})")


@router.callback_query(F.data.startswith("delreq:"))
async def cb_delete_request(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    target = get_path_from_token(token)
    if not target or not target.exists():
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    kb = confirm_delete_keyboard(target)
    await callback.message.edit_text(
        f"⚠️ <b>Haqiqatdan ham ushbu elementni o'chirmoqchimisiz?</b>\n\n"
        f"📍 <code>{escape_html(str(target))}</code>",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delyes:"))
async def cb_delete_confirm(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    target = get_path_from_token(token)
    if not target or not target.exists():
        await callback.answer("❌ Topilmadi!", show_alert=True)
        return

    parent_dir = target.parent
    try:
        res = FileService.delete_item(target)
        await callback.answer(f"✅ {res}", show_alert=True)
        # Ota papkaga qaytish
        items = FileService.list_directory(parent_dir)
        kb = file_browser_keyboard(parent_dir, items, page=0)
        await callback.message.edit_text(
            f"🗑️ <b>Element o'chirildi.</b>\n📍 Joriy papka: <code>{escape_html(str(parent_dir))}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        await callback.answer(f"❌ O'chirishda xatolik: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("edit:"))
async def cb_start_edit_file(callback: CallbackQuery, state: FSMContext):
    token = callback.data.split(":", 1)[1]
    target_file = get_path_from_token(token)
    if not target_file or not target_file.exists():
        await callback.answer("❌ Fayl topilmadi!", show_alert=True)
        return

    await state.update_data(target_file=str(target_file))
    await state.set_state(FileStates.waiting_for_edit_content)
    await callback.answer()
    await callback.message.answer(
        f"✏️ <b>Faylni tahrirlash:</b> <code>{escape_html(target_file.name)}</code>\n\n"
        f"Ushbu faylga yozmoqchi bo'lgan <b>yangi to'liq kodni</b> xabar sifatida yuboring.\n"
        f"<i>Bekor qilish uchun /cancel yuboring.</i>",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("newf:"))
async def cb_new_file_prompt(callback: CallbackQuery, state: FSMContext):
    token = callback.data.split(":", 1)[1]
    target_dir = get_path_from_token(token)
    if not target_dir or not target_dir.exists():
        await callback.answer("❌ Papka topilmadi!", show_alert=True)
        return

    await state.update_data(target_dir=str(target_dir))
    await state.set_state(FileStates.waiting_for_new_file_name)
    await callback.answer()
    await callback.message.answer(
        f"➕ <b>Yangi fayl yaratish</b>\n"
        f"📍 Papka: <code>{escape_html(str(target_dir))}</code>\n\n"
        f"Yaratiladigan fayl nomini kiriting (masalan: <code>app.py</code>):",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("newd:"))
async def cb_new_dir_prompt(callback: CallbackQuery, state: FSMContext):
    token = callback.data.split(":", 1)[1]
    target_dir = get_path_from_token(token)
    if not target_dir or not target_dir.exists():
        await callback.answer("❌ Papka topilmadi!", show_alert=True)
        return

    await state.update_data(target_dir=str(target_dir))
    await state.set_state(FileStates.waiting_for_new_dir_name)
    await callback.answer()
    await callback.message.answer(
        f"📁 <b>Yangi papka ochish</b>\n"
        f"📍 Papka: <code>{escape_html(str(target_dir))}</code>\n\n"
        f"Yangi papka nomini kiriting:",
        parse_mode="HTML"
    )


# ==========================================
# FSM State Handlers (Fayl yaratish/tahrirlash)
# ==========================================

@router.message(Command("cancel"))
async def cmd_cancel_state(message: Message, state: FSMContext):
    """Amalni bekor qilish."""
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.")


@router.message(FileStates.waiting_for_edit_content)
async def handle_file_edit_content(message: Message, state: FSMContext):
    """Faylga yangi kod yozish."""
    data = await state.get_data()
    file_path_str = data.get("target_file")
    await state.clear()

    if not file_path_str:
        await message.answer("❌ Tahrirlanadigan fayl aniqlanmadi.")
        return

    file_path = Path(file_path_str)
    new_content = message.text or ""

    try:
        bytes_written = await FileService.write_file(file_path, new_content, overwrite=True)
        await message.answer(
            f"✅ <b>Fayl muvaffaqiyatli saqlandi!</b>\n"
            f"📄 Fayl: <code>{escape_html(file_path.name)}</code>\n"
            f"💾 Yangi hajm: {format_bytes(bytes_written)}",
            parse_mode="HTML",
            reply_markup=file_actions_keyboard(file_path)
        )
    except Exception as e:
        await message.answer(f"❌ Faylni saqlashda xatolik: {str(e)}")


@router.message(FileStates.waiting_for_new_file_name)
async def handle_new_file_name(message: Message, state: FSMContext):
    data = await state.get_data()
    dir_path_str = data.get("target_dir")
    file_name = message.text.strip()

    if not dir_path_str:
        await state.clear()
        await message.answer("❌ Papka aniqlanmadi.")
        return

    target_file = Path(dir_path_str) / file_name
    await state.update_data(target_file=str(target_file))
    await state.set_state(FileStates.waiting_for_new_file_content)
    await message.answer(
        f"📝 <code>{escape_html(file_name)}</code> uchun boshlang'ich kod yoki matnni yuboring "
        f"(yoki bo'sh fayl yaratish uchun <code>-</code> yuboring):",
        parse_mode="HTML"
    )


@router.message(FileStates.waiting_for_new_file_content)
async def handle_new_file_content(message: Message, state: FSMContext):
    data = await state.get_data()
    file_path_str = data.get("target_file")
    await state.clear()

    if not file_path_str:
        await message.answer("❌ Fayl yo'li topilmadi.")
        return

    file_path = Path(file_path_str)
    content = "" if message.text.strip() == "-" else (message.text or "")

    try:
        await FileService.write_file(file_path, content, overwrite=True)
        await message.answer(
            f"✅ <b>Yangi fayl yaratildi!</b>\n"
            f"📄 <code>{escape_html(file_path.name)}</code>",
            parse_mode="HTML",
            reply_markup=file_actions_keyboard(file_path)
        )
    except Exception as e:
        await message.answer(f"❌ Fayl yaratishda xatolik: {str(e)}")


@router.message(FileStates.waiting_for_new_dir_name)
async def handle_new_dir_name(message: Message, state: FSMContext):
    data = await state.get_data()
    dir_path_str = data.get("target_dir")
    dir_name = message.text.strip()
    await state.clear()

    if not dir_path_str:
        await message.answer("❌ Papka aniqlanmadi.")
        return

    new_dir = Path(dir_path_str) / dir_name
    try:
        FileService.create_directory(new_dir)
        items = FileService.list_directory(new_dir.parent)
        kb = file_browser_keyboard(new_dir.parent, items, page=0)
        await message.answer(
            f"✅ <b>Yangi papka ochildi:</b> <code>{escape_html(dir_name)}</code>",
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"❌ Papka ochishda xatolik: {str(e)}")


@router.message(FileStates.waiting_for_search_query)
async def handle_search_query_state(message: Message, state: FSMContext):
    data = await state.get_data()
    search_dir_str = data.get("search_dir")
    await state.clear()

    search_dir = Path(search_dir_str) if search_dir_str else get_user_cwd(message.from_user.id)
    await _perform_search(message, search_dir, message.text.strip())


# ==========================================
# Telegram orqali Fayl Yuklash (Upload File)
# ==========================================

@router.message(F.document)
async def handle_document_upload(message: Message, bot: Bot):
    """Telegramdan yuborilgan faylni kompyuterdagi joriy ishchi papkaga saqlash."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    document = message.document

    file_name = document.file_name or f"upload_{document.file_id[:8]}"
    save_path = cwd / file_name

    status_msg = await message.answer(f"⏳ Fayl yuklanmoqda: <code>{escape_html(file_name)}</code>...", parse_mode="HTML")

    try:
        file_info = await bot.get_file(document.file_id)
        await bot.download_file(file_info.file_path, destination=save_path)
        await status_msg.edit_text(
            f"✅ <b>Fayl kompyuterga saqlandi!</b>\n\n"
            f"📄 <b>Nomi:</b> <code>{escape_html(file_name)}</code>\n"
            f"📍 <b>Manzil:</b> <code>{escape_html(str(save_path))}</code>\n"
            f"💾 <b>Hajmi:</b> {format_bytes(document.file_size or 0)}",
            parse_mode="HTML",
            reply_markup=file_actions_keyboard(save_path)
        )
    except Exception as e:
        logger.error(f"Faylni yuklab olishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Faylni saqlashda xatolik yuz berdi: {str(e)}")
