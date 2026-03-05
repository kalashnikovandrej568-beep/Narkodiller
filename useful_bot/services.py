"""
Сервисы — API-вызовы и бизнес-логика
Курсы валют ЦБ РФ, погода, калькулятор, конвертер, генераторы и т.д.
"""
import re
import math
import random
import string
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# ===========================
#  КУРСЫ ВАЛЮТ ЦБ РФ
# ===========================

async def get_cbr_rates() -> dict:
    """
    Получить курсы валют с ЦБ РФ (XML API).
    Возвращает dict: {"USD": {"name": ..., "value": ..., "nominal": ...}, ...}
    """
    url = "https://www.cbr.ru/scripts/XML_daily.asp"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return {}
                text = await resp.text(encoding="windows-1251")

        # Парсим XML вручную (без lxml, чтобы не усложнять зависимости)
        rates = {}
        # Каждая валюта в блоке <Valute ...>...</Valute>
        blocks = re.findall(r'<Valute[^>]*>(.*?)</Valute>', text, re.DOTALL)
        for block in blocks:
            code = _xml_tag(block, "CharCode")
            name = _xml_tag(block, "Name")
            nominal = _xml_tag(block, "Nominal")
            value = _xml_tag(block, "Value")
            vunit = _xml_tag(block, "VunitRate")

            if code and value:
                rates[code] = {
                    "name": name or code,
                    "nominal": int(nominal) if nominal else 1,
                    "value": float(value.replace(",", ".")),
                    "vunit": float(vunit.replace(",", ".")) if vunit else None,
                }
        return rates
    except Exception as e:
        logger.error(f"Ошибка получения курсов ЦБ: {e}")
        return {}


def _xml_tag(text: str, tag: str) -> Optional[str]:
    m = re.search(rf'<{tag}>(.*?)</{tag}>', text)
    return m.group(1).strip() if m else None


def format_currency_rates(rates: dict) -> str:
    """Форматирование курсов валют"""
    if not rates:
        return "❌ Не удалось получить курсы валют. Попробуйте позже."

    today = datetime.now().strftime("%d.%m.%Y")

    # Основные валюты
    main = ["USD", "EUR", "CNY", "GBP", "JPY", "TRY", "BYN", "UAH", "KZT", "GEL"]
    crypto_like = ["BTC"]  # ЦБ не даёт крипту, просто для информации

    lines = [f"💰 *Курсы валют ЦБ РФ на {today}*\n"]
    lines.append("─────────────────────────")

    icons = {
        "USD": "🇺🇸", "EUR": "🇪🇺", "CNY": "🇨🇳", "GBP": "🇬🇧",
        "JPY": "🇯🇵", "TRY": "🇹🇷", "BYN": "🇧🇾", "UAH": "🇺🇦",
        "KZT": "🇰🇿", "GEL": "🇬🇪", "CHF": "🇨🇭", "AED": "🇦🇪",
    }

    for code in main:
        if code in rates:
            r = rates[code]
            icon = icons.get(code, "💱")
            nom = f" (за {r['nominal']})" if r['nominal'] != 1 else ""
            lines.append(f"{icon} *{code}*{nom}: `{r['value']:.2f}` ₽")

    # Дополнительные (если есть)
    extra = [c for c in ["CHF", "AED", "CAD", "AUD", "KRW", "INR"] if c in rates]
    if extra:
        lines.append("\n📊 *Дополнительные:*")
        for code in extra:
            r = rates[code]
            icon = icons.get(code, "💱")
            nom = f" (за {r['nominal']})" if r['nominal'] != 1 else ""
            lines.append(f"{icon} *{code}*{nom}: `{r['value']:.2f}` ₽")

    lines.append("\n🔄 Обновление: ежедневно ~12:00 МСК")
    return "\n".join(lines)


# ===========================
#  КОНВЕРТЕР ВАЛЮТ
# ===========================

def convert_currency(amount: float, from_code: str, to_code: str, rates: dict) -> Optional[str]:
    """Конвертация между валютами через рубль"""
    if from_code == "RUB" and to_code == "RUB":
        return f"`{amount:.2f}` ₽ = `{amount:.2f}` ₽"

    if from_code == "RUB":
        if to_code not in rates:
            return None
        r = rates[to_code]
        result = amount / (r["value"] / r["nominal"])
        return f"`{amount:.2f}` ₽ = `{result:.4f}` {to_code}"

    if to_code == "RUB":
        if from_code not in rates:
            return None
        r = rates[from_code]
        result = amount * (r["value"] / r["nominal"])
        return f"`{amount:.2f}` {from_code} = `{result:.2f}` ₽"

    if from_code not in rates or to_code not in rates:
        return None

    r_from = rates[from_code]
    r_to = rates[to_code]
    rub = amount * (r_from["value"] / r_from["nominal"])
    result = rub / (r_to["value"] / r_to["nominal"])
    return f"`{amount:.2f}` {from_code} = `{result:.4f}` {to_code}"


# ===========================
#  ПОГОДА
# ===========================

async def get_weather(city: str, api_key: str = "") -> str:
    """Получить погоду через wttr.in (бесплатно, без ключа)"""
    try:
        url = f"https://wttr.in/{city}?format=j1&lang=ru"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return f"❌ Город «{city}» не найден."
                data = await resp.json(content_type=None)

        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]

        city_name = area.get("areaName", [{}])[0].get("value", city)
        region = area.get("region", [{}])[0].get("value", "")
        country = area.get("country", [{}])[0].get("value", "")

        temp = current.get("temp_C", "?")
        feels = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind_kmph = current.get("windspeedKmph", "0")
        wind_ms = round(int(wind_kmph) / 3.6, 1)
        wind_dir = current.get("winddir16Point", "")
        pressure_mb = current.get("pressure", "0")
        pressure_mmhg = round(int(pressure_mb) * 0.750062, 1)
        desc_ru = current.get("lang_ru", [{}])
        if isinstance(desc_ru, list) and desc_ru:
            desc = desc_ru[0].get("value", "")
        else:
            desc = current.get("weatherDesc", [{}])[0].get("value", "")
        visibility = current.get("visibility", "?")
        uv = current.get("uvIndex", "?")
        cloud = current.get("cloudcover", "?")

        # Иконка погоды
        temp_int = int(temp) if temp != "?" else 0
        if temp_int >= 30:
            icon = "🔥"
        elif temp_int >= 20:
            icon = "☀️"
        elif temp_int >= 10:
            icon = "🌤"
        elif temp_int >= 0:
            icon = "🌥"
        elif temp_int >= -10:
            icon = "❄️"
        else:
            icon = "🥶"

        # Направление ветра RU
        wind_dirs_ru = {
            "N": "С", "NNE": "ССВ", "NE": "СВ", "ENE": "ВСВ",
            "E": "В", "ESE": "ВЮВ", "SE": "ЮВ", "SSE": "ЮЮВ",
            "S": "Ю", "SSW": "ЮЮЗ", "SW": "ЮЗ", "WSW": "ЗЮЗ",
            "W": "З", "WNW": "ЗСЗ", "NW": "СЗ", "NNW": "ССЗ",
        }
        wind_ru = wind_dirs_ru.get(wind_dir, wind_dir)

        # Прогноз на сегодня
        forecast = data.get("weather", [{}])[0]
        max_t = forecast.get("maxtempC", "?")
        min_t = forecast.get("mintempC", "?")
        sunrise = forecast.get("astronomy", [{}])[0].get("sunrise", "?")
        sunset = forecast.get("astronomy", [{}])[0].get("sunset", "?")

        location = city_name
        if region:
            location += f", {region}"
        if country:
            location += f", {country}"

        text = (
            f"{icon} *Погода в {city_name}*\n"
            f"📍 {location}\n"
            f"─────────────────────────\n"
            f"🌡 Температура: *{temp}°C* (ощущается {feels}°C)\n"
            f"📝 {desc}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_ms} м/с ({wind_ru})\n"
            f"🔽 Давление: {pressure_mmhg} мм.рт.ст.\n"
            f"👁 Видимость: {visibility} км\n"
            f"☁️ Облачность: {cloud}%\n"
            f"☀️ UV-индекс: {uv}\n"
            f"─────────────────────────\n"
            f"📊 *Сегодня:* {min_t}°..{max_t}°C\n"
            f"🌅 Восход: {sunrise} | 🌇 Закат: {sunset}\n"
        )

        # 3-дневный прогноз
        weather_days = data.get("weather", [])
        if len(weather_days) >= 3:
            text += "\n📅 *Прогноз:*\n"
            day_names = ["Сегодня", "Завтра", "Послезавтра"]
            for i, day in enumerate(weather_days[:3]):
                day_date = day.get("date", "")
                d_max = day.get("maxtempC", "?")
                d_min = day.get("mintempC", "?")
                d_desc_list = day.get("hourly", [{}])
                # Берём описание в полдень
                noon_desc = ""
                for h in d_desc_list:
                    if h.get("time") in ("1200", "1100", "1300"):
                        lang_ru = h.get("lang_ru", [{}])
                        if isinstance(lang_ru, list) and lang_ru:
                            noon_desc = lang_ru[0].get("value", "")
                        break
                label = day_names[i] if i < len(day_names) else day_date
                text += f"  • *{label}:* {d_min}°..{d_max}°C {noon_desc}\n"

        return text

    except Exception as e:
        logger.error(f"Ошибка погоды: {e}")
        return f"❌ Ошибка получения погоды для «{city}». Проверьте название города."


# ===========================
#  КАЛЬКУЛЯТОР
# ===========================

def safe_calc(expression: str) -> str:
    """Безопасный калькулятор"""
    try:
        # Очищаем
        expr = expression.strip()
        # Заменяем удобные символы
        expr = expr.replace("×", "*").replace("÷", "/").replace(",", ".")
        expr = expr.replace("^", "**")

        # Разрешённые символы
        allowed = set("0123456789+-*/().% ")
        # Разрешённые функции
        funcs = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log10, "ln": math.log,
            "abs": abs, "pi": math.pi, "e": math.e,
            "pow": pow, "round": round,
        }

        # Проверяем на опасные вызовы
        clean = expr
        for fname in funcs:
            clean = clean.replace(fname, "")

        if not all(c in allowed for c in clean):
            return "❌ Некорректное выражение. Допустимы: цифры, +, -, *, /, (, ), sqrt, sin, cos, tan, log, ln, pi, e"

        # Ограничение длины
        if len(expr) > 200:
            return "❌ Слишком длинное выражение (макс 200 символов)."

        result = eval(expr, {"__builtins__": {}}, funcs)

        if isinstance(result, float):
            if result == float('inf') or result == float('-inf'):
                return "❌ Результат: бесконечность"
            if result != result:  # NaN
                return "❌ Результат: не число (NaN)"
            # Красивый вывод
            if result == int(result) and abs(result) < 1e15:
                return f"🧮 `{expression}` = `{int(result)}`"
            return f"🧮 `{expression}` = `{result:.10g}`"
        return f"🧮 `{expression}` = `{result}`"
    except ZeroDivisionError:
        return "❌ Деление на ноль!"
    except Exception as e:
        return f"❌ Ошибка вычисления: `{str(e)[:100]}`"


# ===========================
#  КОНВЕРТЕР ЕДИНИЦ
# ===========================

UNIT_CONVERSIONS = {
    # Длина (всё к метрам)
    "мм": ("длина", 0.001), "см": ("длина", 0.01), "м": ("длина", 1.0),
    "км": ("длина", 1000.0), "дюйм": ("длина", 0.0254), "фут": ("длина", 0.3048),
    "ярд": ("длина", 0.9144), "миля": ("длина", 1609.34),

    # Вес (всё к граммам)
    "мг": ("вес", 0.001), "г": ("вес", 1.0), "кг": ("вес", 1000.0),
    "т": ("вес", 1_000_000.0), "фунт": ("вес", 453.592), "унция": ("вес", 28.3495),

    # Площадь (к кв.м)
    "кв.м": ("площадь", 1.0), "кв.км": ("площадь", 1_000_000.0),
    "га": ("площадь", 10_000.0), "сотка": ("площадь", 100.0),
    "акр": ("площадь", 4046.86), "кв.фут": ("площадь", 0.0929),

    # Объём (к литрам)
    "мл": ("объём", 0.001), "л": ("объём", 1.0), "куб.м": ("объём", 1000.0),
    "галлон": ("объём", 3.78541), "пинта": ("объём", 0.473176),

    # Температура — обработка отдельно
    # Скорость (к м/с)
    "м/с": ("скорость", 1.0), "км/ч": ("скорость", 0.27778),
    "миль/ч": ("скорость", 0.44704), "узел": ("скорость", 0.51444),

    # Данные (к байтам)
    "б": ("данные", 1), "кб": ("данные", 1024), "мб": ("данные", 1048576),
    "гб": ("данные", 1073741824), "тб": ("данные", 1099511627776),
}


def convert_units(expression: str) -> str:
    """
    Конвертер единиц.
    Формат: '100 км в мили' или '100 кг в фунт'
    """
    expr = expression.strip().lower()

    # Температура
    temp_match = re.match(r'([\-\d.]+)\s*(°?[cfкцф])\s*(?:в|to|->)\s*(°?[cfкцф])', expr)
    if temp_match:
        val = float(temp_match.group(1))
        from_u = temp_match.group(2).replace("°", "")
        to_u = temp_match.group(3).replace("°", "")
        return _convert_temp(val, from_u, to_u)

    # Общий формат: число единица в единицу
    m = re.match(r'([\d.]+)\s*(\S+)\s+(?:в|to|->|=>)\s+(\S+)', expr)
    if not m:
        return (
            "❌ Формат: `100 км в мили`\n\n"
            "📏 *Доступные единицы:*\n"
            "• Длина: мм, см, м, км, дюйм, фут, ярд, миля\n"
            "• Вес: мг, г, кг, т, фунт, унция\n"
            "• Площадь: кв.м, кв.км, га, сотка, акр\n"
            "• Объём: мл, л, куб.м, галлон\n"
            "• Скорость: м/с, км/ч, миль/ч, узел\n"
            "• Данные: б, кб, мб, гб, тб\n"
            "• Температура: C, F / Ц, Ф"
        )

    val = float(m.group(1))
    from_u = m.group(2)
    to_u = m.group(3)

    if from_u not in UNIT_CONVERSIONS:
        return f"❌ Неизвестная единица: `{from_u}`"
    if to_u not in UNIT_CONVERSIONS:
        return f"❌ Неизвестная единица: `{to_u}`"

    cat_from, factor_from = UNIT_CONVERSIONS[from_u]
    cat_to, factor_to = UNIT_CONVERSIONS[to_u]

    if cat_from != cat_to:
        return f"❌ Нельзя конвертировать {cat_from} в {cat_to}!"

    base = val * factor_from
    result = base / factor_to

    return f"📏 `{val} {from_u}` = `{result:.6g} {to_u}`"


def _convert_temp(val: float, from_u: str, to_u: str) -> str:
    celsius_aliases = {"c", "ц", "к"}  # к = кельвин? нет, ц = цельсий
    fahr_aliases = {"f", "ф"}

    # Нормализация
    if from_u in {"c", "ц"}:
        from_c = val
    elif from_u in {"f", "ф"}:
        from_c = (val - 32) * 5 / 9
    else:
        return "❌ Допустимо: C/Ц (Цельсий), F/Ф (Фаренгейт)"

    if to_u in {"c", "ц"}:
        result = from_c
    elif to_u in {"f", "ф"}:
        result = from_c * 9 / 5 + 32
    else:
        return "❌ Допустимо: C/Ц (Цельсий), F/Ф (Фаренгейт)"

    return f"🌡 `{val}°{from_u.upper()}` = `{result:.1f}°{to_u.upper()}`"


# ===========================
#  ГЕНЕРАТОР ПАРОЛЕЙ
# ===========================

def generate_password(length: int = 16, use_special: bool = True) -> str:
    """Генерация надёжного пароля"""
    if length < 4:
        length = 4
    if length > 128:
        length = 128

    chars = string.ascii_letters + string.digits
    if use_special:
        chars += "!@#$%&*_+-=?"

    # Гарантируем минимум по одному символу каждого типа
    password = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
    ]
    if use_special:
        password.append(random.choice("!@#$%&*_+-=?"))

    password += [random.choice(chars) for _ in range(length - len(password))]
    random.shuffle(password)
    return "".join(password)


def format_password(pwd: str) -> str:
    """Форматирование пароля"""
    strength = "🟢 Надёжный" if len(pwd) >= 12 else ("🟡 Средний" if len(pwd) >= 8 else "🔴 Слабый")
    return (
        f"🔐 *Сгенерированный пароль:*\n\n"
        f"`{pwd}`\n\n"
        f"📏 Длина: {len(pwd)} символов\n"
        f"💪 Надёжность: {strength}\n\n"
        f"⚠️ Сохраните пароль в надёжном месте!"
    )


# ===========================
#  СЛУЧАЙНОЕ
# ===========================

def random_number(min_val: int = 1, max_val: int = 100) -> str:
    n = random.randint(min_val, max_val)
    return f"🎲 Случайное число ({min_val}–{max_val}): *{n}*"


def coin_flip() -> str:
    result = random.choice(["Орёл 🦅", "Решка 💰"])
    return f"🪙 Подбрасываю монетку...\n\nРезультат: *{result}*"


def yes_or_no() -> str:
    answers = [
        "✅ Да!", "❌ Нет!", "🤔 Скорее да", "😏 Скорее нет",
        "💯 Определённо да!", "🚫 Определённо нет!",
        "🎯 Однозначно!", "🤷 Не уверен...",
        "⭐ Безусловно!", "👎 Вряд ли",
    ]
    return f"🎱 *Магический шар:*\n\n{random.choice(answers)}"


def random_choice(items: list) -> str:
    if not items:
        return "❌ Дайте мне варианты!"
    choice = random.choice(items)
    return f"🎯 *Случайный выбор:*\n\nИз {len(items)} вариантов выбрано:\n\n🏆 *{choice}*"


# ===========================
#  ИМТ (BMI)
# ===========================

def calc_bmi(weight: float, height: float) -> str:
    """Расчёт ИМТ. height в см."""
    if height <= 0 or weight <= 0:
        return "❌ Вес и рост должны быть положительными числами."
    if height > 3:
        height_m = height / 100
    else:
        height_m = height

    bmi = weight / (height_m ** 2)

    if bmi < 16:
        cat = "⚠️ Выраженный дефицит массы"
        color = "🔴"
    elif bmi < 18.5:
        cat = "Недостаточная масса"
        color = "🟡"
    elif bmi < 25:
        cat = "Норма"
        color = "🟢"
    elif bmi < 30:
        cat = "Избыточная масса (предожирение)"
        color = "🟡"
    elif bmi < 35:
        cat = "Ожирение I степени"
        color = "🟠"
    elif bmi < 40:
        cat = "Ожирение II степени"
        color = "🔴"
    else:
        cat = "Ожирение III степени"
        color = "🔴"

    # Нормальный вес
    normal_min = round(18.5 * height_m ** 2, 1)
    normal_max = round(24.9 * height_m ** 2, 1)

    return (
        f"📊 *Индекс массы тела (ИМТ)*\n\n"
        f"⚖️ Вес: {weight} кг\n"
        f"📏 Рост: {height} см\n"
        f"─────────────────────────\n"
        f"📐 *ИМТ: {bmi:.1f}*\n"
        f"{color} Категория: *{cat}*\n\n"
        f"✅ Нормальный вес для вашего роста: {normal_min}–{normal_max} кг\n\n"
        f"ℹ️ ИМТ — ориентировочный показатель."
    )


# ===========================
#  РАСЧЁТ ПОЕЗДКИ
# ===========================

def calc_fuel(distance: float, consumption: float, price: float) -> str:
    """Расчёт стоимости поездки на авто"""
    if distance <= 0 or consumption <= 0 or price <= 0:
        return "❌ Все значения должны быть положительными."

    fuel_needed = distance * consumption / 100
    cost = fuel_needed * price

    return (
        f"⛽ *Расчёт стоимости поездки*\n\n"
        f"📍 Расстояние: {distance} км\n"
        f"🚗 Расход: {consumption} л/100км\n"
        f"💰 Цена топлива: {price} ₽/л\n"
        f"─────────────────────────\n"
        f"⛽ Топлива: *{fuel_needed:.1f} л*\n"
        f"💵 Стоимость: *{cost:.0f} ₽*\n"
        f"\n🔄 Туда и обратно: *{cost * 2:.0f} ₽* ({fuel_needed * 2:.1f} л)"
    )


# ===========================
#  ПРАЗДНИКИ И КАЛЕНДАРЬ
# ===========================

def get_today_info() -> str:
    """Информация о текущем дне"""
    from config import RU_HOLIDAYS

    now = datetime.now()
    today = now.date()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    month_names = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]

    wd = today.weekday()
    weekday_name = weekday_names[wd]
    is_weekend = wd >= 5

    # Сколько дней до выходных
    if wd < 5:
        days_to_weekend = 5 - wd
        weekend_text = f"📅 До выходных: *{days_to_weekend} дн.*"
    else:
        weekend_text = "🎉 *Сегодня выходной!*"

    # Ближайший праздник
    holiday_today = RU_HOLIDAYS.get((today.month, today.day))
    next_holiday = None
    days_to_holiday = None

    for delta in range(1, 366):
        future = today + timedelta(days=delta)
        h = RU_HOLIDAYS.get((future.month, future.day))
        if h:
            next_holiday = h
            days_to_holiday = delta
            break

    # Номер недели
    week_num = today.isocalendar()[1]

    # День года
    day_of_year = today.timetuple().tm_yday
    days_in_year = 366 if (today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)) else 365
    days_left = days_in_year - day_of_year

    # Процент года
    year_pct = round(day_of_year / days_in_year * 100, 1)

    text = (
        f"📅 *{today.day} {month_names[today.month]} {today.year}*\n"
        f"📆 {weekday_name}\n"
        f"─────────────────────────\n"
        f"🕐 Время: {now.strftime('%H:%M:%S')} МСК\n"
        f"📊 Неделя: {week_num} | День: {day_of_year}/{days_in_year}\n"
        f"⏳ Осталось дней в году: {days_left} ({year_pct}% прошло)\n"
        f"{weekend_text}\n"
    )

    if holiday_today:
        text += f"\n🎊 *Сегодня:* {holiday_today}\n"

    if next_holiday and days_to_holiday:
        text += f"🎯 Ближайший праздник через {days_to_holiday} дн.: {next_holiday}\n"

    # Прогресс-бар года
    filled = int(year_pct / 5)
    bar = "▓" * filled + "░" * (20 - filled)
    text += f"\n📊 Прогресс года: [{bar}] {year_pct}%"

    return text


# ===========================
#  ТРАНСЛИТ
# ===========================

TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
    'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def transliterate(text: str) -> str:
    """Транслитерация текста RU → EN"""
    result = []
    for char in text:
        lower = char.lower()
        if lower in TRANSLIT_MAP:
            tr = TRANSLIT_MAP[lower]
            if char.isupper() and tr:
                tr = tr[0].upper() + tr[1:]
            result.append(tr)
        else:
            result.append(char)
    return "".join(result)


def format_translit(original: str) -> str:
    tr = transliterate(original)
    return (
        f"🔄 *Транслитерация:*\n\n"
        f"Оригинал: `{original}`\n"
        f"Результат: `{tr}`"
    )


# ===========================
#  ТЕКСТОВЫЕ УТИЛИТЫ
# ===========================

def text_stats(text: str) -> str:
    """Статистика текста"""
    chars = len(text)
    chars_no_space = len(text.replace(" ", ""))
    words = len(text.split())
    lines = text.count("\n") + 1
    sentences = len(re.findall(r'[.!?]+', text))

    return (
        f"📝 *Статистика текста:*\n\n"
        f"📊 Символов: {chars} (без пробелов: {chars_no_space})\n"
        f"📖 Слов: {words}\n"
        f"📄 Строк: {lines}\n"
        f"💬 Предложений: ~{sentences}\n"
        f"⏱ Чтение: ~{max(1, words // 200)} мин."
    )


# ===========================
#  МИРОВОЕ ВРЕМЯ
# ===========================

def get_world_time() -> str:
    """Время в разных часовых поясах (относительно МСК = UTC+3)"""
    now = datetime.utcnow()

    cities = [
        ("🇷🇺 Москва", 3),
        ("🇷🇺 Новосибирск", 7),
        ("🇷🇺 Владивосток", 10),
        ("🇷🇺 Калининград", 2),
        ("🇷🇺 Екатеринбург", 5),
        ("🇺🇸 Нью-Йорк", -5),
        ("🇺🇸 Лос-Анджелес", -8),
        ("🇬🇧 Лондон", 0),
        ("🇩🇪 Берлин", 1),
        ("🇨🇳 Пекин", 8),
        ("🇯🇵 Токио", 9),
        ("🇦🇪 Дубай", 4),
        ("🇹🇷 Стамбул", 3),
        ("🇮🇳 Дели", 5),  # +5:30, но упрощаем
    ]

    lines = ["🌍 *Мировое время:*\n"]
    for city, offset in cities:
        local = now + timedelta(hours=offset)
        lines.append(f"{city}: `{local.strftime('%H:%M')}` ({local.strftime('%d.%m')})")

    return "\n".join(lines)
