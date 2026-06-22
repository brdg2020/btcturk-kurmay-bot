import os
import ccxt
import sys

# 1. API Anahtarlarını GitHub Secrets'tan Çek
api_key = os.environ.get('TRBINANCE_API_KEY')
api_secret = os.environ.get('TRBINANCE_API_SECRET')

if not api_key or not api_secret:
    print("HATA: API anahtarları bulunamadı! Secrets ayarlarını kontrol et.")
    sys.exit(1)

# 2. Binance TR Bağlantısı (En Güvenli Yöntem)
try:
    # Binance TR için özel yapılandırma
    exchange = ccxt.trbinance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })
    
    # Eğer yukarıdaki sınıf bulunamazsa, aşağıdaki URL override yöntemini kullanıyoruz:
    exchange.urls['api'] = {
        'public': 'https://api.trbinance.com/api',
        'private': 'https://api.trbinance.com/api',
    }

    # 3. Bakiye Kontrolü
    balance = exchange.fetch_balance()
    print("--- BAĞLANTI BAŞARILI ---")
    
    # Bakiyeyi daha detaylı yazdıralım
    total_balance = balance.get('total', {})
    print("Bakiye özeti:")
    for currency, amount in total_balance.items():
        if amount > 0:
            print(f"{currency}: {amount}")
    
except Exception as e:
    print(f"Borsa bağlantı hatası: {e}")
    sys.exit(1)
