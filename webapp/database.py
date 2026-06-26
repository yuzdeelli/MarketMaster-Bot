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
    with get_db() as db:
        if seller:
            existing = db.execute(
                "SELECT id, price FROM prices WHERE item_name=? AND item_lvl=? AND server=? AND seller=? AND type=?",
                (name, level, norm_server(server), seller, norm_type(ptype))
            ).fetchone()
            if existing:
                if price < existing["price"]:
                    db.execute("UPDATE prices SET price=?, timestamp=CURRENT_TIMESTAMP WHERE id=?", (price, existing["id"]))
                return
        db.execute(
            "INSERT INTO prices (item_name, item_lvl, price, type, server, seller) VALUES (?,?,?,?,?,?)",
            (name, level, price, norm_type(ptype), norm_server(server), seller),
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


def get_ohlc_data(item, lvl="", interval="1440", limit=500, server=None, ptype=None):
    """Her kaydi bir mum olarak dondurur.
    id zaman ekseni olarak kullanilir (otomatik artan = kronolojik siralama).
    Her mum: open=high=low=close=price, volume=1
    interval birlestirme suresi (dakika): 1, 5, 15, 60, 1440 veya 'auto'
    """
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

        if interval == "auto":
            n = len(all_records)
            if n <= 60:
                group = 1
            elif n <= 200:
                group = 2
            elif n <= 500:
                group = 5
            else:
                group = max(1, n // 100)
        else:
            interval_map = {
                "1": 1, "5": 5, "15": 15, "30": 30, "45": 45,
                "60": 60, "120": 120, "240": 240, "480": 480, "960": 960,
                "1440": 1440, "10080": 10080, "20160": 20160, "40320": 40320,
                "80640": 80640, "161280": 161280, "302400": 302400,
                "43200": 43200, "129600": 129600, "259200": 259200, "518400": 518400,
                "W": 10080, "M": 43200,
            }
            group = max(1, interval_map.get(interval, 1))

        use_time_grouping = interval != "auto" and group > 1

        if use_time_grouping:
            bucket_seconds = group * 60
            buckets = {}
            for r in all_records:
                epoch = _parse_timestamp(r["timestamp"])
                if not epoch:
                    continue
                bucket_key = (epoch // bucket_seconds) * bucket_seconds
                if bucket_key not in buckets:
                    buckets[bucket_key] = []
                buckets[bucket_key].append(r)

            chart_data = []
            for bucket_key in sorted(buckets.keys()):
                chunk = buckets[bucket_key]
                prices = [c["price"] for c in chunk]
                ids = [c["id"] for c in chunk]
                chart_data.append({
                    "time": bucket_key,
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
                })
        else:
            chart_data = []
            for idx, i in enumerate(range(0, len(all_records), group)):
                chunk = all_records[i:i + group]
                prices = [c["price"] for c in chunk]
                ids = [c["id"] for c in chunk]
                ts_raw = chunk[0]["timestamp"]
                epoch = _parse_timestamp(ts_raw)
                mid_id = (ids[0] + ids[-1]) / 2
                id_ratio = (mid_id - all_records[0]["id"]) / max(1, all_records[-1]["id"] - all_records[0]["id"])
                if not epoch or ":" not in (ts_raw or ""):
                    epoch = int(id_ratio * 86400) + 1782166400
                chart_data.append({
                    "time": epoch,
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
                })

        chart_data.sort(key=lambda x: x["time"])
        seen = set()
        deduped = []
        for c in chart_data:
            t = c["time"]
            while t in seen:
                t += 1
            c["time"] = t
            seen.add(t)
            deduped.append(c)
        chart_data = deduped

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


def get_prices_for_rsi(item, lvl="", limit=500, type_filter=None):
    with get_db() as db:
        if type_filter:
            rows = db.execute(
                "SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)=? ORDER BY id DESC LIMIT ?",
                (item, lvl, norm_type(type_filter), limit),
            ).fetchall()
            return [dict(r) for r in rows]
        else:
            buys = db.execute(
                "SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='buy' ORDER BY id DESC LIMIT ?",
                (item, lvl, limit),
            ).fetchall()
            sells = db.execute(
                "SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)='sell' ORDER BY id DESC LIMIT ?",
                (item, lvl, limit),
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
