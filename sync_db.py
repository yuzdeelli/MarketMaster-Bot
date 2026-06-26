import requests
import os
import sys
import time

PYTHONANYWHERE_USER = "marketmaster"
HOME_DIR = f"/home/{PYTHONANYWHERE_USER}"
PYTHONANYWHERE_TOKEN = ""
DB_LOCAL = os.path.join(os.path.dirname(__file__), "app_data.db")
DB_REMOTE_PATH = "app_data.db"

def get_token():
    if PYTHONANYWHERE_TOKEN:
        return PYTHONANYWHERE_TOKEN
    token = os.environ.get("PYTHONANYWHERE_TOKEN", "")
    if not token:
        token = input("PythonAnywhere API token: ").strip()
    return token

def upload_db(token):
    if not os.path.exists(DB_LOCAL):
        print(f"DB bulunamadi: {DB_LOCAL}")
        return False

    size_mb = os.path.getsize(DB_LOCAL) / (1024 * 1024)
    print(f"DB boyutu: {size_mb:.1f} MB")

    url = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}/files/path/{HOME_DIR}/{DB_REMOTE_PATH}"
    with open(DB_LOCAL, "rb") as f:
        resp = requests.post(url, headers={"Authorization": f"Token {token}"}, files={"content": f}, timeout=120)

    if resp.status_code in (200, 201):
        print("Yukleme basarili!")
        return True
    elif resp.status_code == 403:
        print("Token yetkisi yok veya token yanlis")
        return False
    else:
        print(f"Hata ({resp.status_code}): {resp.text}")
        return False

def reload_web(token):
    url = f"https://www.pythonanywhere.com/api/v0/user/{PYTHONANYWHERE_USER}/webapps/{PYTHONANYWHERE_USER}.pythonanywhere.com/reload/"
    resp = requests.post(url, headers={"Authorization": f"Token {token}"})
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
        print("Senkron basarisiz!")
        sys.exit(1)

if __name__ == "__main__":
    main()
