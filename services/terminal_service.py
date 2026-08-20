import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional
from config import SHELL_TYPE, COMMAND_TIMEOUT
from utils.logger import logger


class TerminalService:
    """PowerShell va CMD buyruqlarini asinxron xavfsiz bajarish xizmati."""

    @staticmethod
    def _build_command(command: str) -> list[str]:
        """Tizim turiga mos qobiq (shell) buyrug'ini tuzadi."""
        if sys.platform == "win32":
            if SHELL_TYPE == "powershell":
                return [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command", command
                ]
            else:
                return ["cmd.exe", "/c", command]
        else:
            return ["/bin/bash", "-c", command]

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
            "cwd": str
        }
        """
        timeout_sec = timeout or COMMAND_TIMEOUT
        working_dir = str(cwd) if cwd else os.getcwd()
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

                # Windows kodirovkalarini xavfsiz ochish
                stdout_str = TerminalService._decode_output(stdout_bytes)
                stderr_str = TerminalService._decode_output(stderr_bytes)

                logger.info(f"Buyruq yakunlandi ({duration}s, exit code: {process.returncode})")

                return {
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                    "exit_code": process.returncode or 0,
                    "duration": duration,
                    "timed_out": False,
                    "cwd": working_dir,
                }

            except asyncio.TimeoutError:
                # Jarayon belgilangan vaqt ichida tugamasa to'xtatish
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
                }

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            logger.error(f"Buyruqni bajarishda tizim xatosi: {e}")
            return {
                "stdout": "",
                "stderr": f"Tizim xatoligi: {str(e)}",
                "exit_code": 1,
                "duration": duration,
                "timed_out": False,
                "cwd": working_dir,
            }

    @staticmethod
    def _decode_output(raw_bytes: bytes) -> str:
        """Har xil terminal kodirovkalarini (UTF-8, CP1251, CP866, CP1252) xavfsiz dekod qiladi."""
        if not raw_bytes:
            return ""

        for encoding in ["utf-8", "cp1251", "cp866", "cp1252", "latin-1"]:
            try:
                return raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw_bytes.decode("utf-8", errors="replace")
