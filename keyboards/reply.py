from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from config import WEBAPP_URL


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Doimiy pastki tezkor menyu tugmalari."""
    keyboard = [
        [
            KeyboardButton(text="🚀 Super Ilova (25 ta so'z)", web_app=WebAppInfo(url=WEBAPP_URL)),
        ],
        [
            KeyboardButton(text="🗣️ Jonli Dialoglar"),
            KeyboardButton(text="📥 Video Yuklash"),
        ],
        [
            KeyboardButton(text="🎵 MP3 Yuklash"),
            KeyboardButton(text="🧹 Hisobni Tozalash"),
        ],
        [
            KeyboardButton(text="ℹ️ Qo'llanma / Yordam"),
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Video linkini tashlang yoki menyudan tanlang..."
    )
