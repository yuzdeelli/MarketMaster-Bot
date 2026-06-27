import requests
import os
import sys
import sqlite3
import json
import time
from datetime import datetime

DB_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_state.json")
SYNC_URL = "https://marketmaster.pythonanywhere.com/api/sync"
PA_API_TOKEN = "7628b6d2eb3f90bfb598bec5036aca85aa1cb8b31473f4269c4202e6d047cb7c"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_synced_id": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_item_list():
    conn = sqlite3.connect(DB_LOCAL)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT item_name, item_lvl, server FROM prices ORDER BY item_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_prices(item_name, item_lvl, server, ptype=None):
    conn = sqlite3.connect(DB_LOCAL)
    conn.row_factory = sqlite3.Row
    query = "SELECT price, timestamp FROM prices WHERE item_name=? AND item_lvl=? AND server LIKE ?"
    params = [item_name, item_lvl, f"%{server}%"]
    if ptype:
        query += " AND type=?"
        params.append(ptype)
    query += " ORDER BY id ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def calc_stats(prices):
    if not prices:
        return {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0, "count": 0}
    vals = sorted([p["price"] for p in prices if p["price"] > 0])
    if not vals:
        return {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0, "count": 0}
    n = len(vals)
    import statistics
    return {
        "min": vals[0],
        "q1": vals[n // 4] if n > 3 else vals[0],
        "median": statistics.median(vals),
        "q3": vals[3 * n // 4] if n > 3 else vals[-1],
        "max": vals[-1],
        "count": n,
    }


def build_snapshot(item_name, item_lvl, server):
    sells = get_prices(item_name, item_lvl, server, "sell")
    buys = get_prices(item_name, item_lvl, server, "buy")
    sell_stats = calc_stats(sells)
    buy_stats = calc_stats(buys)
    all_prices = sells + buys
    return {
        "item_name": item_name,
        "item_lvl": item_lvl,
        "server": server,
        "sell_stats": sell_stats,
        "buy_stats": buy_stats,
        "sell_count": len(sells),
        "buy_count": len(buys),
        "last_price": all_prices[-1]["price"] if all_prices else 0,
        "last_time": all_prices[-1]["timestamp"] if all_prices else "",
    }


def push_snapshots(snapshots):
    resp = requests.post(SYNC_URL,
                         json={"snapshots": snapshots},
                         headers={
                             "X-API-Token": PA_API_TOKEN,
                             "Content-Type": "application/json"
                         },
                         timeout=60)
    if resp.status_code == 200:
        return resp.json().get("inserted", 0)
    print(f"  Hata {resp.status_code}: {resp.text[:200]}")
    return 0


def main():
    if not os.path.exists(DB_LOCAL):
        print(f"DB bulunamadi: {DB_LOCAL}")
        sys.exit(1)

    state = load_state()
    last_id = state.get("last_synced_id", 0)

    conn = sqlite3.connect(DB_LOCAL)
    row = conn.execute("SELECT MAX(id) FROM prices").fetchone()
    max_id = row[0] if row and row[0] else 0
    conn.close()

    if max_id <= last_id:
        print("Yeni kayit yok.")
        return

    print(f"Yeni veri var (ID > {last_id}). Snapshot'lar hesaplaniyor...")
    items = get_item_list()
    snapshots = []
    for item in items:
        snap = build_snapshot(item["item_name"], item["item_lvl"], item["server"])
        snapshots.append(snap)

    print(f"  {len(snapshots)} item snapshot hazir")

    inserted = push_snapshots(snapshots)
    print(f"  PA'ye {inserted} snapshot yuklendi")

    state["last_synced_id"] = max_id
    state["snapshot_count"] = len(snapshots)
    save_state(state)
    print("Tamamlandi!")


if __name__ == "__main__":
    main()
