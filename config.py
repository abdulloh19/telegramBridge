import os
from pathlib import Path
from dotenv import load_dotenv

# .env yoki .env.example faylini yuklash
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"

# Avval .env dan, agar topilmasa .env.example dan o'qish
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
if not os.getenv("BOT_TOKEN") and ENV_EXAMPLE_PATH.exists():
    load_dotenv(dotenv_path=ENV_EXAMPLE_PATH)


# Asosiy sozlamalar
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Telegram Userbot / Account Cleaner sozlamalari
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "").strip()
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "").strip()


# Admin ID larini olish va int to'plamiga aylantirish
admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS: set[int] = set()
if admin_ids_raw:
    for raw_id in admin_ids_raw.split(","):
        raw_id = raw_id.strip()
        if raw_id.isdigit():
            ADMIN_IDS.add(int(raw_id))

# Bot hamma uchun ochiq bo'lishi (Public Mode)
ALLOW_ALL_USERS = os.getenv("ALLOW_ALL_USERS", "true").lower() in ("true", "1", "yes")

# Boshlang'ich ishchi papka
raw_work_dir = os.getenv("DEFAULT_WORKING_DIR", "").strip()
if raw_work_dir and Path(raw_work_dir).exists():
    DEFAULT_WORKING_DIR = Path(raw_work_dir).resolve()
else:
    DEFAULT_WORKING_DIR = BASE_DIR.resolve()


# AI Sozlamalari
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "gemini-3.6-flash").strip()
if any(old in AI_MODEL for old in ("2.5", "2.0", "1.5", "1.0", "flash-lite-preview")):
    AI_MODEL = "gemini-3.6-flash"

# Terminal Sozlamalari
SHELL_TYPE = os.getenv("SHELL_TYPE", "powershell").lower().strip()
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "120"))
MAX_OUTPUT_LENGTH = int(os.getenv("MAX_OUTPUT_LENGTH", "3800"))

# Foydalanuvchilarning joriy ishchi papkalari xotirasi (User Session Storage)
_user_sessions: dict[int, Path] = {}


def get_user_cwd(user_id: int) -> Path:
    """Foydalanuvchining joriy ishchi katalogini qaytaradi."""
    if user_id not in _user_sessions:
        _user_sessions[user_id] = DEFAULT_WORKING_DIR
    return _user_sessions[user_id]


def set_user_cwd(user_id: int, path: Path | str) -> Path:
    """Foydalanuvchining joriy ishchi katalogini o'zgartiradi."""
    resolved_path = Path(path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Katalog topilmadi: {resolved_path}")
    if not resolved_path.is_dir():
        raise NotADirectoryError(f"Ko'rsatilgan yo'l papka emas: {resolved_path}")
    _user_sessions[user_id] = resolved_path
    return resolved_path


def is_admin(user_id: int) -> bool:
    """Foydalanuvchiga botdan foydalanish ruxsati borligini tekshiradi."""
    if ALLOW_ALL_USERS:
        return True
    if not ADMIN_IDS:
        return False
    return user_id in ADMIN_IDS


def is_super_admin(user_id: int) -> bool:
    """Foydalanuvchi asosiy admin ekanligini tekshiradi."""
    if not ADMIN_IDS:
        return ALLOW_ALL_USERS
    return user_id in ADMIN_IDS


def update_env_variable(key: str, value: str):
    """
    .env faylida ko'rsatilgan kalitni yangilaydi yoki qo'shadi,
    hamda joriy Python muhitini darhol yangilaydi.
    """
    global TELEGRAM_API_ID, TELEGRAM_API_HASH, GEMINI_API_KEY, BOT_TOKEN

    key = key.strip()
    value = str(value).strip()
    os.environ[key] = value

    if key == "TELEGRAM_API_ID":
        TELEGRAM_API_ID = value
    elif key == "TELEGRAM_API_HASH":
        TELEGRAM_API_HASH = value
    elif key == "GEMINI_API_KEY":
        GEMINI_API_KEY = value
    elif key == "BOT_TOKEN":
        BOT_TOKEN = value

    lines = []
    found = False
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            pass

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")

    try:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        pass


def save_telegram_api_credentials(api_id: str, api_hash: str):
    """TELEGRAM_API_ID va TELEGRAM_API_HASH ni .env ga avtomatik saqlaydi."""
    update_env_variable("TELEGRAM_API_ID", api_id)
    update_env_variable("TELEGRAM_API_HASH", api_hash)



