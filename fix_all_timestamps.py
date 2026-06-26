import sqlite3, re
from datetime import datetime

db = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"
conn = sqlite3.connect(db)

# 1. Tum timestamp'leri duzelt: dd.mm.yyyy -> yyyy-mm-dd HH:MM:SS
rows = conn.execute("SELECT id, timestamp, last_seen FROM prices").fetchall()
fixed = 0
for row_id, ts, ls in rows:
    new_ts = ts
    new_ls = ls

    # dd.mm.yyyy format -> yyyy-mm-dd 12:00:00
    m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', str(ts or ''))
    if m:
        new_ts = f"{m.group(3)}-{m.group(2)}-{m.group(1)} 12:00:00"

    m2 = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', str(ls or ''))
    if m2:
        new_ls = f"{m2.group(3)}-{m2.group(2)}-{m2.group(1)} 12:00:00"

    # yyyy-mm-dd (saat yok) -> yyyy-mm-dd 12:00:00
    m3 = re.match(r'^(\d{4}-\d{2}-\d{2})$', str(new_ts or ''))
    if m3:
        new_ts = f"{m3.group(1)} 12:00:00"

    m4 = re.match(r'^(\d{4}-\d{2}-\d{2})$', str(new_ls or ''))
    if m4:
        new_ls = f"{m4.group(1)} 12:00:00"

    if new_ts != ts or new_ls != ls:
        conn.execute("UPDATE prices SET timestamp=?, last_seen=? WHERE id=?", (new_ts, new_ls, row_id))
        fixed += 1

conn.commit()
print(f"Duzeltilen: {fixed} satir")

# 2. Sonuc kontrol
rows2 = conn.execute(
    "SELECT id, timestamp, last_seen FROM prices ORDER BY id DESC LIMIT 5"
).fetchall()
print("\nSon 5:")
for r in rows2:
    print(f"  id={r[0]} ts='{r[1]}' ls='{r[2]}'")

# 3. Format dagilimi
fmts = conn.execute(
    "SELECT timestamp, COUNT(*) FROM prices GROUP BY SUBSTR(timestamp, 1, 10) ORDER BY COUNT(*) DESC LIMIT 5"
).fetchall()
print("\nEn cok kullanilan formatlar:")
for r in fmts:
    print(f"  '{r[0][:10]}' => {r[1]}")

conn.close()
