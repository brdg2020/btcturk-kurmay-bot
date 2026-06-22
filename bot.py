import os
import ccxt
import sys

# 1. API Anahtarları
api_key = os.environ.get('TRBINANCE_API_KEY')
api_secret = os.environ.get('TRBINANCE_API_SECRET')

# 2. Bağlantı - Burası en kritik yer
try:
    # 'trbinance' sınıfını doğrudan kullanıyoruz
    exchange = ccxt.trbinance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    
    # Borsa API adresini manuel olarak trbinance'e zorla
    exchange.urls['api'] = {
        'public': 'https://api.trbinance.com/api',
        'private': 'https://api.trbinance.com/api',
    }

    # 3. Test
    balance = exchange.fetch_balance()
    print("--- BAĞLANTI BAŞARILI ---")
    print("Bakiye özeti alındı.")

except Exception as e:
    print(f"HATA: {e}")
    sys.exit(1)
