"""RSI, Moving Averages, Golden/Death Cross, Volume analysis."""
from webapp.database import get_prices_for_rsi, get_price_history


def rsi(prices, period=14):
    """Relative Strength Index from a list of {price} dicts (newest first)."""
    if len(prices) < period + 1:
        return None
    vals = [p["price"] for p in reversed(prices)]
    gains, losses = 0, 0
    for i in range(1, period + 1):
        diff = vals[-i] - vals[-i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return round(100 - (100 / (1 + rs)), 1)


def moving_average(prices, period):
    if len(prices) < period:
        return None
    vals = [p["price"] for p in prices[:period]]
    return round(sum(vals) / period)


def golden_cross(prices, fast=5, slow=20):
    """Check if fast MA crossed above slow MA (Golden Cross) or below (Death Cross)."""
    if len(prices) < slow + 1:
        return None
    ma_fast_now = moving_average(prices, fast)
    ma_slow_now = moving_average(prices, slow)
    ma_fast_prev = moving_average(prices[1:], fast)
    ma_slow_prev = moving_average(prices[1:], slow)
    if None in (ma_fast_now, ma_slow_now, ma_fast_prev, ma_slow_prev):
        return None
    if ma_fast_prev <= ma_slow_prev and ma_fast_now > ma_slow_now:
        return "golden"
    if ma_fast_prev >= ma_slow_prev and ma_fast_now < ma_slow_now:
        return "death"
    if ma_fast_now > ma_slow_now:
        return "bullish"
    return "bearish"


def volume_analysis(item, lvl=""):
    """Count price updates in last 1h, 6h, 24h."""
    from webapp.database import get_db
    with get_db() as db:
        rows = db.execute(
            "SELECT timestamp FROM prices WHERE item_name=? AND item_lvl=? ORDER BY id DESC LIMIT 1000",
            (item, lvl),
        ).fetchall()
    if not rows:
        return {"1h": 0, "6h": 0, "24h": 0}
    import datetime
    now = datetime.datetime.utcnow()
    h1 = h6 = h24 = 0
    for r in rows:
        try:
            ts = datetime.datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
        except:
            continue
        delta = (now - ts).total_seconds() / 3600
        if delta <= 1:
            h1 += 1
        if delta <= 6:
            h6 += 1
        if delta <= 24:
            h24 += 1
    return {"1h": h1, "6h": h6, "24h": h24}


def get_full_analytics(item, lvl=""):
    """Return all analytics for an item."""
    sells = get_prices_for_rsi(item, lvl, limit=500, type_filter="sell")
    prices = get_price_history(item, lvl, limit=200)

    return {
        "rsi_sell": rsi(sells) if sells else None,
        "ma_fast_5": moving_average(sells, 5) if len(sells) >= 5 else None,
        "ma_slow_20": moving_average(sells, 20) if len(sells) >= 20 else None,
        "ma_slow_50": moving_average(sells, 50) if len(sells) >= 50 else None,
        "golden_cross": golden_cross(sells, 5, 20),
        "volume": volume_analysis(item, lvl),
        "data_points": len(prices),
    }

