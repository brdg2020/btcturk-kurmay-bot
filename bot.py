import os
from binance.spot import Spot

# Secrets'tan anahtarları al
api_key = os.environ.get("TRBINANCE_API_KEY")
secret_key = os.environ.get("TRBINANCE_API_SECRET")

# Binance TR Client
client = Spot(
    api_key=api_key, 
    api_secret=secret_key, 
    base_url="https://api.trbinance.com"
)

try:
    print("--- BAĞLANTI DENENİYOR ---")
    
    # Fiyat ve Bakiye Kontrolü
    ticker = client.ticker_price("BTCTRY")
    print(f"BTC/TRY Fiyatı: {ticker['price']}")
    
    account_details = client.account()
    print("--- BAĞLANTI BAŞARILI ---")
    
    for asset in account_details.get('balances', []):
        if float(asset['free']) > 0:
            print(f"Varlık: {asset['asset']} | Bakiye: {asset['free']}")

except Exception as e:
    print(f"HATA: {e}")
