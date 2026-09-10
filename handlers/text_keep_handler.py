"""
Eslatmalar Handleri (Notes Handler)
==================================
1. /notes yoki /eslatmalar — barcha saqlangan eslatmalarni ko'rish
2. /note <matn> yoki /eslatma <matn> — yangi matnli eslatma saqlash
3. "Eslatma: ..." deb yozilsa avtomatik eslatmaga saqlash
4. Eslatmalarni o'chirish va to'liq o'qish
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.notes_service import NotesService
from services.google_keep_service import is_keep_configured, save_to_google_keep

logger = logging.getLogger(__name__)

router = Router()


def _build_notes_list_keyboard(notes: list) -> InlineKeyboardMarkup:
    """Eslatmalar ro'yxati tugmalari."""
    buttons = []
    for n in notes[:10]:
        title = n.get("title", "Eslatma")
        if len(title) > 28:
            title = title[:25] + "..."
        nid = n.get("id")
        buttons.append([
            InlineKeyboardButton(text=f"📌 {title}", callback_data=f"nv_{nid}"),
            InlineKeyboardButton(text="🗑️", callback_data=f"nd_{nid}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("notes", "eslatmalar"))
@router.message(F.text == "📋 Eslatmalarim")
async def cmd_list_notes(message: Message):
    """Foydalanuvchining barcha eslatmalarini ko'rsatish."""
    user_id = message.from_user.id
    notes = NotesService.get_user_notes(user_id)

    if not notes:
        await message.answer(
            "📭 <b>Sizda hozircha saqlangan eslatmalar yo'q.</b>\n\n"
            "💡 <b>Yangi eslatma yaratish:</b>\n"
            "• Botga <b>ovozli xabar</b> yuboring va 'Saqlash' tugmasini bosing\n"
            "• Yoki <code>/note Sizning eslatmangiz</code> deb yozing\n"
            "• Yoki <code>Eslatma: ertaga soat 10 da uchrashuv</code> deb yuboring",
            parse_mode="HTML"
        )
        return

    text = (
        f"📋 <b>Sizning saqlangan eslatmalaringiz ({len(notes)} ta):</b>\n\n"
        "<i>Batafsil o'qish uchun eslatma ustiga bosing:</i>"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_build_notes_list_keyboard(notes)
    )


@router.message(Command("note", "eslatma"))
async def cmd_add_note(message: Message):
    """Tezkor eslatma qo'shish (/note <matn>)."""
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "✍️ <b>Eslatma matnini kiriting:</b>\n"
            "Masalan: <code>/note Ertaga hisobot topshirish kerak</code>",
            parse_mode="HTML"
        )
        return

    note_text = parts[1].strip()
    note = NotesService.save_note(user_id=user_id, text=note_text, source="text")

    if is_keep_configured():
        try:
            await save_to_google_keep(note_text, title=note.get("title"))
        except Exception:
            pass

    await message.answer(
        "<b>✅ Eslatma saqlandi!</b>\n\n"
        f"📌 <b>Sarlavha:</b> {note.get('title')}\n"
        f"🕒 <b>Vaqt:</b> {note.get('created_at')}\n\n"
        "Barcha eslatmalarni ko'rish: /notes",
        parse_mode="HTML"
    )


@router.message(F.text.lower().startswith("eslatma:") | F.text.lower().startswith("eslatma "))
async def handle_note_prefix(message: Message):
    """'Eslatma: ...' formatidagi xabarlarni avtomatik eslatma qilish."""
    user_id = message.from_user.id
    text = message.text
    clean_text = text.split(":", 1)[-1].strip() if ":" in text else text[7:].strip()

    if not clean_text:
        return

    note = NotesService.save_note(user_id=user_id, text=clean_text, source="text")

    if is_keep_configured():
        try:
            await save_to_google_keep(clean_text, title=note.get("title"))
        except Exception:
            pass

    await message.answer(
        "<b>✅ Eslatma saqlandi!</b>\n\n"
        f"📌 <b>{note.get('title')}</b>\n"
        f"🕒 {note.get('created_at')}\n\n"
        "Ro'yxat: /notes",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("nv_"))
async def callback_view_note(callback: CallbackQuery):
    """Eslatmani to'liq o'qish."""
    note_id = callback.data.replace("nv_", "")
    user_id = callback.from_user.id

    note = NotesService.get_note(user_id, note_id)
    if not note:
        await callback.answer("⚠️ Eslatma topilmadi yoki o'chirilgan.", show_alert=True)
        return

    await callback.answer()
    src_icon = "🎤" if note.get("source") == "voice" else "✍️"

    msg = (
        f"{src_icon} <b>{note.get('title')}</b>\n"
        f"🕒 <i>{note.get('created_at')}</i>\n\n"
        f"{note.get('text')}"
    )

    del_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"nd_{note_id}"),
            InlineKeyboardButton(text="⬅️ Ortga", callback_data="n_back_list"),
        ]
    ])

    await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=del_kb)


@router.callback_query(F.data.startswith("nd_"))
async def callback_delete_note(callback: CallbackQuery):
    """Eslatmani o'chirish."""
    note_id = callback.data.replace("nd_", "")
    user_id = callback.from_user.id

    success = NotesService.delete_note(user_id, note_id)
    if success:
        await callback.answer("✅ Eslatma o'chirildi.")
    else:
        await callback.answer("⚠️ Eslatma topilmadi.")

    notes = NotesService.get_user_notes(user_id)
    if not notes:
        await callback.message.edit_text("📭 Sizda boshqa eslatmalar qolmadi.\n\nYangi qo'shish: /note", parse_mode="HTML")
        return

    await callback.message.edit_text(
        f"📋 <b>Sizning saqlangan eslatmalaringiz ({len(notes)} ta):</b>",
        parse_mode="HTML",
        reply_markup=_build_notes_list_keyboard(notes)
    )


@router.callback_query(F.data == "n_back_list")
async def callback_back_to_notes(callback: CallbackQuery):
    """Eslatmalar ro'yxatiga qaytish."""
    await callback.answer()
    user_id = callback.from_user.id
    notes = NotesService.get_user_notes(user_id)

    if not notes:
        await callback.message.edit_text("📭 Sizda hozircha eslatmalar yo'q.", parse_mode="HTML")
        return

    await callback.message.edit_text(
        f"📋 <b>Sizning saqlangan eslatmalaringiz ({len(notes)} ta):</b>",
        parse_mode="HTML",
        reply_markup=_build_notes_list_keyboard(notes)
    )
