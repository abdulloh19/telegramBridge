import os
import sys
import io
import time
import platform
import subprocess
from datetime import datetime, timedelta
import psutil
from utils.helpers import format_bytes
from utils.logger import logger


class SystemService:
    """Kompyuter monitoringi, skrinshot va operatsion tizim boshqaruvi xizmati."""

    @staticmethod
    def get_system_summary() -> dict:
        """Tizim resurslari (CPU, RAM, Disk, Uptime) haqida to'liq ma'lumot beradi."""
        # 1. CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count_logical
        cpu_freq = psutil.cpu_freq()
        cpu_freq_str = f"{round(cpu_freq.current / 1000, 2)} GHz" if cpu_freq else "N/A"

        # 2. RAM
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # 3. Disklar
        disks = []
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt' and 'cdrom' in part.opts or part.fstype == '':
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "total": format_bytes(usage.total),
                    "used": format_bytes(usage.used),
                    "free": format_bytes(usage.free),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                continue

        # 4. Batareya (noutbuklar uchun)
        battery = psutil.sensors_battery()
        battery_info = None
        if battery:
            battery_info = {
                "percent": round(battery.percent, 1),
                "power_plugged": battery.power_plugged,
            }

        # 5. Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_delta = datetime.now() - boot_time
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{days} kun {hours} soat {minutes} daqiqa" if days > 0 else f"{hours} soat {minutes} daqiqa"

        return {
            "os_name": f"{platform.system()} {platform.release()}",
            "os_version": platform.version(),
            "hostname": platform.node(),
            "processor": platform.processor() or "Noma'lum",
            "cpu_percent": cpu_percent,
            "cpu_cores": f"{cpu_count_physical} fizik / {cpu_count_logical} mantiqiy",
            "cpu_freq": cpu_freq_str,
            "ram_total": format_bytes(ram.total),
            "ram_used": format_bytes(ram.used),
            "ram_free": format_bytes(ram.available),
            "ram_percent": ram.percent,
            "swap_total": format_bytes(swap.total),
            "swap_used": format_bytes(swap.used),
            "swap_percent": swap.percent,
            "disks": disks,
            "battery": battery_info,
            "uptime": uptime_str,
            "boot_time": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def capture_screenshot() -> io.BytesIO:
        """
        Kompyuter monitorining ayni damdagi skrinshotini oladi.
        Agar ekran qulflangan yoki nofaol bo'lsa, chiroyli axborot rasmi qaytaradi.
        """
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                output = io.BytesIO()
                img.save(output, format="JPEG", quality=85, optimize=True)
                output.seek(0)
                return output

        except Exception as e1:
            logger.warning(f"MSS orqali skrinshot olishda xatolik ({e1}), Pillow ImageGrab ga o'tilmoqda")
            try:
                from PIL import ImageGrab

                img = ImageGrab.grab(all_screens=True)
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=85)
                output.seek(0)
                return output
            except Exception as e2:
                logger.warning(f"ImageGrab orqali skrinshot olinmadi ({e2}), axborot rasmi generatsiya qilinmoqda")
                from PIL import Image, ImageDraw

                img = Image.new("RGB", (1280, 720), color=(20, 24, 33))
                draw = ImageDraw.Draw(img)
                draw.rectangle([(20, 20), (1260, 700)], outline=(66, 133, 244), width=3)
                draw.text((60, 80), "TELEGRAM DEV BRIDGE - DESKTOP STATUS", fill=(255, 255, 255))
                draw.text((60, 160), "⚠️ Monitor hozirda nofaol yoki ekran qulflangan (Lock / Headless rejim).", fill=(255, 180, 50))
                draw.text((60, 240), f"Qurilma: {platform.node()}", fill=(200, 200, 200))
                draw.text((60, 300), f"Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill=(200, 200, 200))
                draw.text((60, 360), f"CPU: {psutil.cpu_percent()}% | RAM: {psutil.virtual_memory().percent}%", fill=(100, 220, 100))
                draw.text((60, 440), "Kompyuter ekrani yoqilganda yoki tizimga kirilganda", fill=(160, 160, 160))
                draw.text((60, 480), "haqiqiy ish stoli monitori avtomatik ko'rinadi.", fill=(160, 160, 160))

                output = io.BytesIO()
                img.save(output, format="JPEG", quality=90)
                output.seek(0)
                return output


    @staticmethod
    def get_top_processes(limit: int = 8, sort_by: str = "memory") -> list[dict]:
        """Eng ko'p resurs iste'mol qilayotgan jarayonlar ro'yxatini qaytaradi."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
            try:
                pinfo = proc.info
                if not pinfo['name']:
                    continue
                mem_bytes = pinfo['memory_info'].rss if pinfo['memory_info'] else 0
                processes.append({
                    "pid": pinfo['pid'],
                    "name": pinfo['name'],
                    "cpu_percent": pinfo['cpu_percent'] or 0.0,
                    "memory_percent": round(pinfo['memory_percent'] or 0.0, 1),
                    "memory_formatted": format_bytes(mem_bytes),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if sort_by == "cpu":
            processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        else:
            processes.sort(key=lambda x: x["memory_percent"], reverse=True)

        return processes[:limit]

    @staticmethod
    def kill_process(pid: int) -> tuple[bool, str]:
        """PID bo'yicha jarayonni majburiy to'xtatadi."""
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.kill()
            return True, f"Jarayon muvaffaqiyatli to'xtatildi: {name} (PID: {pid})"
        except psutil.NoSuchProcess:
            return False, f"Bunday PID topilmadi: {pid}"
        except psutil.AccessDenied:
            return False, f"Jarayonni to'xtatish uchun ruxsat yetarli emas (Administrator huquqi kerak): {pid}"
        except Exception as e:
            return False, f"Xatolik yuz berdi: {str(e)}"

    @staticmethod
    def lock_workstation() -> tuple[bool, str]:
        """Kompyuter ekranini masofadan qulflaydi (Lock WorkStation)."""
        try:
            if sys.platform == "win32":
                subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True, check=True)
                return True, "🔒 Kompyuter ekrani muvaffaqiyatli qulflandi (Lock)!"
            else:
                return False, "Ushbu buyruq faqat Windows tizimida ishlaydi."
        except Exception as e:
            return False, f"Ekranni qulflashda xatolik: {str(e)}"

    @staticmethod
    def show_windows_notification(title: str, message: str) -> tuple[bool, str]:
        """Kompyuter ekranida Windows Toast bildirishnomasi chiqaradi."""
        try:
            if sys.platform == "win32":
                clean_title = title.replace('"', '`"')
                clean_msg = message.replace('"', '`"')
                ps_script = f"""
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                $template = @"
                <toast>
                    <visual>
                        <binding template="ToastText02">
                            <text id="1">{clean_title}</text>
                            <text id="2">{clean_msg}</text>
                        </binding>
                    </visual>
                </toast>
"@
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $xml.LoadXml($template)
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Telegram Dev Bridge").Show($toast)
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], shell=True)
                return True, "🔔 Bildirishnoma kompyuter ekranida ko'rsatildi!"
            return False, "Faqat Windows tizimida mavjud"
        except Exception as e:
            return False, f"Bildirishnoma chiqarishda xatolik: {str(e)}"
