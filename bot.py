import os
import time
import base64
import hmac
import hashlib
import requests

API_KEY = os.getenv("469F5Db75044C5cA6094506d53E8E51CVc4lSDlluRn9wdXH0TGIoz3uzwFFezs1", "").strip()
API_SECRET = os.getenv("87E3993Ebd105C89B374E5A753E1413AOKhEUFHa9ZZPOiJJ9IRu1Smii7S4Bxyl", "").strip()
BASE_URL = "https://api.btcturk.com"

def get_auth_headers():
    stamp = str(int(time.time() * 1000))
    message = f"{API_KEY}{stamp}".encode("utf-8")
    secret_bytes = base64.b64decode(API_SECRET)
    signature_bytes = hmac.new(secret_bytes, message, hashlib.sha256).digest()
    signature = base64.b64encode(signature_bytes).decode("utf-8")
    return {
        "X-PCK": API_KEY,
        "X-Stamp": stamp,
        "X-Signature": signature,
        "Content-Type": "application/json"
    }

def bakiye_kontrol():
    print("=== BTCTURK GÜNLÜK KURMAY BOT DEVREDE ===")
    try:
        res = requests.get(BASE_URL + "/api/v1/users/balances", headers=get_auth_headers(), timeout=10)
        res.raise_for_status()
        data = res.json()
        print("\n[KASA DURUMU]:")
        for item in data["data"]:
            if float(item["balance"]) > 0:
                print(f" -> {item['asset']}: Toplam {item['balance']} | Boşta: {item['free']}")
        print("\n🚀 Microsoft GitHub Köprüsü Başarıyla Kuruldu!")
    except Exception as e:
        print(f"\n❌ Borsa Bağlantı Hatası: {e}")
        if 'res' in locals():
            print(f"Borsa Yanıtı: {res.text}")

if __name__ == "__main__":
    bakiye_kontrol()
