import sqlite3
import threading
import re
from datetime import datetime
from core.usko_api import UskoApiClient, SERVER_MAP_REVERSE


# +0 YAZILABILECEK ITEM LISTESI (tam isim veya keyword)
# Ekleme yaparken sadece buraya bak, diger listeleri elleme
_ALLOW_ZERO = [
    # --- TAKI ---
    "ring", "yüzük", "kolye", "necklace", "earring", "küpe",
    "belt", "kemer", "amulet", "pendant",
    # --- KILIC ---
    "dark vane", "avedon", "heros valor",
    # --- STAF ---
    "scorching staff", "foverin", "elysium", "rons staff",
    # --- TOKAC / HAMMER ---
    "hammer",
    # --- KALKAN ---
    "dread shield",
    # --- YIYECEK / MATERYAL ---
    "glutinous rice cake", "talisman",
    # --- LEVELSIZ (hepsi +0 olur) ---
    "scroll", "kağıt", "kutu", "box", "chest", "supply",
    "gem", "taş", "jewel", "stone",
    "fragment", "piece", "shard", "breaker", "materyal", "material",
    "costume", "kostüm", "ruler", "legend",
    "recipe", "certificate", "coupon", "voucher", "key",
    "potion", "iksir", "water",
    # --- SUZAK ---
    "murky waters",
    "pet", "transformation", "transform",
    "flag", "embleme", "symbol",
]


def should_allow_zero(item_name):
    """Item +0 seviyesinde kaydedilebilir mi?"""
    name_lower = item_name.lower().strip()
    for kw in _ALLOW_ZERO:
        if kw in name_lower:
            return True
    return False


def should_skip_record(item_name, item_lvl):
    """+0 filtresi kaldirildi - tum kayitlar DB'ye yazilir."""
    return False


def is_reverse_level(lvl):
    """Level string'i reverse mi? (+1R, +2R, etc.)"""
    return bool(lvl) and lvl.strip().upper().endswith("R")


def parse_level(lvl_str):
    """Level string'ini (number, is_reverse) olarak parse et."""
    if not lvl_str:
        return 0, False
    s = lvl_str.strip()
    is_rev = s.upper().endswith("R")
    if is_rev:
        s = s[:-1]
    s = s.replace("+", "").strip()
    try:
        return int(s), is_rev
    except ValueError:
        return 0, False


class MarketEngine:
    def __init__(self, db_name="market_history.db", db_insert_callback=None, api_key=None, **kwargs):
        self.db_name = db_name
        self.db_insert_callback = db_insert_callback
        self.api_client = UskoApiClient(api_key=api_key)
        self.db_lock = threading.Lock()

    def set_api_key(self, api_key):
        self.api_client.set_api_key(api_key)

    def start(self):
        pass

    def scan_dual(self, srv_name, srv_id, item_name, lvls, stop_event=None):
        results = []
        server_code = self.api_client.resolve_server_code(srv_name)

        for lvl_str in lvls:
            if stop_event and stop_event.is_set():
                break
            plus_val, is_rev = parse_level(lvl_str)

            api_result, error = self.api_client.scan_item(
                server_display=srv_name,
                item_name=item_name,
                plus=plus_val if plus_val else None,
                item_type=-1,
                limit=100,
                rebirth=is_rev
            )
            if error:
                print(f"[{srv_name}] {item_name} {lvl_str} Hata: {error}")
                continue

            for item in api_result:
                ptype = "sell" if item["Pazar Tipi"] == "Sell" else "buy"
                item_server = item.get("Sunucu", srv_name)
                self.save_to_db({
                    "Sunucu": item_server,
                    "Pazar Tipi": ptype,
                    "İtem Adı": item_name,
                    "Artı": item["Artı"],
                    "Fiyat": item["Fiyat"],
                    "Zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                print(f"[{item_server}] {item_name} {item['Artı']} -> {item['Fiyat']:,.0f} Coins")
            results.extend(api_result)

        return results

    def scan_single_server(self, server_display, item_name, plus=None, stop_event=None, rebirth=False):
        results = []
        api_result, error = self.api_client.scan_item(
            server_display=server_display,
            item_name=item_name,
            plus=plus,
            item_type=-1,
            limit=100,
            rebirth=rebirth
        )
        if error:
            print(f"[{server_display}] {item_name} Hata: {error}")
            return results

        for item in api_result:
            ptype = "sell" if item["Pazar Tipi"] == "Sell" else "buy"
            item_server = item.get("Sunucu", server_display)
            self.save_to_db({
                "Sunucu": item_server,
                "Pazar Tipi": ptype,
                "İtem Adı": item_name,
                "Artı": item["Artı"],
                "Fiyat": item["Fiyat"],
                "Zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            print(f"[{item_server}] {item_name} {item['Artı']} -> {item['Fiyat']:,.0f} Coins")
        results.extend(api_result)
        return results

    def save_to_db(self, data):
        if self.db_insert_callback:
            try:
                self.db_insert_callback(data)
                return
            except Exception as e:
                print(f"Callback DB hatası: {e}")

        with self.db_lock:
            try:
                name = (data["İtem Adı"] or "").strip()
                level = (data["Artı"] or "").strip()
                if not level:
                    m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)(R?)\)\s*$", name)
                    if not m:
                        m = re.search(r"^(.*?)[\s]*\+([0-9]+)(R?)\s*$", name)
                    if m:
                        name = m.group(1).strip()
                        level = '+' + m.group(2) + m.group(3)
                name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()
                seller = str(data.get("UserID", "") or "").strip()
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

                # +0 FILTRESI (reverse degilse uygula)
                if not is_reverse_level(level) and should_skip_record(name, level):
                    return

                conn = sqlite3.connect(self.db_name, timeout=60)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=60000")
                conn.execute(
                    "INSERT INTO prices (server, type, item_name, item_lvl, price, seller, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (data["Sunucu"], data["Pazar Tipi"], name, level, data["Fiyat"], seller, now)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"DB Yazma Hatası: {e}")

    def stop(self):
        pass

    def check_api_status(self):
        return self.api_client.get_status()

    def activate_api_key(self):
        return self.api_client.activate()
