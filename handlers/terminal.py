import io
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from config import get_user_cwd, SHELL_TYPE
from services.terminal_service import TerminalService
from services.file_service import FileService
from keyboards.inline import quick_terminal_keyboard
from utils.helpers import escape_html, truncate_text, split_text_chunks
from utils.logger import logger

router = Router()


@router.message(Command("sh"))
@router.message(Command("cmd"))
@router.message(Command("ps"))
async def cmd_run_shell(message: Message):
    """Terminal buyrug'ini bajarish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            f"💻 <b>Terminal Buyruqlari</b>\n\n"
            f"Foydalanish: <code>/sh &lt;buyruq&gt;</code>\n"
            f"Masalan:\n"
            f"• <code>/sh git status</code>\n"
            f"• <code>/sh pip list</code>\n"
            f"• <code>/sh python main.py</code>\n"
            f"• <code>/sh npm run build</code>\n\n"
            f"📍 <b>Joriy papka:</b> <code>{escape_html(str(cwd))}</code>",
            parse_mode="HTML",
            reply_markup=quick_terminal_keyboard()
        )
        return

    command = args[1].strip()
    await _execute_and_send_result(message, command, cwd)


@router.message(F.text == "💻 Terminal")
async def btn_terminal_menu(message: Message):
    """Pastki tugma orqali terminal menyusi."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)

    text = (
        f"💻 <b>Masofaviy Terminal ({SHELL_TYPE.upper()})</b>\n\n"
        f"📍 <b>Joriy katalog:</b> <code>{escape_html(str(cwd))}</code>\n\n"
        f"Buyruq yuborish uchun <code>/sh &lt;buyruq&gt;</code> yozing yoki quyidagi tezkor tugmalardan foydalaning:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=quick_terminal_keyboard())


@router.message(F.text == "⚡ Git Status")
async def btn_git_status(message: Message):
    """Git status tezkor tugmasi."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    await _execute_and_send_result(message, "git status", cwd)


@router.callback_query(F.data.startswith("term:"))
async def cb_quick_terminal(callback: CallbackQuery):
    """Tezkor inline terminal tugmalari."""
    command = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    cwd = get_user_cwd(user_id)

    await callback.answer(f"{command} bajarilmoqda...")
    await _execute_and_send_result(callback.message, command, cwd)


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
    await callback.message.answer(text, parse_mode="HTML")


async def _execute_and_send_result(target_msg: Message, command: str, cwd: Path):
    """Terminal buyrug'ini bajarib, natijani formatlab yuboruvchi yordamchi funksiya."""
    status_msg = await target_msg.answer(
        f"⏳ <b>Bajarilmoqda:</b> <code>{escape_html(command)}</code>\n"
        f"📍 <i>{escape_html(str(cwd))}</i>",
        parse_mode="HTML"
    )

    result = await TerminalService.execute_command(command, cwd=cwd)

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
        await status_msg.edit_text(full_text, parse_mode="HTML", reply_markup=quick_terminal_keyboard())
    else:
        # Natija juda uzun bo'lsa qisqartirib ko'rsatish va .txt fayl sifatida ilova qilish
        short_preview = truncate_text(combined_output, max_length=2000)
        full_text = (
            f"{header}<pre>{escape_html(short_preview)}</pre>\n"
            f"<i>⚠️ Natija juda uzun bo'lgani uchun to'liq log fayl pastda ilova qilindi.</i>"
        )
        await status_msg.edit_text(full_text, parse_mode="HTML", reply_markup=quick_terminal_keyboard())

        # Fayl sifatida yuborish
        log_bytes = combined_output.encode("utf-8")
        log_file = BufferedInputFile(log_bytes, filename="terminal_output.txt")
        await target_msg.answer_document(log_file, caption=f"📄 Buyruq logi: {command[:30]}")
