import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле! Создайте .env с BOT_TOKEN=ваш_токен")

# ==================== КРИПТОВАЛЮТЫ ====================
# Тикер → CoinGecko ID + имя
CRYPTO_LIST = {
    # --- ТОП-20 (оригинальные) ---
    'BTC':  {'id': 'bitcoin',              'name': 'Bitcoin',        'emoji': '🟠'},
    'ETH':  {'id': 'ethereum',             'name': 'Ethereum',       'emoji': '🔷'},
    'BNB':  {'id': 'binancecoin',          'name': 'BNB',            'emoji': '🟡'},
    'SOL':  {'id': 'solana',               'name': 'Solana',         'emoji': '🟣'},
    'XRP':  {'id': 'ripple',               'name': 'XRP',            'emoji': '⚪'},
    'ADA':  {'id': 'cardano',              'name': 'Cardano',        'emoji': '🔵'},
    'DOGE': {'id': 'dogecoin',             'name': 'Dogecoin',       'emoji': '🐕'},
    'TON':  {'id': 'the-open-network',     'name': 'Toncoin',        'emoji': '💎'},
    'AVAX': {'id': 'avalanche-2',          'name': 'Avalanche',      'emoji': '🔺'},
    'LINK': {'id': 'chainlink',            'name': 'Chainlink',      'emoji': '🔗'},
    'DOT':  {'id': 'polkadot',             'name': 'Polkadot',       'emoji': '⭕'},
    'NEAR': {'id': 'near',                 'name': 'NEAR Protocol',  'emoji': '🌐'},
    'APT':  {'id': 'aptos',                'name': 'Aptos',          'emoji': '🅰️'},
    'SUI':  {'id': 'sui',                  'name': 'Sui',            'emoji': '🌊'},
    'ATOM': {'id': 'cosmos',               'name': 'Cosmos',         'emoji': '⚛️'},
    'LTC':  {'id': 'litecoin',             'name': 'Litecoin',       'emoji': '🪙'},
    'TRX':  {'id': 'tron',                 'name': 'TRON',           'emoji': '⚡'},
    'MATIC':{'id': 'matic-network',        'name': 'Polygon',        'emoji': '🟪'},
    'UNI':  {'id': 'uniswap',             'name': 'Uniswap',        'emoji': '🦄'},
    'ADI':  {'id': 'adi-token',             'name': 'ADI coin',       'emoji': '🔶'},
    # --- НОВЫЕ 30 (итого 50) ---
    'SHIB': {'id': 'shiba-inu',            'name': 'Shiba Inu',      'emoji': '🐶'},
    'ARB':  {'id': 'arbitrum',             'name': 'Arbitrum',       'emoji': '🔹'},
    'OP':   {'id': 'optimism',             'name': 'Optimism',       'emoji': '🔴'},
    'FIL':  {'id': 'filecoin',             'name': 'Filecoin',       'emoji': '📁'},
    'ALGO': {'id': 'algorand',             'name': 'Algorand',       'emoji': '⬛'},
    'VET':  {'id': 'vechain',              'name': 'VeChain',        'emoji': '✅'},
    'FTM':  {'id': 'fantom',               'name': 'Fantom',         'emoji': '👻'},
    'SAND': {'id': 'the-sandbox',          'name': 'The Sandbox',    'emoji': '🏖️'},
    'MANA': {'id': 'decentraland',         'name': 'Decentraland',   'emoji': '🌍'},
    'AXS':  {'id': 'axie-infinity',        'name': 'Axie Infinity',  'emoji': '🎮'},
    'AAVE': {'id': 'aave',                 'name': 'Aave',           'emoji': '👾'},
    'GRT':  {'id': 'the-graph',            'name': 'The Graph',      'emoji': '📊'},
    'INJ':  {'id': 'injective-protocol',   'name': 'Injective',      'emoji': '💉'},
    'RENDER':{'id': 'render-token',        'name': 'Render',         'emoji': '🎨'},
    'FET':  {'id': 'fetch-ai',             'name': 'Fetch.ai',       'emoji': '🤖'},
    'PEPE': {'id': 'pepe',                 'name': 'Pepe',           'emoji': '🐸'},
    'WIF':  {'id': 'dogwifhat',            'name': 'dogwifhat',      'emoji': '🎩'},
    'BONK': {'id': 'bonk',                 'name': 'Bonk',           'emoji': '🦴'},
    'FLOKI':{'id': 'floki',                'name': 'Floki',          'emoji': '⚔️'},
    'CRO':  {'id': 'crypto-com-chain',     'name': 'Cronos',         'emoji': '🏛️'},
    'IMX':  {'id': 'immutable-x',          'name': 'Immutable',      'emoji': '🛡️'},
    'SEI':  {'id': 'sei-network',          'name': 'Sei',            'emoji': '🌀'},
    'STX':  {'id': 'blockstack',           'name': 'Stacks',         'emoji': '📚'},
    'RUNE': {'id': 'thorchain',            'name': 'THORChain',      'emoji': '⚡'},
    'EGLD': {'id': 'elrond-erd-2',         'name': 'MultiversX',     'emoji': '✨'},
    'XLM':  {'id': 'stellar',              'name': 'Stellar',        'emoji': '⭐'},
    'HBAR': {'id': 'hedera-hashgraph',     'name': 'Hedera',         'emoji': '♯'},
    'ICP':  {'id': 'internet-computer',    'name': 'Internet Computer','emoji': '🖥️'},
    'EOS':  {'id': 'eos',                  'name': 'EOS',            'emoji': '🔵'},
    'THETA':{'id': 'theta-token',          'name': 'Theta',          'emoji': '📺'},
}

# ==================== СОСТОЯНИЯ CONVERSATIONHANDLER ====================
# Алерты
ALERT_CURRENCY_STATE = 1
ALERT_CRYPTO_STATE = 2
ALERT_DIRECTION_STATE = 3
ALERT_PRICE_STATE = 4
DELETE_ALERT_STATE = 5

# Трекер
TRACKER_ADD_CRYPTO_STATE = 10
TRACKER_SET_THRESHOLD_STATE = 11
TRACKER_REMOVE_CRYPTO_STATE = 12

# Конвертер
CONVERTER_FROM_STATE = 20
CONVERTER_TO_STATE = 21
CONVERTER_AMOUNT_STATE = 22

# Сравнение
COMPARE_FIRST_STATE = 25
COMPARE_SECOND_STATE = 26

# Калькулятор прибыли
CALC_CURRENCY_STATE = 29
CALC_CRYPTO_STATE = 30
CALC_BUY_PRICE_STATE = 31
CALC_AMOUNT_STATE = 32

# Викторина
QUIZ_TYPE_STATE = 34
QUIZ_ANSWER_STATE = 35
QUIZ_PRICE_ANSWER_STATE = 36
QUIZ_DIFFICULTY_STATE = 37

# Промокоды
PROMO_CODE_STATE = 40

# Портфель
PORTFOLIO_ACTION_STATE = 50
PORTFOLIO_ASSET_STATE = 51
PORTFOLIO_AMOUNT_STATE = 52

# Предсказание
PREDICTION_ASSET_STATE = 55

# Анализ конкретного актива (Premium)
ASSET_ANALYSIS_STATE = 60
ASSET_ANALYSIS_MODE_STATE = 61

# Снайпер входа (Premium)
SNIPER_STATE = 65

# Машина времени (Premium)
TIME_MACHINE_ASSET_STATE = 70
TIME_MACHINE_AMOUNT_STATE = 71
TIME_MACHINE_DAYS_STATE = 72

# Режим автора
AUTHOR_PASSWORD_STATE = 80

# ==================== НАСТРОЙКИ ====================
ALERT_CHECK_INTERVAL = 60       # Проверка алертов каждые 60 сек
TRACKER_CHECK_INTERVAL = 120    # Проверка трекера каждые 2 мин
TRACKER_COOLDOWN = 14400        # Кулдаун уведомлений трекера: 4 часа (не спамить)
COINGECKO_API = 'https://api.coingecko.com/api/v3'
CACHE_TTL = 30  # Кэш цен на 30 секунд
DATABASE_PATH = 'crypto_bot.db'

# Пороги для выбора кнопками
THRESHOLD_OPTIONS = [3, 5, 7, 10, 15, 20, 25, 30]

# ==================== ПОДПИСКИ ====================
# Бесплатные крипты (10 штук)
FREE_CRYPTOS = ['BTC', 'ETH', 'SOL', 'BNB', 'ADI', 'DOGE', 'XRP', 'PEPE', 'SHIB', 'TON']

# Pro крипты (30 штук — включая бесплатные)
PRO_CRYPTOS = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'TON',
               'AVAX', 'LINK', 'DOT', 'NEAR', 'LTC', 'TRX', 'ADI',
               'SHIB', 'ARB', 'OP', 'FIL', 'ALGO', 'VET', 'FTM',
               'PEPE', 'BONK', 'FLOKI', 'WIF', 'CRO', 'XLM', 'HBAR', 'EOS']

# Premium — все 50

# ==================== АКЦИИ ====================
# Тикер → name + emoji (id = тикер, для совместимости с crypto handlers)
STOCKS_LIST = {
    # --- US Tech ---
    'AAPL':   {'id': 'AAPL',  'name': 'Apple',            'emoji': '🍎'},
    'MSFT':   {'id': 'MSFT',  'name': 'Microsoft',        'emoji': '🪟'},
    'GOOG':   {'id': 'GOOG',  'name': 'Alphabet',         'emoji': '🔍'},
    'AMZN':   {'id': 'AMZN',  'name': 'Amazon',           'emoji': '📦'},
    'META':   {'id': 'META',  'name': 'Meta',             'emoji': '👤'},
    'NVDA':   {'id': 'NVDA',  'name': 'NVIDIA',           'emoji': '🟢'},
    'TSLA':   {'id': 'TSLA',  'name': 'Tesla',            'emoji': '🚗'},
    'NFLX':   {'id': 'NFLX',  'name': 'Netflix',          'emoji': '🎬'},
    'AMD':    {'id': 'AMD',   'name': 'AMD',              'emoji': '💻'},
    'INTC':   {'id': 'INTC',  'name': 'Intel',            'emoji': '🔲'},
    'CRM':    {'id': 'CRM',   'name': 'Salesforce',       'emoji': '☁️'},
    'ORCL':   {'id': 'ORCL',  'name': 'Oracle',           'emoji': '🗄️'},
    'ADBE':   {'id': 'ADBE',  'name': 'Adobe',            'emoji': '🎨'},
    'PYPL':   {'id': 'PYPL',  'name': 'PayPal',           'emoji': '💳'},
    'UBER':   {'id': 'UBER',  'name': 'Uber',             'emoji': '🚕'},
    'SNAP':   {'id': 'SNAP',  'name': 'Snap',             'emoji': '👻'},
    'SPOT':   {'id': 'SPOT',  'name': 'Spotify',          'emoji': '🎵'},
    'SQ':     {'id': 'SQ',    'name': 'Block',            'emoji': '⬛'},
    'SHOP':   {'id': 'SHOP',  'name': 'Shopify',          'emoji': '🛒'},
    'PLTR':   {'id': 'PLTR',  'name': 'Palantir',         'emoji': '🔭'},
    # --- US Finance ---
    'JPM':    {'id': 'JPM',   'name': 'JPMorgan',         'emoji': '🏦'},
    'BAC':    {'id': 'BAC',   'name': 'Bank of America',  'emoji': '🏛️'},
    'GS':     {'id': 'GS',    'name': 'Goldman Sachs',    'emoji': '💰'},
    'V':      {'id': 'V',     'name': 'Visa',             'emoji': '💙'},
    'MA':     {'id': 'MA',    'name': 'Mastercard',       'emoji': '💎'},
    # --- US Consumer ---
    'DIS':    {'id': 'DIS',   'name': 'Disney',           'emoji': '🏰'},
    'NKE':    {'id': 'NKE',   'name': 'Nike',             'emoji': '👟'},
    'KO':     {'id': 'KO',    'name': 'Coca-Cola',        'emoji': '🥤'},
    'MCD':    {'id': 'MCD',   'name': 'McDonalds',        'emoji': '🍔'},
    'WMT':    {'id': 'WMT',   'name': 'Walmart',          'emoji': '🏪'},
    'PG':     {'id': 'PG',    'name': 'Procter & Gamble', 'emoji': '🧴'},
    'PEP':    {'id': 'PEP',   'name': 'PepsiCo',          'emoji': '🥂'},
    # --- US Healthcare ---
    'JNJ':    {'id': 'JNJ',   'name': 'Johnson & Johnson','emoji': '💊'},
    'UNH':    {'id': 'UNH',   'name': 'UnitedHealth',     'emoji': '🏥'},
    'PFE':    {'id': 'PFE',   'name': 'Pfizer',           'emoji': '💉'},
    'MRNA':   {'id': 'MRNA',  'name': 'Moderna',          'emoji': '🧬'},
    # --- Energy ---
    'XOM':    {'id': 'XOM',   'name': 'ExxonMobil',       'emoji': '⛽'},
    'CVX':    {'id': 'CVX',   'name': 'Chevron',          'emoji': '🛢️'},
    # --- International ---
    'BABA':   {'id': 'BABA',  'name': 'Alibaba',          'emoji': '🇨🇳'},
    'TSM':    {'id': 'TSM',   'name': 'TSMC',             'emoji': '🇹🇼'},
    'SONY':   {'id': 'SONY',  'name': 'Sony',             'emoji': '🎧'},
    'TM':     {'id': 'TM',    'name': 'Toyota',           'emoji': '🇯🇵'},
    'NVO':    {'id': 'NVO',   'name': 'Novo Nordisk',     'emoji': '🩺'},
    # --- ETFs ---
    'SPY':    {'id': 'SPY',   'name': 'S&P 500 ETF',     'emoji': '📊'},
    'QQQ':    {'id': 'QQQ',   'name': 'NASDAQ 100 ETF',  'emoji': '📈'},
    # --- Industrial ---
    'BA':     {'id': 'BA',    'name': 'Boeing',           'emoji': '✈️'},
    'CAT':    {'id': 'CAT',   'name': 'Caterpillar',      'emoji': '🚜'},
    'DE':     {'id': 'DE',    'name': 'Deere',            'emoji': '🌾'},
    'LMT':    {'id': 'LMT',   'name': 'Lockheed Martin', 'emoji': '🚀'},
    'RTX':    {'id': 'RTX',   'name': 'RTX Corp',         'emoji': '🛡️'},
}

# Бесплатные акции (10 штук)
FREE_STOCKS = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX', 'SPY', 'QQQ']

# Pro акции (30 штук)
PRO_STOCKS = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'AMD', 'INTC',
              'CRM', 'ORCL', 'ADBE', 'PYPL', 'UBER', 'JPM', 'BAC', 'GS', 'V', 'MA',
              'DIS', 'NKE', 'KO', 'MCD', 'WMT', 'SPY', 'QQQ', 'BA', 'XOM', 'JNJ']

# Premium — все 50

# ==================== ПРОМОКОДЫ ====================
PROMO_CODES = {
    'CRYPTOPRO7': {'tier': 'pro', 'days': 7, 'desc': 'Pro на 7 дней'},
    'PROFOREVER': {'tier': 'pro', 'days': None, 'desc': 'Pro навсегда'},
    'PREMIUMFOREVER': {'tier': 'premium', 'days': None, 'desc': 'Premium навсегда'},
}
