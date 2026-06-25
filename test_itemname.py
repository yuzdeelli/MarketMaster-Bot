import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()
c.execute("SELECT DISTINCT item_name FROM prices WHERE item_name LIKE '%Chitin%' LIMIT 10")
for r in c.fetchall():
    print(repr(r[0]))
print()
c.execute("SELECT DISTINCT item_name FROM prices WHERE item_name LIKE '%Helmet%' LIMIT 20")
for r in c.fetchall():
    print(repr(r[0]))
conn.close()
