import hashlib
import hmac
import os
import time
from urllib.parse import urlencode
import requests

API_KEY = os.getenv("469F5Db75044C5cA6094506d53E8E51CVc4lSDlluRn9wdXH0TGIoz3uzwFFezs1", "").strip()
API_SECRET = os.getenv("87E3993Ebd105C89B374E5A753E1413AOKhEUFHa9ZZPOiJJ9IRu1Smii7S4Bxyl", "").strip()
BASE_URL = "https://api.trbinance.com"


def bakiye_kontrol():
  print("=== BINANCE TR GÜNLÜK KURMAY BOT DEVREDE ===")
  if not API_KEY or not API_SECRET:
    print("❌ HATA: TRBINANCE_API_KEY veya TRBINANCE_API_SECRET bulunamadı!")
    return

  endpoint = "/api/v3/account"
  params = {"timestamp": int(time.time() * 1000)}
  query_string = urlencode(params)
  signature = hmac.new(
      API_SECRET.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
  ).hexdigest()

  url = f"{BASE_URL}{endpoint}?{query_string}&signature={signature}"
  headers = {"X-MBX-APIKEY": API_KEY}

  try:
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()
    data = res.json()
    print("\n[KASA DURUMU]:")
    for item in data.get("balances", []):
      free = float(item["free"])
      locked = float(item["locked"])
      if free > 0 or locked > 0:
        print(f" -> {item['asset']}: Boşta: {free} | Kilitli: {locked}")
    print("\n🚀 Microsoft GitHub Köprüsü Binance TR İçin Başarıyla Kuruldu!")
  except Exception as e:
    print(f"\n❌ Borsa Bağlantı Hatası: {e}")
    if "res" in locals():
      print(f"Borsa Yanıtı: {res.text}")


if __name__ == "__main__":
  bakiye_kontrol()
