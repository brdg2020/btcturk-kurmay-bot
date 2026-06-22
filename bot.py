import os
from binance.spot import Spot

# GitHub Secrets'tan gelen verileri oku
api_key = os.environ.get("TRBINANCE_API_KEY")
secret_key = os.environ.get("TRBINANCE_API_SECRET")

# Binance TR için resmi connector
# Not: base_url'i 'https://api.trbinance.com' olarak tanımlıyoruz
client = Spot(
    api_key=api_key, 
    api_secret=secret_key, 
    base_url="https://api.trbinance.com"
)

try:
    print("--- BAĞLANTI DENENİYOR ---")
    
    # 1. Fiyat Bilgisi
    ticker = client.ticker_price("BTCTRY")
    print(f"BTC/TRY Fiyatı: {ticker['price']}")
    
    # 2. Bakiye Bilgisi
    account_details = client.account()
    balances = account_details.get('balances', [])
    
    print("--- BAĞLANTI BAŞARILI ---")
    print("Bakiye Özeti:")
    for asset in balances:
        if float(asset['free']) > 0 or float(asset['locked']) > 0:
            print(f"{asset['asset']}: {asset['free']} (Kilitli: {asset['locked']})")

except Exception as e:
    print(f"HATA: {e}")
