import asyncio
import locale
import os
import sys
import time
from pathlib import Path
from typing import Optional
from config import SHELL_TYPE, COMMAND_TIMEOUT
from utils.logger import logger


class TerminalService:
    """PowerShell, CMD va Bash buyruqlarini asinxron xavfsiz bajarish xizmati."""

    @staticmethod
    def _build_command(command: str) -> list[str]:
        """Tizim turiga mos qobiq (shell) buyrug'ini tuzadi."""
        if sys.platform == "win32":
            if SHELL_TYPE == "cmd":
                return ["cmd.exe", "/c", command]
            else:
                return [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", command
                ]
        else:
            shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
            return [shell, "-c", command]

    @staticmethod
    async def execute_command(
        command: str,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """
        Terminal buyrug'ini berilgan papkada asinxron tarzda bajaradi.
        
        Qaytaradi: {
            "stdout": str,
            "stderr": str,
            "exit_code": int,
            "duration": float,
            "timed_out": bool,
            "cwd": str,
            "changed_dir": Optional[str]
        }
        """
        timeout_sec = timeout or COMMAND_TIMEOUT
        working_dir = str(cwd) if cwd else os.getcwd()
        trimmed = command.strip()

        # 1. 'cd' buyrug'ini dastur darajasida navigatsiya qilish
        if trimmed == "cd" or trimmed.startswith("cd ") or trimmed == "cd.." or trimmed.startswith("cd..") or trimmed.startswith("cd/") or trimmed.startswith("cd\\"):
            if trimmed == "cd":
                target_dir = Path.home()
            elif trimmed == "cd.." or trimmed.startswith("cd.."):
                parent_dir = Path(working_dir).parent
                target_dir = parent_dir
            else:
                raw_target = trimmed.split(maxsplit=1)[1].strip().strip('"').strip("'")
                target_dir = (Path(working_dir) / raw_target).resolve()

            if target_dir.exists() and target_dir.is_dir():
                return {
                    "stdout": f"📁 Joriy ishchi katalog o'zgartirildi:\n{target_dir}",
                    "stderr": "",
                    "exit_code": 0,
                    "duration": 0.01,
                    "timed_out": False,
                    "cwd": str(target_dir),
                    "changed_dir": str(target_dir),
                }
            else:
                return {
                    "stdout": "",
                    "stderr": f"❌ Papka topilmadi: {target_dir}",
                    "exit_code": 1,
                    "duration": 0.01,
                    "timed_out": False,
                    "cwd": working_dir,
                    "changed_dir": None,
                }

        cmd_args = TerminalService._build_command(command)
        start_time = time.time()
        logger.info(f"Terminal buyrug'i boshlandi [CWD: {working_dir}]: {command}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=0 if sys.platform != "win32" else 0x08000000  # CREATE_NO_WINDOW
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=float(timeout_sec)
                )
                duration = round(time.time() - start_time, 2)

                stdout_str = TerminalService._decode_output(stdout_bytes)
                stderr_str = TerminalService._decode_output(stderr_bytes)

                logger.info(f"Buyruq yakunlandi ({duration}s, exit code: {process.returncode})")

                return {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": process.returncode if process.returncode is not None else 0,
                    "duration": duration,
                    "timed_out": False,
                    "cwd": working_dir,
                    "changed_dir": None,
                }

            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception as kill_err:
                    logger.warning(f"Jarayonni to'xtatishda xatolik: {kill_err}")

                duration = round(time.time() - start_time, 2)
                logger.warning(f"Buyruq vaqti tugadi (Timeout {timeout_sec}s): {command}")

                return {
                    "stdout": "",
                    "stderr": f"⏱️ Buyruq bajarilish vaqti ({timeout_sec} soniya) tugadi va majburiy to'xtatildi.",
                    "exit_code": -1,
                    "duration": duration,
                    "timed_out": True,
                    "cwd": working_dir,
                    "changed_dir": None,
                }

        except Exception as e:
            # Agar PowerShell topilmasa yoki xatolik bo'lsa, CMD orqali qayta urinib ko'rish
            if sys.platform == "win32" and SHELL_TYPE != "cmd":
                try:
                    logger.warning(f"PowerShell xatoligi ({e}), CMD orqali bajarilmoqda...")
                    fallback_args = ["cmd.exe", "/c", command]
                    process = await asyncio.create_subprocess_exec(
                        *fallback_args,
                        cwd=working_dir,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        creationflags=0x08000000
                    )
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(),
                        timeout=float(timeout_sec)
                    )
                    duration = round(time.time() - start_time, 2)
                    return {
                        "stdout": TerminalService._decode_output(stdout_bytes),
                        "stderr": TerminalService._decode_output(stderr_bytes),
                        "exit_code": process.returncode or 0,
                        "duration": duration,
                        "timed_out": False,
                        "cwd": working_dir,
                        "changed_dir": None,
                    }
                except Exception as fallback_err:
                    logger.error(f"Fallback CMD ham ishlamadi: {fallback_err}")

            duration = round(time.time() - start_time, 2)
            logger.error(f"Buyruqni bajarishda tizim xatosi: {e}")
            return {
                "stdout": "",
                "stderr": f"Tizim xatoligi: {str(e)}",
                "exit_code": 1,
                "duration": duration,
                "timed_out": False,
                "cwd": working_dir,
                "changed_dir": None,
            }

    @staticmethod
    def _decode_output(raw_bytes: bytes) -> str:
        """Har xil terminal kodirovkalarini (UTF-8, CP866, CP1251, CP1252, OS locale) xavfsiz dekod qiladi."""
        if not raw_bytes:
            return ""

        pref_enc = locale.getpreferredencoding(False) or "utf-8"
        encodings = ["utf-8", "cp866", "cp1251", pref_enc, "cp1252", "latin-1"]

        for encoding in encodings:
            try:
                return raw_bytes.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue

        return raw_bytes.decode("utf-8", errors="replace")

