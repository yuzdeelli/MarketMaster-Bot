import sqlite3

db = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"
conn = sqlite3.connect(db)
c = conn.cursor()

c.execute("PRAGMA table_info(prices)")
print("prices tablosu kolonlari:")
for r in c.fetchall():
    print(f"  {r}")

c.execute("SELECT COUNT(*) FROM prices")
print(f"\nToplam kayit: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM prices WHERE timestamp > datetime('now', '-1 hour')")
print("Son 1 saatteki kayit:", c.fetchone()[0])

# Check if there's data with older timestamps
c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM prices")
print("Timestamp araligi:", c.fetchone())

conn.close()
