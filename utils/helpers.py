import html
from pathlib import Path

# Fayl turlari uchun emoji piktogrammalar
FILE_ICONS = {
    # Dasturlash tillari
    ".py": "🐍",
    ".js": "📜",
    ".ts": "🔷",
    ".jsx": "⚛️",
    ".tsx": "⚛️",
    ".html": "🌐",
    ".css": "🎨",
    ".scss": "🎨",
    ".java": "☕",
    ".cpp": "⚙️",
    ".c": "⚙️",
    ".cs": "🎯",
    ".go": "🐹",
    ".rs": "🦀",
    ".php": "🐘",
    ".rb": "💎",
    ".kt": "🟪",
    ".swift": "🐦",
    ".sql": "🗄️",
    ".sh": "🐚",
    ".bat": "⚡",
    ".ps1": "⚡",
    # Ma'lumotlar va konfiguratsiya
    ".json": "📋",
    ".yaml": "⚙️",
    ".yml": "⚙️",
    ".xml": "📄",
    ".toml": "⚙️",
    ".ini": "⚙️",
    ".env": "🔒",
    ".md": "📝",
    ".txt": "📄",
    ".log": "📑",
    ".csv": "📊",
    # Media va arxivlar
    ".png": "🖼️",
    ".jpg": "🖼️",
    ".jpeg": "🖼️",
    ".gif": "🖼️",
    ".svg": "🎨",
    ".mp4": "🎥",
    ".mp3": "🎵",
    ".zip": "📦",
    ".tar": "📦",
    ".gz": "📦",
    ".rar": "📦",
    ".7z": "📦",
    ".pdf": "📕",
}


def get_file_icon(path: Path) -> str:
    """Fayl yoki papka kengaytmasiga qarab mos emojini qaytaradi."""
    if path.is_dir():
        if path.name.startswith("."):
            return "📁🔒"
        return "📁"
    return FILE_ICONS.get(path.suffix.lower(), "📄")


def format_bytes(size: float | int) -> str:
    """Baytlarni inson tushunadigan formatga (B, KB, MB, GB) o'tkazadi."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def escape_html(text: str) -> str:
    """Telegram HTML formati uchun maxsus belgilarni xavfsiz qiladi."""
    return html.escape(str(text), quote=False)


def truncate_text(text: str, max_length: int = 3800, suffix: str = "\n... [Natija qisqartirildi]") -> str:
    """Matnni ko'rsatilgan uzunlikka moslab qisqartiradi."""
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return text[:max_length]
    return text[: max_length - len(suffix)] + suffix



def split_text_chunks(text: str, chunk_size: int = 3800) -> list[str]:
    """Uzun matnni Telegram xabari chegaralariga bo'lib beradi."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    current_chunk = []
    current_length = 0

    for line in text.splitlines(keepends=True):
        if current_length + len(line) > chunk_size:
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_length = 0
            # Agar bitta qatorning o'zi chunk_size dan katta bo'lsa
            while len(line) > chunk_size:
                chunks.append(line[:chunk_size])
                line = line[chunk_size:]
        current_chunk.append(line)
        current_length += len(line)

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks
