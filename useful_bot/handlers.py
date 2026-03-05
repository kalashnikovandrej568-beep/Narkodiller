"""
Обработчики команд бота «Полезный Помощник»
15+ функций для повседневной жизни россиянина
"""

import re
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    RATE_LIMIT,
    NOTE_ADD_STATE, NOTE_DELETE_STATE,
    REMINDER_TEXT_STATE, REMINDER_TIME_STATE,
    WEATHER_CITY_STATE, CALC_STATE,
    BMI_WEIGHT_STATE, BMI_HEIGHT_STATE,
    FUEL_DISTANCE_STATE, FUEL_CONSUMPTION_STATE, FUEL_PRICE_STATE,
    SHOPPING_ADD_STATE, SHOPPING_DEL_STATE,
    CONVERT_STATE, PASSWORD_LENGTH_STATE, TRANSLATE_STATE,
)
from database import (
    add_note, get_notes, delete_note, clear_notes,
    add_shopping_item, get_shopping_list, toggle_shopping_item,
    delete_shopping_item, clear_shopping, clear_checked_shopping,
    add_reminder, get_user_reminders, delete_reminder,
    track_usage, get_user_stats,
)
from services import (
    get_cbr_rates, format_currency_rates, convert_currency,
    get_weather, safe_calc, convert_units,
    generate_password, format_password,
    random_number, coin_flip, yes_or_no, random_choice,
    calc_bmi, calc_fuel, get_today_info, format_translit, text_stats,
    get_world_time,
)

logger = logging.getLogger(__name__)

# Rate limiting
user_requests = defaultdict(list)


def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < 60]
    if len(user_requests[user_id]) >= RATE_LIMIT:
        return False
    user_requests[user_id].append(now)
    return True


# ==================== КЛАВИАТУРЫ ====================

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Курсы валют", callback_data="cmd_currency"),
            InlineKeyboardButton("🌤 Погода", callback_data="cmd_weather"),
        ],
        [
            InlineKeyboardButton("🧮 Калькулятор", callback_data="cmd_calc"),
            InlineKeyboardButton("📏 Конвертер", callback_data="cmd_convert"),
        ],
        [
            InlineKeyboardButton("📝 Заметки", callback_data="cmd_notes"),
            InlineKeyboardButton("🛒 Покупки", callback_data="cmd_shopping"),
        ],
        [
            InlineKeyboardButton("⏰ Напоминания", callback_data="cmd_remind"),
            InlineKeyboardButton("🔐 Пароль", callback_data="cmd_password"),
        ],
        [
            InlineKeyboardButton("📅 Календарь", callback_data="cmd_today"),
            InlineKeyboardButton("🎲 Рандом", callback_data="cmd_random"),
        ],
        [
            InlineKeyboardButton("📊 ИМТ", callback_data="cmd_bmi"),
            InlineKeyboardButton("⛽ Бензин", callback_data="cmd_fuel"),
        ],
        [
            InlineKeyboardButton("🔄 Транслит", callback_data="cmd_translit"),
            InlineKeyboardButton("🌍 Мир. время", callback_data="cmd_worldtime"),
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="cmd_help"),
        ],
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="cmd_menu")]
    ])


def random_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 Число", callback_data="rnd_number"),
            InlineKeyboardButton("🪙 Монетка", callback_data="rnd_coin"),
        ],
        [
            InlineKeyboardButton("🎱 Да/Нет", callback_data="rnd_yesno"),
            InlineKeyboardButton("🏠 Меню", callback_data="cmd_menu"),
        ],
    ])


def notes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить", callback_data="note_add"),
            InlineKeyboardButton("📋 Список", callback_data="note_list"),
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data="note_del"),
            InlineKeyboardButton("🏠 Меню", callback_data="cmd_menu"),
        ],
    ])


def shopping_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Добавить", callback_data="shop_add"),
            InlineKeyboardButton("📋 Список", callback_data="shop_list"),
        ],
        [
            InlineKeyboardButton("✅ Купленные", callback_data="shop_clear_done"),
            InlineKeyboardButton("🗑 Очистить", callback_data="shop_clear_all"),
        ],
        [InlineKeyboardButton("🏠 Меню", callback_data="cmd_menu")],
    ])


# ==================== /start ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_usage(user.id)

    text = (
        f"👋 Привет, *{user.first_name}*!\n\n"
        f"🤖 Я — *Полезный Помощник*, бот с кучей функций на каждый день.\n\n"
        f"📋 *Что я умею:*\n\n"
        f"💰 Курсы валют ЦБ РФ (USD, EUR, CNY и ещё 30+)\n"
        f"🌤 Погода в любом городе + прогноз на 3 дня\n"
        f"🧮 Калькулятор (+ sin/cos/sqrt/log)\n"
        f"📏 Конвертер единиц (длина, вес, температура...)\n"
        f"📝 Заметки — сохраняйте мысли\n"
        f"🛒 Список покупок с отметками ✅\n"
        f"⏰ Напоминания — не забуду!\n"
        f"🔐 Генератор надёжных паролей\n"
        f"📅 Календарь — праздники РФ, день года\n"
        f"🎲 Рандом — число, монетка, да/нет, выбор\n"
        f"📊 Калькулятор ИМТ\n"
        f"⛽ Расчёт стоимости поездки\n"
        f"🔄 Транслитерация RU → EN\n"
        f"🌍 Мировое время\n"
        f"📝 Статистика текста\n\n"
        f"⬇️ Выберите функцию или введите /help"
    )

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())
    logger.info(f"User {user.id} ({user.username}) started bot")


# ==================== /help ====================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 *СПРАВКА — Полезный Помощник*\n\n"
        "*Команды:*\n\n"
        "💰 /currency — Курсы валют ЦБ РФ\n"
        "💱 /convert\\_currency `100 USD` — Конвертация валют\n"
        "🌤 /weather — Погода в городе\n"
        "🧮 /calc `2+2*2` — Калькулятор\n"
        "📏 /convert `100 км в мили` — Конвертер единиц\n"
        "📝 /notes — Заметки\n"
        "🛒 /shopping — Список покупок\n"
        "⏰ /remind — Напоминание\n"
        "🔐 /password — Генератор паролей\n"
        "📅 /today — Календарь, праздники\n"
        "🌍 /worldtime — Мировое время\n"
        "🎲 /random — Случайное число\n"
        "🪙 /coin — Монетка\n"
        "🎱 /yesno — Да или нет\n"
        "🎯 /choose `пицца, суши, бургер` — Случайный выбор\n"
        "📊 /bmi — Индекс массы тела\n"
        "⛽ /fuel — Стоимость поездки\n"
        "🔄 /translit `текст` — Транслитерация\n"
        "📝 /textstats — Статистика текста\n"
        "📈 /mystats — Ваша статистика\n\n"
        "🏠 /start — Главное меню\n"
        "🚫 /cancel — Отмена"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ==================== КНОПКИ ====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cmd_menu":
        await query.message.reply_text("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=main_keyboard())
        return ConversationHandler.END

    elif data == "cmd_currency":
        await query.message.reply_text("⏳ Загружаю курсы валют...")
        rates = await get_cbr_rates()
        text = format_currency_rates(rates)
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    elif data == "cmd_weather":
        await query.message.reply_text(
            "🌤 *Погода*\n\nВведите название города:\nПример: Москва, Казань, London",
            parse_mode="Markdown"
        )
        return WEATHER_CITY_STATE

    elif data == "cmd_calc":
        await query.message.reply_text(
            "🧮 *Калькулятор*\n\n"
            "Введите выражение:\n"
            "• `2+2*2`\n"
            "• `sqrt(144)`\n"
            "• `sin(3.14)`\n"
            "• `100/3`\n\n"
            "/cancel — отмена",
            parse_mode="Markdown"
        )
        return CALC_STATE

    elif data == "cmd_convert":
        await query.message.reply_text(
            "📏 *Конвертер единиц*\n\n"
            "Формат: `число единица в единицу`\n\n"
            "Примеры:\n"
            "• `100 км в мили`\n"
            "• `5 кг в фунт`\n"
            "• `30 C в F`\n"
            "• `1 гб в мб`\n\n"
            "/cancel — отмена",
            parse_mode="Markdown"
        )
        return CONVERT_STATE

    elif data == "cmd_notes":
        await query.message.reply_text("📝 *Заметки*\n\nВыберите действие:", parse_mode="Markdown", reply_markup=notes_keyboard())
        return ConversationHandler.END

    elif data == "cmd_shopping":
        await query.message.reply_text("🛒 *Список покупок*\n\nВыберите действие:", parse_mode="Markdown", reply_markup=shopping_keyboard())
        return ConversationHandler.END

    elif data == "cmd_remind":
        await query.message.reply_text(
            "⏰ *Напоминание*\n\nВведите текст напоминания:\n\n/cancel — отмена",
            parse_mode="Markdown"
        )
        return REMINDER_TEXT_STATE

    elif data == "cmd_password":
        await query.message.reply_text(
            "🔐 *Генератор паролей*\n\n"
            "Введите желаемую длину (4–128):\n"
            "Или нажмите /cancel\n\n"
            "По умолчанию: 16 символов",
            parse_mode="Markdown"
        )
        return PASSWORD_LENGTH_STATE

    elif data == "cmd_today":
        text = get_today_info()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    elif data == "cmd_random":
        await query.message.reply_text("🎲 *Рандом*\n\nВыберите:", parse_mode="Markdown", reply_markup=random_keyboard())
        return ConversationHandler.END

    elif data == "cmd_bmi":
        await query.message.reply_text(
            "📊 *Калькулятор ИМТ*\n\nВведите ваш вес (кг):\nПример: 75\n\n/cancel — отмена",
            parse_mode="Markdown"
        )
        return BMI_WEIGHT_STATE

    elif data == "cmd_fuel":
        await query.message.reply_text(
            "⛽ *Расчёт стоимости поездки*\n\n"
            "Введите расстояние (км):\nПример: 500\n\n/cancel — отмена",
            parse_mode="Markdown"
        )
        return FUEL_DISTANCE_STATE

    elif data == "cmd_translit":
        await query.message.reply_text(
            "🔄 *Транслитерация*\n\nВведите текст на русском:\n\n/cancel — отмена",
            parse_mode="Markdown"
        )
        return TRANSLATE_STATE

    elif data == "cmd_worldtime":
        text = get_world_time()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    elif data == "cmd_help":
        text = (
            "📚 *Краткая справка:*\n\n"
            "💰 /currency — Валюты\n"
            "🌤 /weather — Погода\n"
            "🧮 /calc — Калькулятор\n"
            "📏 /convert — Конвертер\n"
            "📝 /notes — Заметки\n"
            "🛒 /shopping — Покупки\n"
            "⏰ /remind — Напоминания\n"
            "🔐 /password — Пароль\n"
            "📅 /today — Календарь\n"
            "🎲 /random — Рандом\n"
            "📊 /bmi — ИМТ\n"
            "⛽ /fuel — Бензин\n"
            "🔄 /translit — Транслит\n"
            "🌍 /worldtime — Время\n\n"
            "Полная справка: /help"
        )
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    # ----- Рандом кнопки -----
    elif data == "rnd_number":
        text = random_number()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=random_keyboard())
        return ConversationHandler.END

    elif data == "rnd_coin":
        text = coin_flip()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=random_keyboard())
        return ConversationHandler.END

    elif data == "rnd_yesno":
        text = yes_or_no()
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=random_keyboard())
        return ConversationHandler.END

    # ----- Заметки кнопки -----
    elif data == "note_add":
        await query.message.reply_text("📝 Введите текст заметки:\n\n/cancel — отмена")
        return NOTE_ADD_STATE

    elif data == "note_list":
        await _show_notes(query.message, query.from_user.id)
        return ConversationHandler.END

    elif data == "note_del":
        notes = get_notes(query.from_user.id)
        if not notes:
            await query.message.reply_text("📝 У вас нет заметок.", reply_markup=notes_keyboard())
        else:
            text = "🗑 Введите *номер* заметки для удаления:\n\n"
            for i, (nid, ntxt, ndate) in enumerate(notes, 1):
                short = ntxt[:40] + ("..." if len(ntxt) > 40 else "")
                text += f"`{nid}`. {short}\n"
            text += "\n/cancel — отмена"
            await query.message.reply_text(text, parse_mode="Markdown")
            return NOTE_DELETE_STATE
        return ConversationHandler.END

    # ----- Покупки кнопки -----
    elif data == "shop_add":
        await query.message.reply_text(
            "🛒 Введите товар (или несколько через запятую):\n\n"
            "Пример: Молоко, Хлеб, Яйца\n\n/cancel — отмена"
        )
        return SHOPPING_ADD_STATE

    elif data == "shop_list":
        await _show_shopping(query.message, query.from_user.id)
        return ConversationHandler.END

    elif data == "shop_clear_done":
        count = clear_checked_shopping(query.from_user.id)
        await query.message.reply_text(
            f"✅ Удалено купленных: {count}", reply_markup=shopping_keyboard()
        )
        return ConversationHandler.END

    elif data == "shop_clear_all":
        count = clear_shopping(query.from_user.id)
        await query.message.reply_text(
            f"🗑 Список очищен (удалено: {count})", reply_markup=shopping_keyboard()
        )
        return ConversationHandler.END

    # Кнопки toggle/delete покупок
    elif data.startswith("shop_toggle_"):
        item_id = int(data.replace("shop_toggle_", ""))
        toggle_shopping_item(query.from_user.id, item_id)
        await _show_shopping(query.message, query.from_user.id, edit=True)
        return ConversationHandler.END

    elif data.startswith("shop_del_"):
        item_id = int(data.replace("shop_del_", ""))
        delete_shopping_item(query.from_user.id, item_id)
        await _show_shopping(query.message, query.from_user.id, edit=True)
        return ConversationHandler.END

    return ConversationHandler.END


# ==================== ПОГОДА ====================

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌤 *Погода*\n\nВведите город:\nПример: Москва\n\n/cancel — отмена",
        parse_mode="Markdown"
    )
    return WEATHER_CITY_STATE


async def weather_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    city = update.message.text.strip()
    track_usage(user.id)

    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ Слишком много запросов.")
        return ConversationHandler.END

    msg = await update.message.reply_text(f"🌤 Получаю погоду для *{city}*...", parse_mode="Markdown")
    text = await get_weather(city)

    try:
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    except Exception:
        await msg.edit_text(text, reply_markup=back_keyboard())

    return ConversationHandler.END


# ==================== ВАЛЮТЫ ====================

async def currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    msg = await update.message.reply_text("💰 Загружаю курсы валют...")
    rates = await get_cbr_rates()
    text = format_currency_rates(rates)
    try:
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    except Exception:
        await msg.edit_text(text, reply_markup=back_keyboard())


async def convert_currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертация валют: /convert_currency 100 USD"""
    track_usage(update.effective_user.id)
    args = context.args

    if not args or len(args) < 2:
        await update.message.reply_text(
            "💱 *Конвертация валют*\n\n"
            "Формат: `/convert_currency 100 USD`\n"
            "Или: `/convert_currency 100 USD EUR`\n\n"
            "По умолчанию конвертирует в RUB.",
            parse_mode="Markdown"
        )
        return

    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Введите число: `/convert_currency 100 USD`", parse_mode="Markdown")
        return

    from_code = args[1].upper()
    to_code = args[2].upper() if len(args) >= 3 else "RUB"

    msg = await update.message.reply_text("💱 Конвертирую...")
    rates = await get_cbr_rates()
    if not rates:
        await msg.edit_text("❌ Не удалось получить курсы.")
        return

    result = convert_currency(amount, from_code, to_code, rates)
    if result:
        await msg.edit_text(f"💱 *Конвертация:*\n\n{result}", parse_mode="Markdown", reply_markup=back_keyboard())
    else:
        await msg.edit_text(f"❌ Валюта `{from_code}` или `{to_code}` не найдена в ЦБ РФ.", parse_mode="Markdown")


# ==================== КАЛЬКУЛЯТОР ====================

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if context.args:
        expr = " ".join(context.args)
        result = safe_calc(expr)
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        "🧮 *Калькулятор*\n\nВведите выражение:\n`2+2`, `sqrt(144)`, `sin(3.14)`\n\n/cancel — отмена",
        parse_mode="Markdown"
    )
    return CALC_STATE


async def calc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    result = safe_calc(update.message.text)
    await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
    return ConversationHandler.END


# ==================== КОНВЕРТЕР ====================

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if context.args:
        expr = " ".join(context.args)
        result = convert_units(expr)
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        "📏 *Конвертер*\n\nФормат: `100 км в мили`\n\n/cancel — отмена",
        parse_mode="Markdown"
    )
    return CONVERT_STATE


async def convert_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    result = convert_units(update.message.text)
    await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
    return ConversationHandler.END


# ==================== ЗАМЕТКИ ====================

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    await update.message.reply_text("📝 *Заметки*", parse_mode="Markdown", reply_markup=notes_keyboard())


async def note_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    track_usage(user.id)

    if add_note(user.id, text):
        await update.message.reply_text(f"✅ Заметка сохранена!", reply_markup=notes_keyboard())
    else:
        await update.message.reply_text("❌ Лимит заметок достигнут. Удалите старые.", reply_markup=notes_keyboard())
    return ConversationHandler.END


async def note_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    track_usage(user.id)

    try:
        note_id = int(text)
        if delete_note(user.id, note_id):
            await update.message.reply_text("🗑 Заметка удалена!", reply_markup=notes_keyboard())
        else:
            await update.message.reply_text("❌ Заметка не найдена.", reply_markup=notes_keyboard())
    except ValueError:
        if text.lower() in ("все", "all", "clear"):
            count = clear_notes(user.id)
            await update.message.reply_text(f"🗑 Удалено заметок: {count}", reply_markup=notes_keyboard())
        else:
            await update.message.reply_text("❌ Введите номер заметки.", reply_markup=notes_keyboard())
    return ConversationHandler.END


async def _show_notes(message, user_id: int):
    notes = get_notes(user_id)
    if not notes:
        await message.reply_text("📝 У вас пока нет заметок.\nНажмите ➕ чтобы добавить.", reply_markup=notes_keyboard())
        return

    text = f"📝 *Ваши заметки ({len(notes)}):*\n\n"
    for nid, ntxt, ndate in notes:
        date_str = ndate[:10] if ndate else ""
        text += f"📌 `{nid}`. {ntxt}\n   _{date_str}_\n\n"

    await message.reply_text(text, parse_mode="Markdown", reply_markup=notes_keyboard())


# ==================== ПОКУПКИ ====================

async def shopping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    await update.message.reply_text("🛒 *Список покупок*", parse_mode="Markdown", reply_markup=shopping_keyboard())


async def shopping_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    track_usage(user.id)

    items = [i.strip() for i in text.split(",") if i.strip()]
    added = 0
    for item in items:
        if add_shopping_item(user.id, item):
            added += 1

    await update.message.reply_text(f"✅ Добавлено: {added} товар(ов)", reply_markup=shopping_keyboard())
    return ConversationHandler.END


async def _show_shopping(message, user_id: int, edit: bool = False):
    items = get_shopping_list(user_id)
    if not items:
        text = "🛒 Список покупок пуст.\nНажмите ➕ чтобы добавить."
        if edit:
            try:
                await message.edit_text(text, reply_markup=shopping_keyboard())
            except Exception:
                pass
        else:
            await message.reply_text(text, reply_markup=shopping_keyboard())
        return

    text = f"🛒 *Список покупок ({len(items)}):*\n\n"
    buttons = []

    for item_id, item_name, checked in items:
        icon = "✅" if checked else "⬜"
        strike = f"~{item_name}~" if checked else item_name
        text += f"{icon} {strike}\n"
        buttons.append([
            InlineKeyboardButton(
                f"{'☑' if checked else '⬜'} {item_name[:20]}",
                callback_data=f"shop_toggle_{item_id}"
            ),
            InlineKeyboardButton("🗑", callback_data=f"shop_del_{item_id}"),
        ])

    buttons.append([
        InlineKeyboardButton("➕ Добавить", callback_data="shop_add"),
        InlineKeyboardButton("🏠 Меню", callback_data="cmd_menu"),
    ])

    kb = InlineKeyboardMarkup(buttons)
    if edit:
        try:
            await message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


# ==================== НАПОМИНАНИЯ ====================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    # Показать активные напоминания
    reminders = get_user_reminders(update.effective_user.id)
    text = "⏰ *Напоминания*\n\n"
    if reminders:
        text += "*Активные:*\n"
        for rid, rtxt, rtime in reminders:
            text += f"  🔔 `{rid}`. {rtxt} — _{rtime}_\n"
        text += "\n"
    text += "Введите текст нового напоминания:\n/cancel — отмена"
    await update.message.reply_text(text, parse_mode="Markdown")
    return REMINDER_TEXT_STATE


async def reminder_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reminder_text"] = update.message.text.strip()
    await update.message.reply_text(
        "⏰ Через сколько напомнить?\n\n"
        "Формат:\n"
        "• `30м` — через 30 минут\n"
        "• `2ч` — через 2 часа\n"
        "• `1д` — через 1 день\n"
        "• `14:30` — в указанное время (сегодня)\n\n"
        "/cancel — отмена",
        parse_mode="Markdown"
    )
    return REMINDER_TIME_STATE


async def reminder_time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    time_text = update.message.text.strip().lower()
    reminder_text = context.user_data.get("reminder_text", "Напоминание")
    track_usage(user.id)

    now = datetime.now()
    remind_at = None

    # Парсинг: 30м, 2ч, 1д
    m = re.match(r'^(\d+)\s*([мmhчдd])', time_text)
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        if unit in ("м", "m"):
            remind_at = now + timedelta(minutes=val)
        elif unit in ("ч", "h"):
            remind_at = now + timedelta(hours=val)
        elif unit in ("д", "d"):
            remind_at = now + timedelta(days=val)

    # Парсинг: 14:30
    if not remind_at:
        tm = re.match(r'^(\d{1,2}):(\d{2})$', time_text)
        if tm:
            h, mi = int(tm.group(1)), int(tm.group(2))
            remind_at = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if remind_at <= now:
                remind_at += timedelta(days=1)

    if not remind_at:
        await update.message.reply_text(
            "❌ Не понял формат. Используйте: `30м`, `2ч`, `1д` или `14:30`",
            parse_mode="Markdown"
        )
        return REMINDER_TIME_STATE

    rid = add_reminder(user.id, update.effective_chat.id, reminder_text, remind_at)
    time_str = remind_at.strftime("%d.%m.%Y %H:%M")

    await update.message.reply_text(
        f"✅ Напоминание #{rid} установлено!\n\n"
        f"📝 {reminder_text}\n"
        f"⏰ {time_str}",
        reply_markup=back_keyboard()
    )
    return ConversationHandler.END


# ==================== ПАРОЛЬ ====================

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if context.args:
        try:
            length = int(context.args[0])
        except ValueError:
            length = 16
        pwd = generate_password(length)
        await update.message.reply_text(format_password(pwd), parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    await update.message.reply_text("🔐 Введите длину пароля (4–128):\nПо умолчанию: 16\n\n/cancel — отмена")
    return PASSWORD_LENGTH_STATE


async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    try:
        length = int(update.message.text.strip())
    except ValueError:
        length = 16

    pwd = generate_password(length)
    await update.message.reply_text(format_password(pwd), parse_mode="Markdown", reply_markup=back_keyboard())
    return ConversationHandler.END


# ==================== ИМТ ====================

async def bmi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    await update.message.reply_text("📊 Введите ваш вес (кг):\nПример: 75\n\n/cancel — отмена")
    return BMI_WEIGHT_STATE


async def bmi_weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip().replace(",", "."))
        context.user_data["bmi_weight"] = weight
        await update.message.reply_text("📏 Теперь введите рост (см):\nПример: 175")
        return BMI_HEIGHT_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число (например: 75)")
        return BMI_WEIGHT_STATE


async def bmi_height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    try:
        height = float(update.message.text.strip().replace(",", "."))
        weight = context.user_data.get("bmi_weight", 70)
        result = calc_bmi(weight, height)
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
    except ValueError:
        await update.message.reply_text("❌ Введите число (например: 175)")
        return BMI_HEIGHT_STATE
    return ConversationHandler.END


# ==================== БЕНЗИН ====================

async def fuel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    await update.message.reply_text("⛽ Введите расстояние (км):\nПример: 500\n\n/cancel — отмена")
    return FUEL_DISTANCE_STATE


async def fuel_distance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dist = float(update.message.text.strip().replace(",", "."))
        context.user_data["fuel_dist"] = dist
        await update.message.reply_text("🚗 Расход топлива (л/100км):\nПример: 8")
        return FUEL_CONSUMPTION_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число.")
        return FUEL_DISTANCE_STATE


async def fuel_consumption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cons = float(update.message.text.strip().replace(",", "."))
        context.user_data["fuel_cons"] = cons
        await update.message.reply_text("💰 Цена топлива (₽/л):\nПример: 54.5")
        return FUEL_PRICE_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число.")
        return FUEL_CONSUMPTION_STATE


async def fuel_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    try:
        price = float(update.message.text.strip().replace(",", "."))
        dist = context.user_data.get("fuel_dist", 100)
        cons = context.user_data.get("fuel_cons", 8)
        result = calc_fuel(dist, cons, price)
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
    except ValueError:
        await update.message.reply_text("❌ Введите число.")
        return FUEL_PRICE_STATE
    return ConversationHandler.END


# ==================== ТРАНСЛИТ ====================

async def translit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if context.args:
        text = " ".join(context.args)
        result = format_translit(text)
        await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
        return ConversationHandler.END

    await update.message.reply_text("🔄 Введите текст для транслитерации:\n\n/cancel — отмена")
    return TRANSLATE_STATE


async def translit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    result = format_translit(update.message.text)
    await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())
    return ConversationHandler.END


# ==================== РАНДОМ ====================

async def random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if context.args:
        try:
            parts = context.args
            if len(parts) == 2:
                text = random_number(int(parts[0]), int(parts[1]))
            else:
                text = random_number(1, int(parts[0]))
            await update.message.reply_text(text, parse_mode="Markdown")
            return
        except ValueError:
            pass
    text = random_number()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=random_keyboard())


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    await update.message.reply_text(coin_flip(), parse_mode="Markdown", reply_markup=random_keyboard())


async def yesno_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    await update.message.reply_text(yes_or_no(), parse_mode="Markdown", reply_markup=random_keyboard())


async def choose_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if not context.args:
        await update.message.reply_text(
            "🎯 *Случайный выбор*\n\nФормат: `/choose пицца, суши, бургер`",
            parse_mode="Markdown"
        )
        return
    items = " ".join(context.args).split(",")
    items = [i.strip() for i in items if i.strip()]
    result = random_choice(items)
    await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())


# ==================== ПРОЧЕЕ ====================

async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    text = get_today_info()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def worldtime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    text = get_world_time()
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def textstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_usage(update.effective_user.id)
    if not context.args:
        await update.message.reply_text(
            "📝 *Статистика текста*\n\nОтправьте текст после команды:\n`/textstats ваш текст`",
            parse_mode="Markdown"
        )
        return
    text = " ".join(context.args)
    result = text_stats(text)
    await update.message.reply_text(result, parse_mode="Markdown", reply_markup=back_keyboard())


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)
    text = (
        f"📈 *Ваша статистика:*\n\n"
        f"👤 {user.first_name}\n"
        f"🔢 Команд использовано: {stats['commands']}\n"
        f"📅 Первое использование: {stats['first_use'] or 'N/A'}\n"
        f"🕐 Последнее: {stats['last_use'] or 'N/A'}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


# ==================== ОТМЕНА ====================

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Отменено.", reply_markup=main_keyboard())
    return ConversationHandler.END
