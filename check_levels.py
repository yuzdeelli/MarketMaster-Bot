import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()

print("=== Tum level dagilimi ===")
c.execute("SELECT item_lvl, COUNT(*) FROM prices GROUP BY item_lvl ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]}")

print("\n=== +0 disinda itemler ===")
c.execute("SELECT DISTINCT item_name, item_lvl, COUNT(*) as cnt FROM prices WHERE item_lvl != '+0' GROUP BY item_name, item_lvl ORDER BY cnt DESC")
for r in c.fetchall():
    print(f"  {r[0]} | {r[1]} | {r[2]} kayit")

print("\n=== Top 20 en pahali (+0 disinda) ===")
c.execute("""
    SELECT item_name, item_lvl, price, type, server FROM prices 
    WHERE item_lvl != '+0' 
    ORDER BY price DESC LIMIT 20
""")
for r in c.fetchall():
    print(f"  {r[0]} {r[1]} | {r[3]} | {r[2]:,.0f} | {r[4]}")

conn.close()
