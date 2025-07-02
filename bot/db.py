import aiosqlite
from datetime import datetime, timedelta, timezone
from aiogram import Bot
import asyncio


DB_PATH = "bot/bookings.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                table_number TEXT NOT NULL,
                time TEXT NOT NULL,
                name TEXT NOT NULL,
                booking_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
        await db.commit()


async def migrate_add_notification_flags():
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN notify_24_sent BOOLEAN DEFAULT 0")
        except aiosqlite.OperationalError:
            pass  # колонка уже есть

        try:
            await db.execute("ALTER TABLE bookings ADD COLUMN notify_12_sent BOOLEAN DEFAULT 0")
        except aiosqlite.OperationalError:
            pass  # колонка уже есть

        await db.commit()


async def get_all_bookings():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, table_number, time, name, booking_at FROM bookings"
        )
        return await cursor.fetchall()
    

async def booking_exists(table_number: str, booking_at: datetime) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM bookings
            WHERE table_number = ? AND ABS(strftime('%s', booking_at) - strftime('%s', ?)) < 7200
            """,
            (table_number, booking_at.isoformat())
        )
        return await cursor.fetchone() is not None


async def save_booking(user_id: int, table_number: str, time: str, name: str, date: str):
    day = datetime.strptime(date, "%d.%m.%Y")
    hour, minute = map(int, time.split(":"))
    booking_at = day.replace(hour=hour, minute=minute)
    booking_at = booking_at.replace(tzinfo=timezone.utc)

    if await booking_exists(table_number, booking_at):
        raise ValueError("Бронь на это время уже существует")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bookings (user_id, table_number, time, name, booking_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, table_number, time, name, booking_at.isoformat())
        )
        await db.commit()




async def get_booking(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT id, table_number, time, name, created_at, booking_at
            FROM bookings
            WHERE user_id = ?
            """,
            (user_id,)
        )
        return await cursor.fetchall()


async def delete_booking(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await db.commit()


import logging

async def reminder_loop(bot: Bot):
    while True:
        try:
            now = datetime.now(timezone.utc)
            for delta in [24, 12]:
                target_time = now + timedelta(hours=delta)
                window_start = target_time - timedelta(minutes=2)
                window_end = target_time + timedelta(minutes=3)

                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("""
                        SELECT user_id, table_number, booking_at, notify_24_sent, notify_12_sent
                        FROM bookings
                    """) as cursor:
                        bookings = await cursor.fetchall()

                    for user_id, table, booking_at_str, notify_24, notify_12 in bookings:
                        booking_at = datetime.fromisoformat(booking_at_str)
                        if booking_at.tzinfo is None:
                            booking_at = booking_at.replace(tzinfo=timezone.utc)

                        if window_start <= booking_at < window_end:
                            if delta == 24 and not notify_24:
                                await bot.send_message(
                                    user_id,
                                    f"⏰ Напоминание: у вас бронь стола — в {booking_at.strftime('%H:%M')}!\n"
                                    f"Для отмены введите /start и перейдите в 'мои брони'"
                                )
                                await db.execute(
                                    "UPDATE bookings SET notify_24_sent = 1 WHERE user_id = ? AND booking_at = ?",
                                    (user_id, booking_at_str)
                                )

                            elif delta == 12 and not notify_12:
                                await bot.send_message(
                                    user_id,
                                    f"⏰ Напоминание: у вас бронь стола через — в {booking_at.strftime('%H:%M')}!\n"
                                    f"Для отмены введите /start и перейдите в 'мои брони'"
                                )
                                await db.execute(
                                    "UPDATE bookings SET notify_12_sent = 1 WHERE user_id = ? AND booking_at = ?",
                                    (user_id, booking_at_str)
                                )

                    await db.commit()

        except Exception as e:
            logging.exception("Ошибка в reminder_loop")

        await asyncio.sleep(60)



async def delete_booking_by_user_and_time(user_id: int, booking_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM bookings WHERE user_id = ? AND booking_at = ?",
            (user_id, booking_at)
        )
        await db.commit()

