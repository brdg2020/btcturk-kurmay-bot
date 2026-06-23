
# backtest.py

import pandas as pd
from config import (
    DATA_1H_PATH,
    DATA_15M_PATH,
    INITIAL_TRY,
    INITIAL_BTC,
    CORE_BTC_RATIO,
    TRADE_BTC_RATIO,
    TRADE_TRY_RATIO,
    FEE_RATE,
)
from indicators import ema, rsi
from strategy import generate_signal


def load_data():
    df_1h = pd.read_csv(DATA_1H_PATH)
    df_15m = pd.read_csv(DATA_15M_PATH)

    # Tarih parse
    df_1h["Open_Time"] = pd.to_datetime(df_1h["Open_Time"])
    df_15m["Open_Time"] = pd.to_datetime(df_15m["Open_Time"])

    # Numeric kolonlar
    for df in (df_1h, df_15m):
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sırala / temizle
    df_1h = df_1h.sort_values("Open_Time").dropna().reset_index(drop=True)
    df_15m = df_15m.sort_values("Open_Time").dropna().reset_index(drop=True)

    return df_1h, df_15m


def add_indicators(df_1h, df_15m):
    # 1H
    df_1h["ema20"] = ema(df_1h["Close"], 20)
    df_1h["ema50"] = ema(df_1h["Close"], 50)
    df_1h["rsi"] = rsi(df_1h["Close"], 14)

    # 15M
    df_15m["ema9"] = ema(df_15m["Close"], 9)
    df_15m["ema21"] = ema(df_15m["Close"], 21)
    df_15m["rsi"] = rsi(df_15m["Close"], 14)

    return df_1h, df_15m


def align_1h_to_15m(df_1h, df_15m):
    """
    Her 15m satırına, o ana kadar kapanmış en son 1H barını eşle.
    """
    df_1h_small = df_1h[
        ["Open_Time", "Close", "ema20", "ema50", "rsi"]
    ].copy()

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
    print("KURMAY BACKTEST v1 BAŞLIYOR")
    print("=" * 70)

    df_1h, df_15m = load_data()
    df_1h, df_15m = add_indicators(df_1h, df_15m)
    df = align_1h_to_15m(df_1h, df_15m)

    # Merge sonrası kolon isimleri:
    # 15m tarafı:
    # Open, High, Low, Close, Volume, ema9, ema21, rsi
    # 1h tarafı:
    # Close_1h? merge sonrası isim çakışmasından dolayı Close_1h gelmeyebilir,
    # bu yüzden aşağıda rename ile netleştireceğiz.

    # Kolonları netleştirelim
    rename_map = {}
    if "Close_15m" in df.columns:
        rename_map["Close_15m"] = "Close"
    if "Close_1h" in df.columns:
        rename_map["Close_1h"] = "Close_1h"

    df = df.rename(columns=rename_map)

    # Eğer merge Close isimlerini farklı bırakmadıysa, manuel toparla
    # merge_asof sonrası genelde soldaki df_15m'in Close kolonu "Close" kalır,
    # sağdaki 1h Close kolonu ise suffix ile "Close_1h" olur.
    if "Close_1h" not in df.columns:
        # bazen suffix yapısı beklenenden farklı olabilir; güvenlik:
        possible = [c for c in df.columns if c.lower() == "close_1h"]
        if possible:
            df["Close_1h"] = df[possible[0]]
        else:
            raise ValueError("1H close kolonu eşleşmedi. CSV kolonlarını kontrol et.")

    # 1H satır görünümü için strategy'ye uygun row üretmek adına
    # aşağıda sanal row_1h dict'i kuracağız.

    # ---------------------------------------------------------
    # BAŞLANGIÇ PORTFÖYÜ
    # ---------------------------------------------------------
    core_btc = INITIAL_BTC * CORE_BTC_RATIO
    trade_btc = INITIAL_BTC * TRADE_BTC_RATIO
    trade_try = INITIAL_TRY * TRADE_TRY_RATIO

    # ilk fiyat
    first_price = float(df.iloc[0]["Close"])
    initial_equity = calc_equity(first_price, core_btc, trade_btc, trade_try)

    equity_curve = []
    trades = []

    max_equity = initial_equity
    max_drawdown = 0.0

    # İlk indikatörlerin oturması için bir miktar veri atla
    start_index = 200

    for i in range(start_index, len(df)):
        row = df.iloc[i]

        # 15m row
        row_15m = {
            "Open_Time": row["Open_Time"],
            "Close": float(row["Close"]),
            "ema9": float(row["ema9"]),
            "ema21": float(row["ema21"]),
            "rsi": float(row["rsi"]),
        }

        # 1h row
        row_1h = {
            "Close": float(row["Close_1h"]),
            "ema20": float(row["ema20"]),
            "ema50": float(row["ema50"]),
            "rsi": float(row["rsi_1h"]) if "rsi_1h" in df.columns else float(row["rsi_y"]) if "rsi_y" in df.columns else float(row["rsi"]),
        }

        # Bazı merge durumlarında 1h rsi sütunu farklı isimle gelebilir.
        # Bunu biraz daha sağlamlaştıralım:
        if "rsi_1h" not in row_1h:
            pass

        # Eğer row'da 1H RSI ayrı sütun değilse, aşağıdaki yedek mekanizma
        if "rsi_1h" not in df.columns:
            # olası isimler
            if "rsi_y" in df.columns:
                row_1h["rsi"] = float(row["rsi_y"])
            elif "rsi_1h" in row.index:
                row_1h["rsi"] = float(row["rsi_1h"])
            else:
                # eğer merge sırasında 1H RSI ezildiyse açık hata verelim
                raise ValueError("1H RSI kolonu bulunamadı.")

        signal = generate_signal(row_15m, row_1h, trade_try, trade_btc)
        price = row_15m["Close"]

        # --------------------------------------
        # BUY
        # --------------------------------------
        if signal["action"] == "BUY":
            amount_try = signal["amount_try"]

            if amount_try > 0 and trade_try >= amount_try:
                fee_try = amount_try * FEE_RATE
                net_try = amount_try - fee_try

                btc_bought = net_try / price

                trade_try -= amount_try
                trade_btc += btc_bought

                trades.append({
                    "time": row_15m["Open_Time"],
                    "action": "BUY",
                    "price": price,
                    "amount_try": amount_try,
                    "btc_change": btc_bought,
                    "reason": signal["reason"],
                })

        # --------------------------------------
        # SELL
        # --------------------------------------
        elif signal["action"] == "SELL":
            amount_btc = signal["amount_btc"]

            if amount_btc > 0 and trade_btc >= amount_btc:
                gross_try = amount_btc * price
                fee_try = gross_try * FEE_RATE
                net_try = gross_try - fee_try

                trade_btc -= amount_btc
                trade_try += net_try

                trades.append({
                    "time": row_15m["Open_Time"],
                    "action": "SELL",
                    "price": price,
                    "amount_try": net_try,
                    "btc_change": -amount_btc,
                    "reason": signal["reason"],
                })

        equity = calc_equity(price, core_btc, trade_btc, trade_try)
        equity_curve.append({
            "time": row_15m["Open_Time"],
            "equity": equity
        })

        if equity > max_equity:
            max_equity = equity

        dd = (max_equity - equity) / max_equity if max_equity > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

    # ---------------------------------------------------------
    # RAPOR
    # ---------------------------------------------------------
    final_price = float(df.iloc[-1]["Close"])
    final_equity = calc_equity(final_price, core_btc, trade_btc, trade_try)
    total_return = (final_equity / initial_equity - 1) * 100

    # Buy & Hold kıyası:
    # başlangıçta tüm varlığı BTC'ye çevirip tutsaydık ne olurdu?
    initial_total_try = INITIAL_TRY + (INITIAL_BTC * first_price)
    hold_btc = initial_total_try / first_price
    hold_final = hold_btc * final_price
    hold_return = (hold_final / initial_total_try - 1) * 100

    buy_count = sum(1 for t in trades if t["action"] == "BUY")
    sell_count = sum(1 for t in trades if t["action"] == "SELL")

    print("\n" + "=" * 70)
    print("BACKTEST SONUCU")
    print("=" * 70)
    print(f"Başlangıç equity : {initial_equity:,.2f} TRY")
    print(f"Bitiş equity     : {final_equity:,.2f} TRY")
    print(f"Toplam getiri    : {total_return:.2f}%")
    print(f"Buy&Hold getiri  : {hold_return:.2f}%")
    print(f"Fark             : {total_return - hold_return:.2f}%")
    print(f"Max Drawdown     : {max_drawdown * 100:.2f}%")
    print(f"Toplam işlem     : {len(trades)}")
    print(f"BUY sayısı       : {buy_count}")
    print(f"SELL sayısı      : {sell_count}")

    print("\nPortföy son durum:")
    print(f"Core BTC   : {core_btc:.8f}")
    print(f"Trade BTC  : {trade_btc:.8f}")
    print(f"Trade TRY  : {trade_try:,.2f}")

    if trades:
        print("\nSon 10 işlem:")
        for t in trades[-10:]:
            print(
                f"{t['time']} | {t['action']} | fiyat={t['price']:.2f} | "
                f"try={t['amount_try']:.2f} | reason={t['reason']}"
            )
    else:
        print("\nHiç işlem oluşmadı.")

    print("\nBİTTİ.")


if __name__ == "__main__":
    main()
