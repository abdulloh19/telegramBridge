import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from telethon import TelegramClient
import config

async def test_bot_mtproto():
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH or not config.BOT_TOKEN:
        print("API_ID, API_HASH or BOT_TOKEN missing!")
        return

    session_path = str(BASE_DIR / "data" / "bot_mtproto_session")
    bot_client = TelegramClient(session_path, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)
    await bot_client.start(bot_token=config.BOT_TOKEN)
    me = await bot_client.get_me()
    print(f"Bot MTProto client connected successfully as: @{me.username} (ID: {me.id})")
    await bot_client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_bot_mtproto())
