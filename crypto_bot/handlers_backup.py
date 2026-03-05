"""
Обработчики команд и сообщений крипто-бота
"""

import random
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from config import (
    CRYPTO_LIST,
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
    THRESHOLD_OPTIONS, TRACKER_COOLDOWN,
    FREE_CRYPTOS, PRO_CRYPTOS, PROMO_CODES
)
from database import Database
from crypto_api import (
    get_crypto_price, get_all_prices, fetch_prices,
    format_price, format_change, format_volume
)

db = Database()


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
    """Главное меню"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Курсы"), KeyboardButton("🔔 Алерты")],
        [KeyboardButton("📡 Трекер"), KeyboardButton("🤖 Сигналы")],
        [KeyboardButton("🔄 Конвертер"), KeyboardButton("⚖️ Сравнение")],
        [KeyboardButton("🧮 Калькулятор"), KeyboardButton("🏆 Рейтинг")],
        [KeyboardButton("⭐ Избранное"), KeyboardButton("🔧 Ещё")],
        [KeyboardButton("👤 Подписка")]
    ], resize_keyboard=True)


def get_currency_keyboard():
    """Выбор валюты (USD / RUB)"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💵 Доллар (USDT)"), KeyboardButton("₽ Рубль (RUB)")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_crypto_keyboard(allowed_tickers=None):
    """Список криптовалют кнопками (3 в ряд), фильтр по подписке"""
    tickers = allowed_tickers if allowed_tickers else list(CRYPTO_LIST.keys())
    buttons = []
    row = []
    for ticker in tickers:
        if ticker not in CRYPTO_LIST:
            continue
        emoji = CRYPTO_LIST[ticker]['emoji']
        row.append(KeyboardButton(f"{emoji} {ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("↩️ Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_crypto_keyboard_plain():
    """Список криптовалют без эмодзи (для алертов)"""
    tickers = list(CRYPTO_LIST.keys())
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

    await update.message.reply_text(
        f"📈 КРИПТО-БОТ\n"
        f"{'═' * 28}\n\n"
        f"👋 Привет, {user.first_name}!\n"
        f"Статус: {tier_label(tier)}\n\n"
        f"📊 Курсы — цены в $ и ₽\n"
        f"🔔 Алерты — уведомления по цене\n"
        f"📡 Трекер — резкие движения\n"
        f"🤖 Сигналы — покупать / продавать\n"
        f"🔄 Конвертер — перевод между крипто\n"
        f"⚖️ Сравнение — сравнить 2 монеты\n"
        f"🧮 Калькулятор — прибыль / убыток\n"
        f"🏆 Рейтинг — топы по капитализации\n"
        f"⭐ Избранное — быстрый доступ\n"
        f"🔧 Ещё — дайджест, рулетка и др.\n"
        f"👤 Подписка — статус и промокоды\n\n"
        f"🧠 Побеждай в викторинах для\n"
        f"бесплатной Pro/Premium подписки!\n\n"
        f"Выбери раздел:",
        reply_markup=get_main_keyboard()
    )
    return -1


# ==================== КУРСЫ ====================

async def show_rates_menu(update, context):
    """Показать выбор валюты"""
    await update.message.reply_text(
        "📊 КУРСЫ КРИПТОВАЛЮТ\n"
        f"{'═' * 28}\n\n"
        "Выберите валюту отображения:\n\n"
        "💵 Доллар (USDT) — цены в $\n"
        "₽ Рубль (RUB) — цены в ₽",
        reply_markup=get_currency_keyboard()
    )


async def show_crypto_list(update, context, currency):
    """Показать список криптовалют после выбора валюты"""
    context.user_data['rate_currency'] = currency
    curr_label = "💵 USD" if currency == 'usd' else "₽ RUB"
    user_id = update.effective_user.id
    allowed = get_allowed_cryptos(user_id)
    tier = get_user_tier(user_id)

    lock_info = ""
    if tier == 'free':
        lock_info = f"\n🔒 Доступно {len(allowed)} из {len(CRYPTO_LIST)} крипт (Free)\n"
    elif tier == 'pro':
        lock_info = f"\n🔓 Доступно {len(allowed)} из {len(CRYPTO_LIST)} крипт (Pro)\n"

    await update.message.reply_text(
        f"📊 КУРСЫ В {curr_label}\n"
        f"{'═' * 28}\n{lock_info}\n"
        f"Нажмите на криптовалюту\n"
        f"чтобы увидеть текущий курс:",
        reply_markup=get_crypto_keyboard(allowed)
    )


async def show_crypto_price(update, context, ticker):
    """Получить и показать цену конкретной крипты"""
    # Проверка доступа по подписке
    user_id = update.effective_user.id
    allowed = get_allowed_cryptos(user_id)
    if ticker not in allowed:
        await update.message.reply_text(
            f"🔒 {ticker} недоступен на вашем тарифе!\n\n"
            f"Доступно: {', '.join(allowed)}\n\n"
            f"Улучшите подписку для доступа ко всем монетам.",
            reply_markup=get_main_keyboard()
        )
        return

    currency = context.user_data.get('rate_currency', 'usd')

    msg = await update.message.reply_text(f"⏳ Загрузка {ticker}...")

    data = await get_crypto_price(ticker, currency)

    if not data or data.get('price') is None:
        try:
            await msg.edit_text(
                f"❌ Не удалось получить цену {ticker}\n\n"
                f"Монета может быть недоступна на CoinGecko\n"
                f"или возникла ошибка сети. Попробуйте позже."
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
            f"🕐 Данные CoinGecko"
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
    count = db.count_user_active_alerts(user_id)

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
    alerts = db.get_user_alerts(user_id)

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
        emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')

        price_str = format_price(target, currency)

        text += f"#{alert_id} {emoji} {ticker} — {dir_emoji} {dir_word} {price_str}\n"

    text += f"\n🔔 Алерты проверяются каждую минуту"

    await update.message.reply_text(text, reply_markup=get_alerts_keyboard())


async def delete_all_alerts(update, context):
    """Удалить все активные алерты"""
    user_id = update.effective_user.id
    count = db.delete_all_user_alerts(user_id)

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
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if "USD" in text:
        context.user_data['alert_currency'] = 'usd'
    elif "RUB" in text:
        context.user_data['alert_currency'] = 'rub'
    else:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return ALERT_CURRENCY_STATE

    currency = context.user_data['alert_currency']
    label = "💵 USD" if currency == 'usd' else "₽ RUB"

    await update.message.reply_text(
        f"🔔 Алерт в {label}\n\n"
        f"Шаг 2/4: Выберите криптовалюту:",
        reply_markup=get_crypto_keyboard_plain()
    )
    return ALERT_CRYPTO_STATE


async def alert_choose_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Шаг 3: ввод целевой цены"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите криптовалюту кнопкой!")
        return ALERT_CRYPTO_STATE

    context.user_data['alert_crypto'] = text

    # Загрузить текущую цену для справки
    currency = context.user_data['alert_currency']
    data = await get_crypto_price(text, currency)
    curr_sym = '$' if currency == 'usd' else '₽'

    price_line = ""
    if data and data.get('price') is not None:
        price_str = format_price(data['price'], currency)
        change_str = format_change(data.get('change_24h', 0))
        price_line = (
            f"\n💰 Текущая цена: {price_str}\n"
            f"{change_str}\n"
        )

    emoji = CRYPTO_LIST[text]['emoji']
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
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
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
    price_str = format_price(target_price, currency)
    emoji = CRYPTO_LIST.get(crypto, {}).get('emoji', '🪙')

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
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
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

    alert_id = db.create_alert(user_id, crypto, target_price, currency, direction)

    price_str = format_price(target_price, currency)
    emoji = CRYPTO_LIST.get(crypto, {}).get('emoji', '🪙')
    dir_emoji = "⬆️ выше" if direction == 'above' else "⬇️ ниже"

    await update.message.reply_text(
        f"✅ АЛЕРТ СОЗДАН!\n"
        f"{'━' * 28}\n\n"
        f"{emoji} Крипта: {crypto}\n"
        f"🎯 Цена: {dir_emoji} {price_str}\n"
        f"🆔 ID: #{alert_id}\n\n"
        f"🔔 Вы получите уведомление когда\n"
        f"цена {crypto} станет {dir_emoji} {price_str}\n\n"
        f"⏰ Проверка каждую минуту",
        reply_markup=get_main_keyboard()
    )
    return -1


# ==================== АЛЕРТЫ: УДАЛЕНИЕ (ConversationHandler) ====================

async def delete_alert_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления алерта — показать список"""
    user_id = update.effective_user.id
    alerts = db.get_user_alerts(user_id)

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

    # === Главное меню ===
    if text == "📊 Курсы":
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
    elif text == "👤 Подписка":
        await show_subscription_info(update, context)

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
    elif text == "🎰 Крипто-рулетка":
        await show_crypto_roulette(update, context)
    elif text == "📈 Мини-график":
        await show_mini_chart(update, context)
    elif text == "🧠 Крипто-викторина":
        await show_crypto_quiz(update, context)
    elif text == "🎟 Промокод":
        await promo_start(update, context)

    # === Навигация ===
    elif text == "↩️ Назад":
        await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())

    # === Крипто-кнопки (с эмодзи) ===
    else:
        # Проверить избранное (FAV+ / FAV-)
        if text.startswith("FAV+"):
            ticker = text[4:]
            if ticker in CRYPTO_LIST:
                user_id = update.effective_user.id
                success = db.add_favorite(user_id, ticker)
                emoji = CRYPTO_LIST[ticker]['emoji']
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
            if ticker in CRYPTO_LIST:
                user_id = update.effective_user.id
                success = db.remove_favorite(user_id, ticker)
                emoji = CRYPTO_LIST[ticker]['emoji']
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

        # Проверить, нажал ли пользователь кнопку крипты (формат: "🟠 BTC")
        ticker = None
        for t in CRYPTO_LIST:
            emoji = CRYPTO_LIST[t]['emoji']
            if text == f"{emoji} {t}" or text.upper() == t:
                ticker = t
                break

        if ticker:
            await show_crypto_price(update, context, ticker)
        else:
            await update.message.reply_text(
                "❓ Используйте кнопки меню:",
                reply_markup=get_main_keyboard()
            )


# ==================== ТРЕКЕР: МЕНЮ ====================

async def show_tracker_menu(update, context):
    """Главное меню трекера"""
    user_id = update.effective_user.id
    count = db.count_user_tracked(user_id)

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
    """Показать отслеживаемые крипты"""
    user_id = update.effective_user.id
    tracked = db.get_user_tracked(user_id)

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
        emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
        name = CRYPTO_LIST.get(ticker, {}).get('name', ticker)
        text += f"{emoji} {ticker} ({name}) — порог: {threshold:.0f}%\n"

    text += f"\n📡 Проверка каждые 2 минуты\n"
    text += f"⏰ Кулдаун уведомлений: 4 часа"

    await update.message.reply_text(text, reply_markup=get_tracker_keyboard())


async def clear_tracker(update, context):
    """Очистить весь трекер"""
    user_id = update.effective_user.id
    count = db.clear_user_tracked(user_id)

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
    tracked = db.get_user_tracked(user_id)
    tracked_tickers = {item[2] for item in tracked}

    # Показать только те, что ещё не отслеживаются
    tickers = [t for t in CRYPTO_LIST if t not in tracked_tickers]

    if not tickers:
        await update.message.reply_text(
            "✅ Все криптовалюты уже в трекере!",
            reply_markup=get_tracker_keyboard()
        )
        return -1

    buttons = []
    row = []
    for ticker in tickers:
        emoji = CRYPTO_LIST[ticker]['emoji']
        row.append(KeyboardButton(f"{emoji} {ticker}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([KeyboardButton("Отмена")])

    await update.message.reply_text(
        "📡 ДОБАВИТЬ В ТРЕКЕР\n"
        f"{'═' * 28}\n\n"
        "Выберите криптовалюту для\n"
        "отслеживания резких движений:",
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
    ticker = None
    for t in CRYPTO_LIST:
        emoji = CRYPTO_LIST[t]['emoji']
        if text == f"{emoji} {t}" or text.upper() == t:
            ticker = t
            break

    if not ticker:
        await update.message.reply_text("❌ Выберите криптовалюту кнопкой!")
        return TRACKER_ADD_CRYPTO_STATE

    context.user_data['tracker_crypto'] = ticker

    emoji = CRYPTO_LIST[ticker]['emoji']
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

    if not ticker:
        await update.message.reply_text("❌ Ошибка, попробуйте снова", reply_markup=get_tracker_keyboard())
        return -1

    db.add_tracked_crypto(user_id, ticker, threshold)

    emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
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
    """Начало удаления крипты из трекера"""
    user_id = update.effective_user.id
    tracked = db.get_user_tracked(user_id)

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
        emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
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

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return TRACKER_REMOVE_CRYPTO_STATE

    success = db.remove_tracked_crypto(user_id, text)
    emoji = CRYPTO_LIST.get(text, {}).get('emoji', '🪙')

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
    count = db.count_user_tracked(user_id)

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
    """Топ-5 растущих и падающих крипт за 24ч"""
    msg = await update.message.reply_text("⏳ Анализ рынка...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать изменения
    changes = []
    for ticker, info in CRYPTO_LIST.items():
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
        emoji = CRYPTO_LIST[ticker]['emoji']
        arrow = "🟢" if change > 0 else "🔴"
        text += f"{arrow} {emoji} {ticker}: {change:+.2f}% (${price:,.2f})\n"

    text += "\n💥 ЛИДЕРЫ ПАДЕНИЯ:\n"
    for ticker, change, price in changes[-5:][::-1]:
        emoji = CRYPTO_LIST[ticker]['emoji']
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

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Нет данных")
        except Exception:
            pass
        return

    changes = []
    total_cap = 0
    total_vol = 0

    for ticker, info in CRYPTO_LIST.items():
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
        f"🕐 Данные CoinGecko"
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
    """Показать сигналы для всех криптовалют"""
    msg = await update.message.reply_text("⏳ Анализирую рынок...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    buy_list = []
    sell_list = []
    hold_list = []

    for ticker, info in CRYPTO_LIST.items():
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
    """Портфель дня — лучшие крипты для покупки с распределением %"""
    msg = await update.message.reply_text("⏳ Считаю оптимальный портфель...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать данные и оценить
    candidates = []
    for ticker, info in CRYPTO_LIST.items():
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

    # Собрать какие валюты нужны
    need_usd = any(a[4] == 'usd' for a in alerts)
    need_rub = any(a[4] == 'rub' for a in alerts)

    usd_prices = {}
    rub_prices = {}

    if need_usd:
        usd_prices = await get_all_prices('usd')
    if need_rub:
        rub_prices = await get_all_prices('rub')

    for alert in alerts:
        alert_id = alert[0]
        user_id = alert[1]
        ticker = alert[2]
        target_price = alert[3]
        currency = alert[4]
        direction = alert[5]

        prices = usd_prices if currency == 'usd' else rub_prices
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

            emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
            name = CRYPTO_LIST.get(ticker, {}).get('name', ticker)
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

    # Получить данные 24h-change
    data = await fetch_prices('usd')
    if not data:
        return

    # Собрать 24h-change для каждого тикера
    changes_map = {}
    prices_map = {}
    for ticker, info in CRYPTO_LIST.items():
        coin_data = data.get(info['id'], {})
        change = coin_data.get('usd_24h_change')
        price = coin_data.get('usd')
        if change is not None:
            changes_map[ticker] = change
        if price is not None:
            prices_map[ticker] = price

    for item in tracked:
        user_id = item[1]
        ticker = item[2]
        threshold = item[3]

        change = changes_map.get(ticker)
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
        emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
        name = CRYPTO_LIST.get(ticker, {}).get('name', ticker)
        price = prices_map.get(ticker, 0)
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
    await update.message.reply_text(
        f"🔄 КОНВЕРТЕР КРИПТОВАЛЮТ\n"
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
    await update.message.reply_text(
        "🔄 КОНВЕРТЕР\n"
        f"{'━' * 28}\n\n"
        "Шаг 1/3: Из какой криптовалюты\n"
        "конвертировать?",
        reply_markup=get_crypto_keyboard_plain()
    )
    return CONVERTER_FROM_STATE


async def converter_choose_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертер: шаг 2 — выбор целевой крипты"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите криптовалюту кнопкой!")
        return CONVERTER_FROM_STATE

    context.user_data['conv_from'] = text
    emoji = CRYPTO_LIST[text]['emoji']

    await update.message.reply_text(
        f"🔄 Из: {emoji} {text}\n\n"
        f"Шаг 2/3: В какую криптовалюту\n"
        f"конвертировать?",
        reply_markup=get_crypto_keyboard_plain()
    )
    return CONVERTER_TO_STATE


async def converter_choose_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Конвертер: шаг 3 — ввод количества"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите криптовалюту кнопкой!")
        return CONVERTER_TO_STATE

    from_ticker = context.user_data.get('conv_from')
    if text == from_ticker:
        await update.message.reply_text("❌ Выберите другую криптовалюту!")
        return CONVERTER_TO_STATE

    context.user_data['conv_to'] = text

    emoji_from = CRYPTO_LIST[from_ticker]['emoji']
    emoji_to = CRYPTO_LIST[text]['emoji']

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
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
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

    msg = await update.message.reply_text("⏳ Конвертирую...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return -1

    from_data = data.get(CRYPTO_LIST[from_ticker]['id'], {})
    to_data = data.get(CRYPTO_LIST[to_ticker]['id'], {})

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

    emoji_from = CRYPTO_LIST[from_ticker]['emoji']
    emoji_to = CRYPTO_LIST[to_ticker]['emoji']

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
            f"🕐 По текущим данным CoinGecko"
        )
    except Exception:
        await update.message.reply_text("❌ Ошибка вывода", reply_markup=get_main_keyboard())

    return -1


# ==================== ⚖️ СРАВНЕНИЕ ДВУХ КРИПТОВАЛЮТ ====================

async def show_compare_menu(update, context):
    """Меню сравнения"""
    await update.message.reply_text(
        f"⚖️ СРАВНЕНИЕ КРИПТОВАЛЮТ\n"
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
    await update.message.reply_text(
        "⚖️ СРАВНЕНИЕ\n"
        f"{'━' * 28}\n\n"
        "Шаг 1/2: Выберите первую\n"
        "криптовалюту:",
        reply_markup=get_crypto_keyboard_plain()
    )
    return COMPARE_FIRST_STATE


async def compare_choose_first(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнение: шаг 2 — вторая крипта"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return COMPARE_FIRST_STATE

    context.user_data['compare_first'] = text
    emoji = CRYPTO_LIST[text]['emoji']

    await update.message.reply_text(
        f"⚖️ Первая: {emoji} {text}\n\n"
        f"Шаг 2/2: Выберите вторую\n"
        f"криптовалюту для сравнения:",
        reply_markup=get_crypto_keyboard_plain()
    )
    return COMPARE_SECOND_STATE


async def compare_choose_second(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнение: результат"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return COMPARE_SECOND_STATE

    first = context.user_data.get('compare_first')
    if text == first:
        await update.message.reply_text("❌ Выберите другую крипту!")
        return COMPARE_SECOND_STATE

    msg = await update.message.reply_text("⏳ Сравниваю...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return -1

    d1 = data.get(CRYPTO_LIST[first]['id'], {})
    d2 = data.get(CRYPTO_LIST[text]['id'], {})

    p1, p2 = d1.get('usd', 0), d2.get('usd', 0)
    c1, c2 = d1.get('usd_24h_change', 0) or 0, d2.get('usd_24h_change', 0) or 0
    v1, v2 = d1.get('usd_24h_vol', 0) or 0, d2.get('usd_24h_vol', 0) or 0
    m1, m2 = d1.get('usd_market_cap', 0) or 0, d2.get('usd_market_cap', 0) or 0

    e1 = CRYPTO_LIST[first]['emoji']
    e2 = CRYPTO_LIST[text]['emoji']
    n1 = CRYPTO_LIST[first]['name']
    n2 = CRYPTO_LIST[text]['name']

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
        await update.message.reply_text(result, reply_markup=get_main_keyboard())

    return -1


# ==================== 🧮 КАЛЬКУЛЯТОР ПРИБЫЛИ ====================

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
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
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

    await update.message.reply_text(
        f"🧮 Валюта: {label}\n\n"
        f"Шаг 2/4: Какую криптовалюту\n"
        f"вы покупали?",
        reply_markup=get_crypto_keyboard_plain()
    )
    return CALC_CRYPTO_STATE


async def calc_choose_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Калькулятор: шаг 3 — цена покупки"""
    text = update.message.text.strip().upper()

    if text == "ОТМЕНА":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    if text not in CRYPTO_LIST:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return CALC_CRYPTO_STATE

    context.user_data['calc_crypto'] = text
    emoji = CRYPTO_LIST[text]['emoji']

    currency = context.user_data.get('calc_currency', 'usd')
    curr_sym = '$' if currency == 'usd' else '₽'

    # Показать текущую цену для справки
    data = await get_crypto_price(text, currency)
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

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
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
    emoji = CRYPTO_LIST[crypto]['emoji']

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

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
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

    data = await get_crypto_price(crypto, currency)
    if not data or not data.get('price'):
        try:
            await msg.edit_text("❌ Не удалось получить текущую цену")
        except Exception:
            pass
        await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())
        return -1

    current_price = data['price']
    emoji = CRYPTO_LIST[crypto]['emoji']

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
        f"{emoji} {CRYPTO_LIST[crypto]['name']} ({crypto})\n\n"
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

    # Вернуть главное меню
    await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())
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
    await update.message.reply_text(
        f"🏆 РЕЙТИНГИ КРИПТОВАЛЮТ\n"
        f"{'═' * 28}\n\n"
        f"Сортировка {len(CRYPTO_LIST)} криптовалют\n"
        f"по разным параметрам:\n\n"
        f"💎 Капитализация — топ по стоимости\n"
        f"📈 Рост 24ч — лучшие за сутки\n"
        f"📊 Объём — самые торгуемые\n"
        f"📉 Лузеры — худшие за сутки",
        reply_markup=get_rankings_keyboard()
    )


async def _get_ranking_data():
    """Получить данные для рейтинга"""
    data = await fetch_prices('usd')
    if not data:
        return None

    items = []
    for ticker, info in CRYPTO_LIST.items():
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
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data()
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
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data()
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
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data()
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
    msg = await update.message.reply_text("⏳ Загрузка рейтинга...")
    items = await _get_ranking_data()
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
    count = db.count_favorites(user_id)

    await update.message.reply_text(
        f"⭐ ИЗБРАННОЕ\n"
        f"{'═' * 28}\n\n"
        f"📌 В избранном: {count} крипт\n\n"
        f"Добавляйте криптовалюты в избранное\n"
        f"для быстрого доступа к их ценам!\n\n"
        f"➕ Добавить в избранное\n"
        f"➖ Убрать из избранного\n"
        f"📋 Список избранных\n"
        f"📊 Цены всех избранных сразу",
        reply_markup=get_favorites_keyboard()
    )


async def favorites_add_start_msg(update, context):
    """Показать крипты для добавления в избранное"""
    user_id = update.effective_user.id
    favorites = db.get_user_favorites(user_id)

    # Показать только те, что ещё не в избранном
    available = [t for t in CRYPTO_LIST if t not in favorites]

    if not available:
        await update.message.reply_text(
            "✅ Все криптовалюты уже в избранном!",
            reply_markup=get_favorites_keyboard()
        )
        return

    buttons = []
    row = []
    for ticker in available:
        emoji = CRYPTO_LIST[ticker]['emoji']
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
        emoji = CRYPTO_LIST[ticker]['emoji']
        text += f"{emoji} {ticker} — {CRYPTO_LIST[ticker]['name']}\n"
    text += "\nВыберите криптовалюту:"

    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


async def favorites_remove_start_msg(update, context):
    """Показать избранные для удаления"""
    user_id = update.effective_user.id
    favorites = db.get_user_favorites(user_id)

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
        emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
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
    favorites = db.get_user_favorites(user_id)

    if not favorites:
        await update.message.reply_text(
            "📋 Избранное пусто! Добавьте крипты ⭐",
            reply_markup=get_favorites_keyboard()
        )
        return

    text = f"⭐ МОЁ ИЗБРАННОЕ ({len(favorites)})\n{'━' * 28}\n\n"
    for ticker in favorites:
        emoji = CRYPTO_LIST.get(ticker, {}).get('emoji', '🪙')
        name = CRYPTO_LIST.get(ticker, {}).get('name', ticker)
        text += f"{emoji} {ticker} — {name}\n"

    await update.message.reply_text(text, reply_markup=get_favorites_keyboard())


async def show_favorites_prices(update, context):
    """Показать цены всех избранных"""
    user_id = update.effective_user.id
    favorites = db.get_user_favorites(user_id)

    if not favorites:
        await update.message.reply_text(
            "📋 Избранное пусто!",
            reply_markup=get_favorites_keyboard()
        )
        return

    msg = await update.message.reply_text("⏳ Загружаю цены избранных...")

    data = await fetch_prices('usd')
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
        info = CRYPTO_LIST.get(ticker)
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
    count = db.clear_favorites(user_id)

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
        [KeyboardButton("🎰 Крипто-рулетка"), KeyboardButton("🧠 Крипто-викторина")],
        [KeyboardButton("🎟 Промокод")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


async def show_extra_menu(update, context):
    """Дополнительное меню"""
    await update.message.reply_text(
        f"🔧 ДОПОЛНИТЕЛЬНО\n"
        f"{'═' * 28}\n\n"
        f"📰 Дайджест — сводка рынка\n"
        f"📈 Мини-график — ASCII-визуализация\n"
        f"🎰 Крипто-рулетка — случайный совет\n"
        f"🧠 Крипто-викторина — проверь знания\n"
        f"🎟 Промокод — активировать код",
        reply_markup=get_extra_keyboard()
    )


# ==================== 📰 РЫНОЧНЫЙ ДАЙДЖЕСТ ====================

async def show_market_digest(update, context):
    """Рыночный дайджест — умная сводка"""
    msg = await update.message.reply_text("⏳ Собираю дайджест рынка...")

    data = await fetch_prices('usd')
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

    for ticker, info in CRYPTO_LIST.items():
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
    msg = await update.message.reply_text("⏳ Строю график...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    items = []
    for ticker, info in CRYPTO_LIST.items():
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
    msg = await update.message.reply_text("🎰 Кручу барабан...")

    data = await fetch_prices('usd')
    if not data:
        try:
            await msg.edit_text("❌ Не удалось загрузить данные")
        except Exception:
            pass
        return

    # Собрать доступные крипты
    available = []
    for ticker, info in CRYPTO_LIST.items():
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


# ==================== 🧠 КРИПТО-ВИКТОРИНА ====================

# --- ВОПРОСЫ ПО УРОВНЯМ СЛОЖНОСТИ ---

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

    data = await get_crypto_price(ticker, 'usd')
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
            f"🔔 Алерты: ❌\n"
            f"📡 Трекер: ❌\n"
            f"🧮 Калькулятор: ❌\n"
            f"🏆 Рейтинг: ❌\n"
            f"🤖 Сигналы: ❌"
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
            f"🔔 Алерты: ✅\n"
            f"📡 Трекер: ✅\n"
            f"🧮 Калькулятор: ✅\n"
            f"🏆 Рейтинг: ✅\n"
            f"🤖 Сигналы: ❌"
        )
    else:  # premium
        features = (
            f"📊 Курсы: все {len(CRYPTO_LIST)} крипт\n"
            f"🔄 Конвертер: ✅\n"
            f"⚖️ Сравнение: ✅\n"
            f"⭐ Избранное: ✅\n"
            f"📰 Дайджест: ✅\n"
            f"🎰 Рулетка: ✅\n"
            f"🧠 Викторина: ✅\n"
            f"🔔 Алерты: ✅\n"
            f"📡 Трекер: ✅\n"
            f"🧮 Калькулятор: ✅\n"
            f"🏆 Рейтинг: ✅\n"
            f"🤖 Сигналы: ✅"
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
