import os
import time
import hmac
import hashlib
import requests
import pandas as pd
from urllib.parse import urlencode
from datetime import datetime

# Zeka ve İndikatörleri Çekiyoruz
from indicators import ema, rsi, bollinger_bands, macd, atr, obv
from strategy import generate_signal

# =========================================================
# GİZLİ AYARLAR VE ANAHTARLAR (BURAYI DOLDUR)
# =========================================================
API_KEY = "BINANCE_TR_API_KEY_BURAYA"
API_SECRET = "BINANCE_TR_SECRET_KEY_BURAYA"

# =========================================================
# SABİTLER
# =========================================================
BASE_URL = "https://www.binance.tr"
MARKET_BASE_URL = "https://api.binance.me"
REQUEST_TIMEOUT = 15
SYMBOL = "BTCTRY"

# Core / Trade Ayrımı
CORE_BTC_RATIO = 0.70
TRADE_BTC_RATIO = 0.30

# =========================================================
# YARDIMCI FONKSİYON
# =========================================================
def log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")

# =========================================================
# BINANCE TR API KÖPRÜSÜ
# =========================================================
def sign_query(params: dict) -> str:
    query = urlencode(params)
    signature = hmac.new(API_SECRET.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{query}&signature={signature}"

def get_server_time():
    url = f"{BASE_URL}/open/v1/common/time"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def signed_request(method, path: str, params=None):
    if params is None: params = {}
    timestamp = get_server_time().get("timestamp")
    params["timestamp"] = timestamp
    query_with_sig = sign_query(params)
    
    url = f"{BASE_URL}{path}"
    headers = {"X-MBX-APIKEY": API_KEY}
    
    if method == "GET":
        url += f"?{query_with_sig}"
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    elif method == "POST":
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        r = requests.post(url, headers=headers, data=query_with_sig, timeout=REQUEST_TIMEOUT)
        
    r.raise_for_status()
    return r.json()

def get_account_balances():
    res = signed_request("GET", "/open/v1/account/spot")
    assets = res.get("data", {}).get("accountAssets", [])
    result = {"TRY": 0.0, "BTC": 0.0}
    for asset in assets:
        coin = asset.get("asset")
        if coin in result:
            result[coin] = float(asset.get("free", 0))
    return result

def place_market_order(side, amount):
    params = {"symbol": SYMBOL, "side": side, "type": "MARKET"}
    if side == "BUY":
        params["quoteOrderQty"] = round(amount, 2)  # TRY bazlı harcama
    else:
        params["quantity"] = round(amount, 5)       # BTC bazlı satım
        
    return signed_request("POST", "/open/v1/orders", params)

def get_klines(interval, limit):
    url = f"{MARKET_BASE_URL}/api/v1/klines"
    params = {"symbol": SYMBOL, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

# =========================================================
# CANLI VERİ VE İNDİKATÖR İŞLEME (Saha Ajanı)
# =========================================================
def fetch_and_analyze():
    klines_1h = get_klines("1h", 500)
    klines_15m = get_klines("15m", 200)

    cols = ["Open_Time", "Open", "High", "Low", "Close", "Volume", "Close_Time", "QAV", "Trades", "TBB", "TBQ", "Ignore"]
    df_1h = pd.DataFrame(klines_1h, columns=cols)
    df_15m = pd.DataFrame(klines_15m, columns=cols)

    for df in (df_1h, df_15m):
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # İndikatör Hesaplamaları
    df_1h["ema200"] = ema(df_1h["Close"], 200)
    df_1h["rsi"] = rsi(df_1h["Close"], 14)
    _, _, df_1h["macd_hist"] = macd(df_1h["Close"])

    df_15m["ema21"] = ema(df_15m["Close"], 21)
    df_15m["rsi"] = rsi(df_15m["Close"], 14)
    sma, upper, lower = bollinger_bands(df_15m["Close"], 20, 2.0)
    df_15m["bb_upper"], df_15m["bb_lower"] = upper, lower
    df_15m["atr"] = atr(df_15m["High"], df_15m["Low"], df_15m["Close"], 14)
    df_15m["obv"] = obv(df_15m["Close"], df_15m["Volume"])
    df_15m["obv_ema"] = ema(df_15m["obv"], 21)

    row_1h = {
        "Close_1h": float(df_1h["Close"].iloc[-1]),
        "ema200": float(df_1h["ema200"].iloc[-1]),
        "rsi_1h": float(df_1h["rsi"].iloc[-1]),
        "macd_hist": float(df_1h["macd_hist"].iloc[-1]),
    }
    
    row_15m = {
        "Close": float(df_15m["Close"].iloc[-1]),
        "ema21": float(df_15m["ema21"].iloc[-1]),
        "rsi": float(df_15m["rsi"].iloc[-1]),
        "bb_upper": float(df_15m["bb_upper"].iloc[-1]),
        "bb_lower": float(df_15m["bb_lower"].iloc[-1]),
        "atr": float(df_15m["atr"].iloc[-1]),
        "obv": float(df_15m["obv"].iloc[-1]),
        "obv_ema": float(df_15m["obv_ema"].iloc[-1]),
    }
    return row_15m, row_1h

# =========================================================
# ANA DÖNGÜ (7/24 Nöbet)
# =========================================================
def run_bot_cycle():
    try:
        log("Saha taraması başlatıldı...")
        balances = get_account_balances()
        try_bal, btc_bal = balances["TRY"], balances["BTC"]
        
        core_btc = btc_bal * CORE_BTC_RATIO
        trade_btc = btc_bal * TRADE_BTC_RATIO

        row_15m, row_1h = fetch_and_analyze()
        
        signal = generate_signal(row_15m, row_1h, try_bal, trade_btc)

        if signal["action"] == "BUY" and signal["amount_try"] > 50:
            harcanacak_try = signal["amount_try"]
            log(f"🟢 ALIM KARARI | Sebep: {signal['reason']} | Fiyat: {row_15m['Close']} | Tutar: {harcanacak_try:.2f} TRY")
            
            res = place_market_order("BUY", harcanacak_try)
            log(f"✅ ALIM BAŞARILI | Gerçekleşen: {res.get('data', {}).get('cummulativeQuoteQty')} TRY")

        elif signal["action"] == "SELL" and signal["amount_btc"] > 0.00001:
            satilacak_btc = signal["amount_btc"]
            log(f"🔴 SATIŞ KARARI | Sebep: {signal['reason']} | Fiyat: {row_15m['Close']} | Miktar: {satilacak_btc:.5f} BTC")
            
            res = place_market_order("SELL", satilacak_btc)
            log(f"✅ SATIŞ BAŞARILI | Elde Edilen: {res.get('data', {}).get('cummulativeQuoteQty')} TRY")

        else:
            log(f"Karar: HOLD (Bekle). Güncel Fiyat: {row_15m['Close']}")

    except Exception as e:
        log(f"⚠️ BOT HATASI: {e}")

def sleep_until_next_15m():
    now = datetime.now()
    minutes = 15 - (now.minute % 15)
    seconds = 60 - now.second
    sleep_time = (minutes - 1) * 60 + seconds
    
    sleep_time += 5 # Mumun borsada tamamen kapanması için fazladan 5 saniye tolerans
    
    next_run = datetime.fromtimestamp(time.time() + sleep_time).strftime("%H:%M:%S")
    log(f"Bir sonraki operasyon saati: {next_run} (Uykuya geçiliyor...)\n")
    time.sleep(sleep_time)

if __name__ == "__main__":
    log("🚀 KURMAY V3 SNIPER BOT CANLIYA ALINDI! Sunucu 7/24 nöbete başladı.\n")
    while True:
        run_bot_cycle()
        sleep_until_next_15m()
