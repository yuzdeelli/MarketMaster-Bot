import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("UPDATE prices SET server = 'OREADS 3' WHERE server = 'ORESTES 3'")
print(f"Guncellenen: {c.rowcount} satir")
conn.commit()

c.execute("SELECT server, COUNT(*) FROM prices GROUP BY server ORDER BY server")
for r in c.fetchall():
    print(f"{r[0]}: {r[1]}")
conn.close()
