import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import aiofiles
from utils.helpers import format_bytes, get_file_icon
from utils.logger import logger


class FileService:
    """Fayllar tizimi bilan xavfsiz va qulay ishlash xizmati."""

    @staticmethod
    def resolve_path(base_dir: Path, target_path: str | Path) -> Path:
        """Berilgan yo'lni to'liq mutlaq Path obyektiga aylantiradi."""
        target = Path(target_path)
        if target.is_absolute():
            return target.resolve()
        return (base_dir / target).resolve()

    @staticmethod
    def list_directory(dir_path: Path, show_hidden: bool = False) -> list[dict]:
        """
        Katalogdagi fayl va papkalar ro'yxatini qaytaradi.
        Tartiblash: avval papkalar, so'ng fayllar alifbo bo'yicha.
        """
        if not dir_path.exists():
            raise FileNotFoundError(f"Papka topilmadi: {dir_path}")
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Ko'rsatilgan yo'l papka emas: {dir_path}")

        items = []
        try:
            entries = list(dir_path.iterdir())
        except PermissionError:
            raise PermissionError(f"Papkani o'qish uchun ruxsat yetarli emas: {dir_path}")

        for entry in entries:
            if not show_hidden and entry.name.startswith("."):
                continue

            try:
                stat = entry.stat()
                size_str = "-" if entry.is_dir() else format_bytes(stat.st_size)
                mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                items.append({
                    "name": entry.name,
                    "path": str(entry.resolve()),
                    "is_dir": entry.is_dir(),
                    "size_bytes": stat.st_size if not entry.is_dir() else 0,
                    "size_formatted": size_str,
                    "icon": get_file_icon(entry),
                    "modified": mod_time,
                })
            except (PermissionError, FileNotFoundError):
                continue

        # Papkalarni birinchi, keyin fayllarni saralash
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return items

    @staticmethod
    async def read_file(file_path: Path, max_length: Optional[int] = None) -> tuple[str, bool]:
        """
        Fayl tarkibini asinxron o'qiydi.
        Qaytaradi: (matn, qisqartirildimi)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Fayl topilmadi: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Ko'rsatilgan yo'l oddiy fayl emas: {file_path}")

        # Matnli fayl ekanligini tekshirish uchun o'qish
        try:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8", errors="replace") as f:
                content = await f.read()
        except Exception as e:
            logger.error(f"Faylni o'qishda xatolik ({file_path}): {e}")
            raise

        is_truncated = False
        if max_length and len(content) > max_length:
            content = content[:max_length]
            is_truncated = True

        return content, is_truncated

    @staticmethod
    async def write_file(file_path: Path, content: str, overwrite: bool = True) -> int:
        """Faylga matn yozadi yoki yangilaydi."""
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"Fayl allaqachon mavjud: {file_path}")

        # Ota papkalar mavjud bo'lmasa yaratish
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            await f.write(content)

        return len(content)

    @staticmethod
    async def append_to_file(file_path: Path, content: str) -> None:
        """Fayl oxiriga yangi qator qo'shadi."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, mode="a", encoding="utf-8") as f:
            await f.write(content)

    @staticmethod
    async def replace_in_file(file_path: Path, target: str, replacement: str) -> bool:
        """Fayl ichidagi ko'rsatilgan matnni yangisiga almashtiradi."""
        content, _ = await FileService.read_file(file_path)
        if target not in content:
            return False
        new_content = content.replace(target, replacement, 1)
        await FileService.write_file(file_path, new_content, overwrite=True)
        return True

    @staticmethod
    def create_directory(dir_path: Path) -> Path:
        """Yangi papka yaratadi."""
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @staticmethod
    def delete_item(path: Path) -> str:
        """Fayl yoki papkani o'chiradi."""
        if not path.exists():
            raise FileNotFoundError(f"Topilmadi: {path}")

        if path.is_dir():
            shutil.rmtree(path)
            return "Papka to'liq o'chirildi"
        else:
            path.unlink()
            return "Fayl o'chirildi"

    @staticmethod
    def search_code(query: str, root_dir: Path, max_matches: int = 25) -> list[dict]:
        """Berilgan katalogdagi fayllar ichidan matn/kod qidiradi."""
        matches = []
        ignored_dirs = {".git", ".idea", ".vscode", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]

            for file_name in files:
                if len(matches) >= max_matches:
                    break

                file_path = Path(root) / file_name
                try:
                    # Katta fayllarni o'tkazib yuborish (> 2MB)
                    if file_path.stat().st_size > 2 * 1024 * 1024:
                        continue

                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                matches.append({
                                    "file": str(file_path.relative_to(root_dir)),
                                    "abs_path": str(file_path),
                                    "line": line_num,
                                    "content": line.strip()[:150]
                                })
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    continue

        return matches

    @staticmethod
    def get_tree_structure(root_dir: Path, max_depth: int = 2, current_depth: int = 0) -> str:
        """Papkalar daraxti ko'rinishini hosil qiladi."""
        if current_depth > max_depth or not root_dir.is_dir():
            return ""

        ignored_dirs = {".git", ".idea", ".vscode", "node_modules", "__pycache__", "venv", ".venv"}
        lines = []

        try:
            entries = sorted(list(root_dir.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            for entry in entries:
                if entry.name in ignored_dirs or entry.name.startswith("."):
                    continue

                indent = "  " * current_depth
                icon = get_file_icon(entry)
                lines.append(f"{indent}{icon} {entry.name}")

                if entry.is_dir() and current_depth < max_depth:
                    sub_tree = FileService.get_tree_structure(entry, max_depth, current_depth + 1)
                    if sub_tree:
                        lines.append(sub_tree)
        except PermissionError:
            pass

        return "\n".join(lines)
