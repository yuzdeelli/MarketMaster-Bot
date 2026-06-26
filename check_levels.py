import sqlite3
db = sqlite3.connect("app_data.db")
rows = db.execute("SELECT DISTINCT item_name, item_lvl, server, price, type FROM prices WHERE LOWER(item_name) LIKE '%mirage%dagger%' AND item_lvl IN ('+11', '+21R', '+11R') ORDER BY item_name, item_lvl, server, type").fetchall()
for r in rows:
    print(f"  {r[0]:>20} [{r[1]:>5}] {r[2]:>10} {r[3]:>15} {r[4]}")
db.close()
