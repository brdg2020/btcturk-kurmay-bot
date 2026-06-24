def generate_signal(row_15m, row_1h, trade_try, trade_btc):
    price = row_15m["Close"]
    
    # 1 Saatlik Büyük Resim Zırhları
    ema200_1h = row_1h.get("ema200", price)
    macd_hist_1h = row_1h.get("macd_hist", 0)
    is_bull_market = row_1h.get("Close_1h", price) > ema200_1h
    
    # 15 Dakikalık Taktik Veriler
    rsi_15m = row_15m["rsi"]
    bb_lower = row_15m["bb_lower"]
    bb_upper = row_15m["bb_upper"]
    atr_val = row_15m["atr"]
    
    # Hacim Onayı (OBV kendi hareketli ortalamasının üstünde mi?)
    hacim_olumlu = row_15m["obv"] > row_15m["obv_ema"]
    
    buy_ok = False
    
    # --- BUY KOŞULU ---
    if trade_try > 50:
        if is_bull_market:
            # Boğada MACD onayı VEYA Hacim onayı iste
            if (price <= bb_lower) or (rsi_15m < 35 and hacim_olumlu):
                buy_ok = True
        else:
            # Ayıda kanama durmadan alma: RSI aşırı dipte ve 1H MACD momentumu toparlıyorsa
            if (rsi_15m < 28) and (macd_hist_1h > 0):
                buy_ok = True
                
    if buy_ok:
        return {
            "action": "BUY",
            "reason": "Sniper Alım (Hacim/MACD Onaylı)",
            "amount_try": trade_try * 0.40,  # Kasanın %40'ı ile
            "amount_btc": 0.0
        }
        
    # --- SELL KOŞULU (ATR İZ SÜREN STOP) ---
    sell_ok = False
    sell_ratio = 0.0
    
    if trade_btc > 0.000001:
        if is_bull_market:
            # Fiyat üst bandı aştıktan sonra, tepeyi görüp ATR (o anki volatilite) kadar aşağı salarsa tetiği çek
            if (rsi_15m > 70) and (price < bb_upper - atr_val):
                sell_ok = True
                sell_ratio = 0.40
        else:
            # Ayıda kaçış daha sert olmalı, ortalamaya (ema21) dönmeden yarı ATR sarkarsa sat
            if (rsi_15m > 60) or (price < bb_upper - (0.5 * atr_val) and price > row_15m.get("ema21", 0)):
                sell_ok = True
                sell_ratio = 0.70
                
    if sell_ok:
        return {
            "action": "SELL",
            "reason": "ATR Dinamik Kâr Alımı",
            "amount_try": 0.0,
            "amount_btc": trade_btc * sell_ratio
        }
        
    return {"action": "HOLD", "reason": "-", "amount_try": 0.0, "amount_btc": 0.0}
