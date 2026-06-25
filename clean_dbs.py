import sqlite3, os

BASE = r"C:\Users\hort\Desktop\Market Master V - 1"
dbs = ["app_data.db", "web_market.db"]

for name in dbs:
    path = os.path.join(BASE, name)
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"Silindi: {name}")
        except Exception as e:
            print(f"{name} silinemedi: {e}")
            # WAL/SHM varsa onlari da sil
            for ext in ["-wal", "-shm"]:
                p = path + ext
                if os.path.exists(p):
                    os.remove(p)
                    print(f"  Silindi: {name}{ext}")
            os.remove(path)
            print(f"  Silindi (tekrar): {name}")
    else:
        print(f"Zaten yok: {name}")

print("\nDB'ler temizlendi.")
