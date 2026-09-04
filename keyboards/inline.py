from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def cleaner_config_keyboard() -> InlineKeyboardMarkup:
    """API sozlanmagan holatdagi klaviatura."""
    buttons = [
        [InlineKeyboardButton(text="⚙️ API_ID va API_HASH ni kiritish", callback_data="cl_set_api")],
        [InlineKeyboardButton(text="📖 my.telegram.org Yo'riqnomasi", callback_data="cl_help_api")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cleaner_login_methods_keyboard() -> InlineKeyboardMarkup:
    """Telegram hisobga kirish usullari."""
    buttons = [
        [InlineKeyboardButton(text="📷 QR Kod orqali kirish (100% ishonchli & tez)", callback_data="cl_login_qr")],
        [InlineKeyboardButton(text="📱 Telefon raqam orqali kirish", callback_data="cl_login_phone")],
        [InlineKeyboardButton(text="🔑 StringSession orqali kirish (0 soniyada)", callback_data="cl_login_string")],
        [InlineKeyboardButton(text="⚙️ API_ID va HASH ni kiritish / yangilash", callback_data="cl_set_api")],
        [InlineKeyboardButton(text="📖 my.telegram.org Yo'riqnomasi", callback_data="cl_help_api")],
        [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cl_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cleaner_main_keyboard(is_auth: bool = True) -> InlineKeyboardMarkup:
    """Telegram hisobni tozalash asosiy inline menyusi."""
    if not is_auth:
        return cleaner_login_methods_keyboard()

    buttons = [
        [
            InlineKeyboardButton(text="🗑️ O'chgan hisoblar (Deleted Accounts)", callback_data="cl_scan_deleted"),
        ],
        [
            InlineKeyboardButton(text="🚪 Nofaol Kanallar va Guruhlar", callback_data="cl_scan_channels"),
        ],
        [
            InlineKeyboardButton(text="⏱️ Eski Dialoglar (Old Chats)", callback_data="cl_scan_old"),
        ],
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="cl_refresh"),
            InlineKeyboardButton(text="🚪 Chiqish (Logout)", callback_data="cl_logout"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_clean_keyboard(action_type: str, count: int) -> InlineKeyboardMarkup:
    """Tozalashni tasdiqlash klaviaturasi."""
    buttons = [
        [
            InlineKeyboardButton(text=f"✅ Ha, barchasini tozalash ({count} ta)", callback_data=f"cl_do_{action_type}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cl_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def start_main_inline_keyboard() -> InlineKeyboardMarkup:
    """Bosh menyu uchun inline tugmalar."""
    buttons = [
        [
            InlineKeyboardButton(text="📥 Video Yuklash", callback_data="open_dl"),
            InlineKeyboardButton(text="🎵 MP3 Yuklash", callback_data="open_mp3"),
        ],
        [
            InlineKeyboardButton(text="🧹 Telegram Hisobni Tozalash", callback_data="open_cleaner"),
        ],
        [
            InlineKeyboardButton(text="📖 Qo'llanma", callback_data="open_help"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pinpad_keyboard(current_code: str = "") -> InlineKeyboardMarkup:
    """Xavfsiz raqamli klaviatura (Telegram kodini bloklanishdan saqlash uchun)."""
    display = ""
    for i in range(5):
        if i < len(current_code):
            display += f"{current_code[i]} "
        else:
            display += "• "
    display = display.strip()

    buttons = [
        [
            InlineKeyboardButton(text=f"🔑 Kod: [ {display} ]", callback_data="noop")
        ],
        [
            InlineKeyboardButton(text="1", callback_data="cl_pin:1"),
            InlineKeyboardButton(text="2", callback_data="cl_pin:2"),
            InlineKeyboardButton(text="3", callback_data="cl_pin:3"),
        ],
        [
            InlineKeyboardButton(text="4", callback_data="cl_pin:4"),
            InlineKeyboardButton(text="5", callback_data="cl_pin:5"),
            InlineKeyboardButton(text="6", callback_data="cl_pin:6"),
        ],
        [
            InlineKeyboardButton(text="7", callback_data="cl_pin:7"),
            InlineKeyboardButton(text="8", callback_data="cl_pin:8"),
            InlineKeyboardButton(text="9", callback_data="cl_pin:9"),
        ],
        [
            InlineKeyboardButton(text="⌫ O'chirish", callback_data="cl_pin:del"),
            InlineKeyboardButton(text="0", callback_data="cl_pin:0"),
            InlineKeyboardButton(text="🚀 Kirish", callback_data="cl_pin:submit"),
        ],
        [
            InlineKeyboardButton(text="📩 SMS orqali qayta so'rash", callback_data="cl_resend_sms"),
            InlineKeyboardButton(text="📷 QR Kod orqali", callback_data="cl_login_qr"),
        ],
        [
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cl_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def media_format_choice_keyboard(token: str) -> InlineKeyboardMarkup:
    """Video yoki havola qabul qilinganda format tanlash tugmalari."""
    buttons = [
        [
            InlineKeyboardButton(text="🎬 Video (MP4)", callback_data=f"dl_fmt:video:{token}"),
            InlineKeyboardButton(text="🎵 Audio (MP3 320kbps)", callback_data=f"dl_fmt:audio:{token}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def media_action_keyboard(token: str) -> InlineKeyboardMarkup:
    """Yuklangan video ostidagi amallar klaviaturasi."""
    buttons = [
        [
            InlineKeyboardButton(text="🎵 MP3 Audioni Yuklab Olish (320kbps)", callback_data=f"conv_mp3:{token}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
