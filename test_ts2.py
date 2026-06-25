import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()

# Check timestamp formats
c.execute("SELECT timestamp, COUNT(*) FROM prices GROUP BY timestamp ORDER BY COUNT(*) DESC LIMIT 20")
for r in c.fetchall():
    print(f"  '{r[0]}' -> {r[1]}")

c.execute("SELECT COUNT(*) FROM prices WHERE timestamp LIKE '____-__-__ %'")
iso = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM prices WHERE timestamp LIKE '__.__.____'")
dot = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM prices")
total = c.fetchone()[0]
print(f"\nISO format: {iso}, DD.MM.YYYY format: {dot}, Total: {total}")
conn.close()
