import asyncio
import random
import sqlite3
import aiohttp
import time
import faker
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types as aiogram_types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# Инициализация фейкера
fake = faker.Faker('ru_RU')

BOT_NAME = "MOON SNOS"
BOT_TOKEN = "9293933717:AAGUSKkDzKDqre0TejgzU2hRvOVOEpkIChY"  # ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ!
ADMIN_IDS = [8653940355, 6380627741] 
REQUIRED_CHANNEL = "@manyapollice"
PROTECTED_BOT = "Shakalbekbot"
DB_NAME = "shakal.db"

# Цены
PRICE_DDOS = 10
PRICE_OSINT = 20
VIP_PRICES = {"week": 70, "month": 100, "forever": 150}

DAILY_LIMIT_NORMAL = 50
DAILY_LIMIT_VIP = float('inf')

VIOLATION_TYPES = {
    "doxxing": {"label": "Доксинг (личные данные)"},
    "copyright": {"label": "Нарушение авторских прав"},
    "spam": {"label": "Спам/реклама"},
    "other": {"label": "Другое"}
}

COLOR_MAP = {'blue': 'Синий', 'green': 'Зеленый', 'red': 'Красный', 'yellow': 'Желтый', 'purple': 'Фиолетовый'}
COLOR_NAMES = COLOR_MAP

def clean_number_input(text: str) -> str:
    text = text.strip()
    if text.startswith('/'):
        text = text[1:]
    return ''.join(filter(str.isdigit, text))

# ============================================================
#  БАЗА ДАННЫХ
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        attacks INTEGER DEFAULT 0,
        joined_date TEXT,
        is_vip INTEGER DEFAULT 0,
        vip_until TEXT,
        daily_attacks INTEGER DEFAULT 0,
        last_attack_date TEXT,
        button_color TEXT DEFAULT 'blue',
        ghost_mode INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 0,
        ddos_requests INTEGER DEFAULT 0,
        osint_requests INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (
        user_id INTEGER,
        target_username TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, target_username)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ad_text', 'Реклама не настроена.')")
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        duration_days INTEGER DEFAULT 0,
        attacks_bonus INTEGER DEFAULT 0,
        type TEXT DEFAULT 'vip',
        created_by INTEGER,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS used_promos (
        user_id INTEGER,
        code TEXT,
        used_at TEXT,
        PRIMARY KEY (user_id, code)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
        target_username TEXT PRIMARY KEY,
        added_by INTEGER,
        added_at TEXT
    )''')
    conn.commit()
    conn.close()
    print("База данных готова.")

# ============================================================
#  ФУНКЦИИ БАЗЫ ДАННЫХ
# ============================================================
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_user_field(user_id, field, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    c.execute('''INSERT INTO users (user_id, username, first_name, joined_date, button_color)
                 VALUES (?, ?, ?, ?, 'blue')''',
              (user_id, username or "нет", first_name or "нет", datetime.now().isoformat()))
    conn.commit()
    conn.close()

def increment_attacks(user_id, count=1):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("SELECT last_attack_date, daily_attacks FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        last_date, daily = row[0], row[1] or 0
        if last_date != today:
            daily = 0
        daily += count
        c.execute("UPDATE users SET attacks = attacks + ?, daily_attacks = ?, last_attack_date = ? WHERE user_id = ?",
                  (count, daily, today, user_id))
    conn.commit()
    conn.close()

def get_daily_attacks(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("SELECT daily_attacks, last_attack_date FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row or row[1] != today:
        return 0
    return row[0] or 0

def is_vip(user_id):
    row = get_user(user_id)
    if not row: return False
    if row[5] != 1: return False
    vip_until = row[6]
    if vip_until is None: return True
    try:
        if datetime.now().isoformat() > vip_until:
            update_user_field(user_id, "is_vip", 0)
            update_user_field(user_id, "vip_until", None)
            return False
        return True
    except:
        return False

def set_vip(user_id, days):
    if days == -1:
        update_user_field(user_id, "is_vip", 1)
        update_user_field(user_id, "vip_until", None)
        return True
    if days <= 0: return False
    until = (datetime.now() + timedelta(days=days)).isoformat()
    update_user_field(user_id, "is_vip", 1)
    update_user_field(user_id, "vip_until", until)
    return True

def get_daily_limit(user_id):
    return DAILY_LIMIT_VIP if is_vip(user_id) else DAILY_LIMIT_NORMAL

def get_button_color(user_id):
    row = get_user(user_id)
    return row[9] if row and row[9] else 'blue'

def set_button_color(user_id, color):
    update_user_field(user_id, "button_color", color)

def get_ghost_mode(user_id):
    row = get_user(user_id)
    return row[10] if row and row[10] else 0

def set_ghost_mode(user_id, mode):
    update_user_field(user_id, "ghost_mode", mode)

def add_target_stat(user_id, target, count=1):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO targets (user_id, target_username, count) VALUES (?, ?, COALESCE((SELECT count FROM targets WHERE user_id=? AND target_username=?), 0)+?)",
              (user_id, target, user_id, target, count))
    conn.commit()
    conn.close()

def get_user_targets(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT target_username, count FROM targets WHERE user_id = ? ORDER BY count DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_setting(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    return [u[0] for u in users]

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, attacks FROM users WHERE ghost_mode = 0 ORDER BY attacks DESC")
    users = c.fetchall()
    conn.close()
    return users

def get_blacklist():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT target_username FROM blacklist")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_to_blacklist(username, admin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO blacklist (target_username, added_by, added_at) VALUES (?, ?, ?)",
                  (username, admin_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def remove_from_blacklist(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM blacklist WHERE target_username = ?", (username,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def is_in_blacklist(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM blacklist WHERE target_username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row is not None

def create_promo(code, max_uses, duration_days, attacks_bonus, promo_type, admin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO promo_codes (code, max_uses, used_count, duration_days, attacks_bonus, type, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (code.lower(), max_uses, 0, duration_days, attacks_bonus, promo_type, admin_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def use_promo(user_id, code):
    code = code.lower().strip()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT max_uses, used_count, duration_days, attacks_bonus, type FROM promo_codes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, "invalid"
    max_uses, used_count, duration, atk_bonus, promo_type = row
    if used_count >= max_uses:
        conn.close()
        return None, "used"
    c.execute("SELECT 1 FROM used_promos WHERE user_id = ? AND code = ?", (user_id, code))
    if c.fetchone():
        conn.close()
        return None, "already"
    if promo_type == "vip" and duration <= 0:
        conn.close()
        return None, "bad_type"
    if promo_type == "attacks" and atk_bonus <= 0:
        conn.close()
        return None, "bad_type"
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    c.execute("INSERT INTO used_promos (user_id, code, used_at) VALUES (?, ?, ?)",
              (user_id, code, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    if promo_type == "vip":
        if set_vip(user_id, duration): return duration, "vip"
        return None, "bad_type"
    elif promo_type == "attacks":
        increment_attacks(user_id, atk_bonus)
        return atk_bonus, "attacks"
    return None, "invalid"

def get_promo_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code, max_uses, used_count, type, duration_days, attacks_bonus FROM promo_codes ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# ============================================================
#  ПОДПИСКА
# ============================================================
def channel_url() -> str:
    if REQUIRED_CHANNEL.startswith("http"): return REQUIRED_CHANNEL
    if REQUIRED_CHANNEL.startswith("@"): return f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    return REQUIRED_CHANNEL

async def check_subscription(user_id):
    if not REQUIRED_CHANNEL: return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться", url=channel_url())],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub")]
    ])

async def ensure_subscribed(message_or_callback, user_id, callback=None):
    if not await check_subscription(user_id):
        text = f"Для использования {BOT_NAME} подпишитесь на канал {REQUIRED_CHANNEL}."
        keyboard = sub_keyboard()
        if callback:
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        else:
            await message_or_callback.answer(text, reply_markup=keyboard)
        return False
    return True

# ============================================================
#  FSM
# ============================================================
class AttackState(StatesGroup):
    waiting_username = State()
    waiting_count = State()
    waiting_violation = State()
    waiting_link = State()

class DdosState(StatesGroup):
    waiting_target = State()
    waiting_count = State()

class OsintState(StatesGroup):
    waiting_phone = State()
    waiting_url = State()

class BroadcastState(StatesGroup):
    waiting_text = State()

class PromoState(StatesGroup):
    waiting_code = State()

class CreatePromoState(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_uses = State()
    waiting_bonus = State()

class BlacklistState(StatesGroup):
    waiting_add = State()
    waiting_remove = State()

class AdState(StatesGroup):
    waiting_text = State()

class EventState(StatesGroup):
    waiting_money_amount = State()
    waiting_attacks_amount = State()

# ============================================================
#  ИМИТАЦИИ
# ============================================================
async def attack_bot(target_username, count, violation_type, link):
    await asyncio.sleep(random.uniform(2, 4))
    successful = int(count * random.uniform(0.7, 0.95))
    return successful, count

async def ddos_bot(target, count):
    await asyncio.sleep(random.uniform(2, 4))
    successful = int(count * random.uniform(0.8, 0.99))
    return successful, count

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================
def main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="Атака", callback_data="attack"), InlineKeyboardButton(text="DDoS", callback_data="ddos")],
        [InlineKeyboardButton(text="OSINT", callback_data="osint_menu"), InlineKeyboardButton(text="Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="Магазин", callback_data="shop"), InlineKeyboardButton(text="Рейтинг", callback_data="rating_attacks")],
        [InlineKeyboardButton(text="Статистика", callback_data="my_stats"), InlineKeyboardButton(text="Поддержка", url="https://t.me/snospve")]
    ]
    
    if is_vip(user_id):
        buttons.append([InlineKeyboardButton(text="Настройки VIP", callback_data="vip_settings")])
        
    if REQUIRED_CHANNEL:
        buttons.append([InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

def osint_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Инфо о номере", callback_data="osint_phone"), InlineKeyboardButton(text="Пинг сайта", callback_data="osint_ping")],
        [InlineKeyboardButton(text="Генератор личности", callback_data="osint_faker")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats"), InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="Создать промокод", callback_data="admin_create_promo"), InlineKeyboardButton(text="Промокоды", callback_data="admin_promo_list")],
        [InlineKeyboardButton(text="Раздача рублей", callback_data="admin_event_money"), InlineKeyboardButton(text="Раздача атак", callback_data="admin_event_attacks")],
        [InlineKeyboardButton(text="Черный список", callback_data="admin_blacklist"), InlineKeyboardButton(text="Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])

def color_choose_keyboard():
    kb = []
    row = []
    for key, name in COLOR_MAP.items():
        row.append(InlineKeyboardButton(text=name, callback_data=f"color_{key}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def vip_settings_keyboard(user_id):
    ghost_status = "Включен" if get_ghost_mode(user_id) else "Выключен"
    kb = [
        [InlineKeyboardButton(text=f"Режим невидимки: {ghost_status}", callback_data="toggle_ghost")],
        [InlineKeyboardButton(text="Цвет кнопок", callback_data="change_color")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def promo_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VIP", callback_data="promo_type_vip"), InlineKeyboardButton(text="Атаки", callback_data="promo_type_attacks")],
        [InlineKeyboardButton(text="Отмена", callback_data="back")]
    ])

def count_keyboard():
    counts = [1, 5, 10, 20, 50, 100, 150, 200, 250, 300]
    kb = []
    row = []
    for c in counts:
        row.append(InlineKeyboardButton(text=str(c), callback_data=f"count_{c}"))
        if len(row) == 3: 
            kb.append(row)
            row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton(text="Ввести вручную", callback_data="count_manual")])
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ============================================================
#  БОТ
# ============================================================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

@dp.errors()
async def errors_handler(event: aiogram_types.ErrorEvent):
    exception = event.exception
    if isinstance(exception, TelegramBadRequest) and "message is not modified" in str(exception):
        return True
    print(f"Ошибка: {exception}")
    return True

# ============================================================
#  СТАРТ
# ============================================================
@dp.message(CommandStart())
async def start_command(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    if not await check_subscription(user_id):
        await message.answer(
            f"Для использования {BOT_NAME} подпишитесь на канал {REQUIRED_CHANNEL}.",
            reply_markup=sub_keyboard()
        )
        return

    text = (
        f"<b>Добро пожаловать в {BOT_NAME}</b>\n\n"
        f"<blockquote>Обычные пользователи: {DAILY_LIMIT_NORMAL} запросов в день.\n"
        f"VIP: безлимит.</blockquote>"
    )
    await message.answer(text, reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.edit_text("<b>Подписка подтверждена.</b>", reply_markup=main_menu(user_id))
    else:
        await callback.message.edit_text(
            f"Вы не подписаны на {REQUIRED_CHANNEL}.\nПодпишитесь и нажмите снова.",
            reply_markup=sub_keyboard()
        )
    await callback.answer()

# ============================================================
#  МАГАЗИН (БЕЗ ПОПОЛНЕНИЯ ЗВЕЗДАМИ)
# ============================================================
@dp.callback_query(F.data == "shop")
async def shop_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    
    row = get_user(user_id)
    balance = row[11] if row else 0
    ddos_reqs = row[12] if row else 0
    osint_reqs = row[13] if row else 0
    
    text = (
        f"<b>Магазин</b>\n\n"
        f"<blockquote>"
        f"Ваш баланс: {balance} руб.\n"
        f"Слоты DDoS: {ddos_reqs} шт.\n"
        f"Слоты OSINT: {osint_reqs} шт.\n"
        f"</blockquote>\n"
        f"<b>Цены:</b>\n"
        f"<blockquote>"
        f"VIP Неделя: {VIP_PRICES['week']} руб.\n"
        f"VIP Месяц: {VIP_PRICES['month']} руб.\n"
        f"VIP Навсегда: {VIP_PRICES['forever']} руб.\n"
        f"DDoS запрос: {PRICE_DDOS} руб/шт.\n"
        f"OSINT запрос: {PRICE_OSINT} руб/шт.\n"
        f"</blockquote>\n"
        f"<b>Пополнение:</b>\n"
        f"<blockquote>Для пополнения баланса напишите @snospve</blockquote>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить VIP", callback_data="buy_vip_menu"), InlineKeyboardButton(text="Купить DDoS", callback_data="buy_ddos")],
        [InlineKeyboardButton(text="Купить OSINT", callback_data="buy_osint"), InlineKeyboardButton(text="Пополнить @snospve", url="https://t.me/snospve")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "buy_vip_menu")
async def buy_vip_menu_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    row = get_user(user_id)
    balance = row[11] if row else 0
    
    text = (
        f"<b>Покупка VIP</b>\n\n"
        f"<blockquote>Ваш баланс: {balance} руб.\n\n"
        f"Неделя: {VIP_PRICES['week']} руб.\n"
        f"Месяц: {VIP_PRICES['month']} руб.\n"
        f"Навсегда: {VIP_PRICES['forever']} руб.</blockquote>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Неделя ({VIP_PRICES['week']}р)", callback_data="buy_vip_week")],
        [InlineKeyboardButton(text=f"Месяц ({VIP_PRICES['month']}р)", callback_data="buy_vip_month")],
        [InlineKeyboardButton(text=f"Навсегда ({VIP_PRICES['forever']}р)", callback_data="buy_vip_forever")],
        [InlineKeyboardButton(text="Назад", callback_data="shop")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_vip_"))
async def buy_vip_process(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    choice = callback.data.split("_")[2]
    price = VIP_PRICES[choice]
    
    row = get_user(user_id)
    balance = row[11] if row else 0
    
    if balance < price:
        await callback.answer(f"Недостаточно средств. Нужно {price} руб.", show_alert=True)
        return
        
    update_user_field(user_id, "balance", balance - price)
    
    if choice == "week":
        set_vip(user_id, 7)
    elif choice == "month":
        set_vip(user_id, 30)
    elif choice == "forever":
        set_vip(user_id, -1)
        
    await callback.message.edit_text(
        f"<b>VIP успешно активирован!</b>\n\n"
        f"<blockquote>Списано: {price} руб.\n"
        f"Остаток: {balance - price} руб.</blockquote>",
        reply_markup=main_menu(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "buy_ddos")
async def buy_ddos_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    row = get_user(user_id)
    balance = row[11] if row else 0
    
    if balance < PRICE_DDOS:
        await callback.answer(f"Недостаточно средств. Нужно {PRICE_DDOS} руб.", show_alert=True)
        return
        
    update_user_field(user_id, "balance", balance - PRICE_DDOS)
    current_reqs = row[12] if row else 0
    update_user_field(user_id, "ddos_requests", current_reqs + 1)
    
    await callback.message.edit_text(
        f"<b>Слот DDoS куплен!</b>\n\n"
        f"<blockquote>Списано: {PRICE_DDOS} руб.\n"
        f"Всего слотов: {current_reqs + 1}</blockquote>",
        reply_markup=main_menu(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "buy_osint")
async def buy_osint_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    row = get_user(user_id)
    balance = row[11] if row else 0
    
    if balance < PRICE_OSINT:
        await callback.answer(f"Недостаточно средств. Нужно {PRICE_OSINT} руб.", show_alert=True)
        return
        
    update_user_field(user_id, "balance", balance - PRICE_OSINT)
    current_reqs = row[13] if row else 0
    update_user_field(user_id, "osint_requests", current_reqs + 1)
    
    await callback.message.edit_text(
        f"<b>Слот OSINT куплен!</b>\n\n"
        f"<blockquote>Списано: {PRICE_OSINT} руб.\n"
        f"Всего слотов: {current_reqs + 1}</blockquote>",
        reply_markup=main_menu(user_id)
    )
    await callback.answer()

# ============================================================
#  ПРОФИЛЬ (С БАЛАНСОМ)
# ============================================================
@dp.callback_query(F.data == "profile")
async def profile_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    
    row = get_user(user_id)
    if not row:
        add_user(user_id, callback.from_user.username, callback.from_user.first_name)
        row = get_user(user_id)
        
    attacks = row[3]
    vip_status = "Активен" if is_vip(user_id) else "Неактивен"
    daily = get_daily_attacks(user_id)
    limit = get_daily_limit(user_id)
    limit_display = "Безлимит" if limit == float('inf') else str(limit)
    balance = row[11] if row else 0
    ddos = row[12] if row else 0
    osint = row[13] if row else 0
    
    text = (
        f"<b>Профиль</b>\n\n"
        f"<blockquote>"
        f"ID: <code>{user_id}</code>\n"
        f"Атак: {attacks}\n"
        f"Сегодня: {daily}/{limit_display}\n"
        f"VIP: {vip_status}\n\n"
        f"<b>Баланс: {balance} руб.</b>\n"
        f"Слоты DDoS: {ddos} шт.\n"
        f"Слоты OSINT: {osint} шт."
        f"</blockquote>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "vip_settings")
async def vip_settings_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    if not is_vip(user_id):
        await callback.answer("Доступно только для VIP.", show_alert=True)
        return
    
    text = "<b>Настройки VIP</b>\n\n<blockquote>Скрытый режим убирает вас из общего рейтинга.</blockquote>"
    await callback.message.edit_text(text, reply_markup=vip_settings_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "toggle_ghost")
async def toggle_ghost_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    current = get_ghost_mode(user_id)
    new_mode = 1 if current == 0 else 0
    set_ghost_mode(user_id, new_mode)
    
    status = "включен" if new_mode else "выключен"
    await callback.answer(f"Режим невидимки {status}.", show_alert=True)
    await callback.message.edit_text("<b>Настройки VIP</b>\n\n<blockquote>Скрытый режим убирает вас из общего рейтинга.</blockquote>", reply_markup=vip_settings_keyboard(user_id))

# ============================================================
#  АТАКА
# ============================================================
@dp.callback_query(F.data == "attack")
async def attack_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await callback.answer(f"Дневной лимит ({limit}) исчерпан. Купите VIP.", show_alert=True)
        return
    
    await callback.message.answer("<b>Введите username цели (без @):</b>", reply_markup=back_menu())
    await state.set_state(AttackState.waiting_username)
    await callback.answer()

@dp.message(AttackState.waiting_username)
async def attack_username(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_subscribed(message, user_id):
        await state.clear()
        return
    target = message.text.strip().lstrip('@')
    if not target:
        await message.answer("Неверный username.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    if is_in_blacklist(target):
        await message.answer(f"Цель @{target} в черном списке.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    if target.lower() == PROTECTED_BOT.lower():
        await message.answer(f"{PROTECTED_BOT} под защитой.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    
    await state.update_data(target=target)
    await message.answer("<b>Сколько жалоб отправить? (1-300):</b>", reply_markup=count_keyboard())
    await state.set_state(AttackState.waiting_count)

@dp.callback_query(F.data.startswith("count_"), AttackState.waiting_count)
async def attack_count_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "count_manual":
        await callback.message.answer("<b>Введите число от 1 до 300:</b>", reply_markup=back_menu())
        return
    try:
        count = int(data.split("_")[1])
    except:
        await callback.answer("Ошибка.", show_alert=True)
        return
    if count < 1 or count > 300:
        await callback.answer("Число от 1 до 300.", show_alert=True)
        return
    await state.update_data(count=count)
    await show_violation_menu(callback.message, state)
    await callback.answer()

@dp.message(AttackState.waiting_count)
async def attack_count_manual(message: aiogram_types.Message, state: FSMContext):
    cleaned = clean_number_input(message.text)
    if not cleaned:
        await message.answer("Введите число от 1 до 300:")
        return
    count = int(cleaned)
    if count < 1 or count > 300:
        await message.answer("Число от 1 до 300:")
        return
    await state.update_data(count=count)
    await show_violation_menu(message, state)

async def show_violation_menu(message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Доксинг", callback_data="violation_doxxing"), InlineKeyboardButton(text="Авторские права", callback_data="violation_copyright")],
        [InlineKeyboardButton(text="Спам", callback_data="violation_spam"), InlineKeyboardButton(text="Другое", callback_data="violation_other")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await message.answer("<b>Выберите тип нарушения:</b>", reply_markup=kb)
    await state.set_state(AttackState.waiting_violation)

@dp.callback_query(F.data.startswith("violation_"), AttackState.waiting_violation)
async def attack_violation(callback: aiogram_types.CallbackQuery, state: FSMContext):
    violation_type = callback.data.split("_")[1]
    await state.update_data(violation=violation_type)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Вставить ссылку", callback_data="link_enter")],
        [InlineKeyboardButton(text="Пропустить", callback_data="link_skip")]
    ])
    await callback.message.answer("<b>Введите ссылку на нарушение:</b>", reply_markup=kb)
    await state.set_state(AttackState.waiting_link)
    await callback.answer()

@dp.callback_query(F.data == "link_enter", AttackState.waiting_link)
async def attack_link_enter(callback: aiogram_types.CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>Введите ссылку:</b>", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "link_skip", AttackState.waiting_link)
async def attack_link_skip(callback: aiogram_types.CallbackQuery, state: FSMContext):
    await state.update_data(link="Без ссылки")
    await finish_attack(callback.message, state, callback.from_user.id, callback)

@dp.message(AttackState.waiting_link)
async def attack_link_input(message: aiogram_types.Message, state: FSMContext):
    link = message.text.strip()
    await state.update_data(link=link or "Без ссылки")
    await finish_attack(message, state, message.from_user.id)

async def finish_attack(message_or_callback, state: FSMContext, user_id, callback=None):
    data = await state.get_data()
    target = data.get("target")
    violation = data.get("violation")
    link = data.get("link", "Без ссылки")
    count = data.get("count", 1)

    if callback:
        msg = await callback.message.answer("<i>Отправка жалоб...</i>")
    else:
        msg = await message_or_callback.answer("<i>Отправка жалоб...</i>")

    successful, total = await attack_bot(target, count, violation, link)
    increment_attacks(user_id, count)
    add_target_stat(user_id, target, count)

    success_rate = int((successful / total) * 100) if total > 0 else 0
    violation_label = VIOLATION_TYPES.get(violation, {}).get("label", "Неизвестно")

    result = (
        f"<b>Отчет об атаке</b>\n\n"
        f"<blockquote>"
        f"Цель: @{target}\n"
        f"Нарушение: {violation_label}\n"
        f"Ссылка: {link}\n\n"
        f"Всего попыток: {total}\n"
        f"Успешно: {successful}\n"
        f"Эффективность: {success_rate}%"
        f"</blockquote>"
    )

    try:
        await msg.edit_text(result, reply_markup=main_menu(user_id))
    except:
        await message_or_callback.answer(result, reply_markup=main_menu(user_id))

    if callback: await callback.answer()
    await state.clear()

# ============================================================
#  DDOS АТАКА
# ============================================================
@dp.callback_query(F.data == "ddos")
async def ddos_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    
    row = get_user(user_id)
    ddos_reqs = row[12] if row else 0
    
    if ddos_reqs <= 0 and not is_vip(user_id):
        await callback.message.answer(
            f"<b>У вас нет слотов для DDoS.</b>\n\n"
            f"<blockquote>Вы можете купить слот за {PRICE_DDOS} руб. в магазине.\n"
            f"Или приобрести VIP для безлимита.</blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="В магазин", callback_data="shop")],
                [InlineKeyboardButton(text="Назад", callback_data="back")]
            ])
        )
        await callback.answer()
        return
        
    if not is_vip(user_id):
        update_user_field(user_id, "ddos_requests", ddos_reqs - 1)
    
    await callback.message.answer("<b>Введите ссылку или IP цели:</b>", reply_markup=back_menu())
    await state.set_state(DdosState.waiting_target)
    await callback.answer()

@dp.message(DdosState.waiting_target)
async def ddos_target(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_subscribed(message, user_id):
        await state.clear()
        return
    target = message.text.strip()
    if not target:
        await message.answer("Неверный формат.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    
    await state.update_data(ddos_target=target)
    await message.answer("<b>Сколько запросов отправить? (1-300):</b>", reply_markup=count_keyboard())
    await state.set_state(DdosState.waiting_count)

@dp.callback_query(F.data.startswith("count_"), DdosState.waiting_count)
async def ddos_count_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "count_manual":
        await callback.message.answer("<b>Введите число от 1 до 300:</b>", reply_markup=back_menu())
        return
    try:
        count = int(data.split("_")[1])
    except:
        await callback.answer("Ошибка.", show_alert=True)
        return
    if count < 1 or count > 300:
        await callback.answer("Число от 1 до 300.", show_alert=True)
        return
    await state.update_data(count=count)
    await finish_ddos(callback.message, state, callback.from_user.id, callback)
    await callback.answer()

@dp.message(DdosState.waiting_count)
async def ddos_count_manual(message: aiogram_types.Message, state: FSMContext):
    cleaned = clean_number_input(message.text)
    if not cleaned:
        await message.answer("Введите число от 1 до 300:")
        return
    count = int(cleaned)
    if count < 1 or count > 300:
        await message.answer("Число от 1 до 300:")
        return
    await state.update_data(count=count)
    await finish_ddos(message, state, message.from_user.id)

async def finish_ddos(message_or_callback, state: FSMContext, user_id, callback=None):
    data = await state.get_data()
    target = data.get("ddos_target")
    count = data.get("count", 1)

    if callback:
        msg = await callback.message.answer("<i>Выполняется DDoS-атака...</i>")
    else:
        msg = await message_or_callback.answer("<i>Выполняется DDoS-атака...</i>")

    successful, total = await ddos_bot(target, count)
    increment_attacks(user_id, count)
    add_target_stat(user_id, target, count)

    success_rate = int((successful / total) * 100) if total > 0 else 0

    result = (
        f"<b>Отчет DDoS</b>\n\n"
        f"<blockquote>"
        f"Цель: {target}\n\n"
        f"Всего запросов: {total}\n"
        f"Успешно: {successful}\n"
        f"Эффективность: {success_rate}%"
        f"</blockquote>"
    )

    try:
        await msg.edit_text(result, reply_markup=main_menu(user_id))
    except:
        await message_or_callback.answer(result, reply_markup=main_menu(user_id))

    if callback: await callback.answer()
    await state.clear()

# ============================================================
#  OSINT МОДУЛЬ
# ============================================================
@dp.callback_query(F.data == "osint_menu")
async def osint_menu_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    
    row = get_user(user_id)
    osint_reqs = row[13] if row else 0
    
    text = (
        f"<b>OSINT Модуль</b>\n\n"
        f"<blockquote>Доступно запросов: {osint_reqs} шт.\n"
        f"Стоимость запроса: {PRICE_OSINT} руб.</blockquote>"
    )
    await callback.message.edit_text(text, reply_markup=osint_menu())
    await callback.answer()

@dp.callback_query(F.data.startswith("osint_") & ~F.data.in_({"osint_menu"}))
async def osint_process_check(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    row = get_user(user_id)
    osint_reqs = row[13] if row else 0
    
    if osint_reqs <= 0 and not is_vip(user_id):
        await callback.message.answer(
            f"<b>У вас нет доступных OSINT-запросов.</b>\n\n"
            f"<blockquote>Купите слот за {PRICE_OSINT} руб. в магазине.</blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="В магазин", callback_data="shop")],
                [InlineKeyboardButton(text="Назад", callback_data="back")]
            ])
        )
        await callback.answer()
        return
        
    if not is_vip(user_id):
        update_user_field(user_id, "osint_requests", osint_reqs - 1)
        
    action = callback.data.split("_")[1]
    if action == "phone":
        await callback.message.edit_text("<b>Информация о номере</b>\n\n<blockquote>Введите номер телефона (например, +79001234567).</blockquote>", reply_markup=back_menu())
        await state.set_state(OsintState.waiting_phone)
    elif action == "ping":
        await callback.message.edit_text("<b>Пинг сайта</b>\n\n<blockquote>Введите URL (например, google.com).</blockquote>", reply_markup=back_menu())
        await state.set_state(OsintState.waiting_url)
    elif action == "faker":
        await send_faker_data(callback.message, user_id)
        return
    await callback.answer()

@dp.message(OsintState.waiting_phone)
async def osint_phone_process(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = clean_number_input(message.text)
    
    if len(phone) < 10:
        await message.answer("Неверный формат номера. Введите номер еще раз:", reply_markup=back_menu())
        return
        
    msg = await message.answer("<i>Анализ базы операторов...</i>")
    
    operator = "Неизвестный оператор"
    region = "Россия"
    
    if phone.startswith('79') or phone.startswith('89'):
        if phone[1:4] in ['900', '901', '902', '903', '904', '905', '906', '908', '909', '950', '951', '952', '953', '960', '961', '962', '963', '964', '965', '966', '967', '968', '969', '980', '981', '982', '983', '984', '985', '986', '987', '988', '989']:
            operator = "Билайн / Мегафон / МТС"
        elif phone[1:4] in ['910', '911', '912', '913', '914', '915', '916', '917', '918', '919', '920', '921', '922', '923', '924', '925', '926', '927', '928', '929', '930', '931', '932', '933', '934', '936', '937', '938', '939', '999']:
            operator = "МТС / Билайн / Теле2"
        else:
            operator = "Мобильный оператор"
    
    result = (
        f"<b>Отчет по номеру:</b> <code>+{phone}</code>\n\n"
        f"<blockquote>"
        f"Страна: {region}\n"
        f"Оператор: {operator}\n"
        f"Статус: Активен (база сотовых сетей)"
        f"</blockquote>"
    )
    
    await msg.edit_text(result, reply_markup=main_menu(user_id))
    await state.clear()

@dp.message(OsintState.waiting_url)
async def osint_ping_process(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    url = message.text.strip()
    if not url.startswith("http"): url = "https://" + url
        
    msg = await message.answer("<i>Выполняется запрос...</i>")
    
    start_time = time.time()
    status_code = "Нет ответа"
    ping_time = 0
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                status_code = response.status
                ping_time = round((time.time() - start_time) * 1000, 2)
    except Exception as e:
        status_code = "Ошибка подключения"
    
    if status_code == 200:
        status_text = "Сайт доступен"
    elif status_code == "Ошибка подключения":
        status_text = "Сайт недоступен (не отвечает)"
    else:
        status_text = f"Ошибка сервера ({status_code})"

    result = (
        f"<b>Статус сайта:</b> <code>{url}</code>\n\n"
        f"<blockquote>"
        f"Статус: {status_text}\n"
        f"Код ответа: {status_code}\n"
        f"Время ответа: {ping_time} мс"
        f"</blockquote>"
    )
    
    await msg.edit_text(result, reply_markup=main_menu(user_id))
    await state.clear()

async def send_faker_data(message, user_id):
    name = fake.name()
    phone = fake.phone_number()
    email = fake.email()
    address = fake.address().replace("\n", ", ")
    passport = f"{random.randint(1000, 9999)} {random.randint(100000, 999999)}"
    
    text = (
        f"<b>Генератор фейковой личности</b>\n\n"
        f"<blockquote>"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
        f"Email: {email}\n"
        f"Адрес: {address}\n"
        f"Паспорт: {passport}"
        f"</blockquote>\n"
        f"<i>* Данные сгенерированы случайно и не принадлежат реальным людям.</i>"
    )
    await message.answer(text, reply_markup=main_menu(user_id))

# ============================================================
#  ПРОМОКОДЫ И СТАТИСТИКА
# ============================================================
@dp.callback_query(F.data == "enter_promo")
async def enter_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    await callback.message.answer("<b>Введите промокод:</b>", reply_markup=back_menu())
    await state.set_state(PromoState.waiting_code)
    await callback.answer()

@dp.message(PromoState.waiting_code)
async def promo_code_handler(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_subscribed(message, user_id):
        await state.clear()
        return
    code = message.text.strip()
    result, typ = use_promo(user_id, code)
    if result is None:
        if typ == "invalid": await message.answer("Промокод не найден.", reply_markup=main_menu(user_id))
        elif typ == "used": await message.answer("Промокод закончился.", reply_markup=main_menu(user_id))
        elif typ == "already": await message.answer("Вы уже использовали этот промокод.", reply_markup=main_menu(user_id))
        else: await message.answer("Ошибка активации.", reply_markup=main_menu(user_id))
    else:
        if typ == "vip": await message.answer(f"<b>VIP активирован на {result} дней.</b>", reply_markup=main_menu(user_id))
        elif typ == "attacks": await message.answer(f"<b>Начислено {result} атак.</b>", reply_markup=main_menu(user_id))
    await state.clear()

@dp.message(F.text, ~F.text.startswith('/'))
async def handle_text(message: aiogram_types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await message.answer(f"Подпишитесь на {REQUIRED_CHANNEL}.", reply_markup=sub_keyboard())
        return
    code = message.text.strip()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM promo_codes WHERE code = ?", (code.lower(),))
    if c.fetchone():
        conn.close()
        result, typ = use_promo(user_id, code)
        if result is None:
            await message.answer("Промокод не найден или использован.", reply_markup=main_menu(user_id))
        else:
            if typ == "vip": await message.answer(f"<b>VIP активирован на {result} дней.</b>", reply_markup=main_menu(user_id))
            elif typ == "attacks": await message.answer(f"<b>Начислено {result} атак.</b>", reply_markup=main_menu(user_id))
    else:
        conn.close()

@dp.callback_query(F.data == "rating_attacks")
async def rating_attacks_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    users = get_all_users()
    if not users:
        await callback.message.edit_text("Рейтинг пуст.", reply_markup=back_menu())
        return
    top = ""
    for i, (uid, username, attacks) in enumerate(users[:10], 1):
        uname = f"@{username}" if username and username != "нет" else f"ID{uid}"
        top += f"{i}. {uname} — {attacks} атак\n"
    
    text = f"<b>Рейтинг по атакам</b>\n\n<blockquote>{top}</blockquote>"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    targets = get_user_targets(user_id)
    if not targets:
        await callback.message.edit_text("Вы еще никого не атаковали.", reply_markup=back_menu())
        return
    lines = []
    total = 0
    for target, count in targets:
        lines.append(f"@{target} — {count} раз")
        total += count
    
    text = f"<b>Статистика</b>\n\n<blockquote>{chr(10).join(lines)}\n\nВсего атак: {total}</blockquote>"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "change_color")
async def change_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    if not is_vip(user_id):
        await callback.answer("Только для VIP.", show_alert=True)
        return
    await callback.message.edit_text("<b>Выберите цвет:</b>", reply_markup=color_choose_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("color_"))
async def set_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback): return
    if not is_vip(user_id):
        await callback.answer("Только для VIP.", show_alert=True)
        return
    color = callback.data.split("_")[1]
    if color not in COLOR_MAP:
        await callback.answer("Неверный цвет.", show_alert=True)
        return
    set_button_color(user_id, color)
    await callback.message.edit_text(f"<b>Цвет изменен на {COLOR_NAMES[color]}.</b>", reply_markup=main_menu(user_id))
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.clear()
    if not await check_subscription(user_id):
        await callback.message.edit_text(f"Вы не подписаны на {REQUIRED_CHANNEL}", reply_markup=sub_keyboard())
        await callback.answer()
        return
    await callback.message.edit_text(f"<b>Главное меню {BOT_NAME}</b>", reply_markup=main_menu(user_id))
    await callback.answer()

# ============================================================
#  АДМИН-ПАНЕЛЬ (РАЗДАЧА С ВВОДОМ СУММЫ)
# ============================================================
@dp.message(Command("admin"))
async def admin_command(message: aiogram_types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Нет доступа.")
        return
    await message.answer("<b>Админ-панель</b>", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    users = get_all_users()
    promos = get_promo_stats()
    top = ""
    for uid, username, attacks in users[:10]:
        uname = f"@{username}" if username != "нет" else "Без ника"
        top += f"{uid} ({uname}) — {attacks} атак\n"
    
    text = f"<b>Статистика</b>\n\n<blockquote>Пользователей: {len(users)}\nПромокодов: {len(promos)}\n\nТоп-10:\n{top}</blockquote>"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_event_money")
async def admin_event_money_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите сумму в рублях для раздачи всем пользователям:</b>", reply_markup=back_menu())
    await state.set_state(EventState.waiting_money_amount)
    await callback.answer()

@dp.message(EventState.waiting_money_amount)
async def event_money_process(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    cleaned = clean_number_input(message.text)
    if not cleaned:
        await message.answer("Введите положительное число:")
        return
    
    amount = int(cleaned)
    users = get_all_user_ids()
    count = 0
    
    status = await message.answer(f"Раздача... 0/{len(users)}")
    
    for i, uid in enumerate(users, 1):
        row = get_user(uid)
        if row:
            update_user_field(uid, "balance", row[11] + amount)
            try:
                await bot.send_message(uid, f"<b>Ивент!</b>\n\n<blockquote>Вам начислено {amount} руб. на баланс!</blockquote>")
            except:
                pass
            count += 1
        
        if i % 10 == 0:
            await status.edit_text(f"Раздача... {count}/{len(users)}")
        await asyncio.sleep(0.05)
        
    await status.edit_text(f"<b>Раздача завершена.</b>\n\n<blockquote>Начислено {amount} руб. {count} пользователям.</blockquote>", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_event_attacks")
async def admin_event_attacks_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите количество атак для раздачи всем пользователям:</b>", reply_markup=back_menu())
    await state.set_state(EventState.waiting_attacks_amount)
    await callback.answer()

@dp.message(EventState.waiting_attacks_amount)
async def event_attacks_process(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    cleaned = clean_number_input(message.text)
    if not cleaned:
        await message.answer("Введите положительное число:")
        return
    
    amount = int(cleaned)
    users = get_all_user_ids()
    count = 0
    
    status = await message.answer(f"Раздача... 0/{len(users)}")
    
    for i, uid in enumerate(users, 1):
        increment_attacks(uid, amount)
        try:
            await bot.send_message(uid, f"<b>Ивент!</b>\n\n<blockquote>Вам начислено {amount} атак!</blockquote>")
        except:
            pass
        count += 1
        
        if i % 10 == 0:
            await status.edit_text(f"Раздача... {count}/{len(users)}")
        await asyncio.sleep(0.05)
        
    await status.edit_text(f"<b>Раздача завершена.</b>\n\n<blockquote>Начислено {amount} атак {count} пользователям.</blockquote>", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите текст рассылки (или /cancel):</b>", reply_markup=back_menu())
    await state.set_state(BroadcastState.waiting_text)
    await callback.answer()

@dp.message(BroadcastState.waiting_text)
async def broadcast_text(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    if message.text == "/cancel":
        await message.answer("Отменено.", reply_markup=admin_menu())
        await state.clear()
        return
    text = message.text
    users = get_all_user_ids()
    sent = 0
    status = await message.answer(f"Рассылка... 0/{len(users)}")
    for i, uid in enumerate(users, 1):
        try:
            await bot.send_message(uid, text)
            sent += 1
        except: pass
        if i % 10 == 0: await status.edit_text(f"Рассылка... {sent}/{len(users)}")
        await asyncio.sleep(0.05)
    await status.edit_text(f"Готово. Отправлено {sent}/{len(users)}", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите код промокода (без пробелов):</b>", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_code)
    await callback.answer()

@dp.message(CreatePromoState.waiting_code)
async def create_promo_code(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    code = message.text.strip()
    if ' ' in code or not code:
        await message.answer("Код не должен содержать пробелов. Попробуйте ещё раз:")
        return
    await state.update_data(code=code)
    await message.answer("<b>Выберите тип промокода:</b>", reply_markup=promo_type_keyboard())
    await state.set_state(CreatePromoState.waiting_type)

@dp.callback_query(F.data == "promo_type_vip")
async def promo_type_vip(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.update_data(type="vip")
    await callback.message.edit_text("<b>Введите количество дней VIP:</b>", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_bonus)
    await callback.answer()

@dp.callback_query(F.data == "promo_type_attacks")
async def promo_type_attacks(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.update_data(type="attacks")
    await callback.message.edit_text("<b>Введите количество атак (бонус):</b>", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_bonus)
    await callback.answer()

@dp.message(CreatePromoState.waiting_bonus)
async def create_promo_bonus(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    text = message.text.strip()
    if text in ['/cancel', '/admin']:
        await message.answer("Отменено.", reply_markup=admin_menu())
        await state.clear()
        return
    cleaned = clean_number_input(text)
    if not cleaned:
        await message.answer("Введите положительное целое число:")
        return
    bonus = int(cleaned)
    if bonus <= 0:
        await message.answer("Введите положительное целое число:")
        return
    await state.update_data(bonus=bonus)
    await message.answer("<b>Введите количество использований (макс):</b>", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_uses)

@dp.message(CreatePromoState.waiting_uses)
async def create_promo_uses(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    text = message.text.strip()
    if text in ['/cancel', '/admin']:
        await message.answer("Отменено.", reply_markup=admin_menu())
        await state.clear()
        return
    cleaned = clean_number_input(text)
    if not cleaned:
        await message.answer("Введите положительное целое число:")
        return
    uses = int(cleaned)
    if uses <= 0:
        await message.answer("Введите положительное целое число:")
        return
    data = await state.get_data()
    code = data['code']
    promo_type = data['type']
    bonus = data['bonus']
    if promo_type == 'vip':
        create_promo(code, uses, bonus, 0, 'vip', message.from_user.id)
        bonus_str = f"{bonus} дней VIP"
    else:
        create_promo(code, uses, 0, bonus, 'attacks', message.from_user.id)
        bonus_str = f"{bonus} атак"
    await message.answer(f"<b>Промокод {code} создан.</b>\n\n<blockquote>Тип: {promo_type}\nИспользований: {uses}\nБонус: {bonus_str}</blockquote>", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_promo_list")
async def admin_promo_list_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    promos = get_promo_stats()
    if not promos:
        text = "Промокодов пока нет."
    else:
        lines = []
        for code, max_uses, used, typ, dur, atk in promos:
            bonus_str = f"{dur} дней VIP" if typ == 'vip' else f"{atk} атак"
            lines.append(f"{code} — {used}/{max_uses}, {bonus_str}")
        text = "<b>Промокоды</b>\n\n<blockquote>" + "\n".join(lines) + "</blockquote>"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_blacklist")
async def admin_blacklist_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    blacklist = get_blacklist()
    text = "<b>Черный список</b>\n\n<blockquote>" + ("\n".join([f"@{b}" for b in blacklist]) if blacklist else "Пуст") + "</blockquote>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить", callback_data="admin_add_blacklist"), InlineKeyboardButton(text="Удалить", callback_data="admin_remove_blacklist")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "admin_add_blacklist")
async def admin_add_blacklist_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите username цели (без @):</b>", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_add)
    await callback.answer()

@dp.callback_query(F.data == "admin_remove_blacklist")
async def admin_remove_blacklist_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите username для удаления (без @):</b>", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_remove)
    await callback.answer()

@dp.message(BlacklistState.waiting_add)
async def add_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    target = message.text.strip().lstrip('@')
    if not target:
        await message.answer("Неверный username.", reply_markup=back_menu())
        return
    if is_in_blacklist(target):
        await message.answer("Цель уже в черном списке.")
    else:
        if add_to_blacklist(target, message.from_user.id):
            await message.answer(f"<b>@{target} добавлен в черный список.</b>", reply_markup=admin_menu())
        else:
            await message.answer("Ошибка добавления.")
    await state.clear()

@dp.message(BlacklistState.waiting_remove)
async def remove_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    target = message.text.strip().lstrip('@')
    if not target:
        await message.answer("Неверный username.")
        return
    if remove_from_blacklist(target):
        await message.answer(f"<b>@{target} удален из черного списка.</b>", reply_markup=admin_menu())
    else:
        await message.answer("Цель не найдена.")
    await state.clear()

@dp.callback_query(F.data == "admin_settings")
async def admin_settings_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    ad_text = get_setting('ad_text') or "Не настроена"
    text = f"<b>Настройки</b>\n\n<blockquote>Реклама:\n{ad_text}</blockquote>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить рекламу", callback_data="admin_edit_ad")],
        [InlineKeyboardButton(text="Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_ad")
async def admin_edit_ad_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.edit_text("<b>Введите новый текст рекламы:</b>", reply_markup=back_menu())
    await state.set_state(AdState.waiting_text)
    await callback.answer()

@dp.message(AdState.waiting_text)
async def set_ad_text(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    if message.text == "/cancel":
        await message.answer("Отменено.", reply_markup=admin_menu())
        await state.clear()
        return
    set_setting('ad_text', message.text)
    await message.answer("<b>Рекламный текст обновлен.</b>", reply_markup=admin_menu())
    await state.clear()

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    init_db()
    print(f"{BOT_NAME} запущен.")
    print(f"Админы: {ADMIN_IDS}")
    if REQUIRED_CHANNEL:
        print(f"Подписка: {REQUIRED_CHANNEL}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
