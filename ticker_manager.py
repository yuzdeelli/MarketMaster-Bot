#!/usr/bin/env python3
"""
ticker_manager.py — Dashboard ticker ve buy-fiyat filtresi yonetici scripti.

Kullanim:
  python ticker_manager.py list                          — Ticker item'lerini listele
  python ticker_manager.py add "Item Name" 1500000       — Ticker'a item ekle
  python ticker_manager.py remove "Item Name"            — Ticker'dan item sil
  python ticker_manager.py clear                         — Ticker'daki tum itemleri sil
  python ticker_manager.py on                            — Ticker'i ac
  python ticker_manager.py off                           — Ticker'i kapat
  python ticker_manager.py toggle                        — Ticker'i ac/kapat
  python ticker_manager.py hide-list                     — Buy fiyat gizleme listesini goster
  python ticker_manager.py hide-add "Item Name"          — Buy fiyatini gizle
  python ticker_manager.py hide-remove "Item Name"       — Buy gizlemeden kaldir
"""
import sys
import os
import json
import requests

BASE_URL = os.environ.get("TICKER_API_URL", "https://marketmaster.pythonanywhere.com")
API_TOKEN = os.environ.get("TICKER_API_TOKEN", "")

_script_dir = os.path.dirname(os.path.abspath(__file__))
if not API_TOKEN:
    _sec_path = os.path.join(_script_dir, "security.json")
    if os.path.exists(_sec_path):
        try:
            with open(_sec_path) as f:
                sec = json.load(f)
            token_raw = sec.get("api_token", "")
            if token_raw and sec.get("api_token_encrypted"):
                sys.path.insert(0, _script_dir)
                from core.config import CryptoManager
                API_TOKEN = CryptoManager.decrypt(token_raw)
            elif token_raw:
                API_TOKEN = token_raw
        except Exception:
            pass

HEADERS = {"X-API-Token": API_TOKEN, "Content-Type": "application/json"}


def api_get():
    r = requests.get(f"{BASE_URL}/api/ticker", timeout=10)
    return r.json()


def api_post(action, **kwargs):
    data = {"action": action, **kwargs}
    r = requests.post(f"{BASE_URL}/api/ticker", headers=HEADERS, json=data, timeout=10)
    return r.json()


def cmd_list():
    cfg = api_get()
    print(f"Durum: {'ACIK' if cfg.get('enabled') else 'KAPALI'}")
    items = cfg.get("items", [])
    if not items:
        print("Ticker'da item yok.")
    else:
        print(f"\nTicker itemlari ({len(items)}):")
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item['name']} — {item['price']:,}")


def cmd_add(name, price):
    result = api_post("add_item", name=name, price=int(price))
    if result.get("ok"):
        print(f"Eklendi: {name} — {int(price):,}")
    else:
        print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")


def cmd_remove(name):
    result = api_post("remove_item", name=name)
    if result.get("ok"):
        print(f"Silindi: {name}")
    else:
        print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")


def cmd_clear():
    result = api_post("set_items", items=[])
    if result.get("ok"):
        print("Ticker temizlendi.")
    else:
        print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")


def cmd_on():
    result = api_post("set_enabled", enabled=True)
    print(f"Ticker: {'ACIK' if result.get('enabled') else 'KAPALI'}")


def cmd_off():
    result = api_post("set_enabled", enabled=False)
    print(f"Ticker: {'ACIK' if result.get('enabled') else 'KAPALI'}")


def cmd_toggle():
    result = api_post("toggle")
    print(f"Ticker: {'ACIK' if result.get('enabled') else 'KAPALI'}")


def cmd_hide_list():
    cfg = api_get()
    hide = cfg.get("hide_buy_for", [])
    if not hide:
        print("Gizli item yok.")
    else:
        print(f"\nBuy fiyat gizlenen itemler ({len(hide)}):")
        for i, name in enumerate(hide, 1):
            print(f"  {i}. {name}")


def cmd_hide_add(name):
    result = api_post("hide_add", name=name)
    if result.get("ok"):
        print(f"Gizlendi: {name}")
    else:
        print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")


def cmd_hide_remove(name):
    result = api_post("hide_remove", name=name)
    if result.get("ok"):
        print(f"Gizleme kaldirildi: {name}")
    else:
        print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "list":
        cmd_list()
    elif cmd == "add" and len(sys.argv) >= 4:
        cmd_add(sys.argv[2], sys.argv[3])
    elif cmd == "remove" and len(sys.argv) >= 3:
        cmd_remove(sys.argv[2])
    elif cmd == "clear":
        cmd_clear()
    elif cmd == "on":
        cmd_on()
    elif cmd == "off":
        cmd_off()
    elif cmd == "toggle":
        cmd_toggle()
    elif cmd == "hide-list":
        cmd_hide_list()
    elif cmd == "hide-add" and len(sys.argv) >= 3:
        cmd_hide_add(sys.argv[2])
    elif cmd == "hide-remove" and len(sys.argv) >= 3:
        cmd_hide_remove(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
