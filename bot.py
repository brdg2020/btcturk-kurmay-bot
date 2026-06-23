cat > bot.py << 'EOF'
import os
import traceback
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime

# =========================================================
# AYARLAR
# =========================================================
API_KEY = os.environ.get("TRBINANCE_API_KEY", "")
API_SECRET = os.environ.get("TRBINANCE_API_SECRET", "")

BASE_URL = "https://www.binance.tr"
MARKET_BASE_URL = "https://api.binance.me"

REQUEST_TIMEOUT = 10
SYMBOL = "BTCTRY"

# Strateji ayarları
CORE_BTC_RATIO = 0.70
TRADE_BTC_RATIO = 0.30
BUY_CHUNK_TRY = 1000.0
MIN_TRY_TO_BUY = 500.0
MIN_BTC_TO_SELL = 0.00005

# Teknik ayarlar
EMA_FAST_MAIN = 20
EMA_SLOW_MAIN = 50
RSI_PERIOD = 14

EMA_FAST_TRIGGER = 9
EMA_SLOW_TRIGGER = 21

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def sign_params(params: dict, secret_key: str) -> str:
    query = urlencode(params)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{query}&signature={signature}"

def safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default

# =========================================================
# BINANCE TR API
# =========================================================
def get_server_time():
    url = f"{BASE_URL}/open/v1/common/time"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if "timestamp" not in data:
        raise Exception(f"Sunucu zamanı alınamadı: {data}")
    return data["timestamp"]

def get_account_info():
    timestamp = get_server_time()
    params = {
        "timestamp": timestamp,
        "recvWindow": 5000
    }
    signed_query = sign_params(params, API_SECRET)
    url = f"{BASE_URL}/open/v1/account/spot?{signed_query}"
    headers = {"X-MBX-APIKEY": API_KEY}

    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_klines(symbol=SYMBOL, interval="1h", limit=200):
    url = f"{MARKET_BASE_URL}/api/v1/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

# =========================================================
# TEKNİK GÖSTERGELER
# =========================================================
def extract_closes(klines):
    return [float(k[4]) for k in klines]

def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)
    ema_value = sum(values[:period]) / period

    for price in values[period:]:
        ema_value = (price - ema_value) * multiplier + ema_value

    return ema_value

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
# BAKİYE OKUMA
# =========================================================
def parse_balances(account_data):
    """
    Binance TR /open/v1/account/spot cevabından TRY ve BTC bakiyesini okur.
    Beklenen yapı:
    {
      "code":0,
      "msg":"Success",
      "data":{
        ...
        "accountAssets":[
          {"asset":"TRY","free":"3013.88","locked":"0"},
          {"asset":"BTC","free":"0.01327","locked":"0"}
        ]
      }
    }
    """
    try_balance = 0.0
    btc_balance = 0.0

    assets = (
        account_data
        .get("data", {})
        .get("accountAssets", [])
    )

    for item in assets:
        asset = item.get("asset", "")
        free_amount = float(item.get("free", "0") or 0)

        if asset == "TRY":
            try_balance = free_amount
        elif asset == "BTC":
            btc_balance = free_amount

    return try_balance, btc_balance

# =========================================================
# STRATEJİ
# =========================================================
def analyze_market():
    klines_1h = get_klines(interval="1h", limit=200)
    closes_1h = extract_closes(klines_1h)

    ema20_1h = ema(closes_1h, EMA_FAST_MAIN)
    ema50_1h = ema(closes_1h, EMA_SLOW_MAIN)
    rsi_1h = rsi(closes_1h, RSI_PERIOD)
    last_close_1h = closes_1h[-1]

    klines_15m = get_klines(interval="15m", limit=200)
    closes_15m = extract_closes(klines_15m)

    ema9_15m = ema(closes_15m, EMA_FAST_TRIGGER)
    ema21_15m = ema(closes_15m, EMA_SLOW_TRIGGER)
    rsi_15m = rsi(closes_15m, RSI_PERIOD)
    last_close_15m = closes_15m[-1]

    return {
        "last_close_1h": last_close_1h,
        "ema20_1h": ema20_1h,
        "ema50_1h": ema50_1h,
        "rsi_1h": rsi_1h,
        "last_close_15m": last_close_15m,
        "ema9_15m": ema9_15m,
        "ema21_15m": ema21_15m,
        "rsi_15m": rsi_15m
    }

def build_signal(try_balance, btc_balance, market):
    price = market["last_close_15m"]

    core_btc = btc_balance * CORE_BTC_RATIO
    trade_btc = btc_balance * TRADE_BTC_RATIO

    trend_up = (
        market["ema20_1h"] is not None and
        market["ema50_1h"] is not None and
        market["ema20_1h"] > market["ema50_1h"] and
        market["rsi_1h"] is not None and
        market["rsi_1h"] >= 40
    )

    trend_down = (
        market["ema20_1h"] is not None and
        market["ema50_1h"] is not None and
        market["ema20_1h"] < market["ema50_1h"] and
        market["rsi_1h"] is not None and
        market["rsi_1h"] < 45
    )

    trigger_buy = (
        market["ema9_15m"] is not None and
        market["ema21_15m"] is not None and
        market["ema9_15m"] > market["ema21_15m"] and
        market["rsi_15m"] is not None and
        market["rsi_15m"] > 38 and
        market["rsi_15m"] < 65
    )

    trigger_sell = (
        market["ema9_15m"] is not None and
        market["ema21_15m"] is not None and
        market["ema9_15m"] < market["ema21_15m"] and
        market["rsi_15m"] is not None and
        market["rsi_15m"] < 48
    )

    decision = "BEKLE"
    reason = "Net koşul oluşmadı."
    suggested_action = None

    if trend_up and trigger_buy and try_balance >= MIN_TRY_TO_BUY:
        buy_try = min(BUY_CHUNK_TRY, try_balance)
        buy_btc_est = buy_try / price if price > 0 else 0

        decision = "AL"
        reason = (
            "1h trend yukarı (EMA20 > EMA50, RSI güçlü) "
            "ve 15m tetik olumlu (EMA9 > EMA21, RSI toparlanıyor)."
        )
        suggested_action = {
            "type": "BUY",
            "buy_try": round(buy_try, 2),
            "estimated_btc": round(buy_btc_est, 8)
        }

    elif trade_btc >= MIN_BTC_TO_SELL and (trend_down or trigger_sell):
        sell_btc = trade_btc * 0.50
        sell_try_est = sell_btc * price

        decision = "SAT"
        if trend_down and trigger_sell:
            reason = "1h trend zayıf ve 15m satış tetiği aktif."
        elif trend_down:
            reason = "1h trend zayıfladı; trade BTC azaltmak mantıklı."
        else:
            reason = "15m satış tetiği oluştu; trade BTC'nin bir kısmı realize edilebilir."

        suggested_action = {
            "type": "SELL",
            "sell_btc": round(sell_btc, 8),
            "estimated_try": round(sell_try_est, 2)
        }

    return {
        "decision": decision,
        "reason": reason,
        "price": price,
        "core_btc": core_btc,
        "trade_btc": trade_btc,
        "suggested_action": suggested_action
    }

# =========================================================
# MAIN
# =========================================================
def main():
    log("KURMAY SİNYAL BOTU BAŞLADI")
    log(f"API_KEY var mı? {'EVET' if API_KEY else 'HAYIR'}")
    log(f"API_SECRET var mı? {'EVET' if API_SECRET else 'HAYIR'}")

    if not API_KEY or not API_SECRET:
        log("API bilgileri eksik. Çıkılıyor.")
        return

    try:
        account = get_account_info()
        log(f"HAM ACCOUNT JSON: {account}")
        try_balance, btc_balance = parse_balances(account)

        log("=== BAKİYE DURUMU ===")
        log(f"TRY Bakiye: {try_balance:.2f}")
        log(f"BTC Bakiye: {btc_balance:.8f}")

        market = analyze_market()

        log("=== TEKNİK DURUM ===")
        log(f"1H Kapanış: {market['last_close_1h']:.2f}")
        log(f"1H EMA20: {market['ema20_1h']:.2f} | EMA50: {market['ema50_1h']:.2f} | RSI: {market['rsi_1h']:.2f}")
        log(f"15M Kapanış: {market['last_close_15m']:.2f}")
        log(f"15M EMA9: {market['ema9_15m']:.2f} | EMA21: {market['ema21_15m']:.2f} | RSI: {market['rsi_15m']:.2f}")

        signal = build_signal(try_balance, btc_balance, market)

        log("=== STRATEJİ RAPORU ===")
        log(f"Fiyat: {signal['price']:.2f}")
        log(f"Core BTC (dokunma): {signal['core_btc']:.8f}")
        log(f"Trade BTC (işlem tarafı): {signal['trade_btc']:.8f}")
        log(f"KARAR: {signal['decision']}")
        log(f"GEREKÇE: {signal['reason']}")

        if signal["suggested_action"]:
            action = signal["suggested_action"]
            if action["type"] == "BUY":
                log(f"ÖNERİLEN İŞLEM: {action['buy_try']} TRY ile yaklaşık {action['estimated_btc']} BTC AL")
            elif action["type"] == "SELL":
                log(f"ÖNERİLEN İŞLEM: yaklaşık {action['sell_btc']} BTC SAT (tahmini {action['estimated_try']} TRY)")
        else:
            log("ÖNERİLEN İŞLEM: YOK")

        log("BOT BİTTİ - BU SÜRÜM GERÇEK EMİR VERMEZ")

    except Exception as e:
    log(f"GENEL HATA: {e}")
    traceback.print_exc()

if __name__ == "__main__":
    main()
EOF
