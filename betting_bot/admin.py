"""Админ-функции для управления ботом"""

from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from config import ADMIN_IDS

db = Database()

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет доступа к админ-панели")
        return
    
    help_text = """
⚙️ АДМИН-ПАНЕЛЬ:

Команды:
/admin_create_event <название> <коэффициент> - создать событие
/admin_list_events - список событий
/admin_close_event <ID события> <победитель> - закрыть событие
/admin_get_stats <user_id> - статистика пользователя
/admin_set_balance <user_id> <сумма> - установить баланс

Примеры:
/admin_create_event "Матч А vs Б" 1.5
/admin_close_event 1 "command_a"
/admin_set_balance 123456789 500
    """.strip()
    
    await update.message.reply_text(help_text)

async def create_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать событие (админ)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /admin_create_event <название> <коэффициент>"
        )
        return
    
    title = ' '.join(context.args[:-1])
    try:
        odds = float(context.args[-1])
    except ValueError:
        await update.message.reply_text("❌ Коэффициент должен быть числом")
        return
    
    event_id = db.create_event(title, "Автоматически созданное событие", odds)
    await update.message.reply_text(
        f"✅ Событие создано!\n"
        f"ID: {event_id}\n"
        f"Название: {title}\n"
        f"Коэффициент: {odds}"
    )

async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список всех событий (админ)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    active_events = db.get_events('active')
    closed_events = db.get_events('closed')
    
    text = "📋 СОБЫТИЯ:\n\n"
    
    if active_events:
        text += "🟢 АКТИВНЫЕ:\n"
        for event_id, title, _, odds, _, _, _, _ in active_events:
            text += f"ID: {event_id} | {title} | коэф: {odds}\n"
    
    if closed_events:
        text += "\n🔴 ЗАКРЫТЫЕ:\n"
        for event_id, title, _, odds, _, winner, _, _ in closed_events:
            text += f"ID: {event_id} | {title} | победитель: {winner}\n"
    
    await update.message.reply_text(text)

async def close_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть событие (админ)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /admin_close_event <ID события> <победитель>"
        )
        return
    
    try:
        event_id = int(context.args[0])
        winner = ' '.join(context.args[1:])
    except ValueError:
        await update.message.reply_text("❌ ID события должен быть числом")
        return
    
    db.close_event(event_id, winner)
    await update.message.reply_text(
        f"✅ Событие {event_id} закрыто!\n"
        f"Победитель: {winner}"
    )

async def get_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить статистику пользователя (админ)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ Использование: /admin_get_stats <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом")
        return
    
    user = db.get_user(target_user_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    user_id, username, balance, wins, losses, created_at = user
    text = f"""
👤 Пользователь: @{username}
🆔 ID: {user_id}
💰 Баланс: {balance}
✅ Побед: {wins}
❌ Проигрышей: {losses}
📅 Зарегистрирован: {created_at}
    """.strip()
    
    await update.message.reply_text(text)

async def set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить баланс пользователю (админ)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /admin_set_balance <user_id> <новый_баланс>"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        new_balance = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ user_id и баланс должны быть числами")
        return
    
    user = db.get_user(target_user_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    
    current_balance = user[2]
    difference = new_balance - current_balance
    db.update_balance(target_user_id, difference)
    
    await update.message.reply_text(
        f"✅ Баланс обновлен!\n"
        f"Пользователь: @{user[1]}\n"
        f"Старый баланс: {current_balance}\n"
        f"Новый баланс: {new_balance}"
    )
