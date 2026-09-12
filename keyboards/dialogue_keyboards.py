from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from services.dialogue_service import TOPIC_METADATA, normalize_topic
from config import WEBAPP_URL


def get_dialogue_topics_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Mavzularni tanlash uchun inline menyu."""
    buttons = [
        [
            InlineKeyboardButton(text="🚕 Taksi (Taxi)", callback_data="dlg_top:taxi"),
            InlineKeyboardButton(text="🏨 Mehmonxona (Hotel)", callback_data="dlg_top:hotel"),
        ],
        [
            InlineKeyboardButton(text="🍽️ Restoran (Restaurant)", callback_data="dlg_top:restaurant"),
            InlineKeyboardButton(text="✈️ Aeroport (Airport)", callback_data="dlg_top:airport"),
        ],
        [
            InlineKeyboardButton(text="🛍️ Xarid (Shopping)", callback_data="dlg_top:shopping"),
            InlineKeyboardButton(text="🏥 Shifokor (Doctor)", callback_data="dlg_top:doctor"),
        ],
        [
            InlineKeyboardButton(text="🏦 Bank (Bank)", callback_data="dlg_top:bank"),
            InlineKeyboardButton(text="🌟 Combo (Birlashgan)", callback_data="dlg_top:combo"),
        ],
        [
            InlineKeyboardButton(
                text=f"🌐 Til: {'🇬🇧 English' if lang == 'en' else '🇷🇺 Русский'}",
                callback_data="dlg_toggle_lang"
            )
        ],
        [
            InlineKeyboardButton(text="📱 Super Ilovada O'rganish", web_app=WebAppInfo(url=WEBAPP_URL)),
        ],
        [
            InlineKeyboardButton(text="⬅️ Bosh menyuga qaytish", callback_data="dlg_back_main"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_dialogue_view_keyboard(
    topic: str,
    scenario_idx: int,
    current_step: int,
    total_steps: int,
    total_scenarios: int = 4,
    lang: str = "en"
) -> InlineKeyboardMarkup:
    """Aktiv dialog uchun boshqaruv tugmalari."""
    canon = normalize_topic(topic)
    is_last_step = (current_step >= total_steps - 1)

    buttons = []

    # 1-qator: Qadam navigatsiyasi
    nav_row = []
    if current_step > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"dlg_step:{canon}:{scenario_idx}:{current_step - 1}"))

    if not is_last_step:
        nav_row.append(InlineKeyboardButton(
            text=f"▶️ Keyingi jumla ({current_step + 2}/{total_steps})",
            callback_data=f"dlg_step:{canon}:{scenario_idx}:{current_step + 1}"
        ))
    else:
        nav_row.append(InlineKeyboardButton(
            text="🎉 Yakunlash (+30 XP)",
            callback_data=f"dlg_finish:{canon}:{scenario_idx}"
        ))
    buttons.append(nav_row)

    # 2-qator: Aynan shu mavzudagi KEYINGI VAZIYAT (Strict Topic Continuity)
    buttons.append([
        InlineKeyboardButton(
            text=f"🔄 Keyingi vaziyat (Ushbu mavzuda)",
            callback_data=f"dlg_scen_next:{canon}:{scenario_idx + 1}"
        )
    ])

    # 3-qator: Mavjud vaziyatlar ro'yxati (Pills)
    pills = []
    for s_idx in range(min(4, total_scenarios)):
        prefix = "✅ " if s_idx == scenario_idx else ""
        pills.append(InlineKeyboardButton(
            text=f"{prefix}{s_idx + 1}-vaziyat",
            callback_data=f"dlg_scen_jump:{canon}:{s_idx}"
        ))
    buttons.append(pills)

    # 4-qator: Tilni almashtirish & Ilovada ochish
    lang_btn_text = "🇬🇧 Englishga o'tish" if lang == "ru" else "🇷🇺 Rus tiliga o'tish"
    buttons.append([
        InlineKeyboardButton(text=f"🌐 {lang_btn_text}", callback_data=f"dlg_lang_switch:{canon}:{scenario_idx}:{current_step}"),
        InlineKeyboardButton(text="📱 Web Ilova", web_app=WebAppInfo(url=WEBAPP_URL))
    ])

    # 5-qator: Mavzular ro'yxatiga qaytish
    buttons.append([
        InlineKeyboardButton(text="⬅️ Boshqa mavzu tanlash", callback_data="dlg_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
