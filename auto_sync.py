import time
import os
import sys

SYNC_INTERVAL = 900
PYTHONANYWHERE_USER = "marketmaster"

def run_sync():
    os.system(f"{sys.executable} sync_db.py")

def main():
    print(f"Otomatik DB senkron baslatildi (her {SYNC_INTERVAL} sn)")
    print("Durdurmak icin Ctrl+C")
    print("-" * 40)
    while True:
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] Senkron basliyor...")
            run_sync()
            print(f"[{time.strftime('%H:%M:%S')}] Siradaki senkron: {SYNC_INTERVAL} sn sonra")
            time.sleep(SYNC_INTERVAL)
        except KeyboardInterrupt:
            print("\nDurduruldu.")
            break

if __name__ == "__main__":
    main()
