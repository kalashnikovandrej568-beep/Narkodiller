"""
Модуль работы с Yahoo Finance через yfinance
Получение цен акций с кэшированием

Формат данных совместим с crypto_api.py для переиспользования
обработчиков в handlers.py
"""

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import STOCKS_LIST

# Настройки кэша
STOCK_CACHE_TTL = 60  # Обновлять раз в 60 сек
_price_cache = {}
_price_cache_time = 0
_usd_rub_rate = None
_usd_rub_time = 0
USD_RUB_TTL = 300  # Курс USD/RUB обновлять раз в 5 мин
_executor = ThreadPoolExecutor(max_workers=2)


def _fetch_all_sync():
    """Синхронная пакетная загрузка цен через yfinance.
    Запускается в executor для неблокирующей работы.
    """
    import yfinance as yf

    tickers = list(STOCKS_LIST.keys())
    if not tickers:
        return {}

    result = {}

    try:
        # Пакетная загрузка за 5 дней (для расчёта изменения)
        data = yf.download(
            tickers,
            period='5d',
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by='ticker'
        )

        if data.empty:
            return {}

        for ticker in tickers:
            try:
                # Для одного тикера — без группировки
                if len(tickers) == 1:
                    td = data
                else:
                    td = data[ticker]

                # Цены закрытия
                closes = td['Close'].dropna()
                if closes.empty:
                    continue

                current = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) > 1 else current

                # Объём
                vols = td['Volume'].dropna()
                volume = float(vols.iloc[-1]) if not vols.empty else 0

                # Изменение за день (%)
                change = ((current - prev) / prev * 100) if prev else 0

                # Формат совместим с CoinGecko (используется в handlers)
                result[ticker] = {
                    'usd': current,
                    'usd_24h_change': round(change, 2),
                    'usd_24h_vol': round(volume * current, 2),
                    'usd_market_cap': 0,
                }
            except Exception:
                continue
    except Exception:
        pass

    return result


def _fetch_usd_rub_sync():
    """Получить курс USD/RUB через yfinance"""
    import yfinance as yf
    try:
        data = yf.download('USDRUB=X', period='1d', auto_adjust=True, progress=False)
        if not data.empty:
            return float(data['Close'].dropna().iloc[-1])
    except Exception:
        pass
    return None


async def get_usd_rub_rate():
    """Получить курс USD/RUB с кэшированием"""
    global _usd_rub_rate, _usd_rub_time
    now = time.time()
    if _usd_rub_rate and now - _usd_rub_time < USD_RUB_TTL:
        return _usd_rub_rate
    loop = asyncio.get_event_loop()
    rate = await loop.run_in_executor(_executor, _fetch_usd_rub_sync)
    if rate:
        _usd_rub_rate = rate
        _usd_rub_time = now
    return _usd_rub_rate or 90.0  # fallback


async def fetch_prices(vs_currency='usd'):
    """Получить цены всех акций (с кэшированием).

    Формат ответа совместим с crypto_api.fetch_prices():
    vs_currency='usd': {ticker: {'usd': price, 'usd_24h_change': %, 'usd_24h_vol': $, 'usd_market_cap': $}}
    vs_currency='rub': {ticker: {'rub': price, 'rub_24h_change': %, 'rub_24h_vol': ₽, 'rub_market_cap': ₽}}
    """
    global _price_cache, _price_cache_time

    now = time.time()
    if not _price_cache or now - _price_cache_time >= STOCK_CACHE_TTL:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _fetch_all_sync)
        if result:
            _price_cache = result
            _price_cache_time = now

    usd_data = _price_cache or {}

    if vs_currency == 'rub':
        rate = await get_usd_rub_rate()
        rub_data = {}
        for ticker, d in usd_data.items():
            rub_data[ticker] = {
                'rub': round(d['usd'] * rate, 2),
                'rub_24h_change': d['usd_24h_change'],
                'rub_24h_vol': round(d['usd_24h_vol'] * rate, 2),
                'rub_market_cap': round(d['usd_market_cap'] * rate, 2),
            }
        return rub_data

    return usd_data


async def get_stock_price(ticker, vs_currency='usd'):
    """Получить данные конкретной акции.

    Возвращает dict совместимый с crypto_api.get_crypto_price():
    {ticker, name, emoji, price, change_24h, volume, market_cap, currency}
    """
    stock = STOCKS_LIST.get(ticker)
    if not stock:
        return None

    data = await fetch_prices(vs_currency)
    if not data or ticker not in data:
        return None

    c = vs_currency
    d = data[ticker]
    return {
        'ticker': ticker,
        'name': stock['name'],
        'emoji': stock['emoji'],
        'price': d.get(c, 0),
        'change_24h': d.get(f'{c}_24h_change', 0),
        'volume': d.get(f'{c}_24h_vol', 0),
        'market_cap': d.get(f'{c}_market_cap', 0),
        'currency': c,
    }


async def get_all_prices(vs_currency='usd'):
    """Получить {тикер: цена} для всех акций.
    Совместимо с crypto_api.get_all_prices()
    """
    data = await fetch_prices(vs_currency)
    c = vs_currency
    return {t: d.get(c, 0) for t, d in data.items()} if data else {}


def _fetch_stock_history_sync(ticker, days=30):
    """Синхронная загрузка истории акции через yfinance"""
    import yfinance as yf
    try:
        period = '1mo' if days <= 30 else '3mo' if days <= 90 else '1y'
        data = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if data.empty:
            return []
        closes = data['Close'].dropna().tolist()
        return [float(c) for c in closes]
    except Exception:
        return []


async def fetch_stock_history(ticker, days=30):
    """Получить историю цен акции за N дней.
    Возвращает список дневных цен закрытия (от старых к новым)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _fetch_stock_history_sync, ticker, days)
