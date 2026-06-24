# backtest.py

import pandas as pd
from config import (
    DATA_1H_PATH, DATA_15M_PATH, INITIAL_TRY, INITIAL_BTC,
    CORE_BTC_RATIO, TRADE_BTC_RATIO, TRADE_TRY_RATIO, FEE_RATE, SLIPPAGE
)
from indicators import ema, rsi, bollinger_bands
from strategy import generate_signal

def load_data():
    df_1h = pd.read_csv(DATA_1H_PATH)
    df_15m = pd.read_csv(DATA_15M_PATH)

    df_1h["Open_Time"] = pd.to_datetime(df_1h["Open_Time"])
    df_15m["Open_Time"] = pd.to_datetime(df_15m["Open_Time"])

    for df in (df_1h, df_15m):
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df_1h = df_1h.sort_values("Open_Time").dropna().reset_index(drop=True)
    df_15m = df_15m.sort_values("Open_Time").dropna().reset_index(drop=True)
    return df_1h, df_15m

def add_indicators(df_1h, df_15m):
    # 1H İndikatörler
    df_1h["ema200"] = ema(df_1h["Close"], 200)
    df_1h["rsi"] = rsi(df_1h["Close"], 14)

    # 15M İndikatörler
    df_15m["rsi"] = rsi(df_15m["Close"], 14)
    sma, upper, lower = bollinger_bands(df_15m["Close"], 20, 2.0)
    df_15m["bb_upper"] = upper
    df_15m["bb_lower"] = lower

    return df_1h, df_15m

def align_1h_to_15m(df_1h, df_15m):
    df_1h_small = df_1h[["Open_Time", "Close", "ema200", "rsi"]].copy()
    merged = pd.merge_asof(
        df_15m.sort_values("Open_Time"),
        df_1h_small.sort_values("Open_Time"),
        on="Open_Time",
        direction="backward",
        suffixes=("_15m", "_1h")
    )
    return merged

def calc_equity(price, core_btc, trade_btc, trade_try):
    return (core_btc + trade_btc) * price + trade_try

def main():
    print("=" * 70)
    print("KURMAY BACKTEST v2 (KAYMA VE REJİM KORUMALI) BAŞLIYOR...")
    print("=" * 70)

    df_1h, df_15m = load_data()
    df_1h, df_15m = add_indicators(df_1h, df_15m)
    df = align_1h_to_15m(df_1h, df_15m)

    # Sütun İsim Çakışmalarını Kesin Olarak Çöz
    rename_map = {
        "Close_15m": "Close",
        "rsi_15m": "rsi",
        "Close_1h": "Close_1h",
        "rsi_1h": "rsi_1h"
    }
    df = df.rename(columns=rename_map)

    core_btc = INITIAL_BTC * CORE_BTC_RATIO
    trade_btc = INITIAL_BTC * TRADE_BTC_RATIO
    trade_try = INITIAL_TRY * TRADE_TRY_RATIO

    first_price = float(df.iloc[0]["Close"])
    initial_equity = calc_equity(first_price, core_btc, trade_btc, trade_try)

    equity_curve = []
    trades = []
    max_equity = initial_equity
    max_drawdown = 0.0

    # EMA200'ün dolması için ilk 200 saati (yaklaşık 800 mum) atla
    start_index = 850

    for i in range(start_index, len(df)):
        row = df.iloc[i]

        row_15m = {
            "Open_Time": row["Open_Time"],
            "Close": float(row["Close"]),
            "rsi": float(row["rsi"]),
            "bb_upper": float(row["bb_upper"]),
            "bb_lower": float(row["bb_lower"]),
        }

        row_1h = {
            "Close_1h": float(row["Close_1h"]),
            "ema200": float(row["ema200"]),
            "rsi_1h": float(row["rsi_1h"]),
        }

        signal = generate_signal(row_15m, row_1h, trade_try, trade_btc)
        
        # Gerçek Fiyat (Normal fiyat)
        base_price = row_15m["Close"]

        if signal["action"] == "BUY":
            amount_try = signal["amount_try"]
            if amount_try > 0 and trade_try >= amount_try:
                # Alırken tahtadaki satıcının üstüne kayıyoruz (Pahalıya alıyoruz)
                exec_price = base_price * (1 + SLIPPAGE)
                
                fee_try = amount_try * FEE_RATE
                net_try = amount_try - fee_try
                btc_bought = net_try / exec_price

                trade_try -= amount_try
                trade_btc += btc_bought

                trades.append({
                    "time": row_15m["Open_Time"], "action": "BUY", "price": exec_price,
                    "amount_try": amount_try, "btc_change": btc_bought, "reason": signal["reason"]
                })

        elif signal["action"] == "SELL":
            amount_btc = signal["amount_btc"]
            if amount_btc > 0 and trade_btc >= amount_btc:
                # Satarken tahtadaki alıcının altına kayıyoruz (Ucuza satıyoruz)
                exec_price = base_price * (1 - SLIPPAGE)
                
                gross_try = amount_btc * exec_price
                fee_try = gross_try * FEE_RATE
                net_try = gross_try - fee_try

                trade_btc -= amount_btc
                trade_try += net_try

                trades.append({
                    "time": row_15m["Open_Time"], "action": "SELL", "price": exec_price,
                    "amount_try": net_try, "btc_change": -amount_btc, "reason": signal["reason"]
                })

        equity = calc_equity(base_price, core_btc, trade_btc, trade_try)
        if equity > max_equity:
            max_equity = equity

        dd = (max_equity - equity) / max_equity if max_equity > 0 else 0
        if dd > max_drawdown: max_drawdown = dd

    final_price = float(df.iloc[-1]["Close"])
    final_equity = calc_equity(final_price, core_btc, trade_btc, trade_try)
    total_return = (final_equity / initial_equity - 1) * 100

    initial_total_try = INITIAL_TRY + (INITIAL_BTC * first_price)
    hold_btc = initial_total_try / first_price
    hold_final = hold_btc * final_price
    hold_return = (hold_final / initial_total_try - 1) * 100

    print("\n" + "=" * 70)
    print("BACKTEST SONUCU")
    print("=" * 70)
    print(f"Toplam getiri    : {total_return:.2f}%")
    print(f"Buy&Hold getiri  : {hold_return:.2f}%")
    print(f"Fark             : {total_return - hold_return:.2f}%")
    print(f"Max Drawdown     : {max_drawdown * 100:.2f}%")
    print(f"Toplam işlem     : {len(trades)}")
    
    print("\nPortföy son durum:")
    print(f"Core BTC (Dokunulmaz): {core_btc:.8f}")
    print(f"Trade BTC (Kalan)    : {trade_btc:.8f}")
    print(f"Trade TRY (Nakit)    : {trade_try:,.2f}")
    print("\nBİTTİ.")

if __name__ == "__main__":
    main()
