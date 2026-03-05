"""
База данных крипто-бота (SQLite)
Хранит пользователей, алерты, отслеживаемые крипты (трекер), подписки
"""

import sqlite3
import time
from datetime import datetime, timedelta
from config import DATABASE_PATH


class Database:
    """Класс для работы с SQLite"""

    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.init_db()

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=10.0)

    def init_db(self):
        conn = self.connect()
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица алертов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                crypto_ticker TEXT NOT NULL,
                target_price REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'usd',
                direction TEXT NOT NULL DEFAULT 'above',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                triggered_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица отслеживаемых крипт (трекер)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracked_cryptos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                crypto_ticker TEXT NOT NULL,
                threshold_percent REAL DEFAULT 10.0,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, crypto_ticker),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица кулдаунов уведомлений трекера
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracker_notifications (
                user_id INTEGER NOT NULL,
                crypto_ticker TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'up',
                last_notified REAL DEFAULT 0,
                PRIMARY KEY(user_id, crypto_ticker, direction)
            )
        ''')

        # Таблица избранных криптовалют
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                crypto_ticker TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, crypto_ticker),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица подписок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                tier TEXT NOT NULL DEFAULT 'free',
                expires_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица использованных промокодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS used_promos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                promo_code TEXT NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, promo_code),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица наград за викторину
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_rewards (
                user_id INTEGER PRIMARY KEY,
                last_medium_attempt TEXT,
                last_medium_reward TEXT,
                last_hard_attempt TEXT,
                last_hard_reward TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица виртуального портфеля
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                quantity REAL NOT NULL,
                buy_price REAL NOT NULL,
                asset_type TEXT DEFAULT 'crypto',
                bought_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Таблица предсказаний цен
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                direction TEXT NOT NULL,
                price_at_prediction REAL NOT NULL,
                asset_type TEXT DEFAULT 'crypto',
                predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved INTEGER DEFAULT 0,
                result TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        conn.commit()

        # === Миграция: добавить asset_type ===
        for table in ['alerts', 'tracked_cryptos', 'tracker_notifications', 'favorites']:
            try:
                cursor = conn.cursor()
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN asset_type TEXT DEFAULT 'crypto'")
                conn.commit()
            except Exception:
                pass  # Столбец уже существует

        # === Таблица автора бота ===
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_author (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                user_id INTEGER NOT NULL,
                username TEXT,
                set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

        conn.close()

    # ==================== ПОЛЬЗОВАТЕЛИ ====================

    def add_user(self, user_id, username):
        """Добавить пользователя (или обновить username)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, username) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = ?
        ''', (user_id, username, username))
        conn.commit()
        conn.close()

    def get_user(self, user_id):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user

    # ==================== АВТОР БОТА ====================

    def get_author(self):
        """Получить user_id автора (или None если не задан)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM bot_author WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_author(self, user_id, username=None):
        """Установить автора бота (можно только один раз)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO bot_author (id, user_id, username)
            VALUES (1, ?, ?)
        ''', (user_id, username))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0  # True если новый автор записан

    def is_author(self, user_id):
        """Проверить, является ли user_id автором"""
        author_id = self.get_author()
        return author_id is not None and author_id == user_id

    # ==================== АЛЕРТЫ ====================

    def create_alert(self, user_id, crypto_ticker, target_price, currency, direction, asset_type='crypto'):
        """Создать новый алерт. Вернёт alert_id."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (user_id, crypto_ticker, target_price, currency, direction, asset_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, crypto_ticker, target_price, currency, direction, asset_type))
        conn.commit()
        alert_id = cursor.lastrowid
        conn.close()
        return alert_id

    def get_user_alerts(self, user_id, active_only=True, asset_type='crypto'):
        """Получить алерты пользователя.
        Возвращает список tuple:
        (alert_id, user_id, crypto_ticker, target_price, currency, direction, active, created_at, triggered_at, asset_type)
        """
        conn = self.connect()
        cursor = conn.cursor()
        if active_only:
            cursor.execute(
                'SELECT * FROM alerts WHERE user_id = ? AND active = 1 AND asset_type = ? ORDER BY created_at DESC',
                (user_id, asset_type)
            )
        else:
            cursor.execute(
                'SELECT * FROM alerts WHERE user_id = ? AND asset_type = ? ORDER BY created_at DESC',
                (user_id, asset_type)
            )
        alerts = cursor.fetchall()
        conn.close()
        return alerts

    def get_all_active_alerts(self):
        """Получить ВСЕ активные алерты (для фоновой проверки)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alerts WHERE active = 1')
        alerts = cursor.fetchall()
        conn.close()
        return alerts

    def trigger_alert(self, alert_id):
        """Пометить алерт как сработавший"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE alerts SET active = 0, triggered_at = ? WHERE alert_id = ?
        ''', (datetime.now().isoformat(), alert_id))
        conn.commit()
        conn.close()

    def delete_alert(self, alert_id, user_id):
        """Удалить конкретный алерт (только свой)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM alerts WHERE alert_id = ? AND user_id = ?',
            (alert_id, user_id)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def delete_all_user_alerts(self, user_id, asset_type='crypto'):
        """Удалить все активные алерты пользователя. Вернёт количество."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM alerts WHERE user_id = ? AND active = 1 AND asset_type = ?',
            (user_id, asset_type)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    def deactivate_alert(self, alert_id, user_id):
        """Деактивировать алерт (не удалять, просто выключить)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE alerts SET active = 0 WHERE alert_id = ? AND user_id = ?',
            (alert_id, user_id)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def count_user_active_alerts(self, user_id, asset_type='crypto'):
        """Сколько активных алертов у пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM alerts WHERE user_id = ? AND active = 1 AND asset_type = ?',
            (user_id, asset_type)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ==================== ТРЕКЕР ====================

    def add_tracked_crypto(self, user_id, crypto_ticker, threshold=10.0, asset_type='crypto'):
        """Добавить крипту/акцию в трекер. Если уже есть — обновить порог."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tracked_cryptos (user_id, crypto_ticker, threshold_percent, asset_type)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, crypto_ticker) DO UPDATE SET
                threshold_percent = ?, active = 1
        ''', (user_id, crypto_ticker, threshold, asset_type, threshold))
        conn.commit()
        conn.close()

    def remove_tracked_crypto(self, user_id, crypto_ticker):
        """Убрать крипту из трекера"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM tracked_cryptos WHERE user_id = ? AND crypto_ticker = ?',
            (user_id, crypto_ticker)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_user_tracked(self, user_id, asset_type='crypto'):
        """Получить список отслеживаемых крипт/акций пользователя.
        Возвращает [(id, user_id, crypto_ticker, threshold_percent, active, created_at, asset_type)]"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM tracked_cryptos WHERE user_id = ? AND active = 1 AND asset_type = ? ORDER BY created_at',
            (user_id, asset_type)
        )
        items = cursor.fetchall()
        conn.close()
        return items

    def get_all_tracked(self):
        """Получить все активные отслеживания (для фоновой проверки).
        Возвращает [(id, user_id, crypto_ticker, threshold_percent, active, created_at)]"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tracked_cryptos WHERE active = 1')
        items = cursor.fetchall()
        conn.close()
        return items

    def set_tracked_threshold(self, user_id, crypto_ticker, threshold):
        """Изменить порог для конкретной крипты"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tracked_cryptos SET threshold_percent = ? WHERE user_id = ? AND crypto_ticker = ?',
            (threshold, user_id, crypto_ticker)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def set_all_tracked_threshold(self, user_id, threshold):
        """Изменить порог для ВСЕХ отслеживаемых крипт пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tracked_cryptos SET threshold_percent = ? WHERE user_id = ? AND active = 1',
            (threshold, user_id)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    def count_user_tracked(self, user_id, asset_type='crypto'):
        """Сколько крипт/акций отслеживает пользователь"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM tracked_cryptos WHERE user_id = ? AND active = 1 AND asset_type = ?',
            (user_id, asset_type)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def is_tracked(self, user_id, crypto_ticker):
        """Проверить, отслеживается ли крипта"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM tracked_cryptos WHERE user_id = ? AND crypto_ticker = ? AND active = 1',
            (user_id, crypto_ticker)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    # ==================== КУЛДАУН ТРЕКЕРА ====================

    def can_notify_tracker(self, user_id, crypto_ticker, direction, cooldown):
        """Проверить, можно ли отправить уведомление (прошёл ли кулдаун)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT last_notified FROM tracker_notifications WHERE user_id = ? AND crypto_ticker = ? AND direction = ?',
            (user_id, crypto_ticker, direction)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return True
        return (time.time() - row[0]) >= cooldown

    def update_tracker_notification(self, user_id, crypto_ticker, direction):
        """Обновить время последнего уведомления"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tracker_notifications (user_id, crypto_ticker, direction, last_notified)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, crypto_ticker, direction) DO UPDATE SET last_notified = ?
        ''', (user_id, crypto_ticker, direction, time.time(), time.time()))
        conn.commit()
        conn.close()

    def clear_user_tracked(self, user_id):
        """Удалить все отслеживания пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tracked_cryptos WHERE user_id = ?', (user_id,))
        affected = cursor.rowcount
        cursor.execute('DELETE FROM tracker_notifications WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return affected

    # ==================== ИЗБРАННОЕ ====================

    def add_favorite(self, user_id, crypto_ticker, asset_type='crypto'):
        """Добавить крипту/акцию в избранное"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO favorites (user_id, crypto_ticker, asset_type) VALUES (?, ?, ?)
            ''', (user_id, crypto_ticker, asset_type))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False  # уже в избранном

    def remove_favorite(self, user_id, crypto_ticker):
        """Убрать крипту из избранного"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM favorites WHERE user_id = ? AND crypto_ticker = ?',
            (user_id, crypto_ticker)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_user_favorites(self, user_id, asset_type='crypto'):
        """Получить избранные крипты/акции пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT crypto_ticker FROM favorites WHERE user_id = ? AND asset_type = ? ORDER BY added_at',
            (user_id, asset_type)
        )
        items = [row[0] for row in cursor.fetchall()]
        conn.close()
        return items

    def is_favorite(self, user_id, crypto_ticker):
        """Проверить, в избранном ли крипта"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM favorites WHERE user_id = ? AND crypto_ticker = ?',
            (user_id, crypto_ticker)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def count_favorites(self, user_id, asset_type='crypto'):
        """Сколько крипт/акций в избранном"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM favorites WHERE user_id = ? AND asset_type = ?',
            (user_id, asset_type)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def clear_favorites(self, user_id, asset_type='crypto'):
        """Очистить избранное"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM favorites WHERE user_id = ? AND asset_type = ?', (user_id, asset_type))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    # ==================== ПОДПИСКИ ====================

    def get_subscription(self, user_id):
        """Получить подписку пользователя. Возвращает (tier, expires_at) или ('free', None)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT tier, expires_at FROM subscriptions WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return ('free', None)

        tier, expires_at = row
        # Проверить срок
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                if exp < datetime.now():
                    # Подписка истекла — сбрасываем на free
                    self.set_subscription(user_id, 'free', None)
                    return ('free', None)
            except Exception:
                pass
        return (tier, expires_at)

    def get_active_tier(self, user_id):
        """Получить актуальный тир подписки: 'free', 'pro', 'premium'"""
        tier, _ = self.get_subscription(user_id)
        return tier

    def set_subscription(self, user_id, tier, expires_at=None):
        """Установить подписку. expires_at — ISO строка или None (навсегда)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subscriptions (user_id, tier, expires_at) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET tier = ?, expires_at = ?
        ''', (user_id, tier, expires_at, tier, expires_at))
        conn.commit()
        conn.close()

    def add_subscription_days(self, user_id, tier, days):
        """Добавить дни к подписке. Если текущая подписка ниже — переключает на tier."""
        current_tier, current_exp = self.get_subscription(user_id)

        tier_rank = {'free': 0, 'pro': 1, 'premium': 2}

        # Если добавляем тот же или более высокий тир — продлить
        if tier_rank.get(tier, 0) >= tier_rank.get(current_tier, 0):
            now = datetime.now()
            if current_exp and tier == current_tier:
                try:
                    base = datetime.fromisoformat(current_exp)
                    if base < now:
                        base = now
                except Exception:
                    base = now
            else:
                base = now

            new_exp = base + timedelta(days=days)
            self.set_subscription(user_id, tier, new_exp.isoformat())
        else:
            # Добавляемый тир ниже текущего — не понижаем
            pass

    # ==================== ПРОМОКОДЫ ====================

    def is_promo_used(self, user_id, promo_code):
        """Проверить, использовал ли пользователь промокод"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM used_promos WHERE user_id = ? AND promo_code = ?',
            (user_id, promo_code)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def use_promo(self, user_id, promo_code):
        """Пометить промокод как использованный"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO used_promos (user_id, promo_code) VALUES (?, ?)',
                (user_id, promo_code)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    # ==================== НАГРАДЫ ЗА ВИКТОРИНУ ====================

    def get_quiz_rewards(self, user_id):
        """Получить данные о наградах за викторину"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM quiz_rewards WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {
                'last_medium_attempt': None,
                'last_medium_reward': None,
                'last_hard_attempt': None,
                'last_hard_reward': None,
            }
        return {
            'last_medium_attempt': row[1],
            'last_medium_reward': row[2],
            'last_hard_attempt': row[3],
            'last_hard_reward': row[4],
        }

    def set_quiz_attempt(self, user_id, difficulty):
        """Записать попытку прохождения викторины (medium/hard)"""
        conn = self.connect()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        field = f'last_{difficulty}_attempt'

        cursor.execute('SELECT user_id FROM quiz_rewards WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute(
                f'UPDATE quiz_rewards SET {field} = ? WHERE user_id = ?',
                (now, user_id)
            )
        else:
            cursor.execute(
                f'INSERT INTO quiz_rewards (user_id, {field}) VALUES (?, ?)',
                (user_id, now)
            )
        conn.commit()
        conn.close()

    def set_quiz_reward(self, user_id, difficulty):
        """Записать получение награды за викторину (medium/hard)"""
        conn = self.connect()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        field = f'last_{difficulty}_reward'

        cursor.execute('SELECT user_id FROM quiz_rewards WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            cursor.execute(
                f'UPDATE quiz_rewards SET {field} = ? WHERE user_id = ?',
                (now, user_id)
            )
        else:
            cursor.execute(
                f'INSERT INTO quiz_rewards (user_id, {field}) VALUES (?, ?)',
                (user_id, now)
            )
        conn.commit()
        conn.close()

    def can_get_quiz_reward(self, user_id, difficulty):
        """Проверить, может ли пользователь получить награду (раз в неделю)"""
        rewards = self.get_quiz_rewards(user_id)
        last_reward = rewards.get(f'last_{difficulty}_reward')
        if not last_reward:
            return True
        try:
            last = datetime.fromisoformat(last_reward)
            return (datetime.now() - last).days >= 7
        except Exception:
            return True

    def can_attempt_quiz_reward(self, user_id, difficulty):
        """Проверить, есть ли ещё попытка на эту неделю (1 попытка в неделю)"""
        rewards = self.get_quiz_rewards(user_id)
        last_attempt = rewards.get(f'last_{difficulty}_attempt')
        if not last_attempt:
            return True
        try:
            last = datetime.fromisoformat(last_attempt)
            return (datetime.now() - last).days >= 7
        except Exception:
            return True

    # ==================== ВИРТУАЛЬНЫЙ ПОРТФЕЛЬ ====================

    def portfolio_buy(self, user_id, ticker, quantity, buy_price, asset_type='crypto'):
        """Купить актив в виртуальный портфель"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfolio (user_id, ticker, quantity, buy_price, asset_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, ticker, quantity, buy_price, asset_type))
        conn.commit()
        conn.close()

    def portfolio_get(self, user_id, asset_type='crypto'):
        """Получить все позиции портфеля.
        Возвращает [(id, user_id, ticker, quantity, buy_price, asset_type, bought_at)]"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM portfolio WHERE user_id = ? AND asset_type = ? ORDER BY bought_at DESC',
            (user_id, asset_type)
        )
        items = cursor.fetchall()
        conn.close()
        return items

    def portfolio_get_aggregated(self, user_id, asset_type='crypto'):
        """Агрегированный портфель: {ticker: (total_qty, avg_price)}"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT ticker, SUM(quantity), SUM(quantity * buy_price) / SUM(quantity)
               FROM portfolio WHERE user_id = ? AND asset_type = ?
               GROUP BY ticker''',
            (user_id, asset_type)
        )
        result = {}
        for row in cursor.fetchall():
            result[row[0]] = (row[1], row[2])
        conn.close()
        return result

    def portfolio_sell(self, user_id, ticker, quantity, asset_type='crypto'):
        """Продать актив из портфеля (FIFO). Возвращает фактически проданное кол-во."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT id, quantity FROM portfolio
               WHERE user_id = ? AND ticker = ? AND asset_type = ?
               ORDER BY bought_at ASC''',
            (user_id, ticker, asset_type)
        )
        positions = cursor.fetchall()
        remaining = quantity
        sold = 0
        for pos_id, pos_qty in positions:
            if remaining <= 0:
                break
            if pos_qty <= remaining:
                cursor.execute('DELETE FROM portfolio WHERE id = ?', (pos_id,))
                remaining -= pos_qty
                sold += pos_qty
            else:
                cursor.execute(
                    'UPDATE portfolio SET quantity = ? WHERE id = ?',
                    (pos_qty - remaining, pos_id)
                )
                sold += remaining
                remaining = 0
        conn.commit()
        conn.close()
        return sold

    def portfolio_clear(self, user_id, asset_type='crypto'):
        """Очистить весь портфель"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM portfolio WHERE user_id = ? AND asset_type = ?',
            (user_id, asset_type)
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    def portfolio_count(self, user_id, asset_type='crypto'):
        """Количество уникальных тикеров в портфеле"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(DISTINCT ticker) FROM portfolio WHERE user_id = ? AND asset_type = ?',
            (user_id, asset_type)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ==================== ПРЕДСКАЗАНИЯ ЦЕН ====================

    def prediction_create(self, user_id, ticker, direction, price, asset_type='crypto'):
        """Создать предсказание (direction: 'up' или 'down')"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predictions (user_id, ticker, direction, price_at_prediction, asset_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, ticker, direction, price, asset_type))
        conn.commit()
        pid = cursor.lastrowid
        conn.close()
        return pid

    def prediction_get_active(self, user_id, asset_type='crypto'):
        """Получить активные (нерешённые) предсказания.
        Возвращает [(id, user_id, ticker, direction, price, asset_type, predicted_at, resolved, result)]"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT * FROM predictions
               WHERE user_id = ? AND asset_type = ? AND resolved = 0
               ORDER BY predicted_at DESC''',
            (user_id, asset_type)
        )
        items = cursor.fetchall()
        conn.close()
        return items

    def prediction_resolve(self, pred_id, result):
        """Отметить предсказание как решённое."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE predictions SET resolved = 1, result = ? WHERE id = ?',
            (result, pred_id)
        )
        conn.commit()
        conn.close()

    def prediction_get_stats(self, user_id):
        """Статистика предсказаний: (total, correct, wrong)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM predictions WHERE user_id = ? AND resolved = 1',
            (user_id,)
        )
        total = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM predictions WHERE user_id = ? AND resolved = 1 AND result = 'correct'",
            (user_id,)
        )
        correct = cursor.fetchone()[0]
        conn.close()
        return (total, correct, total - correct)

    def prediction_count_active(self, user_id, asset_type='crypto'):
        """Сколько активных предсказаний"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM predictions WHERE user_id = ? AND asset_type = ? AND resolved = 0',
            (user_id, asset_type)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def prediction_get_all_active(self):
        """Все активные предсказания (для фоновой проверки)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM predictions WHERE resolved = 0')
        items = cursor.fetchall()
        conn.close()
        return items
