import os, logging, asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def create_calendar_event(
    summary,
    description="",
    date_str=None,
    time_str=None,
    duration_minutes=60,
    calendar_id="primary",
):
    """
    Google Calendar da yangi event yaratadi.

    .env sozlamalari:
      GOOGLE_CALENDAR_CREDENTIALS_JSON  - service_account.json fayl yo'li
        YOKI
      GOOGLE_CALENDAR_TOKEN_JSON        - oauth token.json fayl yo'li
    """
    try:
        from googleapiclient.discovery import build  # pip install google-api-python-client
        from google.oauth2 import service_account     # pip install google-auth
        import google.auth

        # Credentials
        sa_path = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", "")
        token_path = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON", "")

        if sa_path and os.path.exists(sa_path):
            SCOPES = ["https://www.googleapis.com/auth/calendar"]
            creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
        elif token_path and os.path.exists(token_path):
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(token_path)
        else:
            logger.warning(
                "Google Calendar credentials topilmadi! "
                ".env da GOOGLE_CALENDAR_CREDENTIALS_JSON yoki GOOGLE_CALENDAR_TOKEN_JSON kerak."
            )
            return {"success": False, "error": "no_credentials"}

        service = await asyncio.to_thread(
            build, "calendar", "v3", credentials=creds
        )

        # Sanani tayyorlash
        now = datetime.now()
        if date_str:
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                event_date = now.date()
        else:
            event_date = now.date()

        if time_str:
            try:
                hour, minute = map(int, time_str.split(":"))
            except Exception:
                hour, minute = 9, 0
        else:
            hour, minute = 9, 0

        start_dt = datetime(
            event_date.year, event_date.month, event_date.day, hour, minute
        )
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        tz = os.getenv("TZ", "Asia/Tashkent")

        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": tz},
        }

        def _insert():
            return service.events().insert(calendarId=calendar_id, body=event_body).execute()

        result = await asyncio.to_thread(_insert)

        event_link = result.get("htmlLink", "")
        event_id   = result.get("id", "")
        logger.info("Calendar event yaratildi: " + event_id)
        return {"success": True, "event_id": event_id, "link": event_link, "summary": summary}

    except ImportError:
        logger.warning(
            "google-api-python-client topilmadi. "
            "pip install google-api-python-client google-auth"
        )
        return {"success": False, "error": "library_missing"}
    except Exception as e:
        logger.error("Calendar xatosi: " + str(e))
        return {"success": False, "error": str(e)}


async def create_event_from_text_info(text_info):
    """
    stt_service.extract_datetime_from_text() natijasidan event yaratadi.
    text_info: {"date": "2026-09-11", "time": "10:00", "description": "uchrashuv", ...}
    """
    if not text_info:
        return {"success": False, "error": "no_datetime_found"}

    return await create_calendar_event(
        summary=text_info.get("description", "Telegram Eslatma")[:80],
        description="Telegram ovozli xabardan avtomatik qo'shildi.",
        date_str=text_info.get("date"),
        time_str=text_info.get("time"),
    )
