import os
import ccxt
import sys

# 1. API Anahtarlarını GitHub Secrets'tan Çek
api_key = os.environ.get('TRBINANCE_API_KEY')
api_secret = os.environ.get('TRBINANCE_API_SECRET')

# 2. Binance TR Özel Bağlantısı (En Güncel ve Hatasız Yöntem)
try:
    # Ana binance sınıfını kullanıyoruz
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        # ÖNEMLİ: Hostname'i doğrudan Binance TR'ye yönlendiriyoruz
        'urls': {
            'api': {
                'public': 'https://api.trbinance.com/api',
                'private': 'https://api.trbinance.com/api',
            },
        },
    })

    # 3. Bakiye Kontrolü ile Bağlantıyı Doğrula
    balance = exchange.fetch_balance()
    print("--- BAĞLANTI BAŞARILI ---")
    print(f"Toplam Bakiye: {balance['total']}")

except Exception as e:
    print(f"Borsa bağlantı hatası: {e}")
    sys.exit(1)
