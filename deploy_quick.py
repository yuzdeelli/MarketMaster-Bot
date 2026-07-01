import requests
import os
import sys

TOKEN = "fd5c80513edc6ec7218745dc9d7a8787bcc11597"
USER = "marketmaster"
BASE_URL = f"https://www.pythonanywhere.com/api/v0/user/{USER}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    "webapp/database.py",
    "webapp/analytics.py",
    "webapp/portfolio.py",
    "webapp/app.py",
    "ui/bot_tab.py",
]

def upload(local_path, remote_path):
    url = f"{BASE_URL}/files/path{remote_path}"
    with open(local_path, "rb") as f:
        r = requests.post(url, headers={"Authorization": f"Token {TOKEN}"}, files={"content": f})
    if r.status_code in (200, 201):
        print(f"  OK  {remote_path}")
    else:
        print(f"  ERR {remote_path}: {r.status_code} {r.text[:100]}")

for f in FILES:
    local = os.path.join(LOCAL_ROOT, f)
    remote = f"/home/{USER}/{f}"
    upload(local, remote)

# Reload
url = f"https://www.pythonanywhere.com/api/v0/user/{USER}/webapps/{USER}.pythonanywhere.com/reload/"
r = requests.post(url, headers={"Authorization": f"Token {TOKEN}"})
print(f"\nReload: {r.status_code}")
