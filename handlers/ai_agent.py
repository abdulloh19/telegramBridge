from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import get_user_cwd
from services.ai_service import AIService
from services.file_service import FileService
from keyboards.inline import get_path_from_token, file_actions_keyboard
from utils.helpers import escape_html, split_text_chunks
from utils.logger import logger

router = Router()


class AIStates(StatesGroup):
    waiting_for_agent_instruction = State()
    waiting_for_ai_question = State()
    waiting_for_fix_details = State()


@router.message(Command("agent"))
async def cmd_ai_agent(message: Message, state: FSMContext):
    """Avtonom AI Coding Agent buyrug'i."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await state.update_data(cwd=str(cwd))
        await state.set_state(AIStates.waiting_for_agent_instruction)
        await message.answer(
            f"🤖 <b>Avtonom AI Coding Agent</b>\n\n"
            f"Agent loyihangizdagi fayllarni mustaqil o'qishi, tahrirlashi, yangi fayllar yaratishi va terminal buyruqlarini bajarishi mumkin.\n\n"
            f"📍 <b>Ishchi papka:</b> <code>{escape_html(str(cwd))}</code>\n\n"
            f"✍️ <i>Bajarilishi kerak bo'lgan vazifani yozing (masalan: 'Loyihaga yangi login funksiyasini qo'sh' yoki 'Barcha fayllardagi xatolarni tekshir'):</i>",
            parse_mode="HTML"
        )
        return

    instruction = args[1].strip()
    await _run_agent_flow(message, instruction, cwd)


@router.message(F.text == "🤖 AI Agent")
async def btn_ai_agent_menu(message: Message, state: FSMContext):
    """Pastki tugma orqali AI Agent menyusi."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)

    status_str = "🟢 Faol (Sozlangan)" if AIService.is_configured() else "🟡 API Kalit kiritilmagan (.env da GEMINI_API_KEY)"

    text = (
        f"🤖 <b>Sun'iy Intellekt va AI Coding Agent</b>\n\n"
        f"⚡ <b>Holat:</b> {status_str}\n"
        f"📍 <b>Joriy papka:</b> <code>{escape_html(str(cwd))}</code>\n\n"
        f"📌 <b>Mavjud buyruqlar:</b>\n"
        f"• <code>/agent &lt;vazifa&gt;</code> — Avtonom AI dasturchiga vazifa topshirish\n"
        f"• <code>/fix &lt;fayl&gt; [muammo]</code> — Fayldagi xatoni avtomatik topib tuzatish\n"
        f"• <code>/explain &lt;fayl&gt;</code> — Fayl kodi qanday ishlashini tushunish\n"
        f"• <code>/review &lt;fayl&gt;</code> — Code Review va xavfsizlik tekshiruvi\n"
        f"• <code>/ai &lt;savol&gt;</code> — Dasturlash bo'yicha to'g'ridan-to'g'ri AI bilan suhbat\n\n"
        f"<i>Quyida to'g'ridan-to'g'ri vazifangizni yozishingiz mumkin:</i>"
    )
    await state.update_data(cwd=str(cwd))
    await state.set_state(AIStates.waiting_for_agent_instruction)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("ai"))
async def cmd_ai_ask(message: Message, state: FSMContext):
    """To'g'ridan-to'g'ri AI ga savol berish."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await state.set_state(AIStates.waiting_for_ai_question)
        await message.answer("💬 AI ga savolingizni yozing:")
        return

    question = args[1].strip()
    await _answer_ai_question(message, question)


@router.message(Command("explain"))
async def cmd_explain_code(message: Message):
    """Kodni tushuntirish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Foydalanish: <code>/explain &lt;fayl_nomi&gt;</code>", parse_mode="HTML")
        return

    file_path = FileService.resolve_path(cwd, args[1].strip())
    if not file_path.exists() or not file_path.is_file():
        await message.answer("❌ Fayl topilmadi!")
        return

    status_msg = await message.answer(f"🧠 <code>{escape_html(file_path.name)}</code> kodi tahlil qilinmoqda...", parse_mode="HTML")
    explanation = await AIService.explain_code(file_path)
    await _send_long_response(status_msg, f"📖 <b>Kod Tahlili:</b> <code>{escape_html(file_path.name)}</code>\n\n{explanation}")


@router.message(Command("review"))
async def cmd_review_code(message: Message):
    """Code Review o'tkazish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("Foydalanish: <code>/review &lt;fayl_nomi&gt;</code>", parse_mode="HTML")
        return

    file_path = FileService.resolve_path(cwd, args[1].strip())
    if not file_path.exists() or not file_path.is_file():
        await message.answer("❌ Fayl topilmadi!")
        return

    status_msg = await message.answer(f"🔍 <code>{escape_html(file_path.name)}</code> kodi tekshirilmoqda...", parse_mode="HTML")
    review = await AIService.review_code(file_path)
    await _send_long_response(status_msg, f"🔍 <b>Code Review:</b> <code>{escape_html(file_path.name)}</code>\n\n{review}")


@router.message(Command("fix"))
async def cmd_fix_code(message: Message):
    """Koddagi xatolikni AI orqali tuzatish."""
    user_id = message.from_user.id
    cwd = get_user_cwd(user_id)
    parts = message.text.split(maxsplit=2)

    if len(parts) < 2:
        await message.answer(
            "Foydalanish: <code>/fix &lt;fayl_nomi&gt; [muammo_tavsifi]</code>\n"
            "Masalan: <code>/fix main.py TypeError xatosini tuzat</code>",
            parse_mode="HTML"
        )
        return

    file_name = parts[1].strip()
    issue = parts[2].strip() if len(parts) > 2 else "Koddagi xatoliklarni aniqlab, ularni tuzat."
    file_path = FileService.resolve_path(cwd, file_name)

    if not file_path.exists() or not file_path.is_file():
        await message.answer("❌ Fayl topilmadi!")
        return

    status_msg = await message.answer(f"🔧 <code>{escape_html(file_path.name)}</code> tahlil qilinmoqda va tuzatilmoqda...", parse_mode="HTML")
    fix_result, applied = await AIService.fix_code(file_path, issue, auto_apply=True)

    applied_badge = "✅ <b>Tuzatilgan kod faylga avtomatik saqlandi!</b>\n\n" if applied else ""
    await _send_long_response(status_msg, f"🔧 <b>Xatolikni Tuzatish:</b> <code>{escape_html(file_path.name)}</code>\n{applied_badge}{fix_result}")


# ==========================================
# FSM State Handlers
# ==========================================

@router.message(AIStates.waiting_for_agent_instruction)
async def handle_agent_instruction_state(message: Message, state: FSMContext):
    data = await state.get_data()
    cwd_str = data.get("cwd")
    await state.clear()

    cwd = Path(cwd_str) if cwd_str else get_user_cwd(message.from_user.id)
    await _run_agent_flow(message, message.text.strip(), cwd)


@router.message(AIStates.waiting_for_ai_question)
async def handle_ai_question_state(message: Message, state: FSMContext):
    await state.clear()
    await _answer_ai_question(message, message.text.strip())


async def _run_agent_flow(message: Message, instruction: str, cwd: Path):
    """Avtonom agentni ishga tushiruvchi yordamchi oqim."""
    status_msg = await message.answer(
        f"🤖 <b>AI Agent ishga tushdi...</b>\n"
        f"📋 <b>Vazifa:</b> <i>{escape_html(instruction)}</i>\n"
        f"📍 <code>{escape_html(str(cwd))}</code>\n\n"
        f"⏳ <i>Fayllar tahlil qilinmoqda va kerakli o'zgarishlar kiritilmoqda...</i>",
        parse_mode="HTML"
    )

    result = await AIService.run_autonomous_agent(instruction, cwd)
    await _send_long_response(status_msg, f"🏁 <b>AI Agent Hisoboti:</b>\n\n{result}")


async def _answer_ai_question(message: Message, question: str):
    status_msg = await message.answer("💭 AI javob tayyorlamoqda...")
    answer = await AIService.ask_ai(question)
    await _send_long_response(status_msg, f"🤖 <b>AI Javobi:</b>\n\n{answer}")


async def _send_long_response(status_msg: Message, full_text: str):
    """Uzun javoblarni xavfsiz bo'lib yuboruvchi yordamchi funksiya."""
    chunks = split_text_chunks(full_text, chunk_size=3800)
    try:
        # Birinchi qismini status xabariga tahrirlash
        await status_msg.edit_text(chunks[0], parse_mode="HTML")
        # Qolgan qismlarini yangi xabarlar qilib yuborish
        for chunk in chunks[1:]:
            await status_msg.answer(chunk, parse_mode="HTML")
    except Exception:
        # HTML xatosi bo'lsa oddiy matn sifatida chiqarish
        await status_msg.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await status_msg.answer(chunk)


# ==========================================
# Callback Handlers
# ==========================================

@router.callback_query(F.data.startswith("aiexp:"))
async def cb_ai_explain(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    target_file = get_path_from_token(token)
    if not target_file or not target_file.exists():
        await callback.answer("❌ Fayl topilmadi!", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer(f"🧠 <code>{escape_html(target_file.name)}</code> kodi tahlil qilinmoqda...", parse_mode="HTML")
    explanation = await AIService.explain_code(target_file)
    await _send_long_response(status_msg, f"📖 <b>Kod Tahlili:</b> <code>{escape_html(target_file.name)}</code>\n\n{explanation}")


@router.callback_query(F.data.startswith("airev:"))
async def cb_ai_review(callback: CallbackQuery):
    token = callback.data.split(":", 1)[1]
    target_file = get_path_from_token(token)
    if not target_file or not target_file.exists():
        await callback.answer("❌ Fayl topilmadi!", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer(f"🔍 <code>{escape_html(target_file.name)}</code> kodi tekshirilmoqda...", parse_mode="HTML")
    review = await AIService.review_code(target_file)
    await _send_long_response(status_msg, f"🔍 <b>Code Review:</b> <code>{escape_html(target_file.name)}</code>\n\n{review}")
