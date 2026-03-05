import sqlite3
from datetime import datetime
from config import DATABASE_PATH

class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.init_db()
    
    def connect(self):
        """Подключиться к БД с timeout"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        return conn
    
    def init_db(self):
        """Инициализация таблиц БД"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 100,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица авторизованных админов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authorized_admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица дневных бонусов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_bonuses (
                user_id INTEGER PRIMARY KEY,
                last_bonus_date DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица ставок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(event_id) REFERENCES events(event_id)
            )
        ''')
        
        # Таблица событий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                odds REAL DEFAULT 1.5,
                status TEXT DEFAULT 'active',
                winner TEXT,
                participants TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                strengths TEXT DEFAULT '{}'
            )
        ''')
        
        # Миграция: добавить колонки если их нет (для старых БД)
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'strengths' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN strengths TEXT DEFAULT '{}'")
        if 'is_auto' not in columns:
            cursor.execute("ALTER TABLE events ADD COLUMN is_auto INTEGER DEFAULT 0")
        
        # Таблица результатов мини-игр
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_results (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game_type TEXT,
                bet_amount INTEGER,
                won INTEGER DEFAULT 0,
                winnings INTEGER DEFAULT 0,
                details TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Миграция: добавить details если нет
        cursor.execute("PRAGMA table_info(game_results)")
        gr_columns = [col[1] for col in cursor.fetchall()]
        if 'details' not in gr_columns:
            cursor.execute("ALTER TABLE game_results ADD COLUMN details TEXT DEFAULT ''")
        
        # Таблица банкрот-восстановления
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bankrupt_recovery (
                user_id INTEGER PRIMARY KEY,
                last_recovery_date DATE,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Таблица хозяина бота (одноразовая блокировка)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_owner (
                id INTEGER PRIMARY KEY DEFAULT 1,
                user_id INTEGER NOT NULL,
                username TEXT,
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Миграция: добавить xp и level к users
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
        if 'xp' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
        if 'level' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id, username):
        """Добавить нового пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (user_id, username, balance)
                VALUES (?, ?, 100)
            ''', (user_id, username))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_user(self, user_id):
        """Получить информацию пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def update_balance(self, user_id, amount):
        """Обновить баланс пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()
    
    def place_bet(self, user_id, event_id, amount, result):
        """Сделать ставку"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Проверка баланса
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user or user[0] < amount:
            conn.close()
            return False
        
        # Создание ставки
        cursor.execute('''
            INSERT INTO bets (user_id, event_id, amount, status, result)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (user_id, event_id, amount, result))
        
        # Снятие денег
        cursor.execute('''
            UPDATE users SET balance = balance - ? WHERE user_id = ?
        ''', (amount, user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_user_bets(self, user_id):
        """Получить историю ставок пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.bet_id, e.title, b.amount, b.status, b.result, b.created_at
            FROM bets b
            JOIN events e ON b.event_id = e.event_id
            WHERE b.user_id = ?
            ORDER BY b.created_at DESC
            LIMIT 20
        ''', (user_id,))
        bets = cursor.fetchall()
        conn.close()
        return bets
    
    def get_leaderboard(self, limit=10):
        """Получить рейтинг лучших игроков"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, balance, total_wins
            FROM users
            ORDER BY balance DESC
            LIMIT ?
        ''', (limit,))
        leaderboard = cursor.fetchall()
        conn.close()
        return leaderboard
    
    def create_event(self, title, description, odds=1.5, participants=None, strengths=None, is_auto=False):
        """Создать новое событие"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Сохранить участников и силу как JSON
        import json
        participants_json = json.dumps(participants) if participants else json.dumps([])
        strengths_json = json.dumps(strengths) if strengths else json.dumps({})
        
        cursor.execute('''
            INSERT INTO events (title, description, odds, status, participants, strengths, is_auto)
            VALUES (?, ?, ?, 'active', ?, ?, ?)
        ''', (title, description, odds, participants_json, strengths_json, 1 if is_auto else 0))
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()
        return event_id
    
    def get_event_bet_stats(self, event_id):
        """Получить статистику ставок на событие: кол-во ставок, общий пул, ставки по участникам"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Общее кол-во и сумма
        cursor.execute('''
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM bets WHERE event_id = ? AND status = 'pending'
        ''', (event_id,))
        total_count, total_pool = cursor.fetchone()
        
        # Ставки по участникам
        cursor.execute('''
            SELECT result, COUNT(*), SUM(amount)
            FROM bets WHERE event_id = ? AND status = 'pending'
            GROUP BY result
        ''', (event_id,))
        per_participant = {row[0]: {'count': row[1], 'amount': row[2]} for row in cursor.fetchall()}
        
        conn.close()
        return total_count, total_pool, per_participant
    
    def has_user_bet_on_event(self, user_id, event_id):
        """Проверить, делал ли пользователь уже ставку на это событие"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM bets
            WHERE user_id = ? AND event_id = ? AND status = 'pending'
        ''', (user_id, event_id))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def get_user_streak(self, user_id):
        """Получить текущую серию побед/поражений пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status FROM bets
            WHERE user_id = ? AND status IN ('won', 'lost')
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return 0, 'none'
        
        first_status = results[0][0]
        streak = 0
        for (s,) in results:
            if s == first_status:
                streak += 1
            else:
                break
        
        return streak, first_status
    
    def get_event_participants(self, event_id):
        """Получить участников события"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT participants FROM events WHERE event_id = ?', (event_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            import json
            return json.loads(result[0])
        return []
    
    def get_event_strengths(self, event_id):
        """Получить силу участников события"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT strengths FROM events WHERE event_id = ?', (event_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            import json
            strengths = json.loads(result[0])
            if isinstance(strengths, dict) and strengths:
                return strengths
        return {}
    
    def get_events(self, status=None, is_auto=None):
        """Получить события. Фильтр по статусу и типу (auto/admin)"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM events WHERE 1=1'
        params = []
        
        if status:
            query += ' AND status = ?'
            params.append(status)
        if is_auto is not None:
            query += ' AND is_auto = ?'
            params.append(1 if is_auto else 0)
        
        query += ' ORDER BY event_id DESC'
        cursor.execute(query, params)
        events = cursor.fetchall()
        conn.close()
        return events
    
    def close_event(self, event_id, winner):
        """Закрыть событие и определить победителя"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # Обновить статус события
            cursor.execute('''
                UPDATE events SET status = ?, winner = ?, closed_at = ?
                WHERE event_id = ?
            ''', ('closed', winner, datetime.now(), event_id))
            
            # Получить коэффициент и силу участников
            cursor.execute('SELECT odds, strengths FROM events WHERE event_id = ?', (event_id,))
            event_data = cursor.fetchone()
            if not event_data:
                conn.close()
                return False
            
            base_odds = event_data[0]
            
            # Рассчитать коэффициент из силы участников
            import json
            strengths = json.loads(event_data[1]) if event_data[1] else {}
            if strengths and winner in strengths:
                total_strength = sum(strengths.values())
                winner_strength = strengths[winner]
                odds = total_strength / winner_strength
            else:
                odds = base_odds
            
            # Получить выигрышные ставки
            cursor.execute('''
                SELECT user_id, amount FROM bets
                WHERE event_id = ? AND result = ? AND status = ?
            ''', (event_id, winner, 'pending'))
            winning_bets = cursor.fetchall()
            
            # Выплатить выигрыш
            for user_id, amount in winning_bets:
                winnings = int(amount * odds)
                cursor.execute('''
                    UPDATE users SET balance = balance + ?, total_wins = total_wins + 1
                    WHERE user_id = ?
                ''', (winnings, user_id))
                cursor.execute('''
                    UPDATE bets SET status = ? WHERE user_id = ? AND event_id = ? AND result = ?
                ''', ('won', user_id, event_id, winner))
            
            # Отметить проигрышные ставки и обновить потери
            cursor.execute('''
                SELECT user_id FROM bets
                WHERE event_id = ? AND result != ? AND status = ?
            ''', (event_id, winner, 'pending'))
            losing_bets = cursor.fetchall()
            
            for (user_id,) in losing_bets:
                cursor.execute('''
                    UPDATE users SET total_losses = total_losses + 1
                    WHERE user_id = ?
                ''', (user_id,))
                
            cursor.execute('''
                UPDATE bets SET status = ?
                WHERE event_id = ? AND result != ? AND status = ?
            ''', ('lost', event_id, winner, 'pending'))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при закрытии события: {e}")
            if conn:
                conn.close()
            return False
    
    def add_admin(self, user_id, username):
        """Добавить пользователя в админы (сохранить после ввода пароля)"""
        conn = self.connect()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO authorized_admins (user_id, username)
                VALUES (?, ?)
            ''', (user_id, username))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def is_admin(self, user_id):
        """Проверить, является ли пользователь админом"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM authorized_admins WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def claim_daily_bonus(self, user_id):
        """Получить дневной бонус (10-50 монет)"""
        import random
        from datetime import date
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Проверить, уже ли брал бонус сегодня
        cursor.execute('''
            SELECT last_bonus_date FROM daily_bonuses WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        today = date.today().isoformat()
        
        if result and result[0] == today:
            conn.close()
            return None, "Вы уже получили бонус сегодня! Вернитесь завтра."
        
        # Дать бонус
        bonus = random.randint(10, 50)
        cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (bonus, user_id))
        
        # Обновить последний день получения бонуса
        cursor.execute('''
            INSERT OR REPLACE INTO daily_bonuses (user_id, last_bonus_date)
            VALUES (?, ?)
        ''', (user_id, today))
        
        conn.commit()
        conn.close()
        return bonus, "✅ Бонус получен!"
    
    def get_user_by_username(self, username):
        """Найти пользователя по username (без @)"""
        conn = self.connect()
        cursor = conn.cursor()
        clean = username.lstrip('@').lower()
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = ?', (clean,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def transfer_money(self, from_user_id, to_user_id, amount):
        """Перевести деньги от одного пользователя к другому"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Проверить баланс отправителя
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (from_user_id,))
        from_user = cursor.fetchone()
        
        # Проверить существование получателя
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (to_user_id,))
        to_user = cursor.fetchone()
        
        if not from_user:
            conn.close()
            return False, "❌ Отправитель не найден"
        
        if not to_user:
            conn.close()
            return False, "❌ Получатель не найден"
        
        if from_user[0] < amount:
            conn.close()
            return False, f"❌ Недостаточно денег. Баланс: {from_user[0]}"
        
        # Выполнить перевод
        cursor.execute('''
            UPDATE users SET balance = balance - ? WHERE user_id = ?
        ''', (amount, from_user_id))
        
        cursor.execute('''
            UPDATE users SET balance = balance + ? WHERE user_id = ?
        ''', (amount, to_user_id))
        
        conn.commit()
        conn.close()
        return True, "✅ Деньги переведены!"
    
    def record_game(self, user_id, game_type, bet_amount, won, winnings, details=''):
        """Записать результат мини-игры, обновить статистику и начислить XP"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO game_results (user_id, game_type, bet_amount, won, winnings, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, game_type, bet_amount, 1 if won else 0, winnings, details))
        
        if won:
            cursor.execute('UPDATE users SET total_wins = total_wins + 1 WHERE user_id = ?', (user_id,))
        else:
            cursor.execute('UPDATE users SET total_losses = total_losses + 1 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
        # Автоматическое начисление XP
        xp_amount = max(1, bet_amount // 10)
        if won:
            xp_amount = int(xp_amount * 1.5)
        self.add_xp(user_id, xp_amount)
    
    def claim_bankrupt_recovery(self, user_id):
        """Банкрот-восстановление: 50 монет раз в день при нулевом балансе"""
        from datetime import date
        
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return None, "❌ Пользователь не найден"
        
        if user[0] > 0:
            conn.close()
            return None, "❌ Восстановление доступно только при нулевом балансе!"
        
        today = date.today().isoformat()
        cursor.execute('SELECT last_recovery_date FROM bankrupt_recovery WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result and result[0] == today:
            conn.close()
            return None, "⏰ Вы уже использовали восстановление сегодня. Попробуйте завтра!"
        
        cursor.execute('UPDATE users SET balance = balance + 50 WHERE user_id = ?', (user_id,))
        cursor.execute('''
            INSERT OR REPLACE INTO bankrupt_recovery (user_id, last_recovery_date)
            VALUES (?, ?)
        ''', (user_id, today))
        
        conn.commit()
        conn.close()
        return 50, "✅ Восстановление получено!"

    def get_user_last_completed_bet(self, user_id):
        """Получить последнюю завершённую ставку пользователя с деталями события"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.bet_id, e.title, b.amount, b.status, b.result, e.winner,
                   b.created_at, e.strengths, e.event_id
            FROM bets b
            JOIN events e ON b.event_id = e.event_id
            WHERE b.user_id = ? AND b.status IN ('won', 'lost')
            ORDER BY b.created_at DESC
            LIMIT 1
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_user_total_bets_count(self, user_id):
        """Общее количество ставок пользователя"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM bets WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def has_used_bankrupt(self, user_id):
        """Проверить, использовал ли пользователь банкрот-восстановление"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM bankrupt_recovery WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def get_user_games_count(self, user_id):
        """Получить количество сыгранных мини-игр"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_results WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_games_won_count(self, user_id):
        """Количество выигранных мини-игр"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_results WHERE user_id = ? AND won = 1', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_total_winnings(self, user_id):
        """Общая сумма выигрышей"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(SUM(winnings), 0) FROM game_results WHERE user_id = ? AND won = 1', (user_id,))
        total = cursor.fetchone()[0]
        conn.close()
        return total

    def get_user_total_wagered(self, user_id):
        """Общая сумма всех ставок (мини-игры)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(SUM(bet_amount), 0) FROM game_results WHERE user_id = ?', (user_id,))
        total = cursor.fetchone()[0]
        conn.close()
        return total

    def get_user_game_type_count(self, user_id, game_type):
        """Количество игр определённого типа"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_results WHERE user_id = ? AND game_type = ?', (user_id, game_type))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_game_type_wins(self, user_id, game_type):
        """Количество побед в определённой игре"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_results WHERE user_id = ? AND game_type = ? AND won = 1', (user_id, game_type))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_max_win(self, user_id):
        """Максимальный выигрыш за одну игру"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(MAX(winnings), 0) FROM game_results WHERE user_id = ? AND won = 1', (user_id,))
        val = cursor.fetchone()[0]
        conn.close()
        return val

    def get_user_max_balance_ever(self, user_id):
        """Текущий баланс (прокси для максимального)"""
        user = self.get_user(user_id)
        return user[2] if user else 0

    def get_user_daily_bonus_count(self, user_id):
        """Количество собранных дневных бонусов"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM daily_bonuses WHERE user_id = ?', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_bets_won_count(self, user_id):
        """Количество выигранных ставок на события"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bets WHERE user_id = ? AND status = 'won'", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def count_game_details(self, user_id, detail_tag):
        """Подсчитать количество игр с определённым тегом в details"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM game_results WHERE user_id = ? AND details LIKE ?",
            (user_id, f'%{detail_tag}%')
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_games_lost_count(self, user_id):
        """Количество проигранных мини-игр"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM game_results WHERE user_id = ? AND won = 0 AND winnings = 0', (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_user_max_bet(self, user_id):
        """Максимальная ставка за раз"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(MAX(bet_amount), 0) FROM game_results WHERE user_id = ?', (user_id,))
        val = cursor.fetchone()[0]
        conn.close()
        return val

    def get_user_total_lost(self, user_id):
        """Общая сумма проигранных монет"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(SUM(bet_amount), 0) FROM game_results WHERE user_id = ? AND won = 0 AND winnings = 0', (user_id,))
        total = cursor.fetchone()[0]
        conn.close()
        return total

    def get_user_game_streak(self, user_id):
        """Получить текущую серию побед/поражений в мини-играх"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT won FROM game_results
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 30
        ''', (user_id,))
        results = cursor.fetchall()
        conn.close()

        if not results:
            return 0, 'none'

        first = results[0][0]
        streak = 0
        for (w,) in results:
            if w == first:
                streak += 1
            else:
                break
        return streak, 'won' if first == 1 else 'lost'

    def check_loss_streak_bonus(self, user_id, streak_required=10):
        """Проверить и выдать бонус за серию поражений в мини-играх.
        Выдаёт бонус только один раз за серию (трекает через loss_streak_bonuses)."""
        from datetime import date
        conn = self.connect()
        cursor = conn.cursor()

        # Создать таблицу если нет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loss_streak_bonuses (
                bonus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                streak_len INTEGER,
                bonus_amount INTEGER,
                claimed_at DATE,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Посчитать текущую серию поражений
        cursor.execute('''
            SELECT won FROM game_results
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 30
        ''', (user_id,))
        results = cursor.fetchall()

        if not results or results[0][0] != 0:
            conn.close()
            return 0

        streak = 0
        for (w,) in results:
            if w == 0:
                streak += 1
            else:
                break

        if streak < streak_required:
            conn.close()
            return 0

        # Проверить, не выдан ли уже бонус за такую длину серии сегодня
        today = date.today().isoformat()
        cursor.execute('''
            SELECT COUNT(*) FROM loss_streak_bonuses
            WHERE user_id = ? AND streak_len = ? AND claimed_at = ?
        ''', (user_id, streak, today))
        already_claimed = cursor.fetchone()[0]

        if already_claimed > 0:
            conn.close()
            return 0

        # Выдать бонус
        import random
        bonus = random.randint(50, 100)
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, user_id))
        cursor.execute('''
            INSERT INTO loss_streak_bonuses (user_id, streak_len, bonus_amount, claimed_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, streak, bonus, today))
        conn.commit()
        conn.close()
        return bonus

    def check_total_loss_milestone(self, user_id):
        """Проверить и выдать бонус за достижение порога суммарных проигрышей.
        Пороги: 1000, 5000, 10000, 25000, 50000. Бонус: 5% от порога."""
        conn = self.connect()
        cursor = conn.cursor()

        # Создать таблицу если нет
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loss_milestone_bonuses (
                milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                milestone INTEGER,
                bonus_amount INTEGER,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Суммарные проигрыши
        cursor.execute('SELECT COALESCE(SUM(bet_amount), 0) FROM game_results WHERE user_id = ? AND won = 0', (user_id,))
        total_lost = cursor.fetchone()[0]

        milestones = [1000, 5000, 10000, 25000, 50000]
        bonuses_awarded = []

        for milestone in milestones:
            if total_lost >= milestone:
                # Проверить, не получен ли уже
                cursor.execute('''
                    SELECT COUNT(*) FROM loss_milestone_bonuses
                    WHERE user_id = ? AND milestone = ?
                ''', (user_id, milestone))
                if cursor.fetchone()[0] == 0:
                    bonus = milestone // 20  # 5% от порога
                    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus, user_id))
                    cursor.execute('''
                        INSERT INTO loss_milestone_bonuses (user_id, milestone, bonus_amount)
                        VALUES (?, ?, ?)
                    ''', (user_id, milestone, bonus))
                    bonuses_awarded.append((milestone, bonus))

        conn.commit()
        conn.close()
        return bonuses_awarded

    # ==================== ХОЗЯИН ====================
    
    def set_owner(self, user_id, username):
        """Установить хозяина бота (только один раз)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM bot_owner', )
        if cursor.fetchone()[0] > 0:
            conn.close()
            return False  # Уже есть хозяин
        cursor.execute('INSERT INTO bot_owner (id, user_id, username) VALUES (1, ?, ?)', (user_id, username))
        conn.commit()
        conn.close()
        return True
    
    def get_owner(self):
        """Получить хозяина бота"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, username FROM bot_owner WHERE id = 1')
        owner = cursor.fetchone()
        conn.close()
        return owner
    
    def is_owner(self, user_id):
        """Проверить, является ли пользователь хозяином"""
        owner = self.get_owner()
        return owner is not None and owner[0] == user_id
    
    def reset_all_stats(self):
        """Полный сброс статистики всех игроков"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = 100, total_wins = 0, total_losses = 0, xp = 0, level = 1')
        cursor.execute('DELETE FROM game_results')
        cursor.execute('DELETE FROM bets')
        cursor.execute('DELETE FROM daily_bonuses')
        cursor.execute('DELETE FROM bankrupt_recovery')
        # Удалить streak/milestone таблицы если есть
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('loss_streak_bonuses', 'loss_milestone_bonuses')")
        for table in cursor.fetchall():
            cursor.execute(f'DELETE FROM {table[0]}')
        conn.commit()
        conn.close()
        return True
    
    def reset_user_stats(self, username):
        """Сброс статистики конкретного игрока по username"""
        conn = self.connect()
        cursor = conn.cursor()
        # Найти user_id
        cursor.execute('SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)', (username,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return False, "Пользователь не найден"
        
        user_id = user[0]
        cursor.execute('UPDATE users SET balance = 100, total_wins = 0, total_losses = 0, xp = 0, level = 1 WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM game_results WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM bets WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM daily_bonuses WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM bankrupt_recovery WHERE user_id = ?', (user_id,))
        # Streak/milestone
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('loss_streak_bonuses', 'loss_milestone_bonuses')")
        for table in cursor.fetchall():
            cursor.execute(f'DELETE FROM {table[0]} WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, f"Статистика @{username} сброшена"
    
    # ==================== XP / УРОВНИ ====================
    
    def add_xp(self, user_id, amount):
        """Добавить XP игроку и пересчитать уровень.
        Возвращает (new_xp, old_level, new_level)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        old_xp = row[0] or 0
        old_level = row[1] or 1
        new_xp = old_xp + amount
        new_level = self.calc_level(new_xp)
        cursor.execute('UPDATE users SET xp = ?, level = ? WHERE user_id = ?', (new_xp, new_level, user_id))
        conn.commit()
        conn.close()
        return new_xp, old_level, new_level
    
    @staticmethod
    def calc_level(xp):
        """Рассчитать уровень по XP.
        Каждый уровень требует level * 100 XP (прогрессивно).
        Lv1: 0, Lv2: 100, Lv3: 300, Lv4: 600, Lv5: 1000, ..."""
        level = 1
        required = 0
        while True:
            required += level * 100
            if xp < required:
                return level
            level += 1
    
    @staticmethod
    def xp_for_next_level(level):
        """XP нужен для следующего уровня (от 0)"""
        required = 0
        for i in range(1, level + 1):
            required += i * 100
        return required
    
    def get_user_xp_info(self, user_id):
        """Получить XP инфо: (xp, level, xp_to_next)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return 0, 1, 100
        xp = row[0] or 0
        level = row[1] or 1
        xp_to_next = self.xp_for_next_level(level)
        return xp, level, xp_to_next