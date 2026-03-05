"""
Модуль работы с CoinGecko API
Получение цен криптовалют с кэшированием
"""

import time
import aiohttp
from config import COINGECKO_API, CRYPTO_LIST, CACHE_TTL

# Глобальный кэш цен
_price_cache = {}
_cache_timestamps = {}


async def fetch_prices(vs_currency='usd'):
    """Получить цены всех криптовалют из CoinGecko.
    Кэширует результат на CACHE_TTL секунд."""
    global _price_cache, _cache_timestamps

    now = time.time()
    cache_key = vs_currency

    # Вернуть из кэша если свежий
    if cache_key in _price_cache and now - _cache_timestamps.get(cache_key, 0) < CACHE_TTL:
        return _price_cache[cache_key]

    # Собрать все CoinGecko ID
    ids = ','.join(info['id'] for info in CRYPTO_LIST.values())
    url = f"{COINGECKO_API}/simple/price"
    params = {
        'ids': ids,
        'vs_currencies': vs_currency,
        'include_24hr_change': 'true',
        'include_24hr_vol': 'true',
        'include_market_cap': 'true',
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _price_cache[cache_key] = data
                    _cache_timestamps[cache_key] = now
                    return data
                elif resp.status == 429:
                    # Rate limited — вернуть кэш если есть
                    return _price_cache.get(cache_key)
                return None
    except Exception:
        # При ошибке сети вернуть кэш
        return _price_cache.get(cache_key)


async def get_crypto_price(ticker, vs_currency='usd'):
    """Получить цену конкретной крипты.
    Возвращает dict: ticker, name, price, change_24h, volume, market_cap, currency"""
    crypto = CRYPTO_LIST.get(ticker)
    if not crypto:
        return None

    data = await fetch_prices(vs_currency)
    if not data:
        return None

    coin_data = data.get(crypto['id'], {})
    price = coin_data.get(vs_currency)
    change = coin_data.get(f'{vs_currency}_24h_change', 0)
    volume = coin_data.get(f'{vs_currency}_24h_vol', 0)
    market_cap = coin_data.get(f'{vs_currency}_market_cap', 0)

    return {
        'ticker': ticker,
        'name': crypto['name'],
        'emoji': crypto['emoji'],
        'price': price,
        'change_24h': change or 0,
        'volume': volume or 0,
        'market_cap': market_cap or 0,
        'currency': vs_currency,
    }


async def get_all_prices(vs_currency='usd'):
    """Получить словарь {тикер: цена} для всех криптовалют.
    Используется для проверки алертов."""
    data = await fetch_prices(vs_currency)
    if not data:
        return {}

    result = {}
    for ticker, info in CRYPTO_LIST.items():
        coin_data = data.get(info['id'], {})
        price = coin_data.get(vs_currency)
        if price is not None:
            result[ticker] = price

    return result


def format_price(price, currency='usd'):
    """Красиво отформатировать цену"""
    sym = '$' if currency == 'usd' else '₽'
    if price is None:
        return f"{sym}—"
    if price >= 1000:
        return f"{sym}{price:,.2f}"
    elif price >= 1:
        return f"{sym}{price:.2f}"
    elif price >= 0.001:
        return f"{sym}{price:.6f}"
    else:
        return f"{sym}{price:.10f}"


def format_change(change):
    """Отформатировать изменение за 24ч"""
    if change is None:
        change = 0
    if change > 0:
        return f"📈 +{change:.2f}%"
    elif change < 0:
        return f"📉 {change:.2f}%"
    else:
        return f"➡️ 0.00%"


def format_volume(volume, currency='usd'):
    """Отформатировать объём"""
    sym = '$' if currency == 'usd' else '₽'
    if volume is None or volume == 0:
        return "—"
    if volume >= 1_000_000_000:
        return f"{sym}{volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"{sym}{volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"{sym}{volume / 1_000:.2f}K"
    return f"{sym}{volume:.2f}"


async def fetch_crypto_history(coingecko_id, days=30):
    """Получить историю цен крипты за N дней с CoinGecko.
    Возвращает список дневных цен закрытия (от старых к новым)."""
    url = f"{COINGECKO_API}/coins/{coingecko_id}/market_chart"
    params = {
        'vs_currency': 'usd',
        'days': str(days),
        'interval': 'daily',
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params,
                                   timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    prices = data.get('prices', [])
                    # prices = [[timestamp_ms, price], ...]
                    return [p[1] for p in prices] if prices else []
                return []
    except Exception:
        return []
