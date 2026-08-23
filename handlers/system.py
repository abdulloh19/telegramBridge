import io
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.system_service import SystemService
from keyboards.inline import system_actions_keyboard
from utils.helpers import escape_html
from utils.logger import logger

router = Router()


class BroadcastStates(StatesGroup):
    waiting_for_broadcast_text = State()


def _format_status_text(info: dict) -> str:
    """Tizim ma'lumotlarini chiroyli HTML formatga soladi."""
    cpu_bar = "🟩" * int(info["cpu_percent"] // 10) + "⬜" * (10 - int(info["cpu_percent"] // 10))
    ram_bar = "🟦" * int(info["ram_percent"] // 10) + "⬜" * (10 - int(info["ram_percent"] // 10))

    disks_text = ""
    for d in info["disks"]:
        d_bar = "🟨" * int(d["percent"] // 10) + "⬜" * (10 - int(d["percent"] // 10))
        disks_text += (
            f"  • <b>{escape_html(d['mountpoint'])}</b> [{d_bar}] {d['percent']}%\n"
            f"    Band: {d['used']} / {d['total']} (Bo'sh: {d['free']})\n"
        )

    battery_text = ""
    if info["battery"]:
        b_icon = "🔌 Quvvatlanmoqda" if info["battery"]["power_plugged"] else "🔋 Batareyada"
        battery_text = f"🔋 <b>Batareya:</b> {info['battery']['percent']}% ({b_icon})\n"

    return (
        f"📊 <b>Kompyuter Tizim Statistikasi</b>\n\n"
        f"💻 <b>Qurilma:</b> <code>{escape_html(info['hostname'])}</code>\n"
        f"🖥️ <b>OS:</b> {escape_html(info['os_name'])}\n"
        f"⚙️ <b>Protsessor:</b> {escape_html(info['processor'])}\n"
        f"⏱️ <b>Ishlash vaqti (Uptime):</b> {info['uptime']}\n\n"
        f"⚡ <b>CPU Bandligi:</b> {info['cpu_percent']}%\n"
        f"[{cpu_bar}] ({info['cpu_cores']}, {info['cpu_freq']})\n\n"
        f"🧠 <b>RAM Xotira:</b> {info['ram_percent']}%\n"
        f"[{ram_bar}]\n"
        f"Band: {info['ram_used']} / {info['ram_total']} (Bo'sh: {info['ram_free']})\n\n"
        f"💾 <b>Disk Xotiralari:</b>\n{disks_text}\n"
        f"{battery_text}"
        f"🕒 <i>Yuklangan vaqti: {info['boot_time']}</i>"
    )


@router.message(Command("status"), StateFilter("*"))
@router.message(Command("sysinfo"), StateFilter("*"))
@router.message(F.text == "📊 Tizim Holati", StateFilter("*"))
async def cmd_system_status(message: Message, state: FSMContext):
    """Tizim holatini ko'rish."""
    await state.clear()
    info = SystemService.get_system_summary()
    text = _format_status_text(info)
    await message.answer(text, parse_mode="HTML", reply_markup=system_actions_keyboard())


@router.message(Command("screenshot"), StateFilter("*"))
@router.message(F.text == "📸 Skrinshot", StateFilter("*"))
async def cmd_screenshot(message: Message, state: FSMContext):
    """Kompyuter monitoridan skrinshot olish va yuborish."""
    await state.clear()
    status_msg = await message.answer("📸 Skrinshot olinmoqda...")
    try:
        image_stream = SystemService.capture_screenshot()
        photo = BufferedInputFile(image_stream.getvalue(), filename="screenshot.jpg")
        await message.answer_photo(photo, caption="📸 <b>Kompyuter ekrani skrinshoti</b>", parse_mode="HTML")
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Skrinshot olishda xatolik: {e}")
        await status_msg.edit_text(f"❌ Skrinshot olishda xatolik: {str(e)}")


@router.message(Command("processes"), StateFilter("*"))
async def cmd_processes(message: Message, state: FSMContext):
    """Jarayonlar ro'yxatini ko'rish."""
    await state.clear()
    procs = SystemService.get_top_processes(limit=10, sort_by="memory")
    text_lines = ["📋 <b>Eng ko'p xotira (RAM) sarflayotgan jarayonlar:</b>\n"]
    for p in procs:
        text_lines.append(
            f"• <b>{escape_html(p['name'])}</b> (PID: <code>{p['pid']}</code>)\n"
            f"  RAM: {p['memory_formatted']} ({p['memory_percent']}%) | CPU: {p['cpu_percent']}%\n"
        )
    text_lines.append("\n<i>Jarayonni to'xtatish uchun: /kill &lt;pid&gt;</i>")
    await message.answer("\n".join(text_lines), parse_mode="HTML")


@router.message(Command("kill"))
async def cmd_kill_process(message: Message):
    """Jarayonni to'xtatish."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Foydalanish: <code>/kill &lt;PID_raqami&gt;</code>\nMasalan: <code>/kill 1234</code>", parse_mode="HTML")
        return

    pid = int(args[1].strip())
    ok, result = SystemService.kill_process(pid)
    prefix = "✅" if ok else "❌"
    await message.answer(f"{prefix} {result}")


@router.message(Command("lock"))
async def cmd_lock(message: Message):
    """Kompyuter ekranini bloklash."""
    ok, result = SystemService.lock_workstation()
    prefix = "🔒" if ok else "❌"
    await message.answer(f"{prefix} {result}")


@router.message(Command("notify"))
async def cmd_notify(message: Message):
    """Windows ekraniga xabar chiqarish."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Foydalanish: <code>/notify &lt;xabar_matni&gt;</code>", parse_mode="HTML")
        return

    msg_text = args[1].strip()
    ok, result = SystemService.show_windows_notification("Telegram Dev Bridge", msg_text)
    prefix = "🔔" if ok else "❌"
    await message.answer(f"{prefix} {result}")


@router.message(Command("send"))
async def cmd_send_message(message: Message, bot: Bot):
    """Alohida foydalanuvchiga bot nomidan xabar yuborish."""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "📨 <b>Foydalanuvchiga bot nomidan xabar yuborish:</b>\n\n"
            "Format: <code>/send &lt;user_id&gt; &lt;xabar_matni&gt;</code>\n"
            "Masalan: <code>/send 123456789 Assalomu alaykum!</code>",
            parse_mode="HTML"
        )
        return

    target_id = parts[1].strip()
    msg_content = parts[2].strip()

    try:
        dest = int(target_id) if target_id.lstrip("-").isdigit() else target_id
        await bot.send_message(dest, msg_content, parse_mode="HTML")
        await message.answer(f"✅ Xabar <code>{escape_html(target_id)}</code> ga muvaffaqiyatli yuborildi!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xabar yuborishda xatolik: {escape_html(str(e))}")


@router.message(Command("dm"))
async def cmd_direct_user_message(message: Message):
    """Ulangan shaxsiy Telegram hisobingiz nomidan to'g'ridan-to'g'ri foydalanuvchiga yozish."""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "👤 <b>Shaxsiy hisobingizdan (Userbot) xabar yuborish:</b>\n\n"
            "Format: <code>/dm &lt;@username yoki user_id yoki telefon&gt; &lt;xabar_matni&gt;</code>\n\n"
            "<b>Misollar:</b>\n"
            "• <code>/dm @username Salom, yaxshimisiz?</code>\n"
            "• <code>/dm 123456789 Salom!</code>\n"
            "• <code>/dm +998901234567 Salom!</code>",
            parse_mode="HTML"
        )
        return

    target_entity = parts[1].strip()
    msg_content = parts[2].strip()
    user_id = message.from_user.id

    from services.account_cleaner_service import AccountCleanerService
    if not await AccountCleanerService.is_authorized(user_id):
        await message.answer(
            "🔒 Ushbu buyruqni ishlatish uchun avval Telegram hisobingizga kiring (/cleaner).",
            parse_mode="HTML"
        )
        return

    try:
        client = await AccountCleanerService.get_client(user_id)
        dest = int(target_entity) if target_entity.lstrip("-").isdigit() else target_entity
        await client.send_message(dest, msg_content)
        await message.answer(f"✅ Shaxsiy hisobingizdan <b>{escape_html(target_entity)}</b> ga xabar yetkazildi!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xabar yuborishda xatolik: {escape_html(str(e))}")


@router.message(Command("broadcast"))
async def cmd_broadcast_message(message: Message, state: FSMContext, bot: Bot):
    """Barcha adminlarga va foydalanuvchilarga xabar yuborish."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await state.set_state(BroadcastStates.waiting_for_broadcast_text)
        await message.answer(
            "📢 <b>Barcha foydalanuvchilarga qanday xabar yubormoqchisiz?</b>\n\n"
            "Xabar matnini shu yerga yozib yuboring (Bekor qilish: /cancel):",
            parse_mode="HTML"
        )
        return

    broadcast_text = args[1].strip()
    await _send_broadcast(message, broadcast_text, bot)


@router.message(BroadcastStates.waiting_for_broadcast_text)
async def handle_broadcast_input(message: Message, state: FSMContext, bot: Bot):
    """Interaktiv kiritilgan xabarni tarqatish."""
    if message.text and message.text.strip().startswith("/cancel"):
        await state.clear()
        await message.answer("❌ Xabar tarqatish bekor qilindi.")
        return

    await state.clear()
    broadcast_text = message.text or message.caption or ""
    if not broadcast_text:
        await message.answer("❌ Bo'sh xabar yuborib bo'lmaydi.")
        return

    await _send_broadcast(message, broadcast_text, bot)


async def _send_broadcast(message: Message, broadcast_text: str, bot: Bot):
    """Xabarni barcha adminlarga tarqatish."""
    from config import ADMIN_IDS
    sent_count = 0
    fail_count = 0

    status_msg = await message.answer("📢 Xabar tarqatilmoqda...")

    for adm_id in ADMIN_IDS:
        try:
            await bot.send_message(adm_id, f"📢 <b>Xabarnoma:</b>\n\n{broadcast_text}", parse_mode="HTML")
            sent_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"📢 <b>Xabarnoma yakunlandi!</b>\n\n"
        f"✅ Muvaffaqiyatli yetkazildi: {sent_count} ta\n"
        f"❌ Xatolar: {fail_count} ta",
        parse_mode="HTML"
    )


# ==========================================
# Callback Handlers
# ==========================================

@router.callback_query(F.data == "sys_refresh")
async def cb_sys_refresh(callback: CallbackQuery):
    info = SystemService.get_system_summary()
    text = _format_status_text(info)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=system_actions_keyboard())
    except Exception:
        pass
    await callback.answer("Ma'lumotlar yangilandi")


@router.callback_query(F.data == "sys_screenshot")
async def cb_sys_screenshot(callback: CallbackQuery):
    await callback.answer("Skrinshot olinmoqda...")
    try:
        image_stream = SystemService.capture_screenshot()
        photo = BufferedInputFile(image_stream.getvalue(), filename="screenshot.jpg")
        await callback.message.answer_photo(photo, caption="📸 <b>Kompyuter ekrani skrinshoti</b>", parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"❌ Skrinshotda xatolik: {str(e)}")


@router.callback_query(F.data == "sys_top_mem")
async def cb_sys_top_mem(callback: CallbackQuery):
    await callback.answer()
    procs = SystemService.get_top_processes(limit=8, sort_by="memory")
    text_lines = ["📋 <b>Top RAM Jarayonlar:</b>\n"]
    for p in procs:
        text_lines.append(
            f"• <b>{escape_html(p['name'])}</b> (PID: <code>{p['pid']}</code>)\n"
            f"  RAM: {p['memory_formatted']} ({p['memory_percent']}%) | CPU: {p['cpu_percent']}%\n"
        )
    await callback.message.answer("\n".join(text_lines), parse_mode="HTML")


@router.callback_query(F.data == "sys_top_cpu")
async def cb_sys_top_cpu(callback: CallbackQuery):
    await callback.answer()
    procs = SystemService.get_top_processes(limit=8, sort_by="cpu")
    text_lines = ["⚡ <b>Top CPU Jarayonlar:</b>\n"]
    for p in procs:
        text_lines.append(
            f"• <b>{escape_html(p['name'])}</b> (PID: <code>{p['pid']}</code>)\n"
            f"  CPU: {p['cpu_percent']}% | RAM: {p['memory_formatted']}\n"
        )
    await callback.message.answer("\n".join(text_lines), parse_mode="HTML")


@router.callback_query(F.data == "sys_lock")
async def cb_sys_lock(callback: CallbackQuery):
    ok, result = SystemService.lock_workstation()
    await callback.answer(result, show_alert=True)
