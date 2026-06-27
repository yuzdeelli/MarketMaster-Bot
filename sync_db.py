import requests
import os
import sys
import time
import hashlib
import sqlite3
import json

PYTHONANYWHERE_USER = "marketmaster"
HOME_DIR = f"/home/{PYTHONANYWHERE_USER}"
PYTHONANYWHERE_TOKEN = "fd5c80513edc6ec7218745dc9d7a8787bcc11597"
BASE_URL = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}"
DB_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")
DB_REMOTE_PATH = "app_data.db"
HASH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sync_hash")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_state.json")
UPLOAD_TIMEOUT = 600
MAX_RETRIES = 5
SYNC_URL = "https://marketmaster.pythonanywhere.com/api/sync"
BATCH_SIZE = 500


def get_token():
    if PYTHONANYWHERE_TOKEN:
        return PYTHONANYWHERE_TOKEN
    return os.environ.get("PYTHONANYWHERE_TOKEN", "")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_synced_id": 0, "mode": "full"}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def vacuum_db():
    try:
        conn = sqlite3.connect(DB_LOCAL)
        conn.execute("VACUUM")
        conn.close()
    except Exception:
        pass


def upload_file(token, local_path, remote_path, timeout=UPLOAD_TIMEOUT):
    full_path = f"{HOME_DIR}/{remote_path}"
    url = f"{BASE_URL}/files/path/{full_path}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(local_path, "rb") as f:
                resp = requests.post(url, files={"content": f},
                                     headers={"Authorization": f"Token {token}"},
                                     timeout=(60, timeout))
            if resp.status_code in (200, 201):
                return resp.status_code
            if attempt < MAX_RETRIES:
                time.sleep(15 * attempt)
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(15 * attempt)
    return 0


def full_sync(token):
    if not os.path.exists(DB_LOCAL):
        print(f"DB bulunamadi: {DB_LOCAL}")
        return False

    vacuum_db()
    size_mb = os.path.getsize(DB_LOCAL) / (1024 * 1024)
    print(f"FULL SYNC: DB yukleniyor ({size_mb:.1f} MB)...")

    current_hash = file_hash(DB_LOCAL)
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE) as f:
            if f.read().strip() == current_hash:
                print("  DB degisiklik yok.")
                return True

    code = upload_file(token, DB_LOCAL, DB_REMOTE_PATH)
    if code in (200, 201):
        print("  DB yuklendi!")
        with open(HASH_FILE, "w") as f:
            f.write(current_hash)
        state = load_state()
        max_id = get_max_id()
        state["last_synced_id"] = max_id
        state["mode"] = "incremental"
        save_state(state)
        return True
    print(f"  Yukleme basarisiz ({code})")
    return False


def get_max_id():
    try:
        conn = sqlite3.connect(DB_LOCAL)
        row = conn.execute("SELECT MAX(id) FROM prices").fetchone()
        conn.close()
        return row[0] if row and row[0] else 0
    except Exception:
        return 0


def get_new_records(last_id, limit=BATCH_SIZE):
    try:
        conn = sqlite3.connect(DB_LOCAL)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, item_name, item_lvl, price, type, seller, server, timestamp, last_seen "
            "FROM prices WHERE id > ? ORDER BY id ASC LIMIT ?",
            (last_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def incremental_sync(token):
    state = load_state()
    last_id = state.get("last_synced_id", 0)
    max_id = get_max_id()

    if max_id <= last_id:
        print("INC SYNC: Yeni kayit yok.")
        return True

    new_count = max_id - last_id
    print(f"INC SYNC: {new_count} yeni kayit (ID > {last_id})...")

    total_sent = 0
    batch_num = 0
    current_id = last_id

    while True:
        records = get_new_records(current_id)
        if not records:
            break

        batch_num += 1
        try:
            resp = requests.post(SYNC_URL,
                                 json={"records": records},
                                 headers={
                                     "Authorization": f"Token {token}",
                                     "Content-Type": "application/json"
                                 },
                                 timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                sent = data.get("inserted", len(records))
                total_sent += sent
                current_id = records[-1]["id"]
                print(f"  Batch {batch_num}: {sent} kayit yuklendi (ID: {current_id})")
                state["last_synced_id"] = current_id
                save_state(state)
            else:
                print(f"  Batch {batch_num}: Hata {resp.status_code}")
                return False
        except Exception as e:
            print(f"  Batch {batch_num}: {type(e).__name__}")
            return False

        if len(records) < BATCH_SIZE:
            break
        time.sleep(0.5)

    print(f"INC SYNC: Toplam {total_sent} kayit senkronize edildi.")
    return True


def check_dns():
    import socket
    for i in range(3):
        try:
            socket.getaddrinfo("www.pythonanywhere.com", 443)
            return True
        except socket.gaierror:
            if i < 2:
                time.sleep(5 * (i + 1))
                os.system("ipconfig /flushdns >nul 2>&1")
    return False


def main():
    token = get_token()
    if not token:
        print("Token gerekli!")
        sys.exit(1)

    if not check_dns():
        print("DNS cozulemedi, senkron iptal!")
        sys.exit(1)

    state = load_state()

    if state.get("mode") == "full" or not os.path.exists(DB_LOCAL):
        if full_sync(token):
            print("\nFull sync tamamlandi!")
        else:
            print("\nFull sync basarisiz!")
            sys.exit(1)
    else:
        if incremental_sync(token):
            print("\nIncremental sync tamamlandi!")
        else:
            print("\nIncremental sync basarisiz, full sync deneniyor...")
            if full_sync(token):
                print("\nFull sync tamamlandi!")
            else:
                print("\nSenkron basarisiz!")
                sys.exit(1)


if __name__ == "__main__":
    main()
