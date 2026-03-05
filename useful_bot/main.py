"""
Полезный Помощник — Telegram бот с 15+ функциями
Точка входа
"""

import logging
import os
import sys
import asyncio
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, filters
)
from config import (
    BOT_TOKEN, LOG_FILE,
    NOTE_ADD_STATE, NOTE_DELETE_STATE,
    REMINDER_TEXT_STATE, REMINDER_TIME_STATE,
    WEATHER_CITY_STATE, CALC_STATE,
    BMI_WEIGHT_STATE, BMI_HEIGHT_STATE,
    FUEL_DISTANCE_STATE, FUEL_CONSUMPTION_STATE, FUEL_PRICE_STATE,
    SHOPPING_ADD_STATE, SHOPPING_DEL_STATE,
    CONVERT_STATE, PASSWORD_LENGTH_STATE, TRANSLATE_STATE,
)
from handlers import (
    start_command, help_command, cancel_command,
    button_handler,
    weather_command, weather_handler,
    currency_command, convert_currency_command,
    calc_command, calc_handler,
    convert_command, convert_handler,
    notes_command, note_add_handler, note_delete_handler,
    shopping_command, shopping_add_handler,
    remind_command, reminder_text_handler, reminder_time_handler,
    password_command, password_handler,
    bmi_command, bmi_weight_handler, bmi_height_handler,
    fuel_command, fuel_distance_handler, fuel_consumption_handler, fuel_price_handler,
    translit_command, translit_handler,
    random_command, coin_command, yesno_command, choose_command,
    today_command, worldtime_command, textstats_command, mystats_command,
)
from database import init_db, get_pending_reminders, mark_reminder_sent


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


async def check_reminders(context):
    """Проверка и отправка напоминаний (job_queue)"""
    pending = get_pending_reminders()
    for rid, user_id, chat_id, text, remind_at in pending:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🔔 *Напоминание!*\n\n{text}",
                parse_mode="Markdown",
            )
            mark_reminder_sent(rid)
        except Exception as e:
            logging.getLogger(__name__).error(f"Ошибка отправки напоминания {rid}: {e}")


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN не установлен!")
        print("\n⚠️  Создайте .env файл с BOT_TOKEN=ваш_токен\n")
        sys.exit(1)

    # Инициализация БД
    init_db()

    logger.info("🚀 Запуск бота «Полезный Помощник»...")
    app = Application.builder().token(BOT_TOKEN).build()

    # ===== Общие fallbacks =====
    fallbacks = [
        CommandHandler("cancel", cancel_command),
        CommandHandler("start", start_command),
    ]

    text_filter = filters.TEXT & ~filters.COMMAND

    # ===== ConversationHandler для кнопок =====
    conv_buttons = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(cmd_|rnd_|note_|shop_)")
        ],
        states={
            WEATHER_CITY_STATE: [MessageHandler(text_filter, weather_handler)],
            CALC_STATE: [MessageHandler(text_filter, calc_handler)],
            CONVERT_STATE: [MessageHandler(text_filter, convert_handler)],
            NOTE_ADD_STATE: [MessageHandler(text_filter, note_add_handler)],
            NOTE_DELETE_STATE: [MessageHandler(text_filter, note_delete_handler)],
            SHOPPING_ADD_STATE: [MessageHandler(text_filter, shopping_add_handler)],
            REMINDER_TEXT_STATE: [MessageHandler(text_filter, reminder_text_handler)],
            REMINDER_TIME_STATE: [MessageHandler(text_filter, reminder_time_handler)],
            PASSWORD_LENGTH_STATE: [MessageHandler(text_filter, password_handler)],
            BMI_WEIGHT_STATE: [MessageHandler(text_filter, bmi_weight_handler)],
            BMI_HEIGHT_STATE: [MessageHandler(text_filter, bmi_height_handler)],
            FUEL_DISTANCE_STATE: [MessageHandler(text_filter, fuel_distance_handler)],
            FUEL_CONSUMPTION_STATE: [MessageHandler(text_filter, fuel_consumption_handler)],
            FUEL_PRICE_STATE: [MessageHandler(text_filter, fuel_price_handler)],
            TRANSLATE_STATE: [MessageHandler(text_filter, translit_handler)],
        },
        fallbacks=fallbacks,
        per_message=False,
    )

    # ===== ConversationHandler: /weather =====
    conv_weather = ConversationHandler(
        entry_points=[CommandHandler("weather", weather_command)],
        states={WEATHER_CITY_STATE: [MessageHandler(text_filter, weather_handler)]},
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /calc =====
    conv_calc = ConversationHandler(
        entry_points=[CommandHandler("calc", calc_command)],
        states={CALC_STATE: [MessageHandler(text_filter, calc_handler)]},
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /convert =====
    conv_convert = ConversationHandler(
        entry_points=[CommandHandler("convert", convert_command)],
        states={CONVERT_STATE: [MessageHandler(text_filter, convert_handler)]},
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /remind =====
    conv_remind = ConversationHandler(
        entry_points=[CommandHandler("remind", remind_command)],
        states={
            REMINDER_TEXT_STATE: [MessageHandler(text_filter, reminder_text_handler)],
            REMINDER_TIME_STATE: [MessageHandler(text_filter, reminder_time_handler)],
        },
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /password =====
    conv_password = ConversationHandler(
        entry_points=[CommandHandler("password", password_command)],
        states={PASSWORD_LENGTH_STATE: [MessageHandler(text_filter, password_handler)]},
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /bmi =====
    conv_bmi = ConversationHandler(
        entry_points=[CommandHandler("bmi", bmi_command)],
        states={
            BMI_WEIGHT_STATE: [MessageHandler(text_filter, bmi_weight_handler)],
            BMI_HEIGHT_STATE: [MessageHandler(text_filter, bmi_height_handler)],
        },
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /fuel =====
    conv_fuel = ConversationHandler(
        entry_points=[CommandHandler("fuel", fuel_command)],
        states={
            FUEL_DISTANCE_STATE: [MessageHandler(text_filter, fuel_distance_handler)],
            FUEL_CONSUMPTION_STATE: [MessageHandler(text_filter, fuel_consumption_handler)],
            FUEL_PRICE_STATE: [MessageHandler(text_filter, fuel_price_handler)],
        },
        fallbacks=fallbacks,
    )

    # ===== ConversationHandler: /translit =====
    conv_translit = ConversationHandler(
        entry_points=[CommandHandler("translit", translit_command)],
        states={TRANSLATE_STATE: [MessageHandler(text_filter, translit_handler)]},
        fallbacks=fallbacks,
    )

    # ===== Регистрация =====
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_buttons)
    app.add_handler(conv_weather)
    app.add_handler(conv_calc)
    app.add_handler(conv_convert)
    app.add_handler(conv_remind)
    app.add_handler(conv_password)
    app.add_handler(conv_bmi)
    app.add_handler(conv_fuel)
    app.add_handler(conv_translit)

    # Простые команды (без ConversationHandler)
    app.add_handler(CommandHandler("currency", currency_command))
    app.add_handler(CommandHandler("convert_currency", convert_currency_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("shopping", shopping_command))
    app.add_handler(CommandHandler("random", random_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("yesno", yesno_command))
    app.add_handler(CommandHandler("choose", choose_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("worldtime", worldtime_command))
    app.add_handler(CommandHandler("textstats", textstats_command))
    app.add_handler(CommandHandler("mystats", mystats_command))

    # ===== Напоминания (job_queue — каждые 30 сек) =====
    app.job_queue.run_repeating(check_reminders, interval=30, first=5)

    logger.info("✅ Бот «Полезный Помощник» запущен!")
    print()
    print("=" * 55)
    print("  🤖 Полезный Помощник — Telegram Bot")
    print("  ─────────────────────────────────────")
    print("  💰 Валюты    🌤 Погода    🧮 Калькулятор")
    print("  📏 Конвертер  📝 Заметки   🛒 Покупки")
    print("  ⏰ Напоминания  🔐 Пароли  📅 Календарь")
    print("  🎲 Рандом    📊 ИМТ      ⛽ Бензин")
    print("  🔄 Транслит  🌍 Мир. время")
    print("  ─────────────────────────────────────")
    print("  ⏹  Ctrl+C для остановки")
    print("=" * 55)
    print()

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
