# bot/sheduler_time.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from bot.db import get_all_bookings, delete_booking_by_user_and_time
from aiogram import Bot

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()

    async def remove_expired_bookings():
        now = datetime.now()
        bookings = await get_all_bookings()
        for user_id, table, time, name, booking_at_str in bookings:
            booking_at = datetime.fromisoformat(booking_at_str)
            if now > booking_at + timedelta(hours=2):
                await delete_booking_by_user_and_time(user_id, booking_at_str)
                try:
                    await bot.send_message(
                        user_id,
                        "✅ Спасибо, что выбрали нас!\n"
                        "Поделиться впечатлениями можно здесь:\n"
                        "https://yandex.ru/maps/org/meteorit/217545735013?si=7j55a8hmy7v26bxzkk2kqg7dbm\n"
                        "Ждём вас снова в 'Метеорите' 🌠\n\n"
                        "📍 ул. Покровка, 20/1с1"
                    )
                except Exception as e:
                    print(f"Ошибка при отправке: {e}")

    scheduler.add_job(remove_expired_bookings, "interval", minutes=2)
    scheduler.start()
