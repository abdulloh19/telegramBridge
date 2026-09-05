import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.bot_client_service import BotClientService
import config

async def main():
    print("Testing BotClientService...")
    client = await BotClientService.get_client()
    if client:
        me = await client.get_me()
        print(f"Connected as @{me.username}")
    else:
        print("Failed to connect BotClientService")

if __name__ == "__main__":
    asyncio.run(main())
