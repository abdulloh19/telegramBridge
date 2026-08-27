from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Doimiy pastki tezkor menyu tugmalari."""
    keyboard = [
        [
            KeyboardButton(text="📥 Video Yuklash"),
            KeyboardButton(text="🧠 AI Video Konspekt"),
        ],
        [
            KeyboardButton(text="🧹 Hisobni Tozalash"),
            KeyboardButton(text="ℹ️ Qo'llanma / Yordam"),
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Video linkini tashlang yoki menyudan tanlang..."
    )
