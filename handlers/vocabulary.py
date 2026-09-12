"""Yodlangan so'zlar progressini ko'rsatish handlerlari."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.vocabulary_service import VocabularyService


router = Router()


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Rus tili", callback_data="mywords:ru"),
        InlineKeyboardButton(text="🇬🇧 Ingliz tili", callback_data="mywords:en"),
    ]])


def progress_text(user_id: int, language: str) -> str:
    language_name = {"ru": "Rus tili", "en": "Ingliz tili"}[language]
    count = VocabularyService.get_learned_count(user_id, language)
    return (
        f"📚 <b>{language_name}</b> bo'yicha yodlagan so'zlaringiz: <b>{count} ta</b>\n\n"
        "Hisob faqat tanlangan til uchun alohida yuritiladi."
    )


@router.message(Command("mywords"))
@router.message(F.text == "📚 Yodlangan so'zlarim")
async def show_language_picker(message: Message) -> None:
    await message.answer(
        "📚 <b>Yodlangan so'zlarim</b>\n\nTilni tanlang — shu til bo'yicha aniq son ko'rsatiladi.",
        parse_mode="HTML", reply_markup=language_keyboard(),
    )


@router.callback_query(F.data == "open_mywords")
async def show_language_picker_callback(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "📚 <b>Yodlangan so'zlarim</b>\n\nTilni tanlang — shu til bo'yicha aniq son ko'rsatiladi.",
        parse_mode="HTML", reply_markup=language_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"mywords:ru", "mywords:en"}))
async def show_language_progress(callback: CallbackQuery) -> None:
    language = callback.data.split(":", maxsplit=1)[1]
    await callback.message.edit_text(
        progress_text(callback.from_user.id, language), parse_mode="HTML", reply_markup=language_keyboard(),
    )
    await callback.answer()
