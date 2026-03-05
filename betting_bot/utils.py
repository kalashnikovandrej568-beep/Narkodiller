"""Вспомогательные функции для бота"""

def format_balance(balance):
    """Форматировать баланс с валютой"""
    return f"💰 {balance} монет"

def format_bet_info(bet):
    """Форматировать информацию о ставке"""
    bet_id, title, amount, status, result, created_at = bet
    
    status_emoji = {
        'pending': '⏳',
        'won': '✅',
        'lost': '❌'
    }.get(status, '❓')
    
    return f"{status_emoji} ID: {bet_id} | {title} | {amount} монет | {status}"

def format_leaderboard(leaderboard):
    """Форматировать таблицу лидеров"""
    text = "🏆 ТАБЛИЦА ЛИДЕРОВ 🏆\n\n"
    
    for idx, (user_id, username, balance, wins) in enumerate(leaderboard, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}. "
        text += f"{medal} @{username} - {balance} монет (побед: {wins})\n"
    
    return text

def format_user_stats(user):
    """Форматировать статистику пользователя"""
    user_id, username, balance, total_wins, total_losses, created_at = user
    
    total_bets = total_wins + total_losses
    win_rate = (total_wins / total_bets * 100) if total_bets > 0 else 0
    
    text = f"""
👤 Профиль: @{username}
💰 Баланс: {balance} монет
📊 Статистика:
  ✅ Побед: {total_wins}
  ❌ Проигрышей: {total_losses}
  📈 Всего ставок: {total_bets}
  🎯 Процент побед: {win_rate:.1f}%
    """
    
    return text.strip()

def validate_bet_amount(amount, balance, min_bet):
    """Валидировать сумму ставки"""
    if not isinstance(amount, int):
        return False, "Сумма должна быть числом"
    
    if amount < min_bet:
        return False, f"Минимальная ставка: {min_bet} монет"
    
    if amount > balance:
        return False, f"Недостаточно монет. Ваш баланс: {balance}"
    
    return True, "OK"

def get_keyboard_main():
    """Получить главную клавиатуру"""
    from telegram import ReplyKeyboardMarkup, KeyboardButton
    
    keyboard = [
        [KeyboardButton("💰 Баланс"), KeyboardButton("🎲 Ставки")],
        [KeyboardButton("📊 История"), KeyboardButton("🏆 Лидеры")],
        [KeyboardButton("❓ Помощь")]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
