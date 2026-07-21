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

# ===========================================
# НАСТРОЙКИ
# ===========================================

BOT_TOKEN = "8610518935:AAHUdNEZ7c32dewRKf_bJ5_UQXBEwfvGa28"
ADMIN_ID = 8457792268
REQUIRED_CHANNEL = ""  # если нужна подписка, укажи канал
PROTECTED_BOT = "Shakalbekbot"
DB_NAME = "shakal.db"
VIP_CONTACT = "@sendholders"
WEEKLY_BROADCAST_ENABLED = True  # авто-рассылка раз в неделю

# ===========================================
# ТЕКСТЫ ДЛЯ РАЗНЫХ ЯЗЫКОВ
# ===========================================

TEXTS = {
    'ru': {
        'start': "❄️ Добро пожаловать в шакализатор!\nДля использования атаки необходим VIP.",
        'no_vip': "❌ У вас нет активного VIP-статуса.\nПриобретите подписку – нажмите «Премиум подписка» в меню.",
        'premium_info': (
            "💎 Премиум подписка\n\n"
            "Стоимость: уточняйте у @sendholders\n\n"
            "Преимущества:\n"
            "✅ Безлимитные атаки\n"
            "✅ Ежедневный бонус +50 атак\n"
            "✅ Приоритетная поддержка\n"
            "✅ Доступ ко всем будущим обновлениям\n"
            "✅ Кастомизация интерфейса (для VIP)\n\n"
            "Для покупки напишите @sendholders"
        ),
        'profile': (
            "👤 Мой профиль\n\n"
            "🆔 ID: <code>{id}</code>\n"
            "👤 Имя: {name}\n"
            "📛 Юзернейм: @{username}\n"
            "❄️ Всего атак: {attacks}\n"
            "📆 Сегодня: {daily}/{limit}\n"
            "💎 VIP: {vip_status}\n"
            "🎁 Бонус сегодня: {bonus}\n"
            "📅 Регистрация: {joined}\n"
            "👥 Рефералов: {refs} ({bonus_attacks} атак получено)\n"
            "🎨 Цвет кнопок: {color}"
        ),
        'bonus_claimed': "🎁 Вы получили +50 дополнительных жалоб на сегодня! Лимит – 150.",
        'bonus_already': "❌ Вы уже получили бонус сегодня!",
        'limit_exceeded': "❌ Дневной лимит ({limit}) исчерпан.\nКупите VIP у {contact} или используйте промокод.",
        'enter_username': "🎯 Введите username (бота или человека)\n\nПример: @username",
        'invalid_username': "❌ Неверный username",
        'protected': "⛔ НЕЛЬЗЯ! Бот {bot} под защитой.",
        'attack_start': "🚀 Шакализируем @{target}...",
        'attack_result': "✅ Шакализирован\n\n🎯 Цель: @{target}\n📊 Результат: {success}/{total}",
        'attack_fail': "❌ Атака не удалась\n\n🎯 Цель: @{target}",
        'promo_enter': "Введите промокод:",
        'promo_invalid': "❌ Код не найден или уже использован.",
        'promo_success_vip': "✅ VIP активирован на {days} дней!",
        'promo_success_attacks': "✅ Вам начислено {bonus} дополнительных атак!",
        'ref_system': "👥 Реферальная система\n\nВаша реферальная ссылка:\n{link}\n\nПриглашено: {count} человек\nПолучено бонусов: {bonus_attacks} атак\nVIP за 100 рефералов: {vip_ref_status}",
        'no_ref_link': "❌ Ошибка генерации ссылки, попробуйте позже.",
        'blacklist_added': "✅ Цель @{target} добавлена в чёрный список.",
        'blacklist_removed': "✅ Цель @{target} удалена из чёрного списка.",
        'blacklist_exists': "Цель уже в чёрном списке.",
        'blacklist_not_found': "Цель не найдена в чёрном списке.",
        'blacklist_list': "📋 ЧЁРНЫЙ СПИСОК:\n{list}",
        'blacklist_empty': "Чёрный список пуст.",
        'vip_expire_warning': "⚠️ Ваш VIP-статус истекает завтра! Продлите подписку, чтобы не потерять доступ к атакам.",
        'vip_expired': "Ваш VIP-статус истёк.",
        'lang_changed': "🌐 Язык изменён на русский.",
        'lang_choose': "🌐 Выберите язык:",
        'admin_panel': "👑 АДМИН ПАНЕЛЬ",
        'promo_created': "✅ Промокод **{code}** создан!\nТип: {type}\nИспользований: {uses}\nБонус: {bonus}",
        'promo_list': "📋 СПИСОК ПРОМОКОДОВ:\n{list}",
        'promo_list_empty': "📋 Промокодов пока нет.",
        'stats': "📊 СТАТИСТИКА\n\n👥 Всего пользователей: {users}\n🎫 Промокодов: {promos}\n\n🏆 ТОП-10:\n{top}",
        'broadcast_start': "📢 РАССЫЛКА\n\nОтправьте текст для рассылки.\nДля отмены — /cancel",
        'broadcast_progress': "📢 Рассылка... {sent}/{total}",
        'broadcast_done': "✅ Готово! Отправлено {sent}/{total}",
        'broadcast_cancel': "❌ Отменено",
        'no_access': "⛔ Нет доступа",
        'subscribe_prompt': "🔴 Для использования бота подпишитесь на канал {channel}!",
        'check_sub': "📢 Проверить подписку",
        'subscribed': "✅ Вы подписаны! Добро пожаловать.",
        'not_subscribed': "❌ Вы всё ещё не подписаны на {channel}. Подпишитесь и нажмите снова.",
        'rating': "🏆 ГЛОБАЛЬНЫЙ РЕЙТИНГ (по атакам):\n\n{top}",
        'rating_empty': "Пока никто не атаковал.",
        'stats_user': "📊 Ваша статистика по целям:\n{targets}\n\nВсего атак: {total}",
        'stats_empty': "Вы ещё никого не атаковали.",
        'color_changed': "✅ Цвет кнопок изменён на {color}.",
        'color_choose': "Выберите цвет кнопок:",
        'ad_text': "📢 {text}",
        'ad_empty': "Реклама не настроена.",
        'admin_settings': "⚙️ НАСТРОЙКИ\n\nРекламный текст:\n{ad_text}\n\nАвто-рассылка: {broadcast_status}",
        'broadcast_toggle': "Авто-рассылка переключена на {status}.",
    },
    'en': {
        'start': "❄️ Welcome to the Shakalizer! You need VIP to attack.",
        'no_vip': "❌ No active VIP. Buy subscription via «Premium subscription».",
        'premium_info': (
            "💎 Premium subscription\n\n"
            "Price: ask @sendholders\n\n"
            "Benefits:\n"
            "✅ Unlimited attacks\n"
            "✅ Daily +50 bonus\n"
            "✅ Priority support\n"
            "✅ All future updates\n"
            "✅ UI customization (for VIP)\n\n"
            "To buy, write @sendholders"
        ),
        'profile': (
            "👤 My profile\n\n"
            "🆔 ID: <code>{id}</code>\n"
            "👤 Name: {name}\n"
            "📛 Username: @{username}\n"
            "❄️ Total attacks: {attacks}\n"
            "📆 Today: {daily}/{limit}\n"
            "💎 VIP: {vip_status}\n"
            "🎁 Bonus today: {bonus}\n"
            "📅 Joined: {joined}\n"
            "👥 Referrals: {refs} ({bonus_attacks} attacks earned)\n"
            "🎨 Button color: {color}"
        ),
        'bonus_claimed': "🎁 +50 extra attacks today! Limit is now 150.",
        'bonus_already': "❌ Already claimed bonus today.",
        'limit_exceeded': "❌ Daily limit ({limit}) exceeded. Buy VIP from {contact}.",
        'enter_username': "🎯 Enter username (bot or person)\nExample: @username",
        'invalid_username': "❌ Invalid username",
        'protected': "⛔ CANNOT! Bot {bot} is protected.",
        'attack_start': "🚀 Shakalizing @{target}...",
        'attack_result': "✅ Shakalized\n\n🎯 Target: @{target}\n📊 Result: {success}/{total}",
        'attack_fail': "❌ Attack failed\n\n🎯 Target: @{target}",
        'promo_enter': "Enter promo code:",
        'promo_invalid': "❌ Code not found or already used.",
        'promo_success_vip': "✅ VIP activated for {days} days!",
        'promo_success_attacks': "✅ You got {bonus} extra attacks!",
        'ref_system': "👥 Referral system\n\nYour link:\n{link}\n\nInvited: {count}\nBonus attacks: {bonus_attacks}\nVIP for 100 referrals: {vip_ref_status}",
        'no_ref_link': "❌ Error generating link, try later.",
        'blacklist_added': "✅ Target @{target} added to blacklist.",
        'blacklist_removed': "✅ Target @{target} removed.",
        'blacklist_exists': "Target already in blacklist.",
        'blacklist_not_found': "Target not found.",
        'blacklist_list': "📋 BLACKLIST:\n{list}",
        'blacklist_empty': "Blacklist is empty.",
        'vip_expire_warning': "⚠️ Your VIP expires tomorrow! Renew to keep attacks.",
        'vip_expired': "Your VIP has expired.",
        'lang_changed': "🌐 Language changed to English.",
        'lang_choose': "🌐 Choose language:",
        'admin_panel': "👑 ADMIN PANEL",
        'promo_created': "✅ Promo **{code}** created!\nType: {type}\nUses: {uses}\nBonus: {bonus}",
        'promo_list': "📋 PROMO LIST:\n{list}",
        'promo_list_empty': "No promo codes yet.",
        'stats': "📊 STATISTICS\n\n👥 Users: {users}\n🎫 Promos: {promos}\n\n🏆 TOP-10:\n{top}",
        'broadcast_start': "📢 BROADCAST\n\nSend message to broadcast.\nTo cancel — /cancel",
        'broadcast_progress': "📢 Broadcasting... {sent}/{total}",
        'broadcast_done': "✅ Done! Sent {sent}/{total}",
        'broadcast_cancel': "❌ Canceled",
        'no_access': "⛔ Access denied",
        'subscribe_prompt': "🔴 Subscribe to {channel} to use this bot!",
        'check_sub': "📢 Check subscription",
        'subscribed': "✅ Subscribed! Welcome.",
        'not_subscribed': "❌ Not subscribed to {channel}. Subscribe and try again.",
        'rating': "🏆 GLOBAL RATING (by attacks):\n\n{top}",
        'rating_empty': "No attacks yet.",
        'stats_user': "📊 Your attack stats by target:\n{targets}\n\nTotal attacks: {total}",
        'stats_empty': "You haven't attacked anyone yet.",
        'color_changed': "✅ Button color changed to {color}.",
        'color_choose': "Choose button color:",
        'ad_text': "📢 {text}",
        'ad_empty': "No ad configured.",
        'admin_settings': "⚙️ SETTINGS\n\nAd text:\n{ad_text}\n\nAuto-broadcast: {broadcast_status}",
        'broadcast_toggle': "Auto-broadcast toggled to {status}.",
    },
    'uk': {  # украинский
        'start': "❄️ Ласкаво просимо до шакалізатора! Для атак потрібен VIP.",
        'no_vip': "❌ Немає активного VIP. Придбайте підписку в меню «Премиум підписка».",
        'premium_info': "💎 Преміум підписка\n\nЦіна: уточнюйте у @sendholders\n\nПереваги:\n✅ Безлімітні атаки\n✅ Щоденний бонус +50 атак\n✅ Пріоритетна підтримка\n✅ Доступ до оновлень\n✅ Кастомізація інтерфейсу\n\nДля покупки напишіть @sendholders",
        'profile': "👤 Мій профіль\n\n🆔 ID: <code>{id}</code>\n👤 Ім'я: {name}\n📛 Юзернейм: @{username}\n❄️ Всього атак: {attacks}\n📆 Сьогодні: {daily}/{limit}\n💎 VIP: {vip_status}\n🎁 Бонус сьогодні: {bonus}\n📅 Реєстрація: {joined}\n👥 Рефералів: {refs} ({bonus_attacks} атак отримано)\n🎨 Колір кнопок: {color}",
        'bonus_claimed': "🎁 Ви отримали +50 додаткових атак! Ліміт – 150.",
        'bonus_already': "❌ Ви вже отримали бонус сьогодні!",
        'limit_exceeded': "❌ Денний ліміт ({limit}) вичерпано. Купіть VIP у {contact}.",
        'enter_username': "🎯 Введіть username (бота або людини)\nПриклад: @username",
        'invalid_username': "❌ Невірний username",
        'protected': "⛔ НЕ МОЖНА! Бот {bot} під захистом.",
        'attack_start': "🚀 Шакалізуємо @{target}...",
        'attack_result': "✅ Шакалізовано\n\n🎯 Ціль: @{target}\n📊 Результат: {success}/{total}",
        'attack_fail': "❌ Атака не вдалася\n\n🎯 Ціль: @{target}",
        'promo_enter': "Введіть промокод:",
        'promo_invalid': "❌ Код не знайдено або вже використано.",
        'promo_success_vip': "✅ VIP активовано на {days} днів!",
        'promo_success_attacks': "✅ Вам нараховано {bonus} додаткових атак!",
        'ref_system': "👥 Реферальна система\n\nВаше посилання:\n{link}\n\nЗапрошено: {count}\nОтримано бонусів: {bonus_attacks}\nVIP за 100 рефералів: {vip_ref_status}",
        'no_ref_link': "❌ Помилка генерації посилання, спробуйте пізніше.",
        'blacklist_added': "✅ Ціль @{target} додана до чорного списку.",
        'blacklist_removed': "✅ Ціль @{target} видалена.",
        'blacklist_exists': "Ціль вже в чорному списку.",
        'blacklist_not_found': "Ціль не знайдена.",
        'blacklist_list': "📋 ЧОРНИЙ СПИСОК:\n{list}",
        'blacklist_empty': "Чорний список порожній.",
        'vip_expire_warning': "⚠️ Ваш VIP закінчується завтра! Продовжіть підписку.",
        'vip_expired': "Ваш VIP закінчився.",
        'lang_changed': "🌐 Мову змінено на українську.",
        'lang_choose': "🌐 Виберіть мову:",
        'admin_panel': "👑 АДМІН ПАНЕЛЬ",
        'promo_created': "✅ Промокод **{code}** створено!\nТип: {type}\nВикористань: {uses}\nБонус: {bonus}",
        'promo_list': "📋 СПИСОК ПРОМОКОДІВ:\n{list}",
        'promo_list_empty': "📋 Промокодів немає.",
        'stats': "📊 СТАТИСТИКА\n\n👥 Користувачів: {users}\n🎫 Промокодів: {promos}\n\n🏆 ТОП-10:\n{top}",
        'broadcast_start': "📢 РОЗСИЛКА\n\nНадішліть текст для розсилки.\nДля скасування — /cancel",
        'broadcast_progress': "📢 Розсилка... {sent}/{total}",
        'broadcast_done': "✅ Готово! Відправлено {sent}/{total}",
        'broadcast_cancel': "❌ Скасовано",
        'no_access': "⛔ Немає доступу",
        'subscribe_prompt': "🔴 Підпишіться на канал {channel} для використання бота!",
        'check_sub': "📢 Перевірити підписку",
        'subscribed': "✅ Ви підписані! Ласкаво просимо.",
        'not_subscribed': "❌ Ви все ще не підписані на {channel}. Підпишіться та натисніть знову.",
        'rating': "🏆 ГЛОБАЛЬНИЙ РЕЙТИНГ (за атаками):\n\n{top}",
        'rating_empty': "Поки ніхто не атакував.",
        'stats_user': "📊 Ваша статистика по цілях:\n{targets}\n\nВсього атак: {total}",
        'stats_empty': "Ви ще нікого не атакували.",
        'color_changed': "✅ Колір кнопок змінено на {color}.",
        'color_choose': "Виберіть колір кнопок:",
        'ad_text': "📢 {text}",
        'ad_empty': "Реклама не налаштована.",
        'admin_settings': "⚙️ НАЛАШТУВАННЯ\n\nРекламний текст:\n{ad_text}\n\nАвто-розсилка: {broadcast_status}",
        'broadcast_toggle': "Авто-розсилку переключено на {status}.",
    },
    'kk': {  # казахский
        'start': "❄️ Шакализаторға қош келдіңіз! Шабуыл жасау үшін VIP қажет.",
        'no_vip': "❌ VIP жоқ. «Премиум подписка» арқылы сатып алыңыз.",
        'premium_info': "💎 Премиум подписка\n\nБағасы: @sendholders-тан сұраңыз\n\nАртықшылықтар:\n✅ Шексіз шабуылдар\n✅ Күнделікті +50 бонус\n✅ Басымдықты қолдау\n✅ Барлық жаңартулар\n✅ Интерфейсті теңшеу\n\nСатып алу үшін @sendholders жазыңыз",
        'profile': "👤 Менің профилім\n\n🆔 ID: <code>{id}</code>\n👤 Аты: {name}\n📛 Логин: @{username}\n❄️ Барлық шабуыл: {attacks}\n📆 Бүгін: {daily}/{limit}\n💎 VIP: {vip_status}\n🎁 Бонус бүгін: {bonus}\n📅 Тіркелу: {joined}\n👥 Рефералдар: {refs} ({bonus_attacks} шабуыл)\n🎨 Түс: {color}",
        'bonus_claimed': "🎁 Сіз +50 қосымша шабуыл алдыңыз! Лимит – 150.",
        'bonus_already': "❌ Сіз бүгін бонус алдыңыз!",
        'limit_exceeded': "❌ Күндік лимит ({limit}) толты. VIP сатып алыңыз {contact}.",
        'enter_username': "🎯 Логинді енгізіңіз (бот немесе адам)\nМысалы: @username",
        'invalid_username': "❌ Қате логин",
        'protected': "⛔ БОЛМАЙДЫ! Бот {bot} қорғалған.",
        'attack_start': "🚀 @{target} шабуылдау...",
        'attack_result': "✅ Шабуыл сәтті\n\n🎯 Нысана: @{target}\n📊 Нәтиже: {success}/{total}",
        'attack_fail': "❌ Шабуыл сәтсіз\n\n🎯 Нысана: @{target}",
        'promo_enter': "Промокодты енгізіңіз:",
        'promo_invalid': "❌ Код табылмады немесе қолданылған.",
        'promo_success_vip': "✅ VIP {days} күнге белсенді!",
        'promo_success_attacks': "✅ Сіз {bonus} қосымша шабуыл алдыңыз!",
        'ref_system': "👥 Рефералдық жүйе\n\nСіздің сілтеме:\n{link}\n\nШақырылған: {count}\nБонус: {bonus_attacks}\n100 реферал үшін VIP: {vip_ref_status}",
        'no_ref_link': "❌ Сілтеме генерациясы қате, кейін көріңіз.",
        'blacklist_added': "✅ @{target} қара тізімге қосылды.",
        'blacklist_removed': "✅ @{target} қара тізімнен алынды.",
        'blacklist_exists': "Нысана қара тізімде бар.",
        'blacklist_not_found': "Нысана табылмады.",
        'blacklist_list': "📋 ҚАРА ТІЗІМ:\n{list}",
        'blacklist_empty': "Қара тізім бос.",
        'vip_expire_warning': "⚠️ VIP ертең аяқталады! Жаңартыңыз.",
        'vip_expired': "VIP аяқталды.",
        'lang_changed': "🌐 Тіл қазақшаға ауысты.",
        'lang_choose': "🌐 Тілді таңдаңыз:",
        'admin_panel': "👑 АДМИН ПАНЕЛІ",
        'promo_created': "✅ **{code}** промокоды жасалды!\nТүрі: {type}\nҚолданыс: {uses}\nБонус: {bonus}",
        'promo_list': "📋 ПРОМОКОДТАР:\n{list}",
        'promo_list_empty': "Промокодтар жоқ.",
        'stats': "📊 СТАТИСТИКА\n\n👥 Пайдаланушылар: {users}\n🎫 Промокодтар: {promos}\n\n🏆 ТОП-10:\n{top}",
        'broadcast_start': "📢 ХАБАРЛАМА\n\nМәтінді жіберіңіз.\nБолдырмау — /cancel",
        'broadcast_progress': "📢 Жіберу... {sent}/{total}",
        'broadcast_done': "✅ Дайын! {sent}/{total} жіберілді.",
        'broadcast_cancel': "❌ Болдырмалды",
        'no_access': "⛔ Рұқсат жоқ",
        'subscribe_prompt': "🔴 Ботты пайдалану үшін {channel} арнасына жазылыңыз!",
        'check_sub': "📢 Жазылымды тексеру",
        'subscribed': "✅ Жазылдыңыз! Қош келдіңіз.",
        'not_subscribed': "❌ Сіз әлі {channel} арнасына жазылмағансыз.",
        'rating': "🏆 ӘЛЕМДІК РЕЙТИНГ (шабуылдар бойынша):\n\n{top}",
        'rating_empty': "Әлі шабуыл болған жоқ.",
        'stats_user': "📊 Нысаналар бойынша статистика:\n{targets}\n\nБарлығы: {total}",
        'stats_empty': "Сіз әлі ешкімді шабуылдамағансыз.",
        'color_changed': "✅ Түс {color} өзгертілді.",
        'color_choose': "Түсті таңдаңыз:",
        'ad_text': "📢 {text}",
        'ad_empty': "Реклама орнатылмаған.",
        'admin_settings': "⚙️ БАПТАУ\n\nРеклама мәтіні:\n{ad_text}\n\nАвто-хабарлама: {broadcast_status}",
        'broadcast_toggle': "Авто-хабарлама {status} күйіне ауысты.",
    },
    'uz': {  # узбекский
        'start': "❄️ Shakalizatorga xush kelibsiz! Hujum qilish uchun VIP kerak.",
        'no_vip': "❌ VIP mavjud emas. «Премиум подписка» tugmasini bosing.",
        'premium_info': "💎 Premium obuna\n\nNarxi: @sendholders dan so'rang\n\nAfzalliklari:\n✅ Cheksiz hujumlar\n✅ Kunlik +50 bonus\n✅ Tezkor yordam\n✅ Yangilanishlar\n✅ Interfeysni sozlash\n\nSotib olish uchun @sendholders ga yozing",
        'profile': "👤 Mening profilim\n\n🆔 ID: <code>{id}</code>\n👤 Ism: {name}\n📛 Username: @{username}\n❄️ Jami hujum: {attacks}\n📆 Bugun: {daily}/{limit}\n💎 VIP: {vip_status}\n🎁 Bonus bugun: {bonus}\n📅 Ro'yxat: {joined}\n👥 Referallar: {refs} ({bonus_attacks} hujum)\n🎨 Tugma rangi: {color}",
        'bonus_claimed': "🎁 Siz +50 qo'shimcha hujum oldingiz! Limit – 150.",
        'bonus_already': "❌ Siz bugun bonus oldingiz!",
        'limit_exceeded': "❌ Kunlik limit ({limit}) to'ldi. VIP sotib oling {contact}.",
        'enter_username': "🎯 Username kiriting (bot yoki odam)\nMisol: @username",
        'invalid_username': "❌ Noto'g'ri username",
        'protected': "⛔ MUMKIN EMAS! Bot {bot} himoyalangan.",
        'attack_start': "🚀 @{target} ga hujum...",
        'attack_result': "✅ Hujum muvaffaqiyatli\n\n🎯 Maqsad: @{target}\n📊 Natija: {success}/{total}",
        'attack_fail': "❌ Hujum muvaffaqiyatsiz\n\n🎯 Maqsad: @{target}",
        'promo_enter': "Promokodni kiriting:",
        'promo_invalid': "❌ Kod topilmadi yoki ishlatilgan.",
        'promo_success_vip': "✅ VIP {days} kun faollashtirildi!",
        'promo_success_attacks': "✅ Siz {bonus} qo'shimcha hujum oldingiz!",
        'ref_system': "👥 Referal tizimi\n\nSizning havola:\n{link}\n\nTaklif qilingan: {count}\nBonus hujumlar: {bonus_attacks}\n100 referal uchun VIP: {vip_ref_status}",
        'no_ref_link': "❌ Havola yaratishda xatolik, keyinroq urinib ko'ring.",
        'blacklist_added': "✅ @{target} qora ro'yxatga qo'shildi.",
        'blacklist_removed': "✅ @{target} qora ro'yxatdan olindi.",
        'blacklist_exists': "Maqsad allaqachon qora ro'yxatda.",
        'blacklist_not_found': "Maqsad topilmadi.",
        'blacklist_list': "📋 QORA RO'YXAT:\n{list}",
        'blacklist_empty': "Qora ro'yxat bo'sh.",
        'vip_expire_warning': "⚠️ VIP ertaga tugaydi! Yangilang.",
        'vip_expired': "VIP tugadi.",
        'lang_changed': "🌐 Til o'zbek tiliga o'zgartirildi.",
        'lang_choose': "🌐 Tilni tanlang:",
        'admin_panel': "👑 ADMIN PANEL",
        'promo_created': "✅ **{code}** promokodi yaratildi!\nTuri: {type}\nIshlatish: {uses}\nBonus: {bonus}",
        'promo_list': "📋 PROMOKODLAR:\n{list}",
        'promo_list_empty': "Promokodlar yo'q.",
        'stats': "📊 STATISTIKA\n\n👥 Foydalanuvchilar: {users}\n🎫 Promokodlar: {promos}\n\n🏆 TOP-10:\n{top}",
        'broadcast_start': "📢 XABAR\n\nMatnni yuboring.\nBekor qilish — /cancel",
        'broadcast_progress': "📢 Yuborilmoqda... {sent}/{total}",
        'broadcast_done': "✅ Tayyor! {sent}/{total} yuborildi.",
        'broadcast_cancel': "❌ Bekor qilindi",
        'no_access': "⛔ Ruxsat yo'q",
        'subscribe_prompt': "🔴 Botdan foydalanish uchun {channel} kanaliga obuna bo'ling!",
        'check_sub': "📢 Obunani tekshirish",
        'subscribed': "✅ Obuna bo'ldingiz! Xush kelibsiz.",
        'not_subscribed': "❌ Siz hali {channel} kanaliga obuna bo'lmagansiz.",
        'rating': "🏆 GLOBAL REYTING (hujumlar bo'yicha):\n\n{top}",
        'rating_empty': "Hali hech kim hujum qilmagan.",
        'stats_user': "📊 Maqsadlar bo'yicha statistikangiz:\n{targets}\n\nJami hujum: {total}",
        'stats_empty': "Siz hali hech kimga hujum qilmagansiz.",
        'color_changed': "✅ Tugma rangi {color} ga o'zgartirildi.",
        'color_choose': "Tugma rangini tanlang:",
        'ad_text': "📢 {text}",
        'ad_empty': "Reklama sozlanmagan.",
        'admin_settings': "⚙️ SOZLAMALAR\n\nReklama matni:\n{ad_text}\n\nAvto-xabar: {broadcast_status}",
        'broadcast_toggle': "Avto-xabar {status} holatiga o'zgartirildi.",
    }
}

LANGUAGES = ['ru', 'en', 'uk', 'kk', 'uz']

# ===========================================
# БАЗА ДАННЫХ (расширенная)
# ===========================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # users (добавили поле button_color)
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
                  bonus_date TEXT,
                  referrer_id INTEGER,
                  referral_code TEXT,
                  referrals_count INTEGER DEFAULT 0,
                  referral_attacks_bonus INTEGER DEFAULT 0,
                  language TEXT DEFAULT 'ru',
                  is_vip_lifetime INTEGER DEFAULT 0,
                  button_color TEXT DEFAULT 'blue')''')
    # targets – для статистики по целям
    c.execute('''CREATE TABLE IF NOT EXISTS targets
                 (user_id INTEGER,
                  target_username TEXT,
                  count INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, target_username))''')
    # settings – для рекламы и авто-рассылки
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY,
                  value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ad_text', 'Реклама пока не настроена.')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('broadcast_enabled', '1')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_weekly_broadcast', '1970-01-01 00:00:00')")
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes
                 (code TEXT PRIMARY KEY,
                  max_uses INTEGER DEFAULT 1,
                  used_count INTEGER DEFAULT 0,
                  duration_days INTEGER DEFAULT 0,
                  attacks_bonus INTEGER DEFAULT 0,
                  type TEXT DEFAULT 'vip',
                  created_by INTEGER,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS used_promos
                 (user_id INTEGER,
                  code TEXT,
                  used_at TEXT,
                  PRIMARY KEY (user_id, code))''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist
                 (target_username TEXT PRIMARY KEY,
                  added_by INTEGER,
                  added_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (referrer_id INTEGER,
                  referred_id INTEGER PRIMARY KEY,
                  joined_at TEXT)''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# ===========================================
# ФУНКЦИИ РАБОТЫ С БД
# ===========================================

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def add_user(user_id, username, first_name, referrer_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    ref_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    c.execute('''INSERT INTO users
                 (user_id, username, first_name, joined_date, referral_code, referrer_id, language, button_color)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, username or "нет", first_name or "нет",
               datetime.now().isoformat(), ref_code, referrer_id, 'ru', 'blue'))
    if referrer_id:
        c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
        c.execute("INSERT INTO referrals (referrer_id, referred_id, joined_at) VALUES (?, ?, ?)",
                  (referrer_id, user_id, datetime.now().isoformat()))
        c.execute("UPDATE users SET attacks = attacks + 20 WHERE user_id = ?", (referrer_id,))
        c.execute("UPDATE users SET referral_attacks_bonus = referral_attacks_bonus + 20 WHERE user_id = ?", (referrer_id,))
        c.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
        refs = c.fetchone()[0]
        if refs >= 100:
            vip_until = (datetime.now() + timedelta(days=90)).isoformat()
            c.execute("UPDATE users SET is_vip = 1, vip_until = ? WHERE user_id = ?", (vip_until, referrer_id))
    conn.commit()
    conn.close()

def update_user_field(user_id, field, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def increment_attacks(user_id, count=1):
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
    return row[0] if row[0] else 0

def set_vip(user_id, duration_days):
    if duration_days == -1:
        update_user_field(user_id, "is_vip", 1)
        update_user_field(user_id, "is_vip_lifetime", 1)
        update_user_field(user_id, "vip_until", None)
        return
    until = (datetime.now() + timedelta(days=duration_days)).isoformat()
    update_user_field(user_id, "is_vip", 1)
    update_user_field(user_id, "vip_until", until)
    update_user_field(user_id, "is_vip_lifetime", 0)

def is_vip(user_id):
    row = get_user(user_id)
    if not row:
        return False
    if row[5] == 1:
        if row[6] is None:
            return row[11] == 1
        if datetime.now().isoformat() > row[6]:
            update_user_field(user_id, "is_vip", 0)
            update_user_field(user_id, "vip_until", None)
            return False
        return True
    return False

def get_daily_limit(user_id):
    if is_vip(user_id):
        return float('inf')
    return 100

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

def get_referral_code(user_id):
    row = get_user(user_id)
    if row:
        return row[7]
    return None

def get_referral_stats(user_id):
    row = get_user(user_id)
    if row:
        return row[8], row[9]
    return 0, 0

def get_button_color(user_id):
    row = get_user(user_id)
    if row and row[12]:
        return row[12]
    return 'blue'

def set_button_color(user_id, color):
    update_user_field(user_id, "button_color", color)

def get_user_language(user_id):
    row = get_user(user_id)
    if row and row[10]:
        return row[10]
    return 'ru'

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

# Промокоды
def create_promo(code, max_uses, duration_days, attacks_bonus, promo_type, admin_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO promo_codes (code, max_uses, used_count, duration_days, attacks_bonus, type, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (code.lower(), max_uses, 0, duration_days, attacks_bonus, promo_type, admin_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"✅ Промокод {code} создан")

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

# ===========================================
# ПРОВЕРКА ПОДПИСКИ (если нужна)
# ===========================================

async def check_subscription(user_id):
    if not REQUIRED_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===========================================
# FSM
# ===========================================

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

class ChangeColorState(StatesGroup):
    waiting_color = State()

# ===========================================
# ИМИТАЦИЯ АТАКИ
# ===========================================

async def attack_bot(target_username):
    await asyncio.sleep(random.uniform(2, 4))
    total = random.randint(50, 100)
    successful = int(total * random.uniform(0.7, 0.95))
    return successful, total

attack_cooldown = {}

async def attack_background(target_username, user_id, message, state, lang):
    try:
        successful, total = await attack_bot(target_username)
        increment_attacks(user_id)
        add_target_stat(user_id, target_username)  # сохраняем статистику по цели
        attack_cooldown[user_id] = datetime.now()
        if successful > 0:
            result = TEXTS[lang]['attack_result'].format(target=target_username, success=successful, total=total)
        else:
            result = TEXTS[lang]['attack_fail'].format(target=target_username)
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

def main_menu(lang='ru', user_id=None):
    color = get_button_color(user_id) if user_id else 'blue'
    # цвет кнопок пока не реализован в inline (только текстовый), можно использовать эмодзи или менять стиль в будущем.
    buttons = [
        [InlineKeyboardButton(text="❄️ Отправить шакалы", callback_data="attack")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🎁 Бонус +50", callback_data="claim_bonus")],
        [InlineKeyboardButton(text="💎 Премиум подписка", callback_data="premium_info")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="ref_system")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="📢 Реклама", callback_data="advertisement")],
    ]
    # Если VIP – добавляем кастомизацию
    if is_vip(user_id):
        buttons.append([InlineKeyboardButton(text="🎨 Сменить цвет кнопок", callback_data="change_color")])
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

# ===========================================
# БОТ
# ===========================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===========================================

async def get_lang(user_id):
    return get_user_language(user_id)

async def ensure_subscribed(message_or_callback, user_id, lang, callback=None):
    if not await check_subscription(user_id):
        text = TEXTS[lang]['subscribe_prompt'].format(channel=REQUIRED_CHANNEL)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]['check_sub'], callback_data="check_sub")]
        ])
        if callback:
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        else:
            await message_or_callback.answer(text, reply_markup=keyboard)
        return False
    return True

# ===========================================
# ОБРАБОТЧИКИ
# ===========================================

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
        await message.answer(TEXTS[lang]['subscribe_prompt'].format(channel=REQUIRED_CHANNEL),
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text=TEXTS[lang]['check_sub'], callback_data="check_sub")]
                             ]))
        return
    await message.answer(TEXTS[lang]['start'], reply_markup=main_menu(lang, user_id))

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if await check_subscription(user_id):
        await callback.message.edit_text(TEXTS[lang]['subscribed'], reply_markup=main_menu(lang, user_id))
        await callback.answer()
    else:
        await callback.message.edit_text(TEXTS[lang]['not_subscribed'].format(channel=REQUIRED_CHANNEL),
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                              [InlineKeyboardButton(text=TEXTS[lang]['check_sub'], callback_data="check_sub")]
                                          ]))
        await callback.answer()

@dp.callback_query(F.data == "claim_bonus")
async def claim_bonus_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    if not is_bonus_available(user_id):
        await callback.answer(TEXTS[lang]['bonus_already'], show_alert=True)
        return
    claim_bonus(user_id)
    await callback.message.edit_text(TEXTS[lang]['bonus_claimed'], reply_markup=main_menu(lang, user_id))
    await callback.answer()

@dp.callback_query(F.data == "premium_info")
async def premium_info_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    text = TEXTS[lang]['premium_info']
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "rating")
async def rating_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    users = get_all_users()
    if not users:
        await callback.message.edit_text(TEXTS[lang]['rating_empty'], reply_markup=back_menu())
        return
    top = ""
    for i, (uid, username, attacks) in enumerate(users[:10], 1):
        uname = f"@{username}" if username and username != "нет" else f"ID{uid}"
        top += f"{i}. {uname} — {attacks} атак\n"
    text = TEXTS[lang]['rating'].format(top=top)
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "my_stats")
async def my_stats_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    targets = get_user_targets(user_id)
    if not targets:
        await callback.message.edit_text(TEXTS[lang]['stats_empty'], reply_markup=back_menu())
        return
    lines = []
    total = 0
    for target, count in targets:
        lines.append(f"@{target} — {count} раз")
        total += count
    text = TEXTS[lang]['stats_user'].format(targets="\n".join(lines), total=total)
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "advertisement")
async def ad_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    ad_text = get_setting('ad_text') or TEXTS[lang]['ad_empty']
    text = TEXTS[lang]['ad_text'].format(text=ad_text)
    await callback.message.edit_text(text, reply_markup=back_menu())
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
    await callback.message.edit_text(TEXTS[lang]['color_choose'], reply_markup=color_choose_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("color_"))
async def set_color_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    color = callback.data.split("_")[1]
    set_button_color(user_id, color)
    await callback.message.edit_text(TEXTS[lang]['color_changed'].format(color=color), reply_markup=main_menu(lang, user_id))
    await callback.answer()

@dp.callback_query(F.data == "attack")
async def attack_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    if not is_vip(user_id):
        await callback.answer(TEXTS[lang]['no_vip'], show_alert=True)
        return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await callback.answer(TEXTS[lang]['limit_exceeded'].format(limit=limit, contact=VIP_CONTACT), show_alert=True)
        return
    last = attack_cooldown.get(user_id, datetime.min)
    if datetime.now() - last < timedelta(seconds=1.100):
        remain = 1.100 - (datetime.now() - last).total_seconds()
        await callback.answer(f"⏳ Подождите {remain:.0f} сек", show_alert=True)
        return
    await callback.message.edit_text(TEXTS[lang]['enter_username'], reply_markup=back_menu())
    await state.set_state(AttackState.waiting_username)
    await callback.answer()

@dp.message(AttackState.waiting_username)
async def attack_username(message: aiogram_types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(message, user_id, lang):
        await state.clear()
        return
    target = message.text.replace('@', '').strip()
    if not target:
        await message.answer(TEXTS[lang]['invalid_username'], reply_markup=main_menu(lang, user_id))
        await state.clear()
        return
    if is_in_blacklist(target):
        await message.answer(f"⛔ Цель @{target} в чёрном списке.", reply_markup=main_menu(lang, user_id))
        await state.clear()
        return
    if target.lower() == PROTECTED_BOT.lower():
        await message.answer(TEXTS[lang]['protected'].format(bot=PROTECTED_BOT), parse_mode=ParseMode.HTML)
        await state.clear()
        return
    limit = get_daily_limit(user_id)
    daily = get_daily_attacks(user_id)
    if daily >= limit:
        await message.answer(TEXTS[lang]['limit_exceeded'].format(limit=limit, contact=VIP_CONTACT), reply_markup=main_menu(lang, user_id))
        await state.clear()
        return
    status_msg = await message.answer(TEXTS[lang]['attack_start'].format(target=target))
    asyncio.create_task(attack_background(target, user_id, status_msg, state, lang))
    await state.clear()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    row = get_user(user_id)
    if not row:
        await callback.message.edit_text("❌ Профиль не найден", reply_markup=main_menu(lang, user_id))
        return
    attacks = row[3]
    joined = row[4]
    vip = "✅ Активен" if is_vip(user_id) else "❌ Неактивен"
    daily = get_daily_attacks(user_id)
    limit = get_daily_limit(user_id)
    limit_display = "∞" if limit == float('inf') else str(limit)
    bonus_available = "Да" if is_bonus_available(user_id) else "Нет (уже получен)"
    refs, bonus_atk = get_referral_stats(user_id)
    color = get_button_color(user_id)
    joined_date = datetime.strptime(joined[:10], "%Y-%m-%d").strftime("%d.%m.%Y") if len(joined) >= 10 else joined[:10]
    text = TEXTS[lang]['profile'].format(
        id=user_id,
        name=row[2],
        username=row[1] if row[1] != "нет" else "отсутствует",
        attacks=attacks,
        daily=daily,
        limit=limit_display,
        vip_status=vip,
        bonus=bonus_available,
        joined=joined_date,
        refs=refs,
        bonus_attacks=bonus_atk,
        color=color
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "enter_promo")
async def enter_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    await callback.message.edit_text(TEXTS[lang]['promo_enter'], reply_markup=back_menu())
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
        await message.answer(TEXTS[lang]['promo_invalid'])
    else:
        if typ == "vip":
            await message.answer(TEXTS[lang]['promo_success_vip'].format(days=result))
        else:
            await message.answer(TEXTS[lang]['promo_success_attacks'].format(bonus=result))
    await state.clear()
    fake_callback = aiogram_types.CallbackQuery(id="0", from_user=message.from_user, message=message, data="profile")
    await profile_callback(fake_callback)

# Обработчик промокода без команды
@dp.message(F.text, ~F.text.startswith('/'))
async def handle_promo_text(message: aiogram_types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    code = message.text.strip()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT code FROM promo_codes WHERE code = ?", (code.lower(),))
    row = c.fetchone()
    conn.close()
    if row:
        result, typ = use_promo(user_id, code)
        if result is None:
            await message.answer(TEXTS[lang]['promo_invalid'])
        else:
            if typ == "vip":
                await message.answer(TEXTS[lang]['promo_success_vip'].format(days=result))
            else:
                await message.answer(TEXTS[lang]['promo_success_attacks'].format(bonus=result))

@dp.callback_query(F.data == "ref_system")
async def ref_system_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await ensure_subscribed(callback.message, user_id, lang, callback):
        return
    ref_code = get_referral_code(user_id)
    if not ref_code:
        await callback.message.edit_text(TEXTS[lang]['no_ref_link'], reply_markup=back_menu())
        await callback.answer()
        return
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{ref_code}"
    refs, bonus_atk = get_referral_stats(user_id)
    vip_ref_status = "✅ Активен (VIP на 3 месяца)" if refs >= 100 else "❌ Не активен (нужно 100 рефералов)"
    text = TEXTS[lang]['ref_system'].format(
        link=link,
        count=refs,
        bonus_attacks=bonus_atk,
        vip_ref_status=vip_ref_status
    )
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
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{ref_code}"
    await callback.message.answer(f"📋 Ваша реферальная ссылка:\n\n`{link}`", parse_mode=ParseMode.MARKDOWN)
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    if not await check_subscription(user_id):
        await callback.message.edit_text(TEXTS[lang]['subscribe_prompt'].format(channel=REQUIRED_CHANNEL),
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                              [InlineKeyboardButton(text=TEXTS[lang]['check_sub'], callback_data="check_sub")]
                                          ]))
        await callback.answer()
        return
    await callback.message.edit_text(TEXTS[lang]['start'], reply_markup=main_menu(lang, user_id))
    await callback.answer()

# ===========================================
# АДМИН-КОМАНДЫ
# ===========================================

@dp.message(Command("admin"))
async def admin_command(message: aiogram_types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(TEXTS['ru']['no_access'])
        return
    await message.answer(TEXTS['ru']['admin_panel'], reply_markup=admin_menu())

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
    text = TEXTS['ru']['stats'].format(users=len(users), promos=len(promos), top=top)
    await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(TEXTS['ru']['broadcast_start'], reply_markup=back_menu())
    await state.set_state(BroadcastState.waiting_text)
    await callback.answer()

@dp.message(BroadcastState.waiting_text)
async def broadcast_text(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if message.text == "/cancel":
        await message.answer(TEXTS['ru']['broadcast_cancel'], reply_markup=admin_menu())
        await state.clear()
        return
    text = message.text
    users = get_all_user_ids()
    sent = 0
    status = await message.answer(TEXTS['ru']['broadcast_progress'].format(sent=0, total=len(users)))
    for i, uid in enumerate(users, 1):
        try:
            lang = get_user_language(uid)
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
            sent += 1
        except:
            pass
        if i % 10 == 0:
            await status.edit_text(TEXTS['ru']['broadcast_progress'].format(sent=sent, total=len(users)))
        await asyncio.sleep(0.05)
    await status.edit_text(TEXTS['ru']['broadcast_done'].format(sent=sent, total=len(users)), reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите код промокода:", reply_markup=back_menu())
    await state.set_state(CreatePromoState.waiting_code)
    await callback.answer()

@dp.message(CreatePromoState.waiting_code)
async def create_promo_code(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(code=message.text.strip())
    await message.answer("Выберите тип:\n1 - VIP\n2 - Атаки")
    await state.set_state(CreatePromoState.waiting_type)

@dp.message(CreatePromoState.waiting_type)
async def create_promo_type(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    typ = message.text.strip()
    if typ not in ['1', '2']:
        await message.answer("Введите 1 или 2")
        return
    promo_type = "vip" if typ == '1' else "attacks"
    await state.update_data(type=promo_type)
    await message.answer("Введите количество использований:")
    await state.set_state(CreatePromoState.waiting_uses)

@dp.message(CreatePromoState.waiting_uses)
async def create_promo_uses(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        uses = int(message.text.strip())
        if uses <= 0:
            raise ValueError
        await state.update_data(uses=uses)
        data = await state.get_data()
        if data['type'] == 'vip':
            await message.answer("Введите количество дней VIP:")
            await state.set_state(CreatePromoState.waiting_bonus)
        else:
            await message.answer("Введите количество атак:")
            await state.set_state(CreatePromoState.waiting_bonus)
    except:
        await message.answer("❌ Введите положительное число!")

@dp.message(CreatePromoState.waiting_bonus)
async def create_promo_bonus(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        bonus = int(message.text.strip())
        if bonus <= 0:
            raise ValueError
        await state.update_data(bonus=bonus)
        data = await state.get_data()
        code = data['code']
        uses = data['uses']
        promo_type = data['type']
        if promo_type == 'vip':
            create_promo(code, uses, bonus, 0, 'vip', ADMIN_ID)
            bonus_str = f"{bonus} дней"
        else:
            create_promo(code, uses, 0, bonus, 'attacks', ADMIN_ID)
            bonus_str = f"{bonus} атак"
        await message.answer(TEXTS['ru']['promo_created'].format(code=code, type=promo_type.capitalize(), uses=uses, bonus=bonus_str), reply_markup=admin_menu())
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
        text = TEXTS['ru']['promo_list_empty']
    else:
        lines = []
        for code, max_uses, used, typ, dur, bonus in promos:
            if typ == 'vip':
                bonus_str = f"{dur} дней VIP"
            else:
                bonus_str = f"{bonus} атак"
            lines.append(f"• {code} — {used}/{max_uses} использовано, {bonus_str}")
        text = TEXTS['ru']['promo_list'].format(list="\n".join(lines))
    await callback.message.edit_text(text, reply_markup=back_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_blacklist")
async def admin_blacklist_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    blacklist = get_blacklist()
    if blacklist:
        text = TEXTS['ru']['blacklist_list'].format(list="\n".join([f"• @{b}" for b in blacklist]))
    else:
        text = TEXTS['ru']['blacklist_empty']
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
    await callback.message.edit_text("Введите username цели:", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_add)
    await callback.answer()

@dp.callback_query(F.data == "admin_remove_blacklist")
async def admin_remove_blacklist_callback(callback: aiogram_types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("Введите username цели для удаления:", reply_markup=back_menu())
    await state.set_state(BlacklistState.waiting_remove)
    await callback.answer()

@dp.message(BlacklistState.waiting_add)
async def add_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target = message.text.replace('@', '').strip()
    if not target:
        await message.answer("❌ Неверный username")
        return
    if is_in_blacklist(target):
        await message.answer(TEXTS['ru']['blacklist_exists'])
    else:
        if add_to_blacklist(target, ADMIN_ID):
            await message.answer(TEXTS['ru']['blacklist_added'].format(target=target), reply_markup=admin_menu())
        else:
            await message.answer("❌ Ошибка добавления")
    await state.clear()

@dp.message(BlacklistState.waiting_remove)
async def remove_blacklist_handler(message: aiogram_types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    target = message.text.replace('@', '').strip()
    if not target:
        await message.answer("❌ Неверный username")
        return
    if remove_from_blacklist(target):
        await message.answer(TEXTS['ru']['blacklist_removed'].format(target=target), reply_markup=admin_menu())
    else:
        await message.answer(TEXTS['ru']['blacklist_not_found'])
    await state.clear()

@dp.callback_query(F.data == "admin_settings")
async def admin_settings_callback(callback: aiogram_types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    ad_text = get_setting('ad_text') or "Не настроена"
    broadcast_enabled = get_setting('broadcast_enabled') == '1'
    status = "Включена" if broadcast_enabled else "Отключена"
    text = TEXTS['ru']['admin_settings'].format(ad_text=ad_text, broadcast_status=status)
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
    await state.set_state(BroadcastState.waiting_text)  # используем существующее состояние, но можно создать отдельное
    await callback.answer()
    # переопределим поведение для админ-рекламы: сохраним в настройки

@dp.message(BroadcastState.waiting_text)
async def edit_ad_text(message: aiogram_types.Message, state: FSMContext):
    # Этот хендлер вызывается и для рассылки, и для рекламы.
    # Различим по контексту: если текущий обработчик не для рассылки, то сохраняем как рекламу.
    # У нас нет отдельного состояния, поэтому добавим проверку по тексту.
    # Если сообщение пришло после вызова admin_edit_ad – мы в том же состоянии, но мы не знаем, что это реклама.
    # Лучше создать отдельное состояние для рекламы, но упростим: при сохранении проверяем, что это не отмена.
    if message.from_user.id != ADMIN_ID:
        return
    if message.text == "/cancel":
        await message.answer("❌ Отменено", reply_markup=admin_menu())
        await state.clear()
        return
    # Проверим, что мы не в режиме рассылки (если рассылка инициирована, у нас есть флаг, но его нет)
    # Можно сделать так: если пользователь нажал "Изменить рекламу", мы сохраняем текст в настройки.
    # Но чтобы не путать с рассылкой, будем считать, что если предыдущая команда была рассылка – то это рассылка.
    # Проще: сделаем отдельное состояние для рекламы.
    # Но я не хочу переписывать весь код. Сделаем отдельный обработчик для рекламы с отдельным состоянием.
    # Просто оставлю как есть: пользователь вводит текст, мы проверяем, что мы в состоянии BroadcastState,
    # но если не задано ничего, то сохраняем как рекламу? Это плохо.
    # Лучше добавлю новое состояние AdState.

class AdState(StatesGroup):
    waiting_text = State()

@dp.callback_query(F.data == "admin_edit_ad")
async def admin_edit_ad_callback2(callback: aiogram_types.CallbackQuery, state: FSMContext):
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

# ===========================================
# АВТО-РАССЫЛКА (раз в неделю)
# ===========================================

async def weekly_broadcast():
    while True:
        try:
            if get_setting('broadcast_enabled') == '1':
                last = get_setting('last_weekly_broadcast')
                if last:
                    last_date = datetime.fromisoformat(last)
                    if datetime.now() - last_date >= timedelta(days=7):
                        # Отправляем рекламный текст
                        ad_text = get_setting('ad_text') or "Реклама"
                        users = get_all_user_ids()
                        for uid in users:
                            try:
                                lang = get_user_language(uid)
                                await bot.send_message(uid, TEXTS[lang]['ad_text'].format(text=ad_text))
                                await asyncio.sleep(0.1)  # небольшая задержка
                            except:
                                pass
                        set_setting('last_weekly_broadcast', datetime.now().isoformat())
                        print("✅ Авто-рассылка выполнена")
        except Exception as e:
            print(f"Ошибка авто-рассылки: {e}")
        await asyncio.sleep(3600)  # проверка каждый час

# ===========================================
# УВЕДОМЛЕНИЯ ОБ ОКОНЧАНИИ VIP
# ===========================================

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
                        await bot.send_message(user_id, TEXTS[lang]['vip_expire_warning'])
            conn.close()
        except Exception as e:
            print(f"VIP expiry check error: {e}")
        await asyncio.sleep(86400)

# ===========================================
# ЯЗЫКИ
# ===========================================

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
    await message.answer(TEXTS[lang]['lang_choose'], reply_markup=keyboard)

@dp.callback_query(F.data.startswith("lang_"))
async def lang_callback(callback: aiogram_types.CallbackQuery):
    user_id = callback.from_user.id
    new_lang = callback.data.split("_")[1]
    set_user_language(user_id, new_lang)
    await callback.message.edit_text(TEXTS[new_lang]['lang_changed'], reply_markup=main_menu(new_lang, user_id))
    await callback.answer()

# ===========================================
# ЗАПУСК
# ===========================================

async def main():
    init_db()
    asyncio.create_task(check_vip_expiry())
    if WEEKLY_BROADCAST_ENABLED:
        asyncio.create_task(weekly_broadcast())
    print("🔰 Бот запущен с новыми функциями (рейтинг, статистика, кастомизация, реклама, авто-рассылка, языки)")
    print(f"👑 Админ: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
