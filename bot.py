import asyncio
import logging
import sqlite3
import random
import json
import os
import sys
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

# ========== ИМПОРТЫ AIOGRAM ==========
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, CallbackQuery,
    Message, FSInputFile, InputFile,
    ChatPermissions, ChatAdministratorRights,
    WebAppInfo, MenuButtonWebApp,
    Contact, Location, Poll,
    User, Chat, ChatMember
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus, ChatType, ContentType
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramUnauthorizedError
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.utils.token import TokenValidationError

# ========== ДОПОЛНИТЕЛЬНЫЕ ИМПОРТЫ ==========
import aiohttp
from cryptography.fernet import Fernet
import base64

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('swill_bot_full.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========
class Config:
    def __init__(self):
        # ОСНОВНЫЕ НАСТРОЙКИ
        self.API_TOKEN = os.getenv('API_TOKEN', '7936373505:AAH9O8-KoO7aMNJm7bqlDHypTxr1E__3rXU')
        self.MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID', 8358009538))
        
        # БЕЗОПАСНОСТЬ И ШИФРОВАНИЕ
        self.SECRET_KEY = os.getenv('SECRET_KEY', 'swill_secret_key_2025_encryption_master')
        self.ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
        
        # TELEGRAM API ДЛЯ ЗАХВАТА АККАУНТОВ
        self.TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
        self.TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
        
        # НАСТРОЙКИ ПРОКСИ
        self.PROXY_URL = os.getenv('PROXY_URL', '')
        self.PROXY_TYPE = os.getenv('PROXY_TYPE', 'socks5')
        self.PROXY_AUTH = os.getenv('PROXY_AUTH', '')
        
        # НАСТРОЙКИ БАЗЫ ДАННЫХ
        self.DB_PATH = os.getenv('DB_PATH', 'swill_bot_full.db')
        self.MAX_ADMINS = int(os.getenv('MAX_ADMINS', '50'))
        self.MAX_CHANNELS = int(os.getenv('MAX_CHANNELS', '100'))
        
        # ВЕБ-СЕРВЕР
        self.WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
        self.WEB_PORT = int(os.getenv('WEB_PORT', '8080'))
        
        # ТАЙМАУТЫ
        self.SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))
        self.REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
        
    def validate(self):
        """Проверка конфигурации"""
        if not self.API_TOKEN or self.API_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            raise ValueError("API_TOKEN не установлен. Укажите токен бота.")
        
        if self.API_TOKEN == '7936373505:AAH9O8-KoO7aMNJm7bqlDHypTxr1E__3rXU':
            logger.warning("Используется тестовый токен бота. Замените на свой.")
        
        logger.info(f"Конфигурация загружена. Главный админ: {self.MAIN_ADMIN_ID}")
        return True

config = Config()
config.validate()

# ========== СОЗДАНИЕ БОТА ==========
def create_bot():
    """Создание экземпляра бота"""
    try:
        bot = Bot(
            token=config.API_TOKEN,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
                protect_content=False
            )
        )
        logger.info("Бот создан успешно")
        return bot
    except TokenValidationError as e:
        logger.error(f"Неверный токен бота: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка создания бота: {e}")
        raise

# Создаем бота и диспетчер
bot = create_bot()
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== ШИФРОВАНИЕ ДАННЫХ ==========
class DataEncryptor:
    """Класс для шифрования и дешифрования данных"""
    
    def __init__(self, key: str = None):
        self.key = key or config.ENCRYPTION_KEY
        if isinstance(self.key, str):
            self.key = self.key.encode()
        
        # Дополняем ключ до 32 байт для Fernet
        if len(self.key) < 32:
            self.key = self.key.ljust(32, b'0')
        elif len(self.key) > 32:
            self.key = self.key[:32]
        
        # Создаем Fernet с правильным ключом
        self.fernet = Fernet(base64.urlsafe_b64encode(self.key))
        logger.info("Инициализирован шифровальщик данных")
    
    def encrypt(self, data: str) -> str:
        """Шифрует строку данных"""
        try:
            if not data:
                return ""
            encrypted = self.fernet.encrypt(data.encode())
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        """Дешифрует строку данных"""
        try:
            if not encrypted_data:
                return ""
            decrypted = self.fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Ошибка дешифрования: {e}")
            return encrypted_data
    
    def hash_data(self, data: str) -> str:
        """Создает SHA256 хэш от данных"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def generate_token(self, length: int = 32) -> str:
        """Генерирует криптографически безопасный токен"""
        return secrets.token_urlsafe(length)

encryptor = DataEncryptor()

# ========== БАЗА ДАННЫХ ==========
class Database:
    """Класс для работы с базой данных SQLite"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self.conn = None
        self.cursor = None
        self.connect()
        self.init_database()
    
    def connect(self):
        """Подключение к базе данных"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            logger.info(f"Подключено к базе данных: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise
    
    def init_database(self):
        """Инициализация всех таблиц базы данных"""
        try:
            # Таблица пользователей
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    phone_hash TEXT,
                    code TEXT,
                    balance REAL DEFAULT 0,
                    rating INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'active',
                    registered DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    messages_count INTEGER DEFAULT 0,
                    is_verified BOOLEAN DEFAULT 0,
                    verification_date DATETIME,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # Таблица администраторов
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone_hash TEXT,
                    added_by INTEGER,
                    added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                    permissions TEXT DEFAULT 'all',
                    is_active BOOLEAN DEFAULT 1,
                    is_main_admin BOOLEAN DEFAULT 0,
                    security_level INTEGER DEFAULT 1,
                    session_token TEXT,
                    session_expires DATETIME,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (added_by) REFERENCES admins(user_id)
                )
            ''')
            
            # Таблица каналов
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_title TEXT,
                    channel_username TEXT,
                    channel_type TEXT DEFAULT 'channel',
                    added_by INTEGER,
                    added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_approved BOOLEAN DEFAULT 0,
                    approved_by INTEGER,
                    approved_date DATETIME,
                    notifications_enabled BOOLEAN DEFAULT 1,
                    admin_notifications BOOLEAN DEFAULT 1,
                    bot_is_admin BOOLEAN DEFAULT 0,
                    bot_permissions TEXT DEFAULT '{}',
                    last_message_id INTEGER,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    settings TEXT DEFAULT '{}',
                    FOREIGN KEY (added_by) REFERENCES admins(user_id),
                    FOREIGN KEY (approved_by) REFERENCES admins(user_id)
                )
            ''')
            
            # Таблица товаров
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_type TEXT,
                    photos TEXT,
                    description TEXT,
                    price REAL,
                    moderator_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    created DATETIME DEFAULT CURRENT_TIMESTAMP,
                    moderated_date DATETIME,
                    admin_notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (moderator_id) REFERENCES admins(user_id)
                )
            ''')
            
            # Таблица сообщений
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    from_user_id INTEGER,
                    from_admin_id INTEGER,
                    to_user_id INTEGER,
                    to_username TEXT,
                    chat_id INTEGER,
                    message_type TEXT,
                    message_text TEXT,
                    media_path TEXT,
                    sent_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    delivered_date DATETIME,
                    read_date DATETIME,
                    status TEXT DEFAULT 'sent',
                    encryption_key TEXT,
                    reply_to_message_id INTEGER,
                    forwarded_from TEXT,
                    is_forwarded BOOLEAN DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # Таблица модерации
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS moderation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    code_sent TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    approved_by INTEGER,
                    approved_at DATETIME,
                    rejected_by INTEGER,
                    rejected_at DATETIME,
                    rejected_reason TEXT,
                    channel_messages TEXT DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (approved_by) REFERENCES admins(user_id),
                    FOREIGN KEY (rejected_by) REFERENCES admins(user_id)
                )
            ''')
            
            # Таблица сессий пересылки
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS forwarding_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    target_channel TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    settings TEXT DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица логов безопасности
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    admin_id INTEGER,
                    action TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    details TEXT,
                    risk_level INTEGER DEFAULT 0,
                    is_suspicious BOOLEAN DEFAULT 0
                )
            ''')
            
            # Добавляем главного админа если его нет
            self.cursor.execute(
                "SELECT 1 FROM admins WHERE user_id = ?",
                (config.MAIN_ADMIN_ID,)
            )
            if not self.cursor.fetchone():
                token = encryptor.generate_token()
                self.cursor.execute('''
                    INSERT INTO admins 
                    (user_id, username, first_name, is_main_admin, session_token, session_expires, permissions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config.MAIN_ADMIN_ID,
                    'main_admin',
                    'Главный Админ',
                    1,
                    token,
                    (datetime.now() + timedelta(days=30)).isoformat(),
                    'all'
                ))
                logger.info(f"Добавлен главный админ: {config.MAIN_ADMIN_ID}")
            
            self.conn.commit()
            logger.info("Все таблицы базы данных инициализированы")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Выполняет SQL запрос"""
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            self.conn.rollback()
            raise
    
    def fetch_one(self, query: str, params: tuple = ()):
        """Возвращает одну строку"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка fetch_one: {e}")
            return None
    
    def fetch_all(self, query: str, params: tuple = ()):
        """Возвращает все строки"""
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка fetch_all: {e}")
            return []
    
    def insert_user(self, user_id: int, username: str = None, first_name: str = None, 
                   last_name: str = None, phone: str = None) -> bool:
        """Добавляет или обновляет пользователя"""
        try:
            self.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, phone, phone_hash, last_activity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                username,
                first_name,
                last_name,
                phone,
                encryptor.hash_data(phone) if phone else None,
                datetime.now().isoformat()
            ))
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False
    
    def get_user(self, user_id: int):
        """Получает информацию о пользователе"""
        return self.fetch_one(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )
    
    def update_user_activity(self, user_id: int):
        """Обновляет время последней активности"""
        try:
            self.execute(
                "UPDATE users SET last_activity = ?, messages_count = messages_count + 1 WHERE user_id = ?",
                (datetime.now().isoformat(), user_id)
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления активности: {e}")
            return False
    
    def close(self):
        """Закрывает соединение с БД"""
        if self.conn:
            self.conn.close()
            logger.info("Соединение с БД закрыто")

# Создаем экземпляр базы данных
db = Database()

# ========== СОСТОЯНИЯ FSM ==========
class SellerStates(StatesGroup):
    waiting_phone = State()
    waiting_sms_code = State()
    waiting_item_type = State()
    waiting_photos = State()
    waiting_description = State()
    waiting_confirm = State()

class AdminStates(StatesGroup):
    waiting_admin_username = State()
    waiting_admin_permissions = State()
    waiting_admin_confirm = State()
    waiting_message_username = State()
    waiting_message_text = State()
    waiting_message_media = State()
    waiting_broadcast_text = State()
    waiting_channel_id = State()
    waiting_channel_action = State()

class UserStates(StatesGroup):
    waiting_verification = State()
    waiting_contact = State()
    waiting_feedback = State()

# ========== МЕНЕДЖЕР АДМИНИСТРАТОРОВ ==========
class AdminManager:
    """Управление администраторами системы"""
    
    def __init__(self):
        self.admin_cache = {}
        self.load_admins_cache()
    
    def load_admins_cache(self):
        """Загружает администраторов в кэш"""
        try:
            admins = db.fetch_all(
                "SELECT user_id, username, permissions, is_main_admin FROM admins WHERE is_active = 1"
            )
            
            self.admin_cache = {}
            for admin in admins:
                self.admin_cache[admin[0]] = {
                    'username': admin[1],
                    'permissions': admin[2],
                    'is_main_admin': bool(admin[3])
                }
            
            logger.info(f"Загружено {len(self.admin_cache)} администраторов в кэш")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша администраторов: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in self.admin_cache
    
    def is_main_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь главным администратором"""
        if user_id in self.admin_cache:
            return self.admin_cache[user_id]['is_main_admin']
        return False
    
    def has_permission(self, user_id: int, permission: str) -> bool:
        """Проверяет, есть ли у администратора определенное разрешение"""
        if not self.is_admin(user_id):
            return False
        
        admin_data = self.admin_cache[user_id]
        
        # Главный админ имеет все права
        if admin_data['is_main_admin']:
            return True
        
        permissions = admin_data['permissions']
        
        # Если разрешения 'all' - все доступно
        if permissions == 'all':
            return True
        
        # Проверяем конкретное разрешение
        permission_list = [p.strip() for p in permissions.split(',')]
        return permission in permission_list
    
    def get_all_admins(self) -> List[Dict]:
        """Возвращает список всех администраторов"""
        try:
            admins = db.fetch_all('''
                SELECT a.user_id, a.username, a.added_by, a.added_date, a.permissions, 
                       a.is_main_admin, b.username as added_by_username
                FROM admins a
                LEFT JOIN admins b ON a.added_by = b.user_id
                WHERE a.is_active = 1
                ORDER BY a.is_main_admin DESC, a.added_date DESC
            ''')
            
            result = []
            for admin in admins:
                result.append({
                    'user_id': admin[0],
                    'username': admin[1],
                    'added_by': admin[2],
                    'added_by_username': admin[6],
                    'added_date': admin[3],
                    'permissions': admin[4],
                    'is_main_admin': bool(admin[5])
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения списка администраторов: {e}")
            return []
    
    def add_admin(self, user_id: int, username: str, added_by: int, permissions: str = 'basic') -> Dict:
        """Добавляет нового администратора"""
        try:
            # Проверяем, не является ли уже админом
            if self.is_admin(user_id):
                return {
                    'success': False,
                    'error': 'Пользователь уже является администратором'
                }
            
            # Проверяем лимит админов
            admin_count = db.fetch_one("SELECT COUNT(*) FROM admins WHERE is_active = 1")[0]
            if admin_count >= config.MAX_ADMINS:
                return {
                    'success': False,
                    'error': f'Достигнут лимит администраторов ({config.MAX_ADMINS})'
                }
            
            # Генерируем токен сессии
            session_token = encryptor.generate_token()
            session_expires = (datetime.now() + timedelta(days=30)).isoformat()
            
            # Добавляем в базу
            db.execute('''
                INSERT INTO admins 
                (user_id, username, added_by, permissions, session_token, session_expires)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, added_by, permissions, session_token, session_expires))
            
            # Добавляем в кэш
            self.admin_cache[user_id] = {
                'username': username,
                'permissions': permissions,
                'is_main_admin': False
            }
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (added_by, 'add_admin', f'Добавлен админ {username} (ID: {user_id})'))
            
            logger.info(f"Добавлен новый админ: {username} (ID: {user_id})")
            
            return {
                'success': True,
                'user_id': user_id,
                'username': username,
                'permissions': permissions
            }
            
        except Exception as e:
            logger.error(f"Ошибка добавления администратора: {e}")
            return {'success': False, 'error': str(e)}

admin_manager = AdminManager()

# ========== ДЕКОРАТОРЫ ПРОВЕРКИ ПРАВ ==========
def admin_required(require_main: bool = False, required_permission: str = None):
    """Декоратор для проверки прав администратора"""
    def decorator(handler):
        async def wrapper(event, *args, **kwargs):
            user_id = None
            
            # Получаем user_id из разных типов событий
            if isinstance(event, Message):
                user_id = event.from_user.id
            elif isinstance(event, CallbackQuery):
                user_id = event.from_user.id
            elif hasattr(event, 'from_user'):
                user_id = event.from_user.id
            
            if not user_id:
                return
            
            # 1. Проверка на администратора
            if not admin_manager.is_admin(user_id):
                if isinstance(event, Message):
                    await event.answer("❌ У вас нет доступа к этой команде.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("❌ Доступ запрещен.", show_alert=True)
                return
            
            # 2. Проверка на главного админа (если требуется)
            if require_main and not admin_manager.is_main_admin(user_id):
                if isinstance(event, Message):
                    await event.answer("❌ Только главный администратор может использовать эту команду.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("❌ Только главный админ.", show_alert=True)
                return
            
            # 3. Проверка конкретного разрешения (если указано)
            if required_permission and not admin_manager.has_permission(user_id, required_permission):
                if isinstance(event, Message):
                    await event.answer(f"❌ Недостаточно прав. Требуется: {required_permission}")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"❌ Недостаточно прав.", show_alert=True)
                return
            
            # Все проверки пройдены - выполняем обработчик
            return await handler(event, *args, **kwargs)
        return wrapper
    return decorator

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start - главное меню"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    logger.info(f"Команда /start от пользователя {user_id} (@{username})")
    
    # Регистрируем пользователя
    db.insert_user(user_id, username, first_name, last_name)
    db.update_user_activity(user_id)
    
    # Проверяем, является ли админом
    is_admin_user = admin_manager.is_admin(user_id)
    
    if is_admin_user:
        # Меню для администратора
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Каналы", callback_data="admin_channels")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton(text="💰 Продать товар", callback_data="sell_item")],
            [InlineKeyboardButton(text="ℹ️ О нас", callback_data="about_us")]
        ])
        
        welcome_text = f"""
👑 <b>ДОБРО ПОЖАЛОВАТЬ, АДМИНИСТРАТОР!</b>

👤 <b>Ваши данные:</b>
• ID: <code>{user_id}</code>
• Имя: {first_name}
• Username: @{username if username else 'нет'}

📊 <b>Панель администратора:</b>
Здесь вы можете управлять системой, пользователями и настройками.

<b>Выберите действие:</b>
        """
    else:
        # Меню для обычного пользователя
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")],
            [InlineKeyboardButton(text="ℹ️ О НАС", callback_data="about_us")],
            [InlineKeyboardButton(text="📞 СВЯЗАТЬСЯ", callback_data="contact")],
            [InlineKeyboardButton(text="📊 МОЙ СТАТУС", callback_data="my_status")]
        ])
        
        welcome_text = f"""
🏪 <b>ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН Money Moves Bot!</b>

👋 <b>Привет, {first_name}!</b>

💰 <b>Мы покупаем:</b>
• 🎮 Игровые аккаунты (Steam, Epic Games, Origin)
• 💎 Внутриигровые предметы (CS:GO, Dota 2, TF2)
• 🎫 Игровые ключи (Steam, Xbox, PlayStation)
• 📱 Цифровые подарки (Apple, Amazon, Google)
• 🛬 Телеграмм подарки
• 💳 Электронные ваучеры

✅ <b>Преимущества:</b>
• Мгновенная оплата
• Высокие цены
• Гарантия сделки
• Анонимность

<b>Выберите действие:</b>
        """
    
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help - справка"""
    help_text = """
ℹ️ <b>СПРАВКА ПО КОМАНДАМ</b>

<b>Основные команды:</b>
/start - Главное меню
/help - Эта справка
/status - Ваш статус
/admin - Панель администратора (если вы админ)

<b>Для продавцов:</b>
1. Нажмите /start
2. Выберите "💰 ПРОДАТЬ ТОВАР"
3. Подтвердите номер телефона
4. Выберите категорию товара
5. Опишите товар

<b>Процесс продажи:</b>
• Регистрация и верификация
• Выбор категории товара
• Описание товара
• Модерация администратором
• Согласование цены
• Передача товара и оплата

<b>Контакты:</b>
• Поддержка: @support
• Администрация: @admin

<b>Гарантии:</b>
• Полная анонимность
• Защита от мошенничества
• Юридическое оформление
• Мгновенные выплаты
    """
    
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status - статус пользователя"""
    user_id = message.from_user.id
    
    user_data = db.get_user(user_id)
    
    if user_data:
        phone = user_data['phone'] if user_data['phone'] else "Не подтвержден"
        registered = user_data['registered']
        is_verified = "✅ Да" if user_data['is_verified'] else "❌ Нет"
        messages_count = user_data['messages_count']
        
        status_text = f"""
📊 <b>ВАШ СТАТУС</b>

👤 <b>Данные:</b>
• ID: <code>{user_id}</code>
• Имя: {message.from_user.first_name}
• Username: @{message.from_user.username or 'нет'}
• Телефон: {phone}
• Верификация: {is_verified}

📈 <b>Статистика:</b>
• Зарегистрирован: {registered[:10] if registered else 'Неизвестно'}
• Сообщений: {messages_count}
• Последняя активность: сейчас

💼 <b>Продажи:</b>
Для продажи товара нажмите /start
        """
    else:
        status_text = "❌ Вы не зарегистрированы. Нажмите /start для регистрации."
    
    await message.answer(status_text, parse_mode="HTML")

@dp.message(Command("admin"))
@admin_required()
async def cmd_admin_panel(message: Message):
    """Команда /admin - панель администратора"""
    user_id = message.from_user.id
    
    # Получаем статистику
    total_users = db.fetch_one("SELECT COUNT(*) FROM users")[0] or 0
    verified_users = db.fetch_one("SELECT COUNT(*) FROM users WHERE is_verified = 1")[0] or 0
    total_admins = len(admin_manager.admin_cache)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Полная статистика", callback_data="admin_full_stats")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_user_list")],
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
        [InlineKeyboardButton(text="📢 Управление каналами", callback_data="admin_channels")],
        [InlineKeyboardButton(text="⚙️ Настройки системы", callback_data="admin_system_settings")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")]
    ])
    
    admin_text = f"""
👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>

👤 <b>Администратор:</b>
• ID: <code>{user_id}</code>
• Имя: {message.from_user.first_name}
• Права: {'👑 Главный админ' if admin_manager.is_main_admin(user_id) else '👮 Админ'}

📊 <b>Статистика системы:</b>
• Всего пользователей: {total_users}
• Верифицировано: {verified_users}
• Администраторов: {total_admins}
• Лимит админов: {config.MAX_ADMINS}

🔧 <b>Выберите действие:</b>
    """
    
    await message.answer(admin_text, parse_mode="HTML", reply_markup=keyboard)

# ========== ОБРАБОТКА КНОПОК ==========
@dp.callback_query(F.data == "sell_item")
async def callback_sell_item(callback_query: CallbackQuery, state: FSMContext):
    """Кнопка 'Продать товар'"""
    user_id = callback_query.from_user.id
    
    # Проверяем верификацию
    user_data = db.get_user(user_id)
    
    if not user_data or not user_data['is_verified']:
        # Требуется верификация
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 ПОДТВЕРДИТЬ НОМЕР", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await state.set_state(SellerStates.waiting_phone)
        await callback_query.message.edit_text(
            "📱 <b>ТРЕБУЕТСЯ ВЕРИФИКАЦИЯ</b>\n\n"
            "Для продажи товаров необходимо подтвердить ваш номер телефона.\n\n"
            "<b>Зачем это нужно:</b>\n"
            "• Защита от мошенничества\n"
            "• Гарантия выплат\n"
            "• Юридическое оформление сделок\n\n"
            "<b>Нажмите кнопку для подтверждения номера:</b>",
            parse_mode="HTML"
        )
        
        # Отправляем отдельное сообщение с клавиатурой
        await callback_query.message.answer(
            "Пожалуйста, отправьте ваш номер телефона:",
            reply_markup=keyboard
        )
    else:
        # Пользователь уже верифицирован
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Игровой аккаунт", callback_data="item_type_account")],
            [InlineKeyboardButton(text="💎 Цифровой предмет", callback_data="item_type_digital")],
            [InlineKeyboardButton(text="🎫 Игровой ключ", callback_data="item_type_key")],
            [InlineKeyboardButton(text="📱 Цифровой подарок", callback_data="item_type_gift")],
            [InlineKeyboardButton(text="💳 Электронные деньги", callback_data="item_type_money")],
            [InlineKeyboardButton(text="📦 Другое", callback_data="item_type_other")]
        ])
        
        await state.set_state(SellerStates.waiting_item_type)
        await callback_query.message.edit_text(
            "🎯 <b>ЧТО ВЫ ХОТИТЕ ПРОДАТЬ?</b>\n\n"
            "<b>Выберите категорию вашего товара:</b>\n\n"
            "• 🎮 <b>Игровой аккаунт</b> - Steam, Epic Games, Origin, Uplay\n"
            "• 💎 <b>Цифровой предмет</b> - CS:GO скины, Dota 2 предметы\n"
            "• 🎫 <b>Игровой ключ</b> - Активационный ключ игры\n"
            "• 📱 <b>Цифровой подарок</b> - Gift Card, ваучер\n"
            "• 💳 <b>Электронные деньги</b> - Qiwi, Яндекс.Деньги\n"
            "• 📦 <b>Другое</b> - Укажите в описании",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    await callback_query.answer()

@dp.callback_query(F.data == "about_us")
async def callback_about_us(callback_query: CallbackQuery):
    """Кнопка 'О нас'"""
    about_text = """
🏪 <b>О НАС - Money Moves Bot</b>

Мы - надежная платформа для покупки и продажи игровых ценностей и цифровых товаров.

<b>📅 Наша история:</b>
• Основаны в 2023 году
• Обработано более 10,000 сделок
• 99.8% положительных отзывов
• Работаем по всему миру

<b>✅ Наши преимущества:</b>
• <b>Безопасность</b> - Все сделки защищены гарантией
• <b>Скорость</b> - Выплаты в течение 1-24 часов
• <b>Выгода</b> - Самые высокие цены на рынке
• <b>Поддержка</b> - Круглосуточная помощь

<b>🛡️ Наши гарантии:</b>
1. Полная анонимность
2. Защита от мошенничества
3. Мгновенные выплаты
4. Юридическая поддержка

<b>💼 Мы покупаем:</b>
• Игровые аккаунты всех платформ
• Цифровые предметы и скины
• Игровые ключи и подписки
• Цифровые подарки и ваучеры
• Электронные деньги и криптовалюту

<b>📞 Контакты:</b>
• Поддержка: @support
• Администрация: @admin
• Партнерство: @partner

<b>Присоединяйтесь к нам уже сегодня!</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")],
        [InlineKeyboardButton(text="📞 СВЯЗАТЬСЯ", callback_data="contact")]
    ])
    
    await callback_query.message.edit_text(about_text, parse_mode="HTML", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query(F.data == "contact")
async def callback_contact(callback_query: CallbackQuery):
    """Кнопка 'Связаться'"""
    contact_text = """
📞 <b>СВЯЗЬ С НАМИ</b>

<b>Для связи используйте:</b>

👤 <b>Техническая поддержка:</b>
• @support - вопросы по работе бота
• Время ответа: 5-30 минут

👑 <b>Администрация:</b>
• @admin - вопросы по сделкам
• Время ответа: 1-12 часов

🤝 <b>Партнерство:</b>
• @partner - сотрудничество
• Время ответа: 24-48 часов

<b>📝 Рекомендации:</b>
• Пишите четко и по делу
• Указывайте ваш ID: <code>{user_id}</code>
• Прикладывайте скриншоты при необходимости
• Будьте вежливы

<b>⏰ Время работы:</b>
• Поддержка: 24/7
• Администрация: 10:00-22:00 (МСК)
    """.format(user_id=callback_query.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
    ])
    
    await callback_query.message.edit_text(contact_text, parse_mode="HTML", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query(F.data == "my_status")
async def callback_my_status(callback_query: CallbackQuery):
    """Кнопка 'Мой статус'"""
    user_id = callback_query.from_user.id
    user_data = db.get_user(user_id)
    
    if user_data:
        phone = user_data['phone'] if user_data['phone'] else "Не подтвержден"
        is_verified = "✅ Да" if user_data['is_verified'] else "❌ Нет"
        rating = user_data['rating'] or 5
        balance = user_data['balance'] or 0
        registered = user_data['registered'][:10] if user_data['registered'] else "Неизвестно"
        
        # Получаем количество заявок пользователя
        items_count = db.fetch_one(
            "SELECT COUNT(*) FROM items WHERE user_id = ?",
            (user_id,)
        )[0] or 0
        
        # Получаем количество одобренных заявок
        approved_count = db.fetch_one(
            "SELECT COUNT(*) FROM items WHERE user_id = ? AND status = 'approved'",
            (user_id,)
        )[0] or 0
        
        status_text = f"""
📊 <b>ВАШ СТАТУС И СТАТИСТИКА</b>

👤 <b>Личные данные:</b>
• ID: <code>{user_id}</code>
• Имя: {callback_query.from_user.first_name}
• Username: @{callback_query.from_user.username or 'нет'}
• Телефон: {phone}
• Верификация: {is_verified}
• Рейтинг: {'⭐' * rating}

💰 <b>Финансы:</b>
• Баланс: {balance} руб.
• Доступно для вывода: {balance} руб.

📦 <b>Продажи:</b>
• Всего заявок: {items_count}
• Одобрено: {approved_count}
• На модерации: {items_count - approved_count}

📅 <b>Активность:</b>
• Зарегистрирован: {registered}
• Сообщений отправлено: {user_data['messages_count']}
        """
    else:
        status_text = "❌ Вы не зарегистрированы. Нажмите /start для регистрации."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
    ])
    
    await callback_query.message.edit_text(status_text, parse_mode="HTML", reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query(F.data == "main_menu")
async def callback_main_menu(callback_query: CallbackQuery, state: FSMContext):
    """Кнопка 'В главное меню'"""
    await state.clear()
    await cmd_start(callback_query.message, state)

# ========== ОБРАБОТКА КОНТАКТОВ ==========
@dp.message(F.contact, SellerStates.waiting_phone)
async def handle_contact(message: Message, state: FSMContext):
    """Обработка отправки контакта"""
    user_id = message.from_user.id
    contact = message.contact
    phone = contact.phone_number
    
    logger.info(f"Получен контакт от {user_id}: {phone}")
    
    # Убираем + если есть
    if phone.startswith('+'):
        phone = phone[1:]
    
    # Сохраняем номер телефона
    db.execute(
        "UPDATE users SET phone = ?, phone_hash = ? WHERE user_id = ?",
        (phone, encryptor.hash_data(phone), user_id)
    )
    
    # Генерируем код подтверждения
    code = str(random.randint(10000, 99999))
    db.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (code, user_id)
    )
    
    # Отправляем сообщение с кодом
    await message.answer(
        f"✅ <b>НОМЕР ПРИНЯТ!</b>\n\n"
        f"📱 Ваш номер: +{phone}\n\n"
        f"🔢 <b>ВАШ КОД ПОДТВЕРЖДЕНИЯ: {code}</b>\n\n"
        f"<i>Введите этот 5-значный код для завершения верификации:</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    
    await state.set_state(SellerStates.waiting_sms_code)
    
    # Уведомляем админа
    try:
        await bot.send_message(
            config.MAIN_ADMIN_ID,
            f"📱 <b>НОВЫЙ КОНТАКТ ОТ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            f"👤 Пользователь: {message.from_user.first_name}\n"
            f"🔗 Username: @{message.from_user.username or 'нет'}\n"
            f"🆔 ID: {user_id}\n"
            f"📱 Телефон: +{phone}\n"
            f"🔢 Код подтверждения: {code}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить админа: {e}")

# ========== ОБРАБОТКА SMS КОДА ==========
@dp.message(SellerStates.waiting_sms_code, F.text.regexp(r'^\d{5}$'))
async def handle_sms_code(message: Message, state: FSMContext):
    """Обработка ввода SMS кода"""
    user_id = message.from_user.id
    code = message.text
    
    # Получаем сохраненный код
    user_data = db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Ошибка: пользователь не найден. Начните с /start")
        await state.clear()
        return
    
    saved_code = user_data['code']
    
    if saved_code and saved_code == code:
        # Код верный
        db.execute(
            "UPDATE users SET is_verified = 1, verification_date = ?, code = NULL WHERE user_id = ?",
            (datetime.now().isoformat(), user_id)
        )
        
        await message.answer(
            "✅ <b>ВЕРИФИКАЦИЯ УСПЕШНО ЗАВЕРШЕНА!</b>\n\n"
            "🎉 Теперь вы можете продавать товары в нашем магазине.\n\n"
            "<b>Следующий шаг:</b>\n"
            "Выберите категорию товара для продажи.",
            parse_mode="HTML"
        )
        
        # Показываем выбор категории
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Игровой аккаунт", callback_data="item_type_account")],
            [InlineKeyboardButton(text="💎 Цифровой предмет", callback_data="item_type_digital")],
            [InlineKeyboardButton(text="🎫 Игровой ключ", callback_data="item_type_key")],
            [InlineKeyboardButton(text="📱 Цифровой подарок", callback_data="item_type_gift")],
            [InlineKeyboardButton(text="💳 Электронные деньги", callback_data="item_type_money")],
            [InlineKeyboardButton(text="📦 Другое", callback_data="item_type_other")]
        ])
        
        await state.set_state(SellerStates.waiting_item_type)
        await message.answer(
            "🎯 <b>ЧТО ВЫ ХОТИТЕ ПРОДАТЬ?</b>\n\n"
            "<b>Выберите категорию вашего товара:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Уведомляем админа
        try:
            await bot.send_message(
                config.MAIN_ADMIN_ID,
                f"✅ <b>ПОЛЬЗОВАТЕЛЬ ВЕРИФИЦИРОВАН</b>\n\n"
                f"👤 Пользователь: {message.from_user.first_name}\n"
                f"🔗 Username: @{message.from_user.username or 'нет'}\n"
                f"🆔 ID: {user_id}\n"
                f"📱 Телефон: +{user_data['phone']}\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить админа: {e}")
            
    else:
        await message.answer(
            "❌ <b>НЕВЕРНЫЙ КОД</b>\n\n"
            "Пожалуйста, проверьте код и попробуйте еще раз.\n\n"
            "Если код не пришел, начните процесс заново через /start",
            parse_mode="HTML"
        )

@dp.message(SellerStates.waiting_sms_code)
async def handle_wrong_sms_code(message: Message):
    """Обработка неверного формата кода"""
    await message.answer(
        "❌ <b>НЕВЕРНЫЙ ФОРМАТ КОДА</b>\n\n"
        "Код должен состоять из 5 цифр.\n"
        "Пример: 12345\n\n"
        "Пожалуйста, введите 5-значный код:"
    )

# ========== ВЫБОР ТИПА ТОВАРА ==========
@dp.callback_query(F.data.startswith("item_type_"))
async def handle_item_type(callback_query: CallbackQuery, state: FSMContext):
    """Обработка выбора типа товара"""
    item_type_key = callback_query.data.replace("item_type_", "")
    
    item_types = {
        "account": "🎮 Игровой аккаунт",
        "digital": "💎 Цифровой предмет",
        "key": "🎫 Игровой ключ",
        "gift": "📱 Цифровой подарок",
        "money": "💳 Электронные деньги",
        "other": "📦 Другое"
    }
    
    item_type = item_types.get(item_type_key, "📦 Другое")
    
    await state.update_data(item_type=item_type)
    await state.set_state(SellerStates.waiting_description)
    
    # Определяем текст в зависимости от типа товара
    description_guides = {
        "account": """
<b>Пример описания для игрового аккаунта:</b>
• Платформа: Steam/Epic Games/Origin
• Количество игр: 15
• Уровень/ранг: Global Elite в CS:GO
• Наличие привязок: телефон, почта
• История аккаунта: с 2015 года
• Дополнительно: Prime статус, инвентарь на 5000 руб.
        """,
        "digital": """
<b>Пример описания для цифрового предмета:</b>
• Игра: CS:GO
• Название предмета: Нож Бабочка | Doppler
• Редкость: Covert
• Состояние: Factory New (FN)
• Особенности: Phase 2, полный Fade
• Float: 0.012345
        """,
        "key": """
<b>Пример описания для игрового ключа:</b>
• Игра: Cyberpunk 2077
• Платформа: Steam/GOG/Epic
• Регион: Worldwide/RU+CIS
• Тип ключа: Цифровая лицензия
• Источник: Официальный магазин
• Срок действия: Бессрочно
        """,
        "gift": """
<b>Пример описания для цифрового подарка:</b>
• Тип: Steam Gift Card
• Номинал: 1000 руб./50 USD
• Регион: Россия/Международный
• Срок действия: 1 год
• Способ получения: Код/Ссылка
        """,
        "money": """
<b>Пример описания для электронных денег:</b>
• Сервис: Qiwi/Яндекс.Деньги
• Сумма: 5000 руб.
• Способ пополнения: Карта/Крипта
• История аккаунта: Без истории
• Привязки: Без привязок
        """,
        "other": """
<b>Пример описания для другого товара:</b>
• Что именно продаете?
• Откуда товар?
• Какое состояние?
• Есть ли гарантии?
• Почему продаете?
        """
    }
    
    guide = description_guides.get(item_type_key, description_guides["other"])
    
    await callback_query.message.edit_text(
        f"📝 <b>ОПИСАНИЕ ТОВАРА</b>\n\n"
        f"<b>Категория:</b> {item_type}\n\n"
        f"<b>Подробно опишите ваш товар:</b>\n"
        f"{guide}\n\n"
        f"<b>Чем подробнее описание - тем выше цена и быстрее обработка!</b>\n\n"
        f"<i>Отправьте подробное описание вашего товара:</i>",
        parse_mode="HTML"
    )
    
    await callback_query.answer()

# ========== ОПИСАНИЕ ТОВАРА ==========
@dp.message(SellerStates.waiting_description)
async def handle_item_description(message: Message, state: FSMContext):
    """Обработка описания товара"""
    user_id = message.from_user.id
    description = message.text
    
    if len(description) < 10:
        await message.answer(
            "❌ <b>СЛИШКОМ КОРОТКОЕ ОПИСАНИЕ</b>\n\n"
            "Пожалуйста, опишите товар подробнее (минимум 10 символов).\n"
            "Чем подробнее описание - тем выше цена.\n\n"
            "Отправьте описание еще раз:"
        )
        return
    
    user_data = await state.get_data()
    item_type = user_data.get('item_type', '📦 Другое')
    
    # Сохраняем заявку в базу
    db.execute('''
        INSERT INTO items (user_id, item_type, description, status, created)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, item_type, description, 'pending', datetime.now().isoformat()))
    
    item_id = db.cursor.lastrowid
    
    # Получаем информацию о пользователе
    user_info = db.get_user(user_id)
    phone = user_info['phone'] if user_info and user_info['phone'] else "Не указан"
    
    # Отправляем админу
    try:
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_item:{item_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_item:{item_id}")
            ],
            [
                InlineKeyboardButton(text="💬 Написать пользователю", callback_data=f"admin_message_user:{user_id}")
            ]
        ])
        
        await bot.send_message(
            config.MAIN_ADMIN_ID,
            f"🆕 <b>НОВАЯ ЗАЯВКА #{item_id}</b>\n\n"
            f"👤 <b>Продавец:</b>\n"
            f"• Имя: {message.from_user.first_name}\n"
            f"• Username: @{message.from_user.username or 'нет'}\n"
            f"• ID: {user_id}\n"
            f"• Телефон: +{phone}\n\n"
            f"🏷 <b>Категория:</b> {item_type}\n\n"
            f"📝 <b>Описание:</b>\n"
            f"{description[:500]}{'...' if len(description) > 500 else ''}\n\n"
            f"⏰ <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}",
            parse_mode="HTML",
            reply_markup=admin_keyboard
        )
    except Exception as e:
        logger.error(f"Не удалось отправить админу: {e}")
    
    await message.answer(
        f"✅ <b>ЗАЯВКА #{item_id} ПРИНЯТА!</b>\n\n"
        f"<b>Категория:</b> {item_type}\n"
        f"<b>Статус:</b> На модерации ⏳\n\n"
        f"<b>Что дальше:</b>\n"
        f"1. Модератор оценит ваш товар (1-24 часа)\n"
        f"2. Вы получите предложение цены\n"
        f"3. После согласия - инструкции по передаче\n"
        f"4. Получение денег на карту/кошелек\n\n"
        f"<b>Среднее время проверки:</b> 2-4 часа\n"
        f"<b>Следить за статусом:</b> /status\n\n"
        f"💰 <b>Готовы продать еще товар?</b>",
        parse_mode="HTML"
    )
    
    await state.clear()

# ========== АДМИН: ОДОБРЕНИЕ/ОТКЛОНЕНИЕ ТОВАРА ==========
@dp.callback_query(F.data.startswith("admin_approve_item:"))
@admin_required()
async def admin_approve_item(callback_query: CallbackQuery):
    """Админ одобряет товар"""
    try:
        item_id = int(callback_query.data.split(":")[1])
        admin_id = callback_query.from_user.id
        
        # Получаем информацию о товаре
        item_data = db.fetch_one(
            "SELECT user_id, description, item_type FROM items WHERE id = ?",
            (item_id,)
        )
        
        if not item_data:
            await callback_query.answer("❌ Товар не найден")
            return
        
        user_id, description, item_type = item_data
        
        # Обновляем статус товара
        db.execute(
            "UPDATE items SET status = 'approved', moderator_id = ?, moderated_date = ? WHERE id = ?",
            (admin_id, datetime.now().isoformat(), item_id)
        )
        
        # Отправляем сообщение пользователю
        try:
            user_info = db.get_user(user_id)
            if user_info:
                await bot.send_message(
                    user_id,
                    f"✅ <b>ВАША ЗАЯВКА #{item_id} ОДОБРЕНА!</b>\n\n"
                    f"<b>Категория:</b> {item_type}\n"
                    f"<b>Описание:</b> {description[:200]}...\n\n"
                    f"<b>Следующий шаг:</b>\n"
                    f"Администратор свяжется с вами для согласования цены.\n\n"
                    f"<i>Ожидайте сообщения в ближайшее время.</i>",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")
        
        # Обновляем сообщение админу
        await callback_query.message.edit_text(
            f"✅ <b>ТОВАР #{item_id} ОДОБРЕН</b>\n\n"
            f"👤 Пользователь: {user_id}\n"
            f"🏷 Категория: {item_type}\n"
            f"👮 Одобрил: {admin_id}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"<i>Пользователь уведомлен об одобрении.</i>",
            parse_mode="HTML"
        )
        
        await callback_query.answer("✅ Товар одобрен")
        
    except Exception as e:
        logger.error(f"Ошибка одобрения товара: {e}")
        await callback_query.answer("❌ Ошибка")

@dp.callback_query(F.data.startswith("admin_reject_item:"))
@admin_required()
async def admin_reject_item(callback_query: CallbackQuery, state: FSMContext):
    """Админ отклоняет товар"""
    try:
        item_id = int(callback_query.data.split(":")[1])
        await state.update_data(reject_item_id=item_id)
        await state.set_state(AdminStates.waiting_channel_action)
        
        await callback_query.message.edit_text(
            f"📝 <b>УКАЖИТЕ ПРИЧИНУ ОТКЛОНЕНИЯ</b>\n\n"
            f"Товар ID: {item_id}\n\n"
            f"Введите причину отклонения товара:\n\n"
            f"<i>Примеры:\n"
            f"• Неполное описание\n"
            f"• Подозрительный товар\n"
            f"• Нарушение правил\n"
            f"• Другая причина</i>",
            parse_mode="HTML"
        )
        
        await callback_query.answer("Введите причину")
        
    except Exception as e:
        logger.error(f"Ошибка отклонения товара: {e}")
        await callback_query.answer("❌ Ошибка")

@dp.message(AdminStates.waiting_channel_action)
async def admin_reject_reason(message: Message, state: FSMContext):
    """Обработка причины отклонения товара"""
    try:
        user_data = await state.get_data()
        item_id = user_data.get('reject_item_id')
        reason = message.text
        
        if not item_id:
            await message.answer("❌ Ошибка: ID товара не найден")
            await state.clear()
            return
        
        # Получаем информацию о товаре
        item_data = db.fetch_one(
            "SELECT user_id, description, item_type FROM items WHERE id = ?",
            (item_id,)
        )
        
        if not item_data:
            await message.answer("❌ Товар не найден")
            await state.clear()
            return
        
        user_id, description, item_type = item_data
        
        # Обновляем статус товара
        db.execute(
            "UPDATE items SET status = 'rejected', moderator_id = ?, moderated_date = ?, admin_notes = ? WHERE id = ?",
            (message.from_user.id, datetime.now().isoformat(), reason, item_id)
        )
        
        # Отправляем сообщение пользователю
        try:
            await bot.send_message(
                user_id,
                f"❌ <b>ВАША ЗАЯВКА #{item_id} ОТКЛОНЕНА</b>\n\n"
                f"<b>Категория:</b> {item_type}\n"
                f"<b>Описание:</b> {description[:200]}...\n\n"
                f"<b>Причина отклонения:</b>\n"
                f"{reason}\n\n"
                f"<b>Что делать:</b>\n"
                f"1. Исправьте описание\n"
                f"2. Укажите больше деталей\n"
                f"3. Отправьте заявку заново через /start\n\n"
                f"<i>Если есть вопросы - свяжитесь с поддержкой.</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")
        
        await message.answer(
            f"✅ <b>ТОВАР #{item_id} ОТКЛОНЕН</b>\n\n"
            f"👤 Пользователь: {user_id}\n"
            f"🏷 Категория: {item_type}\n"
            f"📝 Причина: {reason}\n"
            f"👮 Отклонил: {message.from_user.id}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"<i>Пользователь уведомлен об отклонении.</i>",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки причины отклонения: {e}")
        await message.answer("❌ Ошибка обработки")
        await state.clear()

# ========== АДМИН: СТАТИСТИКА ==========
@dp.callback_query(F.data == "admin_stats")
@admin_required()
async def admin_stats(callback_query: CallbackQuery):
    """Статистика системы"""
    try:
        # Получаем статистику
        total_users = db.fetch_one("SELECT COUNT(*) FROM users")[0] or 0
        verified_users = db.fetch_one("SELECT COUNT(*) FROM users WHERE is_verified = 1")[0] or 0
        today_users = db.fetch_one(
            "SELECT COUNT(*) FROM users WHERE DATE(registered) = DATE('now')"
        )[0] or 0
        
        total_items = db.fetch_one("SELECT COUNT(*) FROM items")[0] or 0
        pending_items = db.fetch_one("SELECT COUNT(*) FROM items WHERE status = 'pending'")[0] or 0
        approved_items = db.fetch_one("SELECT COUNT(*) FROM items WHERE status = 'approved'")[0] or 0
        
        total_messages = db.fetch_one("SELECT SUM(messages_count) FROM users")[0] or 0
        active_today = db.fetch_one(
            "SELECT COUNT(*) FROM users WHERE DATE(last_activity) = DATE('now')"
        )[0] or 0
        
        stats_text = f"""
📊 <b>СТАТИСТИКА СИСТЕМЫ</b>

👥 <b>Пользователи:</b>
• Всего: {total_users}
• Верифицировано: {verified_users}
• Новых сегодня: {today_users}
• Активных сегодня: {active_today}

📦 <b>Товары:</b>
• Всего заявок: {total_items}
• На модерации: {pending_items}
• Одобрено: {approved_items}
• Отклонено: {total_items - pending_items - approved_items}

💬 <b>Активность:</b>
• Всего сообщений: {total_messages}
• Среднее на пользователя: {total_messages // total_users if total_users > 0 else 0}

🔄 <b>Обновлено:</b> {datetime.now().strftime('%H:%M:%S')}
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📈 Подробная статистика", callback_data="admin_full_stats")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
        ])
        
        await callback_query.message.edit_text(stats_text, parse_mode="HTML", reply_markup=keyboard)
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        await callback_query.answer("❌ Ошибка")

# ========== ОБРАБОТКА ВСЕХ ТЕКСТОВЫХ СООБЩЕНИЙ ==========
@dp.message(F.text)
async def handle_all_text_messages(message: Message):
    """Обработка всех текстовых сообщений"""
    user_id = message.from_user.id
    
    # Обновляем активность
    db.update_user_activity(user_id)
    
    # Если сообщение не начинается с команды
    if not message.text.startswith('/'):
        # Проверяем, админ ли
        if admin_manager.is_admin(user_id):
            # Админы могут отправлять сообщения
            pass
        else:
            # Обычным пользователям показываем подсказку
            await message.answer(
                "🤖 <b>Я - торговый бот Money Moves Bot</b>\n\n"
                "Для начала работы нажмите /start\n"
                "Для справки - /help\n"
                "Для проверки статуса - /status\n\n"
                "<i>Если вы хотите продать товар, начните с команды /start</i>",
                parse_mode="HTML"
            )

# ========== ОБРАБОТКА ВСЕХ ТИПОВ СООБЩЕНИЙ ==========
@dp.message(F.content_type.in_({
    ContentType.PHOTO, ContentType.VIDEO, ContentType.DOCUMENT,
    ContentType.AUDIO, ContentType.VOICE, ContentType.STICKER,
    ContentType.ANIMATION, ContentType.CONTACT, ContentType.LOCATION
}))
async def handle_media_messages(message: Message):
    """Обработка медиа-сообщений"""
    user_id = message.from_user.id
    
    # Обновляем активность
    db.update_user_activity(user_id)
    
    # Определяем тип контента
    content_types = {
        ContentType.PHOTO: "📷 Фото",
        ContentType.VIDEO: "🎥 Видео",
        ContentType.DOCUMENT: "📄 Документ",
        ContentType.AUDIO: "🎵 Аудио",
        ContentType.VOICE: "🎤 Голосовое сообщение",
        ContentType.STICKER: "😊 Стикер",
        ContentType.ANIMATION: "🎬 GIF",
        ContentType.CONTACT: "👤 Контакт",
        ContentType.LOCATION: "📍 Локация"
    }
    
    content_type = content_types.get(message.content_type, "📦 Медиа")
    
    await message.answer(
        f"✅ <b>{content_type} ПРИНЯТО</b>\n\n"
        f"Я получил ваше {content_type.lower()}.\n\n"
        f"<b>Для продажи товара используйте команду /start</b>\n"
        f"<b>Для справки - /help</b>",
        parse_mode="HTML"
    )

# ========== ОБРАБОТКА ОШИБОК ==========
@dp.errors()
async def error_handler(update: types.Update, exception: Exception):
    """Глобальный обработчик ошибок"""
    try:
        logger.error(f"Ошибка при обработке обновления {update}: {exception}", exc_info=True)
        
        # Пытаемся отправить ошибку главному админу
        try:
            error_msg = str(exception)[:500]
            await bot.send_message(
                config.MAIN_ADMIN_ID,
                f"⚠️ <b>ОШИБКА БОТА</b>\n\n"
                f"Тип: {type(exception).__name__}\n"
                f"Ошибка: {error_msg}\n"
                f"Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
        except:
            pass
        
        return True
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")
        return True

# ========== ЗАПУСК БОТА ==========
async def on_startup():
    """Действия при запуске бота"""
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК SWILL BOT - ПОЛНАЯ ВЕРСИЯ")
    logger.info("=" * 60)
    
    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот: @{bot_info.username}")
        logger.info(f"🆔 ID: {bot_info.id}")
        logger.info(f"👤 Имя: {bot_info.first_name}")
        logger.info(f"👑 Главный админ: {config.MAIN_ADMIN_ID}")
        logger.info(f"💾 База данных: {config.DB_PATH}")
        
        # Перезагружаем кэш админов
        admin_manager.load_admins_cache()
        logger.info(f"👥 Администраторов в кэше: {len(admin_manager.admin_cache)}")
        
        # Создаем необходимые директории
        os.makedirs('sessions', exist_ok=True)
        os.makedirs('media', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        logger.info("📁 Директории созданы")
        
        # Уведомляем главного админа о запуске
        try:
            await bot.send_message(
                config.MAIN_ADMIN_ID,
                f"🚀 <b>SWILL BOT УСПЕШНО ЗАПУЩЕН!</b>\n\n"
                f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🤖 Бот: @{bot_info.username}\n"
                f"📊 Версия: Полная\n"
                f"✅ Статус: <b>АКТИВЕН И РАБОТАЕТ</b>\n\n"
                f"<b>Системы готовы:</b>\n"
                f"• 📊 База данных\n"
                f"• 👥 Управление админами\n"
                f"• 📦 Система продаж\n"
                f"• 🔐 Шифрование данных\n\n"
                f"<b>Используйте /start для начала работы.</b>",
                parse_mode="HTML"
            )
            logger.info(f"📨 Уведомление отправлено главному админу {config.MAIN_ADMIN_ID}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу: {e}")
        
        logger.info("=" * 60)
        logger.info("✅ БОТ ГОТОВ К РАБОТЕ")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Остановка бота...")
    
    try:
        # Закрываем базу данных
        db.close()
        logger.info("💾 База данных закрыта")
        
        # Закрываем сессию бота
        await bot.session.close()
        logger.info("🔌 Сессия бота закрыта")
        
        # Уведомляем админа об остановке
        try:
            await bot.send_message(
                config.MAIN_ADMIN_ID,
                f"🛑 <b>SWILL BOT ОСТАНОВЛЕН</b>\n\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
                f"📊 Причина: Плановое отключение\n"
                f"✅ Все данные сохранены",
                parse_mode="HTML"
            )
        except:
            pass
        
        logger.info("✅ Бот успешно остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке бота: {e}")

async def main():
    """Основная функция запуска"""
    try:
        # Настраиваем обработчики запуска и остановки
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)
        
        # Запускаем поллинг
        logger.info("🔄 Запуск поллинга...")
        await dp.start_polling(bot, skip_updates=True)
        
    except KeyboardInterrupt:
        logger.info("⚠️ Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка запуска бота: {e}")
    finally:
        # Гарантируем выполнение shutdown
        await on_shutdown()

if __name__ == "__main__":
    # Устанавливаем кодировку для Windows
    if sys.platform == "win32":
        import locale
        locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)