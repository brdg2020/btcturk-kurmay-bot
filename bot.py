import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime

# =========================================================
# AYARLAR
# =========================================================
API_KEY = os.environ.get("TRBINANCE_API_KEY", "").strip()
API_SECRET = os.environ.get("TRBINANCE_API_SECRET", "").strip()

BASE_URL = "https://www.binance.tr"
MARKET_BASE_URL = "https://api.binance.me"

REQUEST_TIMEOUT = 15
SYMBOL = "BTCTRY"

# Strateji ayarları
CORE_BTC_RATIO = 0.70   # eldeki BTC'nin %70'i "core", dokunma
TRADE_BTC_RATIO = 0.30  # eldeki BTC'nin %30'u trade tarafı
BUY_CHUNK_TRY = 1000.0  # alım sinyalinde önerilecek TRY tutarı

# =========================================================
# YARDIMCI
# =========================================================
def log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

# =========================================================
# İMZA / API
# =========================================================
def sign_query(params: dict) -> str:
    query = urlencode(params)
    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{query}&signature={signature}"

def get_server_time():
    url = f"{BASE_URL}/open/v1/common/time"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def signed_get(path: str, params=None):
    if params is None:
        params = {}

    server = get_server_time()
    if server.get("code") != 0:
        raise Exception(f"Sunucu zamanı alınamadı: {server}")

    timestamp = server.get("timestamp")
    params["timestamp"] = timestamp

    query_with_sig = sign_query(params)
    url = f"{BASE_URL}{path}?{query_with_sig}"

    headers = {
        "X-MBX-APIKEY": API_KEY
    }

    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_account_info():
    # Binance TR spot hesap endpoint'i
    return signed_get("/open/v1/account/spot")

# =========================================================
# MARKET DATA
# =========================================================
def get_klines(symbol=SYMBOL, interval="15m", limit=200):
    url = f"{MARKET_BASE_URL}/api/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list) or len(data) == 0:
        raise Exception(f"Kline verisi alınamadı: {data}")

    return data

def extract_closes(klines):
    closes = []
    for k in klines:
        # Binance kline formatında kapanış fiyatı index 4
        closes.append(float(k[4]))
    return closes

# =========================================================
# TEKNİK İNDİKATÖRLER
# =========================================================
def ema(values, period):
    if len(values) < period:
        return None

    k = 2 / (period + 1)
    ema_val = sum(values[:period]) / period

    for price in values[period:]:
        ema_val = price * k + ema_val * (1 - k)

    return ema_val

def rsi(values, period=14):
    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = max(diff, 0)
        loss = max(-diff, 0)

        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# =========================================================
# ANALİZ
# =========================================================
def analyze_market():
    # 1H veri
    klines_1h = get_klines(interval="1h", limit=200)
    closes_1h = extract_closes(klines_1h)

    # 15M veri
    klines_15m = get_klines(interval="15m", limit=200)
    closes_15m = extract_closes(klines_15m)

    # Son fiyat
    current_price = closes_15m[-1]

    # 1H indikatörleri
    ema20_1h = ema(closes_1h, 20)
    ema50_1h = ema(closes_1h, 50)
    rsi_1h = rsi(closes_1h, 14)

    # 15M indikatörleri
    ema9_15m = ema(closes_15m, 9)
    ema21_15m = ema(closes_15m, 21)
    rsi_15m = rsi(closes_15m, 14)

    if None in [ema20_1h, ema50_1h, rsi_1h, ema9_15m, ema21_15m, rsi_15m]:
        raise Exception("Teknik indikatörlerden biri hesaplanamadı.")

    return {
        "price": current_price,
        "close_1h": closes_1h[-1],
        "ema20_1h": ema20_1h,
        "ema50_1h": ema50_1h,
        "rsi_1h": rsi_1h,
        "close_15m": closes_15m[-1],
        "ema9_15m": ema9_15m,
        "ema21_15m": ema21_15m,
        "rsi_15m": rsi_15m,
    }

# =========================================================
# BAKİYE
# =========================================================
def parse_balances(account_data):
    """
    account_data:
    {
      "code":0,
      "msg":"Success",
      "data":{
         ...
         "accountAssets":[
             {"asset":"TRY","free":"3013.88","locked":"0"},
             {"asset":"BTC","free":"0.01327","locked":"0"},
             ...
         ]
      }
    }
    """
    result = {
        "TRY": {"free": 0.0, "locked": 0.0},
        "BTC": {"free": 0.0, "locked": 0.0},
    }

    if not account_data or account_data.get("code") != 0:
        return result

    data = account_data.get("data", {})
    assets = data.get("accountAssets", [])

    for asset in assets:
        coin = asset.get("asset")
        if coin in result:
            result[coin]["free"] = safe_float(asset.get("free", 0))
            result[coin]["locked"] = safe_float(asset.get("locked", 0))

    return result

# =========================================================
# STRATEJİ
# =========================================================
def generate_signal(market, balances):
    """
    Çıktı:
    {
      "decision": "BUY" / "SELL" / "HOLD",
      "reason": "...",
      "core_btc": ...,
      "trade_btc": ...,
      "suggested_action": {...} or None
    }
    """
    price = market["price"]

    btc_total = balances["BTC"]["free"]
    try_balance = balances["TRY"]["free"]

    core_btc = btc_total * CORE_BTC_RATIO
    trade_btc = btc_total * TRADE_BTC_RATIO

    # Trend filtresi (1H)
    bullish_trend = market["ema20_1h"] > market["ema50_1h"]
    bearish_trend = market["ema20_1h"] < market["ema50_1h"]

    # Kısa vade momentum (15M)
    short_bull = market["ema9_15m"] > market["ema21_15m"]
    short_bear = market["ema9_15m"] < market["ema21_15m"]

    rsi_1h = market["rsi_1h"]
    rsi_15m = market["rsi_15m"]

    # -----------------------------
    # AL KOŞULU
    # -----------------------------
    # Daha çok "dipten toplama" mantığı:
    # - 1H RSI zayıf / aşırı satıma yakın
    # - 15M RSI çok şişik değil
    # - TRY bakiyesi yeterli
    buy_signal = (
        try_balance >= BUY_CHUNK_TRY and
        (
            (rsi_1h < 32 and rsi_15m < 45) or
            (bullish_trend and short_bull and rsi_15m < 55 and rsi_1h < 50)
        )
    )

    # -----------------------------
    # SAT KOŞULU
    # -----------------------------
    # Sadece trade BTC tarafı için öneri üretir
    sell_signal = (
        trade_btc > 0.00001 and
        (
            (rsi_1h > 68 and rsi_15m > 65) or
            (bearish_trend and short_bear and rsi_15m > 55)
        )
    )

    # Çakışma olursa HOLD
    if buy_signal and sell_signal:
        return {
            "decision": "HOLD",
            "reason": "Hem al hem sat koşulu aynı anda oluştu; çakışma nedeniyle bekle.",
            "core_btc": core_btc,
            "trade_btc": trade_btc,
            "suggested_action": None
        }

    if buy_signal:
        buy_try = min(BUY_CHUNK_TRY, try_balance)
        est_btc = buy_try / price if price > 0 else 0.0

        if buy_try < 50:
            return {
                "decision": "HOLD",
                "reason": "Al sinyali var ama kullanılabilir TRY çok düşük.",
                "core_btc": core_btc,
                "trade_btc": trade_btc,
                "suggested_action": None
            }

        reason_parts = []
        if rsi_1h < 32:
            reason_parts.append("1H RSI düşük")
        if bullish_trend:
            reason_parts.append("1H trend toparlanıyor")
        if short_bull:
            reason_parts.append("15M momentum yukarı dönüyor")

        reason = ", ".join(reason_parts) if reason_parts else "Al koşulları oluştu."

        return {
            "decision": "BUY",
            "reason": reason,
            "core_btc": core_btc,
            "trade_btc": trade_btc,
            "suggested_action": {
                "type": "BUY",
                "buy_try": round(buy_try, 2),
                "est_btc": round(est_btc, 8)
            }
        }

    if sell_signal:
        # Trade BTC'nin tamamını değil, %50'sini sat önerelim
        sell_btc = trade_btc * 0.50
        if sell_btc < 0.00001:
            return {
                "decision": "HOLD",
                "reason": "Sat sinyali var ama trade BTC çok küçük.",
                "core_btc": core_btc,
                "trade_btc": trade_btc,
                "suggested_action": None
            }

        est_try = sell_btc * price

        reason_parts = []
        if rsi_1h > 68:
            reason_parts.append("1H RSI yüksek")
        if bearish_trend:
            reason_parts.append("1H trend zayıf")
        if short_bear:
            reason_parts.append("15M momentum aşağı dönüyor")

        reason = ", ".join(reason_parts) if reason_parts else "Sat koşulları oluştu."

        return {
            "decision": "SELL",
            "reason": reason,
            "core_btc": core_btc,
            "trade_btc": trade_btc,
            "suggested_action": {
                "type": "SELL",
                "sell_btc": round(sell_btc, 8),
                "est_try": round(est_try, 2)
            }
        }

    return {
        "decision": "HOLD",
        "reason": "Net koşul oluşmadı.",
        "core_btc": core_btc,
        "trade_btc": trade_btc,
        "suggested_action": None
    }

# =========================================================
# MAIN
# =========================================================
def main():
    log("KURMAY SİNYAL BOTU BAŞLADI")
    log(f"API_KEY var mı? {'EVET' if API_KEY else 'HAYIR'}")
    log(f"API_SECRET var mı? {'EVET' if API_SECRET else 'HAYIR'}")

    if not API_KEY or not API_SECRET:
        log("HATA: API bilgileri environment'ta yok.")
        return

    try:
        # 1) Hesap bilgisi
        account = get_account_info()
        balances = parse_balances(account)

        try_balance = balances["TRY"]["free"]
        btc_balance = balances["BTC"]["free"]

        log("=== BAKİYE DURUMU ===")
        log(f"TRY Bakiye: {try_balance:.2f}")
        log(f"BTC Bakiye: {btc_balance:.8f}")

        # 2) Teknik analiz
        market = analyze_market()

        log("=== TEKNİK DURUM ===")
        log(f"1H Kapanış: {market['close_1h']:.2f}")
        log(
            f"1H EMA20: {market['ema20_1h']:.2f} | "
            f"EMA50: {market['ema50_1h']:.2f} | "
            f"RSI: {market['rsi_1h']:.2f}"
        )
        log(f"15M Kapanış: {market['close_15m']:.2f}")
        log(
            f"15M EMA9: {market['ema9_15m']:.2f} | "
            f"EMA21: {market['ema21_15m']:.2f} | "
            f"RSI: {market['rsi_15m']:.2f}"
        )

        # 3) Strateji
        signal = generate_signal(market, balances)

        log("=== STRATEJİ RAPORU ===")
        log(f"Fiyat: {market['price']:.2f}")
        log(f"Core BTC (dokunma): {signal['core_btc']:.8f}")
        log(f"Trade BTC (işlem tarafı): {signal['trade_btc']:.8f}")
        log(f"KARAR: {signal['decision']}")
        log(f"GEREKÇE: {signal['reason']}")

        if signal["suggested_action"]:
            action = signal["suggested_action"]

            if action["type"] == "BUY":
                log(
                    f"ÖNERİLEN İŞLEM: {action['buy_try']:.2f} TRY ile "
                    f"yaklaşık {action['est_btc']:.8f} BTC AL"
                )

            elif action["type"] == "SELL":
                log(
                    f"ÖNERİLEN İŞLEM: yaklaşık {action['sell_btc']:.8f} BTC SAT "
                    f"(tahmini {action['est_try']:.2f} TRY)"
                )
        else:
            log("ÖNERİLEN İŞLEM: YOK")

        log("BOT BİTTİ - BU SÜRÜM GERÇEK EMİR VERMEZ")

    except Exception as e:
        log(f"GENEL HATA: {e}")
        raise

if __name__ == "__main__":
    main()
