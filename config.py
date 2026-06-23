# config.py

# =========================
# VERİ DOSYALARI
# =========================
DATA_1H_PATH = "data/BTCTRY_1h.csv"
DATA_15M_PATH = "data/BTCTRY_15m.csv"

# =========================
# BAŞLANGIÇ PORTFÖYÜ
# =========================
INITIAL_TRY = 3013.88
INITIAL_BTC = 0.01327

# Core / trade ayrımı
CORE_BTC_RATIO = 0.75      # BTC'nin %75'i core
TRADE_BTC_RATIO = 0.25     # BTC'nin %25'i trade

# Trade tarafı için kullanılacak TRY oranı
TRADE_TRY_RATIO = 1.0      # elimizdeki TRY'nin tamamı trade kasası olsun

# =========================
# KOMİSYON
# =========================
# Binance TR Bronz / TRY market varsayımı
# maker: 0.10% / taker: 0.15%
# İlk testte muhafazakar olmak için taker benzeri maliyet kullanıyoruz.
FEE_RATE = 0.0015   # %0.15

# =========================
# STRATEJİ PARAMETRELERİ
# =========================
BUY_CHUNK_TRY = 1000.0

# trade BTC satarken tek seferde ne kadarı satılsın
SELL_PORTION = 0.40   # %40

# 1H filtre
RSI_1H_BUY_MAX = 40
RSI_1H_SELL_MIN = 60

# 15M tetik
RSI_15M_BUY_MAX = 38
RSI_15M_SELL_MIN = 65

# Güç teyidi için EMA yakınlık / yön koşulu
USE_EMA_FILTER = True
