import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()

gems = ["Silvery Gem", "Blue Gem", "Green Gem", "Black Gem", "Gem"]
for gem in gems:
    c.execute("SELECT item_name, item_lvl, server, COUNT(*) FROM prices WHERE item_name LIKE ? GROUP BY item_name, item_lvl, server", (f"%{gem}%",))
    rows = c.fetchall()
    if rows:
        print(f"\n{gem}: {len(rows)} kayit")
        for r in rows[:5]:
            print(f"  {r[0]} {r[1]} @ {r[2]}: {r[3]}")
    else:
        print(f"\n{gem}: YOK")

conn.close()
