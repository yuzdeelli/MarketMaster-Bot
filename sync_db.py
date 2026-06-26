import requests
import os
import sys
import time
import hashlib
import sqlite3
import gzip
import shutil

PYTHONANYWHERE_USER = "marketmaster"
HOME_DIR = f"/home/{PYTHONANYWHERE_USER}"
PYTHONANYWHERE_TOKEN = "fd5c80513edc6ec7218745dc9d7a8787bcc11597"
DB_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")
DB_REMOTE_PATH = "app_data.db"
HASH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sync_hash")
UPLOAD_TIMEOUT = 300
MAX_RETRIES = 3


def get_token():
    if PYTHONANYWHERE_TOKEN:
        return PYTHONANYWHERE_TOKEN
    token = os.environ.get("PYTHONANYWHERE_TOKEN", "")
    if not token:
        token = input("PythonAnywhere API token: ").strip()
    return token


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def vacuum_db():
    print("DB VACUUM yapiliyor...")
    try:
        conn = sqlite3.connect(DB_LOCAL)
        conn.execute("VACUUM")
        conn.close()
        print("  VACUUM tamamlandi!")
    except Exception as e:
        print(f"  VACUUM hatasi (devam ediliyor): {e}")


def compress_db():
    db_gz = DB_LOCAL + ".gz"
    print("DB sikistiriliyor (gzip)...")
    with open(DB_LOCAL, "rb") as f_in:
        with gzip.open(db_gz, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    orig_mb = os.path.getsize(DB_LOCAL) / (1024 * 1024)
    comp_mb = os.path.getsize(db_gz) / (1024 * 1024)
    print(f"  {orig_mb:.1f} MB -> {comp_mb:.1f} MB ({(1 - comp_mb/orig_mb)*100:.0f}% kucultme)")
    return db_gz


def upload_file(token, local_path, remote_path, timeout=UPLOAD_TIMEOUT):
    full_path = f"{HOME_DIR}/{remote_path}"
    url = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}/files/path/{full_path}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(local_path, "rb") as f:
                resp = requests.post(url, headers={"Authorization": f"Token {token}"}, files={"content": f}, timeout=timeout)
            if resp.status_code in (200, 201):
                return resp.status_code, resp.text
            if attempt < MAX_RETRIES:
                print(f"    Deneme {attempt}/{MAX_RETRIES} basarisiz ({resp.status_code}), tekrar deneniyor...")
                time.sleep(5)
            else:
                return resp.status_code, resp.text
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                print(f"    Deneme {attempt}/{MAX_RETRIES} timeout, tekrar deneniyor...")
                time.sleep(5)
            else:
                return 0, "Timeout"
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"    Deneme {attempt}/{MAX_RETRIES} hata: {e}, tekrar deneniyor...")
                time.sleep(5)
            else:
                return 0, str(e)
    return 0, "Max retries"


def upload_db(token):
    if not os.path.exists(DB_LOCAL):
        print(f"DB bulunamadi: {DB_LOCAL}")
        return False

    current_hash = file_hash(DB_LOCAL)
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE) as f:
            last_hash = f.read().strip()
        if last_hash == current_hash:
            print("DB degisiklik yok, upload atlaniyor.")
            return True

    vacuum_db()
    db_gz = compress_db()

    size_mb = os.path.getsize(db_gz) / (1024 * 1024)
    print(f"DB yukleniyor ({size_mb:.1f} MB compressed)...")

    code, text = upload_file(token, db_gz, DB_REMOTE_PATH + ".gz")
    os.remove(db_gz)

    if code in (200, 201):
        print("  DB yuklendi!")
        with open(HASH_FILE, "w") as f:
            f.write(current_hash)
    else:
        print(f"  DB hatasi ({code}): {text[:200]}")
        return False

    auth_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_users.db")
    if os.path.exists(auth_db):
        code2, text2 = upload_file(token, auth_db, "web_users.db")
        if code2 in (200, 201):
            print("  web_users.db yuklendi!")
        else:
            print(f"  web_users.db hatasi ({code2}): {text2[:100]}")

    return True


def reload_web(token):
    url = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}/webapps/{PYTHONANYWHERE_USER}.pythonanywhere.com/reload/"
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers={"Authorization": f"Token {token}"}, timeout=60)
            if resp.status_code == 200:
                print("Web app yeniden baslatildi!")
                return True
        except Exception:
            pass
        if attempt < MAX_RETRIES - 1:
            time.sleep(5)
    print("Reload basarisiz (timeout)")
    return False


def main():
    token = get_token()
    if not token:
        print("Token gerekli!")
        print("1. https://www.pythonanywhere.com/account/ adresine git")
        print("2. 'API token' bolumunden token olustur")
        print("3. Bu scripti tekrar calistir")
        sys.exit(1)

    print("DB yukleniyor...")
    if upload_db(token):
        print("\nWeb app yeniden baslatiliyor...")
        reload_web(token)
        print("\nSenkron tamamlandi!")
    else:
        print("\nSenkron basarisiz!")
        sys.exit(1)


if __name__ == "__main__":
    main()
