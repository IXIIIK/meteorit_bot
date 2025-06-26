
from aiogram import Router

router = Router()

# сюда добавляй только хендлеры, ничего лишнего
from bot.handlers import form
router.include_router(form.router)