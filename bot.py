import os
import ccxt
import sys

# 1. API Anahtarlarını GitHub Secrets'tan Çek
api_key = os.environ.get('TRBINANCE_API_KEY')
api_secret = os.environ.get('TRBINANCE_API_SECRET')

if not api_key or not api_secret:
    print("HATA: API anahtarları bulunamadı! Secrets ayarlarını kontrol et.")
    sys.exit(1)

# 2. Binance TR Bağlantısı
try:
    exchange = ccxt.binancetr({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
    })

    # 3. Bakiye Kontrolü (Test için)
    balance = exchange.fetch_balance()
    print("--- BAĞLANTI BAŞARILI ---")
    print(f"Toplam Bakiye Bilgisi Alındı.")
    
    # Burada stratejini çalıştırabilirsin
    # Örnek: free_balance = balance['free']
    
except Exception as e:
    print(f"Borsa bağlantı hatası: {e}")
    sys.exit(1)
