import os
import asyncio
import random
import sqlite3
import string
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types as aiogram_types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = "8610518935:AAHUdNEZ7c32dewRKf_bJ5_UQXBEwfvGa28"
ADMIN_ID = 8457792268
REQUIRED_CHANNEL = ""  # если нужна подписка, укажите @канал
PROTECTED_BOT = "Shakalbekbot"
DB_NAME = "shakal.db"
VIP_CONTACT = "@sendholders"
VIP_PRICE = "200 ₽"

REFERRAL_TARGETS = [1, 3, 5, 10, 20]
REFERRAL_BONUSES = [50, 100, 200, 500, 1000]
PROMO_TARGETS = [1, 3, 5, 10, 20]
PROMO_BONUSES = [50, 100, 200, 500, 1000]
VIP_DAYS_FOR_GOAL = 7

# ---------- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОЧИСТКИ ЧИСЕЛ ----------
def clean_number_input(text: str) -> str:
    text = text.strip()
    if text.startswith('/'):
        text = text[1:]
    return ''.join(filter(str.isdigit, text))

# ---------- БАЗА ДАННЫХ ----------
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
        bonus_date TEXT,
        referrer_id INTEGER,
        referral_code TEXT,
        referrals_count INTEGER DEFAULT 0,
        referral_attacks_bonus INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ru',
        is_vip_lifetime INTEGER DEFAULT 0,
        button_color TEXT DEFAULT 'blue',
        promo_activations INTEGER DEFAULT 0
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
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('broadcast_enabled', '1')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_weekly_broadcast', '1970-01-01 00:00:00')")
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
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        referrer_id INTEGER,
        referred_id INTEGER PRIMARY KEY,
        joined_at TEXT
    )''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# ---------- ОСНОВНЫЕ ФУНКЦИИ РАБОТЫ С БД ----------
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

def add_user(user_id, username, first_name, referrer_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    ref_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    c.execute('''INSERT INTO users (
        user_id, username, first_name, joined_date, referral_code, referrer_id, language, button_color, promo_activations
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, username or "нет", first_name or "нет",
         datetime.now().isoformat(), ref_code, referrer_id, 'ru', 'blue', 0))
    if referrer_id:
        c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
        c.execute("INSERT INTO referrals (referrer_id, referred_id, joined_at) VALUES (?, ?, ?)",
                  (referrer_id, user_id, datetime.now().isoformat()))
        c.execute("UPDATE users SET attacks = attacks + 20 WHERE user_id = ?", (referrer_id,))
        c.execute("UPDATE users SET referral_attacks_bonus = referral_attacks_bonus + 20 WHERE user_id = ?", (referrer_id,))
        c.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
        refs = c.fetchone()[0]
        for i, target in enumerate(REFERRAL_TARGETS):
            if refs == target:
                bonus = REFERRAL_BONUSES[i]
                c.execute("UPDATE users SET attacks = attacks + ? WHERE user_id = ?", (bonus, referrer_id))
                c.execute("UPDATE users SET referral_attacks_bonus = referral_attacks_bonus + ? WHERE user_id = ?", (bonus, referrer_id))
        if refs == 10:
            vip_until = (datetime.now() + timedelta(days=VIP_DAYS_FOR_GOAL)).isoformat()
            c.execute("UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?", (vip_until, referrer_id))
    conn.commit()
    conn.close()

def increment_attacks(user_id, count=1):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("SELECT last_attack_date, daily_attacks FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        last_date = row[8]
        daily = row[7] if row[7] else 0
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
    if not row or row[8] != today:
        return 0
    return row[7] if row[7] else 0

def set_vip(user_id, days):
    if days == -1:
        update_user_field(user_id, "is_vip", 1)
        update_user_field(user_id, "is_vip_lifetime", 1)
        update_user_field(user_id, "vip_until", None)
    else:
        until = (datetime.now() + timedelta(days=days)).isoformat()
        update_user_field(user_id, "is_vip", 1)
        update_user_field(user_id, "vip_until", until)
        update_user_field(user_id, "is_vip_lifetime", 0)

def is_vip(user_id):
    row = get_user(user_id)
    if not row: return False
    if row[5] == 1:
        if row[6] is None:
            return row[15] == 1
        if datetime.now().isoformat() > row[6]:
            update_user_field(user_id, "is_vip", 0)
            update_user_field(user_id, "vip_until", None)
            return False
        return True
    return False

def get_daily_limit(user_id):
    return float('inf') if is_vip(user_id) else 100

def is_bonus_available(user_id):
    row = get_user(user_id)
    if not row: return True
    bonus_date = row[9]
    today = datetime.now().date().isoformat()
    return bonus_date != today

def claim_bonus(user_id):
    today = datetime.now().date().isoformat()
    update_user_field(user_id, "bonus_date", today)

def get_referral_code(user_id):
    row = get_user(user_id)
    return row[11] if row else None

def get_referral_stats(user_id):
    row = get_user(user_id)
    if row:
        return row[12], row[13]
    return 0, 0

def get_promo_activations(user_id):
    row = get_user(user_id)
    return row[17] if row else 0

def get_button_color(user_id):
    row = get_user(user_id)
    return row[16] if row and row[16] else 'blue'

def set_button_color(user_id, color):
    update_user_field(user_id, "button_color", color)

def get_user_language(user_id):
    row = get_user(user_id)
    return row[14] if row else 'ru'

def set_user_language(user_id, lang):
    update_user_field(user_id, "language", lang)

def add_target_stat(user_id, target):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO targets (user_id, target_username, count) VALUES (?, ?, COALESCE((SELECT count FROM targets WHERE user_id=? AND target_username=?), 0)+1)",
              (user_id, target, user_id, target))
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

# ---------- ПРОМОКОДЫ ----------
def create_promo(code, max_uses, duration_days, attacks_bonus, promo_type, admin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO promo_codes (code, max_uses, used_count, duration_days, attacks_bonus, type, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (code.lower(), max_uses, 0, duration_days, attacks_bonus, promo_type, admin_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def use_promo(user_id, code):
    code = code.lower()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT max_uses, used_count, duration_days, attacks_bonus, type FROM promo_codes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, "invalid"
    max_uses, used_count, duration, attacks_bonus, promo_type = row
    if used_count >= max_uses:
        conn.close()
        return None, "used"
    c.execute("SELECT * FROM used_promos WHERE user_id = ? AND code = ?", (user_id, code))
    if c.fetchone():
        conn.close()
        return None, "already"
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    c.execute("INSERT INTO used_promos (user_id, code, used_at) VALUES (?, ?, ?)", (user_id, code, datetime.now().isoformat()))
    c.execute("UPDATE users SET promo_activations = promo_activations + 1 WHERE user_id = ?", (user_id,))
    c.execute("SELECT promo_activations FROM users WHERE user_id = ?", (user_id,))
    activations = c.fetchone()[0]
    for i, target in enumerate(PROMO_TARGETS):
        if activations == target:
            bonus = PROMO_BONUSES[i]
            c.execute("UPDATE users SET attacks = attacks + ? WHERE user_id = ?", (bonus, user_id))
    if activations == 10:
        vip_until = (datetime.now() + timedelta(days=VIP_DAYS_FOR_GOAL)).isoformat()
        c.execute("UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?", (vip_until, user_id))
    conn.commit()
    conn.close()
    if promo_type == "vip":
        set_vip(user_id, duration)
        return duration, "vip"
    else:
        increment_attacks(user_id, attacks_bonus)
        return attacks_bonus, "attacks"

def get_promo_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code, max_uses, used_count, type, duration_days, attacks_bonus FROM promo_codes ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- ДРУГИЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
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
    c.execute("SELECT * FROM blacklist WHERE target_username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_next_target(current, targets):
    for t in targets:
        if current < t:
            return t
    return None

def get_bonus_for_target(target, targets, bonuses):
    for i, t in enumerate(targets):
        if t == target:
            return bonuses[i]
    return None

# ---------- FSM СОСТОЯНИЯ ----------
class AttackState(StatesGroup):
    waiting_username = State()

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

# ---------- ПРОВЕРКА ПОДПИСКИ ----------
async def check_subscription(user_id):
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def ensure_subscribed(message_or_callback, user_id, lang, callback=None):
    if not await check_subscription(user_id):
        text = f"🔴 Для использования бота подпишитесь на канал {REQUIRED_CHANNEL}!"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
        ])
        if callback:
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        else:
            await message_or_callback.answer(text, reply_markup=keyboard)
        return False
    return True

# ---------- КЛАВИАТУРЫ ----------
def main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="❄️ Атака", callback_data="attack")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🎁 Бонус +50", callback_data="claim_bonus")],
        [InlineKeyboardButton(text="💎 Премиум", callback_data="premium_info")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="ref_system")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="📢 Реклама", callback_data="advertisement")],
    ]
    if is_vip(user_id):
        buttons.append([InlineKeyboardButton(text="🎨 Цвет кнопок", callback_data="change_color")])
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
    colors = ['🔵 Синий', '🟢 Зелёный', '🔴 Красный', '🟡 Жёлтый', '🟣 Фиолетовый']
    kb = []
    for color in colors:
        kb.append([InlineKeyboardButton(text=color, callback_data=f"color_{color.split()[1]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def promo_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="VIP", callback_data="promo_type_vip")],
        [InlineKeyboardButton(text="Атаки", callback_data="promo_type_attacks")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back")]
    ])

# ---------- БОТ ----------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---------- ОБРАБОТЧИКИ ----------
@dp.message(CommandStart())
async def start_command(message: aiogram_types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    referrer_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        ref_code = args[1][4:]
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE referral_code = ?", (ref_code,))
        row = c.fetchone()
        conn.close()
        if row and row[0] != user_id:
            referrer_id = row[0]
    add_user(user_id, username, first_name, referrer_id)
    lang = get_user_language(user_id)
    if REQUIRED_CHANNEL and not await check_subscription(user_id):
        await message.answer(f"🔴 Подпишитесь на {REQUIRED_CHANNEL}",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
                             ]))
        return
    await message.answer("❄️ Добро пожаловать!", reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        await callback.message.edit_text("✅ Подписка подтверждена!", reply_markup=main_menu(user_id))
    else:
        await callback.message.edit_text(f"❌ Вы не подписаны на {REQUIRED_CHANNEL}. Подпишитесь и нажмите снова.",
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                              [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
                                          ]))
    await callback.answer()

@dp.callback_query(F.data == "claim_bonus")
async def claim_bonus_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    if not is_bonus_available(user_id):
        await callback.answer("❌ Вы уже получили бонус сегодня!", show_alert=True)
        return
    claim_bonus(user_id)
    increment_attacks(user_id, 50)
    await callback.message.edit_text("🎁 Вы получили +50 атак на сегодня! Лимит +50.", reply_markup=main_menu(user_id))
    await callback.answer()

@dp.callback_query(F.data == "premium_info")
async def premium_info_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    text = f"💎 Премиум подписка\n\nЦена: {VIP_PRICE}\n\nПреимущества:\n✅ Безлимитные атаки\n✅ Ежедневный бонус +50\n✅ Приоритетная поддержка\n✅ Кастомизация интерфейса\n\nДля покупки напишите {VIP_CONTACT}"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "rating")
async def rating_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    users = get_all_users()
    if not users:
        await callback.message.edit_text("🏆 Рейтинг пуст.", reply_markup=back_menu())
        return
    top = ""
    for i, (uid, username, attacks) in enumerate(users[:10], 1):
        uname = f"@{username}" if username and username != "нет" else f"ID{uid}"
        top += f"{i}. {uname} — {attacks} атак\n"
    await callback.message.edit_text(f"🏆 ГЛОБАЛЬНЫЙ РЕЙТИНГ:\n\n{top}", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
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
    await callback.message.edit_text(f"📊 Ваша статистика:\n" + "\n".join(lines) + f"\n\nВсего атак: {total}", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "advertisement")
async def ad_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    ad_text = get_setting('ad_text') or "Реклама не настроена."
    await callback.message.edit_text(f"📢 {ad_text}", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "change_color")
async def change_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    if not is_vip(user_id):
        await callback.answer("Только для VIP!", show_alert=True)
        return
    await callback.message.edit_text("🎨 Выберите цвет:", reply_markup=color_choose_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("color_"))
async def set_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    color = callback.data.split("_")[1]
    set_button_color(user_id, color)
    await callback.message.edit_text(f"✅ Цвет кнопок изменён на {color}.", reply_markup=main_menu(user_id))
    await callback.answer()

@dp.callback_query(F.data == "attack")
async def attack_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await callback.answer(f"❌ Дневной лимит ({limit}) исчерпан. Купите VIP для безлимита.", show_alert=True)
        return
    await callback.message.edit_text("🎯 Введите username цели (без @):", reply_markup=back_menu())
    await state.set_state(AttackState.waiting_username)
    await callback.answer()

@dp.message(AttackState.waiting_username)
async def attack_username(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(message, user_id, lang):
        await state.clear()
        return
    target = message.text.strip()
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
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await message.answer(f"❌ Лимит исчерпан.", reply_markup=main_menu(user_id))
        await state.clear()
        return
    await message.answer(f"🚀 Атака на @{target}...")
    await asyncio.sleep(random.uniform(2, 4))
    total = random.randint(50, 100)
    successful = int(total * random.uniform(0.7, 0.95))
    increment_attacks(user_id)
    add_target_stat(user_id, target)
    await message.answer(f"✅ Атака завершена! Отправлено {successful}/{total} жалоб на @{target}.", reply_markup=main_menu(user_id))
    await state.clear()

# ---------- ПРОФИЛЬ (исправлен) ----------
@dp.callback_query(F.data == "profile")
async def profile_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    row = get_user(user_id)
    if not row:
        await callback.message.edit_text("❌ Профиль не найден.", reply_markup=main_menu(user_id))
        return
    attacks = row[3]
    joined = row[4]
    vip_status = "✅ Активен" if is_vip(user_id) else "❌ Неактивен"
    daily = get_daily_attacks(user_id)
    limit = get_daily_limit(user_id)
    limit_display = "∞" if limit == float('inf') else str(limit)
    bonus_available = "Да" if is_bonus_available(user_id) else "Нет"
    refs, bonus_atk = get_referral_stats(user_id)
    color = get_button_color(user_id)
    joined_date = datetime.strptime(joined[:10], "%Y-%m-%d").strftime("%d.%m.%Y") if len(joined) >= 10 else joined[:10]
    promo_acts = get_promo_activations(user_id)
    ref_next = get_next_target(refs, REFERRAL_TARGETS)
    ref_next_str = f"{ref_next} реф. → +{get_bonus_for_target(ref_next, REFERRAL_TARGETS, REFERRAL_BONUSES)} атак" if ref_next else "Все цели достигнуты"
    promo_next = get_next_target(promo_acts, PROMO_TARGETS)
    promo_next_str = f"{promo_next} акт. → +{get_bonus_for_target(promo_next, PROMO_TARGETS, PROMO_BONUSES)} атак" if promo_next else "Все цели достигнуты"
    text = (f"👤 Мой профиль\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Имя: {row[2]}\n"
            f"📛 Юзернейм: @{row[1]}\n"
            f"❄️ Всего атак: {attacks}\n"
            f"📆 Сегодня: {daily}/{limit_display}\n"
            f"💎 VIP: {vip_status}\n"
            f"🎁 Бонус сегодня: {bonus_available}\n"
            f"📅 Регистрация: {joined_date}\n"
            f"👥 Рефералов: {refs} (бонусов: {bonus_atk} атак)\n"
            f"🎯 След. цель реф.: {ref_next_str}\n"
            f"🎫 Активаций промо: {promo_acts}\n"
            f"🎯 След. цель промо: {promo_next_str}\n"
            f"🎨 Цвет кнопок: {color}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ---------- ВВОД ПРОМОКОДА ----------
@dp.callback_query(F.data == "enter_promo")
async def enter_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    await callback.message.edit_text("Введите промокод:", reply_markup=back_menu())
    await state.set_state(PromoState.waiting_code)
    await callback.answer()

@dp.message(PromoState.waiting_code)
async def promo_code_handler(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(message, user_id, lang):
        await state.clear()
        return
    code = message.text.strip()
    result, typ = use_promo(user_id, code)
    if result is None:
        await message.answer("❌ Код не найден или уже использован.", reply_markup=main_menu(user_id))
    else:
        if typ == "vip":
            await message.answer(f"✅ VIP активирован на {result} дней!", reply_markup=main_menu(user_id))
        else:
            await message.answer(f"✅ Вам начислено {result} атак!", reply_markup=main_menu(user_id))
    await state.clear()

@dp.message(F.text, ~F.text.startswith('/'))
async def handle_promo_text(message: aiogram_types.Message):
    user_id = message.from_user.id
    code = message.text.strip()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code FROM promo_codes WHERE code = ?", (code.lower(),))
    row = c.fetchone()
    conn.close()
    if row:
        result, typ = use_promo(user_id, code)
        if result is None:
            await message.answer("❌ Код не найден или уже использован.", reply_markup=main_menu(user_id))
        else:
            if typ == "vip":
                await message.answer(f"✅ VIP активирован на {result} дней!", reply_markup=main_menu(user_id))
            else:
                await message.answer(f"✅ Вам начислено {result} атак!", reply_markup=main_menu(user_id))

# ---------- РЕФЕРАЛЫ ----------
@dp.callback_query(F.data == "ref_system")
async def ref_system_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    ref_code = get_referral_code(user_id)
    if not ref_code:
        await callback.message.edit_text("❌ Ошибка генерации ссылки. Попробуйте позже.", reply_markup=back_menu())
        await callback.answer()
        return
    me = await bot.get_me()
    if me.username:
        link = f"https://t.me/{me.username}?start=ref_{ref_code}"
    else:
        link = f"https://t.me/{me.id}?start=ref_{ref_code}"
    refs, bonus_atk = get_referral_stats(user_id)
    vip_ref_status = "✅ Активен (VIP на 7 дней)" if is_vip(user_id) else "❌ Не активен"
    next_target = get_next_target(refs, REFERRAL_TARGETS)
    if next_target:
        bonus = get_bonus_for_target(next_target, REFERRAL_TARGETS, REFERRAL_BONUSES)
        next_info = f"🎯 Следующая цель: {next_target} рефералов → +{bonus} атак"
    else:
        next_info = "🏁 Все цели достигнуты!"
    text = (f"👥 Реферальная система\n\n"
            f"Ваша ссылка:\n{link}\n\n"
            f"Приглашено: {refs} человек\n"
            f"Бонусов получено: {bonus_atk} атак\n"
            f"VIP за 10 рефералов: {vip_ref_status}\n"
            f"{next_info}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_ref_link")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "copy_ref_link")
async def copy_ref_link_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    ref_code = get_referral_code(user_id)
    if not ref_code:
        await callback.answer("Ошибка", show_alert=True)
        return
    me = await bot.get_me()
    if me.username:
        link = f"https://t.me/{me.username}?start=ref_{ref_code}"
    else:
        link = f"https://t.me/{me.id}?start=ref_{ref_code}"
    await callback.message.answer(f"Ваша реферальная ссылка:\n`{link}`", parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

# ---------- НАЗАД ----------
@dp.callback_query(F.data == "back")
async def back_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await check_subscription(user_id):
        await callback.message.edit_text(f"❌ Вы не подписаны на {REQUIRED_CHANNEL}",
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                              [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
                                          ]))
        await callback.answer()
        return
    await callback.message.edit_text("❄️ Главное меню", reply_markup=main_menu(user_id))
    await callback.answer()

# ---------- АДМИНКА ----------
@dp.message(Command("admin"))
async def admin_command(message: aiogram_types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа")
        return
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
    text = f"📊 СТАТИСТИКА\n\n👥 Всего пользователей: {len(users)}\n🎫 Промокодов: {len(promos)}\n\n🏆 ТОП-10:\n{top}"
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("📢 РАССЫЛКА\n\nВведите текст для рассылки (или /cancel для отмены):", reply_markup=back_menu())
    await state.set_state(BroadcastState.waiting_text)
    await callback.answer()

@dp.message(BroadcastState.waiting_text)
async def broadcast_text(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if message.text == "/cancel":
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    text = message.text
    users = get_all_user_ids()
    sent = 0
    status = await message.answer(f"📢 Рассылка... 0/{len(users)}")
    for i, uid in enumerate(users, 1):
        try:
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
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
    await callback.message.edit_text("Введите код промокода (можно русские буквы, без пробелов):", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_code)
    await callback.answer()

@dp.message(CreatePromoState.waiting_code)
async def create_promo_code(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    if ' ' in code or not code:
        await message.answer("❌ Код не должен содержать пробелов и не может быть пустым. Попробуйте ещё раз:")
        return
    await state.update_data(code=code)
    await message.answer("Выберите тип промокода:", reply_markup=promo_type_keyboard())
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
    if text in ['/cancel', '/admin']:
        await message.answer("❌ Создание промокода отменено.", reply_markup=admin_menu())
        await state.clear()
        return
    cleaned = clean_number_input(text)
    if not cleaned:
        await message.answer("❌ Введите положительное целое число (только цифры):")
        return
    try:
        bonus = int(cleaned)
        if bonus <= 0:
            raise ValueError
        await state.update_data(bonus=bonus)
        await message.answer("Введите количество использований (макс):", reply_markup=back_menu())
        await state.set_state(CreatePromoState.waiting_uses)
    except ValueError:
        await message.answer("❌ Введите положительное целое число (только цифры):")

@dp.message(CreatePromoState.waiting_uses)
async def create_promo_uses(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    if text in ['/cancel', '/admin']:
        await message.answer("❌ Создание промокода отменено.", reply_markup=admin_menu())
        await state.clear()
        return
    cleaned = clean_number_input(text)
    if not cleaned:
        await message.answer("❌ Введите положительное целое число (только цифры):")
        return
    try:
        uses = int(cleaned)
        if uses <= 0:
            raise ValueError
        data = await state.get_data()
        code = data['code']
        promo_type = data['type']
        bonus = data['bonus']
        if promo_type == 'vip':
            create_promo(code, uses, bonus, 0, 'vip', ADMIN_ID)
            bonus_str = f"{bonus} дней VIP"
        else:
            create_promo(code, uses, 0, bonus, 'attacks', ADMIN_ID)
            bonus_str = f"{bonus} атак"
        await message.answer(f"✅ Промокод **{code}** создан!\nТип: {promo_type.capitalize()}\nИспользований: {uses}\nБонус: {bonus_str}", reply_markup=admin_menu())
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите положительное целое число (только цифры):")

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
        for code, max_uses, used, typ, dur, bonus in promos:
            if typ == 'vip':
                bonus_str = f"{dur} дней VIP"
            else:
                bonus_str = f"{bonus} атак"
            lines.append(f"• {code} — {used}/{max_uses} использовано, {bonus_str}")
        text = "📋 СПИСОК ПРОМОКОДОВ:\n" + "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

# ---------- ЧЁРНЫЙ СПИСОК ----------
@dp.callback_query(F.data == "admin_blacklist")
async def admin_blacklist_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    blacklist = get_blacklist()
    if blacklist:
        text = "📋 ЧЁРНЫЙ СПИСОК:\n" + "\n".join([f"• @{b}" for b in blacklist])
    else:
        text = "📋 Чёрный список пуст."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить цель", callback_data="admin_add_blacklist")],
        [InlineKeyboardButton(text="➖ Удалить цель", callback_data="admin_remove_blacklist")],
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
    await callback.message.edit_text("Введите username цели для удаления (без @):", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_remove)
    await callback.answer()

@dp.message(BlacklistState.waiting_add)
async def add_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target = message.text.strip()
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
    target = message.text.strip()
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
    broadcast_enabled = get_setting('broadcast_enabled') == '1'
    status = "Включена" if broadcast_enabled else "Отключена"
    text = f"⚙️ НАСТРОЙКИ\n\nРекламный текст:\n{ad_text}\n\nАвто-рассылка: {status}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить рекламу", callback_data="admin_edit_ad")],
        [InlineKeyboardButton(text="🔄 Переключить авто-рассылку", callback_data="admin_toggle_broadcast")],
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
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    set_setting('ad_text', message.text)
    await message.answer("✅ Рекламный текст обновлён!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_toggle_broadcast")
async def admin_toggle_broadcast_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    current = get_setting('broadcast_enabled') == '1'
    new_status = not current
    set_setting('broadcast_enabled', '1' if new_status else '0')
    await callback.answer(f"Авто-рассылка {'включена' if new_status else 'отключена'}")
    await admin_settings_callback(callback)

# ---------- ФОНОВЫЕ ЗАДАЧИ ----------
async def weekly_broadcast():
    while True:
        try:
            if get_setting('broadcast_enabled') == '1':
                last = get_setting('last_weekly_broadcast')
                if last:
                    last_date = datetime.fromisoformat(last)
                    if datetime.now() - last_date >= timedelta(days=7):
                        ad_text = get_setting('ad_text') or "Реклама"
                        users = get_all_user_ids()
                        for uid in users:
                            try:
                                await bot.send_message(uid, f"📢 {ad_text}")
                                await asyncio.sleep(0.1)
                            except:
                                pass
                        set_setting('last_weekly_broadcast', datetime.now().isoformat())
                        print("✅ Авто-рассылка выполнена")
        except Exception as e:
            print(f"Ошибка авто-рассылки: {e}")
        await asyncio.sleep(3600)

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
                        lang = get_user_language(user_id)
                        await bot.send_message(user_id, f"⚠️ Ваш VIP истекает завтра! Продлите подписку.")
            conn.close()
        except Exception as e:
            print(f"VIP expiry check error: {e}")
        await asyncio.sleep(86400)

# ---------- ЯЗЫКИ ----------
@dp.message(Command("lang"))
async def lang_command(message: aiogram_types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_uk")],
        [InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang_kk")],
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")],
    ])
    await message.answer("🌐 Выберите язык / Choose language:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("lang_"))
async def lang_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.split("_")[1]
    set_user_language(user_id, new_lang)
    await callback.message.edit_text(f"🌐 Язык изменён.", reply_markup=main_menu(user_id))
    await callback.answer()

# ---------- ЗАПУСК ----------
async def main():
    init_db()
    asyncio.create_task(check_vip_expiry())
    asyncio.create_task(weekly_broadcast())
    print("🔰 Бот запущен (все функции исправлены, профиль работает)")
    print(f"👑 Админ: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
