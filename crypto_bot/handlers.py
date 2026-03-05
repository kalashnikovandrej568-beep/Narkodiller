"""
Обработчики команд и сообщений крипто-бота
"""

import random
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from config import (
    CRYPTO_LIST, STOCKS_LIST,
    ALERT_CURRENCY_STATE, ALERT_CRYPTO_STATE,
    ALERT_DIRECTION_STATE, ALERT_PRICE_STATE,
    DELETE_ALERT_STATE,
    TRACKER_ADD_CRYPTO_STATE, TRACKER_SET_THRESHOLD_STATE,
    TRACKER_REMOVE_CRYPTO_STATE,
    CONVERTER_FROM_STATE, CONVERTER_TO_STATE, CONVERTER_AMOUNT_STATE,
    COMPARE_FIRST_STATE, COMPARE_SECOND_STATE,
    CALC_CURRENCY_STATE, CALC_CRYPTO_STATE, CALC_BUY_PRICE_STATE, CALC_AMOUNT_STATE,
    QUIZ_TYPE_STATE, QUIZ_ANSWER_STATE, QUIZ_PRICE_ANSWER_STATE, QUIZ_DIFFICULTY_STATE,
    PROMO_CODE_STATE,
    PORTFOLIO_ACTION_STATE, PORTFOLIO_ASSET_STATE, PORTFOLIO_AMOUNT_STATE,
    PREDICTION_ASSET_STATE,
    ASSET_ANALYSIS_STATE, ASSET_ANALYSIS_MODE_STATE,
    TIME_MACHINE_ASSET_STATE, TIME_MACHINE_AMOUNT_STATE, TIME_MACHINE_DAYS_STATE,
    AUTHOR_PASSWORD_STATE,
    THRESHOLD_OPTIONS, TRACKER_COOLDOWN,
    FREE_CRYPTOS, PRO_CRYPTOS, FREE_STOCKS, PRO_STOCKS, PROMO_CODES
)
from telegram.ext import ConversationHandler
from database import Database
from crypto_api import (
    get_crypto_price, get_all_prices, fetch_prices,
    format_price, format_change, format_volume,
    fetch_crypto_history
)
import stocks_api

db = Database()


# ==================== РЕЖИМ АКТИВА (КРИПТА / АКЦИИ) ====================

def get_mode(context):
    """Получить текущий режим: 'crypto' или 'stocks'"""
    return context.user_data.get('asset_mode', 'crypto')


def get_asset_list(mode):
    """Получить список активов для текущего режима"""
    return STOCKS_LIST if mode == 'stocks' else CRYPTO_LIST


def get_allowed_assets(user_id, mode):
    """Получить разрешённые тикеры по подписке и режиму"""
    tier = get_user_tier(user_id)
    if mode == 'stocks':
        if tier == 'premium': return list(STOCKS_LIST.keys())
        elif tier == 'pro': return PRO_STOCKS
        return FREE_STOCKS
    else:
        if tier == 'premium': return list(CRYPTO_LIST.keys())
        elif tier == 'pro': return PRO_CRYPTOS
        return FREE_CRYPTOS


def asset_label(mode):
    """'Акции' / 'Криптовалюты'"""
    return 'Акции' if mode == 'stocks' else 'Криптовалюты'


def asset_label_gen(mode):
    """'акций' / 'криптовалют'"""
    return 'акций' if mode == 'stocks' else 'криптовалют'


def asset_word(mode):
    """'акцию' / 'криптовалюту'"""
    return 'акцию' if mode == 'stocks' else 'криптовалюту'


def asset_word_short(mode):
    """'акций' / 'крипт'"""
    return 'акций' if mode == 'stocks' else 'крипт'


def asset_source(mode):
    """'Yahoo Finance' / 'CoinGecko'"""
    return 'Yahoo Finance' if mode == 'stocks' else 'CoinGecko'


async def get_asset_price(ticker, mode, vs_currency='usd'):
    """Получить цену актива (крипта или акция)"""
    if mode == 'stocks':
        return await stocks_api.get_stock_price(ticker, vs_currency)
    return await get_crypto_price(ticker, vs_currency)


async def get_all_asset_prices(mode, vs_currency='usd'):
    """Получить {тикер: цена} для всех активов режима"""
    if mode == 'stocks':
        return await stocks_api.get_all_prices(vs_currency)
    return await get_all_prices(vs_currency)


async def fetch_asset_prices(mode, vs_currency='usd'):
    """Получить сырые данные цен для режима"""
    if mode == 'stocks':
        return await stocks_api.fetch_prices(vs_currency)
    return await fetch_prices(vs_currency)


def get_back_keyboard(context):
    """Вернуть клавиатуру: актив-меню если в режиме, иначе главное"""
    mode = context.user_data.get('asset_mode')
    return get_asset_keyboard() if mode else get_main_keyboard()


def _extract_ticker(text, asset_list):
    """Извлечь тикер из текста кнопки (формат '🟠 BTC' или 'BTC')"""
    for t in asset_list:
        emoji = asset_list[t]['emoji']
        if text == f"{emoji} {t}" or text.upper().strip() == t:
            return t
    return None


# ==================== ПОДПИСКА: УТИЛИТЫ ====================

def get_user_tier(user_id):
    """Получить текущий тир подписки"""
    return db.get_active_tier(user_id)


def get_allowed_cryptos(user_id):
    """Список доступных тикеров по подписке"""
    tier = get_user_tier(user_id)
    if tier == 'premium':
        return list(CRYPTO_LIST.keys())
    elif tier == 'pro':
        return PRO_CRYPTOS
    else:
        return FREE_CRYPTOS


def tier_label(tier):
    """Красивое имя тира"""
    labels = {'free': '🆓 Free', 'pro': '⭐ Pro', 'premium': '👑 Premium'}
    return labels.get(tier, tier)


async def sub_blocked(update, feature_name, required_tier='pro'):
    """Отправить сообщение о блокировке функции"""
    tier_emoji = '⭐ Pro' if required_tier == 'pro' else '👑 Premium'
    await update.message.reply_text(
        f"🔒 ФУНКЦИЯ НЕДОСТУПНА\n"
        f"{'━' * 28}\n\n"
        f"Функция «{feature_name}» доступна\n"
        f"только для подписки {tier_emoji}!\n\n"
        f"Как получить подписку:\n"
        f"🧠 Пройди викторину (средний/сложный)\n"
        f"🎟 Активируй промокод\n\n"
        f"Нажми 🔧 Ещё → 🎟 Промокод\n"
        f"или 🧠 Крипто-викторина",
        reply_markup=get_main_keyboard()
    )


# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    """Главное меню — выбор раздела"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📈 Криптовалюты"), KeyboardButton("📊 Акции")],
        [KeyboardButton("🧠 Викторина"), KeyboardButton("👤 Подписка")],
        [KeyboardButton("🎟 Промокод")]
    ], resize_keyboard=True)


def get_asset_keyboard():
    """Меню раздела (крипта или акции)"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Курсы"), KeyboardButton("🔔 Алерты")],
        [KeyboardButton("📡 Трекер"), KeyboardButton("🤖 Сигналы")],
        [KeyboardButton("🔄 Конвертер"), KeyboardButton("⚖️ Сравнение")],
        [KeyboardButton("🧮 Калькулятор"), KeyboardButton("🏆 Рейтинг")],
        [KeyboardButton("⭐ Избранное"), KeyboardButton("🔧 Ещё")],
        [KeyboardButton("↩️ Главное меню")]
    ], resize_keyboard=True)


def get_currency_keyboard():
    """Выбор валюты (USD / RUB)"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💵 Доллар (USDT)"), KeyboardButton("₽ Рубль (RUB)")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_crypto_keyboard(allowed_tickers=None, mode='crypto'):
    """Список активов кнопками (3 в ряд), фильтр по подписке"""
    asset_list = get_asset_list(mode)
    tickers = allowed_tickers if allowed_tickers else list(asset_list.keys())
    tickers = sorted(tickers, key=lambda t: asset_list[t]['name'] if t in asset_list else t)
    buttons = []
    row = []
    for ticker in tickers:
        if ticker not in asset_list:
            continue
        emoji = asset_list[ticker]['emoji']
        row.append(KeyboardButton(f"{emoji} {ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("↩️ Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_crypto_keyboard_plain(mode='crypto'):
    """Список активов без эмодзи (для алертов/конвертера)"""
    asset_list = get_asset_list(mode)
    tickers = sorted(asset_list.keys(), key=lambda t: asset_list[t]['name'])
    buttons = []
    row = []
    for ticker in tickers:
        row.append(KeyboardButton(ticker))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_alerts_keyboard():
    """Меню алертов"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Создать алерт")],
        [KeyboardButton("📋 Мои алерты")],
        [KeyboardButton("❌ Удалить алерт"), KeyboardButton("🗑 Удалить все")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_tracker_keyboard():
    """Меню трекера"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить крипту"), KeyboardButton("➖ Убрать крипту")],
        [KeyboardButton("📋 Мой трекер"), KeyboardButton("⚙️ Порог оповещения")],
        [KeyboardButton("📊 Топ движения"), KeyboardButton("🌡️ Пульс рынка")],
        [KeyboardButton("🗑 Очистить трекер")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_threshold_keyboard():
    """Кнопки выбора порога (%)"""
    buttons = []
    row = []
    for t in THRESHOLD_OPTIONS:
        row.append(KeyboardButton(f"{t}%"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# ==================== КОМАНДА /start ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name)
    tier = get_user_tier(user.id)
    context.user_data.pop('asset_mode', None)

    await update.message.reply_text(
        f"📈 КРИПТО & АКЦИИ БОТ\n"
        f"{'═' * 28}\n\n"
        f"👋 Привет, {user.first_name}!\n"
        f"Статус: {tier_label(tier)}\n\n"
        f"📈 Криптовалюты — 50 крипт\n"
        f"📊 Акции — 50 акций\n\n"
        f"В каждом разделе:\n"
        f"💰 Курсы • 🔔 Алерты • 📡 Трекер\n"
        f"🤖 Сигналы • 🔄 Конвертер • ⚖️ Сравнение\n"
        f"🧮 Калькулятор • 🏆 Рейтинг • ⭐ Избранное\n"
        f"📰 Дайджест • 🎰 Рулетка • 📈 Мини-график\n\n"
        f"🧠 Викторина — проверь знания\n"
        f"👤 Подписка — статус и промокоды\n\n"
        f"Выбери раздел:",
        reply_markup=get_main_keyboard()
    )
    return -1


async def show_asset_menu(update, context, mode):
    """Показать меню раздела (крипта или акции)"""
    context.user_data['asset_mode'] = mode
    label = asset_label(mode)
    al = get_asset_list(mode)
    icon = '📈' if mode == 'crypto' else '📊'
    source = asset_source(mode)

    await update.message.reply_text(
        f"{icon} {label.upper()}\n"
        f"{'═' * 28}\n\n"
        f"📝 Всего: {len(al)} {asset_label_gen(mode)}\n"
        f"📁 Источник: {source}\n\n"
        f"Выберите функцию:",
        reply_markup=get_asset_keyboard()
    )


# ==================== КУРСЫ ====================

async def show_rates_menu(update, context):
    """Показать выбор валюты для любого раздела"""
    mode = get_mode(context)
    label = asset_label(mode)
    await update.message.reply_text(
        f"💰 КУРСЫ {label.upper()}\n"
        f"{'═' * 28}\n\n"
        f"Выберите валюту отображения:\n\n"
        f"💵 Доллар (USD) — цены в $\n"
        f"₽ Рубль (RUB) — цены в ₽",
        reply_markup=get_currency_keyboard()
    )


async def show_crypto_list(update, context, currency):
    """Показать список активов после выбора валюты"""
    context.user_data['rate_currency'] = currency
    mode = get_mode(context)
    al = get_asset_list(mode)
    curr_label = "💵 USD" if currency == 'usd' else "₽ RUB"
    user_id = update.effective_user.id
    allowed = get_allowed_assets(user_id, mode)
    tier = get_user_tier(user_id)

    lock_info = ""
    if tier == 'free':
        lock_info = f"\n🔒 Доступно {len(allowed)} из {len(al)} {asset_word_short(mode)} (Free)\n"
    elif tier == 'pro':
        lock_info = f"\n🔓 Доступно {len(allowed)} из {len(al)} {asset_word_short(mode)} (Pro)\n"

    await update.message.reply_text(
        f"💰 КУРСЫ В {curr_label}\n"
        f"{'═' * 28}\n{lock_info}\n"
        f"Нажмите на {asset_word(mode)}\n"
        f"чтобы увидеть текущий курс:",
        reply_markup=get_crypto_keyboard(allowed, mode)
    )


async def show_crypto_price(update, context, ticker):
    """Получить и показать цену конкретного актива"""
    mode = get_mode(context)
    user_id = update.effective_user.id
    allowed = get_allowed_assets(user_id, mode)
    if ticker not in allowed:
        await update.message.reply_text(
            f"🔒 {ticker} недоступен на вашем тарифе!\n\n"
            f"Доступно: {', '.join(allowed)}\n\n"
            f"Улучшите подписку для доступа ко всем.",
            reply_markup=get_asset_keyboard()
        )
        return

    currency = context.user_data.get('rate_currency', 'usd')

    msg = await update.message.reply_text(f"⏳ Загрузка {ticker}...")

    data = await get_asset_price(ticker, mode, currency)

    if not data or data.get('price') is None:
        try:
            await msg.edit_text(
                f"❌ Не удалось получить цену {ticker}\n\n"
                f"Попробуйте позже."
            )
        except Exception:
            await update.message.reply_text(f"❌ Не удалось получить цену {ticker}")
        return

    price = data['price']
    change = data.get('change_24h', 0)
    volume = data.get('volume', 0)
    market_cap = data.get('market_cap', 0)
    emoji = data.get('emoji', '🪙')

    price_str = format_price(price, currency)
    change_str = format_change(change)
    vol_str = format_volume(volume, currency)
    cap_str = format_volume(market_cap, currency)

    # Визуальный индикатор тренда
    if change and change > 5:
        trend = "🚀 Сильный рост!"
    elif change and change > 2:
        trend = "📈 Рост"
    elif change and change > 0:
        trend = "📈 Лёгкий рост"
    elif change and change > -2:
        trend = "📉 Лёгкое падение"
    elif change and change > -5:
        trend = "📉 Падение"
    else:
        trend = "💥 Сильное падение!" if change and change < -5 else "➡️ Стабильно"

    try:
        await msg.edit_text(
            f"{emoji} {data['name']} ({ticker})\n"
            f"{'━' * 28}\n\n"
            f"💰 Цена: {price_str}\n"
            f"{change_str}\n"
            f"📊 Тренд: {trend}\n\n"
            f"📈 Объём 24ч: {vol_str}\n"
            f"💎 Капитализация: {cap_str}\n\n"
            f"🕐 Данные {asset_source(mode)}"
        )
    except Exception:
        await update.message.reply_text(
            f"{emoji} {data['name']} ({ticker})\n"
            f"💰 Цена: {price_str} | {change_str}"
        )


# ==================== АЛЕРТЫ: МЕНЮ ====================

async def show_alerts_menu(update, context):
    """Показать меню алертов"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.count_user_active_alerts(user_id, mode)

    await update.message.reply_text(
        f"🔔 АЛЕРТЫ\n"
        f"{'═' * 28}\n\n"
        f"📬 Активных алертов: {count}\n\n"
        f"➕ Создать — новый алерт на цену\n"
        f"📋 Мои алерты — список активных\n"
        f"❌ Удалить — удалить один\n"
        f"🗑 Удалить все — очистить все\n\n"
        f"💡 Алерт сработает автоматически\n"
        f"и вам придёт уведомление!",
        reply_markup=get_alerts_keyboard()
    )


async def show_my_alerts(update, context):
    """Показать список алертов пользователя"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    alerts = db.get_user_alerts(user_id, mode)

    if not alerts:
        await update.message.reply_text(
            "📋 У вас нет активных алертов.\n\n"
            "➕ Создайте новый!",
            reply_markup=get_alerts_keyboard()
        )
        return

    text = f"📋 ВАШИ АЛЕРТЫ ({len(alerts)})\n{'━' * 28}\n\n"

    for alert in alerts:
        alert_id = alert[0]
        ticker = alert[2]
        target = alert[3]
        currency = alert[4]
        direction = alert[5]

        curr_sym = '$' if currency == 'usd' else '₽'
        dir_emoji = "⬆️" if direction == 'above' else "⬇️"
        dir_word = "выше" if direction == 'above' else "ниже"
        emoji = asset_list.get(ticker, {}).get('emoji', '🪙')

        price_str = format_price(target, currency)

        text += f"#{alert_id} {emoji} {ticker} — {dir_emoji} {dir_word} {price_str}\n"

    text += f"\n🔔 Алерты проверяются каждую минуту"

    await update.message.reply_text(text, reply_markup=get_alerts_keyboard())


async def delete_all_alerts(update, context):
    """Удалить все активные алерты"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.delete_all_user_alerts(user_id, mode)

    if count > 0:
        await update.message.reply_text(
            f"🗑 Удалено алертов: {count}\n\n"
            f"Все алерты очищены!",
            reply_markup=get_alerts_keyboard()
        )
    else:
        await update.message.reply_text(
            "📋 У вас нет активных алертов!",
            reply_markup=get_alerts_keyboard()
        )


# ==================== АЛЕРТЫ: СОЗДАНИЕ (ConversationHandler) ====================

async def create_alert_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 1: выбор валюты для алерта"""
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    if tier == 'free':
        await sub_blocked(update, "Создание алертов", "pro")
        return -1

    mode = get_mode(context)

    keyboard = [
        [KeyboardButton("💵 USD"), KeyboardButton("₽ RUB")],
        [KeyboardButton("Отмена")]
    ]
    await update.message.reply_text(
        "🔔 СОЗДАНИЕ АЛЕРТА\n"
        f"{'═' * 28}\n\n"
        "Шаг 1/4: В какой валюте\n"
        "отслеживать цену?\n\n"
        "💵 USD — доллары\n"
        "₽ RUB — рубли",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ALERT_CURRENCY_STATE


async def alert_choose_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 2: выбор криптовалюты"""
    text = update.message.text

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    if "USD" in text:
        context.user_data['alert_currency'] = 'usd'
    elif "RUB" in text:
        context.user_data['alert_currency'] = 'rub'
    else:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return ALERT_CURRENCY_STATE

    mode = get_mode(context)
    currency = context.user_data['alert_currency']
    label = "💵 USD" if currency == 'usd' else "₽ RUB"

    await update.message.reply_text(
        f"🔔 Алерт в {label}\n\n"
        f"Шаг 2/4: Выберите {asset_word(mode)}:",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return ALERT_CRYPTO_STATE


async def alert_choose_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: ввод целевой цены"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text not in asset_list:
        await update.message.reply_text(f"❌ Выберите {asset_word(mode)} кнопкой!")
        return ALERT_CRYPTO_STATE

    context.user_data['alert_crypto'] = text

    # Загрузить текущую цену для справки
    currency = context.user_data['alert_currency']
    data = await get_asset_price(text, mode, currency)
    curr_sym = '$' if currency == 'usd' else '₽'

    price_line = ""
    if data and data.get('price') is not None:
        price_str = format_price(data['price'], currency)
        change_str = format_change(data.get('change_24h', 0))
        price_line = (
            f"\n💰 Текущая цена: {price_str}\n"
            f"{change_str}\n"
        )

    emoji = asset_list[text]['emoji']
    keyboard = [[KeyboardButton("Отмена")]]

    await update.message.reply_text(
        f"🔔 Алерт на {emoji} {text}\n"
        f"{'━' * 28}\n"
        f"{price_line}\n"
        f"Шаг 3/4: Введите целевую цену в {curr_sym}:\n\n"
        f"Примеры: 100000, 50.5, 0.001",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ALERT_PRICE_STATE


async def alert_set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 4: выбор направления после ввода цены"""
    text = update.message.text

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    try:
        target_price = float(text.replace(',', '.').replace(' ', ''))
        if target_price <= 0:
            await update.message.reply_text("❌ Цена должна быть > 0!")
            return ALERT_PRICE_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число! Например: 100000 или 0.5")
        return ALERT_PRICE_STATE

    context.user_data['alert_price'] = target_price

    currency = context.user_data['alert_currency']
    crypto = context.user_data['alert_crypto']
    mode = get_mode(context)
    price_str = format_price(target_price, currency)
    emoji = get_asset_list(mode).get(crypto, {}).get('emoji', '🪙')

    keyboard = [
        [KeyboardButton("⬆️ Выше (цена вырастет)")],
        [KeyboardButton("⬇️ Ниже (цена упадёт)")],
        [KeyboardButton("Отмена")]
    ]

    await update.message.reply_text(
        f"🔔 Алерт на {emoji} {crypto}\n"
        f"{'━' * 28}\n\n"
        f"🎯 Целевая цена: {price_str}\n\n"
        f"Шаг 4/4: Уведомить когда цена:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return ALERT_DIRECTION_STATE


async def alert_choose_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финал: сохранение алерта после выбора направления"""
    text = update.message.text

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    if "Выше" in text:
        direction = 'above'
    elif "Ниже" in text:
        direction = 'below'
    else:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return ALERT_DIRECTION_STATE

    user_id = update.effective_user.id
    crypto = context.user_data['alert_crypto']
    currency = context.user_data['alert_currency']
    target_price = context.user_data['alert_price']

    alert_id = db.create_alert(user_id, crypto, target_price, currency, direction, get_mode(context))

    price_str = format_price(target_price, currency)
    mode = get_mode(context)
    emoji = get_asset_list(mode).get(crypto, {}).get('emoji', '🪙')
    dir_emoji = "⬆️ выше" if direction == 'above' else "⬇️ ниже"

    await update.message.reply_text(
        f"✅ АЛЕРТ СОЗДАН!\n"
        f"{'━' * 28}\n\n"
        f"{emoji} {crypto}\n"
        f"🎯 Цена: {dir_emoji} {price_str}\n"
        f"🆔 ID: #{alert_id}\n\n"
        f"🔔 Вы получите уведомление когда\n"
        f"цена {crypto} станет {dir_emoji} {price_str}\n\n"
        f"⏰ Проверка каждую минуту",
        reply_markup=get_back_keyboard(context)
    )
    return -1


# ==================== АЛЕРТЫ: УДАЛЕНИЕ (ConversationHandler) ====================

async def delete_alert_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления алерта — показать список"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    alerts = db.get_user_alerts(user_id, mode)

    if not alerts:
        await update.message.reply_text(
            "📋 Нет активных алертов для удаления!",
            reply_markup=get_alerts_keyboard()
        )
        return -1

    text = "❌ УДАЛЕНИЕ АЛЕРТА\n"
    text += f"{'━' * 28}\n\n"

    buttons = []
    row = []

    for alert in alerts:
        alert_id = alert[0]
        ticker = alert[2]
        target = alert[3]
        currency = alert[4]
        direction = alert[5]

        curr_sym = '$' if currency == 'usd' else '₽'
        dir_emoji = "⬆️" if direction == 'above' else "⬇️"
        price_str = format_price(target, currency)

        text += f"#{alert_id} | {ticker} {dir_emoji} {price_str}\n"
        row.append(KeyboardButton(f"#{alert_id}"))
        if len(row) == 4:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])

    text += "\nНажмите номер алерта для удаления:"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return DELETE_ALERT_STATE


async def delete_alert_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение удаления алерта"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_alerts_keyboard())
        return -1

    try:
        alert_id = int(text.replace('#', ''))
    except ValueError:
        await update.message.reply_text("❌ Нажмите кнопку с номером алерта!")
        return DELETE_ALERT_STATE

    user_id = update.effective_user.id
    success = db.delete_alert(alert_id, user_id)

    if success:
        await update.message.reply_text(
            f"✅ Алерт #{alert_id} удалён!",
            reply_markup=get_alerts_keyboard()
        )
    else:
        await update.message.reply_text(
            f"❌ Алерт #{alert_id} не найден!",
            reply_markup=get_alerts_keyboard()
        )
    return -1


# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Маршрутизатор текстовых сообщений"""
    text = update.message.text
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    mode = get_mode(context)

    # === ГЛАВНОЕ МЕНЮ ===
    if text == "📈 Криптовалюты":
        await show_asset_menu(update, context, 'crypto')
    elif text == "📊 Акции":
        await show_asset_menu(update, context, 'stocks')
    elif text == "🧠 Викторина":
        await show_crypto_quiz(update, context)
    elif text == "👤 Подписка":
        await show_subscription_info(update, context)
    elif text == "🎟 Промокод":
        await promo_start(update, context)

    # === ПАНЕЛЬ АВТОРА ===
    elif text == "📊 Статистика бота" and db.is_author(user_id):
        await author_show_stats(update, context)
    elif text == "👥 Все пользователи" and db.is_author(user_id):
        await author_show_users(update, context)
    elif text == "🎁 Выдать Premium" and db.is_author(user_id):
        await author_grant_premium_start(update, context)
    elif text == "📢 Рассылка" and db.is_author(user_id):
        await author_broadcast_start(update, context)
    elif text == "🗄 База данных" and db.is_author(user_id):
        await author_show_db_info(update, context)
    elif text == "🔄 Сброс подписок" and db.is_author(user_id):
        await author_reset_subs(update, context)
    elif text == "↩️ Выйти из панели" and db.is_author(user_id):
        context.user_data.pop('in_author_mode', None)
        context.user_data.pop('author_action', None)
        await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())

    # === НАВИГАЦИЯ ===
    elif text == "↩️ Главное меню":
        context.user_data.pop('asset_mode', None)
        await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())
    elif text == "↩️ Назад":
        if mode in ('crypto', 'stocks'):
            await show_asset_menu(update, context, mode)
        else:
            await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())

    # === МЕНЮ РАЗДЕЛА (КРИПТА / АКЦИИ) ===
    elif text == "💰 Курсы":
        await show_rates_menu(update, context)
    elif text == "🔔 Алерты":
        if tier == 'free':
            await sub_blocked(update, "Алерты", "pro")
        else:
            await show_alerts_menu(update, context)
    elif text == "📡 Трекер":
        if tier == 'free':
            await sub_blocked(update, "Трекер", "pro")
        else:
            await show_tracker_menu(update, context)
    elif text == "🤖 Сигналы":
        if tier != 'premium':
            await sub_blocked(update, "Сигналы", "premium")
        else:
            await show_signals(update, context)
    elif text == "💰 Портфель дня":
        if tier != 'premium':
            await sub_blocked(update, "Портфель дня", "premium")
        else:
            await show_portfolio_of_day(update, context)
    elif text == "🤖 Все сигналы":
        if tier != 'premium':
            await sub_blocked(update, "Все сигналы", "premium")
        else:
            await show_all_signals(update, context)
    elif text == "🔄 Конвертер":
        await show_converter_menu(update, context)
    elif text == "⚖️ Сравнение":
        await show_compare_menu(update, context)
    elif text == "🧮 Калькулятор":
        if tier == 'free':
            await sub_blocked(update, "Калькулятор", "pro")
        else:
            await show_calculator_menu(update, context)
    elif text == "🏆 Рейтинг":
        if tier == 'free':
            await sub_blocked(update, "Рейтинг", "pro")
        else:
            await show_rankings_menu(update, context)
    elif text == "⭐ Избранное":
        await show_favorites_menu(update, context)
    elif text == "🔧 Ещё":
        await show_extra_menu(update, context)

    # === Курсы: выбор валюты ===
    elif text == "💵 Доллар (USDT)":
        await show_crypto_list(update, context, 'usd')
    elif text == "₽ Рубль (RUB)":
        await show_crypto_list(update, context, 'rub')

    # === Алерты: подменю ===
    elif text == "📋 Мои алерты":
        await show_my_alerts(update, context)
    elif text == "🗑 Удалить все":
        await delete_all_alerts(update, context)

    # === Трекер: подменю ===
    elif text == "📋 Мой трекер":
        await show_my_tracked(update, context)
    elif text == "📊 Топ движения":
        await show_top_movers(update, context)
    elif text == "🌡️ Пульс рынка":
        await show_market_pulse(update, context)
    elif text == "🗑 Очистить трекер":
        await clear_tracker(update, context)

    # === Рейтинг: подменю ===
    elif text == "💎 По капитализации":
        await show_ranking_by_cap(update, context)
    elif text == "📈 По росту 24ч":
        await show_ranking_by_change(update, context)
    elif text == "📊 По объёму":
        await show_ranking_by_volume(update, context)
    elif text == "📉 Лузеры 24ч":
        await show_ranking_losers(update, context)

    # === Избранное: подменю ===
    elif text == "➕ Добавить в ⭐":
        await favorites_add_start_msg(update, context)
    elif text == "➖ Убрать из ⭐":
        await favorites_remove_start_msg(update, context)
    elif text == "📋 Моё избранное":
        await show_my_favorites(update, context)
    elif text == "📊 Цены избранных":
        await show_favorites_prices(update, context)
    elif text == "🗑 Очистить ⭐":
        await clear_favorites(update, context)

    # === Доп. меню ===
    elif text == "📰 Дайджест":
        await show_market_digest(update, context)
    elif text == "🎰 Крипто-рулетка" or text == "🎰 Рулетка":
        await show_crypto_roulette(update, context)
    elif text == "📈 Мини-график":
        await show_mini_chart(update, context)
    elif text == "🧠 Крипто-викторина":
        await show_crypto_quiz(update, context)
    elif text == "👑 Премиум-функции":
        await show_premium_features_menu(update, context)

    # === Новые функции ===
    elif text == "😱 Индекс Страха":
        if tier != 'premium':
            await sub_blocked(update, "Индекс Страха", "premium")
        else:
            await show_fear_greed(update, context)
    elif text == "🐋 Кит-Детектор":
        if tier != 'premium':
            await sub_blocked(update, "Кит-Детектор", "premium")
        else:
            await show_whale_detector(update, context)
    elif text == "🔬 Тех. Анализ":
        if tier != 'premium':
            await sub_blocked(update, "Тех. Анализ", "premium")
        else:
            await show_deep_analysis(update, context)
    elif text == "📊 Корреляция":
        if tier != 'premium':
            await sub_blocked(update, "Корреляция", "premium")
        else:
            await show_correlation(update, context)
    elif text == "🏦 Скринер":
        if tier != 'premium':
            await sub_blocked(update, "Скринер", "premium")
        else:
            await show_screener(update, context)
    elif text == "🧠 AI Советник":
        if tier != 'premium':
            await sub_blocked(update, "AI Советник", "premium")
        else:
            await show_ai_advisor(update, context)
    elif text == "🎯 Снайпер входа":
        if tier != 'premium':
            await sub_blocked(update, "Снайпер входа", "premium")
        else:
            await sniper_start(update, context)
    elif text == "🗺 Хитмап рынка":
        if tier != 'premium':
            await sub_blocked(update, "Хитмап рынка", "premium")
        else:
            await show_market_heatmap(update, context)
    elif text == "📡 Радар аномалий":
        if tier != 'premium':
            await sub_blocked(update, "Радар аномалий", "premium")
        else:
            await show_anomaly_radar(update, context)
    elif text == "🎯 Предсказание":
        await show_prediction_menu(update, context)
    elif text == "💼 Портфель":
        await show_portfolio_menu(update, context)
    elif text == "💡 Совет дня":
        await show_daily_tip(update, context)
    elif text == "🏅 Топ-3 дня":
        await show_top3_today(update, context)
    elif text == "📰 Новости рынка":
        await show_market_news(update, context)
    elif text == "📉 Волатильность":
        if tier == 'free':
            await sub_blocked(update, "Волатильность", "pro")
        else:
            await show_volatility_analysis(update, context)
    elif text == "📊 Объём Профиль":
        if tier == 'free':
            await sub_blocked(update, "Объём Профиль", "pro")
        else:
            await show_volume_profile(update, context)
    elif text == "💎 DCA Калькулятор":
        if tier != 'premium':
            await sub_blocked(update, "DCA Калькулятор", "premium")
        else:
            await show_dca_calculator(update, context)
    elif text == "🧬 Индекс Доминации":
        if tier != 'premium':
            await sub_blocked(update, "Индекс Доминации", "premium")
        else:
            await show_dominance_index(update, context)
    elif text == "📊 Мой портфель":
        await show_portfolio_view(update, context)
    elif text == "🗑 Очистить 💼":
        await portfolio_clear_cmd(update, context)
    elif text == "📈 P&L":
        await show_portfolio_pnl(update, context)
    elif text == "📋 Мои предсказания":
        await show_my_predictions(update, context)
    elif text == "🔮 Проверить":
        await check_predictions(update, context)
    elif text == "📊 Статистика 🎯":
        await show_prediction_stats(update, context)

    # === Ввод автора (выдача Premium / рассылка) ===
    elif context.user_data.get('author_action') and db.is_author(user_id):
        await author_handle_input(update, context)

    # === КНОПКИ АКТИВОВ (с эмодзи) ===
    else:
        asset_list = get_asset_list(mode)

        # Проверить избранное (FAV+ / FAV-)
        if text.startswith("FAV+"):
            ticker = text[4:]
            if ticker in asset_list:
                success = db.add_favorite(user_id, ticker, mode)
                emoji = asset_list[ticker]['emoji']
                if success:
                    await update.message.reply_text(
                        f"✅ {emoji} {ticker} добавлен в избранное!",
                        reply_markup=get_favorites_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        f"⭐ {emoji} {ticker} уже в избранном!",
                        reply_markup=get_favorites_keyboard()
                    )
                return
        elif text.startswith("FAV-"):
            ticker = text[4:]
            if ticker in asset_list:
                success = db.remove_favorite(user_id, ticker)
                emoji = asset_list[ticker]['emoji']
                if success:
                    await update.message.reply_text(
                        f"✅ {emoji} {ticker} убран из избранного!",
                        reply_markup=get_favorites_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        f"❌ {ticker} не найден в избранном!",
                        reply_markup=get_favorites_keyboard()
                    )
                return

        # Конвертер/сравнение кнопки
        if text == "🔄 Конвертировать":
            return
        elif text == "⚖️ Сравнить":
            return
        elif text == "🧮 Рассчитать":
            return

        # Проверить, нажал ли пользователь кнопку актива (формат: "🟠 BTC")
        ticker = None
        for t in asset_list:
            emoji = asset_list[t]['emoji']
            if text == f"{emoji} {t}" or text.upper() == t:
                ticker = t
                break

        if ticker:
            await show_crypto_price(update, context, ticker)
        else:
            await update.message.reply_text(
                "❓ Используйте кнопки меню:",
                reply_markup=get_back_keyboard(context)
            )


# ==================== ТРЕКЕР: МЕНЮ ====================

async def show_tracker_menu(update, context):
    """Главное меню трекера"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    word = asset_label(mode)
    count = db.count_user_tracked(user_id, mode)

    await update.message.reply_text(
        f"📡 ТРЕКЕР\n"
        f"{'═' * 28}\n\n"
        f"🔍 Отслеживаемых крипт: {count}\n\n"
        f"Трекер следит за резкими движениями\n"
        f"выбранных криптовалют и уведомляет\n"
        f"при сильных скачках цены!\n\n"
        f"➕ Добавить крипту в отслеживание\n"
        f"➖ Убрать из отслеживания\n"
        f"📋 Ваш список крипт\n"
        f"⚙️ Настроить порог срабатывания\n"
        f"📊 Топ растущих и падающих\n"
        f"🌡️ Общий пульс рынка",
        reply_markup=get_tracker_keyboard()
    )


async def show_my_tracked(update, context):
    """Показать отслеживаемые активы"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    tracked = db.get_user_tracked(user_id, mode)

    if not tracked:
        await update.message.reply_text(
            "📋 Вы ещё не добавили крипту в трекер.\n\n"
            "➕ Добавьте криптовалюту для отслеживания!",
            reply_markup=get_tracker_keyboard()
        )
        return

    text = f"📋 МОЙ ТРЕКЕР ({len(tracked)})\n{'━' * 28}\n\n"

    for item in tracked:
        ticker = item[2]
        threshold = item[3]
        emoji = asset_list.get(ticker, {}).get('emoji', '🪙')
        name = asset_list.get(ticker, {}).get('name', ticker)
        text += f"{emoji} {ticker} ({name}) — порог: {threshold:.0f}%\n"

    text += f"\n📡 Проверка каждые 2 минуты\n"
    text += f"⏰ Кулдаун уведомлений: 4 часа"

    await update.message.reply_text(text, reply_markup=get_tracker_keyboard())


async def clear_tracker(update, context):
    """Очистить весь трекер"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.clear_user_tracked(user_id, mode)

    if count > 0:
        await update.message.reply_text(
            f"🗑 Трекер очищен! Удалено: {count} крипт",
            reply_markup=get_tracker_keyboard()
        )
    else:
        await update.message.reply_text(
            "📋 Трекер и так пуст!",
            reply_markup=get_tracker_keyboard()
        )


# ==================== ТРЕКЕР: ДОБАВЛЕНИЕ (ConversationHandler) ====================

async def tracker_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления крипты в трекер"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    tracked = db.get_user_tracked(user_id, mode)
    tracked_tickers = {item[2] for item in tracked}

    # Показать только те, что ещё не отслеживаются
    tickers = [t for t in asset_list if t not in tracked_tickers]

    if not tickers:
        await update.message.reply_text(
            f"✅ Все {asset_word_short(mode)} уже в трекере!",
            reply_markup=get_tracker_keyboard()
        )
        return -1

    buttons = []
    row = []
    for ticker in tickers:
        emoji = asset_list[ticker]['emoji']
        row.append(KeyboardButton(f"{emoji} {ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])

    await update.message.reply_text(
        f"📡 ДОБАВИТЬ В ТРЕКЕР\n"
        f"{'═' * 28}\n\n"
        f"Выберите {asset_word(mode)} для\n"
        f"отслеживания резких движений:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return TRACKER_ADD_CRYPTO_STATE


async def tracker_add_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбрана крипта → выбор порога"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_tracker_keyboard())
        return -1

    # Извлечь тикер (формат "🟠 BTC" или "BTC")
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    ticker = None
    for t in asset_list:
        emoji = asset_list[t]['emoji']
        if text == f"{emoji} {t}" or text.upper() == t:
            ticker = t
            break

    if not ticker:
        await update.message.reply_text(f"❌ Выберите {asset_word(mode)} кнопкой!")
        return TRACKER_ADD_CRYPTO_STATE

    context.user_data['tracker_crypto'] = ticker

    emoji = asset_list[ticker]['emoji']
    await update.message.reply_text(
        f"📡 {emoji} {ticker}\n"
        f"{'━' * 28}\n\n"
        f"Выберите порог срабатывания:\n"
        f"(изменение цены за 24ч)\n\n"
        f"Например, 10% = бот напишет если\n"
        f"{ticker} вырастет или упадёт на 10%+",
        reply_markup=get_threshold_keyboard()
    )
    return TRACKER_SET_THRESHOLD_STATE


async def tracker_set_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка порога и сохранение"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_tracker_keyboard())
        return -1

    try:
        threshold = float(text.replace('%', '').replace(' ', ''))
        if threshold <= 0 or threshold > 100:
            await update.message.reply_text("❌ Порог от 1% до 100%!")
            return TRACKER_SET_THRESHOLD_STATE
    except ValueError:
        await update.message.reply_text("❌ Выберите порог кнопкой!")
        return TRACKER_SET_THRESHOLD_STATE

    user_id = update.effective_user.id
    ticker = context.user_data.get('tracker_crypto')
    mode = get_mode(context)

    if not ticker:
        await update.message.reply_text("❌ Ошибка, попробуйте снова", reply_markup=get_tracker_keyboard())
        return -1

    db.add_tracked_crypto(user_id, ticker, threshold, mode)

    emoji = get_asset_list(get_mode(context)).get(ticker, {}).get('emoji', '🪙')
    await update.message.reply_text(
        f"✅ ДОБАВЛЕНО В ТРЕКЕР!\n"
        f"{'━' * 28}\n\n"
        f"{emoji} {ticker}\n"
        f"📊 Порог: {threshold:.0f}%\n\n"
        f"🔔 Вы получите уведомление когда\n"
        f"цена изменится на {threshold:.0f}%+ за 24ч\n\n"
        f"📡 Проверка каждые 2 минуты",
        reply_markup=get_tracker_keyboard()
    )
    return -1


# ==================== ТРЕКЕР: УДАЛЕНИЕ ====================

async def tracker_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления актива из трекера"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    tracked = db.get_user_tracked(user_id, mode)

    if not tracked:
        await update.message.reply_text(
            "📋 Трекер пуст — нечего удалять!",
            reply_markup=get_tracker_keyboard()
        )
        return -1

    buttons = []
    row = []
    text = "➖ УБРАТЬ ИЗ ТРЕКЕРА\n"
    text += f"{'━' * 28}\n\n"

    for item in tracked:
        ticker = item[2]
        threshold = item[3]
        emoji = asset_list.get(ticker, {}).get('emoji', '🪙')
        text += f"{emoji} {ticker} (порог: {threshold:.0f}%)\n"
        row.append(KeyboardButton(ticker))
        if len(row) == 3:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])

    text += "\nВыберите крипту для удаления:"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return TRACKER_REMOVE_CRYPTO_STATE


async def tracker_remove_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление выбранной крипты"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_tracker_keyboard())
        return -1

    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text not in asset_list:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return TRACKER_REMOVE_CRYPTO_STATE

    success = db.remove_tracked_crypto(user_id, text)
    emoji = asset_list.get(text, {}).get('emoji', '🪙')

    if success:
        await update.message.reply_text(
            f"✅ {emoji} {text} удалён из трекера!",
            reply_markup=get_tracker_keyboard()
        )
    else:
        await update.message.reply_text(
            f"❌ {text} не найден в трекере!",
            reply_markup=get_tracker_keyboard()
        )
    return -1


# ==================== ТРЕКЕР: ПОРОГ ====================

async def tracker_threshold_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение порога для всех отслеживаемых крипт"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.count_user_tracked(user_id, mode)

    if count == 0:
        await update.message.reply_text(
            "📋 Сначала добавьте крипту в трекер!",
            reply_markup=get_tracker_keyboard()
        )
        return -1

    await update.message.reply_text(
        "⚙️ ПОРОГ ОПОВЕЩЕНИЯ\n"
        f"{'═' * 28}\n\n"
        f"Сейчас у вас {count} крипт в трекере.\n\n"
        f"Выберите новый порог для ВСЕХ\n"
        f"отслеживаемых криптовалют:\n\n"
        f"Чем ниже порог — тем чаще\n"
        f"уведомления (но больше шума).",
        reply_markup=get_threshold_keyboard()
    )
    return TRACKER_SET_THRESHOLD_STATE


async def tracker_threshold_set_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка порога для всех"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_tracker_keyboard())
        return -1

    try:
        threshold = float(text.replace('%', '').replace(' ', ''))
        if threshold <= 0 or threshold > 100:
            await update.message.reply_text("❌ Порог от 1% до 100%!")
            return TRACKER_SET_THRESHOLD_STATE
    except ValueError:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return TRACKER_SET_THRESHOLD_STATE

    user_id = update.effective_user.id
    count = db.set_all_tracked_threshold(user_id, threshold)

    await update.message.reply_text(
        f"✅ Порог обновлён!\n"
        f"{'━' * 28}\n\n"
        f"📊 Новый порог: {threshold:.0f}%\n"
        f"🔄 Обновлено крипт: {count}\n\n"
        f"🔔 Теперь бот уведомит когда\n"
        f"изменение за 24ч превысит {threshold:.0f}%",
        reply_markup=get_tracker_keyboard()
    )
    return -1


# ==================== ОТ СЕБЯ: ТОП ДВИЖЕНИЯ + ПУЛЬС РЫНКА ====================

async def show_top_movers(update, context):
    """Топ-5 растущих и падающих активов за 24ч"""
    msg = await update.message.reply_text("⏳ Анализ рынка...")

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать изменения
    changes = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        change = coin_data.get('usd_24h_change')
        price = coin_data.get('usd')
        if change is not None and price is not None:
            changes.append((ticker, change, price))

    if not changes:
        try:
            await msg.edit_text("❌ Нет данных об изменениях")
        except Exception:
            pass
        return

    changes.sort(key=lambda x: x[1], reverse=True)

    text = f"📊 ТОП ДВИЖЕНИЯ ЗА 24Ч\n{'━' * 28}\n\n"

    # Топ растущие
    text += "🚀 ЛИДЕРЫ РОСТА:\n"
    for ticker, change, price in changes[:5]:
        emoji = asset_list[ticker]['emoji']
        arrow = "🟢" if change > 0 else "🔴"
        text += f"{arrow} {emoji} {ticker}: {change:+.2f}% (${price:,.2f})\n"

    text += "\n💥 ЛИДЕРЫ ПАДЕНИЯ:\n"
    for ticker, change, price in changes[-5:][::-1]:
        emoji = asset_list[ticker]['emoji']
        arrow = "🔴" if change < 0 else "🟢"
        text += f"{arrow} {emoji} {ticker}: {change:+.2f}% (${price:,.2f})\n"

    # Общая статистика
    avg_change = sum(c[1] for c in changes) / len(changes)
    up_count = sum(1 for c in changes if c[1] > 0)
    down_count = sum(1 for c in changes if c[1] < 0)

    if avg_change > 5:
        demand = "🔥 Невероятный спрос"
    elif avg_change > 2:
        demand = "📈 Огромный спрос"
    elif avg_change > 0.5:
        demand = "✅ Спрос выше среднего"
    elif avg_change > -0.5:
        demand = "➡️ Средний спрос"
    elif avg_change > -2:
        demand = "📉 Спрос ниже среднего"
    elif avg_change > -5:
        demand = "⚠️ Низкий спрос"
    else:
        demand = "🚨 Критически низкий спрос"

    text += f"\n{'━' * 28}\n"
    text += f"📈 Растут: {up_count} | 📉 Падают: {down_count}\n"
    text += f"📊 Средн. изменение: {avg_change:+.2f}%\n"
    text += f"🏷️ Спрос: {demand}"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_tracker_keyboard())


async def show_market_pulse(update, context):
    """Пульс рынка — общая сводка с индикаторами"""
    msg = await update.message.reply_text("⏳ Считываю пульс рынка...")

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Нет данных")
        except Exception:
            pass
        return

    changes = []
    total_cap = 0
    total_vol = 0

    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        change = coin_data.get('usd_24h_change', 0)
        cap = coin_data.get('usd_market_cap', 0)
        vol = coin_data.get('usd_24h_vol', 0)
        if change is not None:
            changes.append(change)
        total_cap += (cap or 0)
        total_vol += (vol or 0)

    if not changes:
        try:
            await msg.edit_text("❌ Нет данных")
        except Exception:
            pass
        return

    avg = sum(changes) / len(changes)
    max_up = max(changes)
    max_down = min(changes)
    up_count = sum(1 for c in changes if c > 0)
    down_count = sum(1 for c in changes if c < 0)
    flat_count = sum(1 for c in changes if c == 0)

    # Уровень спроса
    if avg > 5:
        demand_level = "🔥 Невероятный спрос"
        bar = "🟢🟢🟢🟢🟢"
    elif avg > 2:
        demand_level = "📈 Огромный спрос"
        bar = "🟢🟢🟢🟢⚪"
    elif avg > 0.5:
        demand_level = "✅ Спрос выше среднего"
        bar = "🟢🟢🟢⚪⚪"
    elif avg > -0.5:
        demand_level = "➡️ Средний спрос"
        bar = "🟡🟡🟡⚪⚪"
    elif avg > -2:
        demand_level = "📉 Спрос ниже среднего"
        bar = "🔴🔴⚪⚪⚪"
    elif avg > -5:
        demand_level = "⚠️ Низкий спрос"
        bar = "🔴🔴🔴⚪⚪"
    else:
        demand_level = "🚨 Критически низкий спрос"
        bar = "🔴🔴🔴🔴🔴"

    # Волатильность
    import statistics
    vol_index = statistics.stdev(changes) if len(changes) > 1 else 0
    if vol_index > 10:
        vol_text = "🌋 Экстремальная"
    elif vol_index > 5:
        vol_text = "🔥 Высокая"
    elif vol_index > 2:
        vol_text = "📊 Средняя"
    else:
        vol_text = "😴 Низкая"

    text = (
        f"🌡️ ПУЛЬС РЫНКА\n"
        f"{'━' * 28}\n\n"
        f"📊 Анализ {len(changes)} криптовалют\n\n"
        f"🏷️ Спрос: {demand_level}\n"
        f"   {bar}\n\n"
        f"📈 Средн. изменение: {avg:+.2f}%\n"
        f"🚀 Макс. рост: +{max_up:.2f}%\n"
        f"💥 Макс. падение: {max_down:.2f}%\n\n"
        f"🟢 Растут: {up_count} | 🔴 Падают: {down_count} | ⚪ Без изменений: {flat_count}\n\n"
        f"🌊 Волатильность: {vol_text} ({vol_index:.1f}%)\n"
        f"💎 Общая капитализация: {format_volume(total_cap, 'usd')}\n"
        f"📈 Общий объём 24ч: {format_volume(total_vol, 'usd')}\n\n"
        f"🕐 Данные {asset_source(mode)}"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_tracker_keyboard())


# ==================== СИГНАЛЫ: ПОКУПАТЬ / ПРОДАВАТЬ / ДЕРЖАТЬ ====================

def get_signals_keyboard():
    """Меню сигналов"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🤖 Все сигналы")],
        [KeyboardButton("💰 Портфель дня")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def _analyze_signal(change_24h, volume, market_cap, price):
    """Анализ крипты и выдача сигнала: BUY / SELL / HOLD
    На основе комбинации: 24h-change, объём к капитализации, сила движения"""

    score = 0  # от -100 до +100

    # === Фактор 1: Изменение за 24ч (вес 40%) ===
    if change_24h > 10:
        score += 35  # сильный рост — но возможен откат
    elif change_24h > 5:
        score += 40  # хороший рост
    elif change_24h > 2:
        score += 30  # умеренный рост
    elif change_24h > 0.5:
        score += 15  # лёгкий рост
    elif change_24h > -0.5:
        score += 0   # стабильно
    elif change_24h > -2:
        score -= 10  # лёгкое падение
    elif change_24h > -5:
        score -= 25  # падение
    elif change_24h > -10:
        score -= 30  # сильное падение — но возможен отскок
    else:
        score -= 20  # обвал — может быть выгодная покупка

    # === Фактор 2: Объём к капитализации (вес 30%) ===
    if market_cap and market_cap > 0:
        vol_ratio = (volume or 0) / market_cap
        if vol_ratio > 0.3:
            # Огромный объём — сильный интерес
            score += 20 if change_24h > 0 else -15
        elif vol_ratio > 0.15:
            score += 15 if change_24h > 0 else -10
        elif vol_ratio > 0.05:
            score += 5
        else:
            score -= 5  # низкий объём — слабый интерес

    # === Фактор 3: Ценовой диапазон (вес 15%) ===
    if change_24h > 15:
        score -= 10  # перекуплено, возможен откат
    elif change_24h < -15:
        score += 15  # перепродано, возможен отскок

    # === Фактор 4: Контртренд (вес 15%) ===
    if change_24h > 20:
        score -= 15  # слишком сильный рост — риск коррекции
    elif change_24h < -20:
        score += 20  # сильный обвал — потенциал для покупки

    # Определить сигнал
    if score >= 25:
        return 'BUY', score
    elif score <= -15:
        return 'SELL', score
    else:
        return 'HOLD', score


def _signal_to_text(signal, score):
    """Преобразовать сигнал в красивый текст"""
    if signal == 'BUY':
        strength = "🟢🟢🟢" if score >= 45 else "🟢🟢" if score >= 35 else "🟢"
        return f"✅ ПОКУПАТЬ {strength}", "Рост + высокий интерес"
    elif signal == 'SELL':
        strength = "🔴🔴🔴" if score <= -40 else "🔴🔴" if score <= -25 else "🔴"
        return f"❌ ПРОДАВАТЬ {strength}", "Падение + слабый интерес"
    else:
        return "⏸️ ДЕРЖАТЬ 🟡", "Неопределённость, лучше подождать"


async def show_signals(update, context):
    """Показать меню сигналов"""
    await update.message.reply_text(
        f"🤖 ТОРГОВЫЕ СИГНАЛЫ\n"
        f"{'═' * 28}\n\n"
        f"Бот анализирует каждую крипту\n"
        f"и даёт рекомендацию:\n\n"
        f"✅ ПОКУПАТЬ — рост + высокий спрос\n"
        f"❌ ПРОДАВАТЬ — падение + низкий спрос\n"
        f"⏸️ ДЕРЖАТЬ — ситуация неясная\n\n"
        f"⚠️ Это НЕ финансовый совет!\n"
        f"Анализ на основе 24ч данных.\n\n"
        f"🤖 Все сигналы — полный обзор\n"
        f"💰 Портфель дня — лучшие для покупки",
        reply_markup=get_signals_keyboard()
    )


async def show_all_signals(update, context):
    """Показать сигналы для всех активов"""
    msg = await update.message.reply_text("⏳ Анализирую рынок...")

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    buy_list = []
    sell_list = []
    hold_list = []

    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0)
        change = coin_data.get('usd_24h_change', 0)
        volume = coin_data.get('usd_24h_vol', 0)
        market_cap = coin_data.get('usd_market_cap', 0)

        if price is None or price == 0:
            continue

        signal, score = _analyze_signal(change or 0, volume or 0, market_cap or 0, price)
        emoji = info['emoji']

        entry = (ticker, emoji, signal, score, price, change or 0)

        if signal == 'BUY':
            buy_list.append(entry)
        elif signal == 'SELL':
            sell_list.append(entry)
        else:
            hold_list.append(entry)

    # Сортировка по силе сигнала
    buy_list.sort(key=lambda x: x[3], reverse=True)
    sell_list.sort(key=lambda x: x[3])
    hold_list.sort(key=lambda x: abs(x[5]), reverse=True)

    text = f"🤖 ТОРГОВЫЕ СИГНАЛЫ\n{'━' * 28}\n\n"

    if buy_list:
        text += "✅ ПОКУПАТЬ:\n"
        for ticker, emoji, signal, score, price, change in buy_list:
            sig_text, _ = _signal_to_text(signal, score)
            text += f"{emoji} {ticker}: ${price:,.2f} ({change:+.1f}%) — {sig_text}\n"
        text += "\n"

    if hold_list:
        text += "⏸️ ДЕРЖАТЬ:\n"
        for ticker, emoji, signal, score, price, change in hold_list:
            text += f"{emoji} {ticker}: ${price:,.2f} ({change:+.1f}%) — ⏸️ ДЕРЖАТЬ\n"
        text += "\n"

    if sell_list:
        text += "❌ ПРОДАВАТЬ:\n"
        for ticker, emoji, signal, score, price, change in sell_list:
            sig_text, _ = _signal_to_text(signal, score)
            text += f"{emoji} {ticker}: ${price:,.2f} ({change:+.1f}%) — {sig_text}\n"
        text += "\n"

    text += f"{'━' * 28}\n"
    text += f"📊 Покупать: {len(buy_list)} | Держать: {len(hold_list)} | Продавать: {len(sell_list)}\n"
    text += "⚠️ Не является финансовым советом!"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_signals_keyboard())


# ==================== ОТ СЕБЯ: ПОРТФЕЛЬ ДНЯ ====================

async def show_portfolio_of_day(update, context):
    """Портфель дня — лучшие активы для покупки с распределением %"""
    msg = await update.message.reply_text("⏳ Считаю оптимальный портфель...")

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать данные и оценить
    candidates = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0)
        change = coin_data.get('usd_24h_change', 0)
        volume = coin_data.get('usd_24h_vol', 0)
        market_cap = coin_data.get('usd_market_cap', 0)

        if not price or price == 0:
            continue

        signal, score = _analyze_signal(change or 0, volume or 0, market_cap or 0, price)

        # Для портфеля берём только BUY и сильный HOLD
        if score >= 10:
            # Бонус за стабильность (высокая капитализация)
            stability = 0
            if market_cap and market_cap > 50_000_000_000:
                stability = 15  # топ-монеты
            elif market_cap and market_cap > 10_000_000_000:
                stability = 10
            elif market_cap and market_cap > 1_000_000_000:
                stability = 5

            total_score = score + stability
            candidates.append((ticker, info['emoji'], info['name'], price, change or 0, total_score, market_cap or 0))

    if not candidates:
        try:
            await msg.edit_text(
                "💰 ПОРТФЕЛЬ ДНЯ\n"
                f"{'━' * 28}\n\n"
                "😔 Сегодня нет хороших кандидатов\n"
                "для покупки. Рынок нестабилен.\n\n"
                "💡 Рекомендация: подождать или\n"
                "держать текущие позиции."
            )
        except Exception:
            pass
        return

    # Топ-5 по скору
    candidates.sort(key=lambda x: x[5], reverse=True)
    top = candidates[:5]

    # Распределить % портфеля пропорционально скору
    total_score = sum(c[5] for c in top)

    text = f"💰 ПОРТФЕЛЬ ДНЯ\n{'━' * 28}\n\n"
    text += "Оптимальное распределение средств\n"
    text += "на основе анализа рынка:\n\n"

    risk_total = 0
    for ticker, emoji, name, price, change, score, cap in top:
        pct = (score / total_score) * 100 if total_score > 0 else 20
        # Визуальная шкала
        bars = round(pct / 5)
        bar_visual = "█" * bars + "░" * (20 - bars)

        # Уровень риска
        if cap > 50_000_000_000:
            risk = "🟢 Низкий"
            risk_val = 1
        elif cap > 5_000_000_000:
            risk = "🟡 Средний"
            risk_val = 2
        else:
            risk = "🔴 Высокий"
            risk_val = 3
        risk_total += risk_val

        text += f"{emoji} {ticker} — {pct:.0f}%\n"
        text += f"   {bar_visual}\n"
        text += f"   ${price:,.2f} ({change:+.1f}%) | Риск: {risk}\n\n"

    # Общая оценка портфеля
    avg_risk = risk_total / len(top)
    if avg_risk <= 1.5:
        risk_rating = "🟢 Консервативный"
    elif avg_risk <= 2.2:
        risk_rating = "🟡 Умеренный"
    else:
        risk_rating = "🔴 Агрессивный"

    avg_change = sum(c[4] for c in top) / len(top)
    if avg_change > 0:
        momentum = "📈 Положительная"
    else:
        momentum = "📉 Отрицательная"

    text += f"{'━' * 28}\n"
    text += f"📊 Тип: {risk_rating}\n"
    text += f"📈 Динамика: {momentum} ({avg_change:+.1f}%)\n"
    text += f"🎯 Монет в портфеле: {len(top)}\n\n"
    text += f"💡 Совет: диверсификация снижает\n"
    text += f"риски. Не вкладывай всё в одну!\n\n"
    text += f"⚠️ Не является финансовым советом!"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_signals_keyboard())


# ==================== ФОНОВАЯ ПРОВЕРКА АЛЕРТОВ ====================

async def check_alerts_job(context):
    """Фоновая задача: проверка всех активных алертов каждые N секунд"""
    alerts = db.get_all_active_alerts()
    if not alerts:
        return

    # Определить какие режимы и валюты нужны
    need_crypto_usd = any(a[4] == 'usd' and (len(a) <= 9 or a[9] != 'stocks') for a in alerts)
    need_crypto_rub = any(a[4] == 'rub' and (len(a) <= 9 or a[9] != 'stocks') for a in alerts)
    need_stocks_usd = any(len(a) > 9 and a[9] == 'stocks' and a[4] == 'usd' for a in alerts)
    need_stocks_rub = any(len(a) > 9 and a[9] == 'stocks' and a[4] == 'rub' for a in alerts)

    crypto_usd_prices = {}
    crypto_rub_prices = {}
    stocks_usd_prices = {}
    stocks_rub_prices = {}

    if need_crypto_usd:
        crypto_usd_prices = await get_all_prices('usd')
    if need_crypto_rub:
        crypto_rub_prices = await get_all_prices('rub')
    if need_stocks_usd:
        stocks_usd_prices = await stocks_api.get_all_prices('usd')
    if need_stocks_rub:
        stocks_rub_prices = await stocks_api.get_all_prices('rub')

    for alert in alerts:
        alert_id = alert[0]
        user_id = alert[1]
        ticker = alert[2]
        target_price = alert[3]
        currency = alert[4]
        direction = alert[5]
        asset_type = alert[9] if len(alert) > 9 else 'crypto'

        if asset_type == 'stocks':
            prices = stocks_usd_prices if currency == 'usd' else stocks_rub_prices
            al = STOCKS_LIST
        else:
            prices = crypto_usd_prices if currency == 'usd' else crypto_rub_prices
            al = CRYPTO_LIST

        current_price = prices.get(ticker)

        if current_price is None:
            continue

        # Проверка условия
        triggered = False
        if direction == 'above' and current_price >= target_price:
            triggered = True
        elif direction == 'below' and current_price <= target_price:
            triggered = True

        if triggered:
            db.trigger_alert(alert_id)

            emoji = al.get(ticker, {}).get('emoji', '🪙')
            name = al.get(ticker, {}).get('name', ticker)
            curr_sym = '$' if currency == 'usd' else '₽'
            dir_text = "поднялась выше" if direction == 'above' else "опустилась ниже"

            target_str = format_price(target_price, currency)
            current_str = format_price(current_price, currency)

            message = (
                f"🔔🔔🔔 АЛЕРТ СРАБОТАЛ! 🔔🔔🔔\n"
                f"{'━' * 28}\n\n"
                f"{emoji} {name} ({ticker})\n\n"
                f"📊 Цена {dir_text} {target_str}!\n\n"
                f"🎯 Ваша цель: {target_str}\n"
                f"💰 Текущая цена: {current_str}\n\n"
                f"⚡ Чекай крипту! Время действовать! 🚀"
            )

            try:
                await context.bot.send_message(chat_id=user_id, text=message)
            except Exception:
                pass  # Пользователь заблокировал бота или ошибка


# ==================== ФОНОВАЯ ПРОВЕРКА ТРЕКЕРА ====================

async def check_tracker_job(context):
    """Фоновая задача: проверка резких движений для всех пользователей трекера"""
    tracked = db.get_all_tracked()
    if not tracked:
        return

    # Определить нужны ли крипто и/или акции
    need_crypto = any((len(item) <= 6 or item[6] != 'stocks') for item in tracked)
    need_stocks = any(len(item) > 6 and item[6] == 'stocks' for item in tracked)

    crypto_data = {}
    stocks_data = {}

    if need_crypto:
        crypto_data = await fetch_prices('usd') or {}
    if need_stocks:
        stocks_data = await stocks_api.fetch_prices('usd') or {}

    # Собрать 24h-change для каждого тикера по обоим режимам
    changes_map = {}
    prices_map = {}

    for ticker, info in CRYPTO_LIST.items():
        coin_data = crypto_data.get(info['id'], {})
        change = coin_data.get('usd_24h_change')
        price = coin_data.get('usd')
        if change is not None:
            changes_map[('crypto', ticker)] = change
        if price is not None:
            prices_map[('crypto', ticker)] = price

    for ticker, info in STOCKS_LIST.items():
        stock_data = stocks_data.get(info['id'], {})
        change = stock_data.get('usd_24h_change')
        price = stock_data.get('usd')
        if change is not None:
            changes_map[('stocks', ticker)] = change
        if price is not None:
            prices_map[('stocks', ticker)] = price

    for item in tracked:
        user_id = item[1]
        ticker = item[2]
        threshold = item[3]
        asset_type = item[6] if len(item) > 6 else 'crypto'

        change = changes_map.get((asset_type, ticker))
        if change is None:
            continue

        abs_change = abs(change)
        if abs_change < threshold:
            continue

        # Определить направление
        direction = 'up' if change > 0 else 'down'

        # Проверить кулдаун
        if not db.can_notify_tracker(user_id, ticker, direction, TRACKER_COOLDOWN):
            continue

        # Отправить уведомление
        al = STOCKS_LIST if asset_type == 'stocks' else CRYPTO_LIST
        emoji = al.get(ticker, {}).get('emoji', '🪙')
        name = al.get(ticker, {}).get('name', ticker)
        price = prices_map.get((asset_type, ticker), 0)
        price_str = format_price(price, 'usd')

        if direction == 'up':
            icon = "🚀📈"
            move_text = "РЕЗКИЙ РОСТ"
            color = "🟢"
        else:
            icon = "💥📉"
            move_text = "РЕЗКОЕ ПАДЕНИЕ"
            color = "🔴"

        message = (
            f"{icon} ТРЕКЕР: {move_text}! {icon}\n"
            f"{'━' * 28}\n\n"
            f"{emoji} {name} ({ticker})\n\n"
            f"{color} Изменение 24ч: {change:+.2f}%\n"
            f"💰 Текущая цена: {price_str}\n"
            f"📊 Ваш порог: {threshold:.0f}%\n\n"
            f"⚡ Внимание! {ticker} {'взлетел' if direction == 'up' else 'упал'} "
            f"на {abs_change:.1f}%! Чекай рынок! 👀"
        )

        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            db.update_tracker_notification(user_id, ticker, direction)
        except Exception:
            pass


# ==================== 🔄 КОНВЕРТЕР КРИПТОВАЛЮТ ====================

async def show_converter_menu(update, context):
    """Меню конвертера"""
    mode = get_mode(context)
    label = asset_label(mode)
    await update.message.reply_text(
        f"🔄 КОНВЕРТЕР {label.upper()}\n"
        f"{'═' * 28}\n\n"
        f"Переведите одну криптовалюту\n"
        f"в другую по текущему курсу.\n\n"
        f"Например: сколько ETH можно\n"
        f"купить за 0.5 BTC?\n\n"
        f"Нажмите «🔄 Конвертировать»\n"
        f"чтобы начать:",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🔄 Конвертировать")],
            [KeyboardButton("↩️ Назад")]
        ], resize_keyboard=True)
    )


async def converter_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертер: шаг 1 — выбор исходной крипты"""
    mode = get_mode(context)
    await update.message.reply_text(
        f"🔄 КОНВЕРТЕР\n"
        f"{'━' * 28}\n\n"
        f"Шаг 1/3: Из какого актива\n"
        f"конвертировать?",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return CONVERTER_FROM_STATE


async def converter_choose_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертер: шаг 2 — выбор целевого актива"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text not in asset_list:
        await update.message.reply_text(f"❌ Выберите {asset_word(mode)} кнопкой!")
        return CONVERTER_FROM_STATE

    context.user_data['conv_from'] = text
    emoji = asset_list[text]['emoji']

    await update.message.reply_text(
        f"🔄 Из: {emoji} {text}\n\n"
        f"Шаг 2/3: В какую {asset_word(mode)}\n"
        f"конвертировать?",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return CONVERTER_TO_STATE


async def converter_choose_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертер: шаг 3 — ввод количества"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text not in asset_list:
        await update.message.reply_text(f"❌ Выберите {asset_word(mode)} кнопкой!")
        return CONVERTER_TO_STATE

    from_ticker = context.user_data.get('conv_from')
    if text == from_ticker:
        await update.message.reply_text(f"❌ Выберите другую {asset_word(mode)}!")
        return CONVERTER_TO_STATE

    context.user_data['conv_to'] = text

    emoji_from = asset_list[from_ticker]['emoji']
    emoji_to = asset_list[text]['emoji']

    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🔄 {emoji_from} {from_ticker} → {emoji_to} {text}\n\n"
        f"Шаг 3/3: Введите количество {from_ticker}:\n\n"
        f"Примеры: 1, 0.5, 100",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CONVERTER_AMOUNT_STATE


async def converter_set_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертер: результат"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    try:
        amount = float(text.replace(',', '.').replace(' ', ''))
        if amount <= 0:
            await update.message.reply_text("❌ Количество должно быть > 0!")
            return CONVERTER_AMOUNT_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return CONVERTER_AMOUNT_STATE

    from_ticker = context.user_data.get('conv_from')
    to_ticker = context.user_data.get('conv_to')
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    msg = await update.message.reply_text("⏳ Конвертирую...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return -1

    from_data = data.get(asset_list[from_ticker]['id'], {})
    to_data = data.get(asset_list[to_ticker]['id'], {})

    from_price = from_data.get('usd', 0)
    to_price = to_data.get('usd', 0)

    if not from_price or not to_price:
        try:
            await msg.edit_text("❌ Не удалось получить цены")
        except Exception:
            pass
        return -1

    # Конвертация
    usd_value = amount * from_price
    result_amount = usd_value / to_price
    rate = from_price / to_price

    emoji_from = asset_list[from_ticker]['emoji']
    emoji_to = asset_list[to_ticker]['emoji']

    try:
        await msg.edit_text(
            f"🔄 РЕЗУЛЬТАТ КОНВЕРТАЦИИ\n"
            f"{'━' * 28}\n\n"
            f"{emoji_from} {amount:g} {from_ticker}\n"
            f"   ⬇️\n"
            f"{emoji_to} {result_amount:.8g} {to_ticker}\n\n"
            f"{'━' * 28}\n"
            f"📊 Курсы:\n"
            f"  1 {from_ticker} = ${from_price:,.2f}\n"
            f"  1 {to_ticker} = ${to_price:,.2f}\n\n"
            f"💱 Курс: 1 {from_ticker} = {rate:.8g} {to_ticker}\n"
            f"💵 В долларах: ${usd_value:,.2f}\n\n"
            f"🕐 По текущим данным {asset_source(mode)}"
        )
    except Exception:
        await update.message.reply_text("❌ Ошибка вывода", reply_markup=get_back_keyboard(context))

    return -1


# ==================== ⚖️ СРАВНЕНИЕ ДВУХ КРИПТОВАЛЮТ ====================

async def show_compare_menu(update, context):
    """Меню сравнения"""
    mode = get_mode(context)
    await update.message.reply_text(
        f"⚖️ СРАВНЕНИЕ {asset_label(mode).upper()}\n"
        f"{'═' * 28}\n\n"
        f"Сравните две криптовалюты\n"
        f"по всем параметрам:\n"
        f"цена, капитализация, объём,\n"
        f"рост/падение за 24ч.\n\n"
        f"Нажмите «⚖️ Сравнить» чтобы начать:",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("⚖️ Сравнить")],
            [KeyboardButton("↩️ Назад")]
        ], resize_keyboard=True)
    )


async def compare_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнение: шаг 1 — первая крипта"""
    mode = get_mode(context)
    await update.message.reply_text(
        f"⚖️ СРАВНЕНИЕ\n"
        f"{'━' * 28}\n\n"
        f"Шаг 1/2: Выберите первый актив:",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return COMPARE_FIRST_STATE


async def compare_choose_first(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнение: шаг 2 — второй актив"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text not in asset_list:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return COMPARE_FIRST_STATE

    context.user_data['compare_first'] = text
    emoji = asset_list[text]['emoji']

    await update.message.reply_text(
        f"⚖️ Первая: {emoji} {text}\n\n"
        f"Шаг 2/2: Выберите вторую\n"
        f"{asset_word(mode)} для сравнения:",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return COMPARE_SECOND_STATE


async def compare_choose_second(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнение: результат"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text not in asset_list:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return COMPARE_SECOND_STATE

    first = context.user_data.get('compare_first')
    if text == first:
        await update.message.reply_text(f"❌ Выберите другую {asset_word(mode)}!")
        return COMPARE_SECOND_STATE

    msg = await update.message.reply_text("⏳ Сравниваю...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return -1

    d1 = data.get(asset_list[first]['id'], {})
    d2 = data.get(asset_list[text]['id'], {})

    p1, p2 = d1.get('usd', 0), d2.get('usd', 0)
    c1, c2 = d1.get('usd_24h_change', 0) or 0, d2.get('usd_24h_change', 0) or 0
    v1, v2 = d1.get('usd_24h_vol', 0) or 0, d2.get('usd_24h_vol', 0) or 0
    m1, m2 = d1.get('usd_market_cap', 0) or 0, d2.get('usd_market_cap', 0) or 0

    e1 = asset_list[first]['emoji']
    e2 = asset_list[text]['emoji']
    n1 = asset_list[first]['name']
    n2 = asset_list[text]['name']

    # Определить победителя по каждому параметру
    def winner(val1, val2, higher_better=True):
        if higher_better:
            return "🏆" if val1 > val2 else ("🏆" if val2 > val1 else "🤝")
        return "🏆" if val1 < val2 else ("🏆" if val2 < val1 else "🤝")

    w_price = "—"  # цена — нейтрально
    w_change = winner(c1, c2)
    w_vol = winner(v1, v2)
    w_cap = winner(m1, m2)

    # Общий счёт
    score1, score2 = 0, 0
    if c1 > c2: score1 += 1
    elif c2 > c1: score2 += 1
    if v1 > v2: score1 += 1
    elif v2 > v1: score2 += 1
    if m1 > m2: score1 += 1
    elif m2 > m1: score2 += 1

    if score1 > score2:
        verdict = f"🏆 {first} выигрывает!"
    elif score2 > score1:
        verdict = f"🏆 {text} выигрывает!"
    else:
        verdict = "🤝 Ничья!"

    result = (
        f"⚖️ СРАВНЕНИЕ\n"
        f"{'━' * 28}\n\n"
        f"{'':>14}{e1} {first:>6} vs {text:<6} {e2}\n"
        f"{'━' * 28}\n\n"
        f"💰 Цена:\n"
        f"  {format_price(p1, 'usd'):>12}  |  {format_price(p2, 'usd')}\n\n"
        f"📈 Изменение 24ч:\n"
        f"  {c1:>+.2f}%  {'🏆' if c1 > c2 else '  '}  |  {c2:+.2f}%  {'🏆' if c2 > c1 else ''}\n\n"
        f"📊 Объём 24ч:\n"
        f"  {format_volume(v1, 'usd'):>8}  {'🏆' if v1 > v2 else '  '}  |  {format_volume(v2, 'usd')}  {'🏆' if v2 > v1 else ''}\n\n"
        f"💎 Капитализация:\n"
        f"  {format_volume(m1, 'usd'):>8}  {'🏆' if m1 > m2 else '  '}  |  {format_volume(m2, 'usd')}  {'🏆' if m2 > m1 else ''}\n\n"
        f"{'━' * 28}\n"
        f"📊 Счёт: {first} {score1} — {score2} {text}\n"
        f"{verdict}"
    )

    try:
        await msg.edit_text(result)
    except Exception:
        await update.message.reply_text(result, reply_markup=get_back_keyboard(context))

async def show_calculator_menu(update, context):
    """Меню калькулятора"""
    await update.message.reply_text(
        f"🧮 КАЛЬКУЛЯТОР ПРИБЫЛИ\n"
        f"{'═' * 28}\n\n"
        f"Рассчитайте вашу прибыль\n"
        f"или убыток по криптовалюте.\n\n"
        f"Введите: валюту, крипту, цену\n"
        f"покупки и количество монет.\n\n"
        f"Бот покажет текущую стоимость\n"
        f"и прибыль/убыток в $ или ₽.",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🧮 Рассчитать")],
            [KeyboardButton("↩️ Назад")]
        ], resize_keyboard=True)
    )


async def calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор: шаг 1 — выбор валюты"""
    keyboard = [
        [KeyboardButton("💵 USD"), KeyboardButton("₽ RUB")],
        [KeyboardButton("Отмена")]
    ]
    await update.message.reply_text(
        "🧮 КАЛЬКУЛЯТОР\n"
        f"{'━' * 28}\n\n"
        "Шаг 1/4: В какой валюте\n"
        "считать прибыль?\n\n"
        "💵 USD — доллары\n"
        "₽ RUB — рубли",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CALC_CURRENCY_STATE


async def calc_choose_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор: шаг 2 — выбор крипты"""
    text = update.message.text

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    if "USD" in text:
        context.user_data['calc_currency'] = 'usd'
    elif "RUB" in text:
        context.user_data['calc_currency'] = 'rub'
    else:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return CALC_CURRENCY_STATE

    currency = context.user_data['calc_currency']
    label = "💵 USD" if currency == 'usd' else "₽ RUB"

    mode = get_mode(context)
    await update.message.reply_text(
        f"🧮 Валюта: {label}\n\n"
        f"Шаг 2/4: Какой {asset_word(mode)}\n"
        f"вы покупали?",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return CALC_CRYPTO_STATE


async def calc_choose_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор: шаг 3 — цена покупки"""
    text = update.message.text.strip().upper()
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    if text not in asset_list:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return CALC_CRYPTO_STATE

    context.user_data['calc_crypto'] = text
    emoji = asset_list[text]['emoji']

    currency = context.user_data.get('calc_currency', 'usd')
    curr_sym = '$' if currency == 'usd' else '₽'

    # Показать текущую цену для справки
    data = await get_asset_price(text, mode, currency)
    price_hint = ""
    if data and data.get('price'):
        price_hint = f"\n💰 Текущая цена: {format_price(data['price'], currency)}\n"

    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🧮 {emoji} {text}{price_hint}\n"
        f"Шаг 3/4: По какой цене вы\n"
        f"покупали? (в {curr_sym})\n\n"
        f"Примеры: 100000, 3500, 0.5",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CALC_BUY_PRICE_STATE


async def calc_set_buy_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор: шаг 4 — количество"""
    text = update.message.text.strip()
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    try:
        buy_price = float(text.replace(',', '.').replace(' ', ''))
        if buy_price <= 0:
            await update.message.reply_text("❌ Цена должна быть > 0!")
            return CALC_BUY_PRICE_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return CALC_BUY_PRICE_STATE

    context.user_data['calc_buy_price'] = buy_price

    crypto = context.user_data['calc_crypto']
    currency = context.user_data.get('calc_currency', 'usd')
    curr_sym = '$' if currency == 'usd' else '₽'
    emoji = asset_list[crypto]['emoji']

    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🧮 {emoji} {crypto} по {curr_sym}{buy_price:,.2f}\n\n"
        f"Шаг 4/4: Сколько монет\n"
        f"вы купили?\n\n"
        f"Примеры: 1, 0.5, 100, 10000",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CALC_AMOUNT_STATE


async def calc_set_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор: результат"""
    text = update.message.text.strip()
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_back_keyboard(context))
        return -1

    try:
        amount = float(text.replace(',', '.').replace(' ', ''))
        if amount <= 0:
            await update.message.reply_text("❌ Количество должно быть > 0!")
            return CALC_AMOUNT_STATE
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return CALC_AMOUNT_STATE

    crypto = context.user_data['calc_crypto']
    buy_price = context.user_data['calc_buy_price']
    currency = context.user_data.get('calc_currency', 'usd')
    curr_sym = '$' if currency == 'usd' else '₽'

    msg = await update.message.reply_text("⏳ Считаю прибыль...")

    data = await get_asset_price(crypto, mode, currency)
    if not data or not data.get('price'):
        try:
            await msg.edit_text("❌ Не удалось получить текущую цену")
        except Exception:
            pass
        await update.message.reply_text("↩️ Назад:", reply_markup=get_back_keyboard(context))
        return -1

    current_price = data['price']
    emoji = asset_list[crypto]['emoji']

    invested = buy_price * amount
    current_value = current_price * amount
    profit = current_value - invested
    profit_pct = ((current_price - buy_price) / buy_price) * 100

    # Визуал
    if profit > 0:
        status = "🟢 В ПРИБЫЛИ"
        profit_icon = "📈"
        bars = min(int(profit_pct / 5), 20)
        bar_visual = "🟩" * max(bars, 1)
    elif profit < 0:
        status = "🔴 В УБЫТКЕ"
        profit_icon = "📉"
        bars = min(int(abs(profit_pct) / 5), 20)
        bar_visual = "🟥" * max(bars, 1)
    else:
        status = "⚪ БЕЗУБЫТОК"
        profit_icon = "➡️"
        bar_visual = "⬜"

    result = (
        f"🧮 КАЛЬКУЛЯТОР ПРИБЫЛИ\n"
        f"{'━' * 28}\n\n"
        f"{emoji} {asset_list[crypto]['name']} ({crypto})\n\n"
        f"💳 Цена покупки: {curr_sym}{buy_price:,.2f}\n"
        f"💰 Текущая цена: {curr_sym}{current_price:,.2f}\n"
        f"📦 Количество: {amount:g} {crypto}\n\n"
        f"{'━' * 28}\n"
        f"💼 Вложено: {curr_sym}{invested:,.2f}\n"
        f"💎 Сейчас стоит: {curr_sym}{current_value:,.2f}\n\n"
        f"{profit_icon} Прибыль: {curr_sym}{profit:+,.2f} ({profit_pct:+.2f}%)\n"
        f"📊 {status}\n"
        f"{bar_visual}\n\n"
        f"{'━' * 28}\n"
    )

    # Дополнительные расчёты
    if profit > 0:
        to_x2 = buy_price * 2
        need_for_x2 = ((to_x2 - current_price) / current_price) * 100
        if need_for_x2 > 0:
            result += f"🎯 До x2: ещё +{need_for_x2:.1f}% роста\n"
        else:
            x_multiple = current_price / buy_price
            result += f"🚀 Рост: x{x_multiple:.2f} от покупки!\n"
    else:
        need = ((buy_price - current_price) / current_price) * 100
        result += f"📈 До безубытка: нужен рост +{need:.1f}%\n"

    result += f"\n⚠️ Не является финансовым советом!"

    try:
        await msg.edit_text(result)
    except Exception:
        pass

    # Вернуть меню
    await update.message.reply_text("↩️ Назад:", reply_markup=get_back_keyboard(context))
    return -1


# ==================== 🏆 РЕЙТИНГИ ====================

def get_rankings_keyboard():
    """Меню рейтингов"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💎 По капитализации"), KeyboardButton("📈 По росту 24ч")],
        [KeyboardButton("📊 По объёму"), KeyboardButton("📉 Лузеры 24ч")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


async def show_rankings_menu(update, context):
    """Меню рейтингов"""
    mode = get_mode(context)
    al = get_asset_list(mode)
    label = asset_label(mode)
    await update.message.reply_text(
        f"🏆 РЕЙТИНГИ {label.upper()}\n"
        f"{'═' * 28}\n\n"
        f"Сортировка {len(al)} {asset_label_gen(mode)}\n"
        f"по разным параметрам:\n\n"
        f"💎 Капитализация — топ по стоимости\n"
        f"📈 Рост 24ч — лучшие за сутки\n"
        f"📊 Объём — самые торгуемые\n"
        f"📉 Лузеры — худшие за сутки",
        reply_markup=get_rankings_keyboard()
    )


async def _get_ranking_data(mode='crypto'):
    """Получить данные для рейтинга"""
    asset_list = get_asset_list(mode)
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        return None

    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0) or 0
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        cap = coin_data.get('usd_market_cap', 0) or 0
        if price > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'name': info['name'],
                'price': price,
                'change': change,
                'volume': volume,
                'cap': cap,
            })
    return items


async def show_ranking_by_cap(update, context):
    """Рейтинг по капитализации"""
    mode = get_mode(context)
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data(mode)
    if not items:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items.sort(key=lambda x: x['cap'], reverse=True)

    text = f"💎 РЕЙТИНГ ПО КАПИТАЛИЗАЦИИ\n{'━' * 28}\n\n"
    for i, item in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {item['emoji']} {item['ticker']} — {format_volume(item['cap'], 'usd')}\n"
        text += f"    ${item['price']:,.2f} ({item['change']:+.1f}%)\n"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_rankings_keyboard())


async def show_ranking_by_change(update, context):
    """Рейтинг по росту за 24ч"""
    mode = get_mode(context)
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data(mode)
    if not items:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items.sort(key=lambda x: x['change'], reverse=True)

    text = f"📈 ЛИДЕРЫ РОСТА 24Ч\n{'━' * 28}\n\n"
    for i, item in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        arrow = "🟢" if item['change'] > 0 else "🔴"
        text += f"{medal} {item['emoji']} {item['ticker']} {arrow} {item['change']:+.2f}%\n"
        text += f"    ${item['price']:,.2f}\n"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_rankings_keyboard())


async def show_ranking_by_volume(update, context):
    """Рейтинг по объёму торгов"""
    mode = get_mode(context)
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data(mode)
    if not items:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items.sort(key=lambda x: x['volume'], reverse=True)

    text = f"📊 РЕЙТИНГ ПО ОБЪЁМУ 24Ч\n{'━' * 28}\n\n"
    for i, item in enumerate(items, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {item['emoji']} {item['ticker']} — {format_volume(item['volume'], 'usd')}\n"
        text += f"    ${item['price']:,.2f} ({item['change']:+.1f}%)\n"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_rankings_keyboard())


async def show_ranking_losers(update, context):
    """Рейтинг лузеров за 24ч"""
    mode = get_mode(context)
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data(mode)
    if not items:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items.sort(key=lambda x: x['change'])

    text = f"📉 ЛУЗЕРЫ 24Ч\n{'━' * 28}\n\n"
    for i, item in enumerate(items, 1):
        skull = "💀" if i <= 3 else f"{i}."
        text += f"{skull} {item['emoji']} {item['ticker']} 🔴 {item['change']:+.2f}%\n"
        text += f"    ${item['price']:,.2f}\n"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_rankings_keyboard())


# ==================== ⭐ ИЗБРАННОЕ ====================

def get_favorites_keyboard():
    """Меню избранного"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Добавить в ⭐"), KeyboardButton("➖ Убрать из ⭐")],
        [KeyboardButton("📋 Моё избранное"), KeyboardButton("📊 Цены избранных")],
        [KeyboardButton("🗑 Очистить ⭐")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


async def show_favorites_menu(update, context):
    """Меню избранного"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    al = get_asset_list(mode)
    count = db.count_favorites(user_id, mode)
    label = asset_word_short(mode)

    await update.message.reply_text(
        f"⭐ ИЗБРАННОЕ\n"
        f"{'═' * 28}\n\n"
        f"📌 В избранном: {count} {label}\n\n"
        f"Добавляйте {asset_label_gen(mode)} в избранное\n"
        f"для быстрого доступа к ценам!\n\n"
        f"➕ Добавить в избранное\n"
        f"➖ Убрать из избранного\n"
        f"📋 Список избранных\n"
        f"📊 Цены всех избранных сразу",
        reply_markup=get_favorites_keyboard()
    )


async def favorites_add_start_msg(update, context):
    """Показать крипты для добавления в избранное"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    favorites = db.get_user_favorites(user_id, mode)

    # Показать только те, что ещё не в избранном
    available = [t for t in asset_list if t not in favorites]

    if not available:
        await update.message.reply_text(
            "✅ Все криптовалюты уже в избранном!",
            reply_markup=get_favorites_keyboard()
        )
        return

    buttons = []
    row = []
    for ticker in available:
        emoji = asset_list[ticker]['emoji']
        row.append(KeyboardButton(f"FAV+{ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("↩️ Назад")])

    text = "➕ ДОБАВИТЬ В ИЗБРАННОЕ\n"
    text += f"{'━' * 28}\n\n"
    for ticker in available:
        emoji = asset_list[ticker]['emoji']
        text += f"{emoji} {ticker} — {asset_list[ticker]['name']}\n"
    text += "\nВыберите криптовалюту:"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


async def favorites_remove_start_msg(update, context):
    """Показать избранные для удаления"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    favorites = db.get_user_favorites(user_id, mode)

    if not favorites:
        await update.message.reply_text(
            "📋 Избранное пусто!",
            reply_markup=get_favorites_keyboard()
        )
        return

    buttons = []
    row = []
    text = "➖ УБРАТЬ ИЗ ИЗБРАННОГО\n"
    text += f"{'━' * 28}\n\n"

    for ticker in favorites:
        emoji = asset_list.get(ticker, {}).get('emoji', '🪙')
        text += f"{emoji} {ticker}\n"
        row.append(KeyboardButton(f"FAV-{ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("↩️ Назад")])

    text += "\nВыберите для удаления:"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


async def show_my_favorites(update, context):
    """Показать список избранных"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    favorites = db.get_user_favorites(user_id, mode)

    if not favorites:
        await update.message.reply_text(
            "📋 Избранное пусто! Добавьте крипты ⭐",
            reply_markup=get_favorites_keyboard()
        )
        return

    text = f"⭐ МОЁ ИЗБРАННОЕ ({len(favorites)})\n{'━' * 28}\n\n"
    for ticker in favorites:
        emoji = asset_list.get(ticker, {}).get('emoji', '🪙')
        name = asset_list.get(ticker, {}).get('name', ticker)
        text += f"{emoji} {ticker} — {name}\n"

    await update.message.reply_text(text, reply_markup=get_favorites_keyboard())


async def show_favorites_prices(update, context):
    """Показать цены всех избранных"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    favorites = db.get_user_favorites(user_id, mode)

    if not favorites:
        await update.message.reply_text(
            "📋 Избранное пусто!",
            reply_markup=get_favorites_keyboard()
        )
        return

    msg = await update.message.reply_text("⏳ Загружаю цены избранных...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    text = f"📊 ЦЕНЫ ИЗБРАННЫХ\n{'━' * 28}\n\n"

    total_change = 0
    count = 0

    for ticker in favorites:
        info = asset_list.get(ticker)
        if not info:
            continue
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0)
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0

        emoji = info['emoji']
        arrow = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"

        text += f"{emoji} {ticker}: ${price:,.2f} {arrow} {change:+.2f}%\n"
        text += f"   Объём: {format_volume(volume, 'usd')}\n"

        total_change += change
        count += 1

    if count > 0:
        avg = total_change / count
        text += f"\n{'━' * 28}\n"
        text += f"📊 Среднее изменение: {avg:+.2f}%\n"
        mood = "📈 Растут" if avg > 0 else "📉 Падают"
        text += f"🏷️ Тренд: {mood}"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_favorites_keyboard())


async def clear_favorites(update, context):
    """Очистить избранное"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.clear_favorites(user_id, mode)

    if count > 0:
        await update.message.reply_text(
            f"🗑 Избранное очищено! Удалено: {count}",
            reply_markup=get_favorites_keyboard()
        )
    else:
        await update.message.reply_text(
            "📋 Избранное и так пусто!",
            reply_markup=get_favorites_keyboard()
        )


# ==================== 🔧 ДОПОЛНИТЕЛЬНОЕ МЕНЮ ====================

def get_extra_keyboard():
    """Дополнительное меню"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📰 Дайджест"), KeyboardButton("📈 Мини-график")],
        [KeyboardButton("🎯 Предсказание"), KeyboardButton("💼 Портфель")],
        [KeyboardButton("🎰 Рулетка"), KeyboardButton("💡 Совет дня")],
        [KeyboardButton("🏅 Топ-3 дня"), KeyboardButton("📰 Новости рынка")],
        [KeyboardButton("📉 Волатильность"), KeyboardButton("📊 Объём Профиль")],
        [KeyboardButton("👑 Премиум-функции")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_premium_extra_keyboard():
    """Клавиатура премиум-функций"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🧠 AI Советник"), KeyboardButton("🔎 Анализ актива")],
        [KeyboardButton("🎯 Снайпер входа"), KeyboardButton("📡 Радар аномалий")],
        [KeyboardButton("🗺 Хитмап рынка"), KeyboardButton("⏳ Машина времени")],
        [KeyboardButton("😱 Индекс Страха"), KeyboardButton("🐋 Кит-Детектор")],
        [KeyboardButton("🔬 Тех. Анализ"), KeyboardButton("📊 Корреляция")],
        [KeyboardButton("🏦 Скринер"), KeyboardButton("💎 DCA Калькулятор")],
        [KeyboardButton("🧬 Индекс Доминации")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


async def show_extra_menu(update, context):
    """Дополнительное меню"""
    mode = get_mode(context)
    label = asset_label(mode)
    await update.message.reply_text(
        f"🔧 ДОПОЛНИТЕЛЬНО\n"
        f"{'═' * 28}\n\n"
        f"📰 Дайджест — сводка рынка\n"
        f"📈 Мини-график — ASCII-визуализация\n"
        f"🎯 Предсказание — угадай направление\n"
        f"💼 Портфель — виртуальные инвестиции\n"
        f"🎰 Рулетка — случайный совет\n"
        f"💡 Совет дня — полезные советы\n\n"
        f"🆓 НОВОЕ — бесплатно:\n"
        f"🏅 Топ-3 дня — лидеры роста и падения\n"
        f"📰 Новости рынка — факты и тренды\n\n"
        f"⭐ PRO:\n"
        f"📉 Волатильность — анализ рисков\n"
        f"📊 Объём Профиль — анализ торгов\n\n"
        f"👑 Премиум-функции — эксклюзив!",
        reply_markup=get_extra_keyboard()
    )


async def show_premium_features_menu(update, context):
    """Подменю премиум-функций"""
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    status = "✅ Доступно" if tier == 'premium' else "🔒 Требуется 👑 Premium"
    await update.message.reply_text(
        f"👑 ПРЕМИУМ-ФУНКЦИИ\n"
        f"{'━' * 28}\n\n"
        f"Статус: {status}\n\n"
        f"🧠 AI Советник — покупать/продавать\n"
        f"   + анализ паттернов + прогноз рынка\n"
        f"🔎 Анализ актива — введи тикер,\n"
        f"   выбери режим (купил/покупаю)\n"
        f"🎯 Снайпер входа — топ-5 точек\n"
        f"   входа с стоп-лосс и тейк-профит\n"
        f"� Хитмап рынка — тепловая карта\n"
        f"   всех активов по изменению цен\n"
        f"⏳ Машина времени — что если бы ты\n"
        f"   вложил $X в актив N дней назад?\n"
        f"📡 Радар аномалий — детектор\n"
        f"   подозрительных движений рынка\n"
        f"�😱 Индекс Страха — настроение рынка\n"
        f"🐋 Кит-Детектор — аномалии объёмов\n"
        f"🔬 Тех. Анализ — RSI, тренды, уровни\n"
        f"📊 Корреляция — связь между активами\n"
        f"🏦 Скринер — фильтр по критериям\n"
        f"💎 DCA Калькулятор — стратегия\n"
        f"   усреднения покупок\n"
        f"🧬 Индекс Доминации — кто\n"
        f"   контролирует рынок\n\n"
        f"{'━' * 28}\n"
        f"🧠 Получи Premium: викторина (сложный)\n"
        f"🎟 Или активируй промокод",
        reply_markup=get_premium_extra_keyboard()
    )


# ==================== 📰 РЫНОЧНЫЙ ДАЙДЖЕСТ ====================

async def show_market_digest(update, context):
    """Рыночный дайджест — умная сводка"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    msg = await update.message.reply_text("⏳ Собираю дайджест рынка...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    total_cap = 0
    total_vol = 0
    btc_cap = 0

    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0) or 0
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        cap = coin_data.get('usd_market_cap', 0) or 0

        if price > 0:
            items.append({
                'ticker': ticker, 'emoji': info['emoji'],
                'price': price, 'change': change,
                'volume': volume, 'cap': cap,
            })
            total_cap += cap
            total_vol += volume
            if ticker == 'BTC':
                btc_cap = cap

    if not items:
        try:
            await msg.edit_text("❌ Нет данных")
        except Exception:
            pass
        return

    # Анализ
    changes = [i['change'] for i in items]
    avg_change = sum(changes) / len(changes)
    up = sum(1 for c in changes if c > 0)
    down = sum(1 for c in changes if c < 0)
    best = max(items, key=lambda x: x['change'])
    worst = min(items, key=lambda x: x['change'])
    most_traded = max(items, key=lambda x: x['volume'])

    # BTC доминация
    btc_dom = (btc_cap / total_cap * 100) if total_cap > 0 else 0

    # Определить настроение рынка
    if avg_change > 5:
        mood = "🔥 ЭЙФОРИЯ"
        mood_desc = "Рынок на максимумах! Осторожно с покупками."
    elif avg_change > 2:
        mood = "🚀 БЫЧИЙ РЫНОК"
        mood_desc = "Сильный рост по всему рынку."
    elif avg_change > 0.5:
        mood = "📈 ОПТИМИЗМ"
        mood_desc = "Умеренный рост, хорошее время для анализа."
    elif avg_change > -0.5:
        mood = "😐 НЕЙТРАЛЬНО"
        mood_desc = "Рынок в ожидании. Боковое движение."
    elif avg_change > -2:
        mood = "📉 ПЕССИМИЗМ"
        mood_desc = "Лёгкое давление продавцов."
    elif avg_change > -5:
        mood = "😰 СТРАХ"
        mood_desc = "Распродажа. Возможны выгодные покупки."
    else:
        mood = "🩸 ПАНИКА"
        mood_desc = "Массовая распродажа! Высокие риски."

    # Волатильность
    import statistics
    vol_idx = statistics.stdev(changes) if len(changes) > 1 else 0

    from datetime import datetime
    now = datetime.now()
    time_str = now.strftime("%d.%m.%Y %H:%M")

    text = (
        f"📰 РЫНОЧНЫЙ ДАЙДЖЕСТ\n"
        f"{'━' * 28}\n"
        f"🕐 {time_str}\n\n"
        f"🎭 Настроение: {mood}\n"
        f"💬 {mood_desc}\n\n"
        f"{'━' * 28}\n"
        f"📊 КЛЮЧЕВЫЕ МЕТРИКИ:\n\n"
        f"💎 Общая капитализация: {format_volume(total_cap, 'usd')}\n"
        f"📈 Общий объём 24ч: {format_volume(total_vol, 'usd')}\n"
        f"🟠 Доминация BTC: {btc_dom:.1f}%\n"
        f"🌊 Волатильность: {vol_idx:.1f}%\n\n"
        f"{'━' * 28}\n"
        f"🏆 ЛИДЕРЫ ДНЯ:\n\n"
        f"🚀 Лучший: {best['emoji']} {best['ticker']} ({best['change']:+.2f}%)\n"
        f"💥 Худший: {worst['emoji']} {worst['ticker']} ({worst['change']:+.2f}%)\n"
        f"🔥 Самый торгуемый: {most_traded['emoji']} {most_traded['ticker']} ({format_volume(most_traded['volume'], 'usd')})\n\n"
        f"{'━' * 28}\n"
        f"📊 ИТОГО:\n"
        f"🟢 Растут: {up} | 🔴 Падают: {down}\n"
        f"📈 Средн. изменение: {avg_change:+.2f}%\n\n"
    )

    # Рекомендация
    if avg_change > 3:
        text += "💡 Совет: рынок перегрет, будьте осторожны\nс новыми покупками. Фиксируйте прибыль.\n"
    elif avg_change > 0:
        text += "💡 Совет: умеренный рост — хорошее время\nдля выборочных покупок.\n"
    elif avg_change > -3:
        text += "💡 Совет: лёгкая коррекция — возможность\nдокупить хорошие монеты.\n"
    else:
        text += "💡 Совет: сильная коррекция — ищите\nперепроданные монеты для входа.\n"

    text += "\n⚠️ Не является финансовым советом!"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 📈 МИНИ-ГРАФИК ====================

async def show_mini_chart(update, context):
    """ASCII мини-график всех криптовалют"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    msg = await update.message.reply_text("⏳ Строю график...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        change = coin_data.get('usd_24h_change', 0) or 0
        price = coin_data.get('usd', 0) or 0
        if price > 0:
            items.append((ticker, info['emoji'], change, price))

    items.sort(key=lambda x: x[2], reverse=True)

    text = f"📈 МИНИ-ГРАФИК 24Ч\n{'━' * 28}\n\n"

    max_change = max(abs(i[2]) for i in items) if items else 1
    if max_change == 0:
        max_change = 1

    for ticker, emoji, change, price in items:
        # Нормализовать длину бара
        bar_len = int(abs(change) / max_change * 15)
        bar_len = max(1, bar_len)

        if change > 0:
            bar = "🟩" * bar_len
            sign = f"+{change:.1f}%"
        elif change < 0:
            bar = "🟥" * bar_len
            sign = f"{change:.1f}%"
        else:
            bar = "⬜"
            sign = "0.0%"

        text += f"{emoji} {ticker:>5} {bar} {sign}\n"

    text += f"\n{'━' * 28}\n"
    text += "📊 Длина бара = сила изменения за 24ч"

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 🎰 КРИПТО-РУЛЕТКА ====================

async def show_crypto_roulette(update, context):
    """Случайная рекомендация — крипто-рулетка"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    msg = await update.message.reply_text("🎰 Кручу барабан...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать доступные крипты
    available = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0)
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        cap = coin_data.get('usd_market_cap', 0) or 0
        if price and price > 0:
            available.append({
                'ticker': ticker, 'emoji': info['emoji'],
                'name': info['name'], 'price': price,
                'change': change, 'volume': volume, 'cap': cap,
            })

    if not available:
        try:
            await msg.edit_text("❌ Нет данных")
        except Exception:
            pass
        return

    # Выбрать случайную
    pick = random.choice(available)

    # Сгенерировать "совет"
    phrases_good = [
        "🌟 Звёзды говорят: стоит присмотреться!",
        "🔮 Кристальный шар показывает потенциал!",
        "🎯 Попалась интересная монета!",
        "💫 Удача указывает на эту крипту!",
        "🍀 Четырёхлистный клевер одобряет!",
    ]
    phrases_bad = [
        "💀 Рулетка предупреждает: осторожно!",
        "🌧 Облачно, возможны осадки в портфеле.",
        "⚠️ Высокий риск по мнению рулетки!",
        "🎪 Крипто-цирк: аттракцион не для слабых!",
        "🧊 Холодная монета, нуждается в разогреве.",
    ]

    if pick['change'] > 0:
        phrase = random.choice(phrases_good)
        luck = "🍀 Удача: ВЫСОКАЯ"
    else:
        phrase = random.choice(phrases_bad)
        luck = "🎲 Удача: СРЕДНЯЯ"

    # Случайный "индекс жадности"
    greed = random.randint(20, 85)
    if greed > 60:
        greed_label = "😏 Жадность"
    elif greed > 40:
        greed_label = "😐 Нейтрально"
    else:
        greed_label = "😨 Страх"

    signal, score = _analyze_signal(pick['change'], pick['volume'], pick['cap'], pick['price'])
    sig_text, _ = _signal_to_text(signal, score)

    text = (
        f"🎰 КРИПТО-РУЛЕТКА\n"
        f"{'━' * 28}\n\n"
        f"🎱 Выпало: {pick['emoji']} {pick['name']}\n"
        f"   ({pick['ticker']})\n\n"
        f"💰 Цена: ${pick['price']:,.2f}\n"
        f"📈 24ч: {pick['change']:+.2f}%\n"
        f"📊 Объём: {format_volume(pick['volume'], 'usd')}\n"
        f"💎 Кап: {format_volume(pick['cap'], 'usd')}\n\n"
        f"🤖 Сигнал: {sig_text}\n"
        f"{luck}\n"
        f"😱 Индекс страха: {greed}/100 ({greed_label})\n\n"
        f"{'━' * 28}\n"
        f"💬 {phrase}\n\n"
        f"🔄 Нажми 🎰 ещё раз для нового!\n\n"
        f"⚠️ Это развлечение, не финсовет! 😄"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 😱 ИНДЕКС СТРАХА И ЖАДНОСТИ ====================

async def show_fear_greed(update, context):
    """Индекс Страха и Жадности — рассчитанный из реальных данных рынка"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)
    msg = await update.message.reply_text("⏳ Анализирую рынок...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    changes = []
    volumes = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        change = coin_data.get('usd_24h_change')
        vol = coin_data.get('usd_24h_vol', 0) or 0
        if change is not None:
            changes.append(change)
        if vol > 0:
            volumes.append(vol)

    if not changes:
        try:
            await msg.edit_text("❌ Недостаточно данных")
        except Exception:
            pass
        return

    # Рассчитать компоненты индекса
    avg_change = sum(changes) / len(changes)
    positive = sum(1 for c in changes if c > 0)
    negative = sum(1 for c in changes if c < 0)
    ratio = positive / max(len(changes), 1) * 100

    # Волатильность (среднее абсолютных изменений)
    volatility = sum(abs(c) for c in changes) / len(changes)

    # Индекс: 0-100 (0 = экстремальный страх, 100 = экстремальная жадность)
    # Формула: средняя изменений нормализована + соотношение растущих
    score = min(100, max(0, int(50 + avg_change * 5 + (ratio - 50) * 0.3)))

    # Определить уровень
    if score <= 15:
        level = "😱 ЭКСТРЕМАЛЬНЫЙ СТРАХ"
        emoji_bar = "🔴🔴🔴🔴🔴"
        advice = "Рынок в панике! Умные деньги покупают?"
    elif score <= 30:
        level = "😰 СТРАХ"
        emoji_bar = "🟠🟠🔴🔴🔴"
        advice = "Настроения негативные. Осторожность!"
    elif score <= 45:
        level = "😟 ЛЁГКИЙ СТРАХ"
        emoji_bar = "🟡🟠🟠🔴🔴"
        advice = "Рынок напряжён, но без паники."
    elif score <= 55:
        level = "😐 НЕЙТРАЛЬНО"
        emoji_bar = "🟡🟡🟡🟡🟡"
        advice = "Рынок спокоен, боковой тренд."
    elif score <= 70:
        level = "🙂 ОПТИМИЗМ"
        emoji_bar = "🟢🟢🟡🟡🟡"
        advice = "Позитивные настроения на рынке."
    elif score <= 85:
        level = "😊 ЖАДНОСТЬ"
        emoji_bar = "🟢🟢🟢🟡🟡"
        advice = "Рынок растёт, будь осторожен с FOMO!"
    else:
        level = "🤑 ЭКСТРЕМАЛЬНАЯ ЖАДНОСТЬ"
        emoji_bar = "🟢🟢🟢🟢🟢"
        advice = "Все жадничают! Время фиксировать?"

    # Визуальная шкала
    filled = score // 10
    empty = 10 - filled
    scale = "█" * filled + "░" * empty

    # Топ рост и падение
    changes_sorted = sorted(
        [(t, data.get(info['id'], {}).get('usd_24h_change', 0) or 0)
         for t, info in asset_list.items()
         if data.get(info['id'], {}).get('usd_24h_change') is not None],
        key=lambda x: x[1], reverse=True
    )
    top_gain = changes_sorted[:3] if changes_sorted else []
    top_loss = changes_sorted[-3:] if len(changes_sorted) >= 3 else []

    top_text = ""
    for ticker, ch in top_gain:
        e = asset_list[ticker]['emoji']
        top_text += f"  🟢 {e} {ticker}: {ch:+.2f}%\n"
    top_text += "\n📉 Худшие:\n"
    for ticker, ch in top_loss:
        e = asset_list[ticker]['emoji']
        top_text += f"  🔴 {e} {ticker}: {ch:+.2f}%\n"

    text = (
        f"😱 ИНДЕКС СТРАХА И ЖАДНОСТИ\n"
        f"{'━' * 28}\n\n"
        f"{emoji_bar}\n\n"
        f"📊 Индекс: {score}/100\n"
        f"[{scale}]\n\n"
        f"🏷 Уровень: {level}\n\n"
        f"{'━' * 28}\n"
        f"📈 Компоненты:\n\n"
        f"  📊 Средн. изменение: {avg_change:+.2f}%\n"
        f"  🟢 Растут: {positive}/{len(changes)}\n"
        f"  🔴 Падают: {negative}/{len(changes)}\n"
        f"  📈 Доля роста: {ratio:.0f}%\n"
        f"  ⚡ Волатильность: {volatility:.2f}%\n\n"
        f"{'━' * 28}\n"
        f"📈 Лучшие:\n{top_text}\n"
        f"{'━' * 28}\n"
        f"💬 {advice}\n\n"
        f"⚠️ Не является финансовым советом!"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 🐋 КИТ-ДЕТЕКТОР ====================

async def show_whale_detector(update, context):
    """Кит-Детектор — поиск аномалий объёма и резких движений"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)
    msg = await update.message.reply_text("🐋 Сканирую активность китов...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать данные
    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0) or 0
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        if price > 0 and volume > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'price': price,
                'change': change,
                'volume': volume,
            })

    if not items:
        try:
            await msg.edit_text("❌ Нет данных для анализа")
        except Exception:
            pass
        return

    # Вычислить средний объём и отклонения
    avg_vol = sum(i['volume'] for i in items) / len(items)
    avg_change = sum(abs(i['change']) for i in items) / len(items)

    # Найти «китов» — аномально высокий объём или резкие движения
    whales = []
    for item in items:
        vol_ratio = item['volume'] / avg_vol if avg_vol > 0 else 0
        change_ratio = abs(item['change']) / avg_change if avg_change > 0 else 0
        whale_score = vol_ratio * 0.6 + change_ratio * 0.4

        if vol_ratio > 1.5 or change_ratio > 2.0 or whale_score > 1.8:
            item['vol_ratio'] = vol_ratio
            item['change_ratio'] = change_ratio
            item['whale_score'] = whale_score
            whales.append(item)

    whales.sort(key=lambda x: x['whale_score'], reverse=True)
    whales = whales[:10]

    text = (
        f"🐋 КИТ-ДЕТЕКТОР\n"
        f"{'━' * 28}\n\n"
        f"🔍 Анализ {len(items)} {asset_label_gen(mode)}\n"
        f"📊 Средний объём: {format_volume(avg_vol, 'usd')}\n"
        f"📈 Средн. изменение: ±{avg_change:.2f}%\n\n"
    )

    if not whales:
        text += "✅ Аномалий не обнаружено!\n\nРынок спокоен, киты отдыхают. 🐋💤"
    else:
        text += f"⚠️ Обнаружено {len(whales)} аномали{'я' if len(whales) == 1 else 'й'}:\n\n"
        for i, w in enumerate(whales, 1):
            alert_type = ""
            if w['vol_ratio'] > 3:
                alert_type = "🔥 ОГРОМНЫЙ ОБЪЁМ"
            elif w['vol_ratio'] > 2:
                alert_type = "⚡ Высокий объём"
            elif abs(w['change']) > 10:
                alert_type = "💥 Резкое движение"
            else:
                alert_type = "👀 Подозрительно"

            arrow = "🟢" if w['change'] > 0 else "🔴"
            text += (
                f"{i}. {w['emoji']} {w['ticker']} — {alert_type}\n"
                f"   {arrow} {w['change']:+.2f}% | "
                f"Объём: {format_volume(w['volume'], 'usd')}\n"
                f"   📊 Объём x{w['vol_ratio']:.1f} от среднего\n\n"
            )

    text += (
        f"\n{'━' * 28}\n"
        f"🐋 Большой объём = возможно,\n"
        f"крупные игроки двигают рынок!\n\n"
        f"⚠️ Не является финансовым советом!"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 🔬 ГЛУБОКИЙ АНАЛИЗ (PREMIUM) ====================

async def show_deep_analysis(update, context):
    """Глубокий технический анализ актива — RSI, тренды, уровни"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)
    msg = await update.message.reply_text("🔬 Провожу глубокий анализ рынка...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0) or 0
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        mcap = coin_data.get('usd_market_cap', 0) or 0
        if price > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'price': price,
                'change': change,
                'volume': volume,
                'mcap': mcap,
            })

    if len(items) < 5:
        try:
            await msg.edit_text("❌ Недостаточно данных для анализа")
        except Exception:
            pass
        return

    # === Расчёт RSI-подобного индикатора ===
    gains = [i['change'] for i in items if i['change'] > 0]
    losses = [abs(i['change']) for i in items if i['change'] < 0]
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0.01
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - (100 / (1 + rs))

    # === Определить тренд ===
    avg_change = sum(i['change'] for i in items) / len(items)
    positive_count = sum(1 for i in items if i['change'] > 0)
    ratio = positive_count / len(items) * 100

    if avg_change > 3 and ratio > 70:
        trend = "🚀 СИЛЬНЫЙ БЫЧИЙ"
        trend_emoji = "📈📈📈"
    elif avg_change > 1 and ratio > 55:
        trend = "📈 БЫЧИЙ"
        trend_emoji = "📈📈"
    elif avg_change > 0:
        trend = "↗️ СЛАБО БЫЧИЙ"
        trend_emoji = "📈"
    elif avg_change > -1:
        trend = "↘️ СЛАБО МЕДВЕЖИЙ"
        trend_emoji = "📉"
    elif avg_change > -3:
        trend = "📉 МЕДВЕЖИЙ"
        trend_emoji = "📉📉"
    else:
        trend = "💥 СИЛЬНЫЙ МЕДВЕЖИЙ"
        trend_emoji = "📉📉📉"

    # RSI уровень
    if rsi > 70:
        rsi_signal = "🔴 ПЕРЕКУПЛЕН — возможна коррекция"
    elif rsi > 60:
        rsi_signal = "🟡 Приближается к перекупленности"
    elif rsi > 40:
        rsi_signal = "🟢 НЕЙТРАЛЬНО — нет перекосов"
    elif rsi > 30:
        rsi_signal = "🟡 Приближается к перепроданности"
    else:
        rsi_signal = "🟢 ПЕРЕПРОДАН — возможен отскок!"

    # === Уровни поддержки/сопротивления ===
    sorted_by_change = sorted(items, key=lambda x: x['change'])
    support_candidates = sorted_by_change[:3]  # самые упавшие
    resist_candidates = sorted_by_change[-3:]  # самые выросшие

    # === Объёмный анализ ===
    total_vol = sum(i['volume'] for i in items)
    total_mcap = sum(i['mcap'] for i in items)
    vol_mcap_ratio = (total_vol / total_mcap * 100) if total_mcap > 0 else 0

    if vol_mcap_ratio > 15:
        vol_signal = "🔥 Очень высокая активность!"
    elif vol_mcap_ratio > 8:
        vol_signal = "⚡ Повышенная активность"
    elif vol_mcap_ratio > 3:
        vol_signal = "📊 Нормальная активность"
    else:
        vol_signal = "😴 Низкая активность"

    # === Волатильность ===
    volatility = sum(abs(i['change']) for i in items) / len(items)
    if volatility > 8:
        vol_level = "🌪 Экстремальная"
    elif volatility > 5:
        vol_level = "⚡ Высокая"
    elif volatility > 2:
        vol_level = "📊 Умеренная"
    else:
        vol_level = "😴 Низкая"

    # === Формирование отчёта ===
    support_text = ""
    for s in support_candidates:
        support_text += f"  🟢 {s['emoji']} {s['ticker']}: ${format_price(s['price'])} ({s['change']:+.2f}%)\n"

    resist_text = ""
    for r in reversed(resist_candidates):
        resist_text += f"  🔴 {r['emoji']} {r['ticker']}: ${format_price(r['price'])} ({r['change']:+.2f}%)\n"

    # RSI шкала
    rsi_filled = int(rsi // 10)
    rsi_empty = 10 - rsi_filled
    rsi_bar = "█" * rsi_filled + "░" * rsi_empty

    text = (
        f"🔬 ГЛУБОКИЙ АНАЛИЗ РЫНКА\n"
        f"{'━' * 28}\n\n"
        f"📊 Анализ {len(items)} {asset_label_gen(mode)}\n\n"
        f"{'━' * 28}\n"
        f"📈 ТРЕНД: {trend}\n"
        f"{trend_emoji}\n\n"
        f"  📊 Средн. изменение: {avg_change:+.2f}%\n"
        f"  🟢 Растут: {positive_count}/{len(items)} ({ratio:.0f}%)\n\n"
        f"{'━' * 28}\n"
        f"📉 RSI РЫНКА: {rsi:.0f}\n"
        f"[{rsi_bar}]\n"
        f"{rsi_signal}\n\n"
        f"{'━' * 28}\n"
        f"🛡 УРОВНИ ПОДДЕРЖКИ (падают):\n"
        f"{support_text}\n"
        f"🚧 УРОВНИ СОПРОТИВЛЕНИЯ (растут):\n"
        f"{resist_text}\n"
        f"{'━' * 28}\n"
        f"📊 ОБЪЁМНЫЙ АНАЛИЗ:\n"
        f"  💰 Общий объём: {format_volume(total_vol, 'usd')}\n"
        f"  📈 Объём/Капитал: {vol_mcap_ratio:.2f}%\n"
        f"  {vol_signal}\n\n"
        f"{'━' * 28}\n"
        f"🌪 ВОЛАТИЛЬНОСТЬ: {vol_level}\n"
        f"  ±{volatility:.2f}% средн. колебание\n\n"
        f"{'━' * 28}\n"
        f"⚠️ Не является финансовым советом!"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 📊 КОРРЕЛЯЦИЯ АКТИВОВ (PREMIUM) ====================

async def show_correlation(update, context):
    """Показать корреляцию между активами на основе 24h изменений"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)
    msg = await update.message.reply_text("📊 Вычисляю корреляции...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собираем данные с изменениями
    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        change = coin_data.get('usd_24h_change')
        volume = coin_data.get('usd_24h_vol', 0) or 0
        if change is not None and volume > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'change': change,
                'volume': volume,
            })

    if len(items) < 5:
        try:
            await msg.edit_text("❌ Недостаточно данных для анализа корреляций")
        except Exception:
            pass
        return

    # Сортируем по объёму — берём топ-10 по ликвидности
    items.sort(key=lambda x: x['volume'], reverse=True)
    top_items = items[:10]

    # Рассчитываем «корреляцию» — группируем по направлению и величине
    avg_change = sum(i['change'] for i in top_items) / len(top_items)

    # Группы по поведению
    strong_up = [i for i in top_items if i['change'] > avg_change + 2]
    with_market = [i for i in top_items if abs(i['change'] - avg_change) <= 2]
    strong_down = [i for i in top_items if i['change'] < avg_change - 2]

    # Найти пары с похожим движением (высокая корреляция)
    pairs_similar = []
    pairs_opposite = []
    for i in range(len(top_items)):
        for j in range(i + 1, len(top_items)):
            diff = abs(top_items[i]['change'] - top_items[j]['change'])
            if diff < 1.0:
                pairs_similar.append((top_items[i], top_items[j], diff))
            elif (top_items[i]['change'] > 0) != (top_items[j]['change'] > 0) and diff > 5:
                pairs_opposite.append((top_items[i], top_items[j], diff))

    pairs_similar.sort(key=lambda x: x[2])
    pairs_opposite.sort(key=lambda x: x[2], reverse=True)

    text = (
        f"📊 КОРРЕЛЯЦИЯ АКТИВОВ\n"
        f"{'━' * 28}\n\n"
        f"🔍 Анализ топ-{len(top_items)} {asset_label_gen(mode)}\n"
        f"📈 Средний рынок: {avg_change:+.2f}%\n\n"
    )

    # Высокая корреляция
    text += f"{'━' * 28}\n🔗 ДВИЖУТСЯ ВМЕСТЕ:\n\n"
    if pairs_similar[:5]:
        for a, b, diff in pairs_similar[:5]:
            text += (
                f"  {a['emoji']} {a['ticker']} ({a['change']:+.1f}%)\n"
                f"  ↔️ {b['emoji']} {b['ticker']} ({b['change']:+.1f}%)\n"
                f"  📏 Разница: {diff:.2f}%\n\n"
            )
    else:
        text += "  Нет активов с похожим движением\n\n"

    # Обратная корреляция
    text += f"{'━' * 28}\n🔀 ДВИЖУТСЯ ВРОЗЬ:\n\n"
    if pairs_opposite[:3]:
        for a, b, diff in pairs_opposite[:3]:
            text += (
                f"  {a['emoji']} {a['ticker']} ({a['change']:+.1f}%)\n"
                f"  🔄 {b['emoji']} {b['ticker']} ({b['change']:+.1f}%)\n"
                f"  📏 Разница: {diff:.2f}%\n\n"
            )
    else:
        text += "  Нет активов с противоположным движением\n\n"

    # Группы
    text += f"{'━' * 28}\n📋 ГРУППЫ:\n\n"
    if strong_up:
        text += "🚀 Лидеры роста:\n"
        for i in strong_up:
            text += f"  {i['emoji']} {i['ticker']}: {i['change']:+.2f}%\n"
        text += "\n"
    if with_market:
        text += "📊 Идут с рынком:\n"
        for i in with_market:
            text += f"  {i['emoji']} {i['ticker']}: {i['change']:+.2f}%\n"
        text += "\n"
    if strong_down:
        text += "📉 Аутсайдеры:\n"
        for i in strong_down:
            text += f"  {i['emoji']} {i['ticker']}: {i['change']:+.2f}%\n"
        text += "\n"

    text += (
        f"{'━' * 28}\n"
        f"💡 Похожее движение = высокая\n"
        f"корреляция. Полезно для\n"
        f"диверсификации портфеля!\n\n"
        f"⚠️ Не является финансовым советом!"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 🏦 СКРИНЕР РЫНКА (PREMIUM) ====================

async def show_screener(update, context):
    """Скринер — фильтрация активов по критериям"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)
    msg = await update.message.reply_text("🏦 Сканирую рынок по критериям...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0) or 0
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        mcap = coin_data.get('usd_market_cap', 0) or 0
        if price > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'price': price,
                'change': change,
                'volume': volume,
                'mcap': mcap,
            })

    if len(items) < 3:
        try:
            await msg.edit_text("❌ Недостаточно данных")
        except Exception:
            pass
        return

    # === СКРИНЕР: разные фильтры ===

    # 1. Топ-5 по росту
    top_gainers = sorted(items, key=lambda x: x['change'], reverse=True)[:5]
    # 2. Топ-5 по падению
    top_losers = sorted(items, key=lambda x: x['change'])[:5]
    # 3. Топ-5 по объёму
    top_volume = sorted(items, key=lambda x: x['volume'], reverse=True)[:5]
    # 4. «Недооценённые» — упали, но с высоким объёмом (сильный интерес)
    undervalued = sorted(
        [i for i in items if i['change'] < -2 and i['volume'] > sum(x['volume'] for x in items) / len(items)],
        key=lambda x: x['volume'], reverse=True
    )[:5]
    # 5. «Горячие» — сильный рост + высокий объём
    hot = sorted(
        [i for i in items if i['change'] > 2 and i['volume'] > sum(x['volume'] for x in items) / len(items)],
        key=lambda x: x['change'] * x['volume'], reverse=True
    )[:5]

    text = (
        f"🏦 СКРИНЕР РЫНКА\n"
        f"{'━' * 28}\n\n"
        f"📊 Проанализировано: {len(items)} {asset_label_gen(mode)}\n\n"
    )

    # Топ рост
    text += f"{'━' * 28}\n🚀 ТОП РОСТ:\n\n"
    for i, g in enumerate(top_gainers, 1):
        text += f"  {i}. {g['emoji']} {g['ticker']}: {g['change']:+.2f}%\n     💰 ${format_price(g['price'])}\n"
    text += "\n"

    # Топ падение
    text += f"{'━' * 28}\n📉 ТОП ПАДЕНИЕ:\n\n"
    for i, l in enumerate(top_losers, 1):
        text += f"  {i}. {l['emoji']} {l['ticker']}: {l['change']:+.2f}%\n     💰 ${format_price(l['price'])}\n"
    text += "\n"

    # Топ объём
    text += f"{'━' * 28}\n💎 ТОП ОБЪЁМ:\n\n"
    for i, v in enumerate(top_volume, 1):
        text += f"  {i}. {v['emoji']} {v['ticker']}: {format_volume(v['volume'], 'usd')}\n     📈 {v['change']:+.2f}%\n"
    text += "\n"

    # Горячие
    if hot:
        text += f"{'━' * 28}\n🔥 ГОРЯЧИЕ (рост + объём):\n\n"
        for i, h in enumerate(hot, 1):
            text += f"  {i}. {h['emoji']} {h['ticker']}: {h['change']:+.2f}% | {format_volume(h['volume'], 'usd')}\n"
        text += "\n"

    # Недооценённые
    if undervalued:
        text += f"{'━' * 28}\n💡 ВНИМАНИЕ (падение + объём):\n\n"
        for i, u in enumerate(undervalued, 1):
            text += f"  {i}. {u['emoji']} {u['ticker']}: {u['change']:+.2f}% | {format_volume(u['volume'], 'usd')}\n"
        text += "\n"

    text += (
        f"{'━' * 28}\n"
        f"🔥 = сильный рост с объёмом\n"
        f"💡 = падение с интересом крупных\n\n"
        f"⚠️ Не является финансовым советом!"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 🧠 AI СОВЕТНИК (PREMIUM) ====================

async def show_ai_advisor(update, context):
    """AI Советник — анализ рынка: что покупать, что продавать, прогноз"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)
    msg = await update.message.reply_text("🧠 AI анализирует рынок...\n⏳ Это может занять пару секунд")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собираем полные данные по каждому активу
    items = []
    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get('usd', 0) or 0
        change = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        mcap = coin_data.get('usd_market_cap', 0) or 0
        if price > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'price': price,
                'change': change,
                'volume': volume,
                'mcap': mcap,
            })

    if len(items) < 5:
        try:
            await msg.edit_text("❌ Недостаточно данных для анализа")
        except Exception:
            pass
        return

    # === ГЛУБОКИЙ АНАЛИЗ КАЖДОГО АКТИВА ===
    avg_change = sum(i['change'] for i in items) / len(items)
    avg_vol = sum(i['volume'] for i in items) / len(items)
    avg_mcap = sum(i['mcap'] for i in items if i['mcap'] > 0) / max(1, sum(1 for i in items if i['mcap'] > 0))

    scored_items = []
    for item in items:
        score = 0
        reasons = []

        ch = item['change']
        vol = item['volume']
        mcap = item['mcap']
        vol_ratio = vol / avg_vol if avg_vol > 0 else 1
        mcap_vol = (vol / mcap * 100) if mcap > 0 else 0

        # --- Паттерн 1: Сильное падение + высокий объём = «умные деньги» покупают ---
        if ch < -8 and vol_ratio > 1.5:
            score += 35
            reasons.append("💎 Сильное падение + аномальный объём → возможен отскок")
        elif ch < -5 and vol_ratio > 1.2:
            score += 20
            reasons.append("📉 Падение с повышенным интересом → потенциал отскока")
        elif ch < -3:
            score += 5
            reasons.append("↘️ Умеренная коррекция")

        # --- Паттерн 2: Устойчивый рост с объёмом = тренд ---
        if ch > 5 and vol_ratio > 1.3:
            score += 25
            reasons.append("🚀 Сильный рост подкреплён объёмом")
        elif ch > 3 and vol_ratio > 1.0:
            score += 15
            reasons.append("📈 Стабильный рост с нормальным объёмом")
        elif ch > 8 and vol_ratio < 0.7:
            score -= 15
            reasons.append("⚠️ Рост на низком объёме — слабый тренд")

        # --- Паттерн 3: Перекупленность / Перепроданность ---
        if ch > 15:
            score -= 20
            reasons.append("🔴 Перекуплен! Вероятна коррекция вниз")
        elif ch > 10:
            score -= 10
            reasons.append("🟡 Приближение к перекупленности")
        elif ch < -15:
            score += 25
            reasons.append("🟢 Перепродан! Возможен сильный отскок")
        elif ch < -10:
            score += 15
            reasons.append("📊 Глубокая коррекция — зона интереса")

        # --- Паттерн 4: Объём к капитализации (активность) ---
        if mcap_vol > 20:
            extra = 15 if ch > 0 else -10
            score += extra
            reasons.append("⚡ Экстремальная торговая активность")
        elif mcap_vol > 10:
            extra = 10 if ch > 0 else -5
            score += extra
            reasons.append("📊 Повышенная активность")
        elif mcap_vol < 2:
            score -= 5
            reasons.append("😴 Низкая ликвидность")

        # --- Паттерн 5: Движение против рынка ---
        if avg_change < -2 and ch > 3:
            score += 20
            reasons.append("💪 Растёт ПРОТИВ падающего рынка!")
        elif avg_change > 2 and ch < -3:
            score -= 15
            reasons.append("😰 Падает при растущем рынке")

        # --- Паттерн 6: Крупная капитализация = стабильность ---
        if mcap > avg_mcap * 3:
            if score > 0:
                score += 5
            reasons.append("🏛 Крупный актив — больше стабильности")
        elif mcap < avg_mcap * 0.1 and mcap > 0:
            reasons.append("⚡ Мелкий актив — выше риск и потенциал")

        # Определить рекомендацию
        if score >= 30:
            action = "🟢 ПОКУПАТЬ"
            confidence = min(95, 60 + score // 2)
        elif score >= 15:
            action = "🟡 РАССМОТРЕТЬ"
            confidence = min(75, 45 + score)
        elif score <= -20:
            action = "🔴 ПРОДАВАТЬ"
            confidence = min(90, 50 + abs(score) // 2)
        elif score <= -5:
            action = "🟠 ОСТОРОЖНО"
            confidence = min(70, 40 + abs(score))
        else:
            action = "⚪ ДЕРЖАТЬ"
            confidence = 40

        item['score'] = score
        item['action'] = action
        item['confidence'] = confidence
        item['reasons'] = reasons[:3]  # максимум 3 причины
        scored_items.append(item)

    # === СОРТИРОВКА: лучшие для покупки и продажи ===
    buy_picks = sorted([i for i in scored_items if i['score'] >= 15], key=lambda x: x['score'], reverse=True)[:5]
    sell_picks = sorted([i for i in scored_items if i['score'] <= -5], key=lambda x: x['score'])[:5]
    watch_picks = sorted([i for i in scored_items if -5 < i['score'] < 15], key=lambda x: abs(x['change']), reverse=True)[:3]

    # === РЫНОЧНЫЙ ПРОГНОЗ ===
    positive_count = sum(1 for i in scored_items if i['change'] > 0)
    negative_count = sum(1 for i in scored_items if i['change'] < 0)
    ratio = positive_count / max(len(scored_items), 1) * 100

    # Анализ «импульса» рынка
    strong_up = sum(1 for i in scored_items if i['change'] > 5)
    strong_down = sum(1 for i in scored_items if i['change'] < -5)
    volatility = sum(abs(i['change']) for i in scored_items) / len(scored_items)

    if avg_change > 3 and ratio > 70 and strong_up > strong_down * 2:
        forecast = "🚀 БЫЧИЙ РЫНОК"
        forecast_detail = "Большинство активов растёт, объёмы подтверждают. Вероятно продолжение роста в краткосроке."
        forecast_bar = "🟢🟢🟢🟢🟢"
    elif avg_change > 1 and ratio > 55:
        forecast = "📈 УМЕРЕННЫЙ РОСТ"
        forecast_detail = "Рынок растёт, но без агрессии. Хорошее время для точечных покупок."
        forecast_bar = "🟢🟢🟢🟡🟡"
    elif avg_change > -1 and ratio > 40:
        forecast = "➡️ БОКОВИК"
        forecast_detail = "Рынок в неопределённости. Лучше подождать или торговать осторожно."
        forecast_bar = "🟡🟡🟡🟡🟡"
    elif avg_change > -3 and ratio > 25:
        forecast = "📉 КОРРЕКЦИЯ"
        forecast_detail = "Рынок снижается. Возможны хорошие точки входа для долгосрока."
        forecast_bar = "🟠🟠🟠🔴🔴"
    else:
        forecast = "💥 СИЛЬНОЕ ПАДЕНИЕ"
        forecast_detail = "Рынок в панике. Высокий риск, но и потенциал для покупки на дне."
        forecast_bar = "🔴🔴🔴🔴🔴"

    # === ФОРМИРУЕМ ОТЧЁТ ===
    text = (
        f"🧠 AI СОВЕТНИК\n"
        f"{'━' * 28}\n\n"
        f"📊 Проанализировано: {len(scored_items)} {asset_label_gen(mode)}\n\n"
    )

    # Прогноз рынка
    text += (
        f"{'━' * 28}\n"
        f"🔮 ПРОГНОЗ РЫНКА:\n\n"
        f"{forecast_bar}\n"
        f"{forecast}\n\n"
        f"📊 Средн. движение: {avg_change:+.2f}%\n"
        f"🟢 Растут: {positive_count} | 🔴 Падают: {negative_count}\n"
        f"⚡ Волатильность: {volatility:.2f}%\n\n"
        f"💬 {forecast_detail}\n\n"
    )

    # ТОП покупка
    text += f"{'━' * 28}\n✅ РЕКОМЕНДАЦИИ К ПОКУПКЕ:\n\n"
    if buy_picks:
        for i, p in enumerate(buy_picks, 1):
            text += (
                f"{i}. {p['emoji']} {p['ticker']} — {p['action']}\n"
                f"   💰 ${format_price(p['price'])} | {p['change']:+.2f}%\n"
                f"   📊 Уверенность: {p['confidence']}%\n"
            )
            for r in p['reasons']:
                text += f"   {r}\n"
            text += "\n"
    else:
        text += "   Нет явных сигналов к покупке сейчас\n\n"

    # ТОП продажа
    text += f"{'━' * 28}\n❌ РЕКОМЕНДАЦИИ К ПРОДАЖЕ:\n\n"
    if sell_picks:
        for i, p in enumerate(sell_picks, 1):
            text += (
                f"{i}. {p['emoji']} {p['ticker']} — {p['action']}\n"
                f"   💰 ${format_price(p['price'])} | {p['change']:+.2f}%\n"
                f"   📊 Уверенность: {p['confidence']}%\n"
            )
            for r in p['reasons']:
                text += f"   {r}\n"
            text += "\n"
    else:
        text += "   Нет явных сигналов к продаже сейчас\n\n"

    # На наблюдении
    if watch_picks:
        text += f"{'━' * 28}\n👀 НА НАБЛЮДЕНИИ:\n\n"
        for p in watch_picks:
            text += f"  {p['emoji']} {p['ticker']}: {p['change']:+.2f}% — {p['action']}\n"
        text += "\n"

    # Итого
    total_buy = sum(1 for i in scored_items if i['score'] >= 15)
    total_sell = sum(1 for i in scored_items if i['score'] <= -5)
    total_hold = len(scored_items) - total_buy - total_sell

    text += (
        f"{'━' * 28}\n"
        f"📋 ИТОГО:\n"
        f"  ✅ Покупать: {total_buy}\n"
        f"  ❌ Продавать: {total_sell}\n"
        f"  ⚪ Держать: {total_hold}\n\n"
        f"{'━' * 28}\n"
        f"💡 Анализ основан на:\n"
        f"  • Движение цены 24ч\n"
        f"  • Объёмы торгов\n"
        f"  • Паттерны отскоков\n"
        f"  • Поведение против рынка\n"
        f"  • Активность крупных игроков\n\n"
        f"⚠️ Это приблизительный анализ!\n"
        f"Не является финансовым советом."
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_premium_extra_keyboard())


# ==================== 🔎 АНАЛИЗ АКТИВА (PREMIUM) ====================

async def asset_analysis_start(update, context):
    """Начало анализа конкретного актива — спросить тикер"""
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    if tier != 'premium':
        await sub_blocked(update, "Анализ актива", "premium")
        return ConversationHandler.END

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    # Показать список доступных тикеров
    tickers = list(asset_list.keys())
    cols = 5
    ticker_lines = []
    for i in range(0, len(tickers), cols):
        ticker_lines.append("  ".join(tickers[i:i+cols]))
    ticker_text = "\n".join(ticker_lines)

    await update.message.reply_text(
        f"🔎 АНАЛИЗ АКТИВА\n"
        f"{'━' * 28}\n\n"
        f"Введи тикер {asset_label_gen(mode)}\n"
        f"для глубокого анализа:\n\n"
        f"{ticker_text}\n\n"
        f"📝 Например: BTC, ETH, AAPL...\n\n"
        f"Отправь тикер или нажми ↩️ Назад",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("↩️ Назад")]],
            resize_keyboard=True
        )
    )
    return ASSET_ANALYSIS_STATE


async def asset_analysis_choose_mode(update, context):
    """Пользователь ввёл тикер — теперь спросить: купил / хочу купить / просто анализ"""
    text = update.message.text.strip().upper()
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text == "↩️ НАЗАД":
        await show_premium_features_menu(update, context)
        return ConversationHandler.END

    # Поиск тикера
    ticker = None
    if text in asset_list:
        ticker = text
    else:
        for t, info in asset_list.items():
            if text == t or text.lower() == info['name'].lower():
                ticker = t
                break

    if not ticker:
        await update.message.reply_text(
            f"❌ Актив «{text}» не найден!\n\n"
            f"Введи корректный тикер из списка\n"
            f"или нажми ↩️ Назад",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("↩️ Назад")]],
                resize_keyboard=True
            )
        )
        return ASSET_ANALYSIS_STATE

    # Сохраняем тикер для следующего шага
    context.user_data['analysis_ticker'] = ticker

    info = asset_list[ticker]
    await update.message.reply_text(
        f"🔎 Выбран: {info['emoji']} {ticker} ({info['name']})\n\n"
        f"Какой у тебя сценарий?\n\n"
        f"🛒 Собираюсь купить — планирую вход\n"
        f"📦 Уже купил — ищу что делать дальше\n"
        f"🔍 Просто анализ — общая картина\n",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🛒 Собираюсь купить")],
            [KeyboardButton("📦 Уже купил")],
            [KeyboardButton("🔍 Просто анализ")],
            [KeyboardButton("↩️ Назад")]
        ], resize_keyboard=True)
    )
    return ASSET_ANALYSIS_MODE_STATE


async def asset_analysis_process(update, context):
    """Обработка выбранного режима и полный анализ"""
    text = update.message.text.strip()
    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    if text == "↩️ Назад":
        await show_premium_features_menu(update, context)
        return ConversationHandler.END

    # Определяем режим анализа
    if "Собираюсь купить" in text:
        analysis_mode = "buy_planning"
    elif "Уже купил" in text:
        analysis_mode = "already_bought"
    elif "Просто анализ" in text:
        analysis_mode = "general"
    else:
        await update.message.reply_text(
            "Выбери один из вариантов:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("🛒 Собираюсь купить")],
                [KeyboardButton("📦 Уже купил")],
                [KeyboardButton("🔍 Просто анализ")],
                [KeyboardButton("↩️ Назад")]
            ], resize_keyboard=True)
        )
        return ASSET_ANALYSIS_MODE_STATE

    ticker = context.user_data.get('analysis_ticker')
    if not ticker or ticker not in asset_list:
        await update.message.reply_text("❌ Ошибка. Начни анализ заново.")
        await show_premium_features_menu(update, context)
        return ConversationHandler.END

    info = asset_list[ticker]
    msg = await update.message.reply_text(
        f"🔎 Анализирую {info['emoji']} {ticker}...\n"
        f"⏳ Загружаю историю цен..."
    )

    # === Загрузить текущие данные ===
    data = await fetch_asset_prices(mode, 'usd')
    coin_data = data.get(info['id'], {}) if data else {}
    price = coin_data.get('usd', 0) or 0
    change_24h = coin_data.get('usd_24h_change', 0) or 0
    volume = coin_data.get('usd_24h_vol', 0) or 0
    mcap = coin_data.get('usd_market_cap', 0) or 0

    if price == 0:
        try:
            await msg.edit_text(f"❌ Нет данных по {ticker}")
        except Exception:
            pass
        await show_premium_features_menu(update, context)
        return ConversationHandler.END

    # === Загрузить историю цен (30 дней) ===
    if mode == 'stocks':
        history = await stocks_api.fetch_stock_history(ticker, days=30)
    else:
        history = await fetch_crypto_history(info['id'], days=30)

    # === АНАЛИЗ ИСТОРИИ ===
    has_history = len(history) >= 5

    if has_history:
        prices = history
        current = prices[-1]
        high_30d = max(prices)
        low_30d = min(prices)
        avg_30d = sum(prices) / len(prices)
        start_30d = prices[0]

        change_30d = ((current - start_30d) / start_30d * 100) if start_30d > 0 else 0

        price_range = high_30d - low_30d
        position = ((current - low_30d) / price_range * 100) if price_range > 0 else 50

        daily_changes = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                dc = ((prices[i] - prices[i-1]) / prices[i-1]) * 100
                daily_changes.append(dc)

        avg_daily_change = sum(daily_changes) / len(daily_changes) if daily_changes else 0
        volatility = sum(abs(d) for d in daily_changes) / len(daily_changes) if daily_changes else 0

        if len(prices) >= 7:
            last_7 = prices[-7:]
            trend_7d = ((last_7[-1] - last_7[0]) / last_7[0] * 100) if last_7[0] > 0 else 0
        else:
            trend_7d = change_24h

        if len(prices) >= 14:
            first_half = prices[-14:-7]
            second_half = prices[-7:]
            change_first = ((first_half[-1] - first_half[0]) / first_half[0] * 100) if first_half[0] > 0 else 0
            change_second = ((second_half[-1] - second_half[0]) / second_half[0] * 100) if second_half[0] > 0 else 0
            momentum = change_second - change_first
        else:
            momentum = 0

        if len(daily_changes) >= 14:
            gains_14 = [d for d in daily_changes[-14:] if d > 0]
            losses_14 = [abs(d) for d in daily_changes[-14:] if d < 0]
            avg_gain = sum(gains_14) / 14
            avg_loss = sum(losses_14) / 14
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            else:
                rsi = 100
        else:
            gains = [d for d in daily_changes if d > 0]
            losses = [abs(d) for d in daily_changes if d < 0]
            avg_g = sum(gains) / max(len(gains), 1)
            avg_l = sum(losses) / max(len(losses), 1)
            if avg_l > 0:
                rsi = 100 - (100 / (1 + avg_g / avg_l))
            else:
                rsi = 70

        green_days = sum(1 for d in daily_changes if d > 0)
        red_days = sum(1 for d in daily_changes if d < 0)

        recent = prices[-14:] if len(prices) >= 14 else prices
        support = min(recent)
        resistance = max(recent)

        dist_to_support = ((current - support) / current * 100) if current > 0 else 0
        dist_to_resistance = ((resistance - current) / current * 100) if current > 0 else 0

        dips_count = 0
        recovered_count = 0
        for i in range(2, len(prices)):
            drop = ((prices[i-1] - prices[i-2]) / prices[i-2] * 100) if prices[i-2] > 0 else 0
            bounce = ((prices[i] - prices[i-1]) / prices[i-1] * 100) if prices[i-1] > 0 else 0
            if drop < -3:
                dips_count += 1
                if bounce > 1:
                    recovered_count += 1

        # === Дополнительно: SMA (простые скользящие средние) ===
        sma_7 = sum(prices[-7:]) / min(7, len(prices)) if len(prices) >= 7 else current
        sma_14 = sum(prices[-14:]) / min(14, len(prices)) if len(prices) >= 14 else current
        sma_30 = avg_30d

        # Максимальная просадка за 30д
        peak = prices[0]
        max_drawdown = 0
        for p in prices:
            if p > peak:
                peak = p
            dd = ((peak - p) / peak * 100) if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

    # === ВЫЧИСЛИТЬ РЕКОМЕНДАЦИЮ ===
    score = 0
    reasons = []

    if has_history:
        # 1) RSI
        if rsi > 75:
            score -= 25
            reasons.append(f"🔴 RSI = {rsi:.0f} (перекуплен, вероятна коррекция)")
        elif rsi > 65:
            score -= 10
            reasons.append(f"🟡 RSI = {rsi:.0f} (приближается к перекупленности)")
        elif rsi < 25:
            score += 30
            reasons.append(f"🟢 RSI = {rsi:.0f} (сильно перепродан, возможен отскок!)")
        elif rsi < 35:
            score += 20
            reasons.append(f"🟢 RSI = {rsi:.0f} (перепродан, хороший вход)")
        else:
            reasons.append(f"⚪ RSI = {rsi:.0f} (нейтральная зона)")

        # 2) Позиция в 30-дневном диапазоне
        if position < 20:
            score += 20
            reasons.append(f"💎 Цена у 30д минимума ({position:.0f}% от диапазона)")
        elif position < 35:
            score += 10
            reasons.append(f"📉 Цена ниже среднего ({position:.0f}% от диапазона)")
        elif position > 85:
            score -= 15
            reasons.append(f"🔴 Цена у 30д максимума ({position:.0f}% от диапазона)")
        elif position > 70:
            score -= 5
            reasons.append(f"🟡 Цена выше среднего ({position:.0f}% от диапазона)")

        # 3) Импульс
        if momentum > 5:
            score += 15
            reasons.append(f"🚀 Ускорение роста (импульс +{momentum:.1f}%)")
        elif momentum > 2:
            score += 8
            reasons.append(f"📈 Положительный импульс (+{momentum:.1f}%)")
        elif momentum < -5:
            score -= 10
            reasons.append(f"📉 Сильное замедление (импульс {momentum:.1f}%)")
        elif momentum < -2:
            score -= 5
            reasons.append(f"↘️ Замедление тренда ({momentum:.1f}%)")

        # 4) Тренд 7д
        if trend_7d > 10:
            score += 10
            reasons.append(f"📈 Сильный рост за 7д: +{trend_7d:.1f}%")
        elif trend_7d > 3:
            score += 5
            reasons.append(f"📈 Рост за 7д: +{trend_7d:.1f}%")
        elif trend_7d < -10:
            score += 5
            reasons.append(f"📉 Сильное падение за 7д: {trend_7d:.1f}% (возможен отскок)")
        elif trend_7d < -3:
            score -= 5
            reasons.append(f"📉 Падение за 7д: {trend_7d:.1f}%")

        # 5) Паттерн восстановления
        if dips_count > 0:
            recovery_rate = recovered_count / dips_count * 100
            if recovery_rate > 60:
                score += 10
                reasons.append(f"💪 Хорошо восстанавливается ({recovered_count}/{dips_count} отскоков)")
            elif recovery_rate < 30:
                score -= 5
                reasons.append(f"😰 Плохое восстановление ({recovered_count}/{dips_count})")

        # 6) SMA позиция
        if current > sma_7 > sma_14:
            score += 8
            reasons.append("📊 Цена выше SMA7 и SMA14 — бычий каскад")
        elif current < sma_7 < sma_14:
            score -= 8
            reasons.append("📊 Цена ниже SMA7 и SMA14 — медвежий каскад")

        # 7) Близость к поддержке/сопротивлению
        if dist_to_support < 3:
            score += 10
            reasons.append(f"🛡 Цена близко к поддержке (${format_price(support)})")
        elif dist_to_resistance < 3:
            score -= 5
            reasons.append(f"🚧 Цена близко к сопротивлению (${format_price(resistance)})")

    # Текущие данные (24ч)
    if change_24h > 10:
        score -= 10
        reasons.append(f"⚠️ Рост {change_24h:+.1f}% за 24ч — возможна коррекция")
    elif change_24h > 5:
        score += 5
        reasons.append(f"📈 Хороший рост за 24ч: {change_24h:+.1f}%")
    elif change_24h < -10:
        score += 15
        reasons.append(f"💎 Сильное падение за 24ч: {change_24h:.1f}% — возможен отскок")
    elif change_24h < -5:
        score += 5
        reasons.append(f"📉 Падение за 24ч: {change_24h:.1f}% — наблюдай")

    if volume > 0 and mcap > 0:
        vol_ratio = volume / mcap * 100
        if vol_ratio > 15 and change_24h > 0:
            score += 10
            reasons.append("🔥 Огромный объём на росте — сильный интерес")
        elif vol_ratio > 15 and change_24h < 0:
            score -= 5
            reasons.append("⚠️ Огромный объём на падении — паника?")

    # === ОПРЕДЕЛИТЬ РЕКОМЕНДАЦИЮ ===
    if score >= 30:
        action = "🟢 ПОКУПАТЬ"
        action_detail = "Сильные сигналы на покупку! Хорошая точка входа."
        action_emoji = "✅"
    elif score >= 15:
        action = "🟡 РАССМОТРЕТЬ ПОКУПКУ"
        action_detail = "Есть потенциал для роста. Можно рассмотреть позицию."
        action_emoji = "🔄"
    elif score <= -20:
        action = "🔴 ПРОДАВАТЬ"
        action_detail = "Сильные сигналы к продаже. Стоит зафиксировать прибыль."
        action_emoji = "❌"
    elif score <= -5:
        action = "🟠 ОСТОРОЖНО"
        action_detail = "Есть негативные сигналы. Лучше подождать."
        action_emoji = "⚠️"
    else:
        action = "⚪ ДЕРЖАТЬ"
        action_detail = "Нет явных сигналов. Подожди более чётких движений."
        action_emoji = "⏸️"

    confidence = min(95, max(25, 50 + abs(score)))

    # === СОВЕТЫ В ЗАВИСИМОСТИ ОТ РЕЖИМА ===
    tips = []

    if analysis_mode == "buy_planning":
        # === РЕЖИМ: СОБИРАЮСЬ КУПИТЬ ===
        tips.append("🛒 СОВЕТЫ ДЛЯ ПОКУПКИ:\n")
        if has_history:
            # Оптимальная цена входа
            if position > 60:
                tips.append(f"⏳ Цена высоко в диапазоне — дождись отката к ~${format_price(avg_30d)}")
            elif position < 30:
                tips.append(f"🎯 Цена в зоне скидки — хороший момент для входа!")
            else:
                tips.append(f"📊 Цена в средней зоне — можно входить частично")

            # Стоп-лосс рекомендация
            sl_price = support * 0.97
            tips.append(f"🛡 Стоп-лосс: ${format_price(sl_price)} (ниже поддержки)")

            # Тейк-профит
            tp1 = resistance
            tp2 = resistance * 1.1
            tips.append(f"🎯 Тейк-профит 1: ${format_price(tp1)} (сопротивление)")
            tips.append(f"🎯 Тейк-профит 2: ${format_price(tp2)} (+10% от сопротивл.)")

            # Стратегия входа
            if volatility > 5:
                tips.append("⚡ Высокая волатильность — раздели покупку на 3 части")
                tips.append(f"   1️⃣ 30% сейчас по ${format_price(price)}")
                tips.append(f"   2️⃣ 40% если упадёт к ${format_price(avg_30d)}")
                tips.append(f"   3️⃣ 30% если упадёт к ${format_price(support)}")
            elif volatility > 2:
                tips.append("📊 Средняя волатильность — раздели на 2 части")
                tips.append(f"   1️⃣ 50% сейчас по ${format_price(price)}")
                tips.append(f"   2️⃣ 50% если упадёт к ${format_price(support)}")
            else:
                tips.append("😴 Низкая волатильность — можно купить одним входом")

            # Риск/доходность
            risk = ((price - sl_price) / price * 100) if price > 0 else 0
            reward = ((tp1 - price) / price * 100) if price > 0 else 0
            rr_ratio = reward / risk if risk > 0 else 0
            tips.append(f"📐 Риск: {risk:.1f}% | Доходность: {reward:.1f}%")
            if rr_ratio >= 2:
                tips.append(f"✅ R/R = 1:{rr_ratio:.1f} — отличное соотношение!")
            elif rr_ratio >= 1:
                tips.append(f"🟡 R/R = 1:{rr_ratio:.1f} — нормально, но не идеально")
            else:
                tips.append(f"🔴 R/R = 1:{rr_ratio:.1f} — риск выше потенциала!")

            # Когда лучше покупать
            if rsi < 35 and position < 30:
                tips.append("🔥 СЕЙЧАС хороший момент для входа!")
            elif rsi > 65 and position > 70:
                tips.append("⏳ Лучше ПОДОЖДАТЬ — цена перегрета")
            elif trend_7d < -5:
                tips.append("📉 Тренд вниз — жди разворот (RSI < 30)")
            else:
                tips.append("📊 Можно входить с осторожностью")
        else:
            tips.append("📊 Недостаточно истории для точных уровней")
            tips.append("💡 Начни с маленькой позиции и наблюдай")

    elif analysis_mode == "already_bought":
        # === РЕЖИМ: УЖЕ КУПИЛ ===
        tips.append("📦 СОВЕТЫ ДЛЯ ДЕРЖАТЕЛЯ:\n")
        if has_history:
            # Что ожидать
            if trend_7d > 5 and momentum > 0:
                tips.append("📈 Тренд восходящий с ускорением — ДЕРЖИ!")
                tips.append(f"🎯 Ближайшая цель: ${format_price(resistance)}")
                if current > resistance * 0.95:
                    tips.append("🚀 Близко к сопротивлению — подумай о частичной фиксации")
            elif trend_7d > 0 and momentum < 0:
                tips.append("⚠️ Рост замедляется — будь внимательным")
                tips.append("📊 Подготовь стоп-лосс на случай разворота")
            elif trend_7d < -5:
                tips.append("📉 Нисходящий тренд — оцени стоит ли держать")
                if rsi < 30:
                    tips.append("💎 Но RSI говорит об отскоке — подожди")
                else:
                    tips.append(f"🛡 Ставь стоп-лосс на ${format_price(support * 0.97)}")
            else:
                tips.append("📊 Боковой тренд — жди направления")

            # Уровни фиксации
            tips.append(f"\n📊 Уровни фиксации прибыли:")
            tips.append(f"   1️⃣ ${format_price(resistance)} (сопротивление)")
            tips.append(f"   2️⃣ ${format_price(resistance * 1.15)} (+15%)")
            tips.append(f"   3️⃣ ${format_price(resistance * 1.3)} (+30%)")

            # Стоп-лосс
            tips.append(f"\n🛡 Стоп-лосс:")
            tips.append(f"   Консервативный: ${format_price(support)}")
            tips.append(f"   Агрессивный: ${format_price(support * 0.95)}")

            # Максимальная просадка
            tips.append(f"\n📉 Макс. просадка за 30д: -{max_drawdown:.1f}%")
            if max_drawdown > 20:
                tips.append("⚠️ Актив высоковолатильный — готовься к качелям")
            elif max_drawdown < 5:
                tips.append("✅ Стабильный актив — держать спокойно")

            # Чего ждать
            tips.append(f"\n🔮 Чего ожидать:")
            if volatility > 5:
                tips.append(f"   Дневные колебания: ±{volatility:.1f}%")
                tips.append(f"   Недельные колебания: ±{volatility * 2.5:.0f}%")
            if green_days > red_days:
                tips.append(f"   📈 {green_days} зелёных vs {red_days} красных дней")
                tips.append("   Статистически чаще рост")
            else:
                tips.append(f"   📉 {red_days} красных vs {green_days} зелёных дней")
                tips.append("   Статистически чаще падение")

            # Когда выходить
            tips.append(f"\n🚪 Когда выходить:")
            if rsi > 75:
                tips.append("   🔴 RSI > 75 — СЕЙЧАС хорошее время для фиксации!")
            elif rsi > 65:
                tips.append("   🟡 RSI приближается к перекупленности")
                tips.append("   Начни фиксировать частями")
            else:
                tips.append("   ⏳ RSI в норме — можно держать дальше")
        else:
            tips.append("📊 Недостаточно истории для точных уровней")
            tips.append("💡 Следи за объёмами и новостями")

    else:
        # === РЕЖИМ: ПРОСТО АНАЛИЗ ===
        if has_history:
            if volatility > 5:
                tips.append("🌪 Высокая волатильность. Используй стоп-лосс!")
            elif volatility < 1:
                tips.append("😴 Низкая волатильность. Жди пробоя уровня.")

            if position < 30 and rsi < 40:
                tips.append("💡 На дне диапазона с низким RSI — сигнал к покупке.")
            elif position > 75 and rsi > 65:
                tips.append("💡 У пика с высоким RSI — будь готов к откату.")

            if change_30d > 30:
                tips.append(f"📊 Вырос на {change_30d:.0f}% за месяц — не входи на всю сумму.")
            elif change_30d < -30:
                tips.append(f"📊 Упал на {abs(change_30d):.0f}% за месяц — проверь фундаментал.")

            if green_days > red_days * 2:
                tips.append("📈 Доминируют зелёные дни — восходящий тренд.")
            elif red_days > green_days * 2:
                tips.append("📉 Доминируют красные дни — нисходящий тренд.")

            if dist_to_support < 5 and change_24h < 0:
                tips.append("🛡 Подходишь к поддержке — хороший уровень для стоп-лосса.")
        else:
            tips.append("📊 Недостаточно истории. Анализ только по текущим данным.")

    tips.append("\n📌 Не вкладывай больше, чем можешь потерять.")

    # === Режим label ===
    if analysis_mode == "buy_planning":
        mode_label = "🛒 Режим: Планирую покупку"
    elif analysis_mode == "already_bought":
        mode_label = "📦 Режим: Уже в портфеле"
    else:
        mode_label = "🔍 Режим: Общий анализ"

    # === ФОРМИРОВАНИЕ ОТЧЁТА ===
    report = (
        f"🔎 АНАЛИЗ: {info['emoji']} {ticker}\n"
        f"{'━' * 28}\n"
        f"{mode_label}\n\n"
        f"📛 {info['name']}\n"
        f"💰 Цена: ${format_price(price)}\n"
        f"📈 24ч: {change_24h:+.2f}%\n"
        f"📊 Объём: {format_volume(volume, 'usd')}\n"
    )
    if mcap > 0:
        report += f"🏦 Капит.: {format_volume(mcap, 'usd')}\n"

    if has_history:
        report += (
            f"\n{'━' * 28}\n"
            f"📅 ИСТОРИЯ (30 ДНЕЙ):\n\n"
            f"  📈 Макс: ${format_price(high_30d)}\n"
            f"  📉 Мин: ${format_price(low_30d)}\n"
            f"  📊 Средняя: ${format_price(avg_30d)}\n"
            f"  📈 Изменение: {change_30d:+.1f}%\n"
            f"  🟢 Зелёных дней: {green_days}\n"
            f"  🔴 Красных дней: {red_days}\n"
            f"  🌪 Волатильность: ±{volatility:.2f}%/день\n"
        )

    report += (
        f"\n{'━' * 28}\n"
        f"📊 ТЕХНИЧЕСКИЙ АНАЛИЗ:\n\n"
    )
    for r in reasons:
        report += f"  {r}\n"

    report += (
        f"\n{'━' * 28}\n"
        f"{action_emoji} РЕКОМЕНДАЦИЯ:\n\n"
        f"  {action}\n"
        f"  📊 Уверенность: {confidence}%\n"
        f"  💬 {action_detail}\n"
    )

    if has_history:
        filled = confidence // 10
        empty = 10 - filled
        bar = "█" * filled + "░" * empty
        report += f"  [{bar}]\n"

        report += (
            f"\n{'━' * 28}\n"
            f"🛡 Уровни:\n"
            f"  Поддержка: ${format_price(support)}\n"
            f"  Сопротивл.: ${format_price(resistance)}\n"
        )

        if has_history:
            report += (
                f"  SMA7: ${format_price(sma_7)}\n"
                f"  SMA14: ${format_price(sma_14)}\n"
            )

    report += f"\n{'━' * 28}\n💡 СОВЕТЫ:\n\n"
    for t in tips:
        report += f"  {t}\n"

    report += (
        f"\n{'━' * 28}\n"
        f"⚠️ Приблизительный анализ!\n"
        f"Не является финансовым советом."
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    # Кнопка "Назад" после вывода анализа
    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )
    return ConversationHandler.END


# ==================== 🎯 СНАЙПЕР ВХОДА (PREMIUM) ====================

async def sniper_start(update, context):
    """Снайпер входа — сканирует ВСЕ активы и находит лучшие точки входа"""
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    if tier != 'premium':
        await sub_blocked(update, "Снайпер входа", "premium")
        return

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text(
        f"🎯 СНАЙПЕР ВХОДА\n"
        f"{'━' * 28}\n\n"
        f"⏳ Сканирую {len(asset_list)} {asset_label_gen(mode)}...\n"
        f"🔎 Ищу лучшие точки входа...\n\n"
        f"Это займёт несколько секунд..."
    )

    # Загрузить все данные
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные рынка")
        except Exception:
            pass
        return

    # Собираем кандидатов
    candidates = []

    for ticker, info in asset_list.items():
        coin_data = data.get(info['id'], {})
        if not coin_data:
            continue

        price = coin_data.get('usd', 0) or 0
        change_24h = coin_data.get('usd_24h_change', 0) or 0
        volume = coin_data.get('usd_24h_vol', 0) or 0
        mcap = coin_data.get('usd_market_cap', 0) or 0

        if price <= 0:
            continue

        # Загрузить историю
        try:
            if mode == 'stocks':
                history = await stocks_api.fetch_stock_history(ticker, days=30)
            else:
                history = await fetch_crypto_history(info['id'], days=30)
        except Exception:
            history = []

        if len(history) < 7:
            continue

        prices_hist = history
        high_30d = max(prices_hist)
        low_30d = min(prices_hist)
        avg_30d = sum(prices_hist) / len(prices_hist)
        current = prices_hist[-1]

        price_range = high_30d - low_30d
        position = ((current - low_30d) / price_range * 100) if price_range > 0 else 50

        # Дневные изменения
        daily_changes = []
        for i in range(1, len(prices_hist)):
            if prices_hist[i-1] > 0:
                dc = ((prices_hist[i] - prices_hist[i-1]) / prices_hist[i-1]) * 100
                daily_changes.append(dc)

        volatility = sum(abs(d) for d in daily_changes) / len(daily_changes) if daily_changes else 0

        # RSI
        if len(daily_changes) >= 14:
            gains_14 = [d for d in daily_changes[-14:] if d > 0]
            losses_14 = [abs(d) for d in daily_changes[-14:] if d < 0]
            avg_gain = sum(gains_14) / 14
            avg_loss = sum(losses_14) / 14
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            else:
                rsi = 100
        else:
            gains = [d for d in daily_changes if d > 0]
            losses = [abs(d) for d in daily_changes if d < 0]
            avg_g = sum(gains) / max(len(gains), 1)
            avg_l = sum(losses) / max(len(losses), 1)
            rsi = 100 - (100 / (1 + avg_g / avg_l)) if avg_l > 0 else 70

        # Тренд 7д
        last_7 = prices_hist[-7:]
        trend_7d = ((last_7[-1] - last_7[0]) / last_7[0] * 100) if last_7[0] > 0 else 0

        # Momentum
        if len(prices_hist) >= 14:
            first_h = prices_hist[-14:-7]
            second_h = prices_hist[-7:]
            ch1 = ((first_h[-1] - first_h[0]) / first_h[0] * 100) if first_h[0] > 0 else 0
            ch2 = ((second_h[-1] - second_h[0]) / second_h[0] * 100) if second_h[0] > 0 else 0
            momentum = ch2 - ch1
        else:
            momentum = 0

        # Поддержка / сопротивление
        recent = prices_hist[-14:] if len(prices_hist) >= 14 else prices_hist
        support = min(recent)
        resistance = max(recent)

        # SMA
        sma_7 = sum(prices_hist[-7:]) / 7
        sma_14 = sum(prices_hist[-14:]) / min(14, len(prices_hist)) if len(prices_hist) >= 14 else current

        # Объём/капитализация
        vol_ratio = (volume / mcap * 100) if mcap > 0 else 0

        # === СКОРИНГ для снайпера (фокус на покупку) ===
        sniper_score = 0
        signals = []

        # RSI перепродан = отличная возможность
        if rsi < 25:
            sniper_score += 35
            signals.append("🟢 RSI сильно перепродан")
        elif rsi < 35:
            sniper_score += 25
            signals.append("🟢 RSI перепродан")
        elif rsi > 75:
            sniper_score -= 30  # не входить
            signals.append("🔴 RSI перекуплен")
        elif rsi > 65:
            sniper_score -= 15

        # Цена у дна
        if position < 15:
            sniper_score += 30
            signals.append("💎 У самого дна диапазона")
        elif position < 30:
            sniper_score += 20
            signals.append("📉 В нижней зоне")
        elif position > 85:
            sniper_score -= 20

        # Momentum разворот (ускорение после падения)
        if momentum > 3 and trend_7d < 0:
            sniper_score += 20
            signals.append("🔄 Разворот: импульс растёт")
        elif momentum > 5:
            sniper_score += 10
            signals.append("🚀 Сильный импульс")

        # Цена ниже SMA (отклонение)
        if current < sma_14 * 0.95:
            sniper_score += 15
            signals.append("📊 Ниже SMA14 — недооценён")

        # Сильное падение за 24ч (паническая продажа)
        if change_24h < -8:
            sniper_score += 20
            signals.append(f"💥 Падение {change_24h:.1f}% — паника")
        elif change_24h < -5:
            sniper_score += 10
            signals.append(f"📉 Коррекция {change_24h:.1f}%")

        # Высокий объём при падении = потенциал разворота
        if vol_ratio > 10 and change_24h < -3:
            sniper_score += 15
            signals.append("🔥 Высокий объём на падении")

        # Близость к поддержке
        dist_support = ((current - support) / current * 100) if current > 0 else 99
        if dist_support < 2:
            sniper_score += 15
            signals.append("🛡 На уровне поддержки")

        # Паттерн восстановления
        dips = 0
        recovers = 0
        for i in range(2, len(prices_hist)):
            drop = ((prices_hist[i-1] - prices_hist[i-2]) / prices_hist[i-2] * 100) if prices_hist[i-2] > 0 else 0
            bounce = ((prices_hist[i] - prices_hist[i-1]) / prices_hist[i-1] * 100) if prices_hist[i-1] > 0 else 0
            if drop < -3:
                dips += 1
                if bounce > 1:
                    recovers += 1
        if dips > 0 and recovers / dips > 0.6:
            sniper_score += 10
            signals.append("💪 Хорошо восстанавливается")

        # Только если есть реальный потенциал
        if sniper_score >= 25:
            # Расчёт уровней
            entry_price = price
            stop_loss = support * 0.97
            tp1 = resistance
            tp2 = resistance * 1.15
            tp3 = resistance * 1.3

            risk_pct = ((entry_price - stop_loss) / entry_price * 100) if entry_price > 0 else 0
            reward_pct = ((tp1 - entry_price) / entry_price * 100) if entry_price > 0 else 0
            rr_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

            confidence = min(95, max(30, 40 + sniper_score))

            candidates.append({
                'ticker': ticker,
                'info': info,
                'price': price,
                'change_24h': change_24h,
                'rsi': rsi,
                'position': position,
                'score': sniper_score,
                'confidence': confidence,
                'signals': signals,
                'entry': entry_price,
                'stop_loss': stop_loss,
                'tp1': tp1,
                'tp2': tp2,
                'tp3': tp3,
                'risk_pct': risk_pct,
                'reward_pct': reward_pct,
                'rr_ratio': rr_ratio,
                'volatility': volatility,
                'support': support,
                'resistance': resistance,
                'volume': volume,
            })

    # Сортировка по скору
    candidates.sort(key=lambda x: x['score'], reverse=True)
    top = candidates[:5]

    # === ФОРМИРОВАНИЕ ОТЧЁТА ===
    if not top:
        report = (
            f"🎯 СНАЙПЕР ВХОДА\n"
            f"{'━' * 28}\n\n"
            f"😐 Сейчас нет ярких возможностей\n\n"
            f"Все активы в нейтральной зоне.\n"
            f"Попробуй позже или переключи\n"
            f"режим (крипта/акции).\n\n"
            f"💡 Лучшие входы появляются\n"
            f"после резких падений рынка."
        )
    else:
        report = (
            f"🎯 СНАЙПЕР ВХОДА\n"
            f"{'━' * 28}\n"
            f"🔫 Топ-{len(top)} лучших точек входа\n"
            f"{'━' * 28}\n"
        )

        for i, c in enumerate(top, 1):
            # Медаль
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"#{i}"

            # Шкала уверенности
            filled = c['confidence'] // 10
            empty = 10 - filled
            bar = "█" * filled + "░" * empty

            report += (
                f"\n{medal} {c['info']['emoji']} {c['ticker']} — {c['info']['name']}\n"
                f"   💰 Цена: ${format_price(c['price'])}\n"
                f"   📈 24ч: {c['change_24h']:+.1f}%\n"
                f"   📊 RSI: {c['rsi']:.0f} | Позиция: {c['position']:.0f}%\n"
                f"   [{bar}] {c['confidence']}%\n\n"
            )

            # Сигналы
            for sig in c['signals'][:3]:
                report += f"   {sig}\n"

            report += (
                f"\n   🎯 ТОЧКА ВХОДА:\n"
                f"   ▸ Вход: ${format_price(c['entry'])}\n"
                f"   ▸ Стоп-лосс: ${format_price(c['stop_loss'])} (-{c['risk_pct']:.1f}%)\n"
                f"   ▸ Цель 1: ${format_price(c['tp1'])} (+{c['reward_pct']:.1f}%)\n"
                f"   ▸ Цель 2: ${format_price(c['tp2'])}\n"
                f"   ▸ Цель 3: ${format_price(c['tp3'])}\n"
                f"   ▸ R/R: 1:{c['rr_ratio']:.1f}\n"
                f"   {'━' * 24}\n"
            )

        # Статистика скана
        report += (
            f"\n📊 Просканировано: {len(asset_list)} активов\n"
            f"🎯 Найдено возможностей: {len(candidates)}\n"
            f"🔫 Показано топ: {len(top)}\n\n"
            f"⚠️ Не является финансовым советом!\n"
            f"Всегда ставь стоп-лосс!"
        )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    # Кнопка назад
    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )


# ==================== 🗺 ХИТМАП РЫНКА ====================

async def show_market_heatmap(update, context):
    """Хитмап рынка — визуальная карта всех активов по производительности"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("⏳ Строю хитмап рынка...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собираем активы с изменениями
    items = []
    for ticker, info in asset_list.items():
        d = None
        if mode == 'stocks':
            for s in (data if isinstance(data, list) else []):
                sym = s.get('symbol', '').upper()
                if sym == ticker.upper():
                    d = s
                    break
        else:
            cg_id = info.get('coingecko_id', ticker.lower())
            d = data.get(cg_id) if isinstance(data, dict) else None

        if d:
            if mode == 'stocks':
                price = d.get('price', 0)
                change = d.get('change_24h', 0) or 0
            else:
                price = d.get('usd', 0) or d.get('rub', 0) or 0
                change = d.get('usd_24h_change', 0) or 0

            if price and price > 0:
                items.append({
                    'ticker': ticker,
                    'emoji': info['emoji'],
                    'name': info['name'],
                    'price': price,
                    'change': change
                })

    if not items:
        try:
            await msg.edit_text("❌ Нет данных для построения хитмапа")
        except Exception:
            pass
        return

    # Сортировка по изменению
    items.sort(key=lambda x: x['change'], reverse=True)

    # Разделяем на зоны
    def heat_block(change):
        """Определяем символ для уровня изменения"""
        if change >= 10:
            return "🟩🟩"  # сильный рост
        elif change >= 5:
            return "🟩▲"
        elif change >= 2:
            return "🟢▲"
        elif change >= 0.5:
            return "🟢 "
        elif change >= -0.5:
            return "⬜ "  # нейтральная зона
        elif change >= -2:
            return "🔴 "
        elif change >= -5:
            return "🔴▼"
        elif change >= -10:
            return "🟥▼"
        else:
            return "🟥🟥"  # сильное падение

    # Считаем статистику
    gainers = [i for i in items if i['change'] > 0.5]
    losers = [i for i in items if i['change'] < -0.5]
    neutral = [i for i in items if -0.5 <= i['change'] <= 0.5]
    avg_change = sum(i['change'] for i in items) / len(items)
    max_gainer = items[0]
    max_loser = items[-1]

    # Определяем настроение рынка
    if avg_change > 3:
        mood = "🚀 Сильный бычий тренд"
    elif avg_change > 1:
        mood = "📈 Бычий тренд"
    elif avg_change > 0:
        mood = "🟢 Слабый рост"
    elif avg_change > -1:
        mood = "🟡 Слабое снижение"
    elif avg_change > -3:
        mood = "📉 Медвежий тренд"
    else:
        mood = "💀 Сильный медвежий тренд"

    # Формируем отчёт
    report = (
        f"🗺 ХИТМАП РЫНКА\n"
        f"{'━' * 28}\n"
        f"📊 {label} | {len(items)} активов\n"
        f"{'━' * 28}\n\n"
    )

    # Легенда
    report += (
        f"🟩🟩 +10%+  🟩▲ +5%  🟢▲ +2%\n"
        f"🟢  +0.5%  ⬜ 0%  🔴 -0.5%\n"
        f"🔴▼ -2%  🟥▼ -5%  🟥🟥 -10%+\n"
        f"{'━' * 28}\n\n"
    )

    # Рисуем хитмап
    for item in items:
        block = heat_block(item['change'])
        sign = "+" if item['change'] >= 0 else ""
        report += (
            f"{block} {item['emoji']} {item['ticker']}"
            f" {sign}{item['change']:.1f}%"
            f" ${format_price(item['price'])}\n"
        )

    # Статистика
    report += (
        f"\n{'━' * 28}\n"
        f"📊 СТАТИСТИКА РЫНКА\n"
        f"{'━' * 28}\n\n"
        f"📈 Растут: {len(gainers)} ({len(gainers)*100//len(items)}%)\n"
        f"📉 Падают: {len(losers)} ({len(losers)*100//len(items)}%)\n"
        f"⬜ Нейтрально: {len(neutral)}\n\n"
        f"🔺 Лучший: {max_gainer['emoji']} {max_gainer['ticker']}"
        f" +{max_gainer['change']:.1f}%\n"
        f"🔻 Худший: {max_loser['emoji']} {max_loser['ticker']}"
        f" {max_loser['change']:.1f}%\n\n"
        f"📉 Средн. изменение: {avg_change:+.2f}%\n"
        f"🎭 Настроение: {mood}\n\n"
        f"⚡ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )


# ==================== ⏳ МАШИНА ВРЕМЕНИ ====================

async def time_machine_start(update, context):
    """Машина времени — начало: выбор актива"""
    user_id = update.effective_user.id
    tier = get_user_tier(user_id)
    if tier != 'premium':
        await sub_blocked(update, "Машина времени", "premium")
        return ConversationHandler.END

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    # Список тикеров
    tickers = list(asset_list.keys())
    cols = 4
    rows = []
    for i in range(0, len(tickers), cols):
        row = [KeyboardButton(t) for t in tickers[i:i+cols]]
        rows.append(row)
    rows.append([KeyboardButton("↩️ Назад")])
    kb = ReplyKeyboardMarkup(rows, resize_keyboard=True)

    await update.message.reply_text(
        f"⏳ МАШИНА ВРЕМЕНИ\n"
        f"{'━' * 28}\n\n"
        f"🔮 Что если бы ты инвестировал\n"
        f"в прошлом? Узнай!\n\n"
        f"Шаг 1/3: Выбери актив ({label}):",
        reply_markup=kb
    )
    return TIME_MACHINE_ASSET_STATE


async def time_machine_choose_asset(update, context):
    """Машина времени — выбор актива"""
    text = update.message.text.strip().upper()
    if text == "↩️ НАЗАД":
        await update.message.reply_text(
            "👇 Выбери действие:",
            reply_markup=get_premium_extra_keyboard()
        )
        return ConversationHandler.END

    mode = get_mode(context)
    asset_list = get_asset_list(mode)

    # Проверяем тикер
    ticker = None
    for t in asset_list:
        if t.upper() == text:
            ticker = t
            break

    if not ticker:
        await update.message.reply_text("❌ Тикер не найден. Попробуй ещё раз:")
        return TIME_MACHINE_ASSET_STATE

    context.user_data['tm_ticker'] = ticker
    context.user_data['tm_mode'] = mode

    await update.message.reply_text(
        f"⏳ МАШИНА ВРЕМЕНИ\n"
        f"{'━' * 28}\n\n"
        f"Актив: {asset_list[ticker]['emoji']} {ticker}\n\n"
        f"Шаг 2/3: Сколько $ ты бы вложил?\n"
        f"(введи число, например: 1000)",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("100"), KeyboardButton("500"), KeyboardButton("1000")],
            [KeyboardButton("5000"), KeyboardButton("10000")],
            [KeyboardButton("↩️ Назад")]
        ], resize_keyboard=True)
    )
    return TIME_MACHINE_AMOUNT_STATE


async def time_machine_choose_amount(update, context):
    """Машина времени — ввод суммы"""
    text = update.message.text.strip()
    if text == "↩️ Назад":
        await update.message.reply_text(
            "👇 Выбери действие:",
            reply_markup=get_premium_extra_keyboard()
        )
        return ConversationHandler.END

    try:
        amount = float(text.replace(',', '.').replace('$', '').replace(' ', ''))
        if amount <= 0:
            raise ValueError
        if amount > 1_000_000_000:
            await update.message.reply_text("❌ Слишком большая сумма! Максимум $1,000,000,000")
            return TIME_MACHINE_AMOUNT_STATE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ Введи число (например: 1000):")
        return TIME_MACHINE_AMOUNT_STATE

    context.user_data['tm_amount'] = amount

    await update.message.reply_text(
        f"⏳ МАШИНА ВРЕМЕНИ\n"
        f"{'━' * 28}\n\n"
        f"Актив: {context.user_data['tm_ticker']}\n"
        f"Сумма: ${amount:,.0f}\n\n"
        f"Шаг 3/3: Сколько дней назад?\n"
        f"(от 1 до 365)",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("7"), KeyboardButton("14"), KeyboardButton("30")],
            [KeyboardButton("90"), KeyboardButton("180"), KeyboardButton("365")],
            [KeyboardButton("↩️ Назад")]
        ], resize_keyboard=True)
    )
    return TIME_MACHINE_DAYS_STATE


async def time_machine_result(update, context):
    """Машина времени — результат"""
    text = update.message.text.strip()
    if text == "↩️ Назад":
        await update.message.reply_text(
            "👇 Выбери действие:",
            reply_markup=get_premium_extra_keyboard()
        )
        return ConversationHandler.END

    try:
        days = int(text)
        if days < 1 or days > 365:
            await update.message.reply_text("❌ Введи число от 1 до 365:")
            return TIME_MACHINE_DAYS_STATE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ Введи число дней (1-365):")
        return TIME_MACHINE_DAYS_STATE

    ticker = context.user_data.get('tm_ticker')
    amount = context.user_data.get('tm_amount', 1000)
    mode = context.user_data.get('tm_mode', 'crypto')
    asset_list = get_asset_list(mode)
    info = asset_list.get(ticker)

    if not info:
        await update.message.reply_text("❌ Ошибка данных. Попробуй заново.",
                                         reply_markup=get_premium_extra_keyboard())
        return ConversationHandler.END

    msg = await update.message.reply_text("⏳ Запускаю машину времени...")

    # Получаем историю цен
    try:
        if mode == 'stocks':
            history = await stocks_api.fetch_stock_history(ticker, days=days)
        else:
            cg_id = info.get('coingecko_id', ticker.lower())
            history = await fetch_crypto_history(cg_id, days=days)
    except Exception:
        history = None

    if not history or len(history) < 2:
        try:
            await msg.edit_text(
                f"❌ Не удалось получить историю {ticker} за {days} дней.\n"
                f"Попробуй меньший период.",
                reply_markup=get_premium_extra_keyboard()
            )
        except Exception:
            pass
        # Кнопка назад
        await update.message.reply_text(
            "👇 Выбери действие:",
            reply_markup=get_premium_extra_keyboard()
        )
        return ConversationHandler.END

    # Цена тогда и сейчас
    price_then = history[0]
    price_now = history[-1]
    price_min = min(history)
    price_max = max(history)
    price_avg = sum(history) / len(history)

    # Расчёты
    coins_bought = amount / price_then if price_then > 0 else 0
    value_now = coins_bought * price_now
    profit = value_now - amount
    profit_pct = (profit / amount * 100) if amount > 0 else 0

    # Лучший и худший момент
    value_at_max = coins_bought * price_max
    value_at_min = coins_bought * price_min
    best_profit = value_at_max - amount
    worst_drawdown = value_at_min - amount

    # Волатильность
    changes = []
    for i in range(1, len(history)):
        if history[i-1] > 0:
            changes.append((history[i] - history[i-1]) / history[i-1] * 100)
    avg_daily_change = sum(abs(c) for c in changes) / len(changes) if changes else 0

    # Визуализация пути цены (ASCII мини-график)
    chart_len = 20
    step = max(1, len(history) // chart_len)
    sampled = [history[i] for i in range(0, len(history), step)][:chart_len]
    if sampled:
        mn = min(sampled)
        mx = max(sampled)
        rng = mx - mn if mx != mn else 1
        chart = ""
        levels = "▁▂▃▄▅▆▇█"
        for p in sampled:
            idx = int((p - mn) / rng * (len(levels) - 1))
            chart += levels[idx]
    else:
        chart = "▅▅▅▅▅▅▅▅▅▅"

    # Эмодзи результата
    if profit_pct >= 50:
        result_emoji = "🤑"
        result_text = "НЕВЕРОЯТНАЯ ПРИБЫЛЬ!"
    elif profit_pct >= 20:
        result_emoji = "🚀"
        result_text = "Отличная инвестиция!"
    elif profit_pct >= 5:
        result_emoji = "📈"
        result_text = "Хороший результат"
    elif profit_pct >= 0:
        result_emoji = "😐"
        result_text = "Почти в ноль"
    elif profit_pct >= -10:
        result_emoji = "📉"
        result_text = "Небольшой убыток"
    elif profit_pct >= -30:
        result_emoji = "😰"
        result_text = "Ощутимый убыток"
    else:
        result_emoji = "💀"
        result_text = "Катастрофа!"

    report = (
        f"⏳ МАШИНА ВРЕМЕНИ\n"
        f"{'━' * 28}\n\n"
        f"{info['emoji']} {ticker} — {info['name']}\n"
        f"{'━' * 28}\n\n"
        f"📅 Период: {days} дней назад → сегодня\n"
        f"💰 Вложено: ${amount:,.2f}\n\n"
        f"{'━' * 28}\n"
        f"📊 ПУТЬ ЦЕНЫ:\n"
        f"{'━' * 28}\n\n"
        f"   Тогда:  ${format_price(price_then)}\n"
        f"   Мин:    ${format_price(price_min)}\n"
        f"   Макс:   ${format_price(price_max)}\n"
        f"   Средн:  ${format_price(price_avg)}\n"
        f"   Сейчас: ${format_price(price_now)}\n\n"
        f"   {chart}\n"
        f"   {'⬆️' if price_now >= price_then else '⬇️'} "
        f"{abs(price_now - price_then) / price_then * 100:.1f}% за {days}д\n\n"
        f"{'━' * 28}\n"
        f"{result_emoji} РЕЗУЛЬТАТ: {result_text}\n"
        f"{'━' * 28}\n\n"
        f"   💼 Куплено: {coins_bought:.6f} {ticker}\n"
        f"   💰 Стоимость сейчас: ${value_now:,.2f}\n"
        f"   {'📈' if profit >= 0 else '📉'} Прибыль: "
        f"{'🟢+' if profit >= 0 else '🔴'}"
        f"${abs(profit):,.2f} ({profit_pct:+.1f}%)\n\n"
        f"{'━' * 28}\n"
        f"📈 ЭКСТРЕМУМЫ ПУТИ:\n"
        f"{'━' * 28}\n\n"
        f"   🔺 Лучший момент: ${value_at_max:,.2f}\n"
        f"      (прибыль: {'🟢+' if best_profit >= 0 else '🔴'}"
        f"${abs(best_profit):,.2f})\n"
        f"   🔻 Худший момент: ${value_at_min:,.2f}\n"
        f"      (просадка: 🔴${abs(worst_drawdown):,.2f})\n\n"
        f"   📊 Средн. дневная волат: {avg_daily_change:.2f}%\n\n"
        f"{'━' * 28}\n"
        f"⏳ Это лишь история — не прогноз!\n"
        f"⚠️ Прошлые результаты не гарантируют\n"
        f"будущую доходность."
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )
    return ConversationHandler.END


# ==================== 📡 РАДАР АНОМАЛИЙ ====================

async def show_anomaly_radar(update, context):
    """Радар аномалий — обнаружение необычных движений рынка"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("📡 Сканирую рынок на аномалии...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные рынка")
        except Exception:
            pass
        return

    anomalies = []

    for ticker, info in asset_list.items():
        d = None
        if mode == 'stocks':
            for s in (data if isinstance(data, list) else []):
                sym = s.get('symbol', '').upper()
                if sym == ticker.upper():
                    d = s
                    break
        else:
            cg_id = info.get('coingecko_id', ticker.lower())
            d = data.get(cg_id) if isinstance(data, dict) else None

        if not d:
            continue

        if mode == 'stocks':
            price = d.get('price', 0)
            change_24h = d.get('change_24h', 0) or 0
            volume = d.get('volume', 0) or 0
            market_cap = d.get('market_cap', 0) or 0
            high_24h = d.get('high_24h', price * 1.01) if price else 0
            low_24h = d.get('low_24h', price * 0.99) if price else 0
        else:
            price = d.get('usd', 0) or 0
            change_24h = d.get('usd_24h_change', 0) or 0
            volume = d.get('usd_24h_vol', 0) or 0
            market_cap = d.get('usd_market_cap', 0) or 0
            high_24h = d.get('high_24h', price * 1.01) if price else 0
            low_24h = d.get('low_24h', price * 0.99) if price else 0

        if price <= 0:
            continue

        # === ДЕТЕКЦИЯ АНОМАЛИЙ ===
        signals = []
        anomaly_score = 0

        # 1. Аномальное изменение цены (>8% за 24ч)
        if abs(change_24h) > 8:
            level = "🔴 КРИТИЧЕСКАЯ" if abs(change_24h) > 15 else "🟠 ВЫСОКАЯ"
            direction = "рост" if change_24h > 0 else "падение"
            signals.append(f"⚡ {level}: {direction} {abs(change_24h):.1f}% за 24ч")
            anomaly_score += min(abs(change_24h) / 2, 15)

        # 2. Объём/капитализация (если капитализация есть)
        if market_cap > 0 and volume > 0:
            vol_mcap_ratio = volume / market_cap * 100
            if vol_mcap_ratio > 20:
                signals.append(f"🌊 Объём = {vol_mcap_ratio:.0f}% от капитализации!")
                anomaly_score += 10
            elif vol_mcap_ratio > 10:
                signals.append(f"🌊 Высокий объём: {vol_mcap_ratio:.1f}% от капитализации")
                anomaly_score += 5

        # 3. Диапазон 24ч (широкий канал = волатильность)
        if high_24h and low_24h and low_24h > 0:
            range_pct = (high_24h - low_24h) / low_24h * 100
            if range_pct > 15:
                signals.append(f"📐 Огромный диапазон: {range_pct:.1f}% (H-L)")
                anomaly_score += 8
            elif range_pct > 10:
                signals.append(f"📐 Широкий диапазон: {range_pct:.1f}%")
                anomaly_score += 4

        # 4. Цена у экстремума (около high/low за 24ч)
        if high_24h and low_24h and high_24h > low_24h:
            position = (price - low_24h) / (high_24h - low_24h) * 100
            if position > 95:
                signals.append(f"🔝 Цена на максимуме 24ч ({position:.0f}%)")
                anomaly_score += 3
            elif position < 5:
                signals.append(f"🔻 Цена на минимуме 24ч ({position:.0f}%)")
                anomaly_score += 3

        # 5. Объём без движения цены (накопление/распределение)
        if volume > 0 and market_cap > 0:
            vol_ratio = volume / market_cap * 100
            if vol_ratio > 8 and abs(change_24h) < 2:
                signals.append(f"🕵️ Высокий объём при стабильной цене — накопление?")
                anomaly_score += 7

        # 6. Резкий памп/дамп подозрение
        if change_24h > 20:
            signals.append(f"🚨 Подозрение на ПАМПИНГ!")
            anomaly_score += 12
        elif change_24h < -20:
            signals.append(f"🚨 Подозрение на ДАМП!")
            anomaly_score += 12

        if signals:
            anomalies.append({
                'ticker': ticker,
                'info': info,
                'price': price,
                'change_24h': change_24h,
                'volume': volume,
                'market_cap': market_cap,
                'score': anomaly_score,
                'signals': signals,
            })

    # Сортировка по скору аномальности
    anomalies.sort(key=lambda x: x['score'], reverse=True)

    # Формируем отчёт
    report = (
        f"📡 РАДАР АНОМАЛИЙ\n"
        f"{'━' * 28}\n"
        f"🔍 Режим: {label}\n"
        f"📊 Просканировано: {len(asset_list)} активов\n"
        f"{'━' * 28}\n\n"
    )

    if not anomalies:
        report += (
            f"✅ Аномалий не обнаружено!\n\n"
            f"Рынок сейчас спокоен.\n"
            f"Все активы в нормальном диапазоне.\n\n"
            f"💡 Аномалии появляются при:\n"
            f"• Резких движениях цены (>8%)\n"
            f"• Необычных объёмах торгов\n"
            f"• Подозрительных паттернах"
        )
    else:
        top = anomalies[:7]  # Топ-7 аномалий

        # Шкала опасности
        total_score = sum(a['score'] for a in anomalies)
        if total_score > 80:
            danger = "🔴 ВНИМАНИЕ: Рынок в зоне турбулентности!"
        elif total_score > 40:
            danger = "🟠 Повышенная активность на рынке"
        elif total_score > 15:
            danger = "🟡 Незначительные отклонения"
        else:
            danger = "🟢 Рынок относительно спокоен"

        report += f"{danger}\n\n"

        for i, a in enumerate(top, 1):
            # Иконка скора
            if a['score'] >= 15:
                level_icon = "🔴"
            elif a['score'] >= 8:
                level_icon = "🟠"
            else:
                level_icon = "🟡"

            report += (
                f"{level_icon} #{i} {a['info']['emoji']} {a['ticker']}"
                f" — {a['info']['name']}\n"
                f"   💰 ${format_price(a['price'])}"
                f" | 24ч: {a['change_24h']:+.1f}%\n"
            )
            if a['volume']:
                report += f"   📊 Объём: ${format_volume(a['volume'])}\n"

            for sig in a['signals']:
                report += f"   {sig}\n"

            # Шкала аномальности
            filled = min(int(a['score'] / 2), 10)
            empty = 10 - filled
            bar = "█" * filled + "░" * empty
            report += f"   Аномальность: [{bar}] {a['score']:.0f}\n"
            report += f"   {'━' * 24}\n"

        report += (
            f"\n📊 Найдено аномалий: {len(anomalies)}\n"
            f"🔎 Показано: {len(top)}\n\n"
            f"⚠️ Аномалии — повод для анализа,\n"
            f"не сигнал к действию!"
        )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )


# ==================== 🎯 ПРЕДСКАЗАНИЕ ЦЕН ====================

def get_prediction_keyboard():
    """Клавиатура предсказаний"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📈 Вверх!"), KeyboardButton("📉 Вниз!")],
        [KeyboardButton("📋 Мои предсказания"), KeyboardButton("🔮 Проверить")],
        [KeyboardButton("📊 Статистика 🎯")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


async def show_prediction_menu(update, context):
    """Меню предсказаний"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    active = db.prediction_count_active(user_id, mode)
    total, correct, wrong = db.prediction_get_stats(user_id)
    accuracy = (correct / total * 100) if total > 0 else 0

    await update.message.reply_text(
        f"🎯 ПРЕДСКАЗАНИЕ ЦЕН\n"
        f"{'═' * 28}\n\n"
        f"Угадай, куда пойдёт цена!\n"
        f"Выбери актив → предскажи\n"
        f"📈 Вверх или 📉 Вниз\n\n"
        f"📊 Твоя статистика:\n"
        f"  📋 Активных: {active}\n"
        f"  ✅ Угадано: {correct}/{total}\n"
        f"  🎯 Точность: {accuracy:.0f}%\n\n"
        f"{'━' * 28}\n"
        f"📈📉 — сделать предсказание\n"
        f"📋 — мои активные предсказания\n"
        f"🔮 — проверить результаты\n"
        f"📊 — подробная статистика",
        reply_markup=get_prediction_keyboard()
    )


async def prediction_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало предсказания — выбор актива"""
    text = update.message.text.strip()
    direction = 'up' if '📈' in text or 'верх' in text.lower() else 'down'
    context.user_data['pred_direction'] = direction
    mode = get_mode(context)

    dir_label = "📈 ВВЕРХ" if direction == 'up' else "📉 ВНИЗ"
    await update.message.reply_text(
        f"🎯 ПРЕДСКАЗАНИЕ: {dir_label}\n"
        f"{'━' * 28}\n\n"
        f"Выберите актив для предсказания:",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return PREDICTION_ASSET_STATE


async def prediction_choose_asset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать выбор актива для предсказания"""
    text = update.message.text.strip()

    if text in ("Отмена", "↩️ Назад"):
        await update.message.reply_text("❌ Отменено", reply_markup=get_prediction_keyboard())
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    ticker = _extract_ticker(text, asset_list)

    if not ticker:
        await update.message.reply_text("❌ Не найден. Выберите из списка!")
        return PREDICTION_ASSET_STATE

    user_id = update.effective_user.id
    direction = context.user_data.get('pred_direction', 'up')

    # Проверить лимит (макс 5 активных предсказаний)
    active = db.prediction_count_active(user_id, mode)
    if active >= 5:
        await update.message.reply_text(
            "⚠️ Максимум 5 активных предсказаний!\n"
            "Дождись результатов или проверь через 🔮",
            reply_markup=get_prediction_keyboard()
        )
        return -1

    # Получить текущую цену
    price_data = await get_asset_price(ticker, mode, 'usd')
    if not price_data or not price_data.get('price'):
        await update.message.reply_text(
            "❌ Не удалось получить цену. Попробуйте позже.",
            reply_markup=get_prediction_keyboard()
        )
        return -1

    price = price_data['price']
    emoji = asset_list[ticker]['emoji']
    name = asset_list[ticker]['name']
    dir_label = "📈 ВВЕРХ" if direction == 'up' else "📉 ВНИЗ"

    pid = db.prediction_create(user_id, ticker, direction, price, mode)

    await update.message.reply_text(
        f"🎯 ПРЕДСКАЗАНИЕ СОЗДАНО!\n"
        f"{'━' * 28}\n\n"
        f"{emoji} {name} ({ticker})\n\n"
        f"💰 Текущая цена: ${price:,.4f}\n"
        f"🎯 Твой прогноз: {dir_label}\n"
        f"📋 ID: #{pid}\n\n"
        f"{'━' * 28}\n"
        f"Проверь результат позже через 🔮 Проверить!\n"
        f"Цена должна измениться минимум на 0.5%",
        reply_markup=get_prediction_keyboard()
    )
    return -1


async def show_my_predictions(update, context):
    """Показать активные предсказания"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    preds = db.prediction_get_active(user_id, mode)

    if not preds:
        await update.message.reply_text(
            "📋 У вас нет активных предсказаний.\n\n"
            "Нажмите 📈 или 📉 чтобы создать!",
            reply_markup=get_prediction_keyboard()
        )
        return

    text = f"📋 МОИ ПРЕДСКАЗАНИЯ\n{'━' * 28}\n\n"
    for p in preds:
        pid, _, ticker, direction, price, at, predicted_at = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
        dir_em = "📈" if direction == 'up' else "📉"
        emoji = asset_list.get(ticker, {}).get('emoji', '•')
        text += (
            f"#{pid} {emoji} {ticker} {dir_em}\n"
            f"   💰 Цена входа: ${price:,.4f}\n"
            f"   📅 {predicted_at[:16] if predicted_at else '?'}\n\n"
        )

    text += f"{'━' * 28}\nНажми 🔮 Проверить для результатов!"
    await update.message.reply_text(text, reply_markup=get_prediction_keyboard())


async def check_predictions(update, context):
    """Проверить и закрыть предсказания"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    preds = db.prediction_get_active(user_id, mode)

    if not preds:
        await update.message.reply_text(
            "📋 Нет активных предсказаний для проверки!",
            reply_markup=get_prediction_keyboard()
        )
        return

    msg = await update.message.reply_text("🔮 Проверяю предсказания...")

    # Получить текущие цены
    prices = await get_all_asset_prices(mode, 'usd')
    if not prices:
        try:
            await msg.edit_text("❌ Не удалось загрузить цены")
        except Exception:
            pass
        return

    results = []
    for p in preds:
        pid, _, ticker, direction, old_price = p[0], p[1], p[2], p[3], p[4]
        current_price = prices.get(ticker)
        if current_price is None:
            continue

        # Минимальное изменение 0.5% для решения
        change_pct = ((current_price - old_price) / old_price * 100) if old_price else 0
        if abs(change_pct) < 0.5:
            results.append((pid, ticker, direction, old_price, current_price, change_pct, 'pending'))
            continue

        went_up = current_price > old_price
        correct = (direction == 'up' and went_up) or (direction == 'down' and not went_up)
        result_str = 'correct' if correct else 'wrong'
        db.prediction_resolve(pid, result_str)
        results.append((pid, ticker, direction, old_price, current_price, change_pct, result_str))

    text = f"🔮 РЕЗУЛЬТАТЫ ПРЕДСКАЗАНИЙ\n{'━' * 28}\n\n"
    for pid, ticker, direction, old_p, cur_p, ch_pct, result in results:
        dir_em = "📈" if direction == 'up' else "📉"
        emoji = asset_list.get(ticker, {}).get('emoji', '•')
        if result == 'correct':
            res_em = "✅ УГАДАЛ!"
        elif result == 'wrong':
            res_em = "❌ Мимо!"
        else:
            res_em = "⏳ Ждём (< 0.5%)"

        text += (
            f"#{pid} {emoji} {ticker} {dir_em}\n"
            f"   💰 Вход: ${old_p:,.4f} → ${cur_p:,.4f}\n"
            f"   📊 Изменение: {ch_pct:+.2f}%\n"
            f"   {res_em}\n\n"
        )

    total, correct, wrong = db.prediction_get_stats(user_id)
    accuracy = (correct / total * 100) if total > 0 else 0
    text += (
        f"{'━' * 28}\n"
        f"📊 Общая точность: {accuracy:.0f}% ({correct}/{total})"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_prediction_keyboard())


async def show_prediction_stats(update, context):
    """Подробная статистика предсказаний"""
    user_id = update.effective_user.id
    total, correct, wrong = db.prediction_get_stats(user_id)
    accuracy = (correct / total * 100) if total > 0 else 0

    # Уровень трейдера
    if total == 0:
        rank = "🐣 Новичок"
    elif accuracy >= 80 and total >= 10:
        rank = "🦅 Гуру рынка"
    elif accuracy >= 70 and total >= 5:
        rank = "🐺 Волк с Уолл-стрит"
    elif accuracy >= 60:
        rank = "🦊 Хитрый трейдер"
    elif accuracy >= 50:
        rank = "🐒 Обезьяна с дартс"
    else:
        rank = "🐢 Нужна практика"

    text = (
        f"📊 СТАТИСТИКА ПРЕДСКАЗАНИЙ\n"
        f"{'━' * 28}\n\n"
        f"🏅 Ранг: {rank}\n\n"
        f"📋 Всего предсказаний: {total}\n"
        f"✅ Угадано: {correct}\n"
        f"❌ Не угадано: {wrong}\n"
        f"🎯 Точность: {accuracy:.1f}%\n\n"
        f"{'━' * 28}\n"
    )

    if total >= 10:
        if accuracy >= 70:
            text += "🌟 Отличный результат! Ты чувствуешь рынок!"
        elif accuracy >= 50:
            text += "👍 Неплохо! Ты лучше случайности!"
        else:
            text += "📚 Продолжай практиковаться!"
    else:
        text += f"📈 Сделай ещё {max(0, 10 - total)} предсказаний для полной статистики"

    await update.message.reply_text(text, reply_markup=get_prediction_keyboard())


# ==================== 💼 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ ====================

def get_portfolio_keyboard():
    """Клавиатура портфеля"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Купить"), KeyboardButton("💸 Продать")],
        [KeyboardButton("📊 Мой портфель"), KeyboardButton("📈 P&L")],
        [KeyboardButton("🗑 Очистить 💼")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


async def show_portfolio_menu(update, context):
    """Меню виртуального портфеля"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.portfolio_count(user_id, mode)
    label = asset_label(mode)

    await update.message.reply_text(
        f"💼 ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ\n"
        f"{'═' * 28}\n\n"
        f"Торгуй без риска!\n"
        f"Покупай и продавай виртуально,\n"
        f"отслеживай прибыль и убытки.\n\n"
        f"📊 Активов в портфеле: {count}\n\n"
        f"💰 Купить — добавить актив\n"
        f"💸 Продать — продать из портфеля\n"
        f"📊 Мой портфель — текущие позиции\n"
        f"📈 P&L — прибыль/убыток\n"
        f"🗑 Очистить — удалить всё",
        reply_markup=get_portfolio_keyboard()
    )


async def portfolio_buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало покупки — выбрать актив"""
    context.user_data['portfolio_action'] = 'buy'
    mode = get_mode(context)

    await update.message.reply_text(
        f"💰 ПОКУПКА\n"
        f"{'━' * 28}\n\n"
        f"Выберите актив для покупки:",
        reply_markup=get_crypto_keyboard_plain(mode)
    )
    return PORTFOLIO_ASSET_STATE


async def portfolio_sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало продажи — выбрать актив"""
    context.user_data['portfolio_action'] = 'sell'
    user_id = update.effective_user.id
    mode = get_mode(context)

    portfolio = db.portfolio_get_aggregated(user_id, mode)
    if not portfolio:
        await update.message.reply_text(
            "📋 Портфель пуст! Сначала купите что-нибудь.",
            reply_markup=get_portfolio_keyboard()
        )
        return -1

    asset_list = get_asset_list(mode)
    buttons = []
    row = []
    for ticker in portfolio:
        if ticker in asset_list:
            emoji = asset_list[ticker]['emoji']
            row.append(KeyboardButton(f"{emoji} {ticker}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])

    await update.message.reply_text(
        f"💸 ПРОДАЖА\n"
        f"{'━' * 28}\n\n"
        f"Выберите актив для продажи:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return PORTFOLIO_ASSET_STATE


async def portfolio_choose_asset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор актива для портфеля"""
    text = update.message.text.strip()

    if text in ("Отмена", "↩️ Назад"):
        await update.message.reply_text("❌ Отменено", reply_markup=get_portfolio_keyboard())
        return -1

    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    ticker = _extract_ticker(text, asset_list)

    if not ticker:
        await update.message.reply_text("❌ Не найден. Выберите из списка!")
        return PORTFOLIO_ASSET_STATE

    context.user_data['portfolio_ticker'] = ticker
    action = context.user_data.get('portfolio_action', 'buy')

    if action == 'sell':
        user_id = update.effective_user.id
        portfolio = db.portfolio_get_aggregated(user_id, mode)
        qty = portfolio.get(ticker, (0, 0))[0]
        if qty <= 0:
            await update.message.reply_text(
                f"❌ У вас нет {ticker} в портфеле!",
                reply_markup=get_portfolio_keyboard()
            )
            return -1

        emoji = asset_list[ticker]['emoji']
        await update.message.reply_text(
            f"💸 Продажа {emoji} {ticker}\n"
            f"{'━' * 28}\n\n"
            f"📊 У вас: {qty:.6g} {ticker}\n\n"
            f"Введите количество для продажи\n"
            f"(или «все» для продажи всего):",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Все")], [KeyboardButton("Отмена")]],
                resize_keyboard=True
            )
        )
    else:
        emoji = asset_list[ticker]['emoji']
        await update.message.reply_text(
            f"💰 Покупка {emoji} {ticker}\n"
            f"{'━' * 28}\n\n"
            f"Введите сумму покупки в $\n"
            f"(например: 1000)",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("100"), KeyboardButton("500"), KeyboardButton("1000")],
                 [KeyboardButton("5000"), KeyboardButton("10000")],
                 [KeyboardButton("Отмена")]],
                resize_keyboard=True
            )
        )
    return PORTFOLIO_AMOUNT_STATE


async def portfolio_set_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать сумму покупки/продажи"""
    text = update.message.text.strip()

    if text in ("Отмена", "↩️ Назад"):
        await update.message.reply_text("❌ Отменено", reply_markup=get_portfolio_keyboard())
        return -1

    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    ticker = context.user_data.get('portfolio_ticker')
    action = context.user_data.get('portfolio_action', 'buy')

    if not ticker or ticker not in asset_list:
        await update.message.reply_text("❌ Ошибка. Попробуйте заново.", reply_markup=get_portfolio_keyboard())
        return -1

    emoji = asset_list[ticker]['emoji']
    name = asset_list[ticker]['name']

    # Получить текущую цену
    price_data = await get_asset_price(ticker, mode, 'usd')
    if not price_data or not price_data.get('price'):
        await update.message.reply_text("❌ Не удалось получить цену.", reply_markup=get_portfolio_keyboard())
        return -1

    price = price_data['price']

    if action == 'buy':
        try:
            amount = float(text.replace(',', '.').replace('$', '').replace(' ', ''))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введите положительное число!")
            return PORTFOLIO_AMOUNT_STATE

        quantity = amount / price
        db.portfolio_buy(user_id, ticker, quantity, price, mode)

        await update.message.reply_text(
            f"✅ КУПЛЕНО!\n"
            f"{'━' * 28}\n\n"
            f"{emoji} {name} ({ticker})\n\n"
            f"💰 Цена: ${price:,.4f}\n"
            f"💵 Сумма: ${amount:,.2f}\n"
            f"📊 Кол-во: {quantity:.6g} шт.\n\n"
            f"Позиция добавлена в портфель!",
            reply_markup=get_portfolio_keyboard()
        )
    else:  # sell
        if text.lower() in ('все', 'всё', 'all'):
            portfolio = db.portfolio_get_aggregated(user_id, mode)
            qty_to_sell = portfolio.get(ticker, (0, 0))[0]
        else:
            try:
                qty_to_sell = float(text.replace(',', '.'))
                if qty_to_sell <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ Введите число или «все»!")
                return PORTFOLIO_AMOUNT_STATE

        sold = db.portfolio_sell(user_id, ticker, qty_to_sell, mode)
        sell_value = sold * price

        await update.message.reply_text(
            f"✅ ПРОДАНО!\n"
            f"{'━' * 28}\n\n"
            f"{emoji} {name} ({ticker})\n\n"
            f"💰 Цена: ${price:,.4f}\n"
            f"📊 Продано: {sold:.6g} шт.\n"
            f"💵 Выручка: ${sell_value:,.2f}",
            reply_markup=get_portfolio_keyboard()
        )

    return -1


async def show_portfolio_view(update, context):
    """Показать содержимое портфеля"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    portfolio = db.portfolio_get_aggregated(user_id, mode)

    if not portfolio:
        await update.message.reply_text(
            "📋 Портфель пуст!\n\nНажмите 💰 Купить чтобы начать.",
            reply_markup=get_portfolio_keyboard()
        )
        return

    text = f"📊 МОЙ ПОРТФЕЛЬ\n{'━' * 28}\n\n"
    total_invested = 0

    for ticker, (qty, avg_price) in portfolio.items():
        emoji = asset_list.get(ticker, {}).get('emoji', '•')
        invested = qty * avg_price
        total_invested += invested
        text += (
            f"{emoji} {ticker}: {qty:.6g} шт.\n"
            f"   Средняя: ${avg_price:,.4f}\n"
            f"   Вложено: ${invested:,.2f}\n\n"
        )

    text += (
        f"{'━' * 28}\n"
        f"💰 Всего вложено: ${total_invested:,.2f}\n\n"
        f"📈 Нажми P&L для текущей прибыли"
    )

    await update.message.reply_text(text, reply_markup=get_portfolio_keyboard())


async def show_portfolio_pnl(update, context):
    """Показать прибыль/убыток портфеля"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    portfolio = db.portfolio_get_aggregated(user_id, mode)

    if not portfolio:
        await update.message.reply_text(
            "📋 Портфель пуст!",
            reply_markup=get_portfolio_keyboard()
        )
        return

    msg = await update.message.reply_text("⏳ Считаю P&L...")

    prices = await get_all_asset_prices(mode, 'usd')
    if not prices:
        try:
            await msg.edit_text("❌ Не удалось загрузить цены")
        except Exception:
            pass
        return

    text = f"📈 ПРИБЫЛЬ / УБЫТОК\n{'━' * 28}\n\n"
    total_invested = 0
    total_current = 0

    for ticker, (qty, avg_price) in portfolio.items():
        current_price = prices.get(ticker, 0)
        invested = qty * avg_price
        current_val = qty * current_price
        pnl = current_val - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0

        total_invested += invested
        total_current += current_val

        emoji = asset_list.get(ticker, {}).get('emoji', '•')
        pnl_icon = "🟢" if pnl >= 0 else "🔴"

        text += (
            f"{emoji} {ticker} {pnl_icon}\n"
            f"   📊 {qty:.6g} × ${current_price:,.4f}\n"
            f"   💰 Вложено: ${invested:,.2f}\n"
            f"   💵 Сейчас: ${current_val:,.2f}\n"
            f"   {'📈' if pnl >= 0 else '📉'} P&L: ${pnl:+,.2f} ({pnl_pct:+.1f}%)\n\n"
        )

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    total_icon = "🟢" if total_pnl >= 0 else "🔴"

    text += (
        f"{'━' * 28}\n"
        f"{total_icon} ИТОГО:\n"
        f"💰 Вложено: ${total_invested:,.2f}\n"
        f"💵 Текущее: ${total_current:,.2f}\n"
        f"{'📈' if total_pnl >= 0 else '📉'} P&L: ${total_pnl:+,.2f} ({total_pnl_pct:+.1f}%)"
    )

    try:
        await msg.edit_text(text)
    except Exception:
        await update.message.reply_text(text, reply_markup=get_portfolio_keyboard())


async def portfolio_clear_cmd(update, context):
    """Очистить портфель"""
    user_id = update.effective_user.id
    mode = get_mode(context)
    count = db.portfolio_clear(user_id, mode)
    await update.message.reply_text(
        f"🗑 Портфель очищен! Удалено позиций: {count}",
        reply_markup=get_portfolio_keyboard()
    )


# ==================== 💡 СОВЕТ ДНЯ ====================

DAILY_TIPS = [
    "💡 Никогда не инвестируй больше, чем готов потерять. Это золотое правило крипторынка.",
    "💡 DYOR — Do Your Own Research. Всегда изучай проект перед вложением.",
    "💡 Не поддавайся FOMO! Если цена уже взлетела, возможно, ты опоздал.",
    "💡 Диверсификация — ключ к выживанию. Не ставь всё на одну монету.",
    "💡 Холодный кошелёк — лучший друг криптоинвестора. \"Not your keys, not your coins!\"",
    "💡 DCA (Dollar Cost Averaging) — покупай регулярно небольшими частями, не пытайся угадать дно.",
    "💡 Выходи из позиции постепенно. Не жди, что продашь на самом пике.",
    "💡 Следи за объёмами! Рост без объёма — подозрительный сигнал.",
    "💡 Не торгуй на эмоциях. Составь план и следуй ему.",
    "💡 Фиксируй прибыль! Бумажная прибыль — ещё не прибыль.",
    "💡 Будь осторожен с плечом (leverage). Кредитное плечо умножает и прибыль, и убытки.",
    "💡 Изучай графики, но помни: прошлые результаты не гарантируют будущих.",
    "💡 Медвежий рынок — лучшее время для обучения и накопления.",
    "💡 Seed-фразу храни в надёжном месте ОФФЛАЙН. Никому не показывай!",
    "💡 Остерегайся схем «быстрого обогащения». Если звучит слишком хорошо — это скам.",
    "💡 Не путай инвестирование и трейдинг. Выбери свою стратегию.",
    "💡 Следи за действиями крупных фондов — они часто задают тренд.",
    "💡 Помни о налогах! Во многих странах крипто-доходы облагаются налогом.",
    "💡 Не забывай о стейкинге — пассивный доход от удержания монет.",
    "💡 Рынок циклический: бычий → медвежий → бычий. Терпение награждается.",
    "💡 Индекс Страха и Жадности — отличный индикатор настроений рынка.",
    "💡 Никогда не раскрывай размер своего портфеля в публичных чатах.",
    "💡 Ставь стоп-лосс! Он спасёт от катастрофических потерь.",
    "💡 Лучшая инвестиция — в образование. Разбирайся в технологиях!",
    "💡 Биткоин — это не вся крипта. Изучай экосистему DeFi, NFT, Layer 2.",
    "💡 Если все вокруг покупают — задумайся. Если все продают — присмотрись.",
    "💡 Хороший проект имеет: активную команду, whitepaper, работающий продукт.",
    "💡 Не слушай «крипто-гуру» в Telegram. Большинство из них — мошенники.",
    "💡 Регулирование — не враг. Оно делает рынок зрелее и безопаснее.",
    "💡 Помни: 90% альткоинов не переживут следующий медвежий рынок.",
]

DAILY_TIPS_STOCKS = [
    "📊 P/E (Price-to-Earnings) — базовый мультипликатор для оценки акций.",
    "📊 Дивидендные акции — отличный источник пассивного дохода.",
    "📊 ETF — простой способ диверсифицировать портфель одной покупкой.",
    "📊 Следи за отчётностью! Квартальные отчёты двигают рынок.",
    "📊 S&P 500 исторически растёт ~10% в год. Терпение = прибыль.",
    "📊 Покупай то, что понимаешь. Уоррен Баффет следует этому правилу.",
    "📊 Не пытайся обыграть рынок каждый день. Долгосрочные инвесторы выигрывают.",
    "📊 Обращай внимание на free cash flow — это реальные деньги компании.",
    "📊 Рынок может оставаться иррациональным дольше, чем ты — платёжеспособным.",
    "📊 Сектор технологий — двигатель роста, но и больший риск.",
]


# ==================== 📰 НОВОСТИ РЫНКА [Free] ====================

MARKET_NEWS_CRYPTO = [
    {"title": "Bitcoin халвинг", "text": "Халвинг BTC происходит каждые ~4 года, уменьшая награду майнерам вдвое. Исторически после халвинга цена растёт в течение 12-18 месяцев."},
    {"title": "Ethereum и стейкинг", "text": "После перехода на Proof-of-Stake, ETH стал дефляционным активом. Более 27 млн ETH залочено в стейкинге, снижая предложение на рынке."},
    {"title": "Институциональные инвесторы", "text": "BlackRock, Fidelity и другие гиганты вошли в крипто через Bitcoin ETF. Это привлекает триллионы долларов традиционного капитала."},
    {"title": "Регулирование крипто", "text": "SEC, MiCA (Европа) и другие регуляторы формируют правила игры. Чёткие правила привлекают больше инвесторов."},
    {"title": "DeFi и ликвидность", "text": "Децентрализованные финансы (DeFi) позволяют зарабатывать на предоставлении ликвидности. TVL протоколов превышает $100 млрд."},
    {"title": "Layer 2 решения", "text": "Arbitrum, Optimism, Base — Layer 2 сети снижают комиссии Ethereum в 10-100 раз, ускоряя массовое принятие."},
    {"title": "Стейблкоины", "text": "USDT и USDC — основа крипто-рынка. Вместе они контролируют более $150 млрд, обеспечивая ликвидность бирж."},
    {"title": "NFT и токенизация", "text": "Токенизация реальных активов (RWA) — новый тренд. Недвижимость, акции и облигации переходят на блокчейн."},
    {"title": "Мемкоины", "text": "DOGE, SHIB, PEPE — мемкоины создают хайп, но крайне волатильны. 95% мемкоинов теряют стоимость за первый год."},
    {"title": "AI и крипто", "text": "Токены AI-проектов (FET, RENDER) стали трендом. Объединение AI и блокчейна открывает новые возможности."},
    {"title": "Корреляция BTC и рынков", "text": "Bitcoin постепенно отделяется от фондового рынка, становясь самостоятельным классом активов как 'цифровое золото'."},
    {"title": "Lightning Network", "text": "Сеть Lightning позволяет отправлять BTC мгновенно с минимальной комиссией. El Salvador использует её для повседневных платежей."},
]

MARKET_NEWS_STOCKS = [
    {"title": "AI-революция", "text": "NVIDIA, Microsoft, Google лидируют в AI-гонке. Рынок AI оценивается в $500+ млрд и удваивается каждые 2 года."},
    {"title": "Сезон отчётностей", "text": "Квартальные отчёты (earnings) — ключевые события для акций. Компании отчитываются каждые 3 месяца, двигая рынок."},
    {"title": "Процентные ставки ФРС", "text": "Ставка ФРС напрямую влияет на рынок акций. Снижение ставок = рост рынка, повышение = давление на акции."},
    {"title": "Индексы S&P 500 и NASDAQ", "text": "S&P 500 включает 500 крупнейших компаний США. За последние 50 лет индекс приносил ~10% годовых."},
    {"title": "Дивиденды", "text": "Дивидендные акции (KO, JNJ, PG) обеспечивают стабильный доход. Некоторые компании повышают дивиденды 50+ лет подряд."},
    {"title": "Buyback программы", "text": "Apple, Google, Meta тратят миллиарды на выкуп собственных акций. Это повышает EPS и поддерживает курс."},
    {"title": "Электромобили", "text": "Tesla, Rivian, BYD — рынок EV трансформирует автопром. К 2030 году электромобили займут 30%+ рынка."},
    {"title": "Облачные технологии", "text": "AWS (Amazon), Azure (Microsoft), GCP (Google) — рынок облачных услуг растёт на 20%+ в год."},
    {"title": "Геополитические риски", "text": "Торговые войны, санкции и конфликты влияют на глобальные рынки. Диверсификация — лучшая защита."},
    {"title": "IPO тренды", "text": "Выход компаний на биржу создаёт возможности. Но 60% IPO торгуются ниже цены размещения через год."},
]


async def show_market_news(update, context):
    """Новости и факты о рынке — бесплатно для всех"""
    mode = get_mode(context)

    today = datetime.now().strftime("%Y-%m-%d")
    seed = hash(today + "news")
    random.seed(seed)

    if mode == 'stocks':
        pool = MARKET_NEWS_STOCKS
    else:
        pool = MARKET_NEWS_CRYPTO

    # 3 случайные новости на сегодня
    news = random.sample(pool, min(3, len(pool)))
    random.seed()

    report = (
        f"📰 НОВОСТИ РЫНКА\n"
        f"{'━' * 28}\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y')}\n"
        f"{'━' * 28}\n\n"
    )

    for i, n in enumerate(news, 1):
        report += (
            f"{'📌' if i == 1 else '📎'} {n['title']}\n"
            f"{n['text']}\n\n"
        )

    report += (
        f"{'━' * 28}\n"
        f"🔄 Новые новости — завтра!\n"
        f"💡 Следи за рынком каждый день."
    )

    await update.message.reply_text(report, reply_markup=get_extra_keyboard())


# ==================== 🏅 ТОП-3 ДНЯ [Free] ====================

async def show_top3_today(update, context):
    """Топ-3 роста и топ-3 падения — бесплатно"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("⏳ Загружаю топ дня...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in asset_list.items():
        if mode == 'stocks':
            d = None
            for s in (data if isinstance(data, list) else []):
                sym = s.get('symbol', '').upper()
                if sym == ticker.upper():
                    d = s
                    break
            if d:
                price = d.get('price', 0)
                change = d.get('change_24h', 0) or 0
            else:
                continue
        else:
            cg_id = info.get('id', info.get('coingecko_id', ticker.lower()))
            d = data.get(cg_id) if isinstance(data, dict) else None
            if d:
                price = d.get('usd', 0) or 0
                change = d.get('usd_24h_change', 0) or 0
            else:
                continue

        if price and price > 0:
            items.append({
                'ticker': ticker,
                'emoji': info['emoji'],
                'name': info['name'],
                'price': price,
                'change': change
            })

    if len(items) < 3:
        try:
            await msg.edit_text("❌ Недостаточно данных")
        except Exception:
            pass
        return

    items.sort(key=lambda x: x['change'], reverse=True)
    top3 = items[:3]
    bottom3 = items[-3:][::-1]  # худшие, от худшего к лучшему

    report = (
        f"🏅 ТОП-3 ДНЯ\n"
        f"{'━' * 28}\n"
        f"📊 {label}\n"
        f"{'━' * 28}\n\n"
        f"📈 ЛИДЕРЫ РОСТА:\n\n"
    )

    medals_up = ["🥇", "🥈", "🥉"]
    for i, item in enumerate(top3):
        report += (
            f"{medals_up[i]} {item['emoji']} {item['ticker']}"
            f" — {item['name']}\n"
            f"   💰 ${format_price(item['price'])}"
            f" | 🟢 +{item['change']:.2f}%\n\n"
        )

    report += f"📉 ЛИДЕРЫ ПАДЕНИЯ:\n\n"

    medals_down = ["💀", "☠️", "👎"]
    for i, item in enumerate(bottom3):
        report += (
            f"{medals_down[i]} {item['emoji']} {item['ticker']}"
            f" — {item['name']}\n"
            f"   💰 ${format_price(item['price'])}"
            f" | 🔴 {item['change']:.2f}%\n\n"
        )

    avg = sum(it['change'] for it in items) / len(items)
    report += (
        f"{'━' * 28}\n"
        f"📊 Средний рынок: {avg:+.2f}%\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)


# ==================== 📉 ВОЛАТИЛЬНОСТЬ [Pro] ====================

async def show_volatility_analysis(update, context):
    """Анализ волатильности активов за 30 дней"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("⏳ Анализирую волатильность...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in asset_list.items():
        # Получаем историю
        try:
            if mode == 'stocks':
                history = await stocks_api.fetch_stock_history(ticker, days=30)
            else:
                cg_id = info.get('id', info.get('coingecko_id', ticker.lower()))
                history = await fetch_crypto_history(cg_id, days=30)
        except Exception:
            history = None

        if not history or len(history) < 7:
            continue

        # Рассчитываем волатильность
        changes = []
        for j in range(1, len(history)):
            if history[j-1] > 0:
                changes.append(abs((history[j] - history[j-1]) / history[j-1] * 100))

        if not changes:
            continue

        avg_daily_vol = sum(changes) / len(changes)
        max_daily = max(changes)
        total_change = ((history[-1] - history[0]) / history[0] * 100) if history[0] > 0 else 0
        current_price = history[-1]

        # Мини-график волатильности
        levels = "▁▂▃▄▅▆▇█"
        mn = min(changes[-10:]) if len(changes) >= 10 else min(changes)
        mx = max(changes[-10:]) if len(changes) >= 10 else max(changes)
        rng = mx - mn if mx != mn else 1
        chart = ""
        for c in changes[-10:]:
            idx = int((c - mn) / rng * (len(levels) - 1))
            chart += levels[idx]

        items.append({
            'ticker': ticker,
            'emoji': info['emoji'],
            'name': info['name'],
            'price': current_price,
            'avg_vol': avg_daily_vol,
            'max_vol': max_daily,
            'total_change': total_change,
            'chart': chart,
        })

    if not items:
        try:
            await msg.edit_text("❌ Не удалось получить исторические данные")
        except Exception:
            pass
        return

    # Сортируем по волатильности
    items.sort(key=lambda x: x['avg_vol'], reverse=True)

    report = (
        f"📉 АНАЛИЗ ВОЛАТИЛЬНОСТИ\n"
        f"{'━' * 28}\n"
        f"📊 {label} | 30 дней\n"
        f"{'━' * 28}\n\n"
    )

    # Категории
    high_vol = [i for i in items if i['avg_vol'] >= 5]
    med_vol = [i for i in items if 2 <= i['avg_vol'] < 5]
    low_vol = [i for i in items if i['avg_vol'] < 2]

    report += f"🔴 Высокая ({len(high_vol)}) | 🟡 Средняя ({len(med_vol)}) | 🟢 Низкая ({len(low_vol)})\n\n"

    # Топ-10 самых волатильных
    for i, item in enumerate(items[:10], 1):
        if item['avg_vol'] >= 5:
            level = "🔴"
        elif item['avg_vol'] >= 2:
            level = "🟡"
        else:
            level = "🟢"

        trend = "📈" if item['total_change'] >= 0 else "📉"

        report += (
            f"{level} #{i} {item['emoji']} {item['ticker']}\n"
            f"   Ср. дневная: {item['avg_vol']:.2f}%"
            f" | Макс: {item['max_vol']:.1f}%\n"
            f"   {trend} За 30д: {item['total_change']:+.1f}%"
            f" | ${format_price(item['price'])}\n"
            f"   {item['chart']}\n\n"
        )

    # Самый стабильный
    most_stable = items[-1]
    report += (
        f"{'━' * 28}\n"
        f"🛡 Самый стабильный: {most_stable['emoji']} {most_stable['ticker']}"
        f" ({most_stable['avg_vol']:.2f}%/д)\n"
        f"⚡ Самый волатильный: {items[0]['emoji']} {items[0]['ticker']}"
        f" ({items[0]['avg_vol']:.2f}%/д)\n\n"
        f"💡 Высокая волатильность = больше риска\n"
        f"и больше возможностей."
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_asset_keyboard()
    )


# ==================== 📊 ОБЪЁМ ПРОФИЛЬ [Pro] ====================

async def show_volume_profile(update, context):
    """Профиль объёмов — анализ активности торгов"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("⏳ Анализирую объёмы торгов...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    total_volume = 0
    total_mcap = 0

    for ticker, info in asset_list.items():
        if mode == 'stocks':
            d = None
            for s in (data if isinstance(data, list) else []):
                sym = s.get('symbol', '').upper()
                if sym == ticker.upper():
                    d = s
                    break
            if d:
                price = d.get('price', 0)
                volume = d.get('volume', 0) or 0
                mcap = d.get('market_cap', 0) or 0
                change = d.get('change_24h', 0) or 0
            else:
                continue
        else:
            cg_id = info.get('id', info.get('coingecko_id', ticker.lower()))
            d = data.get(cg_id) if isinstance(data, dict) else None
            if d:
                price = d.get('usd', 0) or 0
                volume = d.get('usd_24h_vol', 0) or 0
                mcap = d.get('usd_market_cap', 0) or 0
                change = d.get('usd_24h_change', 0) or 0
            else:
                continue

        if price <= 0 or volume <= 0:
            continue

        vol_mcap = (volume / mcap * 100) if mcap > 0 else 0
        total_volume += volume
        total_mcap += mcap

        items.append({
            'ticker': ticker,
            'emoji': info['emoji'],
            'name': info['name'],
            'price': price,
            'volume': volume,
            'mcap': mcap,
            'change': change,
            'vol_mcap': vol_mcap,
        })

    if not items:
        try:
            await msg.edit_text("❌ Нет данных об объёмах")
        except Exception:
            pass
        return

    # Сортируем по vol/mcap (самые активные)
    items.sort(key=lambda x: x['vol_mcap'], reverse=True)

    report = (
        f"📊 ПРОФИЛЬ ОБЪЁМОВ\n"
        f"{'━' * 28}\n"
        f"📈 {label}\n"
        f"{'━' * 28}\n\n"
        f"💰 Общий объём 24ч: ${format_volume(total_volume)}\n"
        f"💎 Общая кап-ция: ${format_volume(total_mcap)}\n"
        f"📊 Общий V/M: {(total_volume/total_mcap*100):.2f}%\n\n"
    )

    # Аномально высокий объём
    avg_vol_mcap = sum(i['vol_mcap'] for i in items) / len(items)
    hot = [i for i in items if i['vol_mcap'] > avg_vol_mcap * 2]

    if hot:
        report += f"🔥 АНОМАЛЬНЫЙ ОБЪЁМ ({len(hot)}):\n\n"
        for h in hot[:5]:
            report += (
                f"   {h['emoji']} {h['ticker']} — V/M: {h['vol_mcap']:.1f}%\n"
                f"   📊 Объём: ${format_volume(h['volume'])}"
                f" | {h['change']:+.1f}%\n\n"
            )

    report += f"📋 ТОП-10 ПО АКТИВНОСТИ:\n\n"

    for i, item in enumerate(items[:10], 1):
        if item['vol_mcap'] > avg_vol_mcap * 2:
            icon = "🔥"
        elif item['vol_mcap'] > avg_vol_mcap:
            icon = "📈"
        else:
            icon = "📊"

        report += (
            f"{icon} #{i} {item['emoji']} {item['ticker']}\n"
            f"   Объём: ${format_volume(item['volume'])}"
            f" | V/M: {item['vol_mcap']:.2f}%\n"
        )

    report += (
        f"\n{'━' * 28}\n"
        f"💡 V/M > {avg_vol_mcap*2:.1f}% = аномальный объём\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_asset_keyboard()
    )


# ==================== 💎 DCA КАЛЬКУЛЯТОР [Premium] ====================

async def show_dca_calculator(update, context):
    """DCA (Dollar Cost Averaging) калькулятор"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("⏳ Считаю DCA стратегии...")

    # Берём топ-10 активов по капитализации
    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in asset_list.items():
        if mode == 'stocks':
            d = None
            for s in (data if isinstance(data, list) else []):
                sym = s.get('symbol', '').upper()
                if sym == ticker.upper():
                    d = s
                    break
            if d:
                price = d.get('price', 0)
                mcap = d.get('market_cap', 0) or 0
                change = d.get('change_24h', 0) or 0
            else:
                continue
        else:
            cg_id = info.get('id', info.get('coingecko_id', ticker.lower()))
            d = data.get(cg_id) if isinstance(data, dict) else None
            if d:
                price = d.get('usd', 0) or 0
                mcap = d.get('usd_market_cap', 0) or 0
                change = d.get('usd_24h_change', 0) or 0
            else:
                continue

        if price <= 0:
            continue

        # Получаем историю
        try:
            if mode == 'stocks':
                history = await stocks_api.fetch_stock_history(ticker, days=30)
            else:
                cg_id_h = info.get('id', info.get('coingecko_id', ticker.lower()))
                history = await fetch_crypto_history(cg_id_h, days=30)
        except Exception:
            history = None

        if not history or len(history) < 7:
            continue

        # Симулируем DCA: $100 каждую неделю последние 30 дней
        weekly_invest = 100
        weeks = len(history) // 7
        if weeks < 1:
            continue

        total_invested = 0
        total_coins = 0
        for w in range(weeks):
            day_idx = w * 7
            if day_idx < len(history) and history[day_idx] > 0:
                total_invested += weekly_invest
                total_coins += weekly_invest / history[day_idx]

        current_value = total_coins * price
        dca_profit = current_value - total_invested
        dca_pct = (dca_profit / total_invested * 100) if total_invested > 0 else 0

        # Lump sum (всё сразу в начале)
        lump_coins = total_invested / history[0] if history[0] > 0 else 0
        lump_value = lump_coins * price
        lump_profit = lump_value - total_invested
        lump_pct = (lump_profit / total_invested * 100) if total_invested > 0 else 0

        items.append({
            'ticker': ticker,
            'emoji': info['emoji'],
            'name': info['name'],
            'price': price,
            'mcap': mcap,
            'change': change,
            'total_invested': total_invested,
            'dca_value': current_value,
            'dca_profit': dca_profit,
            'dca_pct': dca_pct,
            'lump_value': lump_value,
            'lump_profit': lump_profit,
            'lump_pct': lump_pct,
            'weeks': weeks,
            'dca_wins': dca_pct > lump_pct,
        })

    if not items:
        try:
            await msg.edit_text("❌ Недостаточно данных для DCA анализа")
        except Exception:
            pass
        return

    # Сортируем по DCA прибыли
    items.sort(key=lambda x: x['dca_pct'], reverse=True)

    report = (
        f"💎 DCA КАЛЬКУЛЯТОР\n"
        f"{'━' * 28}\n"
        f"📊 {label} | 30 дней\n"
        f"💰 Стратегия: ${items[0]['total_invested']//items[0]['weeks']}/неделю × {items[0]['weeks']} нед.\n"
        f"{'━' * 28}\n\n"
    )

    dca_wins_count = sum(1 for i in items if i['dca_wins'])

    report += (
        f"📊 DCA побеждает Lump Sum: {dca_wins_count}/{len(items)} активов\n\n"
    )

    for i, item in enumerate(items[:8], 1):
        dca_icon = "🟢" if item['dca_pct'] >= 0 else "🔴"
        winner = "🏆 DCA" if item['dca_wins'] else "🏆 Lump"

        report += (
            f"{'━' * 24}\n"
            f"#{i} {item['emoji']} {item['ticker']} — {item['name']}\n"
            f"💰 Цена: ${format_price(item['price'])}\n\n"
            f"   📊 DCA ($100/нед × {item['weeks']}):\n"
            f"   Вложено: ${item['total_invested']:.0f}\n"
            f"   Стоимость: ${item['dca_value']:.2f}\n"
            f"   {dca_icon} P&L: ${item['dca_profit']:+.2f}"
            f" ({item['dca_pct']:+.1f}%)\n\n"
            f"   💼 Lump Sum (всё сразу):\n"
            f"   {'🟢' if item['lump_pct'] >= 0 else '🔴'}"
            f" P&L: ${item['lump_profit']:+.2f}"
            f" ({item['lump_pct']:+.1f}%)\n\n"
            f"   {winner}\n"
        )

    report += (
        f"\n{'━' * 28}\n"
        f"💡 DCA снижает риск входа в\n"
        f"неудачный момент. Идеально для\n"
        f"долгосрочных инвестиций.\n\n"
        f"⚠️ Прошлые данные ≠ будущее!"
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )


# ==================== 🧬 ИНДЕКС ДОМИНАЦИИ [Premium] ====================

async def show_dominance_index(update, context):
    """Индекс доминации — сколько % рынка занимает каждый актив"""
    mode = get_mode(context)
    asset_list = get_asset_list(mode)
    label = asset_label(mode)

    msg = await update.message.reply_text("⏳ Рассчитываю доминацию...")

    data = await fetch_asset_prices(mode, 'usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    total_mcap = 0
    total_vol = 0

    for ticker, info in asset_list.items():
        if mode == 'stocks':
            d = None
            for s in (data if isinstance(data, list) else []):
                sym = s.get('symbol', '').upper()
                if sym == ticker.upper():
                    d = s
                    break
            if d:
                price = d.get('price', 0)
                mcap = d.get('market_cap', 0) or 0
                volume = d.get('volume', 0) or 0
                change = d.get('change_24h', 0) or 0
            else:
                continue
        else:
            cg_id = info.get('id', info.get('coingecko_id', ticker.lower()))
            d = data.get(cg_id) if isinstance(data, dict) else None
            if d:
                price = d.get('usd', 0) or 0
                mcap = d.get('usd_market_cap', 0) or 0
                volume = d.get('usd_24h_vol', 0) or 0
                change = d.get('usd_24h_change', 0) or 0
            else:
                continue

        if price <= 0:
            continue

        total_mcap += mcap
        total_vol += volume

        items.append({
            'ticker': ticker,
            'emoji': info['emoji'],
            'name': info['name'],
            'price': price,
            'mcap': mcap,
            'volume': volume,
            'change': change,
        })

    if not items or total_mcap == 0:
        try:
            await msg.edit_text("❌ Не удалось рассчитать доминацию")
        except Exception:
            pass
        return

    # Сортируем по капитализации
    items.sort(key=lambda x: x['mcap'], reverse=True)

    # Рассчитываем доминацию
    for item in items:
        item['dominance'] = (item['mcap'] / total_mcap * 100) if total_mcap > 0 else 0
        item['vol_share'] = (item['volume'] / total_vol * 100) if total_vol > 0 else 0

    report = (
        f"🧬 ИНДЕКС ДОМИНАЦИИ\n"
        f"{'━' * 28}\n"
        f"📊 {label}\n"
        f"💎 Общая кап-ция: ${format_volume(total_mcap)}\n"
        f"📊 Общий объём: ${format_volume(total_vol)}\n"
        f"{'━' * 28}\n\n"
    )

    # Визуальная доминация топ-5
    report += "🏆 ТОП-5 ПО ДОМИНАЦИИ:\n\n"

    for i, item in enumerate(items[:5], 1):
        # Полоска доминации
        bar_len = max(1, int(item['dominance'] / 3))
        bar = "█" * bar_len + "░" * (15 - bar_len)

        medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "#4", 5: "#5"}
        medal = medals.get(i, f"#{i}")

        report += (
            f"{medal} {item['emoji']} {item['ticker']}"
            f" — {item['name']}\n"
            f"   [{bar}] {item['dominance']:.1f}%\n"
            f"   💎 Кап: ${format_volume(item['mcap'])}"
            f" | Об: ${format_volume(item['volume'])}\n"
            f"   24ч: {item['change']:+.1f}%"
            f" | Доля объёма: {item['vol_share']:.1f}%\n\n"
        )

    # Остальные (6-10)
    top5_dominance = sum(i['dominance'] for i in items[:5])
    rest_dominance = 100 - top5_dominance

    report += f"{'━' * 28}\n"
    report += f"📋 ОСТАЛЬНЫЕ ТОП-10:\n\n"

    for i, item in enumerate(items[5:10], 6):
        report += (
            f"   #{i} {item['emoji']} {item['ticker']}"
            f" — {item['dominance']:.2f}%"
            f" | {item['change']:+.1f}%\n"
        )

    # Концентрация рынка
    if items[0]['dominance'] > 50:
        concentration = "🔴 Очень высокая (1 актив > 50%)"
    elif top5_dominance > 80:
        concentration = "🟠 Высокая (топ-5 > 80%)"
    elif top5_dominance > 60:
        concentration = "🟡 Умеренная"
    else:
        concentration = "🟢 Низкая (рынок децентрализован)"

    report += (
        f"\n{'━' * 28}\n"
        f"📊 АНАЛИЗ:\n\n"
        f"   🏆 Лидер: {items[0]['emoji']} {items[0]['ticker']}"
        f" ({items[0]['dominance']:.1f}%)\n"
        f"   🏅 Топ-5: {top5_dominance:.1f}%\n"
        f"   📊 Остальные: {rest_dominance:.1f}%\n\n"
        f"   Концентрация: {concentration}\n\n"
        f"💡 Высокая доминация 1 актива =\n"
        f"весь рынок зависит от него."
    )

    try:
        await msg.edit_text(report)
    except Exception:
        await update.message.reply_text(report)

    await update.message.reply_text(
        "👇 Выбери действие:",
        reply_markup=get_premium_extra_keyboard()
    )


async def show_daily_tip(update, context):
    """Показать совет дня"""
    mode = get_mode(context)

    # Используем дату для постоянного совета на день
    today = datetime.now().strftime("%Y-%m-%d")
    seed = hash(today + str(update.effective_user.id))
    random.seed(seed)

    if mode == 'stocks':
        all_tips = DAILY_TIPS + DAILY_TIPS_STOCKS
    else:
        all_tips = DAILY_TIPS

    tip = random.choice(all_tips)
    tip_num = random.randint(1, len(all_tips))

    # Бонусный факт
    facts = [
        "🔖 Сатоши Накамото добыл первый блок 3 янв 2009.",
        "🔖 Bitcoin Pizza Day: 22 мая 2010 — 10 000 BTC за 2 пиццы.",
        "🔖 Ethereum запустился в июле 2015 года.",
        "🔖 Всего будет добыто 21 млн BTC. И ни одним больше.",
        "🔖 Первая криптобиржа Mt. Gox потеряла 850 000 BTC.",
        "🔖 Слово HODL появилось из опечатки на форуме в 2013 году.",
        "🔖 Виталику Бутерину было 19, когда он придумал Ethereum.",
        "🔖 Apple — первая компания с капитализацией $3 трлн.",
        "🔖 Warren Buffett начал инвестировать в 11 лет.",
        "🔖 Индекс S&P 500 создан в 1957 году.",
    ]
    fact = random.choice(facts)

    random.seed()  # сбросить seed

    text = (
        f"💡 СОВЕТ ДНЯ #{tip_num}\n"
        f"{'━' * 28}\n\n"
        f"{tip}\n\n"
        f"{'━' * 28}\n"
        f"{fact}\n\n"
        f"🔄 Новый совет — завтра!"
    )

    await update.message.reply_text(text, reply_markup=get_extra_keyboard())


# ==================== 🎯 ПРОВЕРКА ПРЕДСКАЗАНИЙ (ФОНОВАЯ) ====================

async def check_predictions_job(context):
    """Фоновая проверка предсказаний (каждые 5 мин)"""
    preds = db.prediction_get_all_active()
    if not preds:
        return

    # Разделить по типам
    crypto_preds = [p for p in preds if (p[5] if len(p) > 5 else 'crypto') != 'stocks']
    stock_preds = [p for p in preds if (p[5] if len(p) > 5 else 'crypto') == 'stocks']

    crypto_prices = {}
    stock_prices = {}

    if crypto_preds:
        crypto_prices = await get_all_prices('usd') or {}
    if stock_preds:
        stock_prices = await stocks_api.get_all_prices('usd') or {}

    for p in preds:
        pid = p[0]
        user_id = p[1]
        ticker = p[2]
        direction = p[3]
        old_price = p[4]
        asset_type = p[5] if len(p) > 5 else 'crypto'

        prices = stock_prices if asset_type == 'stocks' else crypto_prices
        current_price = prices.get(ticker)
        if current_price is None:
            continue

        change_pct = ((current_price - old_price) / old_price * 100) if old_price else 0

        # Автоматически закрыть если изменение > 5%
        if abs(change_pct) >= 5:
            went_up = current_price > old_price
            correct = (direction == 'up' and went_up) or (direction == 'down' and not went_up)
            result = 'correct' if correct else 'wrong'
            db.prediction_resolve(pid, result)

            # Уведомить пользователя
            res_em = "✅ УГАДАЛ!" if correct else "❌ Мимо!"
            dir_em = "📈" if direction == 'up' else "📉"
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎯 РЕЗУЛЬТАТ ПРЕДСКАЗАНИЯ\n"
                        f"{'━' * 28}\n\n"
                        f"#{pid} {ticker} {dir_em}\n"
                        f"💰 Вход: ${old_price:,.4f}\n"
                        f"💵 Сейчас: ${current_price:,.4f}\n"
                        f"📊 Изменение: {change_pct:+.2f}%\n\n"
                        f"{res_em}"
                    )
                )
            except Exception:
                pass

QUIZ_EASY = [
    # --- ОРИГИНАЛЬНЫЕ ---
    {"q": "Кто создал Bitcoin?", "a": "Сатоши Накамото",
     "opts": ["Виталик Бутерин", "Сатоши Накамото", "Чарльз Хоскинсон", "Илон Маск"]},
    {"q": "Какая крипта #2 по капитализации?", "a": "Ethereum",
     "opts": ["Solana", "BNB", "Ethereum", "XRP"]},
    {"q": "Что такое HODL?", "a": "Держать монеты, не продавать",
     "opts": ["Держать монеты, не продавать", "Торговая стратегия", "Тип кошелька", "Криптобиржа"]},
    {"q": "Какой максимальный запас BTC?", "a": "21 миллион",
     "opts": ["100 миллионов", "21 миллион", "1 миллиард", "Безлимитный"]},
    {"q": "Что такое NFT?", "a": "Невзаимозаменяемый токен",
     "opts": ["Новый финансовый тренд", "Невзаимозаменяемый токен", "Криптовалюта", "Тип блокчейна"]},
    {"q": "Кто придумал Ethereum?", "a": "Виталик Бутерин",
     "opts": ["Сатоши Накамото", "Виталик Бутерин", "Чанпэн Чжао", "Сэм Бэнкман-Фрид"]},
    {"q": "Когда был создан Bitcoin?", "a": "2009",
     "opts": ["2005", "2009", "2012", "2015"]},
    {"q": "На каком блокчейне работает DOGE?", "a": "Свой блокчейн (форк Litecoin)",
     "opts": ["Ethereum", "Свой блокчейн (форк Litecoin)", "Solana", "Bitcoin"]},
    # --- НОВЫЕ ЛЁГКИЕ ---
    {"q": "Какую криптовалюту часто называют 'цифровое золото'?", "a": "Bitcoin",
     "opts": ["Ethereum", "Bitcoin", "Litecoin", "Ripple"]},
    {"q": "Что такое блокчейн?", "a": "Цепочка блоков с данными",
     "opts": ["Криптобиржа", "Тип кошелька", "Цепочка блоков с данными", "Торговый бот"]},
    {"q": "Какая криптовалюта имеет логотип собаки?", "a": "Dogecoin",
     "opts": ["Bitcoin", "Ethereum", "Dogecoin", "Cardano"]},
    {"q": "Что такое майнинг?", "a": "Добыча криптовалюты с помощью вычислений",
     "opts": ["Покупка крипты", "Добыча криптовалюты с помощью вычислений", "Продажа токенов", "Обмен валют"]},
    {"q": "Что такое криптокошелёк?", "a": "Программа для хранения криптовалюты",
     "opts": ["Физический сейф", "Программа для хранения криптовалюты", "Биржа", "Банковский счёт"]},
    {"q": "Какая крипта связана с Илоном Маском?", "a": "Dogecoin",
     "opts": ["Bitcoin", "Ethereum", "Dogecoin", "Solana"]},
    {"q": "Что значит 'бычий рынок'?", "a": "Рынок растёт",
     "opts": ["Рынок падает", "Рынок растёт", "Рынок стоит на месте", "Рынок закрыт"]},
    {"q": "Что значит 'медвежий рынок'?", "a": "Рынок падает",
     "opts": ["Рынок растёт", "Рынок падает", "Рынок спит", "Рынок перезапускается"]},
    {"q": "Что такое альткоин?", "a": "Любая криптовалюта кроме Bitcoin",
     "opts": ["Поддельная монета", "Любая криптовалюта кроме Bitcoin", "Новая монета", "Токен на Ethereum"]},
    {"q": "Где хранятся криптовалюты?", "a": "В блокчейне",
     "opts": ["На бирже", "В банке", "В блокчейне", "На сервере"]},
    {"q": "Какая крипта называется 'убийца Ethereum'?", "a": "Solana",
     "opts": ["Bitcoin", "Dogecoin", "Solana", "Litecoin"]},
    {"q": "Что такое токен?", "a": "Цифровой актив на блокчейне",
     "opts": ["Физическая монета", "Цифровой актив на блокчейне", "Пароль от кошелька", "Биржевой ордер"]},
    {"q": "Что означает аббревиатура BTC?", "a": "Bitcoin",
     "opts": ["BitCash", "Bitcoin", "BitToken", "BitChain"]},
    {"q": "Что означает аббревиатура ETH?", "a": "Ethereum",
     "opts": ["EtherToken", "Ethereum", "EtherHash", "EtherChain"]},
    {"q": "Можно ли отменить транзакцию в Bitcoin?", "a": "Нет, транзакции необратимы",
     "opts": ["Да, в течение часа", "Нет, транзакции необратимы", "Да, через поддержку", "Зависит от суммы"]},
    {"q": "Какая криптовалюта была первой?", "a": "Bitcoin",
     "opts": ["Ethereum", "Bitcoin", "Litecoin", "Dogecoin"]},
    {"q": "Что такое airdrop в крипте?", "a": "Бесплатная раздача токенов",
     "opts": ["Падение цены", "Бесплатная раздача токенов", "Тип майнинга", "Хакерская атака"]},
    {"q": "Что такое seed-фраза?", "a": "Набор слов для восстановления кошелька",
     "opts": ["Пароль от биржи", "Набор слов для восстановления кошелька", "Адрес кошелька", "Ключ API"]},
    {"q": "Какой символ у Ethereum?", "a": "Ромб / бриллиант",
     "opts": ["Буква B с полосками", "Ромб / бриллиант", "Собака", "Монета"]},
    {"q": "Сколько сатоши в 1 BTC?", "a": "100 000 000",
     "opts": ["1 000 000", "100 000 000", "10 000 000", "1 000 000 000"]},
    {"q": "Что такое стейблкоин?", "a": "Крипта, привязанная к фиату (доллар и т.д.)",
     "opts": ["Стабильная биржа", "Крипта, привязанная к фиату (доллар и т.д.)", "Бесплатный токен", "Особый NFT"]},
    {"q": "Какой стейблкоин самый популярный?", "a": "USDT (Tether)",
     "opts": ["USDC", "USDT (Tether)", "DAI", "BUSD"]},
    {"q": "Кто основал биржу Binance?", "a": "Чанпэн Чжао (CZ)",
     "opts": ["Виталик Бутерин", "Чанпэн Чжао (CZ)", "Сэм Бэнкман-Фрид", "Брайан Армстронг"]},
    {"q": "Что такое P2P в крипте?", "a": "Обмен между людьми напрямую",
     "opts": ["Тип блокчейна", "Обмен между людьми напрямую", "Протокол майнинга", "Криптобиржа"]},
    {"q": "Какой логотип у Litecoin?", "a": "Буква L на серебряном фоне",
     "opts": ["Буква B", "Буква L на серебряном фоне", "Собака", "Ромб"]},
]

QUIZ_MEDIUM = [
    # --- ОРИГИНАЛЬНЫЕ ---
    {"q": "Что такое DeFi?", "a": "Децентрализованные финансы",
     "opts": ["Цифровые деньги", "Децентрализованные финансы", "Дефицит токенов", "Де-фиатные валюты"]},
    {"q": "Что означает FUD?", "a": "Fear, Uncertainty, Doubt",
     "opts": ["Fast Universal Delivery", "Fear, Uncertainty, Doubt", "Full User Data", "Fund Under Development"]},
    {"q": "Что такое Gas в Ethereum?", "a": "Комиссия за транзакцию",
     "opts": ["Тип токена", "Комиссия за транзакцию", "Скорость блока", "Объём торгов"]},
    {"q": "Что такое халвинг BTC?", "a": "Уменьшение награды майнерам в 2 раза",
     "opts": ["Падение цены на 50%", "Уменьшение награды майнерам в 2 раза", "Раздвоение блокчейна", "Удвоение цены"]},
    {"q": "Что такое стейкинг?", "a": "Заработок за удержание крипты",
     "opts": ["Майнинг на видеокартах", "Заработок за удержание крипты", "Тип трейдинга", "Криптокредит"]},
    {"q": "Что такое смарт-контракт?", "a": "Программа на блокчейне",
     "opts": ["Договор между трейдерами", "Программа на блокчейне", "Тип криптокошелька", "Биржевой ордер"]},
    {"q": "Что такое whale (кит) в крипте?", "a": "Владелец большого количества крипты",
     "opts": ["Тип алгоритма", "Владелец большого количества крипты", "Торговый бот", "Биржевой маркетмейкер"]},
    {"q": "Что такое DAO?", "a": "Децентрализованная автономная организация",
     "opts": ["Тип криптовалюты", "Децентрализованная автономная организация", "Протокол торговли", "Вид майнинга"]},
    {"q": "Какой алгоритм консенсуса у BTC?", "a": "Proof of Work (PoW)",
     "opts": ["Proof of Stake", "Proof of Work (PoW)", "Delegated PoS", "Proof of Authority"]},
    {"q": "Что такое Layer 2?", "a": "Надстройка над основным блокчейном",
     "opts": ["Новый блокчейн", "Надстройка над основным блокчейном", "Тип кошелька", "Биржевой протокол"]},
    # --- НОВЫЕ СРЕДНИЕ ---
    {"q": "Что такое DEX?", "a": "Децентрализованная биржа",
     "opts": ["Цифровая экономика", "Децентрализованная биржа", "Тип токена", "Биржевой индекс"]},
    {"q": "Какой блокчейн создал TON?", "a": "Команда Telegram (братья Дуровы)",
     "opts": ["Google", "Команда Telegram (братья Дуровы)", "Meta", "Microsoft"]},
    {"q": "Что такое rug pull?", "a": "Мошенничество — создатели забирают деньги",
     "opts": ["Коррекция рынка", "Мошенничество — создатели забирают деньги", "Хакерская атака", "Технический сбой"]},
    {"q": "Что такое whitepaper?", "a": "Техническое описание проекта",
     "opts": ["Лицензия", "Техническое описание проекта", "Контракт на покупку", "Руководство пользователя"]},
    {"q": "Что означает DYOR?", "a": "Do Your Own Research",
     "opts": ["Do Your Online Registration", "Do Your Own Research", "Delete Your Old Records", "Don't Yield On Returns"]},
    {"q": "Что такое AMM?", "a": "Автоматический маркетмейкер",
     "opts": ["Альтернативный метод майнинга", "Автоматический маркетмейкер", "Анонимный мессенджер", "Арбитражная модель"]},
    {"q": "Что такое TVL в DeFi?", "a": "Total Value Locked — общий объём заблокированных средств",
     "opts": ["Скорость транзакций", "Total Value Locked — общий объём заблокированных средств", "Комиссия сети", "Тип ликвидности"]},
    {"q": "Что такое yield farming?", "a": "Заработок на предоставлении ликвидности",
     "opts": ["Майнинг на ферме", "Заработок на предоставлении ликвидности", "Покупка на минимуме", "Создание токенов"]},
    {"q": "Какая сеть у SHIB?", "a": "Ethereum (ERC-20)",
     "opts": ["Свой блокчейн", "Ethereum (ERC-20)", "Solana", "BNB Chain"]},
    {"q": "Что такое bridge (мост) в крипте?", "a": "Перевод токенов между разными блокчейнами",
     "opts": ["Соединение кошелька с биржей", "Перевод токенов между разными блокчейнами", "Тип смарт-контракта", "Протокол шифрования"]},
    {"q": "Что такое ICO?", "a": "Initial Coin Offering — первичное размещение",
     "opts": ["Международная криптоорганизация", "Initial Coin Offering — первичное размещение", "Тип кошелька", "Протокол безопасности"]},
    {"q": "Что такое market cap?", "a": "Рыночная капитализация (цена × количество)",
     "opts": ["Максимальная цена", "Рыночная капитализация (цена × количество)", "Комиссия биржи", "Объём торгов"]},
    {"q": "Что такое private key?", "a": "Секретный ключ для доступа к кошельку",
     "opts": ["Пароль от биржи", "Секретный ключ для доступа к кошельку", "Адрес кошелька", "Номер транзакции"]},
    {"q": "Что такое public key?", "a": "Открытый ключ / адрес для получения крипты",
     "opts": ["Секретный код", "Открытый ключ / адрес для получения крипты", "Пароль биржи", "Хеш транзакции"]},
    {"q": "Что такое fork блокчейна?", "a": "Разделение цепочки на две версии",
     "opts": ["Обновление кошелька", "Разделение цепочки на две версии", "Хакерская атака", "Слияние двух блокчейнов"]},
    {"q": "Что такое hard fork?", "a": "Несовместимое обновление протокола",
     "opts": ["Мягкое обновление", "Несовместимое обновление протокола", "Откат транзакций", "Закрытие блокчейна"]},
    {"q": "Какой тип консенсуса у Ethereum (после The Merge)?", "a": "Proof of Stake (PoS)",
     "opts": ["Proof of Work", "Proof of Stake (PoS)", "Delegated PoS", "Proof of History"]},
    {"q": "Что произошло при The Merge Ethereum?", "a": "Переход с PoW на PoS",
     "opts": ["Создание нового токена", "Переход с PoW на PoS", "Удвоение скорости", "Снижение комиссий в 100 раз"]},
    {"q": "Что такое meme-coin?", "a": "Крипта, созданная как шутка / по мему",
     "opts": ["Серьёзный проект", "Крипта, созданная как шутка / по мему", "Токен для NFT", "Стейблкоин"]},
    {"q": "Какой тип консенсуса у Solana?", "a": "Proof of History + Proof of Stake",
     "opts": ["Proof of Work", "Proof of History + Proof of Stake", "Delegated PoS", "Proof of Burn"]},
    {"q": "Что такое DApp?", "a": "Децентрализованное приложение",
     "opts": ["Цифровой кошелёк", "Децентрализованное приложение", "Торговый терминал", "Платёжная система"]},
    {"q": "Что такое liquidity pool?", "a": "Пул ликвидности для обмена на DEX",
     "opts": ["Тип облигации", "Пул ликвидности для обмена на DEX", "Майнинг-ферма", "Инвестиционный фонд"]},
    {"q": "Что такое cold wallet?", "a": "Кошелёк без подключения к интернету",
     "opts": ["Замороженный счёт", "Кошелёк без подключения к интернету", "Кошелёк в холодном помещении", "Неактивный аккаунт"]},
    {"q": "Что такое hot wallet?", "a": "Кошелёк с подключением к интернету",
     "opts": ["Популярный кошелёк", "Кошелёк с подключением к интернету", "Кошелёк с высокой комиссией", "Майнинг-кошелёк"]},
    {"q": "Что такое газовые войны (gas wars)?", "a": "Конкуренция за приоритет транзакций",
     "opts": ["Соревнование майнеров", "Конкуренция за приоритет транзакций", "Рост цены газа", "Тип DDoS-атаки"]},
]

QUIZ_HARD = [
    # --- ОРИГИНАЛЬНЫЕ ---
    {"q": "Какой тикер у Polygon?", "a": "MATIC",
     "opts": ["POLY", "MATIC", "PGN", "POL"]},
    {"q": "Что такое Merkle Tree?", "a": "Структура данных для верификации транзакций",
     "opts": ["Тип токена", "Структура данных для верификации транзакций", "Алгоритм шифрования", "Вид майнинга"]},
    {"q": "Максимальный размер блока BTC?", "a": "1 МБ (базовый)",
     "opts": ["512 КБ", "1 МБ (базовый)", "4 МБ", "10 МБ"]},
    {"q": "Когда произошёл первый халвинг BTC?", "a": "2012",
     "opts": ["2010", "2012", "2014", "2016"]},
    {"q": "Что такое Impermanent Loss?", "a": "Потери от предоставления ликвидности",
     "opts": ["Потери от хакерской атаки", "Потери от предоставления ликвидности", "Комиссия сети", "Ошибка в смарт-контракте"]},
    {"q": "Сколько транзакций в секунду у BTC?", "a": "~7 TPS",
     "opts": ["~7 TPS", "~50 TPS", "~100 TPS", "~1000 TPS"]},
    {"q": "Что такое EIP-1559?", "a": "Механизм сжигания части комиссий ETH",
     "opts": ["Обновление консенсуса", "Механизм сжигания части комиссий ETH", "Стандарт токенов", "Протокол мостов"]},
    {"q": "Какой блокчейн использует язык Move?", "a": "Aptos / Sui",
     "opts": ["Ethereum", "Aptos / Sui", "Solana", "Cardano"]},
    {"q": "Что такое Oracle в блокчейне?", "a": "Сервис, передающий внешние данные в блокчейн",
     "opts": ["Тип кошелька", "Сервис, передающий внешние данные в блокчейн", "Алгоритм шифрования", "Биржевой API"]},
    {"q": "Что такое Zero-Knowledge Proof?", "a": "Доказательство без раскрытия данных",
     "opts": ["Анонимная транзакция", "Доказательство без раскрытия данных", "Шифрование кошелька", "Тип консенсуса"]},
    # --- НОВЫЕ СЛОЖНЫЕ ---
    {"q": "Какой стандарт токенов на Ethereum?", "a": "ERC-20",
     "opts": ["BEP-20", "ERC-20", "SPL", "TRC-20"]},
    {"q": "Что такое nonce в блокчейне?", "a": "Число, используемое для майнинга блока",
     "opts": ["Объём комиссии", "Число, используемое для майнинга блока", "Номер транзакции", "Ключ шифрования"]},
    {"q": "Что такое BIP-39?", "a": "Стандарт мнемонических seed-фраз",
     "opts": ["Протокол биржи", "Стандарт мнемонических seed-фраз", "Тип смарт-контракта", "Обновление Bitcoin"]},
    {"q": "Что такое sharding?", "a": "Разделение блокчейна на параллельные цепочки",
     "opts": ["Шифрование данных", "Разделение блокчейна на параллельные цепочки", "Резервное копирование", "Оптимизация консенсуса"]},
    {"q": "Какой алгоритм хеширования у Bitcoin?", "a": "SHA-256",
     "opts": ["SHA-256", "Scrypt", "Ethash", "Blake2b"]},
    {"q": "Какой алгоритм хеширования у Litecoin?", "a": "Scrypt",
     "opts": ["SHA-256", "Scrypt", "Ethash", "X11"]},
    {"q": "Что такое MEV?", "a": "Maximal Extractable Value — прибыль от переупорядочивания транзакций",
     "opts": ["Минимальная комиссия", "Maximal Extractable Value — прибыль от переупорядочивания транзакций", "Максимальный объём", "Метрика эффективности"]},
    {"q": "Что такое flash loan?", "a": "Мгновенный кредит без залога в одной транзакции",
     "opts": ["Быстрый перевод", "Мгновенный кредит без залога в одной транзакции", "Вид стейкинга", "Тип ордера на бирже"]},
    {"q": "Что такое Wrapped Bitcoin (WBTC)?", "a": "Токен BTC на блокчейне Ethereum (ERC-20)",
     "opts": ["Зашифрованный BTC", "Токен BTC на блокчейне Ethereum (ERC-20)", "Улучшенный BTC", "BTC на Lightning Network"]},
    {"q": "Что такое ERC-721?", "a": "Стандарт невзаимозаменяемых токенов (NFT)",
     "opts": ["Стандарт обычных токенов", "Стандарт невзаимозаменяемых токенов (NFT)", "Протокол DeFi", "Стандарт мостов"]},
    {"q": "Что такое Rollup?", "a": "Технология масштабирования Layer 2",
     "opts": ["Тип консенсуса", "Технология масштабирования Layer 2", "Метод шифрования", "Формат блока"]},
    {"q": "Что такое Optimistic Rollup?", "a": "L2 с презумпцией валидности и периодом оспаривания",
     "opts": ["L2 с ZK-доказательствами", "L2 с презумпцией валидности и периодом оспаривания", "Тип майнинга", "Вид консенсуса"]},
    {"q": "Что такое ZK-Rollup?", "a": "L2 с использованием Zero-Knowledge Proofs",
     "opts": ["L2 с периодом оспаривания", "L2 с использованием Zero-Knowledge Proofs", "Метод стейкинга", "Шифрование данных"]},
    {"q": "Что произошло с биржей FTX в 2022?", "a": "Обанкротилась из-за мошенничества",
     "opts": ["Была куплена Binance", "Обанкротилась из-за мошенничества", "Стала крупнейшей", "Перешла на DeFi"]},
    {"q": "Что такое slippage?", "a": "Разница между ожидаемой и фактической ценой сделки",
     "opts": ["Комиссия биржи", "Разница между ожидаемой и фактической ценой сделки", "Скорость транзакции", "Тип ордера"]},
    {"q": "Что такое validator в PoS?", "a": "Узел, подтверждающий транзакции в обмен на награду",
     "opts": ["Тип кошелька", "Узел, подтверждающий транзакции в обмен на награду", "Аудитор кода", "Модератор сети"]},
    {"q": "Сколько валидаторов нужно запустить ноду Ethereum?", "a": "32 ETH минимум",
     "opts": ["1 ETH", "32 ETH минимум", "100 ETH", "16 ETH"]},
    {"q": "Что такое frontrunning?", "a": "Опережение чужой транзакции для извлечения прибыли",
     "opts": ["Быстрая торговля", "Опережение чужой транзакции для извлечения прибыли", "Первая покупка на ICO", "Лидерство на рынке"]},
    {"q": "Что такое ERC-1155?", "a": "Стандарт для мульти-токенов (fungible + NFT)",
     "opts": ["Стандарт для DeFi", "Стандарт для мульти-токенов (fungible + NFT)", "Стандарт стейблкоинов", "Протокол мостов"]},
    {"q": "Какой TPS у Solana (теоретический)?", "a": "~65 000 TPS",
     "opts": ["~1 000 TPS", "~65 000 TPS", "~10 000 TPS", "~100 000 TPS"]},
    {"q": "В каком году The Merge Ethereum произошёл?", "a": "2022",
     "opts": ["2020", "2021", "2022", "2023"]},
    {"q": "Что такое Chainlink (LINK)?", "a": "Децентрализованная сеть оракулов",
     "opts": ["Биржа", "Децентрализованная сеть оракулов", "Layer 2 решение", "Стейблкоин"]},
    {"q": "Что такое tokenomics?", "a": "Экономическая модель токена",
     "opts": ["Торговая стратегия", "Экономическая модель токена", "Тип смарт-контракта", "Вид биржи"]},
    {"q": "Что такое total supply?", "a": "Общее количество когда-либо созданных монет",
     "opts": ["Количество в обращении", "Общее количество когда-либо созданных монет", "Максимальное количество", "Количество на биржах"]},
    {"q": "Что такое circulating supply?", "a": "Количество монет в обращении",
     "opts": ["Максимальное количество", "Количество монет в обращении", "Общее количество", "Монеты на биржах"]},
    {"q": "Что такое reentrancy attack?", "a": "Атака повторного входа на смарт-контракт",
     "opts": ["DDoS-атака", "Атака повторного входа на смарт-контракт", "Атака 51%", "Фишинг"]},
    {"q": "Что такое атака 51%?", "a": "Контроль над большинством хешрейта сети",
     "opts": ["Продажа 51% монет", "Контроль над большинством хешрейта сети", "Взлом 51% кошельков", "Отмена 51% транзакций"]},
]

# Тренировка — все вопросы лёгкие, средний — средние, сложный — сложные
QUIZ_BY_DIFFICULTY = {
    'training': QUIZ_EASY,
    'medium': QUIZ_MEDIUM,
    'hard': QUIZ_HARD,
}

# Кол-во вопросов для зачёта
QUIZ_QUESTIONS_COUNT = {
    'training': 3,
    'medium': 5,
    'hard': 5,
}

# Минимум правильных для прохождения
QUIZ_PASS_COUNT = {
    'training': 2,
    'medium': 4,
    'hard': 4,
}


# --- Выбор типа викторины ---

async def quiz_type_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Викторина: выбор типа"""
    keyboard = [
        [KeyboardButton("📚 Вопросы о крипте")],
        [KeyboardButton("💰 Угадай цену")],
        [KeyboardButton("Отмена")]
    ]
    await update.message.reply_text(
        f"🧠 КРИПТО-ВИКТОРИНА\n"
        f"{'━' * 28}\n\n"
        f"Выберите тип викторины:\n\n"
        f"📚 Вопросы о крипте\n"
        f"   Проверь знания + получи подписку!\n\n"
        f"💰 Угадай цену\n"
        f"   Угадай текущую цену крипты\n"
        f"   из 4 вариантов!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return QUIZ_TYPE_STATE


async def quiz_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Викторина: обработать выбор типа"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_extra_keyboard())
        return -1

    if text == "📚 Вопросы о крипте":
        return await quiz_difficulty_menu(update, context)
    elif text == "💰 Угадай цену":
        return await quiz_price_difficulty_menu(update, context)
    else:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return QUIZ_TYPE_STATE


# --- Выбор сложности ---

async def quiz_difficulty_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор сложности для вопросов"""
    user_id = update.effective_user.id
    rewards = db.get_quiz_rewards(user_id)

    # Проверяем доступность наград
    can_medium = db.can_attempt_quiz_reward(user_id, 'medium')
    can_hard = db.can_attempt_quiz_reward(user_id, 'hard')
    got_medium = not db.can_get_quiz_reward(user_id, 'medium')
    got_hard = not db.can_get_quiz_reward(user_id, 'hard')

    medium_status = ""
    if got_medium:
        medium_status = " ✅ (награда получена)"
    elif not can_medium:
        medium_status = " ❌ (попытка использована)"

    hard_status = ""
    if got_hard:
        hard_status = " ✅ (награда получена)"
    elif not can_hard:
        hard_status = " ❌ (попытка использована)"

    context.user_data['quiz_mode'] = 'questions'

    keyboard = [
        [KeyboardButton("🟢 Тренировка")],
        [KeyboardButton("🟡 Средний")],
        [KeyboardButton("🔴 Сложный")],
        [KeyboardButton("Отмена")]
    ]
    await update.message.reply_text(
        f"📚 ВОПРОСЫ О КРИПТЕ\n"
        f"{'━' * 28}\n\n"
        f"Выберите сложность:\n\n"
        f"🟢 Тренировка (3 вопроса)\n"
        f"   Без наград, для практики\n\n"
        f"🟡 Средний (5 вопросов, нужно 4✅)\n"
        f"   🎁 +1 день Pro подписки{medium_status}\n"
        f"   ⚠️ 1 попытка в неделю!\n\n"
        f"🔴 Сложный (5 вопросов, нужно 4✅)\n"
        f"   🎁 +1 день Premium подписки{hard_status}\n"
        f"   ⚠️ 1 попытка в неделю!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return QUIZ_DIFFICULTY_STATE


async def quiz_price_difficulty_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать выбор сложности для угадай цену"""
    user_id = update.effective_user.id

    can_medium = db.can_attempt_quiz_reward(user_id, 'medium')
    can_hard = db.can_attempt_quiz_reward(user_id, 'hard')
    got_medium = not db.can_get_quiz_reward(user_id, 'medium')
    got_hard = not db.can_get_quiz_reward(user_id, 'hard')

    medium_status = ""
    if got_medium:
        medium_status = " ✅ (награда получена)"
    elif not can_medium:
        medium_status = " ❌ (попытка использована)"

    hard_status = ""
    if got_hard:
        hard_status = " ✅ (награда получена)"
    elif not can_hard:
        hard_status = " ❌ (попытка использована)"

    context.user_data['quiz_mode'] = 'price'

    keyboard = [
        [KeyboardButton("🟢 Тренировка")],
        [KeyboardButton("🟡 Средний")],
        [KeyboardButton("🔴 Сложный")],
        [KeyboardButton("Отмена")]
    ]
    await update.message.reply_text(
        f"💰 УГАДАЙ ЦЕНУ\n"
        f"{'━' * 28}\n\n"
        f"Выберите сложность:\n\n"
        f"🟢 Тренировка (3 раунда, разброс 50%+)\n"
        f"   Без наград, для практики\n\n"
        f"🟡 Средний (5 раундов, разброс ~30%)\n"
        f"   🎁 +1 день Pro подписки{medium_status}\n\n"
        f"🔴 Сложный (5 раундов, разброс ~15%)\n"
        f"   🎁 +1 день Premium подписки{hard_status}",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return QUIZ_DIFFICULTY_STATE


async def quiz_choose_difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать выбор сложности"""
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_extra_keyboard())
        return -1

    diff_map = {
        "🟢 Тренировка": 'training',
        "🟡 Средний": 'medium',
        "🔴 Сложный": 'hard',
    }

    difficulty = diff_map.get(text)
    if not difficulty:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return QUIZ_DIFFICULTY_STATE

    context.user_data['quiz_difficulty'] = difficulty
    context.user_data['quiz_score'] = 0
    context.user_data['quiz_current'] = 0
    context.user_data['quiz_total'] = QUIZ_QUESTIONS_COUNT[difficulty]

    # Проверка попытки для medium/hard
    if difficulty in ('medium', 'hard'):
        can_attempt = db.can_attempt_quiz_reward(user_id, difficulty)
        can_reward = db.can_get_quiz_reward(user_id, difficulty)
        if not can_attempt or not can_reward:
            reward_name = "Pro" if difficulty == 'medium' else "Premium"
            await update.message.reply_text(
                f"⏳ Попытка на награду {reward_name}\n"
                f"уже использована на этой неделе!\n\n"
                f"Вы можете играть в режиме 🟢 Тренировка\n"
                f"или подождать до следующей недели.",
                reply_markup=get_extra_keyboard()
            )
            return -1
        # Записать попытку
        db.set_quiz_attempt(user_id, difficulty)

    mode = context.user_data.get('quiz_mode', 'questions')

    if mode == 'questions':
        return await quiz_start_round(update, context)
    else:
        return await quiz_price_start_round(update, context)


# --- Тип 1: Вопросы о крипте (с раундами) ---

async def quiz_start_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать следующий вопрос"""
    difficulty = context.user_data.get('quiz_difficulty', 'training')
    current = context.user_data.get('quiz_current', 0)
    total = context.user_data.get('quiz_total', 3)
    score = context.user_data.get('quiz_score', 0)

    if current >= total:
        return await quiz_show_final_result(update, context)

    questions = QUIZ_BY_DIFFICULTY.get(difficulty, QUIZ_EASY)
    quiz = random.choice(questions)

    options = quiz['opts'].copy()
    random.shuffle(options)

    context.user_data['quiz_answer'] = quiz['a']
    context.user_data['quiz_question'] = quiz['q']
    context.user_data['quiz_options'] = options
    context.user_data['quiz_current'] = current + 1

    diff_label = {'training': '🟢 Тренировка', 'medium': '🟡 Средний', 'hard': '🔴 Сложный'}

    text = (
        f"📚 ВОПРОС {current + 1}/{total}\n"
        f"{'━' * 28}\n"
        f"{diff_label.get(difficulty, '')} | ✅ {score}/{current}\n\n"
        f"❓ {quiz['q']}\n\n"
    )

    buttons = []
    for i, opt in enumerate(options, 1):
        text += f"{i}. {opt}\n"
        buttons.append([KeyboardButton(f"📝 {i}")])

    buttons.append([KeyboardButton("Отмена")])

    text += f"\n{'━' * 28}\n"
    text += "Выберите номер ответа:"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return QUIZ_ANSWER_STATE


async def quiz_check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить ответ и продолжить раунд"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_extra_keyboard())
        return -1

    try:
        if text.startswith("📝"):
            num = int(text.replace("📝", "").strip())
        else:
            num = int(text)
    except ValueError:
        await update.message.reply_text("❌ Нажмите кнопку с номером ответа!")
        return QUIZ_ANSWER_STATE

    options = context.user_data.get('quiz_options', [])
    correct_answer = context.user_data.get('quiz_answer', '')

    if num < 1 or num > len(options):
        await update.message.reply_text("❌ Выберите от 1 до 4!")
        return QUIZ_ANSWER_STATE

    user_answer = options[num - 1]
    correct_idx = options.index(correct_answer) + 1
    is_correct = (user_answer == correct_answer)

    if is_correct:
        context.user_data['quiz_score'] = context.user_data.get('quiz_score', 0) + 1
        await update.message.reply_text(f"✅ Правильно! ({correct_answer})")
    else:
        await update.message.reply_text(f"❌ Неверно! Правильный: {correct_idx}. {correct_answer}")

    # Следующий вопрос или финал
    return await quiz_start_round(update, context)


async def quiz_show_final_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать финальный результат викторины"""
    user_id = update.effective_user.id
    difficulty = context.user_data.get('quiz_difficulty', 'training')
    total = context.user_data.get('quiz_total', 3)
    score = context.user_data.get('quiz_score', 0)
    mode = context.user_data.get('quiz_mode', 'questions')
    pass_count = QUIZ_PASS_COUNT.get(difficulty, 2)

    passed = score >= pass_count
    diff_label = {'training': '🟢 Тренировка', 'medium': '🟡 Средний', 'hard': '🔴 Сложный'}
    mode_label = "📚 Вопросы" if mode == 'questions' else "💰 Угадай цену"

    reward_text = ""

    if difficulty == 'training':
        reward_text = "\n💡 В тренировке наград нет.\nПопробуй 🟡 Средний или 🔴 Сложный!"
    elif passed:
        if difficulty == 'medium':
            db.add_subscription_days(user_id, 'pro', 1)
            db.set_quiz_reward(user_id, 'medium')
            reward_text = "\n🎁 НАГРАДА: +1 день ⭐ Pro подписки!"
        elif difficulty == 'hard':
            db.add_subscription_days(user_id, 'premium', 1)
            db.set_quiz_reward(user_id, 'hard')
            reward_text = "\n🎁 НАГРАДА: +1 день 👑 Premium подписки!"
    else:
        if difficulty == 'medium':
            reward_text = "\n😔 Не прошёл! Попытка использована.\nСледующая попытка — через неделю."
        elif difficulty == 'hard':
            reward_text = "\n😔 Не прошёл! Попытка использована.\nСледующая попытка — через неделю."

    if passed:
        verdict = f"🏆 ПРОЙДЕНО! ({score}/{total})"
    else:
        verdict = f"❌ НЕ ПРОЙДЕНО ({score}/{total}, нужно {pass_count})"

    result = (
        f"🧠 РЕЗУЛЬТАТ ВИКТОРИНЫ\n"
        f"{'━' * 28}\n\n"
        f"{mode_label} | {diff_label.get(difficulty, '')}\n\n"
        f"{verdict}\n"
        f"{reward_text}\n\n"
        f"{'━' * 28}\n"
        f"🔄 Нажми 🧠 Крипто-викторина\n"
        f"для нового раунда!"
    )

    await update.message.reply_text(result, reply_markup=get_extra_keyboard())
    return -1


# --- Тип 2: Угадай цену (с раундами и сложностью) ---

def _generate_fake_prices(real_price, difficulty='training'):
    """Генерация 3 фейковых цен — чем сложнее, тем ближе к реальной"""
    fakes = set()

    if difficulty == 'hard':
        # Очень близкие — 5-20% разница
        multipliers = [0.85, 0.88, 0.92, 0.95, 1.05, 1.08, 1.12, 1.15, 1.18, 1.22]
        min_diff = 0.05
    elif difficulty == 'medium':
        # Средние — 15-40%
        multipliers = [0.6, 0.7, 0.75, 0.82, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8]
        min_diff = 0.10
    else:
        # Лёгкие — 30-80%
        multipliers = [0.2, 0.35, 0.5, 0.65, 0.8, 1.2, 1.35, 1.5, 1.65, 1.8, 2.0, 2.5, 3.0]
        min_diff = 0.15

    random.shuffle(multipliers)

    for m in multipliers:
        fake = real_price * m
        if real_price >= 1000:
            fake = round(fake, 2)
        elif real_price >= 1:
            fake = round(fake, 2)
        elif real_price >= 0.01:
            fake = round(fake, 4)
        else:
            fake = round(fake, 8)

        if abs(fake - real_price) / real_price > min_diff:
            fakes.add(fake)
        if len(fakes) >= 3:
            break

    while len(fakes) < 3:
        if difficulty == 'hard':
            m = random.uniform(0.8, 1.25)
        elif difficulty == 'medium':
            m = random.uniform(0.6, 1.6)
        else:
            m = random.uniform(0.3, 3.0)
        fake = real_price * m
        if real_price >= 1:
            fake = round(fake, 2)
        else:
            fake = round(fake, 6)
        if abs(fake - real_price) / real_price > min_diff:
            fakes.add(fake)

    return list(fakes)


async def quiz_price_start_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Угадай цену: следующий раунд"""
    difficulty = context.user_data.get('quiz_difficulty', 'training')
    current = context.user_data.get('quiz_current', 0)
    total = context.user_data.get('quiz_total', 3)
    score = context.user_data.get('quiz_score', 0)

    if current >= total:
        return await quiz_show_final_result(update, context)

    context.user_data['quiz_current'] = current + 1

    msg = await update.message.reply_text("⏳ Загружаю данные...")

    ticker = random.choice(list(CRYPTO_LIST.keys()))
    info = CRYPTO_LIST[ticker]

    data = await get_asset_price(ticker, 'crypto', 'usd')
    if not data or not data.get('price'):
        try:
            await msg.edit_text("❌ Не удалось загрузить цену. Попробуйте ещё раз.")
        except Exception:
            pass
        await update.message.reply_text("🧠 Попробуйте снова:", reply_markup=get_extra_keyboard())
        return -1

    real_price = data['price']
    fakes = _generate_fake_prices(real_price, difficulty)

    all_prices = fakes + [real_price]
    random.shuffle(all_prices)

    def fmt(p):
        if p >= 1000:
            return f"${p:,.2f}"
        elif p >= 1:
            return f"${p:.2f}"
        elif p >= 0.01:
            return f"${p:.4f}"
        else:
            return f"${p:.8f}"

    correct_idx = all_prices.index(real_price) + 1

    context.user_data['quiz_price_correct'] = correct_idx
    context.user_data['quiz_price_real'] = real_price
    context.user_data['quiz_price_ticker'] = ticker
    context.user_data['quiz_price_options'] = all_prices

    diff_label = {'training': '🟢', 'medium': '🟡', 'hard': '🔴'}

    text = (
        f"💰 РАУНД {current + 1}/{total}\n"
        f"{'━' * 28}\n"
        f"{diff_label.get(difficulty, '')} | ✅ {score}/{current}\n\n"
        f"{info['emoji']} {info['name']} ({ticker})\n\n"
        f"❓ Какая сейчас цена {ticker}?\n\n"
    )

    buttons = []
    for i, p in enumerate(all_prices, 1):
        text += f"{i}. {fmt(p)}\n"
        buttons.append([KeyboardButton(f"💲 {i}")])

    buttons.append([KeyboardButton("Отмена")])

    text += f"\n{'━' * 28}\n"
    text += "Выберите номер ответа:"

    try:
        await msg.edit_text(text)
    except Exception:
        pass

    await update.message.reply_text(
        "👇 Выберите ответ:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return QUIZ_PRICE_ANSWER_STATE


async def quiz_price_check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Угадай цену: проверить ответ и продолжить"""
    text = update.message.text.strip()

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_extra_keyboard())
        return -1

    try:
        if text.startswith("💲"):
            num = int(text.replace("💲", "").strip())
        else:
            num = int(text)
    except ValueError:
        await update.message.reply_text("❌ Нажмите кнопку с номером!")
        return QUIZ_PRICE_ANSWER_STATE

    correct_idx = context.user_data.get('quiz_price_correct', 0)
    real_price = context.user_data.get('quiz_price_real', 0)
    ticker = context.user_data.get('quiz_price_ticker', '???')
    all_prices = context.user_data.get('quiz_price_options', [])

    if num < 1 or num > 4:
        await update.message.reply_text("❌ Выберите от 1 до 4!")
        return QUIZ_PRICE_ANSWER_STATE

    def fmt(p):
        if p >= 1000:
            return f"${p:,.2f}"
        elif p >= 1:
            return f"${p:.2f}"
        elif p >= 0.01:
            return f"${p:.4f}"
        else:
            return f"${p:.8f}"

    is_correct = (num == correct_idx)

    if is_correct:
        context.user_data['quiz_score'] = context.user_data.get('quiz_score', 0) + 1
        await update.message.reply_text(f"✅ Правильно! {ticker} = {fmt(real_price)}")
    else:
        await update.message.reply_text(f"❌ Неверно! {ticker} = {fmt(real_price)}")

    return await quiz_price_start_round(update, context)


# Обёртка для handle_message
async def show_crypto_quiz(update, context):
    """Перенаправление на quiz_type_start"""
    return await quiz_type_start(update, context)


# ==================== 🎟 ПРОМОКОДЫ ====================

async def promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ввода промокода"""
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🎟 ПРОМОКОД\n"
        f"{'━' * 28}\n\n"
        f"Введите ваш промокод:\n\n"
        f"⚠️ Каждый промокод можно\n"
        f"использовать только 1 раз!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return PROMO_CODE_STATE


async def promo_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активация промокода"""
    text = update.message.text.strip().upper()
    user_id = update.effective_user.id

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_extra_keyboard())
        return -1

    if text not in PROMO_CODES:
        await update.message.reply_text(
            "❌ Промокод не найден!\n\nПопробуйте ещё раз или нажмите Отмена.",
        )
        return PROMO_CODE_STATE

    if db.is_promo_used(user_id, text):
        await update.message.reply_text(
            "⚠️ Вы уже использовали этот промокод!",
            reply_markup=get_extra_keyboard()
        )
        return -1

    promo = PROMO_CODES[text]
    tier = promo['tier']
    days = promo['days']
    desc = promo['desc']

    # Применить
    if days is None:
        # Навсегда
        db.set_subscription(user_id, tier, None)
    else:
        db.add_subscription_days(user_id, tier, days)

    db.use_promo(user_id, text)

    await update.message.reply_text(
        f"🎉 ПРОМОКОД АКТИВИРОВАН!\n"
        f"{'━' * 28}\n\n"
        f"🎟 Код: {text}\n"
        f"📦 Награда: {desc}\n"
        f"👤 Статус: {tier_label(tier)}\n\n"
        f"Приятного использования! 🚀",
        reply_markup=get_main_keyboard()
    )
    return -1


# ==================== 👤 ПОДПИСКА: ИНФОРМАЦИЯ ====================

async def show_subscription_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о подписке"""
    user_id = update.effective_user.id
    tier, expires_at = db.get_subscription(user_id)

    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            exp_str = exp.strftime("%d.%m.%Y %H:%M")
            days_left = (exp - datetime.now()).days
            exp_info = f"📅 До: {exp_str} ({days_left} дн.)"
        except Exception:
            exp_info = "📅 Навсегда"
    else:
        if tier == 'free':
            exp_info = "📅 —"
        else:
            exp_info = "📅 Навсегда ♾️"

    # Описание тира
    if tier == 'free':
        features = (
            f"📊 Курсы: {len(FREE_CRYPTOS)} крипт "
            f"({', '.join(FREE_CRYPTOS)})\n"
            f"🔄 Конвертер: ✅\n"
            f"⚖️ Сравнение: ✅\n"
            f"⭐ Избранное: ✅\n"
            f"📰 Дайджест: ✅\n"
            f"🎰 Рулетка: ✅\n"
            f"🧠 Викторина: ✅\n"
            f"🏅 Топ-3 дня: ✅\n"
            f"📰 Новости рынка: ✅\n"
            f"🔔 Алерты: ❌\n"
            f"📡 Трекер: ❌\n"
            f"🧮 Калькулятор: ❌\n"
            f"🏆 Рейтинг: ❌\n"
            f"📉 Волатильность: ❌\n"
            f"📊 Объём Профиль: ❌\n"
            f"🤖 Сигналы: ❌\n"
            f"😱 Индекс Страха: ❌\n"
            f"🐋 Кит-Детектор: ❌\n"
            f"🔬 Тех. Анализ: ❌\n"
            f"📊 Корреляция: ❌\n"
            f"🏦 Скринер: ❌\n"
            f"🧠 AI Советник: ❌\n"
            f"🔎 Анализ актива: ❌\n"
            f"🎯 Снайпер входа: ❌\n"
            f"🗺 Хитмап рынка: ❌\n"
            f"⏳ Машина времени: ❌\n"
            f"📡 Радар аномалий: ❌\n"
            f"💎 DCA Калькулятор: ❌\n"
            f"🧬 Индекс Доминации: ❌"
        )
    elif tier == 'pro':
        features = (
            f"📊 Курсы: {len(PRO_CRYPTOS)} крипт\n"
            f"🔄 Конвертер: ✅\n"
            f"⚖️ Сравнение: ✅\n"
            f"⭐ Избранное: ✅\n"
            f"📰 Дайджест: ✅\n"
            f"🎰 Рулетка: ✅\n"
            f"🧠 Викторина: ✅\n"
            f"🏅 Топ-3 дня: ✅\n"
            f"📰 Новости рынка: ✅\n"
            f"🔔 Алерты: ✅\n"
            f"📡 Трекер: ✅\n"
            f"🧮 Калькулятор: ✅\n"
            f"🏆 Рейтинг: ✅\n"
            f"📉 Волатильность: ✅\n"
            f"📊 Объём Профиль: ✅\n"
            f"🤖 Сигналы: ❌\n"
            f"😱 Индекс Страха: ❌\n"
            f"🐋 Кит-Детектор: ❌\n"
            f"🔬 Тех. Анализ: ❌\n"
            f"📊 Корреляция: ❌\n"
            f"🏦 Скринер: ❌\n"
            f"🧠 AI Советник: ❌\n"
            f"🔎 Анализ актива: ❌\n"
            f"🎯 Снайпер входа: ❌\n"
            f"🗺 Хитмап рынка: ❌\n"
            f"⏳ Машина времени: ❌\n"
            f"📡 Радар аномалий: ❌\n"
            f"💎 DCA Калькулятор: ❌\n"
            f"🧬 Индекс Доминации: ❌"
        )
    else:  # premium
        features = (
            f"📊 Курсы: все {len(CRYPTO_LIST)} крипт + {len(STOCKS_LIST)} акций\n"
            f"🔄 Конвертер: ✅\n"
            f"⚖️ Сравнение: ✅\n"
            f"⭐ Избранное: ✅\n"
            f"📰 Дайджест: ✅\n"
            f"🎰 Рулетка: ✅\n"
            f"🧠 Викторина: ✅\n"
            f"🏅 Топ-3 дня: ✅\n"
            f"📰 Новости рынка: ✅\n"
            f"🔔 Алерты: ✅\n"
            f"📡 Трекер: ✅\n"
            f"🧮 Калькулятор: ✅\n"
            f"🏆 Рейтинг: ✅\n"
            f"📉 Волатильность: ✅\n"
            f"📊 Объём Профиль: ✅\n"
            f"🤖 Сигналы: ✅\n"
            f"😱 Индекс Страха: ✅\n"
            f"🐋 Кит-Детектор: ✅\n"
            f"🔬 Тех. Анализ: ✅\n"
            f"📊 Корреляция: ✅\n"
            f"🏦 Скринер: ✅\n"
            f"🧠 AI Советник: ✅\n"
            f"🔎 Анализ актива: ✅\n"
            f"🎯 Снайпер входа: ✅\n"
            f"🗺 Хитмап рынка: ✅\n"
            f"⏳ Машина времени: ✅\n"
            f"📡 Радар аномалий: ✅\n"
            f"💎 DCA Калькулятор: ✅\n"
            f"🧬 Индекс Доминации: ✅"
        )

    text = (
        f"👤 МОЯ ПОДПИСКА\n"
        f"{'━' * 28}\n\n"
        f"Статус: {tier_label(tier)}\n"
        f"{exp_info}\n\n"
        f"{'━' * 28}\n"
        f"📋 Доступные функции:\n\n"
        f"{features}\n\n"
        f"{'━' * 28}\n"
        f"🧠 Побеждай в викторинах!\n"
        f"🟡 Средний → +1 день Pro\n"
        f"🔴 Сложный → +1 день Premium\n"
        f"🎟 Или активируй промокод"
    )

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


# ==================== 🔐 РЕЖИМ АВТОРА ====================

AUTHOR_PASSWORD = "5678901234"


def get_author_keyboard():
    """Клавиатура панели автора"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Статистика бота"), KeyboardButton("👥 Все пользователи")],
        [KeyboardButton("🎁 Выдать Premium"), KeyboardButton("📢 Рассылка")],
        [KeyboardButton("🗄 База данных"), KeyboardButton("🔄 Сброс подписок")],
        [KeyboardButton("↩️ Выйти из панели")]
    ], resize_keyboard=True)


async def author_login_start(update, context):
    """Начало входа в режим автора — запрос пароля"""
    user_id = update.effective_user.id

    # Если автор уже зарегистрирован — проверяем, этот ли пользователь
    existing_author = db.get_author()
    if existing_author is not None and existing_author != user_id:
        await update.message.reply_text(
            "🚫 Доступ запрещён.\n"
            "Режим автора уже закреплён за другим пользователем.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    # Если это уже автор — пускаем без пароля
    if db.is_author(user_id):
        await update.message.reply_text(
            f"🔐 ПАНЕЛЬ АВТОРА\n"
            f"{'━' * 28}\n\n"
            f"👋 С возвращением, автор!\n"
            f"ID: {user_id}\n\n"
            f"Выбери действие:",
            reply_markup=get_author_keyboard()
        )
        context.user_data['in_author_mode'] = True
        return ConversationHandler.END

    # Новый вход — запрашиваем пароль
    await update.message.reply_text(
        f"🔐 ВХОД В РЕЖИМ АВТОРА\n"
        f"{'━' * 28}\n\n"
        f"Введи пароль для доступа:",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("↩️ Отмена")]
        ], resize_keyboard=True)
    )
    return AUTHOR_PASSWORD_STATE


async def author_check_password(update, context):
    """Проверка пароля автора"""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    if text == "↩️ Отмена":
        await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    # Проверяем, не занят ли уже автор другим
    existing_author = db.get_author()
    if existing_author is not None and existing_author != user_id:
        await update.message.reply_text(
            "🚫 Доступ запрещён.\n"
            "Режим автора уже закреплён.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    if text != AUTHOR_PASSWORD:
        await update.message.reply_text(
            "❌ Неверный пароль!\n\n"
            "Попробуй ещё раз или нажми ↩️ Отмена:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("↩️ Отмена")]
            ], resize_keyboard=True)
        )
        return AUTHOR_PASSWORD_STATE

    # Пароль верный — записываем автора навсегда
    saved = db.set_author(user_id, username)
    if saved:
        status_msg = "✅ Ты зарегистрирован как АВТОР бота!\nТеперь никто другой не получит доступ."
    else:
        status_msg = "✅ Доступ подтверждён."

    context.user_data['in_author_mode'] = True

    await update.message.reply_text(
        f"🔐 ПАНЕЛЬ АВТОРА\n"
        f"{'━' * 28}\n\n"
        f"{status_msg}\n\n"
        f"👤 ID: {user_id}\n"
        f"📛 Username: @{username}\n\n"
        f"{'━' * 28}\n"
        f"Доступные функции:\n\n"
        f"📊 Статистика бота — общая инфо\n"
        f"👥 Все пользователи — список юзеров\n"
        f"🎁 Выдать Premium — дать подписку\n"
        f"📢 Рассылка — сообщение всем\n"
        f"🗄 База данных — размер и таблицы\n"
        f"🔄 Сброс подписок — обнулить все\n\n"
        f"Выбери действие:",
        reply_markup=get_author_keyboard()
    )
    return ConversationHandler.END


async def author_show_stats(update, context):
    """Статистика бота — для автора"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    conn = db.connect()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE tier = 'pro' AND (expires_at IS NULL OR expires_at > datetime('now'))")
    pro_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE tier = 'premium' AND (expires_at IS NULL OR expires_at > datetime('now'))")
    premium_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM alerts WHERE active = 1')
    active_alerts = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM tracked_cryptos WHERE active = 1')
    active_trackers = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM predictions WHERE resolved = 0')
    active_predictions = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM portfolio')
    portfolio_items = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM used_promos')
    used_promos = cursor.fetchone()[0]

    conn.close()

    free_count = total_users - pro_count - premium_count

    await update.message.reply_text(
        f"📊 СТАТИСТИКА БОТА\n"
        f"{'━' * 28}\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"   🆓 Free: {free_count}\n"
        f"   ⭐ Pro: {pro_count}\n"
        f"   👑 Premium: {premium_count}\n\n"
        f"{'━' * 28}\n"
        f"📋 Активные данные:\n\n"
        f"   🔔 Алертов: {active_alerts}\n"
        f"   📡 Трекеров: {active_trackers}\n"
        f"   🎯 Предсказаний: {active_predictions}\n"
        f"   💼 Портфель (записей): {portfolio_items}\n"
        f"   🎟 Промокодов использовано: {used_promos}\n\n"
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        reply_markup=get_author_keyboard()
    )


async def author_show_users(update, context):
    """Список всех пользователей — для автора"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, created_at FROM users ORDER BY created_at DESC LIMIT 30')
    users = cursor.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("👥 Пользователей пока нет.", reply_markup=get_author_keyboard())
        return

    text = f"👥 ПОЛЬЗОВАТЕЛИ (последние 30)\n{'━' * 28}\n\n"
    for i, (uid, uname, created) in enumerate(users, 1):
        tier = get_user_tier(uid)
        tier_icon = {'free': '🆓', 'pro': '⭐', 'premium': '👑'}.get(tier, '🆓')
        text += f"{i}. {tier_icon} {uname or '???'} (ID: {uid})\n"
        if created:
            text += f"   📅 {created[:10]}\n"

    await update.message.reply_text(text, reply_markup=get_author_keyboard())


async def author_grant_premium_start(update, context):
    """Выдать Premium — запрос ID пользователя"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    context.user_data['author_action'] = 'grant_premium'
    await update.message.reply_text(
        f"🎁 ВЫДАТЬ PREMIUM\n"
        f"{'━' * 28}\n\n"
        f"Введи ID пользователя\n"
        f"(число, например: 123456789)\n\n"
        f"Или введи 'all' чтобы дать\n"
        f"Premium ВСЕМ пользователям:",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("↩️ Выйти из панели")]
        ], resize_keyboard=True)
    )


async def author_broadcast_start(update, context):
    """Рассылка — запрос текста"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    context.user_data['author_action'] = 'broadcast'
    await update.message.reply_text(
        f"📢 РАССЫЛКА\n"
        f"{'━' * 28}\n\n"
        f"Напиши текст сообщения,\n"
        f"которое будет отправлено\n"
        f"ВСЕМ пользователям бота:",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("↩️ Выйти из панели")]
        ], resize_keyboard=True)
    )


async def author_show_db_info(update, context):
    """Информация о базе данных"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    import os
    db_path = db.db_path
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    info = f"🗄 БАЗА ДАННЫХ\n{'━' * 28}\n\n"
    info += f"📁 Файл: {db_path}\n"
    info += f"💾 Размер: {db_size / 1024:.1f} KB\n\n"
    info += f"📋 Таблицы ({len(tables)}):\n"

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        info += f"   • {table}: {count} записей\n"

    conn.close()

    await update.message.reply_text(info, reply_markup=get_author_keyboard())


async def author_reset_subs(update, context):
    """Сброс всех подписок"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🔄 СБРОС ПОДПИСОК\n"
        f"{'━' * 28}\n\n"
        f"✅ Удалено подписок: {deleted}\n"
        f"Все пользователи теперь Free.",
        reply_markup=get_author_keyboard()
    )


async def author_handle_input(update, context):
    """Обработка ввода автора (grant premium / broadcast)"""
    user_id = update.effective_user.id
    if not db.is_author(user_id):
        return

    text = update.message.text.strip()
    action = context.user_data.get('author_action')

    if action == 'grant_premium':
        context.user_data.pop('author_action', None)

        if text.lower() == 'all':
            # Дать Premium всем
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            all_users = [row[0] for row in cursor.fetchall()]
            conn.close()

            count = 0
            for uid in all_users:
                db.add_subscription_days(uid, 'premium', 365)
                count += 1

            await update.message.reply_text(
                f"🎁 Premium выдан ВСЕМ!\n"
                f"✅ {count} пользователей получили Premium на 365 дней.",
                reply_markup=get_author_keyboard()
            )
        else:
            try:
                target_id = int(text)
            except ValueError:
                await update.message.reply_text(
                    "❌ Введи числовой ID или 'all'.",
                    reply_markup=get_author_keyboard()
                )
                return

            user = db.get_user(target_id)
            if not user:
                await update.message.reply_text(
                    f"❌ Пользователь с ID {target_id} не найден.",
                    reply_markup=get_author_keyboard()
                )
                return

            db.add_subscription_days(target_id, 'premium', 365)
            await update.message.reply_text(
                f"🎁 Premium выдан!\n"
                f"✅ Пользователь {target_id} получил Premium на 365 дней.",
                reply_markup=get_author_keyboard()
            )

    elif action == 'broadcast':
        context.user_data.pop('author_action', None)

        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        all_users = [row[0] for row in cursor.fetchall()]
        conn.close()

        sent = 0
        failed = 0
        for uid in all_users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 ОБЪЯВЛЕНИЕ ОТ АВТОРА\n{'━' * 28}\n\n{text}"
                )
                sent += 1
            except Exception:
                failed += 1

        await update.message.reply_text(
            f"📢 РАССЫЛКА ЗАВЕРШЕНА\n"
            f"{'━' * 28}\n\n"
            f"✅ Доставлено: {sent}\n"
            f"❌ Ошибок: {failed}",
            reply_markup=get_author_keyboard()
        )

    else:
        await update.message.reply_text(
            "👇 Выбери действие:",
            reply_markup=get_author_keyboard()
        )
