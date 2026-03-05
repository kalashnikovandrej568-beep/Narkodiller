"""
Telegram-бот с системой ставок
Точка входа приложения
"""

import logging
import os
import asyncio
import sys
import time
import traceback
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters
from config import BOT_TOKEN, ADMIN_PASSWORD_STATE, ADMIN_MENU_STATE, CREATE_EVENT_NAME_STATE, CREATE_EVENT_ODDS_STATE, CREATE_EVENT_PARTICIPANTS_STATE, CREATE_EVENT_STRENGTH_STATE, CLOSE_EVENT_ID_STATE, CLOSE_EVENT_WINNER_STATE, BET_EVENT_ID_STATE, BET_AMOUNT_STATE, BET_RESULT_STATE, TRANSFER_AMOUNT_STATE, TRANSFER_USER_ID_STATE, ROULETTE_BET_STATE, ROULETTE_CHOICE_STATE, COINFLIP_BET_STATE, COINFLIP_CHOICE_STATE, DICE_BET_STATE, BLACKJACK_BET_STATE, BLACKJACK_PLAY_STATE, SLOTS_BET_STATE, CRASH_BET_STATE, CRASH_CHOICE_STATE, BOWLING_BET_STATE, DARTS_BET_STATE, DARTS_CHOICE_STATE, BET_TYPE_STATE, AUTO_EVENT_INTERVAL, OWNER_PASSWORD_STATE, OWNER_MENU_STATE, OWNER_RESET_USER_STATE, MINES_BET_STATE, MINES_PLAY_STATE, WHEEL_BET_STATE, HIGHLOW_BET_STATE, HIGHLOW_PLAY_STATE, RUSSIANR_BET_STATE, RUSSIANR_CHOICE_STATE
from handlers import (
    start, balance, history, leaderboard, help_command, handle_message,
    admin_button, check_admin_password, admin_menu, create_event_name,
    create_event_odds, create_event_participants, create_event_strengths,
    close_event_id, close_event_winner,
    start_bet, bet_type_choice, bet_ask_event_id, bet_ask_amount, bet_ask_result, daily_bonus,
    transfer_amount, transfer_user_id,
    start_roulette, roulette_bet, roulette_choice,
    start_coinflip, coinflip_bet, coinflip_choice,
    start_dice, dice_bet,
    start_blackjack, blackjack_bet, blackjack_play,
    start_slots, slots_bet,
    start_crash, crash_bet, crash_choice,
    start_bowling, bowling_bet,
    start_darts, darts_bet, darts_choice,
    start_mines, mines_bet, mines_play,
    start_wheel, wheel_bet,
    start_highlow, highlow_bet, highlow_play,
    start_russianr, russianr_bet, russianr_choice,
    owner_button, check_owner_password, owner_menu_handler, owner_reset_handler,
    bankrupt_recovery
)
from auto_events import auto_event_job, ensure_auto_event_exists

# Получить путь к папке проекта
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(PROJECT_DIR, 'logs')

# Создать папку logs если её не существует
os.makedirs(LOGS_DIR, exist_ok=True)

# Настройка логирования с UTF-8
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Главная функция - создание и запуск приложения"""
    
    # Для Windows: создать новый event loop
    if sys.platform == 'win32':
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    
    # ConversationHandler для админ-меню
    admin_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^👨‍💼 Админ$"), admin_button)
        ],
        states={
            ADMIN_PASSWORD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password)
            ],
            ADMIN_MENU_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)
            ],
            CREATE_EVENT_NAME_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_name)
            ],
            CREATE_EVENT_ODDS_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_odds)
            ],
            CREATE_EVENT_PARTICIPANTS_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_participants)
            ],
            CREATE_EVENT_STRENGTH_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_event_strengths)
            ],
            CLOSE_EVENT_ID_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, close_event_id)
            ],
            CLOSE_EVENT_WINNER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, close_event_winner)
            ],
            TRANSFER_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_amount)
            ],
            TRANSFER_USER_ID_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_user_id)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Назад в меню$"), start),
            MessageHandler(filters.Regex("^Отмена$"), start)
        ]
    )
    
    application.add_handler(admin_conv_handler)
    
    # ConversationHandler для ставок
    bet_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎲 Ставки$"), start_bet)
        ],
        states={
            BET_TYPE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bet_type_choice)
            ],
            BET_EVENT_ID_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bet_ask_event_id)
            ],
            BET_AMOUNT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bet_ask_amount)
            ],
            BET_RESULT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bet_ask_result)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(bet_conv_handler)
    
    # ConversationHandler для рулетки
    roulette_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎰 Рулетка$"), start_roulette)
        ],
        states={
            ROULETTE_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, roulette_bet)
            ],
            ROULETTE_CHOICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, roulette_choice)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(roulette_conv_handler)
    
    # ConversationHandler для монетки
    coinflip_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🪙 Монетка$"), start_coinflip)
        ],
        states={
            COINFLIP_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, coinflip_bet)
            ],
            COINFLIP_CHOICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, coinflip_choice)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(coinflip_conv_handler)
    
    # ConversationHandler для костей
    dice_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎯 Кости$"), start_dice)
        ],
        states={
            DICE_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dice_bet)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(dice_conv_handler)
    
    # ConversationHandler для блэкджека
    blackjack_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🃏 Блэкджек$"), start_blackjack)
        ],
        states={
            BLACKJACK_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, blackjack_bet)
            ],
            BLACKJACK_PLAY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, blackjack_play)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(blackjack_conv_handler)
    
    # ConversationHandler для слотов
    slots_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🍀 Слоты$"), start_slots)
        ],
        states={
            SLOTS_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, slots_bet)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(slots_conv_handler)
    
    # ConversationHandler для краша
    crash_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🚀 Краш$"), start_crash)
        ],
        states={
            CRASH_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, crash_bet)
            ],
            CRASH_CHOICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, crash_choice)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(crash_conv_handler)
    
    # ConversationHandler для боулинга
    bowling_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎳 Боулинг$"), start_bowling)
        ],
        states={
            BOWLING_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bowling_bet)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(bowling_conv_handler)
    
    # ConversationHandler для дартса
    darts_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎯 Дартс$"), start_darts)
        ],
        states={
            DARTS_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, darts_bet)
            ],
            DARTS_CHOICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, darts_choice)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(darts_conv_handler)
    
    # ConversationHandler для минного поля
    mines_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💣 Минное поле$"), start_mines)
        ],
        states={
            MINES_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mines_bet)
            ],
            MINES_PLAY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mines_play)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(mines_conv_handler)
    
    # ConversationHandler для колеса фортуны
    wheel_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎡 Колесо$"), start_wheel)
        ],
        states={
            WHEEL_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wheel_bet)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(wheel_conv_handler)
    
    # ConversationHandler для Больше/Меньше
    highlow_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📊 Больше/Меньше$"), start_highlow)
        ],
        states={
            HIGHLOW_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, highlow_bet)
            ],
            HIGHLOW_PLAY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, highlow_play)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(highlow_conv_handler)
    
    # ConversationHandler для Русской рулетки
    russianr_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔫 Русская рулетка$"), start_russianr)
        ],
        states={
            RUSSIANR_BET_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, russianr_bet)
            ],
            RUSSIANR_CHOICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, russianr_choice)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Отмена$"), start),
            MessageHandler(filters.Regex("^Назад в меню$"), start)
        ]
    )
    
    application.add_handler(russianr_conv_handler)
    
    # ConversationHandler для хозяина
    owner_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^👑 Хозяин$"), owner_button)
        ],
        states={
            OWNER_PASSWORD_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_owner_password)
            ],
            OWNER_MENU_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_menu_handler)
            ],
            OWNER_RESET_USER_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, owner_reset_handler)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^Назад в меню$"), start),
            MessageHandler(filters.Regex("^Отмена$"), start)
        ]
    )
    
    application.add_handler(owner_conv_handler)
    
    # Обработчик текстовых сообщений (должен быть в конце)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Создать стартовое авто-событие если нет
    ensure_auto_event_exists()
    
    # Планировщик: авто-события каждые 5 минут
    application.job_queue.run_repeating(
        auto_event_job,
        interval=AUTO_EVENT_INTERVAL,
        first=AUTO_EVENT_INTERVAL,
        name='auto_events'
    )
    logger.info(f"⏰ Авто-события: каждые {AUTO_EVENT_INTERVAL} сек")
    
    # Запуск приложения
    logger.info("Бот запущен и готов к работе!")
    application.run_polling(drop_pending_updates=True)


def run_with_restart():
    """Запуск бота с автоперезапуском при ошибках"""
    MAX_RETRIES = 50
    RESTART_DELAY = 5
    MAX_RESTART_DELAY = 120

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

            uptime = time.time() - last_success
            if uptime > 300:
                retries = 1
                logger.info(f"✅ Бот работал {uptime:.0f} сек — сброс счётчика ошибок")

            delay = min(RESTART_DELAY * retries, MAX_RESTART_DELAY)
            logger.info(f"🔄 Перезапуск через {delay} сек... ({retries}/{MAX_RETRIES})")
            time.sleep(delay)
            last_success = time.time()
        else:
            logger.info("💰 Бот завершил работу штатно")
            break

    if retries >= MAX_RETRIES:
        logger.critical(f"❌ Превышен лимит перезапусков ({MAX_RETRIES}). Бот остановлен.")


if __name__ == '__main__':
    run_with_restart()
