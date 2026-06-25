import sqlite3
import sys
sys.path.insert(0, r'C:\Users\hort\Desktop\Market Master V - 1')
from core.engine import should_allow_zero

conn = sqlite3.connect(r'C:\Users\hort\Desktop\Market Master V - 1\web_market.db')

# Spear of Murky Waters
rows = conn.execute("""
    SELECT item_name, item_lvl, COUNT(*) as cnt
    FROM prices WHERE item_name LIKE '%Spear%' OR item_name LIKE '%Murky%'
    GROUP BY item_name, item_lvl ORDER BY item_name, item_lvl
""").fetchall()

print("Spear/Murky verileri:")
for r in rows:
    allow = should_allow_zero(r[0])
    print(f"  {r[0]:<30} {r[1]:>5} | {r[2]:>5} kayit | +0 izin: {'EVET' if allow else 'HAYIR'}")

# +0 olan tum silah/zırh itemlarini bul
print("\n=== +0 OLMAMASI GEREKENLER ===")
rows2 = conn.execute("""
    SELECT DISTINCT item_name FROM prices WHERE item_lvl = '+0'
""").fetchall()
for (name,) in rows2:
    if not should_allow_zero(name):
        cnt = conn.execute("SELECT COUNT(*) FROM prices WHERE item_name=? AND item_lvl='+0'", (name,)).fetchone()[0]
        print(f"  {name:<40} {cnt:>5} kayit")

conn.close()
