import sqlite3

db = sqlite3.connect("app_data.db")

dupes = db.execute(
    "SELECT item_name, server, price, type, GROUP_CONCAT(DISTINCT item_lvl) as levels, COUNT(*) as cnt "
    "FROM prices "
    "GROUP BY item_name, server, price, type "
    "HAVING COUNT(DISTINCT item_lvl) > 1 "
    "ORDER BY cnt DESC "
    "LIMIT 30"
).fetchall()

print(f"Toplanan {len(dupes)} farkli karisik kayit bulundu:\n")
for r in dupes:
    print(f"  {r[0]:>25} | {r[1]:>10} | {r[2]:>15} | {r[3]:>4} | levels: {r[4]} ({r[5]}x)")

db.close()
