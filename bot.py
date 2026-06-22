import os
import time
import math
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from decimal import Decimal, ROUND_DOWN
from datetime import datetime

# ============================================================
# SAFE BTC/TRY PAPER BOT v1 - BINANCE TR
# ------------------------------------------------------------
# Bu sürüm GERÇEK EMİR VERMEZ.
# Sadece:
# - Binance TR bağlantısı
# - Hesap bakiyesi kontrolü
# - BTC/TRY 15m veri çekme
# - EMA20 / EMA50 / RSI sinyali
# - Paper trade (simülasyon)
# - Stop / TP / günlük limit
# ============================================================

# =========================
# ENV / SETTINGS
# =========================
API_KEY = os.environ.get("TRBINANCE_API_KEY", "")
API_SECRET = os.environ.get("TRBINANCE_API_SECRET", "")

# Binance TR
BASE_URL = "https://www.binance.tr"

# Market data (Binance TR docs: symbolType=1 / main symbols -> api.binance.me)
MARKET_BASE_URL = "https://api.binance.me"

# İşlem sembolü
SYMBOL = "BTCTRY"   # market-data endpoint için underscore'suz
ORDER_SYMBOL = "BTC_TRY"  # order/account tarafında çoğu yerde underscore'lu format kullanılır

# Strateji ayarları
INTERVAL = "15m"
KLINE_LIMIT = 200

EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14

ENTRY_RSI_MIN = 45
ENTRY_RSI_MAX = 68

TP_PCT = 0.011      # %1.1 take profit
SL_PCT = 0.007      # %0.7 stop loss
MAX_POSITION_TRY = 3000.0   # paper işlemde kullanılacak TRY tutarı
MAX_DAILY_TRADES = 3
MAX_CONSECUTIVE_LOSSES = 2
MAX_DAILY_LOSS_PCT = 0.015  # günlük -%1.5'te bot dursun

LOOP_SECONDS = 60           # her 60 sn kontrol
RECV_WINDOW = 5000

# Güvenlik
REQUEST_TIMEOUT = 15
DEBUG = True


# ============================================================
# STATE
# ============================================================
paper_state = {
    "in_position": False,
    "entry_price": None,
    "quantity": None,
    "stop_price": None,
    "take_profit": None,
    "entry_time": None,
}

daily_state = {
    "date": None,
    "trade_count": 0,
    "consecutive_losses": 0,
    "realized_pnl_try": 0.0,
    "starting_capital_assumption": 20000.0,  # günlük zarar yüzdesi hesabı için referans
}

# ============================================================
# HELPERS
# ============================================================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default


def reset_daily_if_needed():
    today = datetime.now().date().isoformat()
    if daily_state["date"] != today:
        daily_state["date"] = today
        daily_state["trade_count"] = 0
        daily_state["consecutive_losses"] = 0
        daily_state["realized_pnl_try"] = 0.0
        log(f"Gün resetlendi: {today}")


def daily_loss_limit_hit():
    base = daily_state["starting_capital_assumption"]
    if base <= 0:
        return False
    return daily_state["realized_pnl_try"] <= -(base * MAX_DAILY_LOSS_PCT)


def trading_blocked():
    if daily_state["trade_count"] >= MAX_DAILY_TRADES:
        log("Günlük maksimum işlem sayısına ulaşıldı.")
        return True
    if daily_state["consecutive_losses"] >= MAX_CONSECUTIVE_LOSSES:
        log("Arka arkaya maksimum zarar sayısına ulaşıldı.")
        return True
    if daily_loss_limit_hit():
        log("Günlük zarar limiti aşıldı.")
        return True
    return False


# ============================================================
# BINANCE TR AUTH / REQUESTS
# ============================================================
def sign_params(params: dict, secret_key: str) -> str:
    query = urlencode(params)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{query}&signature={signature}"


def get_server_time():
    url = f"{BASE_URL}/open/v1/common/time"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise Exception(f"Server time error: {data}")
    return data["timestamp"]


def signed_get(path: str, params=None):
    if params is None:
        params = {}

    timestamp = get_server_time()
    params["timestamp"] = timestamp
    params["recvWindow"] = RECV_WINDOW

    signed_query = sign_params(params, API_SECRET)
    url = f"{BASE_URL}{path}?{signed_query}"

    headers = {
        "X-MBX-APIKEY": API_KEY
    }

    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise Exception(f"Signed GET error: {data}")
    return data


def signed_post(path: str, params=None):
    """
    Şimdilik canlı emir kullanmıyoruz ama ileride lazım olacak.
    """
    if params is None:
        params = {}

    timestamp = get_server_time()
    params["timestamp"] = timestamp
    params["recvWindow"] = RECV_WINDOW

    signed_query = sign_params(params, API_SECRET)
    url = f"{BASE_URL}{path}"

    headers = {
        "X-MBX-APIKEY": API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    r = requests.post(url, headers=headers, data=signed_query, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise Exception(f"Signed POST error: {data}")
    return data


# ============================================================
# ACCOUNT / MARKET DATA
# ============================================================
def get_account_info():
    """
    Binance TR docs:
    GET /open/v1/account/spot
    """
    return signed_get("/open/v1/account/spot")


def get_try_balance(account_data):
    data = account_data.get("data", {})
    assets = data.get("accountAssets", [])
    for a in assets:
        if a.get("asset") == "TRY":
            return safe_float(a.get("free", 0))
    return 0.0


def get_btc_balance(account_data):
    data = account_data.get("data", {})
    assets = data.get("accountAssets", [])
    for a in assets:
        if a.get("asset") == "BTC":
            return safe_float(a.get("free", 0))
    return 0.0


def get_symbol_info():
    """
    Symbol filtreleri için:
    GET /open/v1/common/symbols
    """
    url = f"{BASE_URL}/open/v1/common/symbols"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise Exception(f"Symbol info error: {data}")

    symbols = data.get("data", {}).get("list", [])
    for s in symbols:
        # BTC_TRY formatını arıyoruz
        if s.get("symbol") == ORDER_SYMBOL:
            return s
    raise Exception(f"{ORDER_SYMBOL} sembolü symbol listesinde bulunamadı.")


def get_klines(symbol=SYMBOL, interval=INTERVAL, limit=KLINE_LIMIT):
    """
    Binance TR docs:
    MBX / main symbol için kline endpoint:
    GET https://api.binance.me/api/v1/klines
    symbol parametresi underscore'suz örn BTCTRY
    """
    url = f"{MARKET_BASE_URL}/api/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    # Bu endpoint bazı durumlarda {"code":0,"data":[...]} dönebilir,
    # bazı durumlarda direkt liste dönebilir. İkisini de destekleyelim.
    if isinstance(data, dict):
        if data.get("code") != 0:
            raise Exception(f"Kline error: {data}")
        rows = data.get("data", [])
    elif isinstance(data, list):
        rows = data
    else:
        raise Exception(f"Beklenmeyen kline formatı: {data}")

    candles = []
    for row in rows:
        candles.append({
            "open_time": int(row[0]),
            "open": safe_float(row[1]),
            "high": safe_float(row[2]),
            "low": safe_float(row[3]),
            "close": safe_float(row[4]),
            "volume": safe_float(row[5]),
            "close_time": int(row[6]),
        })
    return candles


# ============================================================
# INDICATORS
# ============================================================
def ema(values, period):
    if len(values) < period:
        return []

    multiplier = 2 / (period + 1)
    ema_values = []

    # ilk EMA için SMA kullan
    sma = sum(values[:period]) / period
    ema_values = [None] * (period - 1)
    ema_values.append(sma)

    prev = sma
    for price in values[period:]:
        current = (price - prev) * multiplier + prev
        ema_values.append(current)
        prev = current

    return ema_values


def rsi(values, period=14):
    if len(values) < period + 1:
        return []

    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsis = [None] * period

    if avg_loss == 0:
        rs = 999999
    else:
        rs = avg_gain / avg_loss
    rsis.append(100 - (100 / (1 + rs)))

    for i in range(period, len(deltas)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

        if avg_loss == 0:
            rs = 999999
            current_rsi = 100
        else:
            rs = avg_gain / avg_loss
            current_rsi = 100 - (100 / (1 + rs))

        rsis.append(current_rsi)

    return rsis


# ============================================================
# STRATEGY
# ============================================================
def build_signal(candles):
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    ema_fast = ema(closes, EMA_FAST)
    ema_slow = ema(closes, EMA_SLOW)
    rsi_vals = rsi(closes, RSI_PERIOD)

    if len(closes) < max(EMA_SLOW, RSI_PERIOD) + 2:
        return {
            "signal": "HOLD",
            "reason": "Yetersiz veri"
        }

    i = len(closes) - 1
    prev_i = i - 1

    price = closes[i]
    prev_price = closes[prev_i]

    ef = ema_fast[i]
    es = ema_slow[i]
    ef_prev = ema_fast[prev_i]
    es_prev = ema_slow[prev_i]
    r = rsi_vals[i]
    r_prev = rsi_vals[prev_i]

    if None in [ef, es, ef_prev, es_prev, r, r_prev]:
        return {
            "signal": "HOLD",
            "reason": "Indikatörler henüz hazır değil"
        }

    # Trend filtresi
    trend_up = ef > es

    # Fiyat EMA20'den çok uzak olmasın
    distance_from_ema = abs(price - ef) / ef if ef else 999

    # Son mum yeşil mi?
    current_candle = candles[i]
    prev_candle = candles[prev_i]
    green_candle = current_candle["close"] > current_candle["open"]

    # Basit momentum teyidi
    breakout_prev_high = current_candle["close"] > prev_candle["high"]

    # Geri çekilme sonrası toparlanma benzeri bir yapı
    # son 3 mumun en düşüklerine yakın geri çekilme sonrası EMA20 üstünde kalma
    last3_lows = [c["low"] for c in candles[-3:]]
    pullback_ok = min(last3_lows) <= ef * 1.003

    buy_conditions = [
        trend_up,
        distance_from_ema <= 0.0045,       # %0.45'ten fazla uzaklaşmasın
        ENTRY_RSI_MIN <= r <= ENTRY_RSI_MAX,
        r > r_prev,
        green_candle,
        pullback_ok
    ]

    if all(buy_conditions):
        return {
            "signal": "BUY",
            "price": price,
            "ema_fast": ef,
            "ema_slow": es,
            "rsi": r,
            "reason": "EMA20>EMA50 + RSI toparlanıyor + geri çekilme sonrası yeşil kapanış"
        }

    return {
        "signal": "HOLD",
        "price": price,
        "ema_fast": ef,
        "ema_slow": es,
        "rsi": r,
        "reason": "Koşullar tam oluşmadı"
    }


# ============================================================
# PAPER TRADE ENGINE
# ============================================================
def paper_buy(price):
    if paper_state["in_position"]:
        return

    qty = MAX_POSITION_TRY / price
    stop_price = price * (1 - SL_PCT)
    take_profit = price * (1 + TP_PCT)

    paper_state["in_position"] = True
    paper_state["entry_price"] = price
    paper_state["quantity"] = qty
    paper_state["stop_price"] = stop_price
    paper_state["take_profit"] = take_profit
    paper_state["entry_time"] = datetime.now().isoformat()

    daily_state["trade_count"] += 1

    log("=== PAPER BUY ===")
    log(f"Giriş fiyatı: {price:,.2f} TRY")
    log(f"Miktar: {qty:.8f} BTC")
    log(f"Stop: {stop_price:,.2f}")
    log(f"TP: {take_profit:,.2f}")


def paper_sell(price, reason="EXIT"):
    if not paper_state["in_position"]:
        return

    entry = paper_state["entry_price"]
    qty = paper_state["quantity"]
    pnl = (price - entry) * qty

    daily_state["realized_pnl_try"] += pnl

    if pnl < 0:
        daily_state["consecutive_losses"] += 1
    else:
        daily_state["consecutive_losses"] = 0

    log(f"=== PAPER SELL / {reason} ===")
    log(f"Çıkış fiyatı: {price:,.2f} TRY")
    log(f"Giriş fiyatı: {entry:,.2f} TRY")
    log(f"Miktar: {qty:.8f} BTC")
    log(f"PnL: {pnl:,.2f} TRY")
    log(f"Günlük realize PnL: {daily_state['realized_pnl_try']:,.2f} TRY")

    paper_state["in_position"] = False
    paper_state["entry_price"] = None
    paper_state["quantity"] = None
    paper_state["stop_price"] = None
    paper_state["take_profit"] = None
    paper_state["entry_time"] = None


def manage_open_position(last_price, ema_fast_value=None):
    if not paper_state["in_position"]:
        return

    stop_price = paper_state["stop_price"]
    take_profit = paper_state["take_profit"]

    if last_price <= stop_price:
        paper_sell(last_price, reason="STOP_LOSS")
        return

    if last_price >= take_profit:
        paper_sell(last_price, reason="TAKE_PROFIT")
        return

    # ekstra güvenlik: fiyat EMA20 altına kaydıysa erken çık
    if ema_fast_value is not None and last_price < ema_fast_value:
        # çok sık çıkmasın diye minik tolerans
        if (ema_fast_value - last_price) / ema_fast_value > 0.0015:
            paper_sell(last_price, reason="EMA20_BREAK")
            return


# ============================================================
# OPTIONAL: LIVE ORDER FUNCTIONS (ŞİMDİLİK KULLANMIYORUZ)
# ============================================================
def place_market_buy_live(quote_try_amount):
    """
    İleride canlıya geçmek istersen kullanılacak.
    Binance TR docs:
    POST /open/v1/orders
    MARKET = type 2
    BUY = side 0

    Not: quoteOrderQty dokümanda var. Canlıda açmadan önce küçük miktarla test et.
    """
    params = {
        "symbol": ORDER_SYMBOL,
        "side": 0,            # BUY
        "type": 2,            # MARKET
        "quoteOrderQty": str(quote_try_amount),
    }
    return signed_post("/open/v1/orders", params=params)


def place_market_sell_live(quantity):
    """
    MARKET SELL
    """
    params = {
        "symbol": ORDER_SYMBOL,
        "side": 1,            # SELL
        "type": 2,            # MARKET
        "quantity": str(quantity),
    }
    return signed_post("/open/v1/orders", params=params)


# ============================================================
# MAIN LOOP
# ============================================================
def print_account_summary():
    if not API_KEY or not API_SECRET:
        log("UYARI: API key/secret yok. Hesap bakiyesi çekilemeyecek.")
        return

    try:
        account = get_account_info()
        try_balance = get_try_balance(account)
        btc_balance = get_btc_balance(account)

        log("--- HESAP ÖZETİ ---")
        log(f"TRY bakiye: {try_balance:,.2f}")
        log(f"BTC bakiye: {btc_balance:.8f}")
    except Exception as e:
        log(f"Hesap özeti alınamadı: {e}")


def run_once():
    reset_daily_if_needed()

    candles = get_klines()
    if not candles:
        log("Kline verisi boş döndü.")
        return

    last_price = candles[-1]["close"]
    signal = build_signal(candles)

    log("--------------------------------------------------")
    log(f"Son fiyat: {last_price:,.2f} TRY")
    log(f"Sinyal: {signal.get('signal')} | Sebep: {signal.get('reason')}")
    if signal.get("ema_fast") is not None:
        log(f"EMA{EMA_FAST}: {signal['ema_fast']:.2f} | EMA{EMA_SLOW}: {signal['ema_slow']:.2f} | RSI: {signal['rsi']:.2f}")

    # Önce açık pozisyon varsa onu yönet
    manage_open_position(last_price, signal.get("ema_fast"))

    # Pozisyon yoksa ve trading bloklu değilse alım düşün
    if not paper_state["in_position"] and not trading_blocked():
        if signal["signal"] == "BUY":
            paper_buy(last_price)

    # Açık pozisyon bilgisi
    if paper_state["in_position"]:
        log("--- AÇIK PAPER POZİSYON ---")
        log(f"Giriş: {paper_state['entry_price']:,.2f}")
        log(f"Stop: {paper_state['stop_price']:,.2f}")
        log(f"TP: {paper_state['take_profit']:,.2f}")


def main():
    log("Safe BTC/TRY Paper Bot başlatılıyor...")

    # API anahtarı varsa hesap özeti al
    if API_KEY and API_SECRET:
        print_account_summary()
    else:
        log("TRBINANCE_API_KEY / TRBINANCE_API_SECRET tanımlı değil. Paper mode devam ediyor.")

    # Ana döngü
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log("Bot kullanıcı tarafından durduruldu.")
            break
        except Exception as e:
            log(f"HATA: {e}")

        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()
