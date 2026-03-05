"""Обработчики команд и сообщений бота"""

import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from database import Database
from config import (
    ADMIN_IDS, MIN_BET, INITIAL_BALANCE, ADMIN_PASSWORD,
    ROULETTE_BET_STATE, ROULETTE_CHOICE_STATE,
    COINFLIP_BET_STATE, COINFLIP_CHOICE_STATE,
    DICE_BET_STATE,
    BLACKJACK_BET_STATE, BLACKJACK_PLAY_STATE,
    SLOTS_BET_STATE,
    CRASH_BET_STATE, CRASH_CHOICE_STATE,
    BOWLING_BET_STATE,
    DARTS_BET_STATE, DARTS_CHOICE_STATE,
    BET_TYPE_STATE, BET_EVENT_ID_STATE, BET_AMOUNT_STATE, BET_RESULT_STATE,
    AUTO_EVENT_INTERVAL,
    OWNER_PASSWORD, OWNER_PASSWORD_STATE, OWNER_MENU_STATE, OWNER_RESET_USER_STATE,
    MINES_BET_STATE, MINES_PLAY_STATE,
    WHEEL_BET_STATE,
    HIGHLOW_BET_STATE, HIGHLOW_PLAY_STATE,
    RUSSIANR_BET_STATE, RUSSIANR_CHOICE_STATE
)
from utils import (
    format_balance, format_bet_info, format_leaderboard,
    format_user_stats, validate_bet_amount, get_keyboard_main
)

db = Database()


async def check_consolation_bonus(user_id):
    """Проверить и выдать утешительные бонусы после проигрыша.
    Возвращает текст для добавления к сообщению результата."""
    bonus_text = ""
    
    # Бонус за 10 поражений подряд
    streak_bonus = db.check_loss_streak_bonus(user_id, streak_required=10)
    if streak_bonus > 0:
        bonus_text += f"\n\n🎁 УТЕШИТЕЛЬНЫЙ БОНУС!\n10 поражений подряд... Держи +{streak_bonus} монет! 💪"
    
    # Бонус за общую сумму проигрышей (1000, 5000, 10000...)
    milestones = db.check_total_loss_milestone(user_id)
    for milestone, bonus in milestones:
        bonus_text += f"\n\n🏅 ДОСТИЖЕНИЕ РАЗБЛОКИРОВАНО!\nПроиграно {milestone}+ монет → +{bonus} монет в подарок!"
    
    return bonus_text


async def award_xp(user_id, bet_amount, won):
    """Начислить XP за игру. Возвращает текст о XP/левелапе или пустую строку."""
    # XP = 10% от ставки (мин 1) + бонус за победу
    xp_amount = max(1, bet_amount // 10)
    if won:
        xp_amount = int(xp_amount * 1.5)
    
    result = db.add_xp(user_id, xp_amount)
    if not result:
        return ""
    
    new_xp, old_level, new_level = result
    text = f"\n⭐ +{xp_amount} XP"
    
    if new_level > old_level:
        text += f"\n\n🎊 НОВЫЙ УРОВЕНЬ! {old_level} → {new_level} 🎊"
        # Бонус за уровень: level * 50 монет
        level_bonus = new_level * 50
        db.update_balance(user_id, level_bonus)
        text += f"\n🎁 Бонус за уровень: +{level_bonus} монет!"
    
    return text


def make_bar(percent, width=10):
    """Создать визуальную полоску шансов"""
    filled = round(percent / 100 * width)
    return "█" * filled + "░" * (width - filled)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    
    # Добавить пользователя если его еще нет
    existing_user = db.get_user(user_id)
    if not existing_user:
        db.add_user(user_id, username)
        welcome = (
            f"🎰 BETTING BOT — Бот ставок на события\n"
            f"{'═' * 35}\n\n"
            f"👋 Добро пожаловать, {username}!\n\n"
            f"🤖 Что это за бот?\n"
            f"Развлекательный бот с виртуальными ставками и мини-играми.\n\n"
            f"🎯 Как это работает?\n"
            f"• Делай ставки на события и мини-игры\n"
            f"• Зарабатывай монеты и поднимайся в рейтинге\n"
            f"• Открывай достижения и получай бонусы\n\n"
            f"💰 Твой стартовый баланс: {INITIAL_BALANCE} монет\n\n"
            f"📋 Разделы:\n"
            f"• 🎮 Мини-игры — 12 игр! Рулетка, монетка,\n"
            f"  кости, блэкджек, слоты, краш, боулинг,\n"
            f"  дартс, минное поле, колесо, больше/меньше,\n"
            f"  русская рулетка\n"
            f"• 🎲 Ставки — ставки на события бота и админа\n"
            f"• 👤 Профиль — баланс, уровень, достижения\n"
            f"• 🎁 Бонусы — дневной бонус и восстановление\n"
            f"• ⭐ Система уровней — получай XP за игры!\n\n"
            f"⚡ Минимальная ставка: {MIN_BET} монет\n"
            f"⚠️ Валюта виртуальная — играй в удовольствие!\n"
            f"{'═' * 35}\n"
        )
    else:
        welcome = f"👋 Рады видеть вас снова, {username}!"
    
    await update.message.reply_text(
        welcome + "\n\nВыберите раздел:",
        reply_markup=get_main_keyboard()
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать баланс пользователя с серией побед"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Пользователь не найден. Используйте /start")
        return
    
    balance_text = format_user_stats(user)
    
    # Добавить серию побед/поражений
    streak, streak_type = db.get_user_streak(user_id)
    if streak >= 2:
        if streak_type == 'won':
            streak_text = f"\n🔥 Серия побед: {streak} подряд!"
            if streak >= 5:
                streak_text += " 🌟 НЕВЕРОЯТНО!"
            elif streak >= 3:
                streak_text += " 💪 Отлично!"
        else:
            streak_text = f"\n❄️ Серия поражений: {streak} подряд"
            if streak >= 5:
                streak_text += " 😢"
        balance_text += streak_text
    
    # Банкрот-подсказка
    if user[2] == 0:
        balance_text += "\n\n💀 Вы банкрот! Перейдите в 🎁 Бонусы для восстановления (50 монет, раз в день)"
        keyboard = [
            [KeyboardButton("💊 Банкрот")],
            [KeyboardButton("🎮 Мини-игры"), KeyboardButton("🎲 Ставки")],
            [KeyboardButton("📋 События"), KeyboardButton("👤 Профиль")],
            [KeyboardButton("🎁 Бонусы"), KeyboardButton("❓ Помощь")],
            [KeyboardButton("👨‍💼 Админ")]
        ]
        await update.message.reply_text(
            balance_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(balance_text, reply_markup=get_main_keyboard())

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать историю ставок"""
    user_id = update.effective_user.id
    bets = db.get_user_bets(user_id)
    
    if not bets:
        await update.message.reply_text("📭 У вас пока нет ставок")
        return
    
    text = "📜 ИСТОРИЯ СТАВОК:\n\n"
    for bet in bets:
        text += format_bet_info(bet) + "\n"
    
    await update.message.reply_text(text)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать таблицу лидеров"""
    leaderboard_data = db.get_leaderboard(10)
    
    if not leaderboard_data:
        await update.message.reply_text("📭 Лидеров еще нет")
        return
    
    text = format_leaderboard(leaderboard_data)
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать справку"""
    help_text = f"""
🤖 СПРАВКА ПО БОТУ:

📋 Команды:
/start — главное меню
/balance — баланс
/history — история ставок
/leaderboard — лидеры
/help — справка

📂 Навигация:
• 🎮 Мини-игры — все мини-игры в одном разделе
• 🎲 Ставки — ставки на события
• 📋 События — просмотр всех событий
• 👤 Профиль — баланс, история, достижения, лидеры
• 🎁 Бонусы — дневной бонус + восстановление
• ↩️ Назад — вернуться в главное меню

🎮 Мини-игры (12 штук!):
• 🎰 Рулетка — красное/чёрное x2, зелёное x10
• 🪙 Монетка — орёл/решка 50/50 (x2)
• 🎯 Кости — 2 кубика против бота (x2, дубль x3)
• 🃏 Блэкджек — набери 21 (x2, блэкджек x2.5)
• 🍀 Слоты — крути барабаны (до x20!)
• 🚀 Краш — множитель растёт (до x50!)
• 🎳 Боулинг — сбей кегли (страйк x5!)
• 🎯 Дартс — попади в яблочко (x10!)
• 💣 Минное поле — открывай клетки (до x500!)
• 🎡 Колесо фортуны — крути колесо (джекпот x10!)
• 📊 Больше/Меньше — угадай карту (x2 за каждый!)
• 🔫 Русская рулетка — нажми на курок (до x6!)

⭐ Система уровней:
• Получай XP за каждую игру
• Больше ставка = больше XP
• Победы дают x1.5 XP
• За новый уровень — бонус монет!

🎁 Утешительные бонусы:
• 10 поражений подряд → +50-100 монет
• Пороги суммарных проигрышей → +5% от порога

💡 Как ставить:
1. 🎲 Ставки → тип событий
2. Выбрать событие по ID
3. Ввести сумму (мин. {MIN_BET})
4. Выбрать участника
5. Ждать результат!

⚙️ Правила:
• Мин. ставка: {MIN_BET} монет
• Старт: {INITIAL_BALANCE} монет
• 1 ставка на событие
    """.strip()
    
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить дневной бонус"""
    user_id = update.effective_user.id
    bonus, message = db.claim_daily_bonus(user_id)
    
    if bonus:
        user = db.get_user(user_id)
        new_balance = user[2]
        await update.message.reply_text(
            f"🎁 {message}\n"
            f"Вы получили: +{bonus} монет\n"
            f"Новый баланс: {new_balance} монет"
        )
    else:
        await update.message.reply_text(f"⏰ {message}")


def get_main_keyboard():
    """Получить главную клавиатуру (иерархическое меню)"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎮 Мини-игры"), KeyboardButton("🎲 Ставки")],
        [KeyboardButton("📋 События"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("🎁 Бонусы"), KeyboardButton("❓ Помощь")],
        [KeyboardButton("👨‍💼 Админ"), KeyboardButton("👑 Хозяин")]
    ], resize_keyboard=True)


def get_games_keyboard():
    """Подменю мини-игр"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎰 Рулетка"), KeyboardButton("🪙 Монетка")],
        [KeyboardButton("🎯 Кости"), KeyboardButton("🃏 Блэкджек")],
        [KeyboardButton("🍀 Слоты"), KeyboardButton("🚀 Краш")],
        [KeyboardButton("🎳 Боулинг"), KeyboardButton("🎯 Дартс")],
        [KeyboardButton("💣 Минное поле"), KeyboardButton("🎡 Колесо")],
        [KeyboardButton("📊 Больше/Меньше"), KeyboardButton("🔫 Русская рулетка")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_profile_keyboard():
    """Подменю профиля"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Баланс"), KeyboardButton("📊 История")],
        [KeyboardButton("🏆 Лидеры"), KeyboardButton("🎖 Достижения")],
        [KeyboardButton("🏅 Результат")],
        [KeyboardButton("↩️ Назад")]
    ], resize_keyboard=True)


def get_bonuses_keyboard(is_bankrupt=False):
    """Подменю бонусов"""
    buttons = []
    buttons.append([KeyboardButton("🎁 Дневной бонус")])
    if is_bankrupt:
        buttons.append([KeyboardButton("💊 Банкрот")])
    buttons.append([KeyboardButton("↩️ Назад")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def show_games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подменю мини-игр"""
    await update.message.reply_text(
        "🎮 МИНИ-ИГРЫ\n"
        f"{'═' * 28}\n\n"
        "🎰 Рулетка — красное/чёрное x2, зелёное x10\n"
        "🪙 Монетка — орёл/решка, 50/50, x2\n"
        "🎯 Кости — 2 кубика против бота, x2 (дубль x3)\n"
        "🃏 Блэкджек — набери 21, x2 (блэкджек x2.5)\n"
        "🍀 Слоты — крути барабаны, до x20!\n"
        "🚀 Краш — множитель растёт, до x50!\n"
        "🎳 Боулинг — сбей кегли, страйк x5!\n"
        "🎯 Дартс — попади в яблочко x10!\n\n"
        "Выберите игру:",
        reply_markup=get_games_keyboard()
    )


async def show_profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подменю профиля"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    balance_val = user[2] if user else 0
    wins = user[3] if user else 0
    losses = user[4] if user else 0
    
    # XP и уровень
    xp, level, xp_to_next = db.get_user_xp_info(user_id)
    # Прогресс-бар уровня
    prev_level_xp = db.xp_for_next_level(level - 1) if level > 1 else 0
    xp_in_level = xp - prev_level_xp
    xp_needed = xp_to_next - prev_level_xp
    progress = xp_in_level / xp_needed * 100 if xp_needed > 0 else 100
    level_bar = make_bar(progress)
    
    await update.message.reply_text(
        f"👤 ПРОФИЛЬ\n"
        f"{'═' * 28}\n\n"
        f"⭐ Уровень: {level} | XP: {xp}/{xp_to_next}\n"
        f"   {level_bar} {progress:.0f}%\n\n"
        f"💰 Баланс: {balance_val} монет\n"
        f"✅ Побед: {wins} | ❌ Поражений: {losses}\n\n"
        f"Выберите раздел:",
        reply_markup=get_profile_keyboard()
    )


async def show_bonuses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать подменю бонусов"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    is_bankrupt = user and user[2] == 0
    
    text = (
        f"🎁 БОНУСЫ\n"
        f"{'═' * 28}\n\n"
        f"🎁 Дневной бонус — 10-50 монет раз в 24 часа\n"
    )
    if is_bankrupt:
        text += "💊 Банкрот — 50 монет при нулевом балансе (раз в день)\n"
    
    text += "\nВыберите:"
    
    await update.message.reply_text(
        text,
        reply_markup=get_bonuses_keyboard(is_bankrupt)
    )


async def start_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры в рулетку"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1
    
    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\n"
            f"Минимальная ставка: {MIN_BET} монет\n"
            f"Ваш баланс: {user_balance} монет",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    await update.message.reply_text(
        f"🎰 РУЛЕТКА\n"
        f"{'═' * 28}\n\n"
        f"� Шансы и выплаты:\n"
        f"🔴 Красное (18/37) — 48.6% — x2\n"
        f"⚫ Чёрное  (18/37) — 48.6% — x2\n"
        f"🟢 Зелёное  (1/37) —  2.7% — x10\n\n"
        f"🔢 Числа 1-36: нечётное = 🔴, чётное = ⚫\n"
        f"🔢 Число 0 = 🟢 (зелёное)\n\n"
        f"📈 Математическое ожидание:\n"
        f"  🔴/⚫: 48.6% × 2 = 97.3% возврата\n"
        f"  🟢: 2.7% × 10 = 27.0% возврата\n\n"
        f"💰 Ваш баланс: {user_balance} монет\n\n"
        f"Введите сумму ставки (минимум {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Отмена")]],
            resize_keyboard=True
        )
    )
    return ROULETTE_BET_STATE


async def roulette_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить сумму ставки для рулетки"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    try:
        amount = int(update.message.text)
        user = db.get_user(update.effective_user.id)
        user_balance = user[2]
        
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимум {MIN_BET} монет! Попробуйте ещё:")
            return ROULETTE_BET_STATE
        
        if amount > user_balance:
            await update.message.reply_text(f"❌ Недостаточно! Баланс: {user_balance} монет")
            return ROULETTE_BET_STATE
        
        context.user_data['roulette_amount'] = amount
        
        keyboard = [
            [KeyboardButton("🔴 Красное"), KeyboardButton("⚫ Чёрное")],
            [KeyboardButton("🟢 Зелёное")],
            [KeyboardButton("Отмена")]
        ]
        
        await update.message.reply_text(
            f"💵 Ставка: {amount} монет\n\n🎨 Выберите цвет:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return ROULETTE_CHOICE_STATE
        
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return ROULETTE_BET_STATE


async def roulette_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор цвета и розыгрыш рулетки"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('roulette_amount', 0)
    
    # Определить выбор игрока
    if "Красное" in text:
        choice = "red"
        choice_name = "🔴 КРАСНОЕ"
    elif "Чёрное" in text:
        choice = "black"
        choice_name = "⚫ ЧЁРНОЕ"
    elif "Зелёное" in text:
        choice = "green"
        choice_name = "🟢 ЗЕЛЁНОЕ"
    else:
        await update.message.reply_text("❌ Выберите цвет кнопкой!")
        return ROULETTE_CHOICE_STATE
    
    # Проверить баланс
    user = db.get_user(user_id)
    if not user or user[2] < amount:
        await update.message.reply_text("❌ Недостаточно монет!", reply_markup=get_main_keyboard())
        return -1
    
    # 🎰 Крутим рулетку! Числа 0-36
    number = random.randint(0, 36)
    if number == 0:
        result_color = "green"
        result_emoji = "🟢"
        result_name = "ЗЕЛЁНОЕ"
    elif number % 2 == 1:
        result_color = "red"
        result_emoji = "🔴"
        result_name = "КРАСНОЕ"
    else:
        result_color = "black"
        result_emoji = "⚫"
        result_name = "ЧЁРНОЕ"
    
    won = (choice == result_color)
    
    if won:
        multiplier = 10 if result_color == "green" else 2
        winnings = amount * multiplier
        net = winnings - amount
        db.update_balance(user_id, net)
        detail = 'green_win' if result_color == 'green' else 'color_win'
        db.record_game(user_id, 'roulette', amount, True, winnings, detail)
        new_balance = user[2] + net
        
        result_text = (
            f"🎰 РУЛЕТКА КРУТИТСЯ...\n"
            f"{'━' * 28}\n\n"
            f"🔢 Выпало: {number} — {result_emoji} {result_name}\n"
            f"🎯 Ваш выбор: {choice_name}\n\n"
            f"🎉 ВЫИГРЫШ! +{winnings} монет (x{multiplier})!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    else:
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'roulette', amount, False, 0, 'loss')
        new_balance = user[2] - amount
        
        result_text = (
            f"🎰 РУЛЕТКА КРУТИТСЯ...\n"
            f"{'━' * 28}\n\n"
            f"🔢 Выпало: {number} — {result_emoji} {result_name}\n"
            f"🎯 Ваш выбор: {choice_name}\n\n"
            f"😢 Не повезло... -{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        if new_balance == 0:
            result_text += "\n\n💀 Баланс пуст! Проверьте /balance для восстановления"
        result_text += await check_consolation_bonus(user_id)
    
    await update.message.reply_text(result_text, reply_markup=get_main_keyboard())
    return -1


async def start_coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры в монетку"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1
    
    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\n"
            f"Минимум: {MIN_BET} монет | Баланс: {user_balance} монет",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    await update.message.reply_text(
        f"🪙 МОНЕТКА\n"
        f"{'═' * 28}\n\n"
        f"Классическая игра! 50/50 шанс.\n"
        f"Угадай сторону — получи x2!\n\n"
        f"🦅 Орёл — выплата x2\n"
        f"🌿 Решка — выплата x2\n\n"
        f"💰 Ваш баланс: {user_balance} монет\n\n"
        f"Введите сумму ставки (минимум {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Отмена")]],
            resize_keyboard=True
        )
    )
    return COINFLIP_BET_STATE


async def coinflip_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить сумму ставки для монетки"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    try:
        amount = int(update.message.text)
        user = db.get_user(update.effective_user.id)
        user_balance = user[2]
        
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимум {MIN_BET} монет!")
            return COINFLIP_BET_STATE
        
        if amount > user_balance:
            await update.message.reply_text(f"❌ Недостаточно! Баланс: {user_balance}")
            return COINFLIP_BET_STATE
        
        context.user_data['coinflip_amount'] = amount
        
        keyboard = [
            [KeyboardButton("🦅 Орёл"), KeyboardButton("🌿 Решка")],
            [KeyboardButton("Отмена")]
        ]
        
        await update.message.reply_text(
            f"💵 Ставка: {amount} монет\n\n🪙 Орёл или Решка?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return COINFLIP_CHOICE_STATE
        
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return COINFLIP_BET_STATE


async def coinflip_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор стороны и бросок монетки"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('coinflip_amount', 0)
    
    if "Орёл" in text:
        choice = "heads"
        choice_name = "🦅 Орёл"
    elif "Решка" in text:
        choice = "tails"
        choice_name = "🌿 Решка"
    else:
        await update.message.reply_text("❌ Выберите сторону кнопкой!")
        return COINFLIP_CHOICE_STATE
    
    # Проверить баланс
    user = db.get_user(user_id)
    if not user or user[2] < amount:
        await update.message.reply_text("❌ Недостаточно монет!", reply_markup=get_main_keyboard())
        return -1
    
    # 🪙 Бросаем монетку!
    result = random.choice(["heads", "tails"])
    result_name = "🦅 ОРЁЛ" if result == "heads" else "🌿 РЕШКА"
    
    won = (choice == result)
    
    if won:
        winnings = amount * 2
        net = amount  # winnings - bet
        db.update_balance(user_id, net)
        db.record_game(user_id, 'coinflip', amount, True, winnings, 'flip_win')
        new_balance = user[2] + net
        
        result_text = (
            f"🪙 Монетка летит в воздух...\n"
            f"{'━' * 28}\n\n"
            f"Результат: {result_name}!\n"
            f"Ваш выбор: {choice_name}\n\n"
            f"🎉 ВЫИГРЫШ! +{winnings} монет (x2)!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    else:
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'coinflip', amount, False, 0, 'flip_loss')
        new_balance = user[2] - amount
        
        result_text = (
            f"🪙 Монетка летит в воздух...\n"
            f"{'━' * 28}\n\n"
            f"Результат: {result_name}!\n"
            f"Ваш выбор: {choice_name}\n\n"
            f"😢 Не повезло... -{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        if new_balance == 0:
            result_text += "\n\n💀 Баланс пуст! Проверьте /balance для восстановления"
        result_text += await check_consolation_bonus(user_id)
    
    await update.message.reply_text(result_text, reply_markup=get_main_keyboard())
    return -1


async def start_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры в кости"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1

    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\n"
            f"Минимальная ставка: {MIN_BET} монет\n"
            f"Ваш баланс: {user_balance} монет",
            reply_markup=get_main_keyboard()
        )
        return -1

    await update.message.reply_text(
        f"🎯 КОСТИ (DICE DUEL)\n"
        f"{'═' * 28}\n\n"
        f"Ты и бот бросаете по 2 кубика 🎲🎲\n"
        f"У кого сумма больше — тот победил!\n\n"
        f"💰 Выигрыш: x2\n"
        f"🤝 Ничья: возврат ставки\n"
        f"🎯 Дубль (два одинаковых): x3!\n\n"
        f"💰 Ваш баланс: {user_balance} монет\n\n"
        f"Введите сумму ставки (минимум {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Отмена")]],
            resize_keyboard=True
        )
    )
    return DICE_BET_STATE


async def dice_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ставку и сразу бросить кости"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    try:
        amount = int(update.message.text)
        user_id = update.effective_user.id
        user = db.get_user(user_id)
        user_balance = user[2]

        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимум {MIN_BET} монет! Попробуйте ещё:")
            return DICE_BET_STATE

        if amount > user_balance:
            await update.message.reply_text(f"❌ Недостаточно! Баланс: {user_balance} монет")
            return DICE_BET_STATE

        # 🎲 Бросаем кости!
        player_d1 = random.randint(1, 6)
        player_d2 = random.randint(1, 6)
        bot_d1 = random.randint(1, 6)
        bot_d2 = random.randint(1, 6)

        player_total = player_d1 + player_d2
        bot_total = bot_d1 + bot_d2
        player_double = (player_d1 == player_d2)

        # Визуализация кубиков
        dice_faces = {1: '⚀', 2: '⚁', 3: '⚂', 4: '⚃', 5: '⚄', 6: '⚅'}
        p1 = dice_faces[player_d1]
        p2 = dice_faces[player_d2]
        b1 = dice_faces[bot_d1]
        b2 = dice_faces[bot_d2]

        result_text = (
            f"🎯 КОСТИ ЛЕТЯТ...\n"
            f"{'━' * 28}\n\n"
            f"👤 Ты: {p1} {p2}  = {player_total}"
        )
        if player_double:
            result_text += " 🔥 ДУБЛЬ!"
        result_text += f"\n🤖 Бот: {b1} {b2}  = {bot_total}\n\n"

        if player_total > bot_total:
            # Победа!
            multiplier = 3 if player_double else 2
            winnings = amount * multiplier
            net = winnings - amount
            db.update_balance(user_id, net)
            detail = 'dice_double_win' if player_double else 'dice_win'
            db.record_game(user_id, 'dice', amount, True, winnings, detail)
            new_balance = user_balance + net

            result_text += (
                f"🎉 ПОБЕДА! +{winnings} монет (x{multiplier})!\n"
            )
            if player_double:
                result_text += f"🔥 Бонус за дубль! Множитель x3!\n"
            result_text += f"💰 Баланс: {new_balance} монет"
        elif player_total == bot_total:
            # Ничья — возврат
            db.record_game(user_id, 'dice', amount, False, amount, 'dice_draw')
            result_text += (
                f"🤝 НИЧЬЯ! Ставка возвращена.\n"
                f"💰 Баланс: {user_balance} монет"
            )
        else:
            # Проигрыш
            db.update_balance(user_id, -amount)
            db.record_game(user_id, 'dice', amount, False, 0, 'dice_loss')
            new_balance = user_balance - amount

            result_text += (
                f"😢 Не повезло... -{amount} монет\n"
                f"💰 Баланс: {new_balance} монет"
            )
            if new_balance == 0:
                result_text += "\n\n💀 Баланс пуст! Проверьте /balance для восстановления"
            result_text += await check_consolation_bonus(user_id)

        await update.message.reply_text(result_text, reply_markup=get_main_keyboard())
        return -1

    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return DICE_BET_STATE


    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return DICE_BET_STATE


# ═══════════════════════════ БЛЭКДЖЕК ═══════════════════════════

CARD_SUITS = ['♠️', '♥️', '♦️', '♣️']
CARD_NAMES = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11
}


def create_deck():
    """Создать и перемешать колоду из 52 карт"""
    deck = [(name, suit) for suit in CARD_SUITS for name in CARD_NAMES]
    random.shuffle(deck)
    return deck


def card_str(card):
    """Отобразить карту: J♠️"""
    return f"{card[0]}{card[1]}"


def hand_str(hand):
    """Отобразить руку: J♠️ 5♥️"""
    return "  ".join(card_str(c) for c in hand)


def hand_value(hand):
    """Посчитать очки руки (туз = 11 или 1)"""
    total = sum(CARD_VALUES[c[0]] for c in hand)
    aces = sum(1 for c in hand if c[0] == 'A')
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def is_blackjack(hand):
    """Блэкджек = ровно 2 карты и 21 очко"""
    return len(hand) == 2 and hand_value(hand) == 21


async def start_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры в блэкджек"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1

    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\n"
            f"Минимальная ставка: {MIN_BET} монет\n"
            f"Ваш баланс: {user_balance} монет",
            reply_markup=get_main_keyboard()
        )
        return -1

    await update.message.reply_text(
        f"🃏 БЛЭКДЖЕК\n"
        f"{'═' * 28}\n\n"
        f"Набери 21 или ближе к 21, чем дилер!\n\n"
        f"📜 Правила:\n"
        f"• Карты 2-10 = номинал, J/Q/K = 10, A = 11 или 1\n"
        f"• Перебор (>21) = проигрыш\n"
        f"• Блэкджек (21 с 2 карт) = выплата x2.5!\n"
        f"• Обычная победа = x2\n"
        f"• Ничья = возврат ставки\n\n"
        f"💰 Ваш баланс: {user_balance} монет\n\n"
        f"Введите сумму ставки (минимум {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Отмена")]],
            resize_keyboard=True
        )
    )
    return BLACKJACK_BET_STATE


async def blackjack_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ставку, раздать карты"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    try:
        amount = int(update.message.text)
        user_id = update.effective_user.id
        user = db.get_user(user_id)
        user_balance = user[2]

        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимум {MIN_BET} монет! Попробуйте ещё:")
            return BLACKJACK_BET_STATE

        if amount > user_balance:
            await update.message.reply_text(f"❌ Недостаточно! Баланс: {user_balance} монет")
            return BLACKJACK_BET_STATE

        # Создать колоду и раздать карты
        deck = create_deck()
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]

        context.user_data['bj_amount'] = amount
        context.user_data['bj_deck'] = deck
        context.user_data['bj_player'] = player_hand
        context.user_data['bj_dealer'] = dealer_hand

        player_val = hand_value(player_hand)

        # Проверить блэкджек у игрока
        if is_blackjack(player_hand):
            # Мгновенный блэкджек!
            dealer_val = hand_value(dealer_hand)

            if is_blackjack(dealer_hand):
                # Оба блэкджека — ничья
                db.record_game(user_id, 'blackjack', amount, False, amount, 'bj_double_blackjack')
                text = (
                    f"🃏 БЛЭКДЖЕК — РАЗДАЧА\n"
                    f"{'━' * 28}\n\n"
                    f"🎴 Ты: {hand_str(player_hand)}  = {player_val} 🔥 БЛЭКДЖЕК!\n"
                    f"🎴 Дилер: {hand_str(dealer_hand)}  = {dealer_val} 🔥 БЛЭКДЖЕК!\n\n"
                    f"🤝 НИЧЬЯ! Оба с блэкджеком. Ставка возвращена.\n"
                    f"💰 Баланс: {user_balance} монет"
                )
            else:
                winnings = int(amount * 2.5)
                net = winnings - amount
                db.update_balance(user_id, net)
                db.record_game(user_id, 'blackjack', amount, True, winnings, 'blackjack_21')
                new_balance = user_balance + net
                text = (
                    f"🃏 БЛЭКДЖЕК — РАЗДАЧА\n"
                    f"{'━' * 28}\n\n"
                    f"🎴 Ты: {hand_str(player_hand)}  = {player_val} 🔥 БЛЭКДЖЕК!\n"
                    f"🎴 Дилер: {card_str(dealer_hand[0])}  🂠\n\n"
                    f"🎉 БЛЭКДЖЕК! +{winnings} монет (x2.5)!\n"
                    f"💰 Баланс: {new_balance} монет"
                )

            await update.message.reply_text(text, reply_markup=get_main_keyboard())
            return -1

        # Показать раздачу и предложить действие
        text = (
            f"🃏 БЛЭКДЖЕК — РАЗДАЧА\n"
            f"{'━' * 28}\n\n"
            f"💵 Ставка: {amount} монет\n\n"
            f"🎴 Ты: {hand_str(player_hand)}  = {player_val}\n"
            f"🎴 Дилер: {card_str(dealer_hand[0])}  🂠\n\n"
            f"Что делать?"
        )

        keyboard = [
            [KeyboardButton("🃏 Ещё"), KeyboardButton("✋ Хватит")],
            [KeyboardButton("Отмена")]
        ]

        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return BLACKJACK_PLAY_STATE

    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return BLACKJACK_BET_STATE


async def blackjack_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка хода блэкджека: Ещё / Хватит"""
    text = update.message.text
    user_id = update.effective_user.id

    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    amount = context.user_data.get('bj_amount', 0)
    deck = context.user_data.get('bj_deck', [])
    player_hand = context.user_data.get('bj_player', [])
    dealer_hand = context.user_data.get('bj_dealer', [])

    user = db.get_user(user_id)
    user_balance = user[2]

    if "Ещё" in text:
        # Взять ещё карту
        player_hand.append(deck.pop())
        context.user_data['bj_player'] = player_hand
        context.user_data['bj_deck'] = deck
        player_val = hand_value(player_hand)

        if player_val > 21:
            # Перебор!
            db.update_balance(user_id, -amount)
            db.record_game(user_id, 'blackjack', amount, False, 0, 'bj_bust')
            new_balance = user_balance - amount

            result_text = (
                f"🃏 БЛЭКДЖЕК\n"
                f"{'━' * 28}\n\n"
                f"🎴 Ты: {hand_str(player_hand)}  = {player_val}\n"
                f"🎴 Дилер: {card_str(dealer_hand[0])}  🂠\n\n"
                f"💥 ПЕРЕБОР! {player_val} > 21\n"
                f"😢 Проигрыш: -{amount} монет\n"
                f"💰 Баланс: {new_balance} монет"
            )
            if new_balance == 0:
                result_text += "\n\n💀 Баланс пуст! Проверьте /balance для восстановления"
            result_text += await check_consolation_bonus(user_id)

            await update.message.reply_text(result_text, reply_markup=get_main_keyboard())
            return -1

        if player_val == 21:
            # Ровно 21 — автоматически стоп, переход к раундy дилера
            return await _blackjack_dealer_turn(update, context)

        # Продолжаем — показать обновлённую руку
        info = (
            f"🃏 БЛЭКДЖЕК\n"
            f"{'━' * 28}\n\n"
            f"🎴 Ты: {hand_str(player_hand)}  = {player_val}\n"
            f"🎴 Дилер: {card_str(dealer_hand[0])}  🂠\n\n"
            f"Что делать?"
        )

        keyboard = [
            [KeyboardButton("🃏 Ещё"), KeyboardButton("✋ Хватит")],
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            info,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return BLACKJACK_PLAY_STATE

    elif "Хватит" in text:
        return await _blackjack_dealer_turn(update, context)
    else:
        await update.message.reply_text("❌ Нажмите кнопку: 🃏 Ещё или ✋ Хватит")
        return BLACKJACK_PLAY_STATE


async def _blackjack_dealer_turn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Дилер берёт карты, определение победителя"""
    user_id = update.effective_user.id
    amount = context.user_data.get('bj_amount', 0)
    deck = context.user_data.get('bj_deck', [])
    player_hand = context.user_data.get('bj_player', [])
    dealer_hand = context.user_data.get('bj_dealer', [])

    user = db.get_user(user_id)
    user_balance = user[2]

    player_val = hand_value(player_hand)

    # Дилер берёт до 17
    while hand_value(dealer_hand) < 17 and deck:
        dealer_hand.append(deck.pop())

    dealer_val = hand_value(dealer_hand)

    result_text = (
        f"🃏 БЛЭКДЖЕК — ИТОГ\n"
        f"{'━' * 28}\n\n"
        f"🎴 Ты: {hand_str(player_hand)}  = {player_val}\n"
        f"🎴 Дилер: {hand_str(dealer_hand)}  = {dealer_val}\n\n"
    )

    if dealer_val > 21:
        # Дилер перебрал
        winnings = amount * 2
        net = amount
        db.update_balance(user_id, net)
        db.record_game(user_id, 'blackjack', amount, True, winnings, 'bj_dealer_bust')
        new_balance = user_balance + net
        result_text += (
            f"💥 Дилер перебрал! ({dealer_val} > 21)\n"
            f"🎉 ПОБЕДА! +{winnings} монет (x2)!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    elif player_val > dealer_val:
        winnings = amount * 2
        net = amount
        db.update_balance(user_id, net)
        detail = 'bj_win_20' if player_val == 20 else ('bj_win_21' if player_val == 21 else 'bj_win')
        db.record_game(user_id, 'blackjack', amount, True, winnings, detail)
        new_balance = user_balance + net
        result_text += (
            f"🎉 ПОБЕДА! {player_val} > {dealer_val}\n"
            f"+{winnings} монет (x2)!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    elif player_val == dealer_val:
        db.record_game(user_id, 'blackjack', amount, False, amount, 'bj_draw')
        result_text += (
            f"🤝 НИЧЬЯ! {player_val} = {dealer_val}\n"
            f"Ставка возвращена.\n"
            f"💰 Баланс: {user_balance} монет"
        )
    else:
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'blackjack', amount, False, 0, 'bj_loss')
        new_balance = user_balance - amount
        result_text += (
            f"😢 Проигрыш... {player_val} < {dealer_val}\n"
            f"-{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        if new_balance == 0:
            result_text += "\n\n💀 Баланс пуст! Проверьте /balance для восстановления"
        result_text += await check_consolation_bonus(user_id)

    await update.message.reply_text(result_text, reply_markup=get_main_keyboard())
    return -1


# ============================================================
# СЛОТЫ (Slot Machine)
# ============================================================

SLOT_SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '🔔', '⭐', '💎', '7️⃣']

# Множители для 3 одинаковых символа
SLOT_PAYOUTS = {
    '7️⃣': 20,   # Джекпот!
    '💎': 15,
    '⭐': 10,
    '🔔': 7,
    '🍇': 5,
    '🍊': 4,
    '🍋': 3,
    '🍒': 2,
}


async def start_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать игру в слоты"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Сначала нажмите /start", reply_markup=get_main_keyboard())
        return -1
    
    user_balance = user[2]
    
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\n"
            f"Ваш баланс: {user_balance} монет\n"
            f"Минимальная ставка: {MIN_BET} монет",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    text = (
        f"🍀 СЛОТЫ\n"
        f"{'━' * 28}\n\n"
        f"🎰 Крути барабаны и выигрывай!\n\n"
        f"📋 Множители (3 совпадения):\n"
        f"  7️⃣7️⃣7️⃣  — x20 (ДЖЕКПОТ!)\n"
        f"  💎💎💎 — x15\n"
        f"  ⭐⭐⭐ — x10\n"
        f"  🔔🔔🔔 — x7\n"
        f"  🍇🍇🍇 — x5\n"
        f"  🍊🍊🍊 — x4\n"
        f"  🍋🍋🍋 — x3\n"
        f"  🍒🍒🍒 — x2\n"
        f"  2 совпадения — x1.5\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"Введите сумму ставки (мин. {MIN_BET}):"
    )
    
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SLOTS_BET_STATE


async def slots_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки слотов и крутка барабанов с анимацией"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() in ['отмена', '/cancel']:
        await update.message.reply_text("❌ Игра отменена", reply_markup=get_main_keyboard())
        return -1
    
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return SLOTS_BET_STATE
    
    user = db.get_user(user_id)
    user_balance = user[2]
    
    if amount < MIN_BET:
        await update.message.reply_text(f"❌ Минимум {MIN_BET} монет!")
        return SLOTS_BET_STATE
    if amount > user_balance:
        await update.message.reply_text(f"❌ Недостаточно! Баланс: {user_balance}")
        return SLOTS_BET_STATE
    
    # Финальные символы
    reel1 = random.choice(SLOT_SYMBOLS)
    reel2 = random.choice(SLOT_SYMBOLS)
    reel3 = random.choice(SLOT_SYMBOLS)
    
    # === АНИМАЦИЯ: одно сообщение, редактируем его ===
    
    # Фаза 1: Все крутятся
    spin_msg = await update.message.reply_text(
        f"🍀 СЛОТЫ — Ставка: {amount} 💰\n"
        f"{'━' * 28}\n\n"
        f"╔═══════════════════╗\n"
        f"║   ❓  |  ❓  |  ❓   ║\n"
        f"╚═══════════════════╝\n\n"
        f"⏳ Барабаны крутятся..."
    )
    await asyncio.sleep(0.8)
    
    # Фаза 2: Первый барабан остановился
    await spin_msg.edit_text(
        f"🍀 СЛОТЫ — Ставка: {amount} 💰\n"
        f"{'━' * 28}\n\n"
        f"╔═══════════════════╗\n"
        f"║   {reel1}  |  ❓  |  ❓   ║\n"
        f"╚═══════════════════╝\n\n"
        f"⏳ Крутятся 2 и 3..."
    )
    await asyncio.sleep(0.8)
    
    # Фаза 3: Второй барабан остановился
    await spin_msg.edit_text(
        f"🍀 СЛОТЫ — Ставка: {amount} 💰\n"
        f"{'━' * 28}\n\n"
        f"╔═══════════════════╗\n"
        f"║   {reel1}  |  {reel2}  |  ❓   ║\n"
        f"╚═══════════════════╝\n\n"
        f"⏳ Последний барабан..."
    )
    await asyncio.sleep(1.0)
    
    # Фаза 4: Финальный результат
    # Определение выигрыша
    if reel1 == reel2 == reel3:
        multiplier = SLOT_PAYOUTS.get(reel1, 2)
        winnings = int(amount * multiplier)
        net = winnings - amount
        db.update_balance(user_id, net)
        # Теги: jackpot_777, triple_diamond, triple_star, triple_bell, triple_grape, triple_orange, triple_lemon, triple_cherry
        if reel1 == '7️⃣':
            slot_detail = 'jackpot_777'
        elif reel1 == '💎':
            slot_detail = 'triple_diamond'
        elif reel1 == '⭐':
            slot_detail = 'triple_star'
        elif reel1 == '🔔':
            slot_detail = 'triple_bell'
        else:
            slot_detail = 'triple_win'
        db.record_game(user_id, 'slots', amount, True, winnings, slot_detail)
        new_balance = user_balance + net
        
        if reel1 == '7️⃣':
            result_line = "🎆🎆🎆 ДЖЕКПОТ!!! 🎆🎆🎆"
        elif multiplier >= 10:
            result_line = "🔥🔥 МЕГА ВЫИГРЫШ! 🔥🔥"
        else:
            result_line = "🎉 ВЫИГРЫШ!"
        
        outcome = (
            f"{result_line}\n"
            f"3x {reel1} = множитель x{multiplier}\n"
            f"+{winnings} монет!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    elif reel1 == reel2 or reel2 == reel3 or reel1 == reel3:
        pair = reel1 if (reel1 == reel2 or reel1 == reel3) else reel2
        multiplier = 1.5
        winnings = int(amount * multiplier)
        net = winnings - amount
        db.update_balance(user_id, net)
        db.record_game(user_id, 'slots', amount, True, winnings, 'slots_pair')
        new_balance = user_balance + net
        outcome = (
            f"✨ Пара {pair}{pair}!\n"
            f"Множитель x{multiplier}\n"
            f"+{winnings} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
    else:
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'slots', amount, False, 0, 'slots_loss')
        new_balance = user_balance - amount
        outcome = (
            f"😢 Нет совпадений...\n"
            f"-{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        if new_balance == 0:
            outcome += "\n\n💀 Баланс пуст! 🎁 Бонусы → 💊 Банкрот"
        consolation = await check_consolation_bonus(user_id)
        if consolation:
            outcome += consolation
    
    await spin_msg.edit_text(
        f"🍀 СЛОТЫ — РЕЗУЛЬТАТ\n"
        f"{'━' * 28}\n\n"
        f"╔═══════════════════╗\n"
        f"║   {reel1}  |  {reel2}  |  {reel3}   ║\n"
        f"╚═══════════════════╝\n\n"
        f"{outcome}"
    )
    
    # Отправляем отдельное сообщение с клавиатурой (edit_text не поддерживает reply_markup для обычных сообщений с ReplyKeyboard)
    await update.message.reply_text("🎰 Крутить ещё? Выберите действие:", reply_markup=get_main_keyboard())
    return -1


# ============================================================
# КРАШ (Crash Game)
# ============================================================

async def start_crash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры Краш — выбери множитель и молись!"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1

    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1

    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🚀 КРАШ\n"
        f"{'═' * 28}\n\n"
        f"Ракета взлетает... но может взорваться в любой момент!\n"
        f"Выбери целевой множитель — чем выше, тем больше выигрыш,\n"
        f"но и шанс краша выше!\n\n"
        f"🟢 x1.5 — шанс 65%\n"
        f"🟡 x2.0 — шанс 49%\n"
        f"🟠 x3.0 — шанс 33%\n"
        f"🔴 x5.0 — шанс 20%\n"
        f"💀 x10.0 — шанс 10%\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CRASH_BET_STATE


async def crash_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки в Краш — выбор множителя"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    user_id = update.effective_user.id
    user = db.get_user(user_id)

    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return CRASH_BET_STATE

        user_balance = user[2]
        if amount > user_balance:
            await update.message.reply_text("❌ Недостаточно монет!")
            return CRASH_BET_STATE

        context.user_data['crash_amount'] = amount

        keyboard = [
            [KeyboardButton("🟢 x1.5 (65%)"), KeyboardButton("🟡 x2.0 (49%)")],
            [KeyboardButton("🟠 x3.0 (33%)"), KeyboardButton("🔴 x5.0 (20%)")],
            [KeyboardButton("💀 x10.0 (10%)")],
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            f"🚀 Ставка: {amount} монет\n\n"
            f"Выбери целевой множитель:\n"
            f"🟢 x1.5 — шанс 65% (безопасно)\n"
            f"🟡 x2.0 — шанс 49%\n"
            f"🟠 x3.0 — шанс 33% (рискованно)\n"
            f"🔴 x5.0 — шанс 20% (опасно)\n"
            f"💀 x10.0 — шанс 10% (экстрим!)",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return CRASH_CHOICE_STATE

    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return CRASH_BET_STATE


async def crash_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора множителя и розыгрыш краша"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('crash_amount', 0)

    user = db.get_user(user_id)
    if not user or user[2] < amount:
        await update.message.reply_text("❌ Недостаточно монет!", reply_markup=get_main_keyboard())
        return -1

    user_balance = user[2]

    # Определить целевой множитель
    if "x1.5" in text:
        target = 1.5
    elif "x2.0" in text:
        target = 2.0
    elif "x3.0" in text:
        target = 3.0
    elif "x5.0" in text:
        target = 5.0
    elif "x10.0" in text:
        target = 10.0
    else:
        await update.message.reply_text("❌ Выберите множитель кнопкой!")
        return CRASH_CHOICE_STATE

    # Генерация точки краша (экспоненциальное распределение)
    r = random.random()
    if r < 0.01:
        crash_point = 1.0
    else:
        crash_point = round(0.99 / (1 - r), 2)
        crash_point = min(crash_point, 50.0)

    # Анимация взлёта
    crash_msg = await update.message.reply_text(
        f"🚀 КРАШ — ВЗЛЁТ!\n"
        f"{'━' * 28}\n\n"
        f"📈 x1.00...\n"
        f"🎯 Цель: x{target:.1f}\n"
        f"🎰 Ставка: {amount} монет"
    )

    # Показываем рост множителя шагами
    current = 1.0
    steps = []
    limit = min(crash_point, target)
    while current < limit:
        step_inc = random.uniform(0.15, 0.45)
        current = round(current + step_inc, 2)
        if current >= limit:
            break
        steps.append(current)

    display_steps = steps[-4:] if len(steps) > 4 else steps
    for step_val in display_steps:
        await asyncio.sleep(0.7)
        filled = int(step_val / target * 10)
        bar = "█" * filled + "░" * (10 - filled)
        await crash_msg.edit_text(
            f"🚀 КРАШ — ВЗЛЁТ!\n"
            f"{'━' * 28}\n\n"
            f"📈 x{step_val:.2f} 🔼\n"
            f"[{bar}]\n"
            f"🎯 Цель: x{target:.1f}\n"
            f"🎰 Ставка: {amount} монет"
        )

    await asyncio.sleep(0.8)

    # Результат
    if crash_point >= target:
        # ВЫИГРАЛ — ракета долетела!
        winnings = int(amount * target)
        net = winnings - amount
        db.update_balance(user_id, net)
        detail = 'crash_mega' if target >= 10 else ('crash_big' if target >= 5 else 'crash_win')
        db.record_game(user_id, 'crash', amount, True, winnings, detail)
        new_balance = user_balance + net

        if target >= 10:
            line = "🌟🌟 МЕГА МНОЖИТЕЛЬ x10! 🌟🌟"
        elif target >= 5:
            line = "🔥 ОТЛИЧНЫЙ МНОЖИТЕЛЬ x5! 🔥"
        elif target >= 3:
            line = "✨ Хороший множитель!"
        else:
            line = "📈 Неплохо!"

        result = (
            f"{line}\n"
            f"🚀 Ракета добралась до x{target:.1f}!\n"
            f"💥 Краш был бы на x{crash_point:.2f}\n\n"
            f"🎉 +{winnings} монет (x{target:.1f})!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    else:
        # ПРОИГРАЛ — ракета разбилась раньше!
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'crash', amount, False, 0, 'crash_fail')
        new_balance = user_balance - amount

        result = (
            f"💥 КРАШ НА x{crash_point:.2f}!\n"
            f"🎯 Цель была x{target:.1f} — не долетела!\n\n"
            f"😢 -{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        if new_balance == 0:
            result += "\n\n💀 Баланс пуст!"
        result += await check_consolation_bonus(user_id)

    await crash_msg.edit_text(
        f"🚀 КРАШ — РЕЗУЛЬТАТ\n"
        f"{'━' * 28}\n\n"
        f"{result}"
    )

    await update.message.reply_text("🚀 Ещё раз? Выберите действие:", reply_markup=get_main_keyboard())
    return -1


# ============================================================
# БОУЛИНГ (Bowling)
# ============================================================

async def start_bowling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры в боулинг — брось шар!"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1

    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1

    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🎳 БОУЛИНГ\n"
        f"{'═' * 28}\n\n"
        f"Брось шар и сбей кегли! 🎳\n"
        f"Анимация броска через Telegram!\n\n"
        f"🎳 Страйк (все кегли) = x5\n"
        f"✨ Спэр (почти все) = x3\n"
        f"👍 Неплохо (часть кеглей) = x1.5\n"
        f"😢 Мимо = проигрыш\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return BOWLING_BET_STATE


async def bowling_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки в боулинг — бросок через Telegram dice"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    user_id = update.effective_user.id
    user = db.get_user(user_id)

    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return BOWLING_BET_STATE

        user_balance = user[2]
        if amount > user_balance:
            await update.message.reply_text("❌ Недостаточно монет!")
            return BOWLING_BET_STATE

        # Бросок через Telegram Dice API — анимация боулинга!
        await update.message.reply_text(
            f"🎳 Ставка: {amount} монет\n🎳 Бросок!"
        )
        dice_msg = await update.message.reply_dice(emoji="🎳")
        value = dice_msg.dice.value  # 1-6

        # Ждём завершения анимации
        await asyncio.sleep(3.5)

        # Результаты по значению dice
        if value == 6:
            # СТРАЙК!
            multiplier = 5
            winnings = amount * multiplier
            net = winnings - amount
            db.update_balance(user_id, net)
            db.record_game(user_id, 'bowling', amount, True, winnings, 'bowling_strike')
            new_balance = user_balance + net
            outcome = (
                f"🎳✨ СТРАЙК!!! Все кегли сбиты! ✨🎳\n\n"
                f"🎉 +{winnings} монет (x{multiplier})!\n"
                f"💰 Баланс: {new_balance} монет"
            )
        elif value == 5:
            # Спэр
            multiplier = 3
            winnings = amount * multiplier
            net = winnings - amount
            db.update_balance(user_id, net)
            db.record_game(user_id, 'bowling', amount, True, winnings, 'bowling_spare')
            new_balance = user_balance + net
            outcome = (
                f"✨ СПЭР! Почти все кегли!\n\n"
                f"🎉 +{winnings} монет (x{multiplier})!\n"
                f"💰 Баланс: {new_balance} монет"
            )
        elif value == 4:
            # Неплохо
            multiplier = 1.5
            winnings = int(amount * multiplier)
            net = winnings - amount
            db.update_balance(user_id, net)
            db.record_game(user_id, 'bowling', amount, True, winnings, 'bowling_good')
            new_balance = user_balance + net
            outcome = (
                f"👍 Неплохо! Часть кеглей сбита\n\n"
                f"✨ +{winnings} монет (x{multiplier})!\n"
                f"💰 Баланс: {new_balance} монет"
            )
        else:
            # Мимо (1-3)
            db.update_balance(user_id, -amount)
            db.record_game(user_id, 'bowling', amount, False, 0, 'bowling_miss')
            new_balance = user_balance - amount
            outcome = (
                f"😢 Мимо! Мало кеглей сбито\n\n"
                f"-{amount} монет\n"
                f"💰 Баланс: {new_balance} монет"
            )
            if new_balance == 0:
                outcome += "\n\n💀 Баланс пуст!"
            consolation = await check_consolation_bonus(user_id)
            if consolation:
                outcome += consolation

        await update.message.reply_text(
            f"🎳 БОУЛИНГ — РЕЗУЛЬТАТ\n"
            f"{'━' * 28}\n\n"
            f"{outcome}",
            reply_markup=get_main_keyboard()
        )
        return -1

    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return BOWLING_BET_STATE


# ============================================================
# ДАРТС (Darts)
# ============================================================

async def start_darts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры в дартс — брось дротик!"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1

    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1

    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🎯 ДАРТС\n"
        f"{'═' * 28}\n\n"
        f"Брось дротик в мишень! 🎯\n"
        f"Выбери зону и попробуй попасть!\n"
        f"Анимация броска через Telegram!\n\n"
        f"🎯 Яблочко (центр) — x10 (шанс ~17%)\n"
        f"🔴 Красная зона — x3 (шанс ~33%)\n"
        f"⚪ Белая зона — x1.5 (шанс ~50%)\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return DARTS_BET_STATE


async def darts_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки и выбора зоны в дартс"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    user_id = update.effective_user.id
    user = db.get_user(user_id)

    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return DARTS_BET_STATE

        user_balance = user[2]
        if amount > user_balance:
            await update.message.reply_text("❌ Недостаточно монет!")
            return DARTS_BET_STATE

        context.user_data['darts_amount'] = amount

        keyboard = [
            [KeyboardButton("🎯 Яблочко (x10)"), KeyboardButton("🔴 Красная (x3)")],
            [KeyboardButton("⚪ Белая (x1.5)")],
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            f"🎯 Ставка: {amount} монет\n\n"
            f"Выберите зону для броска:\n"
            f"🎯 Яблочко — x10 (шанс попасть: 5%)\n"
            f"🔴 Красная — x3 (шанс попасть: 25%)\n"
            f"⚪ Белая — x1.5 (шанс попасть: 40%)",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return DARTS_CHOICE_STATE

    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return DARTS_BET_STATE


async def darts_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора зоны и бросок дротика через Telegram dice"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1

    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('darts_amount', 0)

    user = db.get_user(user_id)
    if not user or user[2] < amount:
        await update.message.reply_text("❌ Недостаточно монет!", reply_markup=get_main_keyboard())
        return -1

    user_balance = user[2]

    # Определить зону
    if "Яблочко" in text:
        target = "bullseye"
        target_name = "🎯 Яблочко"
        multiplier = 10
    elif "Красная" in text:
        target = "red"
        target_name = "🔴 Красная зона"
        multiplier = 3
    elif "Белая" in text:
        target = "white"
        target_name = "⚪ Белая зона"
        multiplier = 1.5
    else:
        await update.message.reply_text("❌ Выберите зону кнопкой!")
        return DARTS_CHOICE_STATE

    # Бросок через Telegram Dice API — анимация дартса!
    dice_msg = await update.message.reply_dice(emoji="🎯")
    value = dice_msg.dice.value  # 1-6

    # Ждём завершения анимации
    await asyncio.sleep(3.5)

    # Определяем попадание на основе значения dice и выбранной зоны
    # value 6 = центр (любая зона попадание)
    # value 5 = близко (красная и белая попадание)
    # value 4 = средне (только белая попадание)
    # value 1-3 = мимо для всех
    if target == "bullseye":
        hit = value == 6
    elif target == "red":
        hit = value >= 5
    else:  # white
        hit = value >= 4

    if hit:
        winnings = int(amount * multiplier)
        net = winnings - amount
        db.update_balance(user_id, net)
        detail = f'darts_{target}_hit'
        db.record_game(user_id, 'darts', amount, True, winnings, detail)
        new_balance = user_balance + net

        if target == "bullseye":
            line = "🎯✨ ЯБЛОЧКО!!! ПРЯМО В ЦЕНТР! ✨🎯"
        elif target == "red":
            line = "🔴 Отличный бросок! Красная зона!"
        else:
            line = "⚪ Попадание в белую зону!"

        result = (
            f"{line}\n\n"
            f"🎉 +{winnings} монет (x{multiplier})!\n"
            f"💰 Баланс: {new_balance} монет"
        )
    else:
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'darts', amount, False, 0, f'darts_{target}_miss')
        new_balance = user_balance - amount
        result = (
            f"💨 Мимо! Дротик пролетел мимо {target_name}\n\n"
            f"😢 -{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        if new_balance == 0:
            result += "\n\n💀 Баланс пуст!"
        consolation = await check_consolation_bonus(user_id)
        if consolation:
            result += consolation

    await update.message.reply_text(
        f"🎯 ДАРТС — РЕЗУЛЬТАТ\n"
        f"{'━' * 28}\n\n"
        f"{result}",
        reply_markup=get_main_keyboard()
    )
    return -1


# ==================== МИННОЕ ПОЛЕ ====================

async def start_mines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры Минное поле"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1
    
    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"💣 МИННОЕ ПОЛЕ\n"
        f"{'═' * 28}\n\n"
        f"Перед тобой поле 5x5 (25 клеток).\n"
        f"Внутри спрятаны 5 мин! 💣\n\n"
        f"Открывай клетки одну за одной:\n"
        f"✅ Безопасная — множитель растёт!\n"
        f"💣 Мина — теряешь всё!\n"
        f"💰 Забрать — забираешь выигрыш!\n\n"
        f"Множители:\n"
        f"1 клетка: x1.2 | 3 клетки: x1.8\n"
        f"5 клеток: x3.0 | 8 клеток: x6.0\n"
        f"10 клеток: x15 | 15+: x50+\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return MINES_BET_STATE


async def mines_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки для минного поля"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return MINES_BET_STATE
        if amount > user[2]:
            await update.message.reply_text("❌ Недостаточно монет!")
            return MINES_BET_STATE
        
        # Создать поле: 25 клеток, 5 мин
        field = [0] * 25  # 0 = безопасно
        mine_positions = random.sample(range(25), 5)
        for pos in mine_positions:
            field[pos] = 1  # 1 = мина
        
        context.user_data['mines_amount'] = amount
        context.user_data['mines_field'] = field
        context.user_data['mines_opened'] = []
        context.user_data['mines_alive'] = True
        
        # Списать ставку
        db.update_balance(user_id, -amount)
        
        return await show_mines_field(update, context, amount)
    
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return MINES_BET_STATE


async def show_mines_field(update, context, amount):
    """Показать текущее поле мин"""
    opened = context.user_data.get('mines_opened', [])
    
    # Множитель
    multiplier = get_mines_multiplier(len(opened))
    current_win = int(amount * multiplier)
    
    # Рисуем поле 5x5
    field_display = ""
    for row in range(5):
        for col in range(5):
            idx = row * 5 + col
            cell_num = idx + 1
            if idx in opened:
                field_display += "✅ "
            else:
                field_display += f"[{cell_num:2d}]"
        field_display += "\n"
    
    # Кнопки: числа доступных клеток + забрать
    available = [i for i in range(25) if i not in opened]
    buttons = []
    row_btns = []
    for i, idx in enumerate(available):
        row_btns.append(KeyboardButton(f"🔲 {idx + 1}"))
        if len(row_btns) == 5:
            buttons.append(row_btns)
            row_btns = []
    if row_btns:
        buttons.append(row_btns)
    
    if len(opened) > 0:
        buttons.append([KeyboardButton("💰 Забрать")])
    buttons.append([KeyboardButton("Отмена")])
    
    text = (
        f"💣 МИННОЕ ПОЛЕ\n"
        f"{'━' * 28}\n\n"
        f"{field_display}\n"
        f"💰 Ставка: {amount} монет\n"
        f"✅ Открыто: {len(opened)}/20 безопасных\n"
        f"📈 Множитель: x{multiplier:.1f}\n"
        f"💵 Текущий выигрыш: {current_win} монет\n\n"
        f"Выберите клетку или заберите выигрыш:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return MINES_PLAY_STATE


def get_mines_multiplier(opened_count):
    """Множитель за количество открытых клеток"""
    multipliers = {
        0: 1.0, 1: 1.2, 2: 1.5, 3: 1.8, 4: 2.2,
        5: 3.0, 6: 3.5, 7: 4.2, 8: 6.0, 9: 7.5,
        10: 15.0, 11: 18.0, 12: 22.0, 13: 28.0, 14: 35.0,
        15: 50.0, 16: 70.0, 17: 100.0, 18: 150.0, 19: 250.0,
        20: 500.0
    }
    return multipliers.get(opened_count, 1.0)


async def mines_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора клетки в минном поле"""
    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('mines_amount', 0)
    field = context.user_data.get('mines_field', [])
    opened = context.user_data.get('mines_opened', [])
    
    if text == "Отмена":
        # Потеря ставки
        db.record_game(user_id, 'mines', amount, False, 0, 'mines_cancel')
        await update.message.reply_text(
            f"❌ Вы вышли из игры!\n💸 Ставка {amount} монет потеряна.",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    if text == "💰 Забрать":
        multiplier = get_mines_multiplier(len(opened))
        winnings = int(amount * multiplier)
        db.update_balance(user_id, winnings)
        db.record_game(user_id, 'mines', amount, True, winnings, f'mines_cashout_{len(opened)}')
        user = db.get_user(user_id)
        
        await update.message.reply_text(
            f"💰 МИННОЕ ПОЛЕ — ЗАБРАЛ!\n"
            f"{'━' * 28}\n\n"
            f"✅ Открыто клеток: {len(opened)}\n"
            f"📈 Множитель: x{multiplier:.1f}\n"
            f"🎉 Выигрыш: {winnings} монет!\n"
            f"💰 Баланс: {user[2]} монет",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    # Клетка
    try:
        if text.startswith("🔲 "):
            cell_num = int(text.replace("🔲 ", ""))
        else:
            cell_num = int(text)
        
        idx = cell_num - 1
        if idx < 0 or idx >= 25 or idx in opened:
            await update.message.reply_text("❌ Выберите доступную клетку!")
            return MINES_PLAY_STATE
        
        if field[idx] == 1:
            # МИНА! 💣
            db.record_game(user_id, 'mines', amount, False, 0, f'mines_boom_{len(opened)}')
            user = db.get_user(user_id)
            
            # Показать все мины
            field_display = ""
            for row in range(5):
                for col in range(5):
                    i = row * 5 + col
                    if i in opened:
                        field_display += "✅ "
                    elif i == idx:
                        field_display += "💥 "
                    elif field[i] == 1:
                        field_display += "💣 "
                    else:
                        field_display += "⬜ "
                field_display += "\n"
            
            result = (
                f"💣 МИННОЕ ПОЛЕ — ВЗРЫВ!\n"
                f"{'━' * 28}\n\n"
                f"{field_display}\n"
                f"💥 БУМ! Вы наступили на мину!\n"
                f"✅ Было открыто: {len(opened)} клеток\n"
                f"😢 -{amount} монет\n"
                f"💰 Баланс: {user[2]} монет"
            )
            
            if user[2] == 0:
                result += "\n\n💀 Баланс пуст!"
            consolation = await check_consolation_bonus(user_id)
            if consolation:
                result += consolation
            
            await update.message.reply_text(result, reply_markup=get_main_keyboard())
            return -1
        
        else:
            # Безопасная клетка
            opened.append(idx)
            context.user_data['mines_opened'] = opened
            
            if len(opened) >= 20:
                # Все безопасные клетки открыты!
                multiplier = get_mines_multiplier(20)
                winnings = int(amount * multiplier)
                db.update_balance(user_id, winnings)
                db.record_game(user_id, 'mines', amount, True, winnings, 'mines_perfect')
                user = db.get_user(user_id)
                
                await update.message.reply_text(
                    f"💣 МИННОЕ ПОЛЕ — ИДЕАЛЬНО! 🏆\n"
                    f"{'━' * 28}\n\n"
                    f"🌟 ВСЕ 20 КЛЕТОК ОТКРЫТЫ!\n"
                    f"📈 Множитель: x{multiplier:.1f}\n"
                    f"🎉 МЕГА-ВЫИГРЫШ: {winnings} монет!\n"
                    f"💰 Баланс: {user[2]} монет",
                    reply_markup=get_main_keyboard()
                )
                return -1
            
            return await show_mines_field(update, context, amount)
    
    except ValueError:
        await update.message.reply_text("❌ Выберите клетку кнопкой!")
        return MINES_PLAY_STATE


# ==================== КОЛЕСО ФОРТУНЫ ====================

async def start_wheel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры Колесо фортуны"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1
    
    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🎡 КОЛЕСО ФОРТУНЫ\n"
        f"{'═' * 28}\n\n"
        f"Крути колесо и испытай удачу! 🎡\n\n"
        f"Секторы колеса:\n"
        f"💀 x0 — потеря всего (10%)\n"
        f"😰 x0.5 — половина назад (15%)\n"
        f"😐 x1 — возврат ставки (20%)\n"
        f"😊 x1.5 — полтора (20%)\n"
        f"🤑 x2 — удвоение (15%)\n"
        f"🔥 x3 — утроение (10%)\n"
        f"💎 x5 — пятикратно (7%)\n"
        f"🏆 x10 — ДЖЕКПОТ! (3%)\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return WHEEL_BET_STATE


async def wheel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки и вращение колеса"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return WHEEL_BET_STATE
        if amount > user[2]:
            await update.message.reply_text("❌ Недостаточно монет!")
            return WHEEL_BET_STATE
        
        user_balance = user[2]
        
        # Анимация вращения
        spin_msg = await update.message.reply_text("🎡 Колесо крутится...")
        await asyncio.sleep(0.8)
        
        frames = ["🎡 ⬆️ . . . . . .", "🎡 . ⬆️ . . . . .", "🎡 . . ⬆️ . . . .",
                   "🎡 . . . ⬆️ . . .", "🎡 . . . . ⬆️ . .", "🎡 . . . . . ⬆️ ."]
        for frame in frames:
            try:
                await spin_msg.edit_text(frame)
                await asyncio.sleep(0.4)
            except Exception:
                pass
        
        # Определить сектор (взвешенный рандом)
        sectors = [
            (0, "💀 x0 — НИЧЕГО!", 10),
            (0.5, "😰 x0.5 — Половина", 15),
            (1, "😐 x1 — Возврат", 20),
            (1.5, "😊 x1.5 — Полтора!", 20),
            (2, "🤑 x2 — Удвоение!", 15),
            (3, "🔥 x3 — Утроение!", 10),
            (5, "💎 x5 — ПЯТЬ ИКСОВ!", 7),
            (10, "🏆 x10 — ДЖЕКПОТ!!!", 3),
        ]
        
        weights = [s[2] for s in sectors]
        chosen = random.choices(sectors, weights=weights, k=1)[0]
        multiplier, sector_name, _ = chosen
        
        winnings = int(amount * multiplier)
        net = winnings - amount
        
        db.update_balance(user_id, net)
        won = multiplier >= 1
        db.record_game(user_id, 'wheel', amount, won, winnings, f'wheel_x{multiplier}')
        new_balance = user_balance + net
        
        if multiplier == 0:
            result_line = f"💀 Колесо остановилось на НУЛЕ!\n😢 -{amount} монет"
        elif multiplier < 1:
            result_line = f"😰 Вернулась только половина...\n💸 -{amount - winnings} монет"
        elif multiplier == 1:
            result_line = f"😐 Ставка вернулась — ни туда, ни сюда\n📤 0 монет"
        else:
            result_line = f"🎉 {sector_name}\n💵 +{winnings} монет!"
        
        try:
            await spin_msg.edit_text(
                f"🎡 КОЛЕСО ФОРТУНЫ — РЕЗУЛЬТАТ\n"
                f"{'━' * 28}\n\n"
                f"🎯 Сектор: {sector_name}\n\n"
                f"{result_line}\n\n"
                f"💰 Баланс: {new_balance} монет"
            )
        except Exception:
            await update.message.reply_text(
                f"🎡 КОЛЕСО ФОРТУНЫ — РЕЗУЛЬТАТ\n"
                f"{'━' * 28}\n\n"
                f"🎯 Сектор: {sector_name}\n\n"
                f"{result_line}\n\n"
                f"💰 Баланс: {new_balance} монет"
            )
        
        if new_balance == 0:
            await update.message.reply_text("💀 Баланс пуст!", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("🎡 Крутить ещё?", reply_markup=get_main_keyboard())
        
        if not won:
            consolation = await check_consolation_bonus(user_id)
            if consolation:
                await update.message.reply_text(consolation)
        
        return -1
    
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return WHEEL_BET_STATE


# ==================== БОЛЬШЕ/МЕНЬШЕ ====================

async def start_highlow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры Больше/Меньше"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1
    
    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"📊 БОЛЬШЕ / МЕНЬШЕ\n"
        f"{'═' * 28}\n\n"
        f"Угадай, будет ли следующая карта\n"
        f"БОЛЬШЕ или МЕНЬШЕ текущей! 🃏\n\n"
        f"Каждый правильный ответ удваивает\n"
        f"ставку! Можно забрать в любой момент.\n\n"
        f"Карты: 2-14 (Валет=11, Дама=12,\n"
        f"Король=13, Туз=14)\n\n"
        f"При равенстве — проигрыш! ⚠️\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return HIGHLOW_BET_STATE


CARD_NAMES_HL = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
                 9: '9', 10: '10', 11: 'Валет', 12: 'Дама', 13: 'Король', 14: 'Туз'}
CARD_SUITS_HL = ['♠️', '♥️', '♦️', '♣️']


async def highlow_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки для Больше/Меньше"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return HIGHLOW_BET_STATE
        if amount > user[2]:
            await update.message.reply_text("❌ Недостаточно монет!")
            return HIGHLOW_BET_STATE
        
        # Списать ставку
        db.update_balance(user_id, -amount)
        
        # Первая карта
        current_card = random.randint(2, 14)
        suit = random.choice(CARD_SUITS_HL)
        
        context.user_data['hl_amount'] = amount
        context.user_data['hl_current'] = current_card
        context.user_data['hl_streak'] = 0
        context.user_data['hl_multiplier'] = 1.0
        
        return await show_highlow_card(update, context, current_card, suit, amount)
    
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return HIGHLOW_BET_STATE


async def show_highlow_card(update, context, card, suit, amount):
    """Показать текущую карту"""
    streak = context.user_data.get('hl_streak', 0)
    multiplier = context.user_data.get('hl_multiplier', 1.0)
    current_win = int(amount * multiplier)
    
    card_name = CARD_NAMES_HL.get(card, str(card))
    
    buttons = [
        [KeyboardButton("⬆️ Больше"), KeyboardButton("⬇️ Меньше")],
    ]
    if streak > 0:
        buttons.append([KeyboardButton("💰 Забрать")])
    buttons.append([KeyboardButton("Отмена")])
    
    await update.message.reply_text(
        f"📊 БОЛЬШЕ / МЕНЬШЕ\n"
        f"{'━' * 28}\n\n"
        f"🃏 Текущая карта: {suit} {card_name}\n\n"
        f"Следующая карта будет БОЛЬШЕ\n"
        f"или МЕНЬШЕ?\n\n"
        f"🔥 Серия: {streak} | x{multiplier:.1f}\n"
        f"💵 Выигрыш: {current_win} монет\n\n"
        f"Выберите:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return HIGHLOW_PLAY_STATE


async def highlow_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора в Больше/Меньше"""
    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('hl_amount', 0)
    current_card = context.user_data.get('hl_current', 7)
    streak = context.user_data.get('hl_streak', 0)
    multiplier = context.user_data.get('hl_multiplier', 1.0)
    
    if text == "Отмена":
        db.record_game(user_id, 'highlow', amount, False, 0, 'hl_cancel')
        await update.message.reply_text(
            f"❌ Вы вышли! Ставка {amount} монет потеряна.",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    if text == "💰 Забрать" and streak > 0:
        winnings = int(amount * multiplier)
        db.update_balance(user_id, winnings)
        db.record_game(user_id, 'highlow', amount, True, winnings, f'hl_cashout_{streak}')
        user = db.get_user(user_id)
        
        await update.message.reply_text(
            f"📊 БОЛЬШЕ/МЕНЬШЕ — ЗАБРАЛ!\n"
            f"{'━' * 28}\n\n"
            f"🔥 Серия: {streak} угадываний!\n"
            f"📈 Множитель: x{multiplier:.1f}\n"
            f"🎉 Выигрыш: {winnings} монет!\n"
            f"💰 Баланс: {user[2]} монет",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    if text not in ("⬆️ Больше", "⬇️ Меньше"):
        await update.message.reply_text("❌ Используйте кнопки!")
        return HIGHLOW_PLAY_STATE
    
    guess_higher = text == "⬆️ Больше"
    
    # Новая карта
    new_card = random.randint(2, 14)
    new_suit = random.choice(CARD_SUITS_HL)
    new_name = CARD_NAMES_HL.get(new_card, str(new_card))
    old_name = CARD_NAMES_HL.get(current_card, str(current_card))
    
    # Проверка
    if new_card == current_card:
        correct = False  # Ничья = проигрыш
    elif guess_higher:
        correct = new_card > current_card
    else:
        correct = new_card < current_card
    
    if correct:
        streak += 1
        multiplier = round(1.0 * (2 ** streak), 1)
        if multiplier > 100:
            multiplier = 100  # Капа
        
        context.user_data['hl_current'] = new_card
        context.user_data['hl_streak'] = streak
        context.user_data['hl_multiplier'] = multiplier
        
        await update.message.reply_text(
            f"✅ ПРАВИЛЬНО!\n\n"
            f"🃏 Была: {old_name} → Новая: {new_suit} {new_name}\n"
            f"🔥 Серия: {streak} | x{multiplier:.1f}!"
        )
        
        return await show_highlow_card(update, context, new_card, new_suit, amount)
    
    else:
        db.record_game(user_id, 'highlow', amount, False, 0, f'hl_lose_{streak}')
        user = db.get_user(user_id)
        new_balance = user[2]
        
        direction = "БОЛЬШЕ" if guess_higher else "МЕНЬШЕ"
        result = (
            f"📊 БОЛЬШЕ/МЕНЬШЕ — ПРОИГРЫШ!\n"
            f"{'━' * 28}\n\n"
            f"🃏 Была: {old_name} → Новая: {new_suit} {new_name}\n"
            f"❌ Вы сказали {direction}, но ошиблись!\n\n"
            f"🔥 Серия: {streak} угадываний\n"
            f"😢 -{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        
        if new_balance == 0:
            result += "\n\n💀 Баланс пуст!"
        consolation = await check_consolation_bonus(user_id)
        if consolation:
            result += consolation
        
        await update.message.reply_text(result, reply_markup=get_main_keyboard())
        return -1


# ==================== РУССКАЯ РУЛЕТКА ====================

async def start_russianr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало игры Русская рулетка"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return -1
    
    user_balance = user[2]
    if user_balance < MIN_BET:
        await update.message.reply_text(
            f"❌ Недостаточно монет!\nМинимум: {MIN_BET} | Баланс: {user_balance}",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        f"🔫 РУССКАЯ РУЛЕТКА\n"
        f"{'═' * 28}\n\n"
        f"В барабане 6 камер. Выбери сколько\n"
        f"пуль зарядить и нажми на курок! 🔫\n\n"
        f"Больше пуль = больше риск = больше\n"
        f"выигрыш!\n\n"
        f"🔹 1 пуля — x1.2 (шанс: 83%)\n"
        f"🔸 2 пули — x1.5 (шанс: 67%)\n"
        f"🟡 3 пули — x2.0 (шанс: 50%)\n"
        f"🟠 4 пули — x3.0 (шанс: 33%)\n"
        f"🔴 5 пуль — x6.0 (шанс: 17%)\n\n"
        f"💰 Баланс: {user_balance} монет\n"
        f"📝 Введите ставку (мин {MIN_BET}):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return RUSSIANR_BET_STATE


async def russianr_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ставки для русской рулетки"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    try:
        amount = int(update.message.text)
        if amount < MIN_BET:
            await update.message.reply_text(f"❌ Минимальная ставка: {MIN_BET}")
            return RUSSIANR_BET_STATE
        if amount > user[2]:
            await update.message.reply_text("❌ Недостаточно монет!")
            return RUSSIANR_BET_STATE
        
        context.user_data['rr_amount'] = amount
        
        keyboard = [
            [KeyboardButton("🔹 1 пуля (x1.2)"), KeyboardButton("🔸 2 пули (x1.5)")],
            [KeyboardButton("🟡 3 пули (x2.0)"), KeyboardButton("🟠 4 пули (x3.0)")],
            [KeyboardButton("🔴 5 пуль (x6.0)")],
            [KeyboardButton("Отмена")]
        ]
        await update.message.reply_text(
            f"🔫 Ставка: {amount} монет\n\n"
            f"Сколько пуль зарядить в барабан?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return RUSSIANR_CHOICE_STATE
    
    except ValueError:
        await update.message.reply_text("❌ Введите число!")
        return RUSSIANR_BET_STATE


async def russianr_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора пуль и выстрел"""
    text = update.message.text
    user_id = update.effective_user.id
    amount = context.user_data.get('rr_amount', 0)
    
    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    # Определить кол-во пуль
    bullets_map = {
        "1 пуля": (1, 1.2), "2 пули": (2, 1.5), "3 пули": (3, 2.0),
        "4 пули": (4, 3.0), "5 пуль": (5, 6.0)
    }
    
    chosen = None
    for key, val in bullets_map.items():
        if key in text:
            chosen = val
            break
    
    if not chosen:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return RUSSIANR_CHOICE_STATE
    
    bullets, multiplier = chosen
    user = db.get_user(user_id)
    if not user or user[2] < amount:
        await update.message.reply_text("❌ Недостаточно монет!", reply_markup=get_main_keyboard())
        return -1
    
    user_balance = user[2]
    
    # Анимация
    spin_msg = await update.message.reply_text("🔫 Заряжаем барабан...")
    await asyncio.sleep(1)
    try:
        await spin_msg.edit_text("🔫 *клик* Крутим барабан...")
        await asyncio.sleep(1)
        await spin_msg.edit_text("🔫 Барабан остановился...")
        await asyncio.sleep(0.8)
        await spin_msg.edit_text("🔫 Нажимаем на курок...")
        await asyncio.sleep(1.5)
    except Exception:
        pass
    
    # Выстрел
    chamber = random.randint(1, 6)
    hit = chamber <= bullets  # Пули в первых N камерах
    
    if hit:
        # Попался!
        db.update_balance(user_id, -amount)
        db.record_game(user_id, 'russianr', amount, False, 0, f'rr_dead_{bullets}')
        new_balance = user_balance - amount
        
        result = (
            f"🔫 РУССКАЯ РУЛЕТКА — ВЫСТРЕЛ!\n"
            f"{'━' * 28}\n\n"
            f"💥 БАБАХ!!! Пуля в камере!\n"
            f"⚰️ Камера #{chamber} из 6\n"
            f"🔴 Пуль в барабане: {bullets}\n\n"
            f"😵 -{amount} монет\n"
            f"💰 Баланс: {new_balance} монет"
        )
        
        if new_balance == 0:
            result += "\n\n💀 Баланс пуст!"
        consolation = await check_consolation_bonus(user_id)
        if consolation:
            result += consolation
    else:
        # Выжил!
        winnings = int(amount * multiplier)
        net = winnings - amount
        db.update_balance(user_id, net)
        db.record_game(user_id, 'russianr', amount, True, winnings, f'rr_alive_{bullets}')
        new_balance = user_balance + net
        
        result = (
            f"🔫 РУССКАЯ РУЛЕТКА — ЩЕЛЧОК!\n"
            f"{'━' * 28}\n\n"
            f"*клик* ... Пусто! Вы выжили! 😮‍💨\n"
            f"🟢 Камера #{chamber} — пустая!\n"
            f"🔴 Пуль было: {bullets} из 6\n\n"
            f"🎉 Выигрыш: +{winnings} монет (x{multiplier})\n"
            f"💰 Баланс: {new_balance} монет"
        )
    
    try:
        await spin_msg.edit_text(result)
    except Exception:
        await update.message.reply_text(result)
    
    await update.message.reply_text("🔫 Играть ещё?", reply_markup=get_main_keyboard())
    return -1


async def bankrupt_recovery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстановление для банкротов"""
    user_id = update.effective_user.id
    
    recovery, message = db.claim_bankrupt_recovery(user_id)
    
    if recovery:
        user = db.get_user(user_id)
        new_balance = user[2]
        await update.message.reply_text(
            f"💊 ВОССТАНОВЛЕНИЕ БАНКРОТА\n"
            f"{'═' * 28}\n\n"
            f"{message}\n"
            f"Получено: +{recovery} монет\n"
            f"💰 Новый баланс: {new_balance} монет\n\n"
            f"🍀 Удачи в следующей игре!",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(f"{message}", reply_markup=get_main_keyboard())


# ==================== ХОЗЯИН ====================

async def owner_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки хозяина"""
    user_id = update.effective_user.id
    
    # Проверить, является ли хозяином
    if db.is_owner(user_id):
        return await show_owner_menu(update, context)
    
    # Проверить, есть ли уже хозяин (другой)
    owner = db.get_owner()
    if owner is not None:
        await update.message.reply_text(
            "🔒 Режим хозяина уже занят другим пользователем!\n"
            "Эта функция одноразовая.",
            reply_markup=get_main_keyboard()
        )
        return -1
    
    # Запросить пароль
    keyboard = [[KeyboardButton("Отмена")]]
    await update.message.reply_text(
        "👑 РЕЖИМ ХОЗЯИНА\n"
        f"{'═' * 28}\n\n"
        "⚠️ Внимание! Этот режим одноразовый!\n"
        "Первый, кто введёт пароль, станет\n"
        "единственным хозяином бота.\n\n"
        "🔑 Введите пароль:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return OWNER_PASSWORD_STATE


async def check_owner_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка пароля хозяина"""
    text = update.message.text
    
    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    if text == OWNER_PASSWORD:
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        # Попытаться стать хозяином
        success = db.set_owner(user_id, username)
        if success:
            await update.message.reply_text(
                "👑 ВЫ СТАЛИ ХОЗЯИНОМ БОТА! 👑\n\n"
                "🔒 Режим заблокирован для всех остальных.\n"
                "Теперь только вы имеете доступ к этой функции."
            )
            return await show_owner_menu(update, context)
        else:
            await update.message.reply_text(
                "🔒 Режим хозяина уже занят!",
                reply_markup=get_main_keyboard()
            )
            return -1
    else:
        await update.message.reply_text(
            "❌ Неверный пароль! Попробуйте ещё раз или нажмите Отмена:"
        )
        return OWNER_PASSWORD_STATE


async def show_owner_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню хозяина"""
    keyboard = [
        [KeyboardButton("🔄 Сбросить ВСЕХ игроков")],
        [KeyboardButton("👤 Сбросить одного игрока")],
        [KeyboardButton("📊 Статистика бота")],
        [KeyboardButton("Назад в меню")]
    ]
    await update.message.reply_text(
        "👑 МЕНЮ ХОЗЯИНА\n"
        f"{'═' * 28}\n\n"
        "🔄 Сбросить ВСЕХ — обнулить статистику\n"
        "   всех игроков (баланс = 100, очки = 0)\n\n"
        "👤 Сбросить одного — обнулить конкретного\n"
        "   игрока по @тегу\n\n"
        "📊 Статистика — сводка по боту",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return OWNER_MENU_STATE


async def owner_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик меню хозяина"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "Назад в меню":
        await update.message.reply_text("👑 Меню хозяина закрыто", reply_markup=get_main_keyboard())
        return -1
    
    if not db.is_owner(user_id):
        await update.message.reply_text("❌ Вы не хозяин!", reply_markup=get_main_keyboard())
        return -1
    
    if text == "🔄 Сбросить ВСЕХ игроков":
        keyboard = [
            [KeyboardButton("✅ ДА, СБРОСИТЬ ВСЕХ")],
            [KeyboardButton("❌ Отмена")]
        ]
        await update.message.reply_text(
            "⚠️ ВНИМАНИЕ!\n\n"
            "Вы уверены, что хотите сбросить\n"
            "статистику ВСЕХ игроков?\n\n"
            "Это обнулит:\n"
            "• Балансы (сброс до 100)\n"
            "• Все победы и поражения\n"
            "• XP и уровни\n"
            "• Историю игр и ставок\n\n"
            "❗ Это действие НЕОБРАТИМО!",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data['owner_action'] = 'reset_all'
        return OWNER_RESET_USER_STATE
    
    elif text == "👤 Сбросить одного игрока":
        keyboard = [[KeyboardButton("Отмена")]]
        await update.message.reply_text(
            "👤 СБРОС ИГРОКА\n\n"
            "Введите @тег игрока (без @):\n"
            "Пример: username",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data['owner_action'] = 'reset_one'
        return OWNER_RESET_USER_STATE
    
    elif text == "📊 Статистика бота":
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        cursor.execute('SELECT COALESCE(SUM(balance), 0) FROM users')
        total_balance = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM game_results')
        total_games = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM game_results WHERE won = 1')
        total_wins = cursor.fetchone()[0]
        cursor.execute('SELECT COALESCE(AVG(level), 1) FROM users')
        avg_level = cursor.fetchone()[0]
        conn.close()
        
        win_rate = (total_wins / total_games * 100) if total_games > 0 else 0
        
        await update.message.reply_text(
            f"📊 СТАТИСТИКА БОТА\n"
            f"{'═' * 28}\n\n"
            f"👥 Игроков: {total_users}\n"
            f"💰 Общий баланс: {total_balance} монет\n"
            f"🎮 Всего игр: {total_games}\n"
            f"📈 Общий винрейт: {win_rate:.1f}%\n"
            f"⭐ Средний уровень: {avg_level:.1f}"
        )
        return OWNER_MENU_STATE
    
    else:
        await update.message.reply_text("❌ Используйте кнопки!")
        return OWNER_MENU_STATE


async def owner_reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения сброса"""
    text = update.message.text
    action = context.user_data.get('owner_action', '')
    
    if text in ("❌ Отмена", "Отмена"):
        return await show_owner_menu(update, context)
    
    if action == 'reset_all':
        if text == "✅ ДА, СБРОСИТЬ ВСЕХ":
            db.reset_all_stats()
            await update.message.reply_text(
                "🔄 ПОЛНЫЙ СБРОС ВЫПОЛНЕН!\n\n"
                "✅ Все игроки обнулены:\n"
                "• Балансы → 100 монет\n"
                "• Победы/поражения → 0\n"
                "• XP/уровни → 0/1\n"
                "• История очищена"
            )
            return await show_owner_menu(update, context)
        else:
            await update.message.reply_text("❌ Нажмите кнопку подтверждения!")
            return OWNER_RESET_USER_STATE
    
    elif action == 'reset_one':
        username = text.strip().lstrip('@')
        if not username:
            await update.message.reply_text("❌ Введите @тег!")
            return OWNER_RESET_USER_STATE
        
        success, message = db.reset_user_stats(username)
        if success:
            await update.message.reply_text(
                f"✅ {message}\n\n"
                f"Игрок @{username} обнулён:\n"
                f"• Баланс → 100 монет\n"
                f"• Статистика → 0\n"
                f"• История очищена"
            )
        else:
            await update.message.reply_text(f"❌ {message}")
        return await show_owner_menu(update, context)
    
    return await show_owner_menu(update, context)


async def admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки админа - проверить, авторизован ли уже"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # Проверить, если уже авторизован
    if db.is_admin(user_id):
        # Сразу показать админ-меню
        keyboard = [
            [KeyboardButton("➕ Создать событие")],
            [KeyboardButton("📋 Список событий")],
            [KeyboardButton("🏁 Закрыть событие")],
            [KeyboardButton("Назад в меню")]
        ]
        await update.message.reply_text(
            "✅ Добро пожаловать, админ!\n\n👨‍💼 АДМИН-МЕНЮ:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return 2  # Админ меню состояние
    
    # Если не авторизован - запросить пароль
    await update.message.reply_text(
        "🔐 Введите пароль администратора:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True)
    )
    return 1  # Следующее состояние

async def check_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка пароля админа"""
    password = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    if password == "Отмена":
        await update.message.reply_text("❌ Отменено")
        return -1  # Завершить диалог
    
    if password == ADMIN_PASSWORD:
        # ✅ Пароль правильный! Сохранить ID админа
        db.add_admin(user_id, username)
        
        # Показать админ-меню
        keyboard = [
            [KeyboardButton("➕ Создать событие")],
            [KeyboardButton("📋 Список событий")],
            [KeyboardButton("🏁 Закрыть событие")],
            [KeyboardButton("💸 Перевести деньги")],
            [KeyboardButton("Назад в меню")]
        ]
        await update.message.reply_text(
            "✅ Пароль верный! Вы добавлены в список администраторов.\n"
            "В следующий раз вам не нужно будет вводить пароль.\n\n"
            "👨‍💼 АДМИН-МЕНЮ:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return 2  # Админ меню состояние
    else:
        await update.message.reply_text(
            "❌ Неверный пароль!\n\nПопробуйте еще раз или напишите 'Отмена':"
        )
        return 1  # Остаемся в том же состоянии

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ меню обработчик"""
    text = update.message.text
    
    if text == "Назад в меню":
        await update.message.reply_text(
            "Вы вышли из админ-меню",
            reply_markup=get_main_keyboard()
        )
        return -1  # Завершить диалог
    
    elif text == "➕ Создать событие":
        await update.message.reply_text("📝 Введите название события:")
        return 3  # Состояние создания события
    
    elif text == "📋 Список событий":
        active_events = db.get_events('active')
        closed_events = db.get_events('closed')
        
        if not active_events and not closed_events:
            await update.message.reply_text("❌ События не найдены")
            return 2
        
        text = ""
        
        if active_events:
            text += "🟢 АКТИВНЫЕ СОБЫТИЯ:\n\n"
            for event in active_events:
                ev_id = event[0]
                ev_title = event[1]
                
                strengths = db.get_event_strengths(ev_id)
                participants = db.get_event_participants(ev_id)
                total_bets, total_pool, per_p = db.get_event_bet_stats(ev_id)
                
                text += f"📌 ID: {ev_id} | {ev_title}\n"
                
                if strengths:
                    total = sum(strengths.values())
                    for p in participants:
                        s = strengths.get(p, 1)
                        chance = s / total * 100
                        odds = total / s
                        bar = make_bar(chance)
                        bets_on_p = per_p.get(p, {}).get('count', 0)
                        text += f"   🥊 {p}: сила {s} — {bar} {chance:.1f}% (x{odds:.2f})"
                        if bets_on_p > 0:
                            text += f" [{bets_on_p} ст.]"
                        text += "\n"
                else:
                    text += f"   Участники: {', '.join(participants)}\n"
                
                if total_bets > 0:
                    text += f"   💰 Ставок: {total_bets} | Пул: {total_pool} монет\n"
                text += "\n"
        
        if closed_events:
            text += "🔴 ЗАКРЫТЫЕ (последние 5):\n\n"
            for event in closed_events[:5]:
                ev_id = event[0]
                ev_title = event[1]
                ev_winner = event[5]
                text += f"   ID: {ev_id} | {ev_title} — 🏆 {ev_winner or '?'}\n"
        
        await update.message.reply_text(text)
        return 2  # Вернуться к админ меню
    
    elif text == "🏁 Закрыть событие":
        events = db.get_events('active')
        if not events:
            await update.message.reply_text("❌ Активных событий нет")
            return 2
        
        text = "🎲 Выберите событие для закрытия:\n"
        text += "(Победитель будет выбран АВТОМАТИЧЕСКИ по силе)\n\n"
        for event in events:
            ev_id = event[0]
            ev_title = event[1]
            participants = db.get_event_participants(ev_id)
            strengths = db.get_event_strengths(ev_id)
            total_bets, total_pool, _ = db.get_event_bet_stats(ev_id)
            
            text += f"ID: {ev_id} - {ev_title}\n"
            if strengths:
                total = sum(strengths.values())
                for p in participants:
                    s = strengths.get(p, 1)
                    chance = s / total * 100
                    bar = make_bar(chance)
                    text += f"   🥊 {p}: {bar} {chance:.1f}%\n"
            else:
                text += f"   Участники: {', '.join(participants)} (равные шансы)\n"
            if total_bets > 0:
                text += f"   💰 Ставок: {total_bets} | Пул: {total_pool} монет\n"
            text += "\n"
        
        await update.message.reply_text(text + "Введите ID события:")
        return 5  # Состояние закрытия события
    
    elif text == "💸 Перевести деньги":
        await update.message.reply_text("💰 Введите сумму для перевода:")
        return 10  # TRANSFER_AMOUNT_STATE
    
    return 2

async def create_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить название события"""
    context.user_data['event_name'] = update.message.text
    await update.message.reply_text(
        "👥 Введите участников события через запятую 🎯\n"
        "(Например: Роналду, Месси)\n"
        "или для других событий: (Вариант1, Вариант2, Вариант3)"
    )
    return 15  # CREATE_EVENT_PARTICIPANTS_STATE — сразу к участникам

async def create_event_odds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить коэффициент события (устаревший, не используется в новом флоу)"""
    try:
        odds = float(update.message.text)
        context.user_data['event_odds'] = odds
        
        await update.message.reply_text(
            "👥 Введите участников события через запятую 🎯\n"
            "(Например: Роналду, Месси)\n"
            "или для других событий: (Вариант1, Вариант2, Вариант3)"
        )
        return 15  # CREATE_EVENT_PARTICIPANTS_STATE
        
    except ValueError:
        await update.message.reply_text("❌ Коэффициент должен быть числом (например: 1.5)")
        return 4

async def create_event_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить список участников и перейти к установке силы"""
    try:
        # Распарсить участников
        participants_text = update.message.text
        participants = [p.strip() for p in participants_text.split(',')]
        
        if len(participants) < 2:
            await update.message.reply_text(
                "❌ Должно быть минимум 2 участника!\n"
                "Введите их через запятую заново:"
            )
            return 15
        
        context.user_data['event_participants'] = participants
        
        # Попросить ввести силу для каждого участника
        text = "⚡ Установите силу каждого участника (от 1 до 10):\n\n"
        for i, p in enumerate(participants, 1):
            text += f"{i}. {p}\n"
        
        example = ", ".join(["5"] * len(participants))
        text += f"\nВведите силу через запятую в том же порядке\n(например: {example}):"
        
        await update.message.reply_text(text)
        return 16  # CREATE_EVENT_STRENGTH_STATE
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return 15


async def create_event_strengths(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить силу участников и создать событие"""
    try:
        strengths_text = update.message.text
        strengths_values = [int(s.strip()) for s in strengths_text.split(',')]
        participants = context.user_data['event_participants']
        
        if len(strengths_values) != len(participants):
            await update.message.reply_text(
                f"❌ Количество значений ({len(strengths_values)}) не совпадает "
                f"с количеством участников ({len(participants)})!\n"
                f"Введите заново:"
            )
            return 16
        
        for s in strengths_values:
            if s < 1 or s > 10:
                await update.message.reply_text(
                    "❌ Сила должна быть от 1 до 10!\nВведите заново:"
                )
                return 16
        
        strengths = dict(zip(participants, strengths_values))
        total = sum(strengths_values)
        
        event_name = context.user_data['event_name']
        event_id = db.create_event(event_name, "", 0, participants, strengths)
        
        # Показать событие с коэффициентами
        text = f"✅ Событие создано!\n"
        text += f"ID: {event_id}\n"
        text += f"Название: {event_name}\n\n"
        text += "⚡ Участники и шансы:\n"
        for p, s in strengths.items():
            odds = total / s
            win_chance = s / total * 100
            bar = make_bar(win_chance)
            text += f"  🥊 {p} — сила: {s}\n"
            text += f"     {bar} {win_chance:.1f}% (x{odds:.2f})\n"
        
        keyboard = [
            [KeyboardButton("➕ Создать событие")],
            [KeyboardButton("📋 Список событий")],
            [KeyboardButton("🏁 Закрыть событие")],
            [KeyboardButton("Назад в меню")]
        ]
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return 2  # Вернуться к админ меню
        
    except ValueError:
        await update.message.reply_text(
            "❌ Введите числа через запятую (например: 5, 8):"
        )
        return 16

async def close_event_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ID события и АВТОМАТИЧЕСКИ выбрать победителя рандомом по силе"""
    try:
        event_id = int(update.message.text)
        
        # Получить участников события
        participants = db.get_event_participants(event_id)
        
        if not participants:
            await update.message.reply_text(
                f"❌ События с ID {event_id} не найдено или нет участников"
            )
            return 5
        
        # Получить силу участников (если нет — равные шансы)
        strengths = db.get_event_strengths(event_id)
        
        if strengths:
            participant_names = list(strengths.keys())
            weights = list(strengths.values())
        else:
            # Нет силы — равные шансы для всех
            participant_names = participants
            weights = [1] * len(participants)
        
        # 🎲 Рандомный выбор с учётом силы
        winner = random.choices(participant_names, weights=weights, k=1)[0]
        
        total = sum(weights)
        winner_strength = weights[participant_names.index(winner)]
        winner_odds = total / winner_strength
        
        # Получить статистику ставок до закрытия
        total_bets, total_pool, per_p = db.get_event_bet_stats(event_id)
        
        # Закрыть событие
        db.close_event(event_id, winner)
        
        # Показать результат
        text = f"🏆 СОБЫТИЕ #{event_id} ЗАВЕРШЕНО!\n"
        text += f"{'═' * 28}\n\n"
        text += "📊 Шансы участников:\n"
        for p in participant_names:
            s = weights[participant_names.index(p)]
            p_odds = total / s
            p_chance = s / total * 100
            bar = make_bar(p_chance)
            marker = " ⬅ 🏆" if p == winner else ""
            text += f"  🥊 {p}\n"
            text += f"     {bar} {p_chance:.1f}% (x{p_odds:.2f}){marker}\n"
        
        text += f"\n🎉 Победитель: {winner}!\n"
        text += f"💎 Коэффициент выплаты: x{winner_odds:.2f}\n"
        
        if total_bets > 0:
            text += f"\n📈 Статистика:\n"
            text += f"   Всего ставок: {total_bets}\n"
            text += f"   Общий пул: {total_pool} монет\n"
            
            # Показать сколько выиграли / проиграли
            winners_count = per_p.get(winner, {}).get('count', 0)
            losers_count = total_bets - winners_count
            text += f"   Угадали: {winners_count} 🎯 | Не угадали: {losers_count} ❌\n"
        
        text += f"\n✅ Выигрыши выплачены!"
        
        keyboard = [
            [KeyboardButton("➕ Создать событие")],
            [KeyboardButton("📋 Список событий")],
            [KeyboardButton("🏁 Закрыть событие")],
            [KeyboardButton("Назад в меню")]
        ]
        
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return 2  # Вернуться в админ меню
        
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом")
        return 5

async def close_event_winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть событие и указать победителя"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Отменено")
        return -1
    
    winner = update.message.text.strip()
    event_id = context.user_data['close_event_id']
    
    # Получить участников события
    participants = db.get_event_participants(event_id)
    
    # Проверить, что победитель есть в списке (case-insensitive)
    valid_winner = None
    for participant in participants:
        if participant.lower() == winner.lower():
            valid_winner = participant
            break
    
    if not valid_winner:
        participants_str = ", ".join(participants)
        await update.message.reply_text(
            f"❌ Вы ввели неправильно!\n\n"
            f"Доступные варианты: {participants_str}\n\n"
            f"Введите имя победителя заново:"
        )
        return 6  # CLOSE_EVENT_WINNER_STATE
    
    db.close_event(event_id, valid_winner)
    
    keyboard = [
        [KeyboardButton("➕ Создать событие")],
        [KeyboardButton("📋 Список событий")],
        [KeyboardButton("🏁 Закрыть событие")],
        [KeyboardButton("Назад в меню")]
    ]
    
    await update.message.reply_text(
        f"✅ Событие {event_id} закрыто!\n"
        f"Победитель: {valid_winner}\n"
        f"Выигрыши выплачены победителям!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    return 2  # Вернуться в меню


async def show_all_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все текущие активные события (авто + админ)"""
    auto_events = db.get_events('active', is_auto=True)
    admin_events = db.get_events('active', is_auto=False)

    if not auto_events and not admin_events:
        await update.message.reply_text(
            "📋 Нет активных событий прямо сейчас.\n"
            "Подождите — новое авто-событие появится через несколько минут!",
            reply_markup=get_main_keyboard()
        )
        return

    text = "📋 ВСЕ АКТИВНЫЕ СОБЫТИЯ\n"
    text += f"{'═' * 30}\n\n"

    if auto_events:
        text += "🤖 СОБЫТИЯ БОТА:\n\n"
        for event in auto_events:
            ev_id = event[0]
            ev_title = event[1]
            strengths = db.get_event_strengths(ev_id)
            participants = db.get_event_participants(ev_id)
            total_bets, total_pool, per_p = db.get_event_bet_stats(ev_id)

            text += f"📌 ID: {ev_id} | {ev_title}\n"
            if strengths:
                total = sum(strengths.values())
                for p in participants:
                    s = strengths.get(p, 1)
                    chance = s / total * 100
                    odds = total / s
                    bar = make_bar(chance)
                    text += f"   🥊 {p}: {bar} {chance:.1f}% (x{odds:.2f})\n"
            if total_bets > 0:
                text += f"   💰 Ставок: {total_bets} | Пул: {total_pool} монет\n"
            text += "\n"

    if admin_events:
        text += "👨‍💼 СОБЫТИЯ АДМИНА:\n\n"
        for event in admin_events:
            ev_id = event[0]
            ev_title = event[1]
            strengths = db.get_event_strengths(ev_id)
            participants = db.get_event_participants(ev_id)
            total_bets, total_pool, per_p = db.get_event_bet_stats(ev_id)

            text += f"📌 ID: {ev_id} | {ev_title}\n"
            if strengths:
                total = sum(strengths.values())
                for p in participants:
                    s = strengths.get(p, 1)
                    chance = s / total * 100
                    odds = total / s
                    bar = make_bar(chance)
                    text += f"   🥊 {p}: {bar} {chance:.1f}% (x{odds:.2f})\n"
            if total_bets > 0:
                text += f"   💰 Ставок: {total_bets} | Пул: {total_pool} монет\n"
            text += "\n"

    total_count = len(auto_events) + len(admin_events)
    text += f"📊 Всего активных: {total_count}\n"
    text += "💡 Чтобы поставить — нажмите 🎲 Ставки"

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def show_last_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последний результат ставки пользователя"""
    user_id = update.effective_user.id

    last_bet = db.get_user_last_completed_bet(user_id)

    if not last_bet:
        await update.message.reply_text(
            "📭 У вас пока нет завершённых ставок.\n"
            "Сделайте ставку через 🎲 Ставки!",
            reply_markup=get_main_keyboard()
        )
        return

    import json
    bet_id, title, amount, status, my_choice, winner, created_at, strengths_json, event_id = last_bet
    strengths = json.loads(strengths_json) if strengths_json else {}

    if status == 'won':
        if strengths and winner in strengths:
            total = sum(strengths.values())
            odds = total / strengths[winner]
            winnings = int(amount * odds)
        else:
            winnings = int(amount * 1.5)

        text = (
            f"🏅 ПОСЛЕДНИЙ РЕЗУЛЬТАТ\n"
            f"{'═' * 30}\n\n"
            f"📌 Событие: {title}\n"
            f"🏆 Победитель: {winner}\n"
            f"🎯 Ваш выбор: {my_choice}\n"
            f"💵 Ставка: {amount} монет\n\n"
            f"✅ ВЫ ВЫИГРАЛИ! +{winnings} монет 🎉\n"
        )
    else:
        text = (
            f"🏅 ПОСЛЕДНИЙ РЕЗУЛЬТАТ\n"
            f"{'═' * 30}\n\n"
            f"📌 Событие: {title}\n"
            f"🏆 Победитель: {winner}\n"
            f"🎯 Ваш выбор: {my_choice}\n"
            f"💵 Ставка: {amount} монет\n\n"
            f"❌ Вы проиграли... -{amount} монет 😢\n"
        )

    # Показать шансы участников события
    if strengths:
        text += f"\n📊 Шансы были:\n"
        total = sum(strengths.values())
        for p, s in strengths.items():
            chance = s / total * 100
            bar = make_bar(chance)
            marker = " 🏆" if p == winner else ""
            my = " ⬅ ВЫ" if p == my_choice else ""
            text += f"   🥊 {p}: {bar} {chance:.1f}%{marker}{my}\n"

    await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать систему достижений пользователя"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        await update.message.reply_text("❌ Используйте /start для регистрации")
        return

    user_balance = user[2]
    total_wins = user[3]
    total_losses = user[4]
    total_bets_count = db.get_user_total_bets_count(user_id)
    streak, streak_type = db.get_user_streak(user_id)
    games_count = db.get_user_games_count(user_id)
    games_won = db.get_user_games_won_count(user_id)
    games_lost = db.get_user_games_lost_count(user_id)
    used_bankrupt = db.has_used_bankrupt(user_id)
    total_winnings = db.get_user_total_winnings(user_id)
    total_wagered = db.get_user_total_wagered(user_id)
    total_lost = db.get_user_total_lost(user_id)
    max_win = db.get_user_max_win(user_id)
    max_bet = db.get_user_max_bet(user_id)
    bets_won = db.get_user_bets_won_count(user_id)

    # Подсчёт по типам игр
    roulette_count = db.get_user_game_type_count(user_id, 'roulette')
    coinflip_count = db.get_user_game_type_count(user_id, 'coinflip')
    dice_count = db.get_user_game_type_count(user_id, 'dice')
    blackjack_count = db.get_user_game_type_count(user_id, 'blackjack')
    slots_count = db.get_user_game_type_count(user_id, 'slots')
    crash_count = db.get_user_game_type_count(user_id, 'crash')
    bowling_count = db.get_user_game_type_count(user_id, 'bowling')
    darts_count = db.get_user_game_type_count(user_id, 'darts')

    roulette_wins = db.get_user_game_type_wins(user_id, 'roulette')
    coinflip_wins = db.get_user_game_type_wins(user_id, 'coinflip')
    dice_wins = db.get_user_game_type_wins(user_id, 'dice')
    blackjack_wins = db.get_user_game_type_wins(user_id, 'blackjack')
    slots_wins = db.get_user_game_type_wins(user_id, 'slots')
    crash_wins = db.get_user_game_type_wins(user_id, 'crash')
    bowling_wins = db.get_user_game_type_wins(user_id, 'bowling')
    darts_wins = db.get_user_game_type_wins(user_id, 'darts')

    # Детальные теги из game_results.details
    jackpot_777 = db.count_game_details(user_id, 'jackpot_777')
    triple_diamond = db.count_game_details(user_id, 'triple_diamond')
    triple_star = db.count_game_details(user_id, 'triple_star')
    green_wins = db.count_game_details(user_id, 'green_win')
    dice_double_wins = db.count_game_details(user_id, 'dice_double_win')
    blackjack_21_count = db.count_game_details(user_id, 'blackjack_21')
    bj_dealer_bust = db.count_game_details(user_id, 'bj_dealer_bust')
    bj_bust_count = db.count_game_details(user_id, 'bj_bust')
    crash_mega = db.count_game_details(user_id, 'crash_mega')
    crash_instant = db.count_game_details(user_id, 'crash_instant')
    bowling_strike = db.count_game_details(user_id, 'bowling_strike')
    bowling_spare = db.count_game_details(user_id, 'bowling_spare')
    darts_bullseye = db.count_game_details(user_id, 'darts_bullseye_hit')

    # Все 8 мини-игр сыграны
    all_games_tried = all([roulette_count > 0, coinflip_count > 0, dice_count > 0,
                           blackjack_count > 0, slots_count > 0, crash_count > 0,
                           bowling_count > 0, darts_count > 0])
    # Все 8 мини-игр выиграны хотя бы раз
    all_games_won = all([roulette_wins > 0, coinflip_wins > 0, dice_wins > 0,
                         blackjack_wins > 0, slots_wins > 0, crash_wins > 0,
                         bowling_wins > 0, darts_wins > 0])

    total_all = total_wins + total_losses
    win_rate = (total_wins / total_all * 100) if total_all > 0 else 0
    loss_rate = (total_losses / total_all * 100) if total_all > 0 else 0

    # Серия в мини-играх
    game_streak, game_streak_type = db.get_user_game_streak(user_id)

    # Все мини-игры по 10+ побед
    master_all_games = all([roulette_wins >= 10, coinflip_wins >= 10, dice_wins >= 10,
                            blackjack_wins >= 10, slots_wins >= 10, crash_wins >= 10,
                            bowling_wins >= 10, darts_wins >= 10])

    # ═══ ДОСТИЖЕНИЯ ═══
    achievements = [
        # 📌 НАЧАЛО ПУТИ (13)
        ("🎯", "Новичок", "Сделай первую ставку", total_bets_count >= 1, "📌 Начало"),
        ("🎮", "Первая игра", "Сыграй мини-игру", games_count >= 1, "📌 Начало"),
        ("🪙", "Подбрось монетку", "Сыграй в монетку", coinflip_count >= 1, "📌 Начало"),
        ("🎰", "Крутись-вертись", "Сыграй в рулетку", roulette_count >= 1, "📌 Начало"),
        ("🎲", "Бросок кубиков", "Сыграй в кости", dice_count >= 1, "📌 Начало"),
        ("🃏", "Своя игра", "Сыграй в блэкджек", blackjack_count >= 1, "📌 Начало"),
        ("🍀", "Слотомания", "Сыграй в слоты", slots_count >= 1, "📌 Начало"),
        ("🚀", "На взлёт!", "Сыграй в краш", crash_count >= 1, "📌 Начало"),
        ("🎳", "Первый бросок", "Сыграй в боулинг", bowling_count >= 1, "📌 Начало"),
        ("🎯", "Метатель", "Сыграй в дартс", darts_count >= 1, "📌 Начало"),
        ("🧭", "Исследователь", "Попробуй все 8 игр", all_games_tried, "📌 Начало"),
        ("🏅", "Первая кровь", "Выиграй первую игру", games_won >= 1, "📌 Начало"),
        ("🎪", "Победить везде", "Выиграй в каждой из 8 игр", all_games_won, "📌 Начало"),

        # 🔥 СЕРИИ (8)
        ("🔥", "Горячая серия", "3 победы подряд в играх", game_streak >= 3 and game_streak_type == 'won', "🔥 Серии"),
        ("⚡", "Неудержимый", "5 побед подряд в играх", game_streak >= 5 and game_streak_type == 'won', "🔥 Серии"),
        ("💥", "Ураган", "7 побед подряд в играх", game_streak >= 7 and game_streak_type == 'won', "🔥 Серии"),
        ("🌋", "Вулкан", "10 побед подряд в играх", game_streak >= 10 and game_streak_type == 'won', "🔥 Серии"),
        ("☄️", "Метеорит", "15 побед подряд в играх", game_streak >= 15 and game_streak_type == 'won', "🔥 Серии"),
        ("❄️", "Невезучий", "3 поражения подряд", game_streak >= 3 and game_streak_type == 'lost', "🔥 Серии"),
        ("🥶", "Чёрная полоса", "5 поражений подряд", game_streak >= 5 and game_streak_type == 'lost', "🔥 Серии"),
        ("💀", "Рок", "10 поражений подряд", game_streak >= 10 and game_streak_type == 'lost', "🔥 Серии"),

        # 🏆 ПОБЕДЫ (7)
        ("📈", "Опытный", "10 побед", total_wins >= 10, "🏆 Победы"),
        ("🏆", "Чемпион", "25 побед", total_wins >= 25, "🏆 Победы"),
        ("👑", "Мастер", "50 побед", total_wins >= 50, "🏆 Победы"),
        ("🌟", "Легенда", "100 побед", total_wins >= 100, "🏆 Победы"),
        ("⭐", "Неостановимый", "200 побед", total_wins >= 200, "🏆 Победы"),
        ("🔱", "Полубог", "500 побед", total_wins >= 500, "🏆 Победы"),
        ("🌌", "Бог ставок", "1000 побед", total_wins >= 1000, "🏆 Победы"),

        # 🎖 АКТИВНОСТЬ (8)
        ("🎖", "Ветеран", "50 ставок", total_bets_count >= 50, "🎖 Активность"),
        ("📊", "Статистик", "100 ставок", total_bets_count >= 100, "🎖 Активность"),
        ("🏅", "Марафонец", "25 мини-игр", games_count >= 25, "🎖 Активность"),
        ("🎪", "Завсегдатай", "50 мини-игр", games_count >= 50, "🎖 Активность"),
        ("🤹", "Безумный игрок", "100 мини-игр", games_count >= 100, "🎖 Активность"),
        ("🧮", "Зависимый", "200 мини-игр", games_count >= 200, "🎖 Активность"),
        ("🏗", "Трудоголик", "500 мини-игр", games_count >= 500, "🎖 Активность"),
        ("♾️", "Бесконечность", "1000 мини-игр", games_count >= 1000, "🎖 Активность"),

        # 💎 БОГАТСТВО (8)
        ("💰", "Копилка", "250 монет", user_balance >= 250, "💎 Богатство"),
        ("💎", "Богач", "500 монет", user_balance >= 500, "💎 Богатство"),
        ("👑", "Магнат", "1000 монет", user_balance >= 1000, "💎 Богатство"),
        ("🏦", "Банкир", "2500 монет", user_balance >= 2500, "💎 Богатство"),
        ("🏰", "Империя", "5000 монет", user_balance >= 5000, "💎 Богатство"),
        ("🌍", "Олигарх", "10000 монет", user_balance >= 10000, "💎 Богатство"),
        ("🪐", "Космический барон", "25000 монет", user_balance >= 25000, "💎 Богатство"),
        ("🌌", "Владыка вселенной", "50000 монет", user_balance >= 50000, "💎 Богатство"),

        # 💸 ВЫИГРЫШИ (6)
        ("🤑", "Денежный поток", "Выиграть 500 суммарно", total_winnings >= 500, "💸 Выигрыши"),
        ("💸", "Поток золота", "Выиграть 2000", total_winnings >= 2000, "💸 Выигрыши"),
        ("🏧", "Монетный двор", "Выиграть 5000", total_winnings >= 5000, "💸 Выигрыши"),
        ("💹", "Финансовый гений", "Выиграть 10000", total_winnings >= 10000, "💸 Выигрыши"),
        ("🏛", "Казначейство", "Выиграть 25000", total_winnings >= 25000, "💸 Выигрыши"),
        ("🗽", "Уолл-стрит", "Выиграть 50000", total_winnings >= 50000, "💸 Выигрыши"),

        # 🎯 РЕКОРДЫ (6)
        ("🎯", "Удачный бросок", "100+ за раз", max_win >= 100, "🎯 Рекорды"),
        ("🐟", "Крупная рыба", "500+ за раз", max_win >= 500, "🎯 Рекорды"),
        ("🦈", "Хайроллер", "1000+ за раз", max_win >= 1000, "🎯 Рекорды"),
        ("🐋", "Кит", "2500+ за раз", max_win >= 2500, "🎯 Рекорды"),
        ("💫", "Суперджекпот", "5000+ за раз", max_win >= 5000, "🎯 Рекорды"),
        ("🌠", "Невозможное", "10000+ за раз", max_win >= 10000, "🎯 Рекорды"),

        # 🍀 СЛОТЫ СПЕЦИАЛЬНЫЕ (10)
        ("7️⃣", "ДЖЕКПОТ!", "Выбить 7️⃣7️⃣7️⃣ в слотах", jackpot_777 >= 1, "🍀 Слоты"),
        ("7️⃣", "Дважды удачлив", "Джекпот 777 два раза", jackpot_777 >= 2, "🍀 Слоты"),
        ("7️⃣", "Король казино", "Джекпот 777 пять раз", jackpot_777 >= 5, "🍀 Слоты"),
        ("💎", "Бриллиантовый", "Выбить 💎💎💎", triple_diamond >= 1, "🍀 Слоты"),
        ("⭐", "Звёздный час", "Выбить ⭐⭐⭐", triple_star >= 1, "🍀 Слоты"),
        ("🍀", "Слот-мастер", "25 побед в слотах", slots_wins >= 25, "🍀 Слоты"),
        ("🍀", "Слот-маньяк", "50 игр в слоты", slots_count >= 50, "🍀 Слоты"),
        ("🍀", "Однорукий бандит", "100 игр в слоты", slots_count >= 100, "🍀 Слоты"),
        ("🍀", "Слот-бог", "50 побед в слотах", slots_wins >= 50, "🍀 Слоты"),
        ("🍀", "Слот-легенда", "100 побед в слотах", slots_wins >= 100, "🍀 Слоты"),

        # 🎰 РУЛЕТКА СПЕЦИАЛЬНЫЕ (8)
        ("🟢", "Зелёная удача", "Выиграть на зелёном", green_wins >= 1, "🎰 Рулетка"),
        ("🟢", "Зелёный гуру", "Зелёное 3 раза", green_wins >= 3, "🎰 Рулетка"),
        ("🟢", "Хозяин зеро", "Зелёное 5 раз", green_wins >= 5, "🎰 Рулетка"),
        ("🟢", "Мистер Грин", "Зелёное 10 раз", green_wins >= 10, "🎰 Рулетка"),
        ("🎰", "Рулетка-про", "10 побед", roulette_wins >= 10, "🎰 Рулетка"),
        ("🎰", "Крупье", "25 побед", roulette_wins >= 25, "🎰 Рулетка"),
        ("🎰", "Рулетка-маньяк", "50 игр", roulette_count >= 50, "🎰 Рулетка"),
        ("🎰", "Казино Рояль", "100 побед", roulette_wins >= 100, "🎰 Рулетка"),

        # 🃏 БЛЭКДЖЕК СПЕЦИАЛЬНЫЕ (9)
        ("🃏", "Блэкджек!", "Собрать 21 с 2 карт", blackjack_21_count >= 1, "🃏 Блэкджек"),
        ("🃏", "Двойной блэкджек", "Блэкджек 3 раза", blackjack_21_count >= 3, "🃏 Блэкджек"),
        ("🃏", "Мастер 21", "Блэкджек 10 раз", blackjack_21_count >= 10, "🃏 Блэкджек"),
        ("💥", "Дилер лопнул", "Дилер перебрал", bj_dealer_bust >= 1, "🃏 Блэкджек"),
        ("💥", "Ломатель дилеров", "Дилер перебрал 10 раз", bj_dealer_bust >= 10, "🃏 Блэкджек"),
        ("😵", "Перебор!", "Перебрать самому", bj_bust_count >= 1, "🃏 Блэкджек"),
        ("🃏", "Картёжник", "10 побед", blackjack_wins >= 10, "🃏 Блэкджек"),
        ("🃏", "Шулер", "25 игр", blackjack_count >= 25, "🃏 Блэкджек"),
        ("🃏", "Король стола", "50 побед", blackjack_wins >= 50, "🃏 Блэкджек"),

        # 🎲 КОСТИ СПЕЦИАЛЬНЫЕ (6)
        ("🎲", "Дубль!", "Выиграть с дублем (x3)", dice_double_wins >= 1, "🎲 Кости"),
        ("🎲", "Дубль-мастер", "5 побед с дублем", dice_double_wins >= 5, "🎲 Кости"),
        ("🎲", "Дубль-маньяк", "10 побед с дублем", dice_double_wins >= 10, "🎲 Кости"),
        ("🎲", "Костяной барон", "10 побед в костях", dice_wins >= 10, "🎲 Кости"),
        ("🎲", "Кости-маньяк", "50 игр в кости", dice_count >= 50, "🎲 Кости"),
        ("🎲", "Бог кубиков", "50 побед в костях", dice_wins >= 50, "🎲 Кости"),

        # 🪙 МОНЕТКА СПЕЦИАЛЬНЫЕ (5)
        ("🪙", "Монетный мастер", "10 побед", coinflip_wins >= 10, "🪙 Монетка"),
        ("🪙", "Монетка-маньяк", "50 игр", coinflip_count >= 50, "🪙 Монетка"),
        ("🪙", "Орёл или решка", "25 побед", coinflip_wins >= 25, "🪙 Монетка"),
        ("🪙", "Монетный гуру", "50 побед", coinflip_wins >= 50, "🪙 Монетка"),
        ("🪙", "Двусторонний", "100 игр", coinflip_count >= 100, "🪙 Монетка"),

        # 📊 СТАВКИ НА СОБЫТИЯ (5)
        ("🏇", "Букмекер", "5 побед в событиях", bets_won >= 5, "📊 События"),
        ("🏟", "Арена", "10 побед", bets_won >= 10, "📊 События"),
        ("🧠", "Аналитик", "25 побед", bets_won >= 25, "📊 События"),
        ("🔮", "Оракул", "50 побед", bets_won >= 50, "📊 События"),
        ("📋", "Ставочник", "50 ставок всего", total_bets_count >= 50, "📊 События"),

        # � КРАШ (6)
        ("🚀", "Выжил", "Побеждай в краше", crash_wins >= 1, "🚀 Краш"),
        ("🚀", "Пилот", "10 побед в краше", crash_wins >= 10, "🚀 Краш"),
        ("🚀", "Космонавт", "25 побед в краше", crash_wins >= 25, "🚀 Краш"),
        ("💥", "Краш на старте", "Мгновенный краш", crash_instant >= 1, "🚀 Краш"),
        ("🌟", "Мега-множитель", "Получить x10+ в краше", crash_mega >= 1, "🚀 Краш"),
        ("🌟", "Краш-бог", "Получить x10+ три раза", crash_mega >= 3, "🚀 Краш"),

        # 🎳 БОУЛИНГ (6)
        ("🎳", "Кеглебой", "Побеждай в боулинге", bowling_wins >= 1, "🎳 Боулинг"),
        ("🎳", "Страйк!", "Сбей все 10 кеглей", bowling_strike >= 1, "🎳 Боулинг"),
        ("🎳", "Страйк-мастер", "5 страйков", bowling_strike >= 5, "🎳 Боулинг"),
        ("🎳", "Спэр-машина", "10 спэров", bowling_spare >= 10, "🎳 Боулинг"),
        ("🎳", "Боулинг-маньяк", "50 игр в боулинг", bowling_count >= 50, "🎳 Боулинг"),
        ("🎳", "Король дорожки", "50 побед", bowling_wins >= 50, "🎳 Боулинг"),

        # 🎯 ДАРТС (6)
        ("🎯", "Стрелок", "Побеждай в дартсе", darts_wins >= 1, "🎯 Дартс"),
        ("🎯", "Яблочко!", "Попади в центр мишени", darts_bullseye >= 1, "🎯 Дартс"),
        ("🎯", "Снайпер", "3 попадания в яблочко", darts_bullseye >= 3, "🎯 Дартс"),
        ("🎯", "Робин Гуд", "10 попаданий в яблочко", darts_bullseye >= 10, "🎯 Дартс"),
        ("🎯", "Дартс-маньяк", "50 игр в дартс", darts_count >= 50, "🎯 Дартс"),
        ("🎯", "Мастер мишени", "25 побед в дартсе", darts_wins >= 25, "🎯 Дартс"),

        # �💀 ОСОБЫЕ (12)
        ("💀", "Феникс", "Банкрот: баланс = 0 → 🎁 Бонусы → 💊 Банкрот", used_bankrupt, "💀 Особые"),
        ("🧊", "Хладнокровие", "Winrate > 60%", win_rate > 60 and total_all >= 10, "💀 Особые"),
        ("🔥", "Машина побед", "Winrate > 70%", win_rate > 70 and total_all >= 20, "💀 Особые"),
        ("🎱", "Всё на зеро", "Проставить 1000+", total_wagered >= 1000, "💀 Особые"),
        ("💣", "Ва-банк мастер", "Проставить 5000+", total_wagered >= 5000, "💀 Особые"),
        ("🚀", "Ракета", "Проставить 10000+", total_wagered >= 10000, "💀 Особые"),
        ("⚰️", "Проигрыш 1000+", "Проиграть 1000+ монет", total_lost >= 1000, "💀 Особые"),
        ("🕳", "Бездна", "Проиграть 5000+ монет", total_lost >= 5000, "💀 Особые"),
        ("💵", "Крупная ставка", "Поставить 100+ за раз", max_bet >= 100, "💀 Особые"),
        ("💴", "Ставка на всё", "Поставить 500+ за раз", max_bet >= 500, "💀 Особые"),
        ("🎓", "Мультимастер", "10+ побед в каждой игре", master_all_games, "💀 Особые"),
        ("🏆", "Коллекционер", "Открыть 50 достижений", False, "💀 Особые"),  # placeholder
    ]

    # Подсчёт для Коллекционера (рекурсия без самого себя)
    unlocked_without_collector = sum(1 for _, _, _, done, _ in achievements if done and _ != "Коллекционер")
    # Обновить Коллекционера
    for i, (e, n, d, done, c) in enumerate(achievements):
        if n == "Коллекционер":
            achievements[i] = (e, n, d, unlocked_without_collector >= 50, c)
            break

    unlocked = sum(1 for _, _, _, done, _ in achievements if done)
    total = len(achievements)

    # Прогресс-бар
    progress = unlocked / total * 100
    progress_bar = make_bar(progress, 15)

    # Группировка по категориям (сохраняя порядок)
    categories = {}
    cat_order = []
    for emoji, name, desc, done, cat in achievements:
        if cat not in categories:
            categories[cat] = []
            cat_order.append(cat)
        categories[cat].append((emoji, name, desc, done))

    # Разбиваем на сообщения (Telegram лимит 4096 символов)
    header = f"🎖 ДОСТИЖЕНИЯ ({unlocked}/{total})\n"
    header += f"{'═' * 32}\n"
    header += f"{progress_bar} {progress:.0f}%\n"

    messages = []
    current_msg = header + "\n"

    for cat_name in cat_order:
        items = categories[cat_name]
        cat_unlocked = sum(1 for _, _, _, d in items if d)
        cat_total = len(items)
        
        block = f"{cat_name} ({cat_unlocked}/{cat_total})\n"
        for emoji, name, desc, done in items:
            if done:
                block += f"  {emoji} {name} ✅ — {desc}\n"
            elif cat_name == "💀 Особые":
                block += f"  🔒 ???\n"
            else:
                block += f"  🔒 {name} — {desc}\n"
        block += "\n"

        # Если блок не влезает — отправляем текущее и начинаем новое
        if len(current_msg) + len(block) > 3900:
            messages.append(current_msg)
            current_msg = ""
        current_msg += block

    # Footer
    footer = f"{'═' * 32}\n"
    if unlocked == total:
        footer += "🌟 ВСЕ ДОСТИЖЕНИЯ ОТКРЫТЫ! Ты — легенда!"
    elif unlocked >= total * 0.75:
        footer += "💪 Почти все! Осталось чуть-чуть!"
    elif unlocked >= total * 0.5:
        footer += "🚀 Больше половины! Так держать!"
    elif unlocked >= total * 0.25:
        footer += "🌱 Хороший старт! Продолжай играть!"
    else:
        footer += f"🌱 Открыто {unlocked} из {total}. Играй и открывай!"
    current_msg += footer
    messages.append(current_msg)

    # Отправляем все сообщения
    for i, msg in enumerate(messages):
        if i == len(messages) - 1:
            await update.message.reply_text(msg, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # === Главное меню ===
    if text == "🎮 Мини-игры":
        await show_games_menu(update, context)
    elif text == "👤 Профиль":
        await show_profile_menu(update, context)
    elif text == "🎁 Бонусы":
        await show_bonuses_menu(update, context)
    elif text == "↩️ Назад":
        await update.message.reply_text("🏠 Главное меню:", reply_markup=get_main_keyboard())
    
    # === Профиль ===
    elif text == "💰 Баланс":
        await balance(update, context)
    elif text == "📊 История":
        await history(update, context)
    elif text == "🏆 Лидеры":
        await leaderboard(update, context)
    elif text == "🏅 Результат":
        await show_last_result(update, context)
    elif text == "🎖 Достижения":
        await show_achievements(update, context)
    
    # === Бонусы ===
    elif text == "🎁 Дневной бонус":
        await daily_bonus(update, context)
    elif text == "💊 Банкрот":
        await bankrupt_recovery(update, context)
    
    # === Прочее ===
    elif text == "❓ Помощь":
        await help_command(update, context)
    elif text == "📋 События":
        await show_all_events(update, context)
    
    # === Мини-игры (запускают ConversationHandler) ===
    elif text == "🎰 Рулетка":
        return await start_roulette(update, context)
    elif text == "🪙 Монетка":
        return await start_coinflip(update, context)
    elif text == "🎯 Кости":
        return await start_dice(update, context)
    elif text == "🃏 Блэкджек":
        return await start_blackjack(update, context)
    elif text == "🍀 Слоты":
        return await start_slots(update, context)
    elif text == "🚀 Краш":
        return await start_crash(update, context)
    elif text == "🎳 Боулинг":
        return await start_bowling(update, context)
    elif text == "🎯 Дартс":
        return await start_darts(update, context)
    elif text == "💣 Минное поле":
        return await start_mines(update, context)
    elif text == "🎡 Колесо":
        return await start_wheel(update, context)
    elif text == "📊 Больше/Меньше":
        return await start_highlow(update, context)
    elif text == "🔫 Русская рулетка":
        return await start_russianr(update, context)
    
    # === Ставки, Админ, Хозяин ===
    elif text == "👨‍💼 Админ":
        return await admin_button(update, context)
    elif text == "👑 Хозяин":
        return await owner_button(update, context)
    elif text == "🎲 Ставки":
        return await start_bet(update, context)

async def start_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало ставок — выбор типа: авто-события или события админа"""
    keyboard = [
        [KeyboardButton("🤖 События бота"), KeyboardButton("👨‍💼 События админа")],
        [KeyboardButton("Отмена")]
    ]
    await update.message.reply_text(
        "🎲 СТАВКИ\n\n"
        "Выберите тип событий:\n\n"
        "🤖 События бота — автоматические бои,\n"
        "создаются и завершаются каждые 5 минут\n\n"
        "👨‍💼 События админа — созданы\n"
        "администратором вручную",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return BET_TYPE_STATE


async def bet_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать выбор типа событий"""
    text = update.message.text
    
    if text == "Отмена":
        await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())
        return -1
    
    if "События бота" in text:
        is_auto = True
        label = "🤖 СОБЫТИЯ БОТА"
    elif "События админа" in text:
        is_auto = False
        label = "👨‍💼 СОБЫТИЯ АДМИНА"
    else:
        await update.message.reply_text("❌ Выберите кнопкой!")
        return BET_TYPE_STATE
    
    context.user_data['bet_is_auto'] = is_auto
    events = db.get_events('active', is_auto=is_auto)
    
    if not events:
        msg = "❌ Активных авто-событий нет. Подождите немного!" if is_auto else "❌ Админ ещё не создал события"
        await update.message.reply_text(msg, reply_markup=get_main_keyboard())
        return -1
    
    msg = f"🎲 {label}:\n\n"
    for event in events:
        ev_id = event[0]
        ev_title = event[1]
        
        strengths = db.get_event_strengths(ev_id)
        participant_list = db.get_event_participants(ev_id)
        total_bets, total_pool, per_p = db.get_event_bet_stats(ev_id)
        
        msg += f"📌 ID: {ev_id} | {ev_title}\n"
        
        if strengths:
            total = sum(strengths.values())
            for p in participant_list:
                s = strengths.get(p, 1)
                p_odds = total / s
                p_chance = s / total * 100
                bar = make_bar(p_chance)
                msg += f"   🥊 {p}: {bar} {p_chance:.1f}% (x{p_odds:.2f})\n"
        else:
            equal_chance = 100 / len(participant_list)
            for p in participant_list:
                bar = make_bar(equal_chance)
                msg += f"   🥊 {p}: {bar} {equal_chance:.1f}%\n"
        
        if total_bets > 0:
            msg += f"   💰 Ставок: {total_bets} | Пул: {total_pool} монет\n"
        msg += "\n"
    
    await update.message.reply_text(
        msg + "📝 Введите ID события, на которое хотите поставить:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True)
    )
    return BET_EVENT_ID_STATE

async def bet_ask_event_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ID события для ставки с проверкой дубликата"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Ставка отменена")
        return -1
    
    try:
        event_id = int(update.message.text)
        event = db.get_events('active')
        
        # Проверить, существует ли событие
        event_exists = False
        for ev in event:
            if ev[0] == event_id and ev[4] == 'active':
                event_exists = True
                break
        
        if not event_exists:
            await update.message.reply_text("❌ Событие не найдено или закрыто. Попробуйте еще раз:")
            return 7
        
        # Проверить, уже ставил ли на это событие
        user_id = update.effective_user.id
        if db.has_user_bet_on_event(user_id, event_id):
            await update.message.reply_text(
                "⚠️ Вы уже сделали ставку на это событие!\n"
                "Можно ставить только 1 раз на событие.\n\n"
                "Выберите другое событие или нажмите Отмена:"
            )
            return 7
        
        context.user_data['bet_event_id'] = event_id
        
        # Спросить сумму
        user = db.get_user(update.effective_user.id)
        balance = user[2] if user else 0
        
        await update.message.reply_text(
            f"💵 Введите сумму ставки:\n"
            f"(Минимум: {MIN_BET} монет, ваш баланс: {balance} монет)",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True)
        )
        return 8  # BET_AMOUNT_STATE
        
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом. Попробуйте еще раз:")
        return 7

async def bet_ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить сумму ставки и спросить результат"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Ставка отменена")
        return -1
    
    try:
        amount = int(update.message.text)
        user_id = update.effective_user.id
        event_id = context.user_data['bet_event_id']
        
        # Проверить баланс
        user = db.get_user(user_id)
        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return -1
        
        balance = user[2]
        
        # Валидация
        if amount < MIN_BET:
            await update.message.reply_text(
                f"❌ Минимальная ставка: {MIN_BET} монет\n\nПопробуйте еще раз:"
            )
            return 8
        
        if amount > balance:
            await update.message.reply_text(
                f"❌ Недостаточно монет!\n"
                f"У вас: {balance} монет\n\n"
                f"Попробуйте меньшую сумму:"
            )
            return 8
        
        context.user_data['bet_amount'] = amount
        
        # Получить участников события с коэффициентами
        participants = db.get_event_participants(event_id)
        strengths = db.get_event_strengths(event_id)
        
        text = "🎯 На кого вы ставите?\n\n"
        if strengths:
            total = sum(strengths.values())
            for p in participants:
                s = strengths.get(p, 1)
                p_odds = total / s
                p_chance = s / total * 100
                bar = make_bar(p_chance)
                text += f"🥊 {p}: {bar} {p_chance:.1f}% (x{p_odds:.2f})\n"
        else:
            for p in participants:
                text += f"🥊 {p}\n"
        
        text += "\nВыберите бойца кнопкой:"
        
        # Создать кнопки с именами бойцов (по 2 в ряд, для 5+ по 3)
        fighter_buttons = []
        per_row = 2 if len(participants) <= 4 else 3
        for i in range(0, len(participants), per_row):
            row = [KeyboardButton(f"🥊 {p}") for p in participants[i:i+per_row]]
            fighter_buttons.append(row)
        fighter_buttons.append([KeyboardButton("Отмена")])
        
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup(fighter_buttons, resize_keyboard=True)
        )
        return 9  # BET_RESULT_STATE
        
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом. Попробуйте еще раз:")
        return 8

async def bet_ask_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить результат и выполнить ставку"""
    if update.message.text == "Отмена":
        await update.message.reply_text("❌ Ставка отменена", reply_markup=get_main_keyboard())
        return -1
    
    # Убрать префикс 🥊 если пользователь нажал кнопку
    result = update.message.text.strip()
    if result.startswith("🥊 "):
        result = result[2:].strip()
    
    user_id = update.effective_user.id
    event_id = context.user_data['bet_event_id']
    amount = context.user_data['bet_amount']
    
    # Получить участников события
    participants = db.get_event_participants(event_id)
    
    # Проверить, что результат есть в списке участников (case-insensitive)
    valid_result = None
    for participant in participants:
        if participant.lower() == result.lower():
            valid_result = participant
            break
    
    if not valid_result:
        # Перепоказать кнопки
        fighter_buttons = []
        per_row = 2 if len(participants) <= 4 else 3
        for i in range(0, len(participants), per_row):
            row = [KeyboardButton(f"🥊 {p}") for p in participants[i:i+per_row]]
            fighter_buttons.append(row)
        fighter_buttons.append([KeyboardButton("Отмена")])
        
        await update.message.reply_text(
            f"❌ Неправильный выбор! Нажмите кнопку с именем бойца:",
            reply_markup=ReplyKeyboardMarkup(fighter_buttons, resize_keyboard=True)
        )
        return 9  # BET_RESULT_STATE
    
    # Проверить баланс еще раз
    user = db.get_user(user_id)
    if not user or user[2] < amount:
        await update.message.reply_text("❌ Недостаточно монет")
        return -1
    
    # Сделать ставку
    success = db.place_bet(user_id, event_id, amount, valid_result)
    
    if success:
        new_balance = user[2] - amount
        
        # Показать шанс пользователя
        strengths = db.get_event_strengths(event_id)
        chance_text = ""
        if strengths:
            total = sum(strengths.values())
            s = strengths.get(valid_result, 1)
            chance = s / total * 100
            odds = total / s
            chance_text = f"Шанс на победу: {chance:.1f}% (x{odds:.2f})\n"
        
        await update.message.reply_text(
            f"✅ Ставка принята!\n"
            f"Событие ID: {event_id}\n"
            f"Размер: {amount} монет\n"
            f"Ваш выбор: {valid_result}\n"
            f"{chance_text}"
            f"Новый баланс: {new_balance} монет\n\n"
            f"🍀 Удачи! Ждите объявления результатов!",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("❌ Ошибка при размещении ставки")
    
    return -1  # Завершить диалог

async def transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить сумму для перевода денег"""
    try:
        amount = int(update.message.text)
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0. Попробуйте еще раз:")
            return 10
        
        context.user_data['transfer_amount'] = amount
        await update.message.reply_text(
            f"👤 Введите @тег пользователя, которому отправить {amount} монет:\n"
            f"(Например: @username)"
        )
        return 11  # TRANSFER_USER_ID_STATE
        
    except ValueError:
        await update.message.reply_text("❌ Сумма должна быть числом. Попробуйте еще раз:")
        return 10

async def transfer_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить перевод денег по @тегу"""
    username_input = update.message.text.strip().lstrip('@')
    from_user_id = update.effective_user.id
    amount = context.user_data['transfer_amount']
    
    if not username_input:
        await update.message.reply_text("❌ Введите @тег пользователя:")
        return 11
    
    # Найти пользователя по username
    to_user = db.get_user_by_username(username_input)
    
    if not to_user:
        await update.message.reply_text(
            f"❌ Пользователь @{username_input} не найден в боте.\n"
            f"Он должен сначала написать /start в боте.\n\n"
            f"Попробуйте ещё раз:"
        )
        return 11
    
    to_user_id = to_user[0]
    
    if to_user_id == from_user_id:
        await update.message.reply_text("❌ Нельзя переводить самому себе! Введите другой @тег:")
        return 11
    
    success, message = db.transfer_money(from_user_id, to_user_id, amount)
    
    if success:
        to_username = to_user[1]
        await update.message.reply_text(
            f"✅ {message}\n"
            f"Отправлено: {amount} монет\n"
            f"Получателю: @{to_username}"
        )
    else:
        await update.message.reply_text(message)
    
    # Вернуться в админ-меню
    keyboard = [
        [KeyboardButton("➕ Создать событие")],
        [KeyboardButton("📋 Список событий")],
        [KeyboardButton("🏁 Закрыть событие")],
        [KeyboardButton("💸 Перевести деньги")],
        [KeyboardButton("Назад в меню")]
    ]
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return 2
