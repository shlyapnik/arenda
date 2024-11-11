import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import os

API_TOKEN = '5047371265:AAHdC6RXacQ2tdx70yjaLxEi0V-OLp7JA4I'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS posts
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER,
                   address TEXT,
                   floor TEXT,
                   rooms TEXT,
                   status TEXT,
                   amenities TEXT,
                   price TEXT,
                   phone TEXT,
                   photos TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS channels
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT,
                   channel_id TEXT)''')

conn.commit()


class Form(StatesGroup):
    address = State()
    floor = State()
    rooms = State()
    status = State()
    amenities = State()
    price = State()
    phone = State()
    photos = State()


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply(
        "Привет! Я бот для создания объявлений. Используйте /create_post для создания нового объявления.")


@dp.message_handler(commands=['create_post'])
async def create_post(message: types.Message):
    await Form.address.set()
    await message.reply("Давайте создадим новое объявление. Введите адрес:")


@dp.message_handler(state=Form.address)
async def process_address(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['address'] = message.text
    await Form.next()
    await message.reply("Введите этаж:")


@dp.message_handler(state=Form.floor)
async def process_floor(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['floor'] = message.text
    await Form.next()
    await message.reply("Введите количество комнат:")


@dp.message_handler(state=Form.rooms)
async def process_rooms(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['rooms'] = message.text
    await Form.next()
    await message.reply("Введите статус (например, Новостройка):")


@dp.message_handler(state=Form.status)
async def process_status(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['status'] = message.text
    await Form.next()
    await message.reply("Что есть в квартире? (перечислите через запятую):")


@dp.message_handler(state=Form.amenities)
async def process_amenities(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['amenities'] = message.text
    await Form.next()
    await message.reply("Введите цену аренды:")


@dp.message_handler(state=Form.price)
async def process_price(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['price'] = message.text
    await Form.next()
    await message.reply("Введите контактный телефон:")


@dp.message_handler(state=Form.phone)
async def process_phone(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phone'] = message.text
    await Form.next()
    await message.reply("Теперь отправьте фотографии квартиры (до 5 штук). После отправки всех фото напишите 'готово'.")


@dp.message_handler(state=Form.photos, content_types=['photo'])
async def process_photos(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if 'photos' not in data:
            data['photos'] = []
        data['photos'].append(message.photo[-1].file_id)

    if len(data['photos']) < 5:
        await message.reply("Фото добавлено. Отправьте еще фото или напишите 'готово', если закончили.")
    else:
        await message.reply("Достигнуто максимальное количество фото. Напишите 'готово' для завершения.")


@dp.message_handler(lambda message: message.text.lower() == 'готово', state=Form.photos)
async def process_done(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        # Проверка, что хотя бы одно фото было загружено
        if 'photos' not in data or len(data['photos']) == 0:
            await message.reply("Вы не загрузили ни одного фото. Пожалуйста, загрузите хотя бы одно фото.")
            return

        # Сохранение данных в базу
        cursor.execute('''INSERT INTO posts (user_id, address, floor, rooms, status, amenities, price, phone, photos)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (message.from_user.id, data['address'], data['floor'], data['rooms'], data['status'],
                        data['amenities'], data['price'], data['phone'], ','.join(data['photos'])))
        conn.commit()
        post_id = cursor.lastrowid

    await state.finish()
    await send_post_to_admin(post_id)
    await message.reply("Спасибо! Ваше объявление отправлено на проверку администратору.")


async def send_post_to_admin(post_id):
    admin_id = 149891069  # Замените на реальный ID администратора
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    post = cursor.fetchone()

    text = f"""
📢 #Сдается в аренду

📍 Адрес: {post[2]}
🏠 Этаж: {post[3]}
✅ Количество комнат: {post[4]}
🏠 Статус: {post[5]}
✅ Что есть в квартире: {post[6]}
✅ Долгосрочный арендатор

💸 Цена: {post[7]}

📞 Тел: {post[8]}
    """

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Опубликовать", callback_data=f"publish_{post_id}"))
    keyboard.add(InlineKeyboardButton("Отклонить", callback_data=f"reject_{post_id}"))

    photo_ids = post[9].split(',')
    media = [types.InputMediaPhoto(media=photo_id, caption=text if i == 0 else '') for i, photo_id in
             enumerate(photo_ids)]

    await bot.send_media_group(admin_id, media)
    await bot.send_message(admin_id, "Выберите действие:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith('publish_'))
async def process_publish(callback_query: types.CallbackQuery):
    post_id = int(callback_query.data.split('_')[1])
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    post = cursor.fetchone()

    # Получение списка каналов
    cursor.execute("SELECT * FROM channels")
    channels = cursor.fetchall()

    keyboard = InlineKeyboardMarkup()
    for channel in channels:
        keyboard.add(InlineKeyboardButton(channel[1], callback_data=f"send_{post_id}_{channel[2]}"))

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Выберите канал для публикации:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith('send_'))
async def send_to_channel(callback_query: types.CallbackQuery):
    _, post_id, channel_id = callback_query.data.split('_')
    post_id = int(post_id)

    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    post = cursor.fetchone()

    text = f"""
📢 #Сдается в аренду

📍 Адрес: {post[2]}
🏠 Этаж: {post[3]}
✅ Количество комнат: {post[4]}
🏠 Статус: {post[5]}
✅ Что есть в квартире: {post[6]}
✅ Долгосрочный арендатор

💸 Цена: {post[7]}

📞 Тел: {post[8]}
    """

    photo_ids = post[9].split(',')
    media = [types.InputMediaPhoto(media=photo_id, caption=text if i == 0 else '') for i, photo_id in
             enumerate(photo_ids)]

    await bot.send_media_group(channel_id, media)

    await bot.answer_callback_query(callback_query.id, "Пост опубликован в канале!")


@dp.callback_query_handler(lambda c: c.data.startswith('reject_'))
async def process_reject(callback_query: types.CallbackQuery):
    post_id = int(callback_query.data.split('_')[1])
    cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    await bot.answer_callback_query(callback_query.id, "Пост отклонен и удален из базы данных.")


@dp.message_handler(commands=['add_channel'])
async def add_channel(message: types.Message):
    await message.reply("Введите название канала и его ID через запятую (например: Мой канал, -100123456789)")


@dp.message_handler(lambda message: ',' in message.text)
async def process_add_channel(message: types.Message):
    name, channel_id = message.text.split(',')
    name = name.strip()
    channel_id = channel_id.strip()

    cursor.execute("INSERT INTO channels (name, channel_id) VALUES (?, ?)", (name, channel_id))
    conn.commit()

    await message.reply(f"Канал '{name}' успешно добавлен!")


@dp.message_handler(commands=['list_channels'])
async def list_channels(message: types.Message):
    cursor.execute("SELECT * FROM channels")
    channels = cursor.fetchall()

    if channels:
        response = "Список каналов:\n\n"
        for channel in channels:
            response += f"{channel[1]} (ID: {channel[2]})\n"
    else:
        response = "Список каналов пуст."

    await message.reply(response)


if __name__ == '__main__':
    from aiogram import executor

    executor.start_polling(dp, skip_updates=True)