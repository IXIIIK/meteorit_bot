import aiosqlite
from datetime import datetime, timedelta
from pathlib import Path
from aiogram import Bot
import asyncio


DB_PATH = Path(__file__).parent / "bookings.db"


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


async def get_all_bookings():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT table_number, time, name, booking_at FROM bookings")
        rows = await cursor.fetchall()
        return rows

async def save_booking(user_id: int, table_number: str, time: str, name: str, date: str):
    # date = "24.06.2025", time = "14:00"
    day = datetime.strptime(date, "%d.%m.%Y")
    hour = int(time.split(":")[0])
    booking_at = day.replace(hour=hour, minute=0)

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


async def reminder_loop(bot: Bot):
    while True:
        now = datetime.now()
        for delta in [24, 12]:
            target_time = now + timedelta(hours=delta)
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("""
                    SELECT user_id, table_number, booking_at FROM bookings
                """) as cursor:
                    bookings = await cursor.fetchall()
                    for user_id, table, booking_at_str in bookings:
                        booking_at = datetime.fromisoformat(booking_at_str)
                        # разница до цели - в пределах 1 минуты (чтобы не упустить момент)
                        if abs((booking_at - target_time).total_seconds()) < 60:
                            await bot.send_message(
                                user_id,
                                f"⏰ Напоминание: у вас бронь стола через {delta} часов — в {booking_at.strftime('%H:%M')}!\n"
                                f"Для отмены введите /start и перейдите в 'мои брони'"
                            )
        await asyncio.sleep(60)

