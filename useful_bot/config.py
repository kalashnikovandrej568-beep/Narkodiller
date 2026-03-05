"""
Конфигурация бота «Полезный Помощник»
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== Токен бота =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ===== API ключи (опционально) =====
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")  # OpenWeatherMap (бесплатно)

# ===== База данных =====
DB_PATH = "useful_bot.db"

# ===== Лимиты =====
RATE_LIMIT = 10  # запросов в минуту
MAX_NOTES = 50  # макс заметок на пользователя
MAX_SHOPPING_ITEMS = 100  # макс товаров в списке покупок

# ===== Логи =====
LOG_FILE = "logs/bot.log"

# ===== Состояния ConversationHandler =====
(
    NOTE_ADD_STATE,
    NOTE_DELETE_STATE,
    REMINDER_TEXT_STATE,
    REMINDER_TIME_STATE,
    WEATHER_CITY_STATE,
    CALC_STATE,
    BMI_WEIGHT_STATE,
    BMI_HEIGHT_STATE,
    FUEL_DISTANCE_STATE,
    FUEL_CONSUMPTION_STATE,
    FUEL_PRICE_STATE,
    SHOPPING_ADD_STATE,
    SHOPPING_DEL_STATE,
    CONVERT_STATE,
    PASSWORD_LENGTH_STATE,
    TRANSLATE_STATE,
) = range(16)

# ===== Праздники РФ =====
RU_HOLIDAYS = {
    (1, 1): "🎄 Новогодние каникулы",
    (1, 2): "🎄 Новогодние каникулы",
    (1, 3): "🎄 Новогодние каникулы",
    (1, 4): "🎄 Новогодние каникулы",
    (1, 5): "🎄 Новогодние каникулы",
    (1, 6): "🎄 Новогодние каникулы",
    (1, 7): "🎄 Рождество Христово",
    (1, 8): "🎄 Новогодние каникулы",
    (2, 23): "🎖 День защитника Отечества",
    (3, 8): "💐 Международный женский день",
    (5, 1): "🌸 Праздник Весны и Труда",
    (5, 9): "🎗 День Победы",
    (6, 12): "🇷🇺 День России",
    (11, 4): "🤝 День народного единства",
}
