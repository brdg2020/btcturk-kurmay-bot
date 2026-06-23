
# strategy.py

from config import (
    BUY_CHUNK_TRY,
    SELL_PORTION,
    RSI_1H_BUY_MAX,
    RSI_1H_SELL_MIN,
    RSI_15M_BUY_MAX,
    RSI_15M_SELL_MIN,
    USE_EMA_FILTER,
)


def generate_signal(row_15m, row_1h, trade_try, trade_btc):
    """
    Dönüş formatı:
    {
        "action": "BUY" / "SELL" / "HOLD",
        "reason": "...",
        "amount_try": float,
        "amount_btc": float
    }
    """

    price = row_15m["Close"]

    # 1H göstergeler
    ema20_1h = row_1h["ema20"]
    ema50_1h = row_1h["ema50"]
    rsi_1h = row_1h["rsi"]

    # 15M göstergeler
    ema9_15m = row_15m["ema9"]
    ema21_15m = row_15m["ema21"]
    rsi_15m = row_15m["rsi"]

    # -------------------------------------------------
    # BUY KOŞULU
    # -------------------------------------------------
    # Mantık:
    # - 1H tarafı çok sıcak değil, zayıf / dip bölgesinde
    # - 15M RSI düşük
    # - 15M kısa EMA toparlanıyor / yukarı tarafta
    # - elde trade TRY var
    buy_ok = False

    if trade_try >= 50:  # saçma derecede küçük alımı engelle
        cond_1h = rsi_1h <= RSI_1H_BUY_MAX
        cond_15m = rsi_15m <= RSI_15M_BUY_MAX

        if USE_EMA_FILTER:
            cond_ema = ema9_15m >= ema21_15m * 0.997
        else:
            cond_ema = True

        # 1H trend çok bozuksa frene basalım:
        # fiyat EMA50'nin çok altında ve EMA20 < EMA50 ise daha seçici ol
        # burada row_1h["Close"] kullanıyoruz
        close_1h = row_1h["Close"]
        disaster_trend = (close_1h < ema50_1h * 0.94) and (ema20_1h < ema50_1h)

        if cond_1h and cond_15m and cond_ema and not disaster_trend:
            buy_ok = True

    if buy_ok:
        amount_try = min(BUY_CHUNK_TRY, trade_try)
        return {
            "action": "BUY",
            "reason": "1H zayıf bölge + 15M dip/toparlanma",
            "amount_try": amount_try,
            "amount_btc": 0.0
        }

    # -------------------------------------------------
    # SELL KOŞULU
    # -------------------------------------------------
    # Mantık:
    # - 1H artık güçlenmiş / sıcak bölge
    # - 15M de şişmiş
    # - trade BTC var
    sell_ok = False

    if trade_btc > 0.00001:
        cond_1h = rsi_1h >= RSI_1H_SELL_MIN
        cond_15m = rsi_15m >= RSI_15M_SELL_MIN

        if USE_EMA_FILTER:
            cond_ema = ema9_15m <= ema21_15m * 1.003
        else:
            cond_ema = True

        if cond_1h and cond_15m and cond_ema:
            sell_ok = True

    if sell_ok:
        amount_btc = trade_btc * SELL_PORTION
        return {
            "action": "SELL",
            "reason": "1H güçlü bölge + 15M aşırı ısınma",
            "amount_try": 0.0,
            "amount_btc": amount_btc
        }

    return {
        "action": "HOLD",
        "reason": "Koşul yok",
        "amount_try": 0.0,
        "amount_btc": 0.0
    }
