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
BATCH_SIZE = 500


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_synced_id": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_max_id():
    conn = sqlite3.connect(DB_LOCAL)
    row = conn.execute("SELECT MAX(id) FROM prices").fetchone()
    conn.close()
    return row[0] if row and row[0] else 0


def get_new_records(last_id, limit=BATCH_SIZE):
    conn = sqlite3.connect(DB_LOCAL)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT item_name, item_lvl, price, type, seller, server, timestamp, last_seen "
        "FROM prices WHERE id > ? ORDER BY id ASC LIMIT ?",
        (last_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def push_batch(records):
    resp = requests.post(SYNC_URL,
                         json={"records": records},
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
    max_id = get_max_id()

    if max_id <= last_id:
        print("Yeni kayit yok.")
        return

    total = max_id - last_id
    print(f"{total} yeni kayit (ID > {last_id})")

    sent = 0
    current_id = last_id

    while True:
        records = get_new_records(current_id)
        if not records:
            break

        inserted = push_batch(records)
        sent += inserted
        current_id_result = current_id

        for r in records:
            pass
        current_id = max_id

        state["last_synced_id"] = current_id
        save_state(state)
        print(f"  {sent}/{total} yuklendi")

        if len(records) < BATCH_SIZE:
            break
        time.sleep(0.3)

    print(f"Tamamlandi: {sent} kayit sendikronize edildi.")


if __name__ == "__main__":
    main()
