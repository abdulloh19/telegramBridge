import uuid
from pathlib import Path
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Telegram callback_data 64 bayt chegarasi uchun qisqa ID larni keshda saqlash
_PATH_CACHE: dict[str, Path] = {}
_MAX_CACHE_SIZE = 1000


def get_path_token(path: Path) -> str:
    """Path uchun 8 belgili qisqa token qaytaradi va keshga saqlaydi."""
    global _PATH_CACHE
    if len(_PATH_CACHE) > _MAX_CACHE_SIZE:
        _PATH_CACHE.clear()

    # Avval mavjud tokenni qidirish
    for token, cached_path in _PATH_CACHE.items():
        if cached_path == path:
            return token

    token = uuid.uuid4().hex[:8]
    _PATH_CACHE[token] = path
    return token


def get_path_from_token(token: str) -> Path | None:
    """Qisqa tokendan Path obyektini tiklaydi."""
    return _PATH_CACHE.get(token)


def file_browser_keyboard(current_dir: Path, items: list[dict], page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    """Fayllar va papkalar bo'yicha sahifalangan interaktiv klaviatura."""
    buttons = []

    # 1. Ota papkaga o'tish tugmasi (agar disk ildizi bo'lmasa)
    has_parent = current_dir.parent != current_dir
    if has_parent:
        parent_token = get_path_token(current_dir.parent)
        buttons.append([
            InlineKeyboardButton(text="⬆️ [..] Ota papkaga chiqish", callback_data=f"dir:{parent_token}")
        ])

    # 2. Sahifalash hisobi
    total_items = len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total_items)
    page_items = items[start_idx:end_idx]

    # 3. Fayl va papka tugmalari
    for item in page_items:
        item_path = Path(item["path"])
        token = get_path_token(item_path)
        if item["is_dir"]:
            btn_text = f"📁 {item['name']}/"
            cb_data = f"dir:{token}"
        else:
            btn_text = f"{item['icon']} {item['name']} ({item['size_formatted']})"
            cb_data = f"file:{token}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])

    # 4. Sahifa navigatsiyasi (Oldingi / Keyingi)
    nav_row = []
    if page > 0:
        dir_token = get_path_token(current_dir)
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"page:{dir_token}:{page-1}"))
    
    nav_row.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="noop"))

    if page < total_pages - 1:
        dir_token = get_path_token(current_dir)
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"page:{dir_token}:{page+1}"))

    if nav_row:
        buttons.append(nav_row)

    # 5. Tezkor amallar
    curr_token = get_path_token(current_dir)
    buttons.append([
        InlineKeyboardButton(text="➕ Yangi fayl", callback_data=f"newf:{curr_token}"),
        InlineKeyboardButton(text="📁 Yangi papka", callback_data=f"newd:{curr_token}"),
        InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"dir:{curr_token}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def file_actions_keyboard(file_path: Path) -> InlineKeyboardMarkup:
    """Alohida fayl uchun amallar klaviaturasi."""
    token = get_path_token(file_path)
    parent_token = get_path_token(file_path.parent)

    buttons = [
        [
            InlineKeyboardButton(text="👁️ Ko'rish (View)", callback_data=f"view:{token}"),
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"edit:{token}"),
        ],
        [
            InlineKeyboardButton(text="📥 Yuklab olish", callback_data=f"down:{token}"),
            InlineKeyboardButton(text="🗑️ O'chirish", callback_data=f"delreq:{token}"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI Kod Tahlili", callback_data=f"aiexp:{token}"),
            InlineKeyboardButton(text="🔧 AI Code Review", callback_data=f"airev:{token}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Papkaga qaytish", callback_data=f"dir:{parent_token}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_keyboard(item_path: Path) -> InlineKeyboardMarkup:
    """O'chirishni tasdiqlash klaviaturasi."""
    token = get_path_token(item_path)
    parent_token = get_path_token(item_path.parent)

    buttons = [
        [
            InlineKeyboardButton(text="✅ Ha, o'chirilsin!", callback_data=f"delyes:{token}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"dir:{parent_token}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def quick_terminal_keyboard() -> InlineKeyboardMarkup:
    """Tezkor terminal buyruqlari tugmalari."""
    buttons = [
        [
            InlineKeyboardButton(text="⚡ Git Status", callback_data="term:git status"),
            InlineKeyboardButton(text="🔄 Git Pull", callback_data="term:git pull"),
        ],
        [
            InlineKeyboardButton(text="🔍 Git Diff", callback_data="term:git diff"),
            InlineKeyboardButton(text="📦 Pip List", callback_data="term:pip list"),
        ],
        [
            InlineKeyboardButton(text="🧪 Python Tests", callback_data="term:pytest"),
            InlineKeyboardButton(text="🧹 Papka daraxti", callback_data="term_tree"),
        ]
    ]
def system_actions_keyboard() -> InlineKeyboardMarkup:
    """Tizim monitoringi va amallari klaviaturasi."""
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="sys_refresh"),
            InlineKeyboardButton(text="📸 Skrinshot", callback_data="sys_screenshot"),
        ],
        [
            InlineKeyboardButton(text="📋 Top RAM Jarayonlar", callback_data="sys_top_mem"),
            InlineKeyboardButton(text="⚡ Top CPU Jarayonlar", callback_data="sys_top_cpu"),
        ],
        [
            InlineKeyboardButton(text="🔒 Ekranni qulflash (Lock)", callback_data="sys_lock"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cleaner_config_keyboard() -> InlineKeyboardMarkup:
    """API sozlanmagan holatdagi klaviatura."""
    buttons = [
        [InlineKeyboardButton(text="⚙️ API_ID va API_HASH ni kiritish", callback_data="cl_set_api")],
        [InlineKeyboardButton(text="📖 my.telegram.org Yo'riqnomasi", callback_data="cl_help_api")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cleaner_login_methods_keyboard() -> InlineKeyboardMarkup:
    """Telegram hisobga kirish usullari."""
    buttons = [
        [InlineKeyboardButton(text="📷 QR Kod orqali kirish (Tezkor va oson)", callback_data="cl_login_qr")],
        [InlineKeyboardButton(text="📱 Telefon raqam orqali kirish", callback_data="cl_login_phone")],
        [InlineKeyboardButton(text="⚙️ API_ID va HASH ni kiritish / yangilash", callback_data="cl_set_api")],
        [InlineKeyboardButton(text="📖 my.telegram.org Yo'riqnomasi", callback_data="cl_help_api")],
        [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cl_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cleaner_main_keyboard(is_auth: bool = True) -> InlineKeyboardMarkup:
    """Telegram hisobni tozalash asosiy inline menyusi."""
    if not is_auth:
        return cleaner_login_methods_keyboard()

    buttons = [
        [
            InlineKeyboardButton(text="🗑️ O'chgan hisoblar (Deleted Accounts)", callback_data="cl_scan_deleted"),
        ],
        [
            InlineKeyboardButton(text="🚪 Nofaol Kanallar va Guruhlar", callback_data="cl_scan_channels"),
        ],
        [
            InlineKeyboardButton(text="⏱️ Eski Dialoglar (Old Chats)", callback_data="cl_scan_old"),
        ],
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="cl_refresh"),
            InlineKeyboardButton(text="🚪 Chiqish (Logout)", callback_data="cl_logout"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_clean_keyboard(action_type: str, count: int) -> InlineKeyboardMarkup:
    """Tozalashni tasdiqlash klaviaturasi."""
    buttons = [
        [
            InlineKeyboardButton(text=f"✅ Ha, barchasini tozalash ({count} ta)", callback_data=f"cl_do_{action_type}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cl_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def start_main_inline_keyboard() -> InlineKeyboardMarkup:
    """Bosh menyu uchun tezkor interaktiv inline tugmalar."""
    buttons = [
        [
            InlineKeyboardButton(text="📁 Fayllar Menejeri", callback_data="open_files"),
            InlineKeyboardButton(text="💻 Terminal", callback_data="open_terminal"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI Agent", callback_data="open_ai"),
            InlineKeyboardButton(text="📊 Tizim Holati", callback_data="sys_status"),
        ],
        [
            InlineKeyboardButton(text="🧹 Hisobni Tozalash", callback_data="open_cleaner"),
            InlineKeyboardButton(text="📥 Video Yuklash", callback_data="open_dl"),
        ],
        [
            InlineKeyboardButton(text="📸 Ekran Skrinshoti", callback_data="sys_screenshot"),
            InlineKeyboardButton(text="📖 Qo'llanma", callback_data="open_help"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pinpad_keyboard(current_code: str = "") -> InlineKeyboardMarkup:
    """Xavfsiz raqamli klaviatura (Telegram chat skanerini aylanib o'tish va kodni bloklanishdan saqlash uchun)."""
    display = ""
    for i in range(5):
        if i < len(current_code):
            display += f"{current_code[i]} "
        else:
            display += "• "
    display = display.strip()

    buttons = [
        [
            InlineKeyboardButton(text=f"🔑 Kod: [ {display} ]", callback_data="noop")
        ],
        [
            InlineKeyboardButton(text="1", callback_data="cl_pin:1"),
            InlineKeyboardButton(text="2", callback_data="cl_pin:2"),
            InlineKeyboardButton(text="3", callback_data="cl_pin:3"),
        ],
        [
            InlineKeyboardButton(text="4", callback_data="cl_pin:4"),
            InlineKeyboardButton(text="5", callback_data="cl_pin:5"),
            InlineKeyboardButton(text="6", callback_data="cl_pin:6"),
        ],
        [
            InlineKeyboardButton(text="7", callback_data="cl_pin:7"),
            InlineKeyboardButton(text="8", callback_data="cl_pin:8"),
            InlineKeyboardButton(text="9", callback_data="cl_pin:9"),
        ],
        [
            InlineKeyboardButton(text="⌫ O'chirish", callback_data="cl_pin:del"),
            InlineKeyboardButton(text="0", callback_data="cl_pin:0"),
            InlineKeyboardButton(text="🚀 Kirish", callback_data="cl_pin:submit"),
        ],
        [
            InlineKeyboardButton(text="📷 QR Kod orqali", callback_data="cl_login_qr"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cl_cancel"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


