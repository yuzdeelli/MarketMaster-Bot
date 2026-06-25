import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("SELECT server, timestamp FROM prices ORDER BY id DESC LIMIT 10")
for r in c.fetchall():
    print(f"{r[0]}: {r[1]}")
print()
c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM prices")
r = c.fetchone()
print(f"Min: {r[0]}  Max: {r[1]}")
conn.close()
