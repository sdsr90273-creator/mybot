import os
import asyncio
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types as aiogram_types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===========================================
# НАСТРОЙКИ – ЗАМЕНИТЕ НА СВОИ
# ===========================================

BOT_TOKEN = "8610518935:AAHUdNEZ7c32dewRKf_bJ5_UQXBEwfvGa28"
ADMIN_ID = 8457792268
REQUIRED_CHANNEL = "@shakal_channel"  # или -1001234567890 (ID канала)
PROTECTED_BOT = "Shakalbekbot"
DB_NAME = "shakal.db"
VIP_CONTACT = "@sendholders"  # контакт для покупки VIP

# ===========================================
# БАЗА ДАННЫХ
# ===========================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  attacks INTEGER DEFAULT 0,
                  joined_date TEXT,
                  is_vip INTEGER DEFAULT 0,
                  vip_until TEXT,
                  daily_attacks INTEGER DEFAULT 0,
                  last_attack_date TEXT,
                  bonus_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes
                 (code TEXT PRIMARY KEY,
                  max_uses INTEGER DEFAULT 1,
                  used_count INTEGER DEFAULT 0,
                  duration_days INTEGER DEFAULT 30,
                  created_by INTEGER,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS used_promos
                 (user_id INTEGER,
                  code TEXT,
                  used_at TEXT,
                  PRIMARY KEY (user_id, code))''')
    c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def add_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, joined_date) 
                 VALUES (?, ?, ?, ?)''',
              (user_id, username or "нет", first_name or "нет", datetime.now().isoformat()))
    conn.commit()
    conn.close()

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

def increment_attacks(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    c.execute("SELECT last_attack_date, daily_attacks FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        last_date = row[0]
        daily = row[1] if row[1] else 0
        if last_date != today:
            daily = 0
        daily += 1
        c.execute("UPDATE users SET attacks = attacks + 1, daily_attacks = ?, last_attack_date = ? WHERE user_id = ?",
                  (daily, today, user_id))
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
    return row[0] if row[0] else 0

def set_vip(user_id, duration_days):
    until = (datetime.now() + timedelta(days=duration_days)).isoformat()
    update_user_field(user_id, "is_vip", 1)
    update_user_field(user_id, "vip_until", until)

def is_vip(user_id):
    row = get_user(user_id)
    if not row:
        return False
    if not row[5]:
        return False
    until = row[6]
    if until and datetime.now().isoformat() > until:
        update_user_field(user_id, "is_vip", 0)
        update_user_field(user_id, "vip_until", None)
        return False
    return True

def check_access(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
    admin = c.fetchone()
    conn.close()
    return admin is not None

def grant_access(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def revoke_access(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    row = get_user(user_id)
    if row:
        return row[3], row[4]
    return 0, datetime.now().isoformat()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, username, attacks FROM users ORDER BY attacks DESC")
    users = c.fetchall()
    conn.close()
    return users

def get_all_user_ids():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    return [u[0] for u in users]

# ----- Бонус -----
def get_bonus_date(user_id):
    row = get_user(user_id)
    if row:
        return row[9]
    return None

def claim_bonus(user_id):
    today = datetime.now().date().isoformat()
    update_user_field(user_id, "bonus_date", today)

def is_bonus_available(user_id):
    bonus_date = get_bonus_date(user_id)
    today = datetime.now().date().isoformat()
    return bonus_date != today

def get_daily_limit(user_id):
    if is_vip(user_id):
        return float('inf')
    if is_bonus_available(user_id):
        return 100
    else:
        return 150

# ----- Промокоды (регистронезависимые) -----
def create_promo(code, max_uses, duration_days, admin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO promo_codes (code, max_uses, used_count, duration_days, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (code.lower(), max_uses, 0, duration_days, admin_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def use_promo(user_id, code):
    code = code.lower()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT max_uses, used_count, duration_days FROM promo_codes WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, "❌ Код не найден"
    max_uses, used_count, duration = row
    if used_count >= max_uses:
        conn.close()
        return None, "❌ Код уже исчерпан"
    c.execute("SELECT * FROM used_promos WHERE user_id = ? AND code = ?", (user_id, code))
    if c.fetchone():
        conn.close()
        return None, "❌ Вы уже использовали этот код"
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    c.execute("INSERT INTO used_promos (user_id, code, used_at) VALUES (?, ?, ?)", (user_id, code, datetime.now().isoformat()))
    set_vip(user_id, duration)
    conn.commit()
    conn.close()
    return duration, f"✅ VIP активирован на {duration} дней!"

def get_promo_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code, max_uses, used_count, duration_days, created_at FROM promo_codes ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# ===========================================
# ПРОВЕРКА ПОДПИСКИ (реальная)
# ===========================================

async def check_subscription(user_id):
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return True

# ===========================================
# FSM СОСТОЯНИЯ
# ===========================================

class AttackState(StatesGroup):
    waiting_username = State()

class BroadcastState(StatesGroup):
    waiting_text = State()

class PromoState(StatesGroup):
    waiting_code = State()

class CreatePromoState(StatesGroup):
    waiting_code = State()
    waiting_uses = State()
    waiting_days = State()

# ===========================================
# ИМИТАЦИЯ АТАКИ
# ===========================================

async def attack_bot(target_username):
    await asyncio.sleep(random.uniform(2, 4))
    total = random.randint(50, 100)
    successful = int(total * random.uniform(0.7, 0.95))
    return successful, total

attack_cooldown = {}

async def attack_background(target_username, user_id, message, state: FSMContext):
    try:
        successful, total = await attack_bot(target_username)
        increment_attacks(user_id)
        attack_cooldown[user_id] = datetime.now()
        if successful > 0:
            result = f"✅ Шакализирован\n\n🎯 Цель: @{target_username}\n📊 Результат: {successful}/{total}"
        else:
            result = f"❌ Атака не удалась\n\n🎯 Цель: @{target_username}"
        await message.edit_text(result, parse_mode=ParseMode.HTML)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
        await message.answer("Выберите действие:", reply_markup=keyboard)
    except Exception as e:
        await message.edit_text(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        await state.clear()

# ===========================================
# КЛАВИАТУРЫ
# ===========================================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❄️ Отправить шакалы", callback_data="attack")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🎁 Бонус +50", callback_data="claim_bonus")],
        [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
    ])

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Выдать доступ", callback_data="admin_grant")],
        [InlineKeyboardButton(text="🚫 Забрать доступ", callback_data="admin_revoke")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎫 Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="📋 Промокоды", callback_data="admin_promo_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])

# ===========================================
# БОТ
# ===========================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def ensure_access(message_or_callback, user_id, callback=None):
    if not check_access(user_id):
        if callback:
            await callback.answer("⛔ Нет доступа", show_alert=True)
        else:
            await message_or_callback.answer("⛔ Нет доступа", parse_mode=ParseMode.HTML)
        return False
    if not await check_subscription(user_id):
        text = f"❌ Вы не подписаны на канал {REQUIRED_CHANNEL}!\nПодпишитесь и нажмите «Проверить подписку»."
        if callback:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
            ]))
        else:
            await message_or_callback.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
            ]))
        return False
    return True

# ===========================================
# ОБРАБОТЧИКИ
# ===========================================

@dp.message(Command("start"))
async def start_command(message: aiogram_types.Message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    if not check_access(user_id):
        await message.answer("🔴 Этот бот только для крутых\n\nСтать крутым и получить доступ - @shklhelping")
        return
    if not await check_subscription(user_id):
        await message.answer(f"❌ Вы не подписаны на канал {REQUIRED_CHANNEL}!\nПодпишитесь и нажмите «Проверить подписку».",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
                             ]))
        return
    await message.answer("❄️ Добро пожаловать в шакализатор!\nВоспользуйся меню:", reply_markup=main_menu())

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not check_access(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    if await check_subscription(user_id):
        await callback.message.edit_text("✅ Вы подписаны! Добро пожаловать.", reply_markup=main_menu())
        await callback.answer()
    else:
        await callback.message.edit_text(f"❌ Вы всё ещё не подписаны на {REQUIRED_CHANNEL}. Подпишитесь и нажмите снова.",
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                              [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
                                          ]))
        await callback.answer()

@dp.callback_query(F.data == "claim_bonus")
async def claim_bonus_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_access(callback.message, user_id, callback):
        return
    if not is_bonus_available(user_id):
        await callback.answer("❌ Вы уже получили бонус сегодня!", show_alert=True)
        return
    claim_bonus(user_id)
    await callback.message.edit_text("🎁 Вы получили +50 дополнительных жалоб на сегодня!\nТеперь ваш лимит – 150.", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(F.data == "attack")
async def attack_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_access(callback.message, user_id, callback):
        return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await callback.answer(
            f"❌ Дневной лимит ({limit}) исчерпан.\nКупите VIP у {VIP_CONTACT} для безлимита.",
            show_alert=True
        )
        return
    last = attack_cooldown.get(user_id, datetime.min)
    if datetime.now() - last < timedelta(seconds=1.100):
        remain = 1.100 - (datetime.now() - last).total_seconds()
        await callback.answer(f"⏳ Подождите {remain:.0f} сек", show_alert=True)
        return
    await callback.message.edit_text("🎯 Введите username (бота или человека)\n\nПример: @username", reply_markup=back_menu())
    await state.set_state(AttackState.waiting_username)
    await callback.answer()

@dp.message(AttackState.waiting_username)
async def attack_username(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_access(message, user_id):
        await state.clear()
        return
    target = message.text.replace('@', '').strip()
    if not target:
        await message.answer("❌ Неверный username", reply_markup=main_menu())
        await state.clear()
        return
    if target.lower() == PROTECTED_BOT.lower():
        await message.answer(f"⛔ НЕЛЬЗЯ! Бот {PROTECTED_BOT} под защитой.", parse_mode=ParseMode.HTML)
        await state.clear()
        return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await message.answer(
            f"❌ Дневной лимит ({limit}) исчерпан.\nКупите VIP у {VIP_CONTACT} для безлимита.",
            reply_markup=main_menu()
        )
        await state.clear()
        return
    status_msg = await message.answer(f"🚀 Шакализируем @{target}...")
    asyncio.create_task(attack_background(target, user_id, status_msg, state))
    await state.clear()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not await ensure_access(callback.message, user_id, callback):
        return
    attacks, joined = get_user_stats(user_id)
    vip = "✅ VIP" if is_vip(user_id) else "❌ Обычный"
    daily = get_daily_attacks(user_id)
    limit = get_daily_limit(user_id)
    bonus_available = "Да" if is_bonus_available(user_id) else "Нет (уже получен)"
    row = get_user(user_id)
    username = row[1] if row else "нет"
    first_name = row[2] if row else "нет"
    joined_date = datetime.strptime(joined[:10], "%Y-%m-%d").strftime("%d.%m.%Y") if len(joined) >= 10 else joined[:10]
    text = (f"👤 Мой профиль\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Имя: {first_name}\n"
            f"📛 Юзернейм: @{username}\n"
            f"❄️ Всего атак: {attacks}\n"
            f"📆 Сегодня: {daily}/{limit if limit != float('inf') else '∞'}\n"
            f"🌟 Статус: {vip}\n"
            f"🎁 Бонус сегодня: {bonus_available}\n"
            f"📅 Регистрация: {joined_date}")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ----- Промокоды через команду /promo или /промо -----
@dp.message(Command("promo", "промо"))
async def promo_command(message: aiogram_types.Message):
    user_id = message.from_user.id
    if not await ensure_access(message, user_id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /промо <код>")
        return
    code = args[1].strip()
    duration, msg = use_promo(user_id, code)
    if duration:
        await message.answer(f"{msg}\nVIP действует до {datetime.now()+timedelta(days=duration)}")
    else:
        await message.answer(msg)

# ----- Ввод промокода через кнопку (FSM) -----
@dp.callback_query(F.data == "enter_promo")
async def enter_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await ensure_access(callback.message, user_id, callback):
        return
    await callback.message.edit_text("Введите промокод:", reply_markup=back_menu())
    await state.set_state(PromoState.waiting_code)
    await callback.answer()

@dp.message(PromoState.waiting_code)
async def promo_code_handler(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await ensure_access(message, user_id):
        await state.clear()
        return
    code = message.text.strip()
    duration, msg = use_promo(user_id, code)
    if duration:
        await message.answer(f"{msg}\nVIP действует до {datetime.now()+timedelta(days=duration)}")
    else:
        await message.answer(msg)
    await state.clear()
    fake_callback = aiogram_types.CallbackQuery(id="0", from_user=message.from_user, message=message, data="profile")
    await profile_callback(fake_callback)

@dp.callback_query(F.data == "back")
async def back_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    if not check_access(user_id):
        await callback.message.edit_text("🔴 Нет доступа")
        await callback.answer()
        return
    if not await check_subscription(user_id):
        await callback.message.edit_text(f"❌ Вы не подписаны на {REQUIRED_CHANNEL}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Проверить подписку", callback_data="check_sub")]
        ]))
        await callback.answer()
        return
    await callback.message.edit_text("❄️ Добро пожаловать!", reply_markup=main_menu())
    await callback.answer()

# ===========================================
# АДМИН-КОМАНДЫ
# ===========================================

@dp.message(Command("admin"))
async def admin_command(message: aiogram_types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Нет доступа")
        return
    await message.answer("👑 АДМИН ПАНЕЛЬ", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_grant")
async def admin_grant_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("📝 ВЫДАЧА ДОСТУПА\n\nОтправьте /grant ID", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_revoke")
async def admin_revoke_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("📝 ОТЗЫВ ДОСТУПА\n\nОтправьте /revoke ID", reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    users = get_all_users()
    promo_count = len(get_promo_stats())
    text = f"📊 СТАТИСТИКА\n\n👥 Всего пользователей: {len(users)}\n🎫 Промокодов: {promo_count}\n\n🏆 ТОП-10:\n"
    for uid, username, attacks in users[:10]:
        uname = f"@{username}" if username != "нет" else "БЕЗ ЮЗЕРНЕЙМА"
        text += f"• <code>{uid}</code> ({uname}) — {attacks} атак\n"
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("📢 РАССЫЛКА\n\nОтправьте текст для рассылки всем пользователям.\nДля отмены — /cancel", reply_markup=back_menu())
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

@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите название промокода (код):", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_code)
    await callback.answer()

@dp.message(CreatePromoState.waiting_code)
async def create_promo_code(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(code=message.text.strip())
    await message.answer("Введите количество использований (например, 10):")
    await state.set_state(CreatePromoState.waiting_uses)

@dp.message(CreatePromoState.waiting_uses)
async def create_promo_uses(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uses = int(message.text.strip())
        await state.update_data(uses=uses)
        await message.answer("Введите количество дней VIP (например, 30):")
        await state.set_state(CreatePromoState.waiting_days)
    except:
        await message.answer("❌ Введите число!")

@dp.message(CreatePromoState.waiting_days)
async def create_promo_days(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        days = int(message.text.strip())
        data = await state.get_data()
        code = data.get("code")
        uses = data.get("uses")
        create_promo(code, uses, days, ADMIN_ID)
        await message.answer(f"✅ Промокод **{code}** создан!\nИспользований: {uses}\nДней VIP: {days}", parse_mode=ParseMode.HTML, reply_markup=admin_menu())
        await state.clear()
    except:
        await message.answer("❌ Введите число!")

@dp.callback_query(F.data == "admin_promo_list")
async def admin_promo_list_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    promos = get_promo_stats()
    if not promos:
        text = "📋 Промокодов пока нет."
    else:
        text = "📋 СПИСОК ПРОМОКОДОВ:\n\n"
        for code, max_uses, used, days, created in promos:
            text += f"• {code} — {used}/{max_uses} использовано, {days} дней VIP\n"
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.message(Command("grant"))
async def grant_command(message: aiogram_types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        grant_access(target_id)
        await message.answer(f"✅ Доступ выдан {target_id}")
    except:
        await message.answer("❌ Использование: /grant ID")

@dp.message(Command("revoke"))
async def revoke_command(message: aiogram_types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        revoke_access(target_id)
        await message.answer(f"✅ Доступ отозван у {target_id}")
    except:
        await message.answer("❌ Использование: /revoke ID")

# ===========================================
# ЗАПУСК
# ===========================================

async def main():
    init_db()
    print("🔰 Бот запущен (реальная подписка, промокоды через /промо)")
    print(f"👑 Админ: {ADMIN_ID}")
    print(f"📢 Канал: {REQUIRED_CHANNEL}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
