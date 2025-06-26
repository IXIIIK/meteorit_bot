import asyncio
from aiogram import Bot, Dispatcher
from bot import router
from bot.config import TOKEN
from bot.db import init_db, reminder_loop
from bot.scheduler_time import setup_scheduler

async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    setup_scheduler(bot)
    asyncio.create_task(reminder_loop(bot))

    print("🚀 Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
