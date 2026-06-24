# config.py

DATA_1H_PATH = "data/BTCTRY_1h.csv"
DATA_15M_PATH = "data/BTCTRY_15m.csv"

INITIAL_TRY = 3013.88
INITIAL_BTC = 0.01327

CORE_BTC_RATIO = 0.70      # BTC'nin %70'i Ana Kasa (Dokunulmaz)
TRADE_BTC_RATIO = 0.30     # BTC'nin %30'u Avcı Kasa

TRADE_TRY_RATIO = 1.0      

# KOMİSYON VE KAYMA (SLIPPAGE)
FEE_RATE = 0.0015          # %0.15 Binance TR Taker Fee
SLIPPAGE = 0.0005          # %0.05 Tahta Kayma Payı (Gerçekçilik için şart)
