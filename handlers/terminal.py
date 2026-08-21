import io
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import get_user_cwd, set_user_cwd, SHELL_TYPE
from services.terminal_service import TerminalService
from services.file_service import FileService
from keyboards.inline import quick_terminal_keyboard
from utils.helpers import escape_html, truncate_text
from utils.logger import logger

router = Router()


class TerminalStates(StatesGroup):
    waiting_for_command = State()


# Bosh menyu tugmalari ro'yxati (terminal holatidan chiqish uchun)
MAIN_MENU_BUTTONS = {
    "📁 Fayllar",
    "🤖 AI Agent",
    "📊 Tizim Holati",
    "📸 Skrinshot",
    "🧹 Hisobni Tozalash",
    "⚡ Git Status",
    "⚙️ Sozlamalar / Yordam",
}


@router.message(Command("sh"), StateFilter("*"))
@router.message(Command("cmd"), StateFilter("*"))
@router.message(Command("ps"), StateFilter("*"))
async def cmd_run_shell(message: Message, state: FSMContext):
    """Terminal buyrug'ini bajarish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await state.clear()
        await message.answer(
            f"💻 <b>Terminal Buyruqlari</b>\n\n"
            f"Foydalanish: <code>/sh &lt;buyruq&gt;</code>\n"
            f"Masalan:\n"
            f"• <code>/sh git status</code>\n"
            f"• <code>/sh pip list</code>\n"
            f"• <code>/sh python main.py</code>\n"
            f"• <code>/sh dir</code> yoki <code>/sh ls</code>\n"
            f"• <code>/sh cd ..</code>\n\n"
            f"📍 <b>Joriy papka:</b> <code>{escape_html(str(cwd))}</code>",
            parse_mode="HTML",
            reply_markup=quick_terminal_keyboard()
        )
        return

    command = args[1].strip()
    await _execute_and_send_result(message, command, user_id)


@router.message(Command("terminal"), StateFilter("*"))
@router.message(F.text == "💻 Terminal", StateFilter("*"))
async def btn_terminal_menu(message: Message, state: FSMContext):
    """Interaktiv terminal rejimi."""
    await state.clear()
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)

    await state.set_state(TerminalStates.waiting_for_command)

    text = (
        f"💻 <b>Interaktiv Masofaviy Terminal ({SHELL_TYPE.upper()})</b>\n\n"
        f"📍 <b>Joriy katalog:</b> <code>{escape_html(str(cwd))}</code>\n\n"
        f"⚡ <b>Terminal rejimi faol!</b> Endi istalgan buyruqni to'g'ridan-to'g'ri yozib yuborishingiz mumkin "
        f"(masalan: <code>dir</code>, <code>git status</code>, <code>pip list</code>, <code>cd ..</code>, <code>python -V</code>).\n\n"
        f"<i>(Chiqish uchun: /cancel yuboring yoki boshqa menyu tugmasini bosing)</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=quick_terminal_keyboard())


@router.message(TerminalStates.waiting_for_command)
async def handle_interactive_terminal_input(message: Message, state: FSMContext):
    """Terminal holatida yuborilgan buyruqlarni qabul qilish."""
    text = message.text.strip() if message.text else ""

    # Chiqish yoki menyu tugmalari bosilgan bo'lsa
    if text.startswith("/cancel") or text.startswith("/start") or text in MAIN_MENU_BUTTONS:
        await state.clear()
        if text.startswith("/cancel"):
            await message.answer("❌ Terminal rejimidan chiqildi.")
        return

    user_id = message.from_user.id

    # Agar /sh, /cmd, /ps bilan yozilgan bo'lsa old qismini olib tashlash
    command = text
    for prefix in ("/sh ", "/cmd ", "/ps "):
        if command.lower().startswith(prefix):
            command = command[len(prefix):].strip()
            break

    if not command:
        return

    await _execute_and_send_result(message, command, user_id)


@router.message(F.text == "⚡ Git Status", StateFilter("*"))
async def btn_git_status(message: Message, state: FSMContext):
    """Git status tezkor tugmasi."""
    await state.clear()
    user_id = message.from_user.id
    await _execute_and_send_result(message, "git status", user_id)


@router.callback_query(F.data.startswith("term:"))
async def cb_quick_terminal(callback: CallbackQuery):
    """Tezkor inline terminal tugmalari."""
    command = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    await callback.answer(f"{command} bajarilmoqda...")
    await _execute_and_send_result(callback.message, command, user_id)


@router.callback_query(F.data == "term_tree")
async def cb_terminal_tree(callback: CallbackQuery):
    """Papka daraxtini ko'rsatish."""
    user_id = callback.from_user.id
    cwd = get_user_cwd(user_id)

    await callback.answer()
    tree = FileService.get_tree_structure(cwd, max_depth=2)
    if not tree:
        tree = "(Papka bo'sh)"

    text = (
        f"🌳 <b>Papka Tuzilmasi:</b>\n"
        f"📍 <code>{escape_html(str(cwd))}</code>\n\n"
        f"<pre>{escape_html(tree)}</pre>"
    )
    try:
        await callback.message.answer(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(f"🌳 Papka Tuzilmasi:\n{tree}")


async def _execute_and_send_result(target_msg: Message, command: str, user_id: int):
    """Terminal buyrug'ini bajarib, natijani formatlab yuboruvchi yordamchi funksiya."""
    cwd = get_user_cwd(user_id)
    status_msg = await target_msg.answer(
        f"⏳ <b>Bajarilmoqda:</b> <code>{escape_html(command)}</code>\n"
        f"📍 <i>{escape_html(str(cwd))}</i>",
        parse_mode="HTML"
    )

    result = await TerminalService.execute_command(command, cwd=cwd)

    # Agar 'cd' buyrug'i orqali papka o'zgargan bo'lsa
    if result.get("changed_dir"):
        try:
            cwd = set_user_cwd(user_id, result["changed_dir"])
        except Exception:
            pass

    exit_code = result["exit_code"]
    duration = result["duration"]
    stdout = result["stdout"].strip()
    stderr = result["stderr"].strip()

    status_icon = "✅" if exit_code == 0 else "❌"
    header = (
        f"{status_icon} <b>Buyruq:</b> <code>{escape_html(command)}</code>\n"
        f"⏱️ Vaqt: <b>{duration}s</b> | Kod: <b>{exit_code}</b>\n"
        f"📍 <code>{escape_html(str(cwd))}</code>\n\n"
    )

    # Chiqish matnini yig'ish
    combined_output = ""
    if stdout:
        combined_output += stdout
    if stderr:
        if combined_output:
            combined_output += "\n--- STDERR ---\n"
        combined_output += stderr

    if not combined_output:
        combined_output = "(Natija bo'sh / Hech narsa qaytmadi)"

    # Xabar uzunligi Telegram chegarasidan kichik bo'lsa
    if len(header) + len(combined_output) < 3800:
        full_text = f"{header}<pre>{escape_html(combined_output)}</pre>"
        try:
            await status_msg.edit_text(full_text, parse_mode="HTML", reply_markup=quick_terminal_keyboard())
        except Exception:
            await status_msg.edit_text(f"{status_icon} Buyruq: {command}\nVaqt: {duration}s | Kod: {exit_code}\n\n{combined_output}", reply_markup=quick_terminal_keyboard())
    else:
        # Natija juda uzun bo'lsa qisqartirib ko'rsatish va .txt fayl sifatida ilova qilish
        short_preview = truncate_text(combined_output, max_length=2000)
        full_text = (
            f"{header}<pre>{escape_html(short_preview)}</pre>\n"
            f"<i>⚠️ Natija juda uzun bo'lgani uchun to'liq log fayl pastda ilova qilindi.</i>"
        )
        try:
            await status_msg.edit_text(full_text, parse_mode="HTML", reply_markup=quick_terminal_keyboard())
        except Exception:
            await status_msg.edit_text(f"{status_icon} Buyruq: {command}\n\n{short_preview}", reply_markup=quick_terminal_keyboard())

        # Fayl sifatida yuborish
        try:
            log_bytes = combined_output.encode("utf-8", errors="replace")
            log_file = BufferedInputFile(log_bytes, filename="terminal_output.txt")
            await target_msg.answer_document(log_file, caption=f"📄 Buyruq logi: {command[:30]}")
        except Exception as file_err:
            logger.error(f"Log faylni yuborishda xatolik: {file_err}")

