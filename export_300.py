import sqlite3

db = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
db.row_factory = sqlite3.Row

rows = db.execute("""
    SELECT id, item_name, item_lvl, price, type, server, seller, last_seen, timestamp
    FROM prices
    ORDER BY id DESC
    LIMIT 300
""").fetchall()
db.close()

lines = []
lines.append(f"{'ID':>8} | {'Item':<35} | {'Lvl':>5} | {'Fiyat':>15} | {'Tip':<5} | {'Server':<15} | {'Satici':<20} | {'Son Gorus':<20} | {'Timestamp':<20}")
lines.append("-" * 180)

for r in rows:
    lines.append(
        f"{r['id']:>8} | {r['item_name']:<35} | {r['item_lvl']:>5} | {r['price']:>15,} | {r['type']:<5} | {r['server']:<15} | {(r['seller'] or ''):<20} | {(r['last_seen'] or ''):<20} | {(r['timestamp'] or ''):<20}"
    )

output = "\n".join(lines)

path = r"C:\Users\hort\Desktop\Market Master V - 1\son_300_kayit.txt"
with open(path, "w", encoding="utf-8") as f:
    f.write(output)

print(f"{len(rows)} kayit {path} dosyasina yazildi")
