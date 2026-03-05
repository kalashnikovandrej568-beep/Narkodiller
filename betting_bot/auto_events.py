"""
Автоматические события бота.
Каждые 5 минут: закрывает старое авто-событие → создаёт новое.
"""

import random
import logging
from database import Database
from events_pool import THEMES, FIGHTER_COUNTS

logger = logging.getLogger(__name__)
db = Database()


def generate_auto_event():
    """Сгенерировать автоматическое событие из пула тем"""
    # Выбрать случайную тему
    theme = random.choice(THEMES)
    
    # Выбрать количество бойцов
    count = random.choice(FIGHTER_COUNTS)
    
    # Убедиться что в теме достаточно бойцов
    available = theme["fighters"]
    if count > len(available):
        count = len(available)
    
    # Выбрать бойцов
    fighters = random.sample(available, count)
    
    # Сгенерировать силу для каждого (1-10, случайно но разная)
    strengths = {}
    for f in fighters:
        strengths[f] = random.randint(1, 10)
    
    # Сгенерировать название
    vs_text = " vs ".join(fighters[:3])
    if count > 3:
        vs_text = " vs ".join(fighters[:2]) + f" и ещё {count - 2}"
    
    template = random.choice(theme["event_templates"])
    title = f"{theme['category']} {template.format(vs=vs_text)}"
    
    return title, fighters, strengths


def create_new_auto_event():
    """Создать новое автоматическое событие в БД"""
    title, fighters, strengths = generate_auto_event()
    
    event_id = db.create_event(
        title=title,
        description="Автоматическое событие бота",
        odds=0,
        participants=fighters,
        strengths=strengths,
        is_auto=True
    )
    
    logger.info(f"🤖 Авто-событие создано: #{event_id} — {title} ({len(fighters)} бойцов)")
    return event_id, title, fighters, strengths


def close_oldest_auto_event():
    """Закрыть самое старое активное авто-событие"""
    events = db.get_events('active', is_auto=True)
    
    if not events:
        return None
    
    # Взять самое старое (последнее в списке, т.к. ORDER BY DESC)
    oldest = events[-1]
    event_id = oldest[0]
    
    # Получить участников и силу
    participants = db.get_event_participants(event_id)
    strengths = db.get_event_strengths(event_id)
    
    if not participants:
        return None
    
    # Выбрать победителя рандомом по силе
    if strengths:
        names = list(strengths.keys())
        weights = list(strengths.values())
    else:
        names = participants
        weights = [1] * len(participants)
    
    winner = random.choices(names, weights=weights, k=1)[0]
    
    # Закрыть
    db.close_event(event_id, winner)
    
    logger.info(f"🏆 Авто-событие #{event_id} закрыто. Победитель: {winner}")
    return event_id, winner


async def auto_event_job(context):
    """Job для планировщика — закрыть старое и создать новое авто-событие"""
    # Закрыть самое старое авто-событие (если есть)
    result = close_oldest_auto_event()
    if result:
        event_id, winner = result
        logger.info(f"Авто-закрытие: #{event_id} → {winner}")
    
    # Создать новое
    event_id, title, fighters, strengths = create_new_auto_event()
    logger.info(f"Авто-создание: #{event_id}")


def ensure_auto_event_exists():
    """При запуске бота — убедиться что есть хотя бы одно авто-событие"""
    events = db.get_events('active', is_auto=True)
    if not events:
        create_new_auto_event()
        logger.info("Создано стартовое авто-событие")
