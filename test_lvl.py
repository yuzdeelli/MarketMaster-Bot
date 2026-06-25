import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("SELECT DISTINCT item_lvl FROM prices WHERE item_name='Chitin Helmet' ORDER BY item_lvl")
print("Chitin Helmet levels:")
for r in c.fetchall():
    print(f"  '{r[0]}'")

c.execute("SELECT item_lvl, COUNT(*) FROM prices WHERE item_name='Chitin Helmet' GROUP BY item_lvl")
print("\nChitin Helmet level counts:")
for r in c.fetchall():
    print(f"  '{r[0]}' -> {r[1]}")
conn.close()
