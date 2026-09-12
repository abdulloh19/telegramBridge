"""Foydalanuvchilarning til bo'yicha yodlagan so'zlari progressini saqlash."""

import json
from pathlib import Path
from typing import Iterable

from utils.logger import logger


VOCABULARY_FILE = Path(__file__).resolve().parent.parent / "data" / "learned_words.json"
SUPPORTED_LANGUAGES = {"ru", "en"}


class VocabularyService:
    """Yodlangan so'zlarni foydalanuvchi va til kesimida boshqaradi."""

    @staticmethod
    def _load() -> dict:
        if not VOCABULARY_FILE.exists():
            return {}
        try:
            with VOCABULARY_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as error:
            logger.warning(f"Yodlangan so'zlar faylini o'qib bo'lmadi: {error}")
            return {}

    @staticmethod
    def _save(data: dict) -> None:
        try:
            VOCABULARY_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_file = VOCABULARY_FILE.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            temp_file.replace(VOCABULARY_FILE)
        except OSError as error:
            logger.error(f"Yodlangan so'zlarni saqlab bo'lmadi: {error}")
            raise

    @classmethod
    def get_learned_count(cls, user_id: int, language: str) -> int:
        """Tanlangan til uchun noyob yodlangan so'zlar sonini qaytaradi."""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Qo'llab-quvvatlanmaydigan til: {language}")
        words = cls._load().get(str(user_id), {}).get(language, [])
        if not isinstance(words, list):
            return 0
        return len({str(word).strip() for word in words if str(word).strip()})

    @classmethod
    def mark_word_learned(cls, user_id: int, language: str, word_id: str) -> bool:
        """So'zni yodlangan deb belgilaydi; yangi bo'lsa ``True`` qaytaradi."""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Qo'llab-quvvatlanmaydigan til: {language}")
        normalized_word_id = str(word_id).strip()
        if not normalized_word_id:
            raise ValueError("So'z identifikatori bo'sh bo'lishi mumkin emas")

        data = cls._load()
        user_words = data.setdefault(str(user_id), {})
        learned_words = user_words.setdefault(language, [])
        if not isinstance(learned_words, list):
            learned_words = []
            user_words[language] = learned_words
        if normalized_word_id in learned_words:
            return False

        learned_words.append(normalized_word_id)
        cls._save(data)
        return True

    @classmethod
    def set_learned_words(cls, user_id: int, language: str, word_ids: Iterable[str]) -> None:
        """Dars moduli uchun progressni noyob so'zlar ro'yxati bilan yangilaydi."""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Qo'llab-quvvatlanmaydigan til: {language}")
        unique_words = list(dict.fromkeys(str(word).strip() for word in word_ids if str(word).strip()))
        data = cls._load()
        data.setdefault(str(user_id), {})[language] = unique_words
        cls._save(data)
