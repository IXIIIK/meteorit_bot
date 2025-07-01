import asyncio
from aiogram import Bot, Dispatcher
from bot_core import router
from db import init_db, reminder_loop, migrate_add_notification_flags
from sheduler_time import setup_scheduler

import os
import logging
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

async def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )


    await init_db()
    await migrate_add_notification_flags()
    bot = Bot(TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    setup_scheduler(bot)
    asyncio.create_task(reminder_loop(bot))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
