import asyncio
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# Loyiha papkasini sys.path ga qo'shish
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from utils.logger import logger
from utils.helpers import format_bytes, get_file_icon, truncate_text, split_text_chunks
from services.file_service import FileService
from services.terminal_service import TerminalService
from services.system_service import SystemService
from services.ai_service import AIService
from keyboards.inline import get_path_token, get_path_from_token, file_browser_keyboard, file_actions_keyboard
import config


async def run_all_tests():
    print("========================================")
    print("🧪 Telegram Dev Bridge - Test Tekshiruvi")
    print("========================================")

    # 1. Helpers Test
    print("\n[1] Helpers tekshiruvi...")
    assert format_bytes(1024) == "1.0 KB", f"format_bytes xatosi: {format_bytes(1024)}"
    assert format_bytes(1048576) == "1.0 MB"
    assert get_file_icon(Path("test.py")) == "🐍"
    assert get_file_icon(Path("test.html")) == "🌐"
    assert truncate_text("Hello World", max_length=50) == "Hello World"
    assert "..." in truncate_text("Hello " * 1000, max_length=100)

    chunks = split_text_chunks("A" * 5000, chunk_size=2000)
    assert len(chunks) == 3
    print("✅ Helpers muvaffaqiyatli o'tdi.")

    # 2. Keyboards & Token Cache Test
    print("\n[2] Inline Keyboards & Token Cache tekshiruvi...")
    sample_path = BASE_DIR / "requirements.txt"
    token = get_path_token(sample_path)
    recovered = get_path_from_token(token)
    assert recovered == sample_path, f"Token cache xatosi: {recovered} != {sample_path}"
    kb = file_actions_keyboard(sample_path)
    assert kb is not None
    print("✅ Keyboards & Token Cache muvaffaqiyatli o'tdi.")

    # 3. FileService Test
    print("\n[3] FileService tekshiruvi...")
    items = FileService.list_directory(BASE_DIR)
    assert len(items) > 0, "Papka ro'yxati bo'sh chiqdi"
    file_names = [it["name"] for it in items]
    assert "bot.py" in file_names or "requirements.txt" in file_names, "Asosiy fayllar topilmadi"

    # Temp fayl bilan ishlash testi
    temp_file = BASE_DIR / "scratch" / "_test_sample.txt"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    await FileService.write_file(temp_file, "Line 1\nHello World\nLine 3", overwrite=True)
    content, is_trunc = await FileService.read_file(temp_file)
    assert "Hello World" in content
    assert not is_trunc

    # Replace in file testi
    replaced = await FileService.replace_in_file(temp_file, "Hello World", "Hello Gemini")
    assert replaced is True
    content_after, _ = await FileService.read_file(temp_file)
    assert "Hello Gemini" in content_after

    # Search testi
    matches = FileService.search_code("Hello Gemini", BASE_DIR / "scratch")
    assert len(matches) > 0, "Qidiruv natija bermadi"

    # Tree testi
    tree = FileService.get_tree_structure(BASE_DIR, max_depth=1)
    assert len(tree) > 0

    # Delete testi
    FileService.delete_item(temp_file)
    assert not temp_file.exists(), "Fayl o'chirilmadi"
    print("✅ FileService barcha testlari muvaffaqiyatli o'tdi.")

    # 4. TerminalService Test
    print("\n[4] TerminalService tekshiruvi...")
    test_cmd = "echo TelegramDevBridge_OK"
    cmd_res = await TerminalService.execute_command(test_cmd, cwd=BASE_DIR, timeout=10)
    assert cmd_res["exit_code"] == 0, f"Buyruq xatolik qaytardi: {cmd_res}"
    assert "TelegramDevBridge_OK" in cmd_res["stdout"], f"Stdout kutilganidek emas: {cmd_res['stdout']}"
    assert cmd_res["duration"] >= 0
    print("✅ TerminalService muvaffaqiyatli o'tdi.")

    # 5. SystemService Test
    print("\n[5] SystemService tekshiruvi...")
    summary = SystemService.get_system_summary()
    assert "cpu_percent" in summary
    assert "ram_total" in summary
    assert len(summary["disks"]) > 0
    print(f"   OS: {summary['os_name']}, Hostname: {summary['hostname']}")
    print(f"   CPU: {summary['cpu_percent']}%, RAM: {summary['ram_used']}/{summary['ram_total']} ({summary['ram_percent']}%)")
    print(f"   Uptime: {summary['uptime']}")

    procs = SystemService.get_top_processes(limit=3, sort_by="memory")
    assert len(procs) > 0
    print(f"   Top RAM jarayon: {procs[0]['name']} ({procs[0]['memory_formatted']})")

    # Screenshot testi
    screenshot_bytes = SystemService.capture_screenshot()
    assert screenshot_bytes.getbuffer().nbytes > 1000, "Skrinshot olinmadi yoki bo'sh"
    print(f"   Skrinshot hajmi: {format_bytes(screenshot_bytes.getbuffer().nbytes)}")
    print("✅ SystemService muvaffaqiyatli o'tdi.")

    # 6. AIService Test
    print("\n[6] AIService tekshiruvi...")
    is_conf = AIService.is_configured()
    print(f"   AI sozlangan holat: {is_conf}")
    print("✅ AIService moduli tekshirildi.")

    print("\n========================================")
    print("🎉 Barcha testlar 100% muvaffaqiyatli o'tdi!")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
