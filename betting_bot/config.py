import os
from dotenv import load_dotenv

# Загрузить .env из текущей папки
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

# Telegram токен
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# ID админов (список)
ADMIN_IDS = [123456789, 987654321]  # Замени на реальные ID

# ПАРОЛЬ ДЛЯ АДМИНА
ADMIN_PASSWORD = "32415"  # Админский пароль!

# Константы игры
INITIAL_BALANCE = 100  # Начальный баланс новых игроков
MIN_BET = 10           # Минимальная ставка
MAX_BET_PERCENT = 1.0  # Максимум - весь баланс

# БД
DATABASE_PATH = 'bot_database.db'

# API
API_TIMEOUT = 30

# Состояния для ConversationHandler
ADMIN_PASSWORD_STATE = 1
ADMIN_MENU_STATE = 2
CREATE_EVENT_NAME_STATE = 3
CREATE_EVENT_ODDS_STATE = 4
CREATE_EVENT_PARTICIPANTS_STATE = 15
CLOSE_EVENT_ID_STATE = 5
CLOSE_EVENT_WINNER_STATE = 6
BET_EVENT_ID_STATE = 7
BET_AMOUNT_STATE = 8
BET_RESULT_STATE = 9
TRANSFER_AMOUNT_STATE = 10
TRANSFER_USER_ID_STATE = 11
CREATE_EVENT_STRENGTH_STATE = 16

# Мини-игры
ROULETTE_BET_STATE = 20
ROULETTE_CHOICE_STATE = 21
COINFLIP_BET_STATE = 22
COINFLIP_CHOICE_STATE = 23

# Кости
DICE_BET_STATE = 24

# Блэкджек
BLACKJACK_BET_STATE = 25
BLACKJACK_PLAY_STATE = 26

# Слоты
SLOTS_BET_STATE = 27

# Краш
CRASH_BET_STATE = 28
CRASH_CHOICE_STATE = 33

# Боулинг
BOWLING_BET_STATE = 29

# Ставки: выбор типа
BET_TYPE_STATE = 30

# Дартс
DARTS_BET_STATE = 31
DARTS_CHOICE_STATE = 32

# Хозяин
OWNER_PASSWORD = "567891234"
OWNER_PASSWORD_STATE = 34
OWNER_MENU_STATE = 35
OWNER_RESET_USER_STATE = 36

# Минное поле
MINES_BET_STATE = 37
MINES_PLAY_STATE = 38

# Колесо фортуны
WHEEL_BET_STATE = 39

# Больше/Меньше
HIGHLOW_BET_STATE = 40
HIGHLOW_PLAY_STATE = 41

# Русская рулетка
RUSSIANR_BET_STATE = 42
RUSSIANR_CHOICE_STATE = 43

# Автоматические события
AUTO_EVENT_INTERVAL = 300  # Секунд (5 минут)
