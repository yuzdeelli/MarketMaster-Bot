import sys, os, time, json, sqlite3

BASE = r"C:\Users\hort\Desktop\Market Master V - 1"
sys.path.insert(0, BASE)
os.chdir(BASE)

from core.config import ConfigManager
from core.usko_api import UskoApiClient
from core.database import initialize_database, DatabaseManager
from core.engine import should_skip_record, is_reverse_level
import re

DB_PATH = os.path.join(BASE, "app_data.db")
initialize_database(DB_PATH)
db = DatabaseManager(DB_PATH)

api_key = ConfigManager.load_api_key()
client = UskoApiClient(api_key=api_key)

ALL_SERVERS = [
    "ZERO 3", "ZERO 4", "ZERO 5", "ZERO 8",
    "PANDORA 3", "PANDORA 4",
    "AGARTHA 3", "AGARTHA 4",
    "FELIS 2",
    "DESTAN 3", "DESTAN 2",
    "MINARK 2",
    "DRYADS 2",
    "OREADS 2", "OREADS 3",
]

ALL_LEVELS = list(range(11))  # +0'dan +10'a
ALL_REVERSE = list(range(1, 22))  # +1R'den +21R'ye

print(f"DB: {DB_PATH}")
print(f"Sunucular: {len(ALL_SERVERS)}")
print(f"Normal: +0'dan +10'a | Reverse: +1R'den +21R'ye")
print("=" * 50)

total_saved = 0

def on_progress(msg, cnt):
    parts = msg.split("|")
    if parts[0] == "SERVER_START":
        print(f"\n[{parts[1]}] Basliyor... ({parts[2]}/{parts[3]})")
    elif parts[0] == "PAGE":
        print(f"  [{parts[2]}] Sayfa {parts[3]} -> {parts[4]} item")
    elif parts[0] == "SERVER_DONE":
        print(f"[{parts[1]}] TAMAMLANDI - {parts[2]} item")

start = time.time()

results = client.fetch_all_servers(
    server_names=ALL_SERVERS,
    progress_callback=on_progress,
    stop_event=None,
    levels=ALL_LEVELS,
    reverse_levels=ALL_REVERSE
)

duration = time.time() - start
print(f"\n{'=' * 50}")
print(f"Toplam: {len(results)} item cekildi ({int(duration//60)}dk {int(duration%60)}sn)")
print("DB'ye kaydediliyor...")

saved = 0
skipped = 0
filtered = 0
for r in results:
    name = (r.get("İtem Adı", "") or "").strip()
    if not name:
        continue
    lvl = (r.get("Artı", "+0") or "+0").strip()
    if not lvl:
        lvl = "+0"
    ptype = "buy" if (r.get("Pazar Tipi", "") or "").lower() == "buy" else "sell"
    price = r.get("Fiyat", 0)
    server = r.get("Sunucu", "")
    ts = r.get("Zaman", "")
    seller = str(r.get("UserID", "") or "").strip()

    m = re.search(r"^(.*?)[\s]*\+([0-9]+)(R?)\s*$", name)
    if m:
        name = m.group(1).strip()
        if not is_reverse_level(lvl):
            lvl = "+" + m.group(2) + m.group(3)
    name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()

    if not is_reverse_level(lvl) and should_skip_record(name, lvl):
        filtered += 1
        continue

    db.insert_price({
        "Sunucu": server,
        "Pazar Tipi": ptype,
        "İtem Adı": name,
        "Artı": lvl,
        "Fiyat": price,
        "Zaman": ts,
        "UserID": seller,
    })
    saved += 1

print(f"\nKaydedilen: {saved}")
print(f"+0 Filtrelenen: {filtered}")
print(f"Toplam sure: {int(duration//60)}dk {int(duration%60)}sn")

# Kontrol
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM prices")
print(f"\nDB'de toplam: {c.fetchone()[0]} kayit")
c.execute("SELECT item_name, item_lvl, COUNT(*) FROM prices GROUP BY item_name, item_lvl ORDER BY COUNT(*) DESC LIMIT 10")
print("En cok kayitli:")
for r in c.fetchall():
    print(f"  {r[0]} {r[1]}: {r[2]}")
conn.close()
