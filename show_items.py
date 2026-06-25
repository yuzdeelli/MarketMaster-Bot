import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("SELECT DISTINCT item_name, item_lvl FROM prices WHERE item_lvl != '+0' ORDER BY item_lvl, item_name")
items = c.fetchall()
print(f"+0 disinda {len(items)} item:")
for r in items:
    print(f"  {r[0]} {r[1]}")
conn.close()
