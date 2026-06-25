"""Sunucu tarafı teknik analiz indicator hesaplamaları.
Tüm fonksiyonlar Python listesi alır ve dict/series döner.
"""
import math


def calc_sma(data, period):
    """Simple Moving Average - dizi döner."""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(round(sum(data[i - period + 1:i + 1]) / period, 2))
    return result


def calc_ema(data, period):
    """Exponential Moving Average - dizi döner."""
    if not data:
        return []
    k = 2 / (period + 1)
    ema = [data[0]]
    for i in range(1, len(data)):
        val = data[i] * k + ema[-1] * (1 - k)
        ema.append(round(val, 2))
    return ema


def calc_rsi(closes, period=14):
    """Relative Strength Index - dizi döner."""
    if len(closes) < period + 1:
        return [None] * len(closes)

    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_vals = [None] * period
    if avg_loss == 0:
        rsi_vals.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_vals.append(round(100 - (100 / (1 + rs)), 2))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_vals.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_vals.append(round(100 - (100 / (1 + rs)), 2))

    return rsi_vals


def calc_macd(closes, fast=12, slow=26, signal=9):
    """MACD, Signal, Histogram - dict döner."""
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    macd_line = [round(f - s, 2) for f, s in zip(ema_fast, ema_slow)]
    signal_line = calc_ema(macd_line, signal)
    histogram = [round(m - s, 2) for m, s in zip(macd_line, signal_line)]
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def calc_bollinger(closes, period=20, std_dev=2):
    """Bollinger Bands - upper, middle, lower dizileri."""
    middle = calc_sma(closes, period)
    upper = []
    lower = []
    for i in range(len(closes)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = closes[i - period + 1:i + 1]
            mean = middle[i]
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)
            upper.append(round(mean + std_dev * std, 2))
            lower.append(round(mean - std_dev * std, 2))
    return {"upper": upper, "middle": middle, "lower": lower}


def calc_cci(closes, period=20):
    """Commodity Channel Index - dizi döner."""
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
            continue
        window = closes[i - period + 1:i + 1]
        tp = sum(window) / period
        mean_dev = sum(abs(x - tp) for x in window) / period
        if mean_dev == 0:
            result.append(0)
        else:
            result.append(round((closes[i] - tp) / (0.015 * mean_dev), 2))
    return result


def calc_stoch_rsi(closes, rsi_period=14, stoch_period=14, k_period=3, d_period=3):
    """Stochastic RSI - K ve D dizileri."""
    rsi_vals = calc_rsi(closes, rsi_period)
    k_vals = []
    for i in range(len(rsi_vals)):
        if rsi_vals[i] is None or i < stoch_period - 1:
            k_vals.append(None)
            continue
        window = [r for r in rsi_vals[i - stoch_period + 1:i + 1] if r is not None]
        if not window:
            k_vals.append(None)
            continue
        rsi_min = min(window)
        rsi_max = max(window)
        if rsi_max == rsi_min:
            k_vals.append(50)
        else:
            k_vals.append(round(((rsi_vals[i] - rsi_min) / (rsi_max - rsi_min)) * 100, 2))

    d_vals = []
    for i in range(len(k_vals)):
        if k_vals[i] is None or i < d_period - 1:
            d_vals.append(None)
            continue
        window = [k for k in k_vals[i - d_period + 1:i + 1] if k is not None]
        if not window:
            d_vals.append(None)
        else:
            d_vals.append(round(sum(window) / len(window), 2))

    return {"k": k_vals, "d": d_vals}


def calc_atr(closes, period=14):
    """Average True Range - dizi döner (high=low=close olduğu için basitleştirilmiş)."""
    if len(closes) < 2:
        return [None] * len(closes)
    tr_vals = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    atr_vals = [None]
    if len(tr_vals) < period:
        atr_vals.extend([None] * (len(tr_vals)))
        return atr_vals
    atr = sum(tr_vals[:period]) / period
    atr_vals.append(round(atr, 2))
    for i in range(period, len(tr_vals)):
        atr = (atr * (period - 1) + tr_vals[i]) / period
        atr_vals.append(round(atr, 2))
    return atr_vals


def calc_supertrend(closes, period=10, multiplier=3):
    """Supertrend - trend dizisi (1=uptrend, -1=downtrend)."""
    n = len(closes)
    if n < period + 1:
        return [0] * n
    atr = calc_atr(closes, period)
    upper_band = []
    lower_band = []

    for i in range(n):
        a = atr[i] if i < len(atr) and atr[i] is not None else 0
        if a == 0:
            upper_band.append(closes[i] * 1.1)
            lower_band.append(closes[i] * 0.9)
        else:
            upper_band.append(closes[i] + multiplier * a)
            lower_band.append(closes[i] - multiplier * a)

    final_upper = upper_band[:]
    final_lower = lower_band[:]
    for i in range(1, n):
        if final_lower[i] < final_lower[i - 1] and closes[i - 1] < final_lower[i - 1]:
            final_lower[i] = final_lower[i - 1]
        if final_upper[i] > final_upper[i - 1] and closes[i - 1] > final_upper[i - 1]:
            final_upper[i] = final_upper[i - 1]

    trend = []
    st = 1
    for i in range(n):
        if i == 0:
            trend.append(1)
            continue
        if st == 1:
            if closes[i] < final_lower[i]:
                st = -1
                trend.append(-1)
            else:
                trend.append(1)
        else:
            if closes[i] > final_upper[i]:
                st = 1
                trend.append(1)
            else:
                trend.append(-1)

    return trend


def calc_vwap(highs, lows, closes, volumes):
    """Volume Weighted Average Price - cumulative rolling VWAP.
    Her nokta o ana kadar olan ağırlıklı ortalamayı gösterir.
    """
    result = []
    cum_tp_vol = 0.0
    cum_vol = 0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3.0
        vol = volumes[i] if volumes[i] > 0 else 1
        cum_tp_vol += tp * vol
        cum_vol += vol
        if cum_vol > 0:
            result.append(round(cum_tp_vol / cum_vol, 2))
        else:
            result.append(round(tp, 2))
    return result


def calc_fib_levels(high, low):
    """Fibonacci Retracement seviyeleri."""
    diff = high - low
    return {
        "0.0": round(high, 2),
        "0.236": round(high - 0.236 * diff, 2),
        "0.382": round(high - 0.382 * diff, 2),
        "0.5": round(high - 0.5 * diff, 2),
        "0.618": round(high - 0.618 * diff, 2),
        "0.786": round(high - 0.786 * diff, 2),
        "1.0": round(low, 2),
    }


def find_support_resistance(closes, tolerance=0.03):
    """Destek/Direnç noktalarını bul."""
    if not closes:
        return [], []
    sorted_prices = sorted(set(closes))
    levels = []
    for p in sorted_prices:
        count = sum(1 for c in closes if abs(c - p) / p < tolerance)
        if count >= 3:
            levels.append({"price": p, "strength": count})
    levels.sort(key=lambda x: x["strength"], reverse=True)
    supports = [l for l in levels if l["price"] < closes[-1]][:3]
    resistances = [l for l in levels if l["price"] > closes[-1]][:3]
    return supports, resistances


def compute_all_indicators(ohlc_data):
    """Tüm indicator'ları hesapla ve sonuçları dict olarak döner.

    ohlc_data: [{"time": epoch, "open": x, "high": x, "low": x, "close": x, "volume": n}, ...]
    """
    if not ohlc_data or len(ohlc_data) < 2:
        return {"error": "Yeterli veri yok", "count": len(ohlc_data or [])}

    closes = [d["close"] for d in ohlc_data]
    highs = [d.get("high", d["close"]) for d in ohlc_data]
    lows = [d.get("low", d["close"]) for d in ohlc_data]
    volumes = [d.get("volume", 1) for d in ohlc_data]
    times = [d["time"] for d in ohlc_data]

    # VWAP
    vwap = calc_vwap(highs, lows, closes, volumes)

    # RSI
    rsi_vals = calc_rsi(closes, 14)

    # EMA
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)

    # SMA
    sma5 = calc_sma(closes, 5)
    sma20 = calc_sma(closes, 20)

    # MACD
    macd = calc_macd(closes)

    # Bollinger
    bollinger = calc_bollinger(closes, 20)

    # CCI
    cci = calc_cci(closes, 20)

    # Stochastic RSI
    stoch_rsi = calc_stoch_rsi(closes)

    # ATR
    atr = calc_atr(closes, 14)

    # Supertrend
    supertrend = calc_supertrend(closes, 10, 3)

    # Fibonacci
    fib = calc_fib_levels(max(highs), min(lows))

    # Support/Resistance
    supports, resistances = find_support_resistance(closes)

    # Son değerler
    last_close = closes[-1]
    last_rsi = next((r for r in reversed(rsi_vals) if r is not None), None)
    last_ema9 = ema9[-1] if ema9 else None
    last_ema21 = ema21[-1] if ema21 else None
    last_macd = macd["macd"][-1] if macd["macd"] else None
    last_signal = macd["signal"][-1] if macd["signal"] else None
    last_hist = macd["histogram"][-1] if macd["histogram"] else None
    last_vwap = vwap[-1] if vwap else None
    last_bb_upper = bollinger["upper"][-1] if bollinger["upper"] else None
    last_bb_lower = bollinger["lower"][-1] if bollinger["lower"] else None
    last_cci = next((c for c in reversed(cci) if c is not None), None)
    last_stoch_k = next((k for k in reversed(stoch_rsi["k"]) if k is not None), None)
    last_stoch_d = next((d for d in reversed(stoch_rsi["d"]) if d is not None), None)
    last_atr = next((a for a in reversed(atr) if a is not None), None)
    last_supertrend = supertrend[-1] if supertrend else 0

    # Status belirleme
    bull_signals = 0
    bear_signals = 0

    if last_rsi is not None:
        if last_rsi > 55: bull_signals += 1
        elif last_rsi < 45: bear_signals += 1

    if last_ema9 and last_ema21:
        if last_ema9 > last_ema21: bull_signals += 1
        else: bear_signals += 1

    if last_macd is not None and last_signal is not None:
        if last_macd > last_signal: bull_signals += 1
        else: bear_signals += 1

    if last_vwap and last_close:
        if last_close > last_vwap: bull_signals += 1
        else: bear_signals += 1

    if last_supertrend == 1: bull_signals += 1
    elif last_supertrend == -1: bear_signals += 1

    if bull_signals > bear_signals + 1:
        status = "BULLISH"
    elif bear_signals > bull_signals + 1:
        status = "BEARISH"
    else:
        status = "NEUTRAL"

    # VWAP serisi (chart için)
    vwap_series = [{"time": t, "value": v} for t, v in zip(times, vwap)]

    return {
        "count": len(ohlc_data),
        "last_close": last_close,
        "status": status,
        "bull_signals": bull_signals,
        "bear_signals": bear_signals,
        "indicators": {
            "vwap": {"current": last_vwap, "series": vwap_series},
            "rsi": {"current": last_rsi, "series": rsi_vals},
            "ema9": {"current": last_ema9, "series": ema9},
            "ema21": {"current": last_ema21, "series": ema21},
            "sma5": {"current": sma5[-1] if sma5 else None, "series": sma5},
            "sma20": {"current": sma20[-1] if sma20 else None, "series": sma20},
            "macd": {"macd": last_macd, "signal": last_signal, "histogram": last_hist,
                      "macd_series": macd["macd"], "signal_series": macd["signal"], "histogram_series": macd["histogram"]},
            "bollinger": {"upper": last_bb_upper, "lower": last_bb_lower,
                          "upper_series": bollinger["upper"], "lower_series": bollinger["lower"]},
            "cci": {"current": last_cci, "series": cci},
            "stoch_rsi": {"k": last_stoch_k, "d": last_stoch_d, "k_series": stoch_rsi["k"], "d_series": stoch_rsi["d"]},
            "atr": {"current": last_atr, "series": atr},
            "supertrend": {"current": last_supertrend, "series": supertrend},
        },
        "fibonacci": fib,
        "support": supports,
        "resistance": resistances,
    }
