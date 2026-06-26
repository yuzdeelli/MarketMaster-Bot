import requests
import os
import sys
import json

PYTHONANYWHERE_USER = "marketmaster"
HOME_DIR = f"/home/{PYTHONANYWHERE_USER}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES_TO_UPLOAD = [
    "webapp/app.py",
    "webapp/database.py",
    "webapp/security.py",
    "webapp/portfolio.py",
    "core/config.py",
    "ui/settings_tab.py",
    "ui/bot_tab.py",
    "core/analyzer.py",
    "webapp/templates/analiz.html",
    "webapp/templates/portfoy.html",
    "webapp/templates/dashboard.html",
    "webapp/templates/item.html",
    "webapp/templates/item_index.html",
    "webapp/templates/live.html",
    "webapp/templates/admin.html",
]

def get_token():
    token = os.environ.get("PYTHONANYWHERE_TOKEN", "")
    if not token:
        try:
            sys.path.insert(0, LOCAL_ROOT)
            from core.config import ConfigManager
            token = ConfigManager.load_sync_token()
        except Exception:
            pass
    if not token:
        config_path = os.path.join(LOCAL_ROOT, "analyzer_config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
            token = cfg.get("pythonanywhere_token", "")
    if not token:
        token = input("PythonAnywhere API token: ").strip()
    return token

def upload_file(token, local_path, remote_path):
    full_path = f"{HOME_DIR}/{remote_path}"
    url = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}/files/path/{full_path}"
    with open(local_path, "rb") as f:
        resp = requests.post(url, headers={"Authorization": f"Token {token}"}, files={"content": f}, timeout=120)
    return resp.status_code, resp.text

def upload_db(token):
    db_path = os.path.join(LOCAL_ROOT, "app_data.db")
    if not os.path.exists(db_path):
        print(f"DB bulunamadi: {db_path}")
        return False
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"DB yukleniyor ({size_mb:.1f} MB)...")
    code, text = upload_file(token, db_path, "app_data.db")
    if code == 200:
        print("  DB yuklendi!")
        return True
    else:
        print(f"  DB hatasi ({code}): {text[:100]}")
        return False

def upload_files(token):
    ok = 0
    fail = 0
    for rel_path in FILES_TO_UPLOAD:
        local = os.path.join(LOCAL_ROOT, rel_path)
        if not os.path.exists(local):
            print(f"  [SKIP] {rel_path} - dosya yok")
            continue
        code, text = upload_file(token, local, rel_path)
        if code in (200, 201):
            print(f"  [OK] {rel_path}")
            ok += 1
        else:
            print(f"  [FAIL] {rel_path} ({code}): {text[:80]}")
            fail += 1
    return ok, fail

def reload_web(token):
    url = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}/webapps/{PYTHONANYWHERE_USER}.pythonanywhere.com/reload/"
    resp = requests.post(url, headers={"Authorization": f"Token {token}"}, timeout=30)
    if resp.status_code == 200:
        print("Web app yeniden baslatildi!")
        return True
    else:
        print(f"Reload hatasi ({resp.status_code}): {resp.text}")
        return False

def main():
    token = get_token()
    if not token:
        print("Token gerekli!")
        sys.exit(1)

    print("=" * 40)
    print("PythonAnywhere Deploy")
    print("=" * 40)

    print("\n1. DB yukleniyor...")
    upload_db(token)

    print(f"\n2. {len(FILES_TO_UPLOAD)} dosya yukleniyor...")
    ok, fail = upload_files(token)
    print(f"\n   Sonuc: {ok} basarili, {fail} basarisiz")

    print("\n3. Web app yeniden baslatiliyor...")
    reload_web(token)

    print("\n" + "=" * 40)
    print("Deploy tamamlandi!")
    print("=" * 40)

if __name__ == "__main__":
    main()
