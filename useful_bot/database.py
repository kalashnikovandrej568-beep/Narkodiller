"""
База данных — заметки, списки покупок, напоминания
"""
import sqlite3
import logging
from datetime import datetime
from config import DB_PATH, MAX_NOTES, MAX_SHOPPING_ITEMS

logger = logging.getLogger(__name__)


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS shopping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            checked INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            remind_at TIMESTAMP NOT NULL,
            sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            commands_used INTEGER DEFAULT 0,
            first_use TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_use TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")


# ===== ЗАМЕТКИ =====
def add_note(user_id: int, text: str) -> bool:
    """Добавить заметку"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM notes WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    if count >= MAX_NOTES:
        conn.close()
        return False
    c.execute("INSERT INTO notes (user_id, text) VALUES (?, ?)", (user_id, text))
    conn.commit()
    conn.close()
    return True


def get_notes(user_id: int) -> list:
    """Список заметок"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, text, created_at FROM notes WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def delete_note(user_id: int, note_id: int) -> bool:
    """Удалить заметку"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id=? AND user_id=?", (note_id, user_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def clear_notes(user_id: int) -> int:
    """Очистить все заметки"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE user_id=?", (user_id,))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count


# ===== ПОКУПКИ =====
def add_shopping_item(user_id: int, item: str) -> bool:
    """Добавить товар в список"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM shopping WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    if count >= MAX_SHOPPING_ITEMS:
        conn.close()
        return False
    c.execute("INSERT INTO shopping (user_id, item) VALUES (?, ?)", (user_id, item))
    conn.commit()
    conn.close()
    return True


def get_shopping_list(user_id: int) -> list:
    """Список покупок"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, item, checked FROM shopping WHERE user_id=? ORDER BY checked, created_at",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def toggle_shopping_item(user_id: int, item_id: int) -> bool:
    """Отметить/снять отметку товара"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT checked FROM shopping WHERE id=? AND user_id=?", (item_id, user_id))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    new_val = 0 if row[0] else 1
    c.execute("UPDATE shopping SET checked=? WHERE id=? AND user_id=?", (new_val, item_id, user_id))
    conn.commit()
    conn.close()
    return True


def delete_shopping_item(user_id: int, item_id: int) -> bool:
    """Удалить товар"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM shopping WHERE id=? AND user_id=?", (item_id, user_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def clear_shopping(user_id: int) -> int:
    """Очистить список покупок"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM shopping WHERE user_id=?", (user_id,))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count


def clear_checked_shopping(user_id: int) -> int:
    """Удалить купленные товары"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM shopping WHERE user_id=? AND checked=1", (user_id,))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count


# ===== НАПОМИНАНИЯ =====
def add_reminder(user_id: int, chat_id: int, text: str, remind_at: datetime) -> int:
    """Добавить напоминание, возвращает id"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO reminders (user_id, chat_id, text, remind_at) VALUES (?, ?, ?, ?)",
        (user_id, chat_id, text, remind_at)
    )
    reminder_id = c.lastrowid
    conn.commit()
    conn.close()
    return reminder_id


def get_pending_reminders() -> list:
    """Получить напоминания к отправке"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "SELECT id, user_id, chat_id, text, remind_at FROM reminders WHERE sent=0 AND remind_at<=?",
        (now,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def mark_reminder_sent(reminder_id: int):
    """Отметить напоминание как отправленное"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
    conn.commit()
    conn.close()


def get_user_reminders(user_id: int) -> list:
    """Активные напоминания пользователя"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, text, remind_at FROM reminders WHERE user_id=? AND sent=0 ORDER BY remind_at",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def delete_reminder(user_id: int, reminder_id: int) -> bool:
    """Удалить напоминание"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE id=? AND user_id=?", (reminder_id, user_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ===== СТАТИСТИКА =====
def track_usage(user_id: int):
    """Отслеживание использования"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO stats (user_id, commands_used, first_use, last_use)
        VALUES (?, 1, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            commands_used = commands_used + 1,
            last_use = ?
    """, (user_id, now, now, now))
    conn.commit()
    conn.close()


def get_user_stats(user_id: int) -> dict:
    """Статистика пользователя"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT commands_used, first_use, last_use FROM stats WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"commands": row[0], "first_use": row[1], "last_use": row[2]}
    return {"commands": 0, "first_use": None, "last_use": None}
