import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM prices WHERE seller LIKE 'sim_%'")
print("Simulasyon:", c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM prices WHERE seller NOT LIKE 'sim_%'")
print("Gercek API:", c.fetchone()[0])

c.execute("DELETE FROM prices WHERE seller LIKE 'sim_%'")
conn.commit()

c.execute("SELECT COUNT(*) FROM prices")
print("Kalan:", c.fetchone()[0])

conn.close()
