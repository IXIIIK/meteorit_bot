from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from collections import defaultdict

from datetime import datetime, timedelta, timezone, time
from pathlib import Path
from db import save_booking, get_booking, delete_booking, get_all_bookings


IMG_PATH = Path(__file__).parent / "img" / "booking_img.png"
router = Router()

TABLES = {
    8: ["T8_1"],
    6: ["T6_1"],
    3: [f"T3_{i}" for i in range(1, 7)]
}



class Booking(StatesGroup):
    date = State()
    guests = State()
    time = State()
    name = State()
    phone = State()


async def find_next_available_slot(guests: int, selected_dt: datetime, all_bookings):
    tables = TABLES.get(guests)
    if not tables:
        return None, None

    bookings_by_table = defaultdict(list)
    selected_date = selected_dt.date()

    # Группируем брони по столам
    for _, table, _, _, booking_at_str in all_bookings:
        booking_at = datetime.fromisoformat(booking_at_str).replace(tzinfo=timezone.utc)
        if booking_at.date() == selected_date:
            bookings_by_table[table].append(booking_at)

    for table_id in tables:
        occupied = bookings_by_table.get(table_id, [])
        occupied.sort()

        # Проверка текущего слота
        slot_start = selected_dt
        slot_end = slot_start + timedelta(hours=2)

        conflict = any(
            not (b + timedelta(hours=2) <= slot_start or b >= slot_end)
            for b in occupied
        )
        if not conflict:
            return table_id, selected_dt

        # Поиск ближайшего свободного слота позже
        test_start = max(slot_end, max(occupied) + timedelta(minutes=30) if occupied else slot_start)
        while test_start.hour < 23:
            test_end = test_start + timedelta(hours=2)
            if all(
                b + timedelta(hours=2) <= test_start or b >= test_end
                for b in occupied
            ):
                return table_id, test_start
            test_start += timedelta(minutes=30)

    return None, None



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
    await msg.answer("Добрый день! На связи Метеорит, в этом боте можно забронировать стол или посмотреть действующее бронирование?",\
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
async def cancel_booking(callback: CallbackQuery, bot):
    booking_id = int(callback.data.split("_")[1])

    # Получаем все брони пользователя
    bookings = await get_booking(callback.from_user.id)
    cancelled = None

    for b in bookings:
        b_id, table, time, name, created_at, booking_at = b
        if b_id == booking_id:
            cancelled = b
            break

    await delete_booking(booking_id)
    await callback.message.answer("Бронь успешно отменена ✅")

    if cancelled:
        manager_chat_id = -4980377325
        booking_fmt = datetime.fromisoformat(cancelled[5]).astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")
        await bot.send_message(
            manager_chat_id,
            f"❌ Отмена брони:\n"
            f"📅 {booking_fmt}\n"
            f"👥 Гостей: {cancelled[1]}\n"
            f"👤 Имя: {cancelled[3]}"
        )


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
    await state.set_state(Booking.guests)  # предположим, что дальше идёт выбор количества гостей

    # Получаем все брони на эту дату
    existing = await get_all_bookings()
    selected_date = datetime.strptime(date_str, "%d.%m.%Y").date()

    # Слоты, которые надо скрыть
    unavailable_slots = set()

    for record in existing:
        user_id, table, time_str, name, booking_at_str = record
        booking_at = datetime.fromisoformat(booking_at_str).replace(tzinfo=None)

        if booking_at.date() != selected_date:
            continue

        start = booking_at
        end = start + timedelta(hours=2)

        for hour in range(start.hour, end.hour + 1):
            for minute in [0, 30]:
                ts = datetime.combine(start.date(), time(hour, minute))
                if start <= ts < end:
                    unavailable_slots.add(ts.strftime("%H:%M"))

    # Создаём кнопки только для свободного времени
    builder = InlineKeyboardBuilder()
    for hour in range(9, 23):  # с 9:00 до 22:30
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            if time_str in unavailable_slots:
                continue
            builder.button(text=time_str, callback_data=f"time_{time_str}")

    builder.adjust(3)

    await callback.message.answer("Выбери время брони:", reply_markup=builder.as_markup())




@router.callback_query(F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    # Защита от пропущенных шагов
    if "guests" not in data or "date" not in data:
        await callback.message.answer("⚠️ Пожалуйста, начните бронирование заново: выбери дату и количество гостей.")
        await state.set_state(Booking.date)
        return

    time_str = callback.data.split("_")[1]
    hour, minute = map(int, time_str.split(":"))
    
    guests = data['guests']
    date = data['date']
    selected_dt = datetime.strptime(date, "%d.%m.%Y").replace(hour=hour, minute=minute, tzinfo=timezone.utc)

    all_bookings = await get_all_bookings()
    table_id, slot_time = await find_next_available_slot(guests, selected_dt, all_bookings)

    if not table_id:
        await callback.message.answer("😞 На эту дату нет доступных столов нужной вместимости.")
        return

    if slot_time != selected_dt:
        time_suggested = slot_time.astimezone(timezone(timedelta(hours=3))).strftime("%H:%M")
        await callback.message.answer(
            f"⚠️ Кто-то только что забронировал этот стол на это время. Попробуйте выбрать другой.\n"
            f"Ближайшее доступное время: {time_suggested}"
        )
        return

    # Если время свободно, сохраняем данные и запрашиваем имя
    await state.update_data(hour=hour, minute=minute, table_number=table_id)
    await state.set_state(Booking.name)
    await callback.message.answer("Как к вам можно обратиться?")


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


@router.callback_query(F.data.startswith("guests_"))
async def get_guests(callback: CallbackQuery, state: FSMContext):
    guests = int(callback.data.replace("guests_", ""))
    await state.update_data(guests=guests)

    user_data = await state.get_data()
    if "date" not in user_data:
        await callback.message.answer("⚠️ Сначала выбери дату бронирования.")
        await state.set_state(Booking.date)
        return

    await state.set_state(Booking.time)

    date_str = user_data["date"]
    selected_date = datetime.strptime(date_str, "%d.%m.%Y")
    now = datetime.now(timezone(timedelta(hours=3)))  # МСК
    is_today = selected_date.date() == now.date()

    all_bookings = await get_all_bookings()
    blocked_slots = set()

    if guests == 8:
        for user_id, table, time, name, booking_at_str in all_bookings:
            booking_at = datetime.fromisoformat(booking_at_str).replace(tzinfo=timezone.utc)
            booking_at_local = booking_at.astimezone(timezone(timedelta(hours=3)))

            if booking_at_local.date() != selected_date.date():
                continue

            if int(table) == 8:  # бронь на 8 гостей
                for shift_minutes in range(-119, 120, 30):
                    blocked = (booking_at_local + timedelta(minutes=shift_minutes)).strftime("%H:%M")
                    blocked_slots.add(blocked)

    builder = InlineKeyboardBuilder()
    for hour in range(9, 24):
        for minute in [0, 30]:
            slot_time = selected_date.replace(hour=hour, minute=minute, tzinfo=timezone(timedelta(hours=3)))

            if is_today and slot_time <= now:
                continue

            time_str = f"{hour:02d}:{minute:02d}"
            if time_str in blocked_slots:
                continue  # ⛔️ Пропускаем заблокированное время

            builder.button(text=time_str, callback_data=f"time_{time_str}")

    builder.adjust(3)

    if not builder.buttons:
        await callback.message.answer("😞 К сожалению, на выбранную дату нет свободных слотов.\nПопробуйте выбрать другой день.")
        await state.set_state(Booking.date)
        return

    await callback.message.answer("Выбери время бронирования:", reply_markup=builder.as_markup())


@router.message(Booking.phone)
async def get_phone(msg: Message, state: FSMContext):
    phone = msg.text
    await state.update_data(phone=phone)

    data = await state.get_data()
    time_str = f"{data['hour']:02d}:{data['minute']:02d}"

    # Удалена проверка доступности, так как она уже выполнена в choose_time
    await save_booking(
        user_id=msg.from_user.id,
        table_number=str(data["guests"]),
        time=time_str,
        name=data["name"],
        date=data["date"]
    )

    await msg.answer(
        f"Спасибо {str(data['name']).capitalize()}! Ваше бронирование на {data['guests']} гостей, {data['date']}, в {time_str}.\n"
        f"Отличный отдых теперь гарантирован! Хотим сообщить что длительность бронирования составляет 2 часа, "
        f"если у нас будет возможность мы с радостью продлим это время 🤍"
    )

    manager_chat_id = -4980377325
    text = (
        f"📢 Новая бронь!\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {time_str}\n"
        f"👥 Кол-во гостей: {data['guests']}\n"
        f"👤 Имя: {str(data['name']).capitalize()}\n"
        f"📞 Телефон: {phone}"
    )
    await msg.bot.send_message(chat_id=manager_chat_id, text=text)


