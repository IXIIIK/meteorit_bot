from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from datetime import datetime, timedelta, timezone
from pathlib import Path
from db import save_booking, get_booking, delete_booking, get_all_bookings

IMG_PATH = Path(__file__).parent / "img" / "booking_img.png"

router = Router()

class Booking(StatesGroup):
    date = State()
    time = State()
    table = State()
    name = State()
    phone = State()


@router.message(F.text == "/start")
async def send_welcome(msg: Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Забронировать стол")],
            [KeyboardButton(text="Мои брони")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await msg.answer("Добрый день! На связи метеорит, в этом боте можно забронировать стол или посмотреть действующее бронирование?",\
                    reply_markup=keyboard)


@router.message(F.text == "Мои брони")
async def my_bookings(msg: Message):
    bookings = await get_booking(msg.from_user.id)

    if not bookings:
        await msg.answer("У тебя пока нет активных броней.")
        return

    text = "📝 Твои брони:\n\n"
    for booking in bookings:
        # если get_booking возвращает: (id, table, time, name, created_at, booking_at)
        booking_id, table, time, name, created_at, booking_at = booking
        booking_fmt = datetime.fromisoformat(booking_at).strftime("%d.%m.%Y")
        text = (
            f"📅 Дата: {booking_fmt}\n"
            f"🪑 Стол {table} на {time}\n"
            f"👤 Имя: {name}"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{booking_id}")]
            ]
        )
        await msg.answer(text, reply_markup=keyboard)



@router.callback_query(F.data.startswith("cancel_"))
async def cancel_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split("_")[1])
    await delete_booking(booking_id)
    await callback.message.answer("Бронь успешно отменена ✅")


# Создаём кнопки времени с шагом в 1 час
@router.message(F.text == "Забронировать стол")
async def start_booking(msg: Message, state: FSMContext):
    await state.set_state(Booking.date)

    builder = InlineKeyboardBuilder()
    today = datetime.today()
    for i in range(14):
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        builder.button(text=date_str, callback_data=f"date_{date_str}")
    builder.adjust(2)

    await msg.answer("Выбери дату брони:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.replace("date_", "")
    await state.update_data(date=date_str)
    await state.set_state(Booking.time)

    builder = InlineKeyboardBuilder()
    for hour in range(9, 24):
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            builder.button(text=time_str, callback_data=f"time_{time_str}")
    builder.adjust(3)

    await callback.message.answer("Выбери время брони:", reply_markup=builder.as_markup())



@router.callback_query(F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.split("_")[1]  # формат "HH:MM"
    hour, minute = map(int, time_str.split(":"))
    await state.update_data(hour=hour, minute=minute)
    await state.set_state(Booking.table)

    user_data = await state.get_data()
    selected_date = datetime.strptime(user_data['date'], "%d.%m.%Y")
    current_datetime = selected_date.replace(hour=hour, minute=minute)
    current_datetime = current_datetime.replace(tzinfo=timezone.utc)  # 👈 добавили

    existing = await get_all_bookings()
    unavailable = []
    for record in existing:
        user_id, table, time, name, booking_at_str = record
        booking_at = datetime.fromisoformat(booking_at_str)

        # 👇 Приведение к tz-aware, если вдруг строка сохранилась без tzinfo
        if booking_at.tzinfo is None:
            booking_at = booking_at.replace(tzinfo=timezone.utc)

        booking_start = booking_at
        booking_end = booking_at + timedelta(hours=2)

        new_start = current_datetime
        new_end = current_datetime + timedelta(hours=2)

        if booking_start.date() == new_start.date() and (new_start < booking_end and booking_start < new_end):
            unavailable.append(table)


    all_tables = ["13 от 6 человек", "16 до 5 человек", "23 до 2 людей",
                  "17 до 3 людей", "18 до 3 людей", "19 до 3 людей", "20 до 3 людей", "22 до 3 людей"]
    available = [t for t in all_tables if t not in unavailable]

    if not available:
        await callback.message.answer("На это время нет доступных столов. Попробуй выбрать другую дату или время.")
        await state.set_state(Booking.time)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Стол {t}", callback_data=f"table_{t[:2]}")] for t in available
        ]
    )
    await callback.message.answer(f"Выбери стол на {time_str}, {user_data['date']}:", reply_markup=keyboard)




@router.callback_query(F.data.startswith("table_"))
async def choose_table(callback: CallbackQuery, state: FSMContext):
    table_number = callback.data.split("_")[1]
    await state.update_data(table_number=table_number)
    await state.set_state(Booking.name)
    await callback.message.answer("Как к вам можно обратиться?")


@router.message(Booking.name)
async def get_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(Booking.phone)
    await msg.answer("Оставьте, пожалуйста, номер телефона для связи.")


@router.message(Booking.phone)
async def get_phone(msg: Message, state: FSMContext):
    phone = msg.text
    await state.update_data(phone=phone)

    data = await state.get_data()
    time_str = f"{data['hour']:02d}:{data['minute']:02d}"

    try:
        await save_booking(
            user_id=msg.from_user.id,
            table_number=data["table_number"],
            time=time_str,
            name=data["name"],
            date=data["date"]
        )
    except ValueError:
        await msg.answer("⚠️ Кто-то только что забронировал этот стол на это время. Попробуй выбрать другой.")
        await state.clear()
        return

    await msg.answer(f"Готово! Стол {data['table_number']} забронирован на {time_str}. До встречи, {data['name']}!\n"
                     f"Бронь на столик длиться 2 часа!")
    await state.clear()

    manager_chat_id = -4980377325

    text = (
        f"📢 Новая бронь!\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {time_str}\n"
        f"🪑 Стол: {data['table_number']}\n"
        f"👤 Имя: {data['name']}\n"
        f"📞 Телефон: {phone}"
    )

    await msg.bot.send_message(chat_id=manager_chat_id, text=text)
