import datetime
import logging
import os
import re
from datetime import date

import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)
from aiogram.utils import executor
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

from telegram_bot_calendar import DetailedTelegramCalendar

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')  # ID администратора, кому будут отправляться заявки
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')  # ID таблицы Google Sheets
STICKER_FILE_ID1 = os.getenv('STICKER_FILE_ID1')
STICKER_FILE_ID2 = os.getenv('STICKER_FILE_ID2')

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Подключение к Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

LEVELS = ["Нулевой, не учил(а) китайский", "Знаю базу фонетики и иероглифики", "HSK 1", "HSK 2", "HSK 3+"]
FORMATS = ["Индивидуальный", "Групповой (со знакомыми)", "Групповой (с другими учениками)"]
PURPOSES = ["Для работы/ бизнеса", "Хочу учиться в Китае", "Для поездки в Китай", "Для жизни в Китае", "Сдать HSK",
            "Учу для себя (хобби)"]
USERNAME = ['Использовать текущий', "Указать другой"]
CHECK = ['Отправить!', 'Изменить данные']
CONTACT_TYPE = ['Написать в телеграм', 'Позвонить']
CHANGE_INFO = ['Никнейм', 'Телефон', 'Уровень', 'Формат']

CHANGE_DICT = {
    'Никнейм': 'username',
    'Телефон': 'phone',
    'Уровень': 'level',
    'Формат': 'format'
}
phone_regex = re.compile(r'(\+?\d{1,3}[- ]?)?\d{10}')
user_data = {}


def create_keyboard(options):
    keyboard = InlineKeyboardMarkup()
    for option in options:
        keyboard.add(InlineKeyboardButton(text=option, callback_data=option))
    return keyboard


@dp.message_handler(commands=['start'])
async def start_consultation(message: types.Message):
    with open('images/test1.jpeg', 'rb') as photo:
        caption = (
            "你好!\n\n"
            "Это бот Сиропа — онлайн-школы китайского, "
            "где ты сможешь выучить один из самых интересных и перспективных языков."
        )
        message_text = (
            "Для начала мы пригласим тебя на бесплатную консультацию. "
            "На ней мы познакомимся, расскажем подробнее о школе, подберем подходящий "
            "для тебя формат обучения и ответим на все вопросы 🙌🏻\n\n"
            "Чтобы записаться на бесплатную консультацию, ответить, пожалуйста, "
            "на несколько коротких вопросов о себе 👇🏻"
        )
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("Поехали!"))

        await message.answer_photo(photo, caption=caption, reply_markup=keyboard)
        await message.answer(message_text, reply_markup=keyboard)


@dp.message_handler(lambda message: message.text in ["Поехали!", "Записаться на консультацию"])
async def start_survey(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"state": "name"}
    await ask_question(message, user_data[user_id]["state"])


async def send_message(message, text, keyboard_name):
    try:
        await bot.edit_message_text(
            text,
            message.chat.id,
            message.message_id,
            reply_markup=create_keyboard(keyboard_name)
        )
    except Exception as e:
        await message.answer(
            text,
            reply_markup=create_keyboard(keyboard_name)
        )


async def ask_question(message, state):
    if state == "name":
        await bot.send_sticker(chat_id=message.chat.id, sticker=STICKER_FILE_ID2)
        await message.answer("Как тебя зовут?", reply_markup=ReplyKeyboardRemove())
    elif state == "level":
        text = "Какой у тебя уровень языка?"
        await send_message(message, text=text, keyboard_name=LEVELS)
    elif state == "format":
        text = "Какой формат занятий тебя интересует?"
        await send_message(message, text=text, keyboard_name=FORMATS)
    elif state == 'contact':
        text = "Мы свяжемся с тобой, чтобы обсудить удобное время для консультации.\nКак тебе будет удобнее?"
        await send_message(message, text=text, keyboard_name=CONTACT_TYPE)
    elif state == "username":
        username = message.chat.username
        await bot.edit_message_text(
            f"Теперь укажи, пожалуйста, контакт, по которому с тобой можно связаться.\n"
            f"Мы можем написать тебе в Telegram по нику @{username} или напиши свой никнейм",
            message.chat.id,
            message.message_id,
            reply_markup=create_keyboard(USERNAME)
        )
    elif state == "username_write":
        await bot.edit_message_text(
            f"Укажи свой никнейм в телеграм",
            message.chat.id,
            message.message_id
        )
    elif state == "purpose":
        await bot.edit_message_text(
            "Для чего ты хочешь учить китайский? 🧐",
            message.chat.id,
            message.message_id,
            reply_markup=create_keyboard(PURPOSES)
        )
    elif state == "phone":
        user_id = message.chat.id
        if state in user_data[user_id]:
            await bot.edit_message_text(
                "Укажи телефонный номер для связи (в формате +7ххххххх)",
                message.chat.id,
                message.message_id
            )
        else:
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.add(KeyboardButton("Отправить мой контакт", request_contact=True))
            try:
                await bot.edit_message_text(
                    "Отлично, полдела сделано!",
                    message.chat.id,
                    message.message_id
                )
            except:
                await message.answer(
                    "Отлично, полдела сделано!"
                )
            await message.answer(
                "Укажи телефонный номер для связи (в формате +7ххххххх) или "
                "воспользуйся кнопкой ниже 👇",
                reply_markup=keyboard
            )
    elif state == 'meet_date':
        calendar, step = DetailedTelegramCalendar(min_date=date.today()).build()
        try:
            await bot.edit_message_text(
                'Выбери удобный день для консультации 🗓',
                message.chat.id,
                message.message_id)
        except:
            await message.answer(
                'Выбери удобный день для консультации 🗓',
                reply_markup=ReplyKeyboardRemove()
            )
        await message.answer(
            "Воспользуйся календарем",
            reply_markup=calendar
        )


@dp.message_handler(lambda message: message.text and user_data.get(message.from_user.id, {}).get("state") == "name")
async def handle_name(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id]["name"] = message.text
    user_data[user_id]["state"] = "level"
    await ask_question(message, "level")


@dp.message_handler(
    lambda message: message.text and user_data.get(message.from_user.id, {}).get("state") == "username_write")
async def handle_nickname(message: types.Message):
    user_id = message.from_user.id
    if 'username' in user_data[user_id]:
        user_data[user_id]["username"] = message.text
        results = get_results(user_id, addit_text='Твоя заявка:')
        await send_message(message, text=results, keyboard_name=CHECK)
    else:
        user_data[user_id]["username"] = message.text
        user_data[user_id]["state"] = "meet_date"
        await ask_question(message, "meet_date")


@dp.callback_query_handler(lambda c: c.data in CHECK)
async def handle_check(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    if data == 'Изменить данные':
        await bot.edit_message_text(
            "Какую информацию Вы бы хотели изменить?",
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=create_keyboard(CHANGE_INFO)
        )
    elif data == 'Отправить!':
        results = get_results(user_id, 'Твоя заявка:')
        result_admin = get_results(user_id, 'Новая заявка')
        save_results(user_id)
        del user_data[user_id]
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("Записаться на консультацию"))
        await bot.edit_message_text('Спасибо за уделенное время!',
                                    callback_query.message.chat.id,
                                    callback_query.message.message_id)
        await callback_query.message.answer(
            f"Наш менеджер скоро с тобой свяжется для подтверждения заявки 🔆",
            reply_markup=keyboard)
        await bot.send_sticker(chat_id=callback_query.message.chat.id, sticker=STICKER_FILE_ID1)
        await bot.send_message(ADMIN_ID, result_admin)


@dp.callback_query_handler(lambda c: c.data in CHANGE_INFO)
async def change_info(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    state = CHANGE_DICT[data]
    user_data[user_id]["state"] = state
    await ask_question(callback_query.message, state)


@dp.callback_query_handler(lambda c: c.data in LEVELS + FORMATS + PURPOSES + USERNAME + CONTACT_TYPE)
async def handle_inline_response(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    state = user_data[user_id]["state"]

    if state in user_data[user_id] and data != 'Написать свой':
        if data == 'Использовать текущий':
            username = callback_query.message.chat.username
            user_data[user_id][state] = username
        else:
            user_data[user_id][state] = data
        results = get_results(user_id, addit_text='Твоя заявка:')
        await bot.edit_message_text(results,
                                    callback_query.message.chat.id,
                                    callback_query.message.message_id,
                                    reply_markup=create_keyboard(CHECK))
    elif state == "level":
        user_data[user_id]["level"] = data
        user_data[user_id]["state"] = "format"
        await ask_question(callback_query.message, "format")
    elif state == "format":
        user_data[user_id]["format"] = data
        user_data[user_id]["state"] = "purpose"
        await ask_question(callback_query.message, "purpose")
    elif state == "purpose":
        user_data[user_id]["purpose"] = data
        user_data[user_id]["state"] = "username"
        await ask_question(callback_query.message, "contact")
    elif data == 'Написать в телеграм':
        user_data[user_id]["state"] = "username"
        await ask_question(callback_query.message, "username")
    elif data == 'Позвонить':
        user_data[user_id]["state"] = "phone"
        await ask_question(callback_query.message, "phone")
    elif data == 'Указать другой':
        user_data[user_id]["state"] = "username_write"
        await ask_question(callback_query.message, "username_write")
    elif data == 'Использовать текущий':
        username = callback_query.message.chat.username
        user_data[user_id]["username"] = username
        user_data[user_id]["state"] = "meet_date"
        await ask_question(callback_query.message, "meet_date")


@dp.message_handler(content_types=types.ContentType.CONTACT)
@dp.message_handler(lambda message: phone_regex.search(message.text))
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    state = 'phone'

    if message.contact:
        phone_number = message.contact.phone_number
    else:
        phone_number = message.text

    if state in user_data[user_id]:
        user_data[user_id][state] = phone_number
        results = get_results(user_id, addit_text='Твоя заявка')
        await message.answer(results, reply_markup=create_keyboard(CHECK))
    else:
        user_data[user_id]["phone"] = phone_number
        await ask_question(message, "meet_date")


@dp.callback_query_handler(DetailedTelegramCalendar.func())
async def inline_kb_answer_callback_handler(query):
    result, key, step = DetailedTelegramCalendar(min_date=date.today()).process(query.data)

    if not result and key:
        await bot.edit_message_text(f"Воспользуйся календарем",
                                    query.message.chat.id,
                                    query.message.message_id,
                                    reply_markup=key)
    elif result:
        user_id = query.from_user.id
        user_data[user_id]["meet_date"] = str(result)
        results = get_results(user_id, addit_text='Твоя заявка')
        await bot.edit_message_text(results,
                                    query.message.chat.id,
                                    query.message.message_id,
                                    reply_markup=create_keyboard(CHECK))


def save_results(user_id):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user = user_data[user_id]
    user['username'] = user.get('username', '-') or '-'
    user['phone'] = user.get('phone', '-') or '-'
    row = [
        user["name"],
        user["level"],
        user["format"],
        user["purpose"],
        user['username'],
        user["phone"],
        user["meet_date"],
        now
    ]
    sheet.append_row(row)


def get_results(user_id, addit_text):
    user = user_data[user_id]
    user['username'] = user.get('username', '-') or '-'
    user['phone'] = user.get('phone', '-') or '-'
    message = (f"{addit_text}:\n"
               f"Имя: {user['name']}\n"
               f"Уровень языка: {user['level']}\n"
               f"Формат занятий: {user['format']}\n"
               f"Цель: {user['purpose']}\n"
               f"Ник в тг: {user['username']}\n"
               f"Телефон: {user['phone']}\n"
               f"Предварительная дата консультации: {user['meet_date']}\n\n")
    return message


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
