import sqlite3, os, time

base = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base, "app_data.db")

print("Veritabani kontrol ediliyor...")
while True:
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    last = conn.execute("SELECT MAX(timestamp) FROM prices").fetchone()[0]
    unique = conn.execute("SELECT COUNT(DISTINCT item_name || item_lvl) FROM prices").fetchone()[0]
    conn.close()
    
    print(f"  Toplam: {count} | Item: {unique} | Son: {last}")
    
    time.sleep(5)
