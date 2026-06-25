import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("SELECT server, COUNT(*) as cnt FROM prices GROUP BY server ORDER BY cnt DESC")
for r in c.fetchall():
    print(f"{r[0]}: {r[1]}")
print(f"\nToplam sunucu: {c.execute('SELECT COUNT(DISTINCT server) FROM prices').fetchone()[0]}")
print(f"Toplam kayit: {c.execute('SELECT COUNT(*) FROM prices').fetchone()[0]}")
conn.close()
