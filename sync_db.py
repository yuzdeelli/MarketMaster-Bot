import requests
import os
import sys
import sqlite3
import json
import time

DB_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_state.json")
SYNC_URL = "https://marketmaster.pythonanywhere.com/api/sync"
PA_API_TOKEN = "7628b6d2eb3f90bfb598bec5036aca85aa1cb8b31473f4269c4202e6d047cb7c"
BATCH_SIZE = 100


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_synced_id": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def calc_stats(prices):
    if not prices:
        return {"min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0, "count": 0}
    vals = sorted(prices)
    n = len(vals)
    return {
        "min": vals[0],
        "q1": vals[n // 4] if n > 3 else vals[0],
        "median": vals[n // 2],
        "q3": vals[3 * n // 4] if n > 3 else vals[-1],
        "max": vals[-1],
        "count": n,
    }


def get_batches(last_id):
    conn = sqlite3.connect(DB_LOCAL)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, item_name, item_lvl, price, type, server, timestamp FROM prices WHERE id > ? ORDER BY id ASC LIMIT 50000",
        (last_id,)
    ).fetchall()
    conn.close()

    groups = {}
    max_id = last_id
    for r in rows:
        rid = r["id"]
        if rid > max_id:
            max_id = rid
        key = (r["item_name"], r["item_lvl"], r["server"])
        if key not in groups:
            groups[key] = {"sells": [], "buys": [], "last_price": 0, "last_time": ""}
        if r["type"] == "sell":
            groups[key]["sells"].append(r["price"])
        else:
            groups[key]["buys"].append(r["price"])
        groups[key]["last_price"] = r["price"]
        groups[key]["last_time"] = r["timestamp"] or ""

    return groups, max_id


def push_batch(snapshots):
    resp = requests.post(SYNC_URL,
                         json={"snapshots": snapshots},
                         headers={"X-API-Token": PA_API_TOKEN, "Content-Type": "application/json"},
                         timeout=60)
    if resp.status_code == 200:
        return resp.json().get("inserted", 0)
    print(f"  Hata {resp.status_code}")
    return 0


def main():
    if not os.path.exists(DB_LOCAL):
        print(f"DB bulunamadi: {DB_LOCAL}")
        sys.exit(1)

    state = load_state()
    last_id = state.get("last_synced_id", 0)

    conn = sqlite3.connect(DB_LOCAL)
    max_id = conn.execute("SELECT MAX(id) FROM prices").fetchone()[0] or 0
    conn.close()

    if max_id <= last_id:
        print("Yeni kayit yok.")
        return

    print(f"ID > {last_id} icin snapshot'lar hesaplaniyor...")
    groups, new_max_id = get_batches(last_id)
    print(f"  {len(groups)} item bulundu")

    snapshots = []
    for (name, lvl, server), data in groups.items():
        snap = {
            "item_name": name,
            "item_lvl": lvl or "+0",
            "server": server or "",
            "sell_stats": calc_stats(data["sells"]),
            "buy_stats": calc_stats(data["buys"]),
            "sell_count": len(data["sells"]),
            "buy_count": len(data["buys"]),
            "last_price": data["last_price"],
            "last_time": data["last_time"],
        }
        snapshots.append(snap)

    total = len(snapshots)
    sent = 0
    for i in range(0, total, BATCH_SIZE):
        batch = snapshots[i:i + BATCH_SIZE]
        inserted = push_batch(batch)
        sent += inserted
        pct = int(sent / total * 100)
        print(f"  {sent}/{total} ({pct}%)")
        time.sleep(0.3)

    state["last_synced_id"] = new_max_id
    save_state(state)
    print(f"Tamamlandi: {sent} snapshot yuklendi.")


if __name__ == "__main__":
    main()
