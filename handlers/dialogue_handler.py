import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from services.dialogue_service import (
    normalize_topic,
    get_dialogues_for_topic,
    get_active_dialogue,
    format_dialogue_telegram_message,
    TOPIC_METADATA
)
from keyboards.dialogue_keyboards import (
    get_dialogue_topics_keyboard,
    get_dialogue_view_keyboard
)
from utils.logger import logger

router = Router()

# Foydalanuvchi joriy sozlamalari (In-Memory Session)
# { user_id: { "topic": "taxi", "scenario_idx": 0, "step": 0, "lang": "en" } }
_USER_DIALOGUE_SESSIONS: dict[int, dict] = {}


def _get_session(user_id: int) -> dict:
    if user_id not in _USER_DIALOGUE_SESSIONS:
        _USER_DIALOGUE_SESSIONS[user_id] = {
            "topic": "taxi",
            "scenario_idx": 0,
            "step": 0,
            "lang": "en"
        }
    return _USER_DIALOGUE_SESSIONS[user_id]


@router.message(Command("dialogue", "dialog", "speaking"), StateFilter("*"))
@router.message(F.text.in_({"🗣️ Dialoglar", "🗣️ Jonli Dialoglar", "🗣️ Dialoglar (Speaking)", "🗣️ Dialog"}), StateFilter("*"))
async def cmd_dialogue_menu(message: Message, state: FSMContext):
    """Mavzular tanlash bosh menyusini ko'rsatadi."""
    await state.clear()
    user_id = message.from_user.id
    session = _get_session(user_id)
    lang = session.get("lang", "en")

    text = (
        "🗣️ <b>Hayotiy Jonli Dialoglar Markazi</b>\n\n"
        "Barcha mavzularda bir nechta real vaziyatlar (ssenariylar) mavjud!\n"
        "Bir mavzuni tanlaganingizda, tizim <b>qat'iy ravishda</b> shu mavzuga xos yangi vaziyatlarni taqdim etadi.\n\n"
        "👇 <i>O'rganmoqchi bo'lgan mavzungizni tanlang:</i>"
    )

    kb = get_dialogue_topics_keyboard(lang=lang)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "dlg_menu")
async def cb_dlg_menu(callback: CallbackQuery, state: FSMContext):
    """Mavzular menyusiga qaytish."""
    user_id = callback.from_user.id
    session = _get_session(user_id)
    lang = session.get("lang", "en")

    text = (
        "🗣️ <b>Hayotiy Jonli Dialoglar Markazi</b>\n\n"
        "👇 <i>O'rganmoqchi bo'lgan mavzungizni tanlang:</i>"
    )
    kb = get_dialogue_topics_keyboard(lang=lang)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "dlg_toggle_lang")
async def cb_dlg_toggle_lang(callback: CallbackQuery):
    """Mavzular menyusida tilni o'zgartirish."""
    user_id = callback.from_user.id
    session = _get_session(user_id)
    current_lang = session.get("lang", "en")
    new_lang = "ru" if current_lang == "en" else "en"
    session["lang"] = new_lang

    kb = get_dialogue_topics_keyboard(lang=new_lang)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    lang_name = "🇷🇺 Rus tili" if new_lang == "ru" else "🇬🇧 Ingliz tili"
    await callback.answer(f"O'rganish tili: {lang_name}ga o'zgartirildi!")


@router.callback_query(F.data == "dlg_back_main")
async def cb_dlg_back_main(callback: CallbackQuery, state: FSMContext):
    """Asosiy start menyusiga qaytish."""
    from handlers.start import cmd_start
    await cmd_start(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.startswith("dlg_top:"))
async def cb_select_topic(callback: CallbackQuery):
    """Foydalanuvchi yangi mavzuni tanlaganda 1-vaziyat va 1-qadamdan boshlaydi."""
    user_id = callback.from_user.id
    raw_topic = callback.data.split(":")[1]
    topic = normalize_topic(raw_topic)

    session = _get_session(user_id)
    session["topic"] = topic
    session["scenario_idx"] = 0
    session["step"] = 0
    lang = session.get("lang", "en")

    dialogues = get_dialogues_for_topic(topic, lang)
    active_dlg = dialogues[0] if dialogues else get_active_dialogue(topic, 0, lang)

    text = format_dialogue_telegram_message(
        dialogue=active_dlg,
        current_step=0,
        topic=topic,
        scenario_idx=0,
        lang=lang
    )

    kb = get_dialogue_view_keyboard(
        topic=topic,
        scenario_idx=0,
        current_step=0,
        total_steps=len(active_dlg.get("lines", [])),
        total_scenarios=len(dialogues),
        lang=lang
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(f"Tanlandi: {TOPIC_METADATA.get(topic, {}).get('name', topic)}")


@router.callback_query(F.data.startswith("dlg_step:"))
async def cb_dialogue_step(callback: CallbackQuery):
    """Joriy vaziyat ichida qadamma-qadam oldinga/orqaga siljish."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic = normalize_topic(parts[1])
    scenario_idx = int(parts[2])
    step = int(parts[3])

    session = _get_session(user_id)
    session["topic"] = topic
    session["scenario_idx"] = scenario_idx
    session["step"] = step
    lang = session.get("lang", "en")

    dialogues = get_dialogues_for_topic(topic, lang)
    active_dlg = get_active_dialogue(topic, scenario_idx, lang)
    total_steps = len(active_dlg.get("lines", []))

    text = format_dialogue_telegram_message(
        dialogue=active_dlg,
        current_step=step,
        topic=topic,
        scenario_idx=scenario_idx,
        lang=lang
    )

    kb = get_dialogue_view_keyboard(
        topic=topic,
        scenario_idx=scenario_idx,
        current_step=step,
        total_steps=total_steps,
        total_scenarios=len(dialogues),
        lang=lang
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(f"Qadam: {step + 1}/{total_steps}")


@router.callback_query(F.data.startswith("dlg_scen_next:"))
async def cb_next_scenario(callback: CallbackQuery):
    """
    AYNAN SHU MAVZUDA keyingi vaziyatga o'tish (Strict Topic Continuity).
    Mavzu o'zgarmaydi!
    """
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic = normalize_topic(parts[1])
    next_scenario_idx = int(parts[2])

    session = _get_session(user_id)
    session["topic"] = topic
    session["scenario_idx"] = next_scenario_idx
    session["step"] = 0
    lang = session.get("lang", "en")

    dialogues = get_dialogues_for_topic(topic, lang)
    # Agar ro'yxat chegarasidan oshsa, aylantirib davom ettiramiz
    total_available = len(dialogues)
    safe_idx = next_scenario_idx % max(1, total_available)
    session["scenario_idx"] = safe_idx

    active_dlg = dialogues[safe_idx] if safe_idx < len(dialogues) else get_active_dialogue(topic, safe_idx, lang)

    text = format_dialogue_telegram_message(
        dialogue=active_dlg,
        current_step=0,
        topic=topic,
        scenario_idx=safe_idx,
        lang=lang
    )

    kb = get_dialogue_view_keyboard(
        topic=topic,
        scenario_idx=safe_idx,
        current_step=0,
        total_steps=len(active_dlg.get("lines", [])),
        total_scenarios=total_available,
        lang=lang
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(f"🔄 Yangi vaziyat: {safe_idx + 1}-vaziyat ({TOPIC_METADATA.get(topic, {}).get('name')})")


@router.callback_query(F.data.startswith("dlg_scen_jump:"))
async def cb_scenario_jump(callback: CallbackQuery):
    """Mavjud vaziyat tugmalari (Pills) orqali to'g'ridan-to'g'ri tanlash."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic = normalize_topic(parts[1])
    target_idx = int(parts[2])

    session = _get_session(user_id)
    session["topic"] = topic
    session["scenario_idx"] = target_idx
    session["step"] = 0
    lang = session.get("lang", "en")

    dialogues = get_dialogues_for_topic(topic, lang)
    active_dlg = get_active_dialogue(topic, target_idx, lang)

    text = format_dialogue_telegram_message(
        dialogue=active_dlg,
        current_step=0,
        topic=topic,
        scenario_idx=target_idx,
        lang=lang
    )

    kb = get_dialogue_view_keyboard(
        topic=topic,
        scenario_idx=target_idx,
        current_step=0,
        total_steps=len(active_dlg.get("lines", [])),
        total_scenarios=len(dialogues),
        lang=lang
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(f"{target_idx + 1}-vaziyat yuklandi!")


@router.callback_query(F.data.startswith("dlg_lang_switch:"))
async def cb_lang_switch(callback: CallbackQuery):
    """
    O'rganish tilini almashtirish (EN <-> RU).
    Mavzu, vaziyat va qadam to'liq saqlanadi!
    """
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic = normalize_topic(parts[1])
    scenario_idx = int(parts[2])
    step = int(parts[3])

    session = _get_session(user_id)
    current_lang = session.get("lang", "en")
    new_lang = "ru" if current_lang == "en" else "en"
    session["lang"] = new_lang
    session["topic"] = topic
    session["scenario_idx"] = scenario_idx
    session["step"] = step

    dialogues = get_dialogues_for_topic(topic, new_lang)
    active_dlg = get_active_dialogue(topic, scenario_idx, new_lang)
    total_steps = len(active_dlg.get("lines", []))
    safe_step = min(step, total_steps - 1)

    text = format_dialogue_telegram_message(
        dialogue=active_dlg,
        current_step=safe_step,
        topic=topic,
        scenario_idx=scenario_idx,
        lang=new_lang
    )

    kb = get_dialogue_view_keyboard(
        topic=topic,
        scenario_idx=scenario_idx,
        current_step=safe_step,
        total_steps=total_steps,
        total_scenarios=len(dialogues),
        lang=new_lang
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer(f"Til almashtirildi: {'🇬🇧 English' if new_lang == 'en' else '🇷🇺 Русский'}")


@router.callback_query(F.data.startswith("dlg_finish:"))
async def cb_finish_dialogue(callback: CallbackQuery):
    """Dialog muvaffaqiyatli yakunlanganda tabriklash va keyingi vaziyatga o'tish."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from config import WEBAPP_URL

    user_id = callback.from_user.id
    parts = callback.data.split(":")
    topic = normalize_topic(parts[1])
    scenario_idx = int(parts[2])

    session = _get_session(user_id)
    lang = session.get("lang", "en")
    active_dlg = get_active_dialogue(topic, scenario_idx, lang)
    meta = TOPIC_METADATA.get(topic, TOPIC_METADATA["taxi"])

    congrats_text = (
        f"🎉 <b>Tabriklaymiz! Dialog Muvaffaqiyatli O'rganildi!</b>\n\n"
        f"🏆 <b>«{active_dlg.get('title')}»</b>\n"
        f"📌 <b>Mavzu:</b> {meta['icon']} {meta['name']}\n"
        f"⭐️ <b>O'zlashtirish:</b> 100% (+30 XP ochko)\n\n"
        f"Siz ushbu vaziyatdagi barcha replikalarni to'liq takrorlab chiqdingiz.\n"
        f"Aynan shu mavzudagi navbatdagi vaziyatga o'tishni xohlaysizmi?"
    )

    finish_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🔄 Ushbu mavzudagi keyingi vaziyatga o'tish",
                callback_data=f"dlg_scen_next:{topic}:{scenario_idx + 1}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔁 1-qadamdan qaytadan o'qish",
                callback_data=f"dlg_step:{topic}:{scenario_idx}:0"
            )
        ],
        [
            InlineKeyboardButton(
                text="📱 Super Ilovada davom etish",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Boshqa mavzu tanlash", callback_data="dlg_menu")
        ]
    ])

    try:
        await callback.message.edit_text(congrats_text, parse_mode="HTML", reply_markup=finish_kb)
    except Exception:
        await callback.message.answer(congrats_text, parse_mode="HTML", reply_markup=finish_kb)
    await callback.answer("🎉 Ajoyib natija! +30 XP")
