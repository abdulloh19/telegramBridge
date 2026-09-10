"""
Eslatmalar Xizmati va Skeduler (Reminder Service & Background Scheduler)
=======================================================================
1. data/reminders.json faylida eslatmalarni saqlaydi (server reboot bo'lsa ham yo'qolmaydi)
2. Har 15 soniyada kutayotgan eslatmalarni tekshiradi
3. Vaqti yetgan zahoti Telegram orqali foydalanuvchiga aniq ogohlantirish yuboradi
"""

import os
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from aiogram import Bot

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REMINDERS_FILE = DATA_DIR / "reminders.json"

# Toshkent vaqt mintaqasi (UTC+5)
TZ_TASHKENT = timezone(timedelta(hours=5))


def _ensure_reminders_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not REMINDERS_FILE.exists():
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def _load_all_reminders() -> List[Dict[str, Any]]:
    _ensure_reminders_storage()
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"reminders.json o'qishda xatolik: {e}")
        return []


def _save_all_reminders(reminders: List[Dict[str, Any]]):
    _ensure_reminders_storage()
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"reminders.json saqlashda xatolik: {e}")


class ReminderService:
    @classmethod
    def add_reminder(
        cls,
        user_id: int,
        chat_id: int,
        title: str,
        due_datetime: str,
        due_timestamp: int,
        source: str = "voice"
    ) -> Dict[str, Any]:
        """Bitta yangi eslatma qo'shish."""
        reminders = _load_all_reminders()

        now = datetime.now(TZ_TASHKENT)
        rem_id = f"rem_{int(time.time() * 1000)}_{len(reminders)}"

        new_rem = {
            "id": rem_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "title": title.strip(),
            "due_datetime": due_datetime,
            "due_timestamp": due_timestamp,
            "source": source,
            "status": "pending",  # pending, sent, cancelled
            "created_at": now.strftime("%d.%m.%Y %H:%M")
        }

        reminders.append(new_rem)
        _save_all_reminders(reminders)
        logger.info(f"Yangi eslatma saqlandi: {rem_id} ({due_datetime} - {title})")
        return new_rem

    @classmethod
    def add_multiple_reminders(
        cls,
        user_id: int,
        chat_id: int,
        items: List[Dict[str, Any]],
        source: str = "voice"
    ) -> List[Dict[str, Any]]:
        """Bir nechta eslatmalarni birvarakay saqlash."""
        created = []
        for it in items:
            title = it.get("title", "Eslatma")
            due_dt = it.get("due_datetime", "")
            due_ts = it.get("due_timestamp", 0)

            if due_ts > 0:
                rem = cls.add_reminder(
                    user_id=user_id,
                    chat_id=chat_id,
                    title=title,
                    due_datetime=due_dt,
                    due_timestamp=due_ts,
                    source=source
                )
                created.append(rem)

        return created

    @classmethod
    def get_user_reminders(
        cls,
        user_id: int,
        status: Optional[str] = "pending"
    ) -> List[Dict[str, Any]]:
        """Foydalanuvchining eslatmalarini olish."""
        reminders = _load_all_reminders()
        user_rems = [r for r in reminders if r.get("user_id") == user_id]

        if status:
            user_rems = [r for r in user_rems if r.get("status") == status]

        # Eng yaqin vaqt bo'yicha saralash
        user_rems.sort(key=lambda x: x.get("due_timestamp", 0))
        return user_rems

    @classmethod
    def cancel_reminder(cls, user_id: int, reminder_id: str) -> bool:
        """Eslatmani bekor qilish."""
        reminders = _load_all_reminders()
        found = False

        for r in reminders:
            if r.get("id") == reminder_id and r.get("user_id") == user_id:
                r["status"] = "cancelled"
                found = True
                break

        if found:
            _save_all_reminders(reminders)
            logger.info(f"Eslatma bekor qilindi: {reminder_id}")
            return True
        return False

    @classmethod
    async def check_and_trigger_due_reminders(cls, bot: Bot) -> int:
        """
        Vaqti yetgan barcha eslatmalarni topib, Telegram orqali xabar yuboradi.
        """
        reminders = _load_all_reminders()
        now_ts = int(datetime.now(TZ_TASHKENT).timestamp())

        triggered_count = 0

        for r in reminders:
            if r.get("status") == "pending" and r.get("due_timestamp", 0) <= now_ts:
                chat_id = r.get("chat_id")
                title = r.get("title", "Eslatma")
                due_dt = r.get("due_datetime", "")

                msg_text = (
                    "⏰ <b>ESLATMA VAQTI KELDI!</b> 🔔\n\n"
                    f"📌 <b>Vazifa:</b> <b>{title}</b>\n"
                    f"🕒 <b>Belgilangan vaqt:</b> <code>{due_dt}</code>\n\n"
                    "<i>Ushbu eslatma sizning xabaringiz asosida o'z vaqtida yetkazildi.</i>"
                )

                try:
                    await bot.send_message(chat_id, msg_text, parse_mode="HTML")
                    r["status"] = "sent"
                    r["sent_at"] = datetime.now(TZ_TASHKENT).strftime("%d.%m.%Y %H:%M:%S")
                    triggered_count += 1
                    logger.info(f"Eslatma muvaffaqiyatli yuborildi: {r.get('id')} -> {chat_id}")
                except Exception as e:
                    logger.warning(f"Eslatma yuborishda xatolik ({chat_id}): {e}")
                    # Agar foydalanuvchi botni bloklagan bo'lsa yoki xato bo'lsa
                    r["status"] = "failed"
                    r["error"] = str(e)

        if triggered_count > 0:
            _save_all_reminders(reminders)

        return triggered_count


async def start_reminder_scheduler(bot: Bot):
    """
    Orqa fonda har 15 soniyada eslatmalarni tekshirib boruvchi doimiy jarayon.
    """
    logger.info("⏰ Eslatmalar skeduleri (Background Scheduler) ishga tushdi.")

    while True:
        try:
            await ReminderService.check_and_trigger_due_reminders(bot)
        except Exception as e:
            logger.error(f"Skeduler siklida xatolik: {e}")

        # Har 15 soniyada bir marta tekshiriladi
        await asyncio.sleep(15)
