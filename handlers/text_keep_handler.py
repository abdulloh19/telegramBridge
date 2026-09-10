"""
Eslatmalar va Rejalar Handleri (Notes & Reminders Handler)
=========================================================
1. /reminders — barcha faol, kutayotgan eslatmalarni ko'rish va bekor qilish
2. /notes — saqlangan matnli qaydlarni ko'rish
3. /remind <matn> — matndan vaqtlarni aniqlab eslatma o'rnatish
4. /note <matn> — oddiy qayd saqlash
5. Eslatma: ... yoki ko'p vaqtli matn kelsa eslatma yoqishni taklif qilish
"""

import time
import logging
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.notes_service import NotesService
from services.reminder_service import ReminderService
from services.reminder_parser import parse_multiple_reminders, format_reminders_summary, get_current_tashkent_time

logger = logging.getLogger(__name__)

router = Router()

# Vaqtincha matnli eslatma takliflarini saqlash (chat_id -> dict)
_pending_text_reminders: dict = {}


def _build_reminders_list_keyboard(reminders: list) -> InlineKeyboardMarkup:
    """Faol eslatmalar uchun o'chirish tugmalari."""
    buttons = []
    for r in reminders[:10]:
        title = r.get("title", "Eslatma")
        if len(title) > 22:
            title = title[:19] + "..."
        time_str = r.get("due_datetime", "").split()[-1]
        rid = r.get("id")
        buttons.append([
            InlineKeyboardButton(text=f"⏰ {time_str} — {title}", callback_data=f"rnoop_{rid}"),
            InlineKeyboardButton(text="🗑️ Bekor qilish", callback_data=f"rcancel_{rid}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("reminders", "eslatmalarim"))
async def cmd_list_reminders(message: Message):
    """Foydalanuvchining barcha faol eslatmalarini ko'rsatish."""
    user_id = message.from_user.id
    rems = ReminderService.get_user_reminders(user_id, status="pending")

    if not rems:
        await message.answer(
            "⏰ <b>Sizda hozircha faol eslatmalar yo'q.</b>\n\n"
            "💡 <b>Yangi eslatma o'rnatish:</b>\n"
            "• Ovozli xabarda vaqtni ayting (masalan: <i>«Soat 10:00 da majlis, keyin 14:00 da dars»</i>)\n"
            "• Yoki matn orqali yozing: <code>/remind Ertaga soat 9:00 da hisobot</code>",
            parse_mode="HTML"
        )
        return

    now_ts = int(get_current_tashkent_time().timestamp())
    lines = []
    for i, r in enumerate(rems, 1):
        due_ts = r.get("due_timestamp", 0)
        diff_sec = max(0, due_ts - now_ts)
        hours_left = diff_sec // 3600
        mins_left = (diff_sec % 3600) // 60

        time_left_str = ""
        if hours_left > 0:
            time_left_str = f"<i>(qolgan vaqt: {hours_left} soat {mins_left} daqiqa)</i>"
        else:
            time_left_str = f"<i>(qolgan vaqt: {mins_left} daqiqa)</i>"

        lines.append(
            f"{i}. ⏰ <b>{r.get('due_datetime')}</b> — <b>{r.get('title')}</b>\n   └ {time_left_str}"
        )

    text = (
        f"🔔 <b>Sizning faol eslatmalaringiz ({len(rems)} ta):</b>\n\n"
        + "\n\n".join(lines)
        + "\n\n<i>Belgilangan vaqtda bot sizga avtomatik xabar yuboradi.</i>"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_build_reminders_list_keyboard(rems)
    )


@router.callback_query(F.data.startswith("rcancel_"))
async def callback_cancel_reminder(callback: CallbackQuery):
    """Eslatmani bekor qilish."""
    rem_id = callback.data.replace("rcancel_", "")
    user_id = callback.from_user.id

    success = ReminderService.cancel_reminder(user_id, rem_id)
    if success:
        await callback.answer("✅ Eslatma bekor qilindi.")
    else:
        await callback.answer("⚠️ Eslatma topilmadi.")

    rems = ReminderService.get_user_reminders(user_id, status="pending")
    if not rems:
        await callback.message.edit_text(
            "⏰ <b>Barcha eslatmalar bekor qilindi. Faol eslatmalar qolmadi.</b>",
            parse_mode="HTML"
        )
        return

    await callback.message.edit_reply_markup(reply_markup=_build_reminders_list_keyboard(rems))


@router.callback_query(F.data.startswith("rnoop_"))
async def callback_rnoop(callback: CallbackQuery):
    await callback.answer()


@router.message(Command("remind", "eslatma"))
async def cmd_create_reminder_from_text(message: Message):
    """Matndan ko'p vaqtli eslatmalar yaratish (/remind <matn>)."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "✍️ <b>Eslatma matnini va vaqtini yozing:</b>\n"
            "Masalan: <code>/remind Soat 10:00 da majlis, 14:30 da tushlik</code>",
            parse_mode="HTML"
        )
        return

    text = parts[1].strip()
    reminders = await parse_multiple_reminders(text)

    if not reminders:
        # Agar vaqt aniqlanmasa, oddiy qayd sifatida saqlaymiz
        note = NotesService.save_note(user_id=message.from_user.id, text=text, source="text")
        await message.answer(
            f"ℹ️ Matnda aniq vaqt topilmadi, lekin qayd sifatida saqlandi: <b>{note.get('title')}</b>\n\n"
            "Ko'rish: /notes",
            parse_mode="HTML"
        )
        return

    # Eslatmalarni o'rnatish
    user_id = message.from_user.id
    chat_id = message.chat.id

    created = ReminderService.add_multiple_reminders(
        user_id=user_id,
        chat_id=chat_id,
        items=reminders,
        source="text"
    )

    rem_summary = format_reminders_summary(reminders)

    msg = (
        f"✅ <b>{len(created)} ta eslatma muvaffaqiyatli o'rnatildi! 🔔</b>\n\n"
        f"{rem_summary}\n\n"
        "⚡ <i>Har bir vaqt yetib kelganida bot sizga eslatma yuboradi.</i>\n\n"
        "Barcha eslatmalar: <b>/reminders</b>"
    )

    await message.answer(msg, parse_mode="HTML")


# =========================================================================
# Qaydlar (Notes) qismi
# =========================================================================

def _build_notes_list_keyboard(notes: list) -> InlineKeyboardMarkup:
    buttons = []
    for n in notes[:10]:
        title = n.get("title", "Qayd")
        if len(title) > 28:
            title = title[:25] + "..."
        nid = n.get("id")
        buttons.append([
            InlineKeyboardButton(text=f"📌 {title}", callback_data=f"nv_{nid}"),
            InlineKeyboardButton(text="🗑️", callback_data=f"nd_{nid}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("notes"))
@router.message(F.text == "📋 Eslatmalarim")
async def cmd_list_notes(message: Message):
    """Foydalanuvchining barcha saqlangan qaydlarini ko'rsatish."""
    user_id = message.from_user.id
    notes = NotesService.get_user_notes(user_id)
    rems = ReminderService.get_user_reminders(user_id, status="pending")

    rem_info = ""
    if rems:
        rem_info = f"\n🔔 <i>(Sizda {len(rems)} ta faol vaqtli eslatma ham bor: /reminders)</i>\n"

    if not notes:
        await message.answer(
            f"📭 <b>Sizda saqlangan matnli qaydlar yo'q.</b>{rem_info}\n\n"
            "💡 Yangi qayd yaratish: <code>/note Sizning eslatmangiz</code>\n"
            "⏰ Vaqtli eslatma: <code>/remind 15:00 da uchrashuv</code>",
            parse_mode="HTML"
        )
        return

    text = (
        f"📋 <b>Sizning saqlangan qaydlaringiz ({len(notes)} ta):</b>{rem_info}\n\n"
        "<i>Batafsil o'qish uchun ustiga bosing:</i>"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_build_notes_list_keyboard(notes)
    )


@router.message(Command("note"))
async def cmd_add_note(message: Message):
    """Oddiy qayd qo'shish (/note <matn>)."""
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "✍️ <b>Qayd matnini kiriting:</b>\n"
            "Masalan: <code>/note Ertaga hisobot topshirish kerak</code>",
            parse_mode="HTML"
        )
        return

    note_text = parts[1].strip()
    note = NotesService.save_note(user_id=user_id, text=note_text, source="text")

    await message.answer(
        "<b>✅ Qayd saqlandi!</b>\n\n"
        f"📌 <b>{note.get('title')}</b>\n"
        f"🕒 {note.get('created_at')}\n\n"
        "Ro'yxat: /notes",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("nv_"))
async def callback_view_note(callback: CallbackQuery):
    note_id = callback.data.replace("nv_", "")
    user_id = callback.from_user.id

    note = NotesService.get_note(user_id, note_id)
    if not note:
        await callback.answer("⚠️ Qayd topilmadi yoki o'chirilgan.", show_alert=True)
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
    note_id = callback.data.replace("nd_", "")
    user_id = callback.from_user.id

    success = NotesService.delete_note(user_id, note_id)
    if success:
        await callback.answer("✅ Qayd o'chirildi.")
    else:
        await callback.answer("⚠️ Topilmadi.")

    notes = NotesService.get_user_notes(user_id)
    if not notes:
        await callback.message.edit_text("📭 Boshqa qaydlar qolmadi.", parse_mode="HTML")
        return

    await callback.message.edit_text(
        f"📋 <b>Sizning saqlangan qaydlaringiz ({len(notes)} ta):</b>",
        parse_mode="HTML",
        reply_markup=_build_notes_list_keyboard(notes)
    )


@router.callback_query(F.data == "n_back_list")
async def callback_back_to_notes(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    notes = NotesService.get_user_notes(user_id)

    if not notes:
        await callback.message.edit_text("📭 Sizda hozircha qaydlar yo'q.", parse_mode="HTML")
        return

    await callback.message.edit_text(
        f"📋 <b>Sizning saqlangan qaydlaringiz ({len(notes)} ta):</b>",
        parse_mode="HTML",
        reply_markup=_build_notes_list_keyboard(notes)
    )


# =========================================================================
# Oddiy matnli xabarlardan vaqt va eslatmalarni avtomatik aniqlash
# =========================================================================

@router.message(F.text, StateFilter(None))
async def handle_plain_text_message(message: Message, state: FSMContext):
    """
    Foydalanuvchi oddiy matn yuborganda (masalan: «10:20 da uchrashuv bor» yoki «soat 10:20 da majlis»):
    Agar matnda vaqt aniqlansa, darhol eslatma o'rnatiladi va tasdiq xabari yuboriladi.
    """
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    # Havolalarni media downloader ga berish uchun chetlab o'tamiz
    if text.startswith("http://") or text.startswith("https://") or "t.me/" in text:
        return

    # Reply menyu tugmalari
    ignored_menu_texts = [
        "📥 Video Yuklash (/dl)",
        "🎵 Faqat MP3 (/mp3)",
        "🧹 Hisob Tozalash (/cleaner)",
        "ℹ️ Qo'llanma / Yordam",
        "📋 Eslatmalarim"
    ]
    if text in ignored_menu_texts:
        return

    reminders = await parse_multiple_reminders(text)
    if not reminders:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    created = ReminderService.add_multiple_reminders(
        user_id=user_id,
        chat_id=chat_id,
        items=reminders,
        source="text"
    )

    rem_summary = format_reminders_summary(reminders)

    buttons = []
    for r in created:
        rid = r.get("id")
        t_str = r.get("time", "")
        buttons.append([
            InlineKeyboardButton(text=f"🗑️ Bekor qilish ({t_str})", callback_data=f"rcancel_{rid}")
        ])

    await message.reply(
        f"✅ <b>{len(created)} ta eslatma muvaffaqiyatli o'rnatildi! 🔔</b>\n\n"
        f"{rem_summary}\n\n"
        "⚡ <i>Belgilangan vaqtda bot sizga avtomatik eslatma yuboradi.</i>\n\n"
        "Barcha eslatmalar: <b>/reminders</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    )

