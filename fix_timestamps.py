import sqlite3
import re
from datetime import datetime

db_path = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, timestamp FROM prices")
rows = c.fetchall()
updated = 0
for row_id, ts in rows:
    if not ts:
        continue
    if re.match(r'^\d{4}-\d{2}-\d{2}', ts):
        continue
    m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})(.*)', ts)
    if m:
        new_ts = f"{m.group(3)}-{m.group(2)}-{m.group(1)}{m.group(4)}"
        c.execute("UPDATE prices SET timestamp = ? WHERE id = ?", (new_ts, row_id))
        updated += 1

conn.commit()
print(f"Guncellenen: {updated} satir")

c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM prices")
r = c.fetchone()
print(f"Min: {r[0]}  Max: {r[1]}")

c.execute("SELECT timestamp, COUNT(*) FROM prices GROUP BY timestamp ORDER BY COUNT(*) DESC LIMIT 5")
for r in c.fetchall():
    print(f"  '{r[0]}' -> {r[1]}")

conn.close()
