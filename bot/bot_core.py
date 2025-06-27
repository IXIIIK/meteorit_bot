from aiogram import Router

router = Router()


from handlers import form

router.include_router(form.router)