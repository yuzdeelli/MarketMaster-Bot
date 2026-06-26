import sqlite3, os, re

db = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"
print("Boyut:", os.path.getsize(db))

conn = sqlite3.connect(db)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tablolar:", tables)

for t in tables:
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', t):
        print(f"  {t}: SKIP (invalid table name)")
        continue
    c.execute(f"SELECT COUNT(*) FROM [{t}]")
    cnt = c.fetchone()[0]
    print(f"  {t}: {cnt} kayit")

if "prices" in tables:
    c.execute("SELECT DISTINCT item_name FROM prices LIMIT 10")
    print("Ornek itemlar:", [r[0] for r in c.fetchall()])

conn.close()
