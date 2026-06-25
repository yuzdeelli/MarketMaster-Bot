import sqlite3, os

base = r"C:\Users\hort\Desktop\Market Master V - 1"
for db_name in ["app_data.db", "web_market.db", "webapp\market.db", "market_history.db"]:
    path = os.path.join(base, db_name)
    if os.path.exists(path):
        sz = os.path.getsize(path)
        conn = sqlite3.connect(path)
        c = conn.cursor()
        try:
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            if "prices" in tables:
                c.execute("SELECT COUNT(*) FROM prices")
                cnt = c.fetchone()[0]
                print(f"{db_name}: {sz} byte, {cnt} kayit")
            else:
                print(f"{db_name}: {sz} byte, prices tablosu yok. Tablolar: {tables}")
        except Exception as e:
            print(f"{db_name}: {sz} byte, HATA: {e}")
        conn.close()
    else:
        print(f"{db_name}: YOK")
