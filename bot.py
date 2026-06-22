import os
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from datetime import datetime

API_KEY = os.environ.get("TRBINANCE_API_KEY", "")
API_SECRET = os.environ.get("TRBINANCE_API_SECRET", "")

BASE_URL = "https://www.binance.tr"
MARKET_BASE_URL = "https://api.binance.me"

REQUEST_TIMEOUT = 10
SYMBOL = "BTCTRY"

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

def get_server_time():
    log("1) Sunucu zamanı isteniyor...")
    url = f"{BASE_URL}/open/v1/common/time"
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    log(f"1) Status: {r.status_code}")
    log(f"1) Raw response: {r.text[:500]}")
    r.raise_for_status()
    return r.json()

def get_account_info():
    log("2) Hesap bilgisi isteniyor...")
    ts_data = get_server_time()
    timestamp = ts_data.get("timestamp")
    if not timestamp:
        raise Exception(f"timestamp bulunamadı: {ts_data}")

    params = {
        "timestamp": timestamp,
        "recvWindow": 5000
    }

    signed_query = sign_params(params, API_SECRET)
    url = f"{BASE_URL}/open/v1/account/spot?{signed_query}"
    headers = {"X-MBX-APIKEY": API_KEY}

    log(f"2) Account URL: {url}")
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    log(f"2) Status: {r.status_code}")
    log(f"2) Raw response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()

def get_klines():
    log("3) Kline verisi isteniyor...")
    url = f"{MARKET_BASE_URL}/api/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": "15m",
        "limit": 5
    }

    log(f"3) Kline URL: {url} | params={params}")
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    log(f"3) Status: {r.status_code}")
    log(f"3) Raw response: {r.text[:1000]}")
    r.raise_for_status()
    return r.json()

def main():
    log("DEBUG BOT BAŞLADI")
    log(f"API_KEY var mı? {'EVET' if API_KEY else 'HAYIR'}")
    log(f"API_SECRET var mı? {'EVET' if API_SECRET else 'HAYIR'}")

    try:
        time_data = get_server_time()
        log(f"Sunucu zamanı başarılı: {time_data}")
    except Exception as e:
        log(f"SUNUCU ZAMANI HATASI: {e}")

    if API_KEY and API_SECRET:
        try:
            account = get_account_info()
            log(f"Hesap bilgisi başarılı: {account}")
        except Exception as e:
            log(f"HESAP HATASI: {e}")
    else:
        log("API key/secret olmadığı için hesap testi atlandı.")

    try:
        klines = get_klines()
        log(f"Kline başarılı. İlk veri: {klines[0] if klines else 'boş'}")
    except Exception as e:
        log(f"KLINE HATASI: {e}")

    log("DEBUG BOT BİTTİ")

if __name__ == "__main__":
    main()
