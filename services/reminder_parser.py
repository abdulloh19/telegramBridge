"""
Ko'p Vaqtli Eslatmalar Tahlilchisi (Reminder Parser)
=====================================================
Bitta matn yoki ovozli xabardagi barcha turli vaqtlar va vazifalarni ajratib oladi.
1-qavat: Google Gemini 3.6 Flash (Tabiiy nutqni 100% aniqlikda tushunadi)
2-qavat: Mahalliy Qoidali / Regex Parser (Zahira usul)
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Toshkent vaqt mintaqasi (UTC+5)
TZ_TASHKENT = timezone(timedelta(hours=5))


def get_current_tashkent_time() -> datetime:
    """Toshkent bo'yicha joriy vaqt."""
    return datetime.now(TZ_TASHKENT)


def _compute_due_timestamp(date_str: str, time_str: str) -> int:
    """YYYY-MM-DD va HH:MM dan Unix timestamp hisoblaydi (Toshkent vaqti)."""
    dt_naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_aware = dt_naive.replace(tzinfo=TZ_TASHKENT)
    return int(dt_aware.timestamp())


async def parse_with_gemini(text: str) -> List[Dict[str, Any]]:
    """Gemini 3.6 Flash orqali barcha vaqtlarni aniqlash."""
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return []

        from google import genai
        client = genai.Client(api_key=api_key)

        now = get_current_tashkent_time()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")

        prompt = f"""Quyidagi matndan barcha eslatma/vazifalar va ularga tegishli vaqtlarni ajratib oling.
Hozirgi sana va vaqt: {now_str} (Toshkent vaqti, UTC+5).

Muhim qoidalar:
1. Agar matnda bir nechta vaqt ko'rsatilgan bo'lsa (masalan: "Soat 10:00 da majlis, keyin 14:00 da dars"), HAR BIRINI alohida obyekt qilib ajrating.
2. Agar sana aytilmagan bo'lsa, bugungi sana deb hisoblang. Agar aytilgan vaqt bugungi hozirgi vaqtdan o'tib ketgan bo'lsa (va "bugun" deb ta'kidlanmagan bo'lsa), ertangi kunga o'tkazing.
3. Vaqtni qat'iy "HH:MM" (24 soatlik formatda, masalan "10:00", "14:30", "20:00") formatida yozing.
4. "title" ga qisqa va aniq nima qilish kerakligini yozing (masalan "Majlis", "Dars", "Doktorga borish").
5. Faqat toza JSON array formatida javob bering, boshqa hech qanday izoh qo'shmang. Agar vaqt topilmasa [] qaytaring.

Format:
[
  {{"title": "Majlis", "date": "YYYY-MM-DD", "time": "HH:MM"}},
  {{"title": "Dars", "date": "YYYY-MM-DD", "time": "HH:MM"}}
]

Matn: {text}"""

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.6-flash",
            contents=prompt
        )

        if not response or not response.text:
            return []

        raw = response.text.strip()
        # JSON blokini tozalash (agar ```json ... ``` bo'lsa)
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        data = json.loads(raw)
        if not isinstance(data, list):
            return []

        results = []
        for item in data:
            title = item.get("title", "").strip()
            date_str = item.get("date", "").strip()
            time_str = item.get("time", "").strip()

            if not title or not date_str or not time_str:
                continue

            # Vaqt formati tekshiruvi (HH:MM)
            t_match = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
            if not t_match:
                continue
            h, m = int(t_match.group(1)), int(t_match.group(2))
            time_str = f"{h:02d}:{m:02d}"

            due_ts = _compute_due_timestamp(date_str, time_str)
            results.append({
                "title": title,
                "date": date_str,
                "time": time_str,
                "due_datetime": f"{date_str} {time_str}",
                "due_timestamp": due_ts,
            })

        return results

    except Exception as e:
        logger.warning(f"Gemini ko'p vaqtli tahlilida xatolik: {e}")
        return []


def parse_with_regex(text: str) -> List[Dict[str, Any]]:
    """Mahalliy Regex/Qoidali parser (Gemini ishlamay qolganda zahira usul)."""
    now = get_current_tashkent_time()
    results = []

    # Matnni qismlarga ajratamiz (vergul, nuqta, "keyin", "so'ng", "va")
    delimiters = r"[,;\n]|\s+(?:keyin|so'ng|va|undanso'ng|then|потом|а\s+затем)\s+"
    parts = re.split(delimiters, text, flags=re.IGNORECASE)

    time_regex = re.compile(
        r"(?:soat\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(?:da|de|ga)?(?:\s*(?:am|pm))?",
        re.IGNORECASE
    )

    base_date = now.date()
    text_lower = text.lower()
    if "ertaga" in text_lower or "tomorrow" in text_lower or "завтра" in text_lower:
        base_date = base_date + timedelta(days=1)
    elif "indin" in text_lower or "послезавтра" in text_lower:
        base_date = base_date + timedelta(days=2)

    for p in parts:
        clean_p = p.strip()
        if not clean_p:
            continue

        match = time_regex.search(clean_p)
        if match:
            h_str, m_str = match.group(1), match.group(2)
            hour = int(h_str)
            minute = int(m_str) if m_str else 0

            # 24-soatlik normalizatsiya (agar "kechqurun" bo'lsa)
            p_lower = clean_p.lower()
            if any(w in p_lower for w in ["kechqurun", "kechki", "pm", "вечером"]) and hour < 12:
                hour += 12
            elif any(w in p_lower for w in ["kunduzi", "tushdan keyin"]) and 1 <= hour <= 6:
                hour += 12

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                # Sarlavhani ajratish (vaqt so'zlarini olib tashlash)
                title = time_regex.sub("", clean_p).strip()
                title = re.sub(r"\b(?:bugun|ertaga|indin|soat|da|de|ga)\b", "", title, flags=re.IGNORECASE).strip()
                title = re.sub(r"\s+", " ", title).strip()

                if not title:
                    title = "Eslatma"

                time_str = f"{hour:02d}:{minute:02d}"
                date_str = base_date.strftime("%Y-%m-%d")
                due_ts = _compute_due_timestamp(date_str, time_str)

                # Agar o'tib ketgan bo'lsa va sana aniq aytilmagan bo'lsa, ertaga
                if due_ts < int(now.timestamp()) and base_date == now.date():
                    next_date = base_date + timedelta(days=1)
                    date_str = next_date.strftime("%Y-%m-%d")
                    due_ts = _compute_due_timestamp(date_str, time_str)

                results.append({
                    "title": title[:60],
                    "date": date_str,
                    "time": time_str,
                    "due_datetime": f"{date_str} {time_str}",
                    "due_timestamp": due_ts,
                })

    return results


async def parse_multiple_reminders(text: str) -> List[Dict[str, Any]]:
    """
    Bitta xabardan barcha vaqtlar va eslatmalarni ajratadi.
    Birinchi Gemini AI, so'ng Regex fallback.
    """
    if not text or len(text.strip()) < 3:
        return []

    # 1. Gemini AI orqali aniqlash
    results = await parse_with_gemini(text)
    if results:
        return results

    # 2. Mahalliy Regex orqali aniqlash
    results = parse_with_regex(text)
    return results


def format_reminders_summary(reminders: List[Dict[str, Any]]) -> str:
    """Aniqlangan eslatmalarni chiroyli ro'yxat qilib beradi."""
    if not reminders:
        return ""

    now = get_current_tashkent_time()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    num_icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = []

    for i, r in enumerate(reminders):
        icon = num_icons[i] if i < len(num_icons) else f"{i+1}."
        d_str = r.get("date", "")
        t_str = r.get("time", "")
        title = r.get("title", "Eslatma")

        day_label = ""
        if d_str == today_str:
            day_label = " (Bugun)"
        elif d_str == tomorrow_str:
            day_label = " (Ertaga)"
        else:
            day_label = f" ({d_str})"

        lines.append(f"{icon} <b>{t_str}</b>{day_label} — <i>{title}</i>")

    return "\n".join(lines)
