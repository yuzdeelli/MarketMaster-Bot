import sqlite3

db = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"
conn = sqlite3.connect(db, timeout=10)

# WAL checkpoint
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print("Checkpoint tamamlandi")

# Simdi sayi
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM prices")
print(f"Toplam kayit: {c.fetchone()[0]}")

c.execute("SELECT item_name, item_lvl, COUNT(*) as cnt FROM prices GROUP BY item_name, item_lvl ORDER BY cnt DESC LIMIT 15")
print("\nEn cok kayitli itemlar:")
for r in c.fetchall():
    print(f"  {r[0]} {r[1]}: {r[2]}")

c.execute("SELECT DISTINCT server FROM prices")
print(f"\nSunucular: {[r[0] for r in c.fetchall()]}")

c.execute("SELECT COUNT(DISTINCT item_name) FROM prices")
print(f"Farkli item: {c.fetchone()[0]}")

conn.close()
