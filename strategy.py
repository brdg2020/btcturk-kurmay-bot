# strategy.py

def generate_signal(row_15m, row_1h, trade_try, trade_btc):
    price = row_15m["Close"]
    
    # 1 Saatlik Büyük Resim (Rejim Belirleyici)
    ema200_1h = row_1h.get("ema200", price)
    rsi_1h = row_1h["rsi_1h"]
    is_bull_market = row_1h["Close_1h"] > ema200_1h
    
    # 15 Dakikalık Saha Ajanı (Tetikleyici)
    rsi_15m = row_15m["rsi"]
    bb_lower = row_15m["bb_lower"]
    bb_upper = row_15m["bb_upper"]
    
    buy_ok = False
    
    # -------------------------------------------------
    # BUY KOŞULU (Dinamik DCA)
    # -------------------------------------------------
    if trade_try > 50:
        if is_bull_market:
            # Boğada fırsat kaçırma, alt banda değdiğinde veya RSI soğuduğunda al
            if (price <= bb_lower * 1.001) or (rsi_15m < 33 and rsi_1h < 55):
                buy_ok = True
        else:
            # Ayıda mızmız ol, aşırı kanama bekle
            if (price <= bb_lower * 0.998) and (rsi_15m < 25):
                buy_ok = True
                
    if buy_ok:
        amount_try = trade_try * 0.35 # Kasanın %35'i ile kademeli gir
        return {
            "action": "BUY",
            "reason": "Rejim Bazlı Dinamik Alım",
            "amount_try": amount_try,
            "amount_btc": 0.0
        }
        
    # -------------------------------------------------
    # SELL KOŞULU
    # -------------------------------------------------
    sell_ok = False
    sell_ratio = 0.0
    
    if trade_btc > 0.000001:
        if is_bull_market:
            # Boğada malın hepsini satma, coşkuda %30 kâr al
            if (price >= bb_upper * 0.998) and (rsi_15m > 68):
                sell_ok = True
                sell_ratio = 0.30
        else:
            # Ayıda dirençte acımasızca sat (%60'ını boşalt)
            if (rsi_15m > 62) or (price >= bb_upper * 0.999):
                sell_ok = True
                sell_ratio = 0.60
                
    if sell_ok:
        amount_btc = trade_btc * sell_ratio
        return {
            "action": "SELL",
            "reason": "Rejim Bazlı Dinamik Satış",
            "amount_try": 0.0,
            "amount_btc": amount_btc
        }
        
    return {
        "action": "HOLD",
        "reason": "-",
        "amount_try": 0.0,
        "amount_btc": 0.0
    }
