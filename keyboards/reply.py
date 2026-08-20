from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Doimiy pastki tezkor menyu tugmalari."""
    keyboard = [
        [
            KeyboardButton(text="📁 Fayllar"),
            KeyboardButton(text="💻 Terminal"),
        ],
        [
            KeyboardButton(text="🤖 AI Agent"),
            KeyboardButton(text="📊 Tizim Holati"),
        ],
        [
            KeyboardButton(text="📸 Skrinshot"),
            KeyboardButton(text="🧹 Hisobni Tozalash"),
        ],
        [
            KeyboardButton(text="⚡ Git Status"),
            KeyboardButton(text="⚙️ Sozlamalar / Yordam"),
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Buyruq yoki xabar yozing..."
    )
