from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import is_admin, ADMIN_IDS
from utils.logger import logger


class AuthMiddleware(BaseMiddleware):
    """
    Xavfsizlik va ruxsatlarni tekshiruvchi middleware.
    Faqatgina ADMIN_IDS ro'yxatidagi foydalanuvchilarga ruxsat beradi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id
        username = user.username or user.full_name or "Noma'lum"

        # Agar adminlar ro'yxati bo'sh bo'lsa yoki foydalanuvchi admin bo'lmasa
        if not is_admin(user_id):
            logger.warning(
                f"Ruxsatsiz kirishga urinish! User ID: {user_id}, Ism/Username: {username}"
            )

            warning_text = (
                "⛔ <b>Kirish taqiqlangan!</b>\n\n"
                "Ushbu bot shaxsiy dasturchi ko'prigi (Telegram Dev Bridge) hisoblanadi va "
                "faqat kompyuter egasi uchun mo'ljallangan.\n\n"
                f"🆔 <b>Sizning Telegram ID raqamingiz:</b> <code>{user_id}</code>\n\n"
                "ℹ️ <i>Agar bu sizning botingiz bo'lsa, ushbu ID raqamni loyihadagi <code>.env</code> "
                "faylining <code>ADMIN_IDS</code> qatoriga kiriting va botni qayta ishga tushiring.</i>"
            )

            if isinstance(event, Message):
                await event.answer(warning_text, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Ruxsat berilmagan!", show_alert=True)
                if event.message:
                    await event.message.answer(warning_text, parse_mode="HTML")

            return None

        # Foydalanuvchi admin bo'lsa, davom ettirish
        return await handler(event, data)
