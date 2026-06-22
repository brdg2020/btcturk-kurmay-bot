import os
import ccxt
import sys

# API Anahtarlarını Al
api_key = os.environ.get("TRBINANCE_API_KEY")
api_secret = os.environ.get("TRBINANCE_API_SECRET")

if not api_key or not api_secret:
    print("HATA: API anahtarları GitHub Secrets'ta tanımlı değil!")
    sys.exit(1)

try:
    # Binance Global sınıfını kullanarak Binance TR adresine yönlendirme
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    
    # Binance TR API adreslerini manuel set et (En kesin çözüm)
    exchange.urls['api'] = {
        'public': 'https://api.trbinance.com/api',
        'private': 'https://api.trbinance.com/api',
    }

    # Bağlantıyı kontrol et
    balance = exchange.fetch_balance()
    print("--- BAĞLANTI BAŞARILI ---")
    
    # Bakiye Özeti
    total = balance.get('total', {})
    for coin, amount in total.items():
        if float(amount) > 0:
            print(f"{coin}: {amount}")

except Exception as e:
    print(f"HATA: {e}")
    sys.exit(1)
