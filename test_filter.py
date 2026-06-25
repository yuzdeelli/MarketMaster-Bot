import sqlite3
import os
db_path = os.path.join(r"C:\Users\hort\Desktop\Market Master V - 1", "app_data.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

servers = ["AGARTHA", "PANDORA", "ZERO", "DESTAN", "FELIS"]
item = "Chitin Helmet"
for srv in servers:
    c.execute("SELECT COUNT(*) FROM prices WHERE item_name=? AND server LIKE ?", (item, f"%{srv}%"))
    cnt = c.fetchone()[0]
    c.execute("SELECT type, price, server, timestamp FROM prices WHERE item_name=? AND server LIKE ? ORDER BY timestamp DESC LIMIT 3", (item, f"%{srv}%"))
    rows = c.fetchall()
    print(f"\n{srv}: {cnt} kayit")
    for r in rows:
        print(f"  {r[0]} {r[1]} @ {r[2]} @ {r[3]}")

conn.close()
