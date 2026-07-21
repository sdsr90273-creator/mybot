# ==========================
# config.py
# ==========================

from pathlib import Path

# ===== Telegram =====
BOT_TOKEN = "ВСТАВЬ_СЮДА_ТОКЕН_БОТА"

# ID администратора
ADMINS = [
    123456789
]

# ===== Database =====
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

# ===== VIP =====
VIP_PRICE = 2500          # стоимость VIP навсегда

# ===== Energy =====
START_ENERGY = 100
DAILY_BONUS = 50
REF_BONUS = 100

# ===== Promo =====
PROMO_MAX_LENGTH = 32

# ===== Text =====
BOT_NAME = "Energy Bot"

WELCOME_TEXT = f"""
⚡ Добро пожаловать в {BOT_NAME}!

Здесь ты можешь:

👤 Смотреть профиль
⚡ Получать энергию
🎁 Активировать промокоды
👥 Приглашать друзей
🏆 Попадать в рейтинг
⭐ Купить VIP

Приятной игры!
"""

MAIN_MENU = [
    "👤 Профиль",
    "⚡ Получить бонус",
    "🎟 Промокод",
    "👥 Рефералы",
    "🏆 Рейтинг",
    "🛒 Магазин",
    "ℹ Помощь"
]
import sqlite3
from datetime import datetime
from config import DB_PATH, START_ENERGY

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


def create_tables():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,

        energy INTEGER DEFAULT 100,

        vip INTEGER DEFAULT 0,

        referrals INTEGER DEFAULT 0,

        reg_date TEXT,

        last_bonus TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        code TEXT UNIQUE,

        reward INTEGER,

        max_uses INTEGER,

        used INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_used(
        user_id INTEGER,

        code TEXT
    )
    """)

    conn.commit()


create_tables()


# -------------------------
# Пользователи
# -------------------------

def user_exists(user_id):
    cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )
    return cursor.fetchone()


def register_user(user):
    if user_exists(user.id):
        return

    cursor.execute("""
    INSERT INTO users(
        user_id,
        username,
        full_name,
        energy,
        vip,
        referrals,
        reg_date
    )
    VALUES(?,?,?,?,?,?,?)
    """,
    (
        user.id,
        user.username,
        user.full_name,
        START_ENERGY,
        0,
        0,
        datetime.now().strftime("%d.%m.%Y")
    ))

    conn.commit()


# -------------------------
# Получить пользователя
# -------------------------

def get_user(user_id):

    cursor.execute(
        "SELECT * FROM users WHERE user_id=?",
        (user_id,)
    )

    return cursor.fetchone()


# -------------------------
# Энергия
# -------------------------

def get_energy(user_id):

    cursor.execute(
        "SELECT energy FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row:
        return row["energy"]

    return 0


def add_energy(user_id, amount):

    cursor.execute("""
    UPDATE users
    SET energy=energy+?
    WHERE user_id=?
    """,
    (
        amount,
        user_id
    ))

    conn.commit()


def remove_energy(user_id, amount):

    cursor.execute("""
    UPDATE users
    SET energy=energy-?
    WHERE user_id=?
    """,
    (
        amount,
        user_id
    ))

    conn.commit()


# -------------------------
# VIP
# -------------------------

def is_vip(user_id):

    cursor.execute(
        "SELECT vip FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row:
        return bool(row["vip"])

    return False


def give_vip(user_id):

    cursor.execute("""
    UPDATE users
    SET vip=1
    WHERE user_id=?
    """,
    (
        user_id,
    ))

    conn.commit()


# -------------------------
# Рейтинг
# -------------------------

def get_top(limit=10):

    cursor.execute("""
    SELECT *
    FROM users

    ORDER BY energy DESC

    LIMIT ?
    """,
    (limit,)
    )

    return cursor.fetchall()
    from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ===========================
# Главное меню
# ===========================

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 Профиль"),
            KeyboardButton(text="⚡ Получить бонус")
        ],
        [
            KeyboardButton(text="🎟 Промокод"),
            KeyboardButton(text="👥 Рефералы")
        ],
        [
            KeyboardButton(text="🏆 Рейтинг"),
            KeyboardButton(text="🛒 Магазин")
        ],
        [
            KeyboardButton(text="ℹ Помощь")
        ]
    ],
    resize_keyboard=True
)

# ===========================
# Магазин
# ===========================

shop_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⭐ VIP НАВСЕГДА — 2500⚡",
                callback_data="buy_vip"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data="back_menu"
            )
        ]
    ]
)

# ===========================
# Профиль
# ===========================

profile_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="refresh_profile"
            )
        ]
    ]
)

# ===========================
# Рейтинг
# ===========================

rating_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Обновить рейтинг",
                callback_data="rating_refresh"
            )
        ]
    ]
)

# ===========================
# Админ
# ===========================

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📢 Рассылка")
        ],
        [
            KeyboardButton(text="➕ Выдать энергию"),
            KeyboardButton(text="⭐ Выдать VIP")
        ],
        [
            KeyboardButton(text="🎟 Создать промокод")
        ],
        [
            KeyboardButton(text="📊 Статистика")
        ],
        [
            KeyboardButton(text="⬅ Меню")
        ]
    ],
    resize_keyboard=True
)
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from database import (
    register_user,
    user_exists,
    add_energy,
)

from keyboards import main_menu
from config import REF_BONUS, WELCOME_TEXT

router = Router()


@router.message(CommandStart())
async def start_command(message: Message):

    # -----------------------------
    # Регистрация пользователя
    # -----------------------------
    if not user_exists(message.from_user.id):
        register_user(message.from_user)

    # -----------------------------
    # Реферальная система
    # /start 123456789
    # -----------------------------
    args = message.text.split()

    if len(args) > 1:

        try:
            inviter = int(args[1])

            if inviter != message.from_user.id:

                if not user_exists(message.from_user.id):
                    register_user(message.from_user)

                add_energy(inviter, REF_BONUS)

        except:
            pass

    # -----------------------------
    # Приветствие
    # -----------------------------
    text = f"""
⚡ <b>Добро пожаловать!</b>

{WELCOME_TEXT}

━━━━━━━━━━━━━━

🆔 <code>{message.from_user.id}</code>

👤 @{message.from_user.username}

━━━━━━━━━━━━━━

Выберите нужный раздел ниже.
"""

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu
    )
# ==========================
# profile.py
# ==========================

from aiogram import Router, F
from aiogram.types import Message

from database import (
    get_user,
    add_energy,
)

from keyboards import profile_keyboard
from config import DAILY_BONUS

from datetime import datetime

router = Router()

# Хранение даты получения бонуса (в памяти)
# Для постоянного хранения лучше добавить поле last_bonus в БД.
bonus_cache = {}


@router.message(F.text == "👤 Профиль")
async def profile(message: Message):

    user = get_user(message.from_user.id)

    if not user:
        await message.answer(
            "❌ Вы не зарегистрированы.\nИспользуйте /start"
        )
        return

    vip = "⭐ Да" if user["vip"] else "❌ Нет"

    text = f"""
👤 <b>Ваш профиль</b>

🆔 ID: <code>{user['user_id']}</code>

👤 Username:
@{user['username'] or '-'}

⚡ Энергия:
<b>{user['energy']}</b>

⭐ VIP:
{vip}

👥 Рефералы:
{user['referrals']}

📅 Регистрация:
{user['reg_date']}
"""

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=profile_keyboard
    )


@router.message(F.text == "⚡ Получить бонус")
async def daily_bonus(message: Message):

    today = datetime.now().strftime("%d.%m.%Y")

    last = bonus_cache.get(message.from_user.id)

    if last == today:
        await message.answer(
            "⏳ Сегодня ежедневный бонус уже получен."
        )
        return

    add_energy(
        message.from_user.id,
        DAILY_BONUS
    )

    bonus_cache[message.from_user.id] = today

    await message.answer(
        f"""
🎉 Ежедневный бонус получен!

⚡ +{DAILY_BONUS} энергии

Заходите завтра снова ❤️
"""
    )
    # ==========================
# shop.py
# ==========================

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery
)

from database import (
    get_energy,
    remove_energy,
    give_vip,
    is_vip
)

from keyboards import shop_keyboard
from config import VIP_PRICE

router = Router()


# ==========================
# Открыть магазин
# ==========================

@router.message(F.text == "🛒 Магазин")
async def open_shop(message: Message):

    text = f"""
🛒 <b>МАГАЗИН</b>

━━━━━━━━━━━━━━━━━━

⭐ VIP НАВСЕГДА

Стоимость:
⚡ {VIP_PRICE} энергии

Преимущества:

• Красивый значок ⭐

• Будущие VIP-команды

• Особый статус

━━━━━━━━━━━━━━━━━━
"""

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=shop_keyboard
    )


# ==========================
# Купить VIP
# ==========================

@router.callback_query(F.data == "buy_vip")
async def buy_vip(callback: CallbackQuery):

    user_id = callback.from_user.id

    if is_vip(user_id):

        await callback.answer(
            "У вас уже есть VIP ⭐",
            show_alert=True
        )

        return

    energy = get_energy(user_id)

    if energy < VIP_PRICE:

        await callback.answer(
            f"Недостаточно энергии.\nНужно {VIP_PRICE} ⚡",
            show_alert=True
        )

        return

    remove_energy(
        user_id,
        VIP_PRICE
    )

    give_vip(user_id)

    await callback.message.edit_text(
        """
🎉 Поздравляем!

⭐ VIP успешно куплен!

Спасибо за поддержку проекта ❤️
""",
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================
# Назад
# ==========================

@router.callback_query(F.data == "back_menu")
async def back(callback: CallbackQuery):

    await callback.message.delete()

    await callback.answer()
    # ==========================
# promo.py
# ==========================

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from database import (
    activate_promo,
)

router = Router()


class PromoState(StatesGroup):
    waiting_code = State()


# ==========================
# Открыть ввод промокода
# ==========================

@router.message(F.text == "🎟 Промокод")
async def promo_menu(message: Message, state: FSMContext):

    await state.set_state(PromoState.waiting_code)

    await message.answer(
        """
🎟 Введите промокод.

Пример:

ENERGY100
"""
    )


# ==========================
# Проверка промокода
# ==========================

@router.message(PromoState.waiting_code)
async def check_promo(message: Message, state: FSMContext):

    code = message.text.upper()

    result = activate_promo(
        message.from_user.id,
        code
    )

    if result == "success":

        await message.answer(
            "✅ Промокод успешно активирован!"
        )

    elif result == "already":

        await message.answer(
            "❌ Вы уже использовали этот промокод."
        )

    elif result == "not_found":

        await message.answer(
            "❌ Промокод не найден."
        )

    elif result == "limit":

        await message.answer(
            "❌ Лимит активаций исчерпан."
        )

    else:

        await message.answer(
            "❌ Ошибка активации."
        )

    await state.clear()
    # ==========================
# admin.py
# ==========================

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import ADMINS
from keyboards import admin_keyboard
from database import (
    add_energy,
    give_vip,
    get_stats,
    create_promo
)

router = Router()


# ==========================
# Проверка администратора
# ==========================

def is_admin(user_id: int):
    return user_id in ADMINS


# ==========================
# FSM
# ==========================

class AdminState(StatesGroup):
    energy = State()
    vip = State()
    promo = State()


# ==========================
# Панель администратора
# ==========================

@router.message(F.text == "/admin")
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "⚙️ Админ-панель",
        reply_markup=admin_keyboard
    )


# ==========================
# Статистика
# ==========================

@router.message(F.text == "📊 Статистика")
async def stats(message: Message):

    if not is_admin(message.from_user.id):
        return

    users, vip, promos = get_stats()

    await message.answer(
        f"""
📊 Статистика

👤 Пользователей: {users}

⭐ VIP: {vip}

🎟 Промокодов: {promos}
"""
    )


# ==========================
# Выдать энергию
# ==========================

@router.message(F.text == "➕ Выдать энергию")
async def energy_start(message: Message, state: FSMContext):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminState.energy)

    await message.answer(
        "Введите:\n\nID СУММА\n\nПример:\n123456789 500"
    )


@router.message(AdminState.energy)
async def energy_finish(message: Message, state: FSMContext):

    try:

        uid, amount = message.text.split()

        add_energy(
            int(uid),
            int(amount)
        )

        await message.answer("✅ Энергия выдана.")

    except:

        await message.answer("❌ Неверный формат.")

    await state.clear()


# ==========================
# Выдать VIP
# ==========================

@router.message(F.text == "⭐ Выдать VIP")
async def vip_start(message: Message, state: FSMContext):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminState.vip)

    await message.answer(
        "Введите ID пользователя."
    )


@router.message(AdminState.vip)
async def vip_finish(message: Message, state: FSMContext):

    try:

        give_vip(
            int(message.text)
        )

        await message.answer(
            "⭐ VIP успешно выдан."
        )

    except:

        await message.answer(
            "Ошибка."
        )

    await state.clear()


# ==========================
# Создать промокод
# ==========================

@router.message(F.text == "🎟 Создать промокод")
async def promo_start(message: Message, state: FSMContext):

    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminState.promo)

    await message.answer(
        """
Введите:

КОД НАГРАДА ЛИМИТ

Пример:

START100 100 50
"""
    )


@router.message(AdminState.promo)
async def promo_finish(message: Message, state: FSMContext):

    try:

        code, reward, limit = message.text.split()

        create_promo(
            code.upper(),
            int(reward),
            int(limit)
        )

        await message.answer(
            "✅ Промокод создан."
        )

    except:

        await message.answer(
            "❌ Неверный формат."
        )

    await state.clear()
    # ==========================
# rating.py
# ==========================

from aiogram import Router, F
from aiogram.types import Message

from database import (
    get_top,
    get_user
)

from config import BOT_NAME

router = Router()


# ==========================
# ТОП игроков
# ==========================

@router.message(F.text == "🏆 Рейтинг")
async def rating(message: Message):

    top = get_top()

    if not top:

        await message.answer(
            "Рейтинг пока пуст."
        )

        return

    text = "🏆 <b>ТОП ПО ЭНЕРГИИ</b>\n\n"

    place = 1

    medals = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }

    for user in top:

        medal = medals.get(place, f"{place}.")

        username = user["username"]

        if username:
            username = "@" + username
        else:
            username = f"ID {user['user_id']}"

        text += (
            f"{medal} {username}\n"
            f"⚡ {user['energy']}\n\n"
        )

        place += 1

    await message.answer(
        text,
        parse_mode="HTML"
    )


# ==========================
# Рефералы
# ==========================

@router.message(F.text == "👥 Рефералы")
async def referrals(message: Message):

    me = get_user(
        message.from_user.id
    )

    ref_link = (
        f"https://t.me/{BOT_NAME}"
        f"?start={message.from_user.id}"
    )

    await message.answer(
f"""
👥 <b>Реферальная система</b>

Ваших приглашено:

<b>{me['referrals']}</b>

━━━━━━━━━━━━━━

За каждого нового пользователя:

⚡ +100 энергии

━━━━━━━━━━━━━━

Ваша ссылка:

<code>{ref_link}</code>
""",
        parse_mode="HTML"
    )


# ==========================
# Помощь
# ==========================

@router.message(F.text == "ℹ Помощь")
async def help_menu(message: Message):

    await message.answer(
"""
ℹ <b>Помощь</b>

👤 Профиль
Показывает ваш аккаунт.

⚡ Получить бонус
Ежедневный бонус энергии.

🎟 Промокод
Активация промокодов.

👥 Рефералы
Приглашайте друзей.

🏆 Рейтинг
Лучшие игроки.

🛒 Магазин
Покупка VIP.

━━━━━━━━━━━━━━

Версия: 1.0
""",
        parse_mode="HTML"
    )
    # ==========================
# main.py
# ==========================

import asyncio

from aiogram import Bot
from aiogram import Dispatcher

from config import BOT_TOKEN

# Роутеры
from start import router as start_router
from profile import router as profile_router
from promo import router as promo_router
from shop import router as shop_router
from rating import router as rating_router
from admin import router as admin_router


async def main():

    bot = Bot(
        token=BOT_TOKEN,
        parse_mode="HTML"
    )

    dp = Dispatcher()

    # ----------------------
    # Подключение роутеров
    # ----------------------

    dp.include_router(start_router)
    dp.include_router(profile_router)
    dp.include_router(shop_router)
    dp.include_router(promo_router)
    dp.include_router(rating_router)
    dp.include_router(admin_router)

    print("=" * 40)
    print("Бот успешно запущен!")
    print("=" * 40)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
