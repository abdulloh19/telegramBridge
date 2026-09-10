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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REMINDERS_FILE = DATA_DIR / "reminders.json"

# Toshkent vaqt mintaqasi (UTC+5)
TZ_TASHKENT = timezone(timedelta(hours=5))


def get_reminder_notification_keyboard(rem_id: str) -> InlineKeyboardMarkup:
    """Eslatma kelganda chiqariladigan [✅ Bajarildi] va [⏳ Keyin bajaraman] tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Bajarildi", callback_data=f"rc_done_{rem_id}"),
            InlineKeyboardButton(text="⏳ Keyin bajaraman", callback_data=f"rc_later_{rem_id}")
        ]
    ])


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
            "status": "pending",  # pending, postponed, completed, cancelled
            "created_at": now.strftime("%d.%m.%Y %H:%M"),
            "notify_count_today": 0,
            "last_notify_date": "",
            "last_notify_timestamp": 0,
            "completed_at": None,
            "postponed_at": None
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
    def get_categorized_reminders(cls, user_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """Foydalanuvchining eslatmalarini toifalar bo'yicha ajratib beradi."""
        reminders = _load_all_reminders()
        user_rems = [r for r in reminders if r.get("user_id") == user_id]

        pending = [r for r in user_rems if r.get("status") == "pending"]
        postponed = [r for r in user_rems if r.get("status") == "postponed"]
        completed = [r for r in user_rems if r.get("status") == "completed"]

        pending.sort(key=lambda x: x.get("due_timestamp", 0))
        postponed.sort(key=lambda x: x.get("due_timestamp", 0))
        completed.sort(key=lambda x: x.get("due_timestamp", 0), reverse=True)

        return {
            "pending": pending,
            "postponed": postponed,
            "completed": completed
        }

    @classmethod
    def mark_reminder_completed(cls, user_id: Optional[int], reminder_id: str) -> Optional[Dict[str, Any]]:
        """Foydalanuvchi 'Bajarildi' deb tanlaganda vazifani completed holatiga o'tkazish."""
        reminders = _load_all_reminders()
        target = None
        for r in reminders:
            if r.get("id") == reminder_id and (user_id is None or r.get("user_id") == user_id):
                r["status"] = "completed"
                r["completed_at"] = datetime.now(TZ_TASHKENT).strftime("%d.%m.%Y %H:%M")
                target = r
                break

        if target:
            _save_all_reminders(reminders)
            logger.info(f"Eslatma 'bajarildi' deb belgilandi: {reminder_id}")
        return target

    @classmethod
    def mark_reminder_postponed(cls, user_id: Optional[int], reminder_id: str) -> Optional[Dict[str, Any]]:
        """Foydalanuvchi 'Keyin bajaraman' deb tanlaganda vazifani postponed holatiga o'tkazish."""
        reminders = _load_all_reminders()
        target = None
        for r in reminders:
            if r.get("id") == reminder_id and (user_id is None or r.get("user_id") == user_id):
                r["status"] = "postponed"
                r["postponed_at"] = datetime.now(TZ_TASHKENT).strftime("%d.%m.%Y %H:%M")
                target = r
                break

        if target:
            _save_all_reminders(reminders)
            logger.info(f"Eslatma 'keyin bajariladigan' deb belgilandi: {reminder_id}")
        return target

    @classmethod
    def cancel_reminder(cls, user_id: int, reminder_id: str) -> bool:
        """Eslatmani bekor qilish."""
        reminders = _load_all_reminders()
        found = False

        for r in reminders:
            if r.get("id") == reminder_id and (user_id is None or r.get("user_id") == user_id):
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
        Vaqti yetgan yoki qayta eslatilishi kerak bo'lgan barcha vazifalarni yuboradi.

        Qoidalar:
        1. status in ['completed', 'cancelled'] bo'lsa aslo yuborilmaydi.
        2. Sana o'zgarganda bugungi eslatmalar hisoblagichi (notify_count_today) 0 ga tushadi.
        3. Bir kunda ko'pi bilan 2 marta eslatma yuboriladi (notify_count_today < 2).
        4. Har soatda eslatiladi (kamida 3600 soniya o'tgan bo'lishi shart).
        5. Har bir eslatmada [✅ Bajarildi] va [⏳ Keyin bajaraman] tugmalari chiqadi.
        """
        reminders = _load_all_reminders()
        now_dt = datetime.now(TZ_TASHKENT)
        now_ts = int(now_dt.timestamp())
        today_str = now_dt.strftime("%Y-%m-%d")

        triggered_count = 0

        for r in reminders:
            status = r.get("status", "pending")
            # Bajarilgan yoki bekor qilinganlarni chetlab o'tamiz
            if status in ["completed", "cancelled"]:
                continue

            # Yangi kun bo'lsa hisoblagichni 0 ga tushiramiz
            if r.get("last_notify_date") != today_str:
                r["notify_count_today"] = 0

            notify_count = r.get("notify_count_today", 0)
            # Kunlik limit: maksimal 2 marta
            if notify_count >= 2:
                continue

            due_ts = r.get("due_timestamp", 0)
            last_notify_ts = r.get("last_notify_timestamp", 0)

            should_notify = False
            is_rereminder = False

            # 1-holat: Hali birinchi marta eslatilmagan va vaqti kelgan
            if notify_count == 0 and due_ts <= now_ts:
                should_notify = True
                is_rereminder = False

            # 2-holat: Kechiktirilgan (postponed) yoki javob berilmagan (pending overdue) vazifaga 1 soatdan keyin qayta eslatma (2-marta)
            elif notify_count == 1 and (status == "postponed" or (status == "pending" and due_ts <= now_ts)):
                # Kamida 1 soat (3600 soniya) o'tganmi?
                if (now_ts - last_notify_ts) >= 3600:
                    should_notify = True
                    is_rereminder = True

            if should_notify:
                chat_id = r.get("chat_id")
                title = r.get("title", "Eslatma")
                due_dt = r.get("due_datetime", "")
                rem_id = r.get("id")

                if is_rereminder:
                    header = "⏰ <b>QAYTA ESLATMA (Bugungi 2-eslatma)</b> 🔔"
                    note = "<i>Ushbu vazifa hali bajarilmadi. Iltimos, holatini belgilang:</i>"
                else:
                    header = "⏰ <b>ESLATMA VAQTI KELDI!</b> 🔔"
                    note = "<i>Iltimos, vazifa holatini belgilang:</i>"

                msg_text = (
                    f"{header}\n\n"
                    f"📌 <b>Vazifa:</b> <b>{title}</b>\n"
                    f"🕒 <b>Belgilangan vaqt:</b> <code>{due_dt}</code>\n\n"
                    f"{note}"
                )

                kb = get_reminder_notification_keyboard(rem_id)

                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=msg_text,
                        parse_mode="HTML",
                        reply_markup=kb
                    )
                    r["notify_count_today"] = notify_count + 1
                    r["last_notify_date"] = today_str
                    r["last_notify_timestamp"] = now_ts
                    r["last_sent_at"] = now_dt.strftime("%d.%m.%Y %H:%M:%S")
                    triggered_count += 1
                    logger.info(f"Eslatma yuborildi ({r['notify_count_today']}-marta): {rem_id} -> {chat_id}")
                except Exception as e:
                    logger.warning(f"Eslatma yuborishda xatolik ({chat_id}): {e}")
                    r["last_error"] = str(e)

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
