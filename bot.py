import os
import time
from binance.spot import Spot

# Secrets'tan anahtarları al
api_key = os.environ.get("TRBINANCE_API_KEY")
secret_key = os.environ.get("TRBINANCE_API_SECRET")

client = Spot(api_key=api_key, api_secret=secret_key, base_url="https://api.trbinance.com")

def main():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"--- BAĞLANTI DENENİYOR (Deneme {attempt + 1}) ---")
            ticker = client.ticker_price("BTCTRY")
            print(f"BTC/TRY Fiyatı: {ticker['price']}")
            
            account_details = client.account()
            print("--- BAĞLANTI BAŞARILI ---")
            
            for asset in account_details.get('balances', []):
                if float(asset['free']) > 0:
                    print(f"Varlık: {asset['asset']} | Bakiye: {asset['free']}")
            return # Başarılı oldu, çık

        except Exception as e:
            print(f"Deneme {attempt + 1} başarısız: {e}")
            time.sleep(5) # 5 saniye bekle ve tekrar dene
    
    print("Maksimum deneme sayısına ulaşıldı, bağlantı kurulamadı.")

if __name__ == "__main__":
    main()
