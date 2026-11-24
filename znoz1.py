import os
import asyncio
import random
import sqlite3
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

BOT_NAME = "MAFIA SNOS"
BOT_TOKEN = "9293933717:AAGUSKkDzKDqre0TejgzU2hRvOVOEpkIChY"  # ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ НА НОВЫЙ!
ADMIN_ID = 8653940355
REQUIRED_CHANNEL = "@manyapollice"
PROTECTED_BOT = "Shakalbekbot"
DB_NAME = "shakal.db"

# ============================================================
#  ЛИМИТЫ (50 запросов для обычных)
# ============================================================
DAILY_LIMIT_NORMAL = 50
DAILY_LIMIT_VIP = float('inf')

VIOLATION_TYPES = {
    "doxxing": {"emoji": "📛", "label": "Доксинг (личные данные)"},
    "copyright": {"emoji": "©️", "label": "Нарушение авторских прав"},
    "spam": {"emoji": "📢", "label": "Спам/реклама"},
    "other": {"emoji": "⚠️", "label": "Другое"}
}

COLOR_MAP = {'blue': '🔵', 'green': '🟢', 'red': '🔴', 'yellow': '🟡', 'purple': '🟣'}
COLOR_NAMES = {'blue': 'Синий', 'green': 'Зелёный', 'red': 'Красный', 'yellow': 'Жёлтый', 'purple': 'Фиолетовый'}

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
        button_color TEXT DEFAULT 'blue'
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
    print("✅ База данных готова")

# ============================================================
#  ПОЛЬЗОВАТЕЛИ
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
    if not row:
        return False
    if row[5] != 1:
        return False
    vip_until = row[6]
    if vip_until is None:
        return True
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
    if days <= 0:
        return False
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
    c.execute("SELECT user_id, username, attacks FROM users ORDER BY attacks DESC")
    users = c.fetchall()
    conn.close()
    return users

# ============================================================
#  ЧЁРНЫЙ СПИСОК
# ============================================================
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

# ============================================================
#  ПРОМОКОДЫ
# ============================================================
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
        if set_vip(user_id, duration):
            return duration, "vip"
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
    if REQUIRED_CHANNEL.startswith("http"):
        return REQUIRED_CHANNEL
    if REQUIRED_CHANNEL.startswith("@"):
        return f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    return REQUIRED_CHANNEL

async def check_subscription(user_id):
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=channel_url())],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")]
    ])

async def ensure_subscribed(message_or_callback, user_id, callback=None):
    if not await check_subscription(user_id):
        text = f"🔴 Подпишитесь на канал {REQUIRED_CHANNEL}!"
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

# ============================================================
#  ОЧИСТКА СООБЩЕНИЙ
# ============================================================
async def cleanup_state_messages(chat_id, message_ids):
    for mid in message_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except:
            pass

# ============================================================
#  ИМИТАЦИЯ АТАКИ
# ============================================================
async def attack_bot(target_username, count, violation_type, link):
    await asyncio.sleep(random.uniform(2, 4))
    successful = int(count * random.uniform(0.7, 0.95))
    return successful, count

# ============================================================
#  КЛАВИАТУРЫ
# ============================================================
def main_menu(user_id):
    color = get_button_color(user_id)
    emoji = COLOR_MAP.get(color, '🔵')
    
    buttons = [
        [InlineKeyboardButton(text="🚀 Начать", callback_data="attack")],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
            InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/snospve")
        ],
        [
            InlineKeyboardButton(text="🛒 Магазин", callback_data="shop"),
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating_attacks")
        ],
        [
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")
        ]
    ]
    
    if is_vip(user_id):
        buttons[3].append(InlineKeyboardButton(text=f"{emoji} Цвет", callback_data="change_color"))
        
    if REQUIRED_CHANNEL:
        buttons.append([InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_sub")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Промокоды", callback_data="admin_promo_list")],
        [InlineKeyboardButton(text="🛑 Чёрный список", callback_data="admin_blacklist")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

def color_choose_keyboard():
    kb = []
    for key, emoji in COLOR_MAP.items():
        kb.append([InlineKeyboardButton(text=f"{emoji} {COLOR_NAMES[key]}", callback_data=f"color_{key}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def promo_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VIP", callback_data="promo_type_vip")],
        [InlineKeyboardButton(text="Атаки", callback_data="promo_type_attacks")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back")]
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
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="count_manual")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ============================================================
#  БОТ
# ============================================================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================================================
#  ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК КНОПОК
# ============================================================
@dp.errors()
async def errors_handler(event: aiogram_types.ErrorEvent):
    exception = event.exception
    if isinstance(exception, TelegramBadRequest) and "message is not modified" in str(exception):
        return True
    print(f"Ошибка в обработчике: {exception}")
    return True

# ============================================================
#  СТАРТ
# ============================================================
@dp.message(CommandStart())
async def start_command(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    try:
        await message.delete()
    except:
        pass
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    if not await check_subscription(user_id):
        await message.answer(
            f"🔴 Для использования {BOT_NAME} подпишитесь на канал {REQUIRED_CHANNEL}!",
            reply_markup=sub_keyboard()
        )
        return

    text = (
        f"Убираем нарушения и защищаем аккаунты в Telegram, TikTok и на сайтах.\n\n"
        f"⚠️ Обычные пользователи: {DAILY_LIMIT_NORMAL} запросов в день.\n"
        f"💎 VIP: безлимит."
    )
    
    await message.answer(text, reply_markup=main_menu(user_id))

# Обработчик для старых кнопок "Начать" из истории
@dp.message(F.text == "🚀 Начать")
async def old_start_button(message: aiogram_types.Message):
    try:
        await message.delete()
    except:
        pass
    await message.answer("🎯 Введите username цели (без @):", reply_markup=back_menu())

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.edit_text("✅ Подписка подтверждена!", reply_markup=main_menu(user_id))
    else:
        await callback.message.edit_text(
            f"❌ Вы не подписаны на {REQUIRED_CHANNEL}.\nПодпишитесь и нажмите снова.",
            reply_markup=sub_keyboard()
        )
    await callback.answer()

# ============================================================
#  МАГАЗИН
# ============================================================
@dp.callback_query(F.data == "shop")
async def shop_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    
    text = (
        "🛒 <b>Магазин VIP-подписок</b>\n\n"
        "📅 <b>Неделя</b> — 70 руб.\n"
        "📅 <b>Месяц</b> — 100 руб.\n"
        "💎 <b>Навсегда</b> — 150 руб.\n\n"
        "Для покупки напишите нашему менеджеру: @snospve"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @snospve", url="https://t.me/snospve")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================================
#  АТАКА
# ============================================================
@dp.callback_query(F.data == "attack")
async def attack_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await callback.answer(f"❌ Дневной лимит ({limit}) исчерпан. Купите VIP для безлимита.", show_alert=True)
        return
    await state.update_data(step_messages=[])
    msg = await callback.message.edit_text("🎯 Введите username цели (без @):", reply_markup=back_menu())
    await state.update_data(step_messages=[msg.message_id])
    await state.set_state(AttackState.waiting_username)
    await callback.answer()

@dp.message(AttackState.waiting_username)
async def attack_username(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_subscribed(message, user_id):
        await state.clear()
        return
    target = message.text.strip().lstrip('@')
    try:
        await message.delete()
    except:
        pass
    if not target:
        await message.answer("❌ Неверный username", reply_markup=main_menu(user_id))
        await state.clear()
        return
    if is_in_blacklist(target):
        await message.answer(f"⛔ Цель @{target} в чёрном списке.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    if target.lower() == PROTECTED_BOT.lower():
        await message.answer(f"⛔ {PROTECTED_BOT} под защитой.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    data = await state.get_data()
    step_msgs = data.get("step_messages", [])
    msg = await message.answer("Сколько жалоб отправить? (1–300):", reply_markup=count_keyboard())
    step_msgs.append(msg.message_id)
    await state.update_data(target=target, step_messages=step_msgs)
    await state.set_state(AttackState.waiting_count)

@dp.callback_query(F.data.startswith("count_"), AttackState.waiting_count)
async def attack_count_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    data = callback.data
    if data == "count_manual":
        await callback.message.edit_text("Введите число от 1 до 300:", reply_markup=back_menu())
        return
    try:
        count = int(data.split("_")[1])
    except:
        await callback.answer("Ошибка", show_alert=True)
        return
    if count < 1 or count > 300:
        await callback.answer("Число должно быть от 1 до 300", show_alert=True)
        return
    await state.update_data(count=count)
    await show_violation_menu(callback.message, state)
    await callback.answer()

@dp.message(AttackState.waiting_count)
async def attack_count_manual(message: aiogram_types.Message, state: FSMContext):
    cleaned = clean_number_input(message.text)
    try:
        await message.delete()
    except:
        pass
    if not cleaned:
        await message.answer("❌ Введите число от 1 до 300:")
        return
    count = int(cleaned)
    if count < 1 or count > 300:
        await message.answer("❌ Число должно быть от 1 до 300:")
        return
    await state.update_data(count=count)
    await show_violation_menu(message, state)

async def show_violation_menu(message, state: FSMContext):
    data = await state.get_data()
    step_msgs = data.get("step_messages", [])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{v['emoji']} {v['label']}", callback_data=f"violation_{k}")]
        for k, v in VIOLATION_TYPES.items()
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back")]])
    msg = await message.answer("Выберите тип нарушения:", reply_markup=kb)
    step_msgs.append(msg.message_id)
    await state.update_data(step_messages=step_msgs)
    await state.set_state(AttackState.waiting_violation)

@dp.callback_query(F.data.startswith("violation_"), AttackState.waiting_violation)
async def attack_violation(callback: aiogram_types.CallbackQuery, state: FSMContext):
    violation_type = callback.data.split("_")[1]
    await state.update_data(violation=violation_type)
    data = await state.get_data()
    step_msgs = data.get("step_messages", [])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Вставить ссылку", callback_data="link_enter")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="link_skip")]
    ])
    msg = await callback.message.edit_text("Введите ссылку на нарушение (или пропустите):", reply_markup=kb)
    step_msgs.append(msg.message_id)
    await state.update_data(step_messages=step_msgs)
    await state.set_state(AttackState.waiting_link)
    await callback.answer()

@dp.callback_query(F.data == "link_enter", AttackState.waiting_link)
async def attack_link_enter(callback: aiogram_types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите ссылку:", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "link_skip", AttackState.waiting_link)
async def attack_link_skip(callback: aiogram_types.CallbackQuery, state: FSMContext):
    await state.update_data(link="без ссылки")
    await finish_attack(callback.message, state, callback.from_user.id, callback)

@dp.message(AttackState.waiting_link)
async def attack_link_input(message: aiogram_types.Message, state: FSMContext):
    link = message.text.strip()
    try:
        await message.delete()
    except:
        pass
    await state.update_data(link=link or "без ссылки")
    await finish_attack(message, state, message.from_user.id)

async def finish_attack(message_or_callback, state: FSMContext, user_id, callback=None):
    data = await state.get_data()
    target = data.get("target")
    violation = data.get("violation")
    link = data.get("link", "без ссылки")
    count = data.get("count", 1)
    step_msgs = data.get("step_messages", [])

    # Имитация процесса с показом прогресса
    progress_text = "⏳ <b>Отправка жалоб...</b>\n\n"
    if callback:
        msg = await callback.message.edit_text(progress_text + "░" * 10 + " 0%")
        chat_id = callback.message.chat.id
    else:
        msg = await message_or_callback.answer(progress_text + "░" * 10 + " 0%")
        chat_id = message_or_callback.chat.id

    # Анимация прогресс-бара
    for i in range(1, 11):
        await asyncio.sleep(random.uniform(0.1, 0.3))
        bar = "█" * i + "░" * (10 - i)
        percent = i * 10
        try:
            await msg.edit_text(progress_text + f"{bar} {percent}%")
        except:
            pass

    # Сама имитация атаки
    successful, total = await attack_bot(target, count, violation, link)
    increment_attacks(user_id, count)
    add_target_stat(user_id, target, count)

    # Подсчет процента успеха
    success_rate = int((successful / total) * 100) if total > 0 else 0
    
    # Статусы в зависимости от успеха
    if success_rate >= 90:
        status_emoji = "🔥"
        status_text = "Максимальная эффективность!"
    elif success_rate >= 70:
        status_emoji = "✅"
        status_text = "Хороший результат."
    elif success_rate >= 50:
        status_emoji = "⚠️"
        status_text = "Средний результат."
    else:
        status_emoji = "❌"
        status_text = "Низкий результат, попробуйте еще раз."

    violation_label = VIOLATION_TYPES.get(violation, {}).get("label", "Неизвестно")

    # Итоговый красивый текст
    result = (
        f"{status_emoji} <b>Жалобы успешно отправлены!</b>\n\n"
        f"🎯 <b>Цель:</b> @{target}\n"
        f"📋 <b>Нарушение:</b> {violation_label}\n"
        f"🔗 <b>Ссылка:</b> {link}\n\n"
        f"📊 <b>Статистика отправки:</b>\n"
        f"├ Всего попыток: <b>{total}</b>\n"
        f"├ Успешно доставлено: <b>{successful}</b>\n"
        f"└ Эффективность: <b>{success_rate}%</b>\n\n"
        f"💬 <i>{status_text}</i>"
    )

    # Меняем сообщение с прогресс-баром на итоговый результат
    try:
        await msg.edit_text(result, reply_markup=main_menu(user_id))
    except:
        if callback:
            await callback.message.edit_text(result, reply_markup=main_menu(user_id))
        else:
            await message_or_callback.answer(result, reply_markup=main_menu(user_id))

    if callback:
        await callback.answer()

    # Очищаем промежуточные сообщения
    await cleanup_state_messages(chat_id, step_msgs)
    await state.clear()

# ============================================================
#  ПРОФИЛЬ
# ============================================================
@dp.callback_query(F.data == "profile")
async def profile_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    row = get_user(user_id)
    if not row:
        add_user(user_id, callback.from_user.username, callback.from_user.first_name)
        row = get_user(user_id)
    attacks = row[3]
    vip_status = "✅" if is_vip(user_id) else "❌"
    vip_until = row[6]
    if is_vip(user_id):
        if vip_until is None:
            vip_status = "✅ (навсегда)"
        else:
            try:
                dt = datetime.fromisoformat(vip_until)
                vip_status = f"✅ до {dt.strftime('%d.%m.%Y')}"
            except:
                vip_status = "✅"
    daily = get_daily_attacks(user_id)
    limit = get_daily_limit(user_id)
    limit_display = "∞" if limit == float('inf') else str(limit)
    color = get_button_color(user_id)
    text = (
        f"👤 Профиль\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"❄️ Атак: {attacks}\n"
        f"📆 Сегодня: {daily}/{limit_display}\n"
        f"💎 VIP: {vip_status}\n"
        f"🎨 Цвет: {COLOR_MAP.get(color, '🔵')} {COLOR_NAMES.get(color, color)}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ============================================================
#  ПРОМОКОД (ввод)
# ============================================================
@dp.callback_query(F.data == "enter_promo")
async def enter_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    msg = await callback.message.edit_text("Введите промокод:", reply_markup=back_menu())
    await state.update_data(promo_msg=msg.message_id)
    await state.set_state(PromoState.waiting_code)
    await callback.answer()

@dp.message(PromoState.waiting_code)
async def promo_code_handler(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_subscribed(message, user_id):
        await state.clear()
        return
    code = message.text.strip()
    try:
        await message.delete()
    except:
        pass
    data = await state.get_data()
    promo_msg = data.get("promo_msg")
    if promo_msg:
        try:
            await bot.delete_message(message.chat.id, promo_msg)
        except:
            pass
    result, typ = use_promo(user_id, code)
    if result is None:
        if typ == "invalid":
            await message.answer("❌ Промокод не найден.", reply_markup=main_menu(user_id))
        elif typ == "used":
            await message.answer("❌ Промокод уже закончился (лимит использований).", reply_markup=main_menu(user_id))
        elif typ == "already":
            await message.answer("❌ Вы уже использовали этот промокод.", reply_markup=main_menu(user_id))
        elif typ == "bad_type":
            await message.answer("❌ Ошибка в настройках промокода (неверный бонус). Обратитесь к админу.", reply_markup=main_menu(user_id))
        else:
            await message.answer("❌ Не удалось активировать промокод.", reply_markup=main_menu(user_id))
    else:
        if typ == "vip":
            row = get_user(user_id)
            vip_until = row[6] if row else None
            if vip_until is None:
                until_str = "навсегда"
            else:
                try:
                    until_str = datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')
                except:
                    until_str = "?"
            await message.answer(f"✅ VIP активирован на {result} дней (до {until_str})!", reply_markup=main_menu(user_id))
        elif typ == "attacks":
            await message.answer(f"✅ Вам начислено {result} атак!", reply_markup=main_menu(user_id))
    await state.clear()

@dp.message(F.text, ~F.text.startswith('/'))
async def handle_text(message: aiogram_types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await message.answer(f"❌ Подпишитесь на {REQUIRED_CHANNEL}.", reply_markup=sub_keyboard())
        return
    code = message.text.strip()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM promo_codes WHERE code = ?", (code.lower(),))
    if c.fetchone():
        conn.close()
        result, typ = use_promo(user_id, code)
        try:
            await message.delete()
        except:
            pass
        if result is None:
            if typ == "invalid":
                await message.answer("❌ Промокод не найден.", reply_markup=main_menu(user_id))
            elif typ == "used":
                await message.answer("❌ Промокод уже закончился.", reply_markup=main_menu(user_id))
            elif typ == "already":
                await message.answer("❌ Вы уже использовали этот промокод.", reply_markup=main_menu(user_id))
            elif typ == "bad_type":
                await message.answer("❌ Ошибка в настройках промокода.", reply_markup=main_menu(user_id))
        else:
            if typ == "vip":
                row = get_user(user_id)
                vip_until = row[6] if row else None
                if vip_until is None:
                    until_str = "навсегда"
                else:
                    try:
                        until_str = datetime.fromisoformat(vip_until).strftime('%d.%m.%Y')
                    except:
                        until_str = "?"
                await message.answer(f"✅ VIP активирован на {result} дней (до {until_str})!", reply_markup=main_menu(user_id))
            elif typ == "attacks":
                await message.answer(f"✅ Вам начислено {result} атак!", reply_markup=main_menu(user_id))
    else:
        conn.close()

# ============================================================
#  РЕЙТИНГ
# ============================================================
@dp.callback_query(F.data == "rating_attacks")
async def rating_attacks_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    users = get_all_users()
    if not users:
        await callback.message.edit_text("🏆 Рейтинг пуст.", reply_markup=back_menu())
        return
    top = ""
    for i, (uid, username, attacks) in enumerate(users[:10], 1):
        uname = f"@{username}" if username and username != "нет" else f"ID{uid}"
        top += f"{i}. {uname} — {attacks} атак\n"
    await callback.message.edit_text(f"🏆 РЕЙТИНГ ПО АТАКАМ:\n\n{top}", reply_markup=back_menu())
    await callback.answer()

# ============================================================
#  СТАТИСТИКА
# ============================================================
@dp.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    targets = get_user_targets(user_id)
    if not targets:
        await callback.message.edit_text("Вы ещё никого не атаковали.", reply_markup=back_menu())
        return
    lines = []
    total = 0
    for target, count in targets:
        lines.append(f"@{target} — {count} раз")
        total += count
    await callback.message.edit_text(f"📊 Статистика:\n" + "\n".join(lines) + f"\n\nВсего атак: {total}", reply_markup=back_menu())
    await callback.answer()

# ============================================================
#  ЦВЕТ КНОПОК
# ============================================================
@dp.callback_query(F.data == "change_color")
async def change_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    if not is_vip(user_id):
        await callback.answer("Только для VIP!", show_alert=True)
        return
    await callback.message.edit_text("🎨 Выберите цвет:", reply_markup=color_choose_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("color_"))
async def set_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_subscribed(callback.message, user_id, callback):
        return
    if not is_vip(user_id):
        await callback.answer("Только для VIP!", show_alert=True)
        return
    color = callback.data.split("_")[1]
    if color not in COLOR_MAP:
        await callback.answer("Неверный цвет", show_alert=True)
        return
    set_button_color(user_id, color)
    await callback.message.edit_text(
        f"✅ Цвет кнопок изменён на {COLOR_MAP[color]} {COLOR_NAMES[color]}.",
        reply_markup=main_menu(user_id)
    )
    await callback.answer()

# ============================================================
#  НАЗАД
# ============================================================
@dp.callback_query(F.data == "back")
async def back_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    step_msgs = data.get("step_messages", [])
    await state.clear()
    await cleanup_state_messages(callback.message.chat.id, step_msgs)
    if not await check_subscription(user_id):
        await callback.message.edit_text(
            f"❌ Вы не подписаны на {REQUIRED_CHANNEL}",
            reply_markup=sub_keyboard()
        )
        await callback.answer()
        return
    await callback.message.edit_text(f"❄️ Главное меню {BOT_NAME}", reply_markup=main_menu(user_id))
    await callback.answer()

# ============================================================
#  АДМИН-ПАНЕЛЬ
# ============================================================
@dp.message(Command("admin"))
async def admin_command(message: aiogram_types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа")
        return
    try:
        await message.delete()
    except:
        pass
    await message.answer("👑 АДМИН ПАНЕЛЬ", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    users = get_all_users()
    promos = get_promo_stats()
    top = ""
    for uid, username, attacks in users[:10]:
        uname = f"@{username}" if username != "нет" else "БЕЗ ЮЗЕРНЕЙМА"
        top += f"• <code>{uid}</code> ({uname}) — {attacks} атак\n"
    text = f"📊 СТАТИСТИКА\n\n👥 Пользователей: {len(users)}\n🎫 Промокодов: {len(promos)}\n\n🏆 ТОП-10:\n{top}"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("📢 Введите текст рассылки (или /cancel):", reply_markup=back_menu())
    await state.set_state(BroadcastState.waiting_text)
    await callback.answer()

@dp.message(BroadcastState.waiting_text)
async def broadcast_text(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if message.text == "/cancel":
        try:
            await message.delete()
        except:
            pass
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    text = message.text
    try:
        await message.delete()
    except:
        pass
    users = get_all_user_ids()
    sent = 0
    status = await message.answer(f"📢 Рассылка... 0/{len(users)}")
    for i, uid in enumerate(users, 1):
        try:
            await bot.send_message(uid, text)
            sent += 1
        except:
            pass
        if i % 10 == 0:
            await status.edit_text(f"📢 Рассылка... {sent}/{len(users)}")
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ Готово! Отправлено {sent}/{len(users)}", reply_markup=admin_menu())
    await state.clear()

# ---------- СОЗДАНИЕ ПРОМОКОДА ----------
@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    msg = await callback.message.edit_text("Введите код промокода (без пробелов):", reply_markup=back_menu())
    await state.update_data(admin_msgs=[msg.message_id])
    await state.set_state(CreatePromoState.waiting_code)
    await callback.answer()

@dp.message(CreatePromoState.waiting_code)
async def create_promo_code(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    try:
        await message.delete()
    except:
        pass
    if ' ' in code or not code:
        await message.answer("❌ Код не должен содержать пробелов. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    admin_msgs = data.get("admin_msgs", [])
    await state.update_data(code=code, admin_msgs=admin_msgs)
    msg = await message.answer("Выберите тип промокода:", reply_markup=promo_type_keyboard())
    admin_msgs.append(msg.message_id)
    await state.update_data(admin_msgs=admin_msgs)
    await state.set_state(CreatePromoState.waiting_type)

@dp.callback_query(F.data == "promo_type_vip")
async def promo_type_vip(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.update_data(type="vip")
    await callback.message.edit_text("Введите количество дней VIP (например, 30):", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_bonus)
    await callback.answer()

@dp.callback_query(F.data == "promo_type_attacks")
async def promo_type_attacks(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.update_data(type="attacks")
    await callback.message.edit_text("Введите количество атак (бонус):", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_bonus)
    await callback.answer()

@dp.message(CreatePromoState.waiting_bonus)
async def create_promo_bonus(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    try:
        await message.delete()
    except:
        pass
    if text in ['/cancel', '/admin']:
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    cleaned = clean_number_input(text)
    if not cleaned:
        await message.answer("❌ Введите положительное целое число (только цифры):")
        return
    bonus = int(cleaned)
    if bonus <= 0:
        await message.answer("❌ Введите положительное целое число (только цифры):")
        return
    data = await state.get_data()
    if data.get("type") == "vip" and bonus <= 0:
        await message.answer("❌ Для VIP количество дней должно быть > 0:")
        return
    await state.update_data(bonus=bonus)
    await message.answer("Введите количество использований (макс):", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_uses)

@dp.message(CreatePromoState.waiting_uses)
async def create_promo_uses(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    try:
        await message.delete()
    except:
        pass
    if text in ['/cancel', '/admin']:
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    cleaned = clean_number_input(text)
    if not cleaned:
        await message.answer("❌ Введите положительное целое число (только цифры):")
        return
    uses = int(cleaned)
    if uses <= 0:
        await message.answer("❌ Введите положительное целое число (только цифры):")
        return
    data = await state.get_data()
    code = data['code']
    promo_type = data['type']
    bonus = data['bonus']
    if promo_type == 'vip':
        if bonus <= 0:
            await message.answer("❌ Для VIP количество дней должно быть > 0.", reply_markup=admin_menu())
            await state.clear()
            return
        create_promo(code, uses, bonus, 0, 'vip', ADMIN_ID)
        bonus_str = f"{bonus} дней VIP"
    else:
        if bonus <= 0:
            await message.answer("❌ Для атак количество должно быть > 0.", reply_markup=admin_menu())
            await state.clear()
            return
        create_promo(code, uses, 0, bonus, 'attacks', ADMIN_ID)
        bonus_str = f"{bonus} атак"
    await message.answer(f"✅ Промокод <b>{code}</b> создан!\nТип: {promo_type}\nИспользований: {uses}\nБонус: {bonus_str}", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_promo_list")
async def admin_promo_list_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    promos = get_promo_stats()
    if not promos:
        text = "📋 Промокодов пока нет."
    else:
        lines = []
        for code, max_uses, used, typ, dur, atk in promos:
            bonus_str = f"{dur} дней VIP" if typ == 'vip' else f"{atk} атак"
            lines.append(f"• {code} — {used}/{max_uses}, {bonus_str}")
        text = "📋 ПРОМОКОДЫ:\n" + "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

# ---------- ЧЁРНЫЙ СПИСОК ----------
@dp.callback_query(F.data == "admin_blacklist")
async def admin_blacklist_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    blacklist = get_blacklist()
    text = "📋 ЧЁРНЫЙ СПИСОК:\n" + "\n".join([f"• @{b}" for b in blacklist]) if blacklist else "📋 Чёрный список пуст."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="admin_add_blacklist")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="admin_remove_blacklist")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "admin_add_blacklist")
async def admin_add_blacklist_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите username цели (без @):", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_add)
    await callback.answer()

@dp.callback_query(F.data == "admin_remove_blacklist")
async def admin_remove_blacklist_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите username для удаления (без @):", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_remove)
    await callback.answer()

@dp.message(BlacklistState.waiting_add)
async def add_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target = message.text.strip().lstrip('@')
    try:
        await message.delete()
    except:
        pass
    if not target:
        await message.answer("❌ Неверный username", reply_markup=back_menu())
        return
    if is_in_blacklist(target):
        await message.answer("❌ Цель уже в чёрном списке.")
    else:
        if add_to_blacklist(target, ADMIN_ID):
            await message.answer(f"✅ @{target} добавлен в чёрный список.", reply_markup=admin_menu())
        else:
            await message.answer("❌ Ошибка добавления.")
    await state.clear()

@dp.message(BlacklistState.waiting_remove)
async def remove_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target = message.text.strip().lstrip('@')
    try:
        await message.delete()
    except:
        pass
    if not target:
        await message.answer("❌ Неверный username")
        return
    if remove_from_blacklist(target):
        await message.answer(f"✅ @{target} удалён из чёрного списка.", reply_markup=admin_menu())
    else:
        await message.answer("❌ Цель не найдена.")
    await state.clear()

# ---------- НАСТРОЙКИ ----------
@dp.callback_query(F.data == "admin_settings")
async def admin_settings_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    ad_text = get_setting('ad_text') or "Не настроена"
    text = f"⚙️ НАСТРОЙКИ\n\nРекламный текст:\n{ad_text}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить рекламу", callback_data="admin_edit_ad")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_ad")
async def admin_edit_ad_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите новый текст рекламы:", reply_markup=back_menu())
    await state.set_state(AdState.waiting_text)
    await callback.answer()

@dp.message(AdState.waiting_text)
async def set_ad_text(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if message.text == "/cancel":
        try:
            await message.delete()
        except:
            pass
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    set_setting('ad_text', message.text)
    try:
        await message.delete()
    except:
        pass
    await message.answer("✅ Рекламный текст обновлён!", reply_markup=admin_menu())
    await state.clear()

# ============================================================
#  ФОНОВАЯ ПРОВЕРКА VIP
# ============================================================
async def check_vip_expiry():
    while True:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            now = datetime.now()
            c.execute("SELECT user_id, vip_until FROM users WHERE is_vip=1 AND vip_until IS NOT NULL")
            rows = c.fetchall()
            for user_id, vip_until in rows:
                if vip_until:
                    expiry_date = datetime.fromisoformat(vip_until)
                    if now.date() + timedelta(days=1) == expiry_date.date():
                        await bot.send_message(user_id, "⚠️ Ваш VIP истекает завтра!")
            conn.close()
        except Exception as e:
            print(f"VIP expiry error: {e}")
        await asyncio.sleep(86400)

# ============================================================
#  ЗАПУСК
# ============================================================
async def main():
    init_db()
    asyncio.create_task(check_vip_expiry())
    print(f"🔰 {BOT_NAME} запущен")
    print(f"👑 Админ: {ADMIN_ID}")
    if REQUIRED_CHANNEL:
        print(f"📢 Подписка: {REQUIRED_CHANNEL}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
