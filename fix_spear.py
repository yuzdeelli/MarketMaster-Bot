import sqlite3

conn = sqlite3.connect(r'C:\Users\hort\Desktop\Market Master V - 1\web_market.db')

cur = conn.execute("UPDATE prices SET item_lvl='+1' WHERE item_name='Spear of Murky Waters' AND item_lvl='+0'")
print(f"Spear of Murky Waters: {cur.rowcount} kayit +0 -> +1")

conn.commit()

# Son kontrol
rows = conn.execute("""
    SELECT item_name, item_lvl, COUNT(*) as cnt
    FROM prices WHERE item_name LIKE '%Spear%' OR item_name LIKE '%Murky%'
    GROUP BY item_name, item_lvl ORDER BY item_name, item_lvl
""").fetchall()
print("\nGuncel durum:")
for r in rows:
    print(f"  {r[0]:<30} {r[1]:>5} | {r[2]:>5} kayit")

conn.close()
