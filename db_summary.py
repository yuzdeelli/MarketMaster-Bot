import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM prices")
print("Toplam Kayit:", c.fetchone()[0])
c.execute("SELECT item_lvl, COUNT(*) FROM prices GROUP BY item_lvl ORDER BY COUNT(*) DESC")
print("Level dagilimi:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]}")
c.execute("SELECT DISTINCT item_name, item_lvl FROM prices WHERE item_lvl = '+7' LIMIT 10")
print("+7 itemleri:")
for r in c.fetchall():
    print(f"  {r[0]} {r[1]}")
conn.close()
