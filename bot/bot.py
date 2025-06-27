import asyncio
import logging
from db import init_db, reminder_loop

from aiogram import Bot, Dispatcher
from aiogram.fsm.strategy import FSMStrategy
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.client.default import DefaultBotProperties
from handlers.form import router
from config import config


bot = Bot(config.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode='HTML'))

async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()
    storage = MemoryStorage()
    events_isolation = SimpleEventIsolation()

    dp = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_CHAT,
        events_isolation=events_isolation,
    )

    dp.include_router(router)

    asyncio.create_task(reminder_loop(bot))
    await init_db()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

