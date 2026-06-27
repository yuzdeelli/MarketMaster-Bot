import sqlite3
import os
import sys
import json
from datetime import datetime
import re

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(BASE_DIR, "app_data.db")
_TICKER_FILE = os.path.join(BASE_DIR, "ticker.json")


def _should_hide_buy(item_name):
    try:
        with open(_TICKER_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        hide_list = cfg.get("hide_buy_for", [])
        return item_name.lower() in [h.lower() for h in hide_list]
    except Exception:
        return False


SERVER_MAP = {
    "Tüm Zero": "Zero", "Tum Zero": "Zero",
    "Tüm Pandora": "Pandora", "Tum Pandora": "Pandora",
    "Tüm Agartha": "Agartha", "Tum Agartha": "Agartha",
    "Tüm Felis": "Felis", "Tum Felis": "Felis",
    "Tüm Destan": "Destan", "Tum Destan": "Destan",
    "Tüm Minark": "Minark", "Tum Minark": "Minark",
    "Tüm Dryads": "Dryads", "Tum Dryads": "Dryads",
    "Tüm Oreads": "Oreads", "Tum Oreads": "Oreads",
}


def norm_type(t):
    return t.strip().lower()


def norm_server(s):
    s = s.strip()
    return SERVER_MAP.get(s, s)


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL DEFAULT '',
                item_lvl TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('buy','sell')),
                server TEXT NOT NULL DEFAULT '',
                seller TEXT NOT NULL DEFAULT '',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_item_lvl ON prices(item_name, item_lvl)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON prices(timestamp)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_seller ON prices(seller)")
        try:
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_listing ON prices(item_name, item_lvl, server, seller, type)")
        except Exception:
            pass
        db.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                lvl TEXT NOT NULL DEFAULT '',
                server TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_search_item ON search_history(item)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_history(timestamp)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS item_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Genel',
                items TEXT NOT NULL DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_list_category ON item_lists(category)")
        db.commit()


def insert_price(item, lvl, price, ptype, server="", seller=""):
    from core.engine import should_skip_record, is_reverse_level
    name = (item or '').strip()
    level = (lvl or '').strip()
    if not level:
        m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)R?\)\s*$", name)
        if not m:
            m = re.search(r"^(.*?)[\s]*\+([0-9]+)R?\s*$", name)
        if m:
            name = m.group(1).strip()
            level = '+' + m.group(2)
    name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()

    # +0 FILTRESI (reverse degilse uygula)
    if not is_reverse_level(level) and should_skip_record(name, level):
        return

    seller = (seller or '').strip()
    price = int(price)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        if seller:
            existing = db.execute(
                "SELECT id, price FROM prices WHERE item_name=? AND item_lvl=? AND server=? AND seller=? AND type=?",
                (name, level, norm_server(server), seller, norm_type(ptype))
            ).fetchone()
            if existing:
                if price < existing["price"]:
                    db.execute("UPDATE prices SET price=?, timestamp=?, last_seen=? WHERE id=?", (price, now, now, existing["id"]))
                else:
                    db.execute("UPDATE prices SET last_seen=? WHERE id=?", (now, existing["id"]))
                return
        db.execute(
            "INSERT INTO prices (item_name, item_lvl, price, type, server, seller, timestamp, last_seen) VALUES (?,?,?,?,?,?,?,?)",
            (name, level, price, norm_type(ptype), norm_server(server), seller, now, now),
        )


def insert_prices_batch(prices):
    from core.engine import should_skip_record, is_reverse_level
    with get_db() as db:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for p in prices:
            name = (p.get("item") or "").strip()
            level = (p.get("lvl") or "").strip()
            if not level:
                m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)R?\)\s*$", name)
                if not m:
                    m = re.search(r"^(.*?)[\s]*\+([0-9]+)R?\s*$", name)
                if m:
                    name = m.group(1).strip()
                    level = '+' + m.group(2)
            name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()

            # +0 FILTRESI (reverse degilse uygula)
            if not is_reverse_level(level) and should_skip_record(name, level):
                continue

            seller = (p.get("seller") or "").strip()
            price = int(p["price"])
            srv = norm_server(p.get("server", ""))
            ptype = norm_type(p["type"])
            if seller:
                existing = db.execute(
                    "SELECT id, price FROM prices WHERE item_name=? AND item_lvl=? AND server=? AND seller=? AND type=?",
                    (name, level, srv, seller, ptype)
                ).fetchone()
                if existing:
                    if price < existing["price"]:
                        db.execute("UPDATE prices SET price=?, last_seen=? WHERE id=?", (price, now, existing["id"]))
                    else:
                        db.execute("UPDATE prices SET last_seen=? WHERE id=?", (now, existing["id"]))
                    continue
            db.execute(
                "INSERT INTO prices (item_name, item_lvl, price, type, server, seller, last_seen) VALUES (?,?,?,?,?,?,?)",
                (name, level, price, ptype, srv, seller, now),
            )


def _time_filter(hours=None):
    if hours and hours > 0:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d")
        return f" AND timestamp >= ?", cutoff
    return "", None


def _calc_stats(db, item, lvl, ptype, hours=None, server=None):
    if ptype.lower() == "buy" and _should_hide_buy(item):
        return None
    tf, tf_param = _time_filter(hours)
    sf = ""
    lf = ""
    params = [item]
    if lvl:
        lf = " AND item_lvl=?"
        params.append(lvl)
    params.append(norm_type(ptype))
    if server:
        sf = " AND LOWER(TRIM(server)) LIKE LOWER(?)"
        params.append(f"%{server}%")
    if tf_param:
        params.append(tf_param)
    rows = db.execute(
        f"SELECT price, seller FROM prices WHERE item_name=?{lf} AND LOWER(type)=?{sf}{tf} ORDER BY price",
        params,
    ).fetchall()
    if not rows:
        return None
    all_vals = [r["price"] for r in rows]
    all_sellers = set(r["seller"] for r in rows if r["seller"])
    n_all = len(all_vals)
    ns = len(all_sellers) if all_sellers else n_all

    vals_sorted = sorted(all_vals)
    q1_idx = int(n_all * 0.25)
    q3_idx = int(n_all * 0.75)
    q1 = vals_sorted[q1_idx] if n_all >= 4 else vals_sorted[0]
    q3 = vals_sorted[q3_idx] if n_all >= 4 else vals_sorted[-1]
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    vals = [v for v in all_vals if lower_bound <= v <= upper_bound]
    if len(vals) < 3:
        vals = all_vals

    n = len(vals)
    vals_sorted = sorted(vals)
    median = vals_sorted[n // 2] if n % 2 else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) // 2
    trimmed_q1 = vals_sorted[n // 4] if n >= 4 else vals_sorted[0]
    trimmed_q3 = vals_sorted[3 * n // 4] if n >= 4 else vals_sorted[-1]
    mean_val = sum(vals) / n
    variance = sum((v - mean_val) ** 2 for v in vals) / n
    std = round(variance ** 0.5)
    trimmed_iqr = trimmed_q3 - trimmed_q1
    hata = round((std / mean_val) * 100, 1) if mean_val > 0 else 0
    return {
        "min": vals_sorted[0],
        "max": vals_sorted[-1],
        "avg": round(mean_val),
        "median": median,
        "q1": trimmed_q1,
        "q3": trimmed_q3,
        "std": std,
        "iqr": trimmed_iqr,
        "hata": hata,
        "count": n,
        "sellers": ns,
    }


def get_item_stats(item, lvl="", hours=None, server=None):
    with get_db() as db:
        tf, tf_param = _time_filter(hours)
        sf = ""
        lf = ""
        params = [item]
        if lvl:
            lf = " AND item_lvl=?"
            params.append(lvl)
        if server:
            sf = " AND LOWER(TRIM(server)) LIKE LOWER(?)"
            params.append(f"%{server}%")
        if tf_param:
            params.append(tf_param)
        cnt = db.execute(
            f"SELECT COUNT(*) FROM prices WHERE item_name=?{lf}{sf}{tf}", params
        ).fetchone()[0]
        if cnt == 0:
            return None
        buy = _calc_stats(db, item, lvl, "buy", hours, server)
        sell = _calc_stats(db, item, lvl, "sell", hours, server)
        return {"buy": buy, "sell": sell}


def get_price_history(item, lvl="", limit=200, server=None, ptype=None):
    with get_db() as db:
        query = "SELECT id, price, type, server, timestamp FROM prices WHERE item_name=? AND item_lvl=?"
        params = [item, lvl]
        if server:
            query += " AND LOWER(TRIM(server)) LIKE LOWER(?)"
            params.append(f"%{server}%")
        if ptype:
            query += " AND LOWER(type)=?"
            params.append(ptype.lower())
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def _parse_timestamp(ts):
    """Parse various timestamp formats, return epoch seconds (UTC) or None."""
    if not ts:
        return None
    ts = ts.strip()
    try:
        from datetime import timezone
        if "." in ts and ":" in ts:
            dt = datetime.strptime(ts, "%d.%m.%Y %H:%M:%S")
        elif "." in ts and ts.count(".") == 2:
            dt = datetime.strptime(ts, "%d.%m.%Y")
            dt = dt.replace(hour=12, minute=0, second=0)
        elif "-" in ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
            dt = dt.replace(tzinfo=None)
        else:
            return None
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return None


def get_ohlc_data(item, lvl="", interval="1440", limit=500, server=None, ptype=None, candle_size=None):
    """Pandas resample+ffill mantigi ile OHLC olusturma.
    1) Veritabanindan ham kayitlari cek
    2) IQR ile aykirilari temizle
    3) Timestamp'leri parse et, epoch'a cevir
    4) View range ile filtrele (son N dakika)
    5) Candle size'a gore resample (open=first, high=max, low=min, close=last, volume=sum)
    6) Ffill: bos mumlari onceki fiyatla doldur
    candle_size: saniye cinsinden mum boyutu (interval'dan bagimsiz, opsiyonel override)
    """
    from datetime import timedelta

    TIMEFRAME_CONFIG = {
        "15":  (timedelta(minutes=15),  5 * 60),
        "30":  (timedelta(minutes=30),  5 * 60),
        "45":  (timedelta(minutes=45),  5 * 60),
        "60":  (timedelta(hours=1),     5 * 60),
        "120": (timedelta(hours=2),     5 * 60),
        "240": (timedelta(hours=4),     15 * 60),
        "480": (timedelta(hours=8),     15 * 60),
        "960": (timedelta(hours=16),    30 * 60),
        "1440":(timedelta(hours=24),    30 * 60),
        "10080":(timedelta(days=7),     3600),
        "20160":(timedelta(days=14),    3600),
        "40320":(timedelta(days=28),    3600),
        "80640":(timedelta(days=56),    7200),
        "161280":(timedelta(days=112),  7200),
        "302400":(timedelta(days=365),  86400),
        "43200":(timedelta(days=30),    86400),
        "129600":(timedelta(days=90),   86400),
        "259200":(timedelta(days=180),  86400),
        "518400":(timedelta(days=365),  86400),
    }

    AUTO_CONFIGS = [
        (30,    timedelta(minutes=15),  60),
        (100,   timedelta(hours=1),     5 * 60),
        (300,   timedelta(hours=4),     15 * 60),
        (1000,  timedelta(days=1),      30 * 60),
        (5000,  timedelta(days=7),      3600),
        (20000, timedelta(days=30),     86400),
    ]

    with get_db() as db:
        query = "SELECT id, item_name, item_lvl, price, type, seller, timestamp FROM prices WHERE item_name=? AND item_lvl=?"
        params = [item, lvl]
        if server:
            query += " AND LOWER(TRIM(server)) LIKE LOWER(?)"
            params.append(f"%{server}%")
        if ptype:
            query += " AND LOWER(type)=?"
            params.append(ptype.lower())
        query += " ORDER BY id ASC"
        rows = db.execute(query, params).fetchall()

        if not rows:
            return []

        all_records = []
        for r in rows:
            price = float(r["price"])
            if price <= 0:
                continue
            all_records.append({
                "id": int(r["id"]),
                "item_name": str(r["item_name"]),
                "item_lvl": str(r["item_lvl"]),
                "price": price,
                "type": str(r["type"]),
                "seller": str(r["seller"] or ""),
                "timestamp": str(r["timestamp"] or ""),
            })

        if not all_records:
            return []

        prices_all = sorted([r["price"] for r in all_records])
        n_prices = len(prices_all)
        if n_prices > 5:
            q1_idx = int(n_prices * 0.25)
            q3_idx = int(n_prices * 0.75)
            q1 = prices_all[q1_idx]
            q3 = prices_all[q3_idx]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            all_records = [r for r in all_records if lower_bound <= r["price"] <= upper_bound]

        if not all_records:
            return []

        for r in all_records:
            r["epoch"] = _parse_timestamp(r["timestamp"])

        all_records.sort(key=lambda r: r["epoch"] or 0)

        ts_samples = [r["timestamp"] for r in all_records[:20] if r["timestamp"]]
        has_real_time = any(
            ":" in str(ts) and "12:00:00" not in str(ts) for ts in ts_samples
        )

        if not has_real_time:
            min_id = all_records[0]["id"]
            max_id = all_records[-1]["id"]
            id_range = max(1, max_id - min_id)
            now_epoch = int(datetime.utcnow().timestamp())

            if interval == "auto":
                view_sec = int(timedelta(days=30).total_seconds())
            elif TIMEFRAME_CONFIG.get(interval):
                view_sec = int(TIMEFRAME_CONFIG[interval][0].total_seconds())
            else:
                view_sec = 86400

            end_epoch = now_epoch
            start_epoch = end_epoch - view_sec

            for r in all_records:
                id_ratio = (r["id"] - min_id) / id_range
                r["epoch"] = start_epoch + int(id_ratio * view_sec)
        else:
            timed = [r for r in all_records if r["epoch"]]
            untimed = [r for r in all_records if not r["epoch"]]

            if timed and untimed:
                min_id_t = min(r["id"] for r in timed)
                max_id_t = max(r["id"] for r in timed)
                min_epoch_t = min(r["epoch"] for r in timed)
                max_epoch_t = max(r["epoch"] for r in timed)
                id_range = max(1, max_id_t - min_id_t)
                epoch_range = max(1, max_epoch_t - min_epoch_t)
                for r in untimed:
                    id_ratio = (r["id"] - min_id_t) / id_range
                    r["epoch"] = min_epoch_t + int(id_ratio * epoch_range)

        all_records.sort(key=lambda r: r["epoch"] or 0)

        max_epoch = all_records[-1]["epoch"]
        if not max_epoch:
            return []

        if interval == "auto":
            n = len(all_records)
            view_sec = None
            candle_sec = None
            for threshold, v, c in AUTO_CONFIGS:
                if n <= threshold:
                    view_sec = int(v.total_seconds())
                    candle_sec = c
                    break
            if view_sec is None:
                view_sec = int(timedelta(days=365).total_seconds())
                candle_sec = 86400
        else:
            cfg = TIMEFRAME_CONFIG.get(interval)
            if cfg:
                view_sec = int(cfg[0].total_seconds())
                candle_sec = cfg[1]
            else:
                view_sec = 86400
                candle_sec = 30 * 60

        if candle_size is not None:
            candle_sec = int(candle_size)

        start_epoch = max_epoch - view_sec

        chart_data = []
        last_close = None
        last_record = None
        bucket_t = (start_epoch // candle_sec) * candle_sec
        end_bucket = (max_epoch // candle_sec) * candle_sec

        buckets = {}
        for r in all_records:
            epoch = r["epoch"]
            if not epoch or epoch < start_epoch:
                continue
            bkey = (epoch // candle_sec) * candle_sec
            if bkey not in buckets:
                buckets[bkey] = []
            buckets[bkey].append(r)

        while bucket_t <= end_bucket:
            if bucket_t in buckets:
                chunk = buckets[bucket_t]
                prices = [c["price"] for c in chunk]
                ids = [c["id"] for c in chunk]
                bar = {
                    "time": bucket_t,
                    "open": prices[0],
                    "high": max(prices),
                    "low": min(prices),
                    "close": prices[-1],
                    "volume": len(prices),
                    "item_name": chunk[0]["item_name"],
                    "item_lvl": chunk[0]["item_lvl"],
                    "timestamp": chunk[0]["timestamp"],
                    "seller": chunk[0]["seller"],
                    "first_id": ids[0],
                    "last_id": ids[-1],
                }
                last_close = prices[-1]
                last_record = bar
            elif last_close is not None:
                bar = {
                    "time": bucket_t,
                    "open": last_close,
                    "high": last_close,
                    "low": last_close,
                    "close": last_close,
                    "volume": 0,
                    "item_name": last_record["item_name"] if last_record else "",
                    "item_lvl": last_record["item_lvl"] if last_record else "",
                    "timestamp": "",
                    "seller": "",
                    "first_id": last_record["first_id"] if last_record else 0,
                    "last_id": last_record["last_id"] if last_record else 0,
                }
            else:
                bucket_t += candle_sec
                continue

            chart_data.append(bar)
            bucket_t += candle_sec

        if len(chart_data) > 2:
            filled = [b for b in chart_data if b["volume"] > 0]
            if len(filled) >= 2:
                for i in range(len(chart_data)):
                    if chart_data[i]["volume"] == 0:
                        prev_idx = None
                        next_idx = None
                        for j in range(i - 1, -1, -1):
                            if chart_data[j]["volume"] > 0:
                                prev_idx = j
                                break
                        for j in range(i + 1, len(chart_data)):
                            if chart_data[j]["volume"] > 0:
                                next_idx = j
                                break
                        if prev_idx is not None and next_idx is not None:
                            prev_close = chart_data[prev_idx]["close"]
                            next_open = chart_data[next_idx]["open"]
                            span = next_idx - prev_idx
                            step = (i - prev_idx) / span
                            interp = prev_close + (next_open - prev_close) * step
                            chart_data[i]["open"] = interp
                            chart_data[i]["high"] = interp
                            chart_data[i]["low"] = interp
                            chart_data[i]["close"] = interp
                        elif prev_idx is not None:
                            chart_data[i]["open"] = chart_data[prev_idx]["close"]
                            chart_data[i]["high"] = chart_data[prev_idx]["close"]
                            chart_data[i]["low"] = chart_data[prev_idx]["close"]
                            chart_data[i]["close"] = chart_data[prev_idx]["close"]

        return chart_data[-limit:]


def get_ohlc_summary(item, lvl="", server=None):
    """Tek bir item icin ozet: toplam satis adedi, medyan, ham fiyat listesi."""
    sells = get_price_history(item, lvl, limit=500, server=server, ptype="sell")
    if not sells:
        return {"count": 0, "median": 0, "prices": [], "confidence": "none"}

    prices = [p["price"] for p in sells if p["price"] > 0]
    if not prices:
        return {"count": 0, "median": 0, "prices": [], "confidence": "none"}

    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    if n == 1:
        median = prices_sorted[0]
    elif n % 2 == 1:
        median = prices_sorted[n // 2]
    else:
        median = (prices_sorted[n // 2 - 1] + prices_sorted[n // 2]) // 2

    if n == 1:
        confidence = "single"
    elif n <= 3:
        confidence = "low"
    elif n <= 10:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "count": n,
        "median": median,
        "min": prices_sorted[0],
        "max": prices_sorted[-1],
        "prices": prices[:20],
        "confidence": confidence,
    }


def get_all_items(hours=None):
    with get_db() as db:
        tf, tf_param = _time_filter(hours)
        params = []
        if tf_param:
            params.append(tf_param)
        rows = db.execute(
            f"SELECT DISTINCT item_name AS item, item_lvl AS lvl FROM prices WHERE 1=1{tf} ORDER BY item_name",
            params
        ).fetchall()
        return [dict(r) for r in rows]


def get_unique_servers():
    with get_db() as db:
        rows = db.execute("SELECT DISTINCT server FROM prices WHERE server!=''").fetchall()
        db_servers = set()
        for r in rows:
            s = norm_server(r["server"])
            if s:
                db_servers.add(s)
    desired_order = ["Zero", "Pandora", "Agartha", "Felis", "Destan", "Minark", "Dryads", "Oreads"]
    ordered = [s for s in desired_order if s in db_servers]
    # Fallback: if ordered empty but db_servers has names, return them raw
    if not ordered:
        return sorted(db_servers)
    return ordered


def get_db_stats(hours=None):
    with get_db() as db:
        tf, tf_param = _time_filter(hours)
        params = []
        if tf_param:
            params.append(tf_param)
        items = db.execute(f"SELECT COUNT(DISTINCT item_name || item_lvl) FROM prices WHERE 1=1{tf}", params).fetchone()[0]
        params2 = []
        if tf_param:
            params2.append(tf_param)
        servers = db.execute(f"SELECT COUNT(DISTINCT server) FROM prices WHERE server!='' AND 1=1{tf}", params2).fetchone()[0]
        params3 = []
        if tf_param:
            params3.append(tf_param)
        total = db.execute(f"SELECT COUNT(*) FROM prices WHERE 1=1{tf}", params3).fetchone()[0]
        last = db.execute("SELECT MAX(timestamp) FROM prices").fetchone()[0]
        return {"items": items, "servers": servers, "total_prices": total, "last_scan": last or "-"}


def get_item_stats_for_server(item, lvl, server, hours=None):
    with get_db() as db:
        tf, tf_param = _time_filter(hours)
        params = [item, lvl, f"%{server}%"]
        if tf_param:
            params.append(tf_param)
        cnt = db.execute(
            f"SELECT COUNT(*) FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(TRIM(server)) LIKE LOWER(?) {tf}", params
        ).fetchone()[0]
        if cnt == 0:
            return None
        params_buy = [item, lvl, f"%{server}%"]
        if tf_param:
            params_buy.append(tf_param)
        buy = db.execute(
            f"SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='buy' AND LOWER(TRIM(server)) LIKE LOWER(?) {tf} ORDER BY price",
            params_buy,
        ).fetchall()
        params_sell = [item, lvl, f"%{server}%"]
        if tf_param:
            params_sell.append(tf_param)
        sell = db.execute(
            f"SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='sell' AND LOWER(TRIM(server)) LIKE LOWER(?) {tf} ORDER BY price",
            params_sell,
        ).fetchall()

        def calc(vals):
            if not vals:
                return None
            n = len(vals)
            median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) // 2
            return {"min": vals[0], "max": vals[-1], "avg": round(sum(vals) / n), "median": median}

        buy_vals = [r["price"] for r in buy]
        sell_vals = [r["price"] for r in sell]
        return {"buy": calc(buy_vals), "sell": calc(sell_vals)}


def get_all_items_for_server(server, hours=None):
    with get_db() as db:
        tf, tf_param = _time_filter(hours)
        params = [f"%{server}%"]
        if tf_param:
            params.append(tf_param)
        rows = db.execute(
            f"SELECT DISTINCT item_name AS item, item_lvl AS lvl FROM prices WHERE LOWER(TRIM(server)) LIKE LOWER(?) {tf} ORDER BY item_name",
            params
        ).fetchall()
        return [dict(r) for r in rows]


def get_prices_for_rsi(item, lvl="", limit=500, type_filter=None, server=None):
    with get_db() as db:
        sf = ""
        sparams = []
        if server:
            sf = " AND LOWER(TRIM(server)) LIKE LOWER(?)"
            sparams = [f"%{server}%"]
        if type_filter:
            rows = db.execute(
                f"SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)=?{sf} ORDER BY id DESC LIMIT ?",
                (item, lvl, norm_type(type_filter)) + tuple(sparams) + (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        else:
            buys = db.execute(
                f"SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='buy'{sf} ORDER BY id DESC LIMIT ?",
                (item, lvl) + tuple(sparams) + (limit,),
            ).fetchall()
            sells = db.execute(
                f"SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='sell'{sf} ORDER BY id DESC LIMIT ?",
                (item, lvl) + tuple(sparams) + (limit,),
            ).fetchall()
            return [dict(r) for r in buys], [dict(r) for r in sells]


def save_search(item, lvl="", server=""):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    name = (item or '').strip()
    level = (lvl or '').strip()
    # extract and normalize like insert_price
    if not level:
        m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)R?\)\s*$", name)
        if not m:
            m = re.search(r"^(.*?)[\s]*\+([0-9]+)R?\s*$", name)
        if m:
            name = m.group(1).strip()
            level = '+' + m.group(2)
    name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()
    with get_db() as db:
        db.execute(
            "INSERT INTO search_history (item, lvl, server, timestamp) VALUES (?,?,?,?)",
            (name, level, server.strip(), ts),
        )


def get_search_history(limit=50):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM search_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_popular_searches(limit=20):
    with get_db() as db:
        rows = db.execute(
            """SELECT item, lvl, COUNT(*) as count 
               FROM search_history 
               GROUP BY item, lvl 
               ORDER BY count DESC 
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def search_items(query):
    with get_db() as db:
        q = query.lower().strip()
        rows = db.execute(
            """SELECT DISTINCT item_name AS item, item_lvl AS lvl,
               CASE
                 WHEN LOWER(item_name) = ? THEN 1
                 WHEN LOWER(item_name) LIKE ? THEN 2
                 WHEN LOWER(item_name) LIKE ? THEN 3
                 ELSE 4
               END AS rank
               FROM prices
               WHERE LOWER(item_name) LIKE ?
               ORDER BY rank, item_name""",
            (q, q + "%", "%" + q + "%", f"%{q}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_item_names():
    with get_db() as db:
        rows = db.execute("SELECT DISTINCT item_name FROM prices ORDER BY item_name").fetchall()
        return [r["item_name"] for r in rows]


def normalize_existing_data():
    """One-time migration: normalize item names by stripping (+N) suffixes into item_lvl."""
    import re as _re
    with get_db() as db:
        db.execute("UPDATE prices SET item_lvl='+0' WHERE item_lvl='' OR item_lvl IS NULL")
        rows = db.execute("SELECT DISTINCT item_name, item_lvl FROM prices").fetchall()
        fixed = 0
        for r in rows:
            name = r["item_name"]
            lvl = r["item_lvl"]
            new_name = name
            new_lvl = lvl
            if not lvl or not lvl.strip():
                m = _re.search(r"^(.*?)[\s]*\(\+?([0-9]+)R?\)\s*$", name)
                if not m:
                    m = _re.search(r"^(.*?)[\s]*\+([0-9]+)R?\s*$", name)
                if m:
                    new_name = m.group(1).strip()
                    new_lvl = '+' + m.group(2)
            new_name = _re.sub(r"\(\+?[0-9]+R?\)\s*$", "", new_name).strip()
            if new_name != name or new_lvl != lvl:
                db.execute(
                    "UPDATE prices SET item_name=?, item_lvl=? WHERE item_name=? AND item_lvl=?",
                    (new_name, new_lvl, name, lvl),
                )
                fixed += 1
                db.commit()
        return fixed


def cleanup_stale_listings(hours=24):
    with get_db() as db:
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        result = db.execute(
            "DELETE FROM prices WHERE last_seen < ?", (cutoff,)
        )
        db.commit()
        deleted = result.rowcount
        return deleted


def get_historical_extremes(item, lvl="", server=None):
    """Gecmiste en dusuk ve en yuksek alis/satis fiyatlarini dondur (%1 outlier hariç)."""
    with get_db() as db:
        result = {}
        for ptype in ("buy", "sell"):
            query = "SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)=? ORDER BY price"
            params = [item, lvl, ptype]
            if server:
                query += " AND LOWER(TRIM(server)) LIKE LOWER(?)"
                params.append(f"%{server}%")
            rows = db.execute(query, params).fetchall()
            if rows and len(rows) > 2:
                prices = [r[0] for r in rows]
                n = len(prices)
                lower_idx = max(0, int(n * 0.01))
                upper_idx = min(n - 1, int(n * 0.99))
                result[ptype] = {"min": prices[lower_idx], "max": prices[upper_idx]}
            elif rows:
                prices = [r[0] for r in rows]
                result[ptype] = {"min": min(prices), "max": max(prices)}
            else:
                result[ptype] = {"min": 0, "max": 0}
        return result


def get_previous_prices(item, lvl="", server=None):
    """Son iki kaydi dondur: onceki ve guncel alis/satis fiyatlarini karsilastirmak icin."""
    with get_db() as db:
        result = {}
        for ptype in ("buy", "sell"):
            query = "SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)=?"
            params = [item, lvl, ptype]
            if server:
                query += " AND LOWER(TRIM(server)) LIKE LOWER(?)"
                params.append(f"%{server}%")
            query += " ORDER BY id DESC LIMIT 2"
            rows = db.execute(query, params).fetchall()
            if len(rows) >= 2:
                result[ptype] = {"current": rows[0][0], "previous": rows[1][0]}
            elif len(rows) == 1:
                result[ptype] = {"current": rows[0][0], "previous": 0}
            else:
                result[ptype] = {"current": 0, "previous": 0}
        return result


import json

def save_item_list(name, category, items):
    with get_db() as db:
        db.execute(
            "INSERT INTO item_lists (name, category, items) VALUES (?, ?, ?)",
            (name, category, json.dumps(items, ensure_ascii=False))
        )
        db.commit()

def update_item_list(list_id, name, category, items):
    with get_db() as db:
        db.execute(
            "UPDATE item_lists SET name=?, category=?, items=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (name, category, json.dumps(items, ensure_ascii=False), list_id)
        )
        db.commit()

def delete_item_list(list_id):
    with get_db() as db:
        db.execute("DELETE FROM item_lists WHERE id=?", (list_id,))
        db.commit()

def get_all_item_lists():
    with get_db() as db:
        rows = db.execute("SELECT id, name, category, items, created_at, updated_at FROM item_lists ORDER BY category, name").fetchall()
    result = []
    for r in rows:
        try:
            items = json.loads(r["items"])
        except Exception:
            items = []
        result.append({"id": r["id"], "name": r["name"], "category": r["category"], "items": items, "created_at": r["created_at"], "updated_at": r["updated_at"]})
    return result

def get_item_lists_by_category(category):
    with get_db() as db:
        rows = db.execute("SELECT id, name, category, items, created_at, updated_at FROM item_lists WHERE category=? ORDER BY name", (category,)).fetchall()
    result = []
    for r in rows:
        try:
            items = json.loads(r["items"])
        except Exception:
            items = []
        result.append({"id": r["id"], "name": r["name"], "category": r["category"], "items": items, "created_at": r["created_at"], "updated_at": r["updated_at"]})
    return result

def get_list_categories():
    with get_db() as db:
        rows = db.execute("SELECT DISTINCT category FROM item_lists ORDER BY category").fetchall()
    return [r["category"] for r in rows]
