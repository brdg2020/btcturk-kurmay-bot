import os
from binance.client import Client

# 1. API Anahtarlarını GitHub Secrets'tan oku
# (Local'de çalışırken .env kullanıyorsan load_dotenv() burada da kalabilir)
API_KEY = os.environ.get("TRBINANCE_API_KEY")
SECRET_KEY = os.environ.get("TRBINANCE_API_SECRET")

# 2. Binance TR Client Bağlantısı
# tld='tr' parametresi Binance TR'ye bağlanmanı sağlar
client = Client(api_key=API_KEY, api_secret=SECRET_KEY, tld='tr')

# 3. Test İşlemleri
try:
    # Fiyat çekme
    ticker = client.get_symbol_ticker(symbol="BTCTRY")
    print(f"Current BTC/TRY Price: {ticker['price']}")

    # Bakiye kontrolü
    account_info = client.get_account()
    for asset in account_info['balances']:
        if float(asset['free']) > 0 or float(asset['locked']) > 0:
            print(f"Asset: {asset['asset']} | Free: {asset['free']}")

    print("--- BAĞLANTI BAŞARILI ---")
except Exception as e:
    print(f"An error occurred: {e}")
