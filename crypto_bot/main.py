"""
Telegram Крипто-бот
Курсы криптовалют + алерты
Точка входа
"""

import logging
import os
import sys
import asyncio
import time
import traceback
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters
)
from config import (
    BOT_TOKEN,
    ALERT_CURRENCY_STATE, ALERT_CRYPTO_STATE,
    ALERT_DIRECTION_STATE, ALERT_PRICE_STATE,
    DELETE_ALERT_STATE, ALERT_CHECK_INTERVAL,
    TRACKER_ADD_CRYPTO_STATE, TRACKER_SET_THRESHOLD_STATE,
    TRACKER_REMOVE_CRYPTO_STATE, TRACKER_CHECK_INTERVAL,
    CONVERTER_FROM_STATE, CONVERTER_TO_STATE, CONVERTER_AMOUNT_STATE,
    COMPARE_FIRST_STATE, COMPARE_SECOND_STATE,
    CALC_CURRENCY_STATE, CALC_CRYPTO_STATE, CALC_BUY_PRICE_STATE, CALC_AMOUNT_STATE,
    QUIZ_TYPE_STATE, QUIZ_ANSWER_STATE, QUIZ_PRICE_ANSWER_STATE, QUIZ_DIFFICULTY_STATE,
    PROMO_CODE_STATE,
    PORTFOLIO_ASSET_STATE, PORTFOLIO_AMOUNT_STATE,
    PREDICTION_ASSET_STATE,
    ASSET_ANALYSIS_STATE, ASSET_ANALYSIS_MODE_STATE,
    TIME_MACHINE_ASSET_STATE, TIME_MACHINE_AMOUNT_STATE, TIME_MACHINE_DAYS_STATE,
    AUTHOR_PASSWORD_STATE,
)
from handlers import (
    start, handle_message,
    create_alert_start, alert_choose_currency, alert_choose_crypto,
    alert_choose_direction, alert_set_price,
    delete_alert_start, delete_alert_confirm,
    check_alerts_job,
    # Трекер
    tracker_add_start, tracker_add_crypto, tracker_set_threshold,
    tracker_remove_start, tracker_remove_crypto,
    tracker_threshold_start, tracker_threshold_set_all,
    check_tracker_job,
    # Сигналы
    show_signals, show_all_signals, show_portfolio_of_day,
    # Конвертер
    converter_start, converter_choose_from, converter_choose_to, converter_set_amount,
    # Сравнение
    compare_start, compare_choose_first, compare_choose_second,
    # Калькулятор
    calc_start, calc_choose_currency, calc_choose_crypto, calc_set_buy_price, calc_set_amount,
    # Викторина
    quiz_type_start, quiz_choose_type, quiz_choose_difficulty,
    quiz_check_answer, quiz_price_check_answer,
    # Промокоды
    promo_start, promo_activate,
    # Предсказания
    prediction_start, prediction_choose_asset,
    check_predictions_job,
    # Портфель
    portfolio_buy_start, portfolio_sell_start,
    portfolio_choose_asset, portfolio_set_amount,
    # Анализ актива
    asset_analysis_start, asset_analysis_choose_mode, asset_analysis_process,
    # Снайпер входа
    sniper_start,
    # Новые премиум-функции
    show_market_heatmap, show_anomaly_radar,
    time_machine_start, time_machine_choose_asset,
    time_machine_choose_amount, time_machine_result,
    # Режим автора
    author_login_start, author_check_password,
)

# Папка проекта
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(PROJECT_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'crypto_bot.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Главная функция — создание и запуск бота"""

    if sys.platform == 'win32':
        asyncio.set_event_loop(asyncio.new_event_loop())

    application = Application.builder().token(BOT_TOKEN).build()

    # === Команды ===
    application.add_handler(CommandHandler("start", start))

    # === ConversationHandler: создание алерта ===
    alert_create_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Создать алерт$"), create_alert_start)
        ],
        states={
            ALERT_CURRENCY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_choose_currency)
            ],
            ALERT_CRYPTO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_choose_crypto)
            ],
            ALERT_DIRECTION_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_choose_direction)
            ],
            ALERT_PRICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_set_price)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(alert_create_conv)

    # === ConversationHandler: удаление алерта ===
    alert_delete_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^❌ Удалить алерт$"), delete_alert_start)
        ],
        states={
            DELETE_ALERT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_alert_confirm)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(alert_delete_conv)

    # === ConversationHandler: добавить крипту в трекер ===
    tracker_add_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Добавить крипту$"), tracker_add_start)
        ],
        states={
            TRACKER_ADD_CRYPTO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tracker_add_crypto)
            ],
            TRACKER_SET_THRESHOLD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tracker_set_threshold)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(tracker_add_conv)

    # === ConversationHandler: убрать крипту из трекера ===
    tracker_remove_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➖ Убрать крипту$"), tracker_remove_start)
        ],
        states={
            TRACKER_REMOVE_CRYPTO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tracker_remove_crypto)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(tracker_remove_conv)

    # === ConversationHandler: изменить порог трекера ===
    tracker_threshold_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⚙️ Порог оповещения$"), tracker_threshold_start)
        ],
        states={
            TRACKER_SET_THRESHOLD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tracker_threshold_set_all)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(tracker_threshold_conv)

    # === ConversationHandler: конвертер ===
    converter_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔄 Конвертировать$"), converter_start)
        ],
        states={
            CONVERTER_FROM_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, converter_choose_from)
            ],
            CONVERTER_TO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, converter_choose_to)
            ],
            CONVERTER_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, converter_set_amount)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(converter_conv)

    # === ConversationHandler: сравнение ===
    compare_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⚖️ Сравнить$"), compare_start)
        ],
        states={
            COMPARE_FIRST_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, compare_choose_first)
            ],
            COMPARE_SECOND_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, compare_choose_second)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(compare_conv)

    # === ConversationHandler: калькулятор прибыли ===
    calc_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🧮 Рассчитать$"), calc_start)
        ],
        states={
            CALC_CURRENCY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, calc_choose_currency)
            ],
            CALC_CRYPTO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, calc_choose_crypto)
            ],
            CALC_BUY_PRICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, calc_set_buy_price)
            ],
            CALC_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, calc_set_amount)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(calc_conv)

    # === ConversationHandler: крипто-викторина ===
    quiz_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🧠 Крипто-викторина$"), quiz_type_start),
            MessageHandler(filters.Regex("^🧠 Викторина$"), quiz_type_start),
        ],
        states={
            QUIZ_TYPE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_choose_type)
            ],
            QUIZ_DIFFICULTY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_choose_difficulty)
            ],
            QUIZ_ANSWER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_check_answer)
            ],
            QUIZ_PRICE_ANSWER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_price_check_answer)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(quiz_conv)

    # === ConversationHandler: промокоды ===
    promo_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎟 Промокод$"), promo_start)
        ],
        states={
            PROMO_CODE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, promo_activate)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(promo_conv)

    # === ConversationHandler: предсказание цен ===
    prediction_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📈 Вверх!$"), prediction_start),
            MessageHandler(filters.Regex("^📉 Вниз!$"), prediction_start),
        ],
        states={
            PREDICTION_ASSET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, prediction_choose_asset)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(prediction_conv)

    # === ConversationHandler: портфель (покупка) ===
    portfolio_buy_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💰 Купить$"), portfolio_buy_start),
        ],
        states={
            PORTFOLIO_ASSET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, portfolio_choose_asset)
            ],
            PORTFOLIO_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, portfolio_set_amount)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(portfolio_buy_conv)

    # === ConversationHandler: портфель (продажа) ===
    portfolio_sell_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💸 Продать$"), portfolio_sell_start),
        ],
        states={
            PORTFOLIO_ASSET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, portfolio_choose_asset)
            ],
            PORTFOLIO_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, portfolio_set_amount)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(portfolio_sell_conv)

    # === ConversationHandler: анализ актива (Premium) ===
    asset_analysis_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔎 Анализ актива$"), asset_analysis_start),
        ],
        states={
            ASSET_ANALYSIS_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, asset_analysis_choose_mode)
            ],
            ASSET_ANALYSIS_MODE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, asset_analysis_process)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(asset_analysis_conv)

    # === ConversationHandler: машина времени (Premium) ===
    time_machine_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⏳ Машина времени$"), time_machine_start),
        ],
        states={
            TIME_MACHINE_ASSET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_machine_choose_asset)
            ],
            TIME_MACHINE_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_machine_choose_amount)
            ],
            TIME_MACHINE_DAYS_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, time_machine_result)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(time_machine_conv)

    # === ConversationHandler: режим автора ===
    author_conv = ConversationHandler(
        entry_points=[
            CommandHandler("author", author_login_start),
            MessageHandler(filters.Regex("^🔐 Автор$"), author_login_start),
        ],
        states={
            AUTHOR_PASSWORD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, author_check_password)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Отмена$"), start),
            MessageHandler(filters.Regex("^↩️ Назад$"), start),
        ]
    )
    application.add_handler(author_conv)

    # === Обработчик текстовых сообщений (в конце!) ===
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # === Фоновая проверка алертов ===
    application.job_queue.run_repeating(
        check_alerts_job,
        interval=ALERT_CHECK_INTERVAL,
        first=10,  # первая проверка через 10 сек после старта
        name='alert_checker'
    )
    logger.info(f"🔔 Проверка алертов: каждые {ALERT_CHECK_INTERVAL} сек")

    # === Фоновая проверка трекера ===
    application.job_queue.run_repeating(
        check_tracker_job,
        interval=TRACKER_CHECK_INTERVAL,
        first=30,  # первая проверка через 30 сек
        name='tracker_checker'
    )
    logger.info(f"📡 Проверка трекера: каждые {TRACKER_CHECK_INTERVAL} сек")

    # === Фоновая проверка предсказаний ===
    application.job_queue.run_repeating(
        check_predictions_job,
        interval=300,  # каждые 5 минут
        first=60,
        name='prediction_checker'
    )
    logger.info("🎯 Проверка предсказаний: каждые 300 сек")

    # === Запуск ===
    logger.info("📈 Крипто-бот запущен и готов к работе!")
    application.run_polling(drop_pending_updates=True)


def run_with_restart():
    """Запуск бота с автоперезапуском при ошибках"""
    MAX_RETRIES = 50          # максимум перезапусков подряд
    RESTART_DELAY = 5         # пауза перед перезапуском (сек)
    MAX_RESTART_DELAY = 120   # максимальная пауза (сек)

    retries = 0
    last_success = time.time()

    while retries < MAX_RETRIES:
        try:
            logger.info(f"🚀 Запуск бота (попытка #{retries + 1})...")
            main()
        except KeyboardInterrupt:
            logger.info("⛔ Бот остановлен вручную (Ctrl+C)")
            break
        except SystemExit:
            logger.info("⛔ Бот завершён через SystemExit")
            break
        except Exception as e:
            retries += 1
            error_text = traceback.format_exc()
            logger.error(f"💥 ОШИБКА БОТА (попытка #{retries}):\n{error_text}")

            # Если бот проработал >5 минут — сброс счётчика
            uptime = time.time() - last_success
            if uptime > 300:
                retries = 1
                logger.info(f"✅ Бот работал {uptime:.0f} сек — сброс счётчика ошибок")

            # Задержка с нарастанием
            delay = min(RESTART_DELAY * retries, MAX_RESTART_DELAY)
            logger.info(f"🔄 Перезапуск через {delay} сек... ({retries}/{MAX_RETRIES})")
            time.sleep(delay)
            last_success = time.time()
        else:
            # Нормальное завершение (без ошибки)
            logger.info("📈 Бот завершил работу штатно")
            break

    if retries >= MAX_RETRIES:
        logger.critical(f"❌ Превышен лимит перезапусков ({MAX_RETRIES}). Бот остановлен.")


if __name__ == '__main__':
    run_with_restart()
