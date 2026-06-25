import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()

items = ["silvery gem", "blue gem", "green gem", "black gem", "Superior Draki Supply Box", "Blue Treasure Chest"]

for item in items:
    print(f"\n{item}:")
    for ptype in ["buy", "sell"]:
        c.execute("SELECT server, price FROM prices WHERE item_name=? AND LOWER(type)=? ORDER BY server", (item, ptype))
        rows = c.fetchall()
        servers = {}
        for srv, price in rows:
            base = srv.split()[0]
            if base not in servers:
                servers[base] = []
            servers[base].append(price)
        for srv, prices in sorted(servers.items()):
            print(f"  {ptype:4s} {srv:10s}: {len(prices)} kayit, min={min(prices)}, max={max(prices)}")
conn.close()
