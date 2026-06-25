import sys, time
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

client = UskoApiClient(api_key=ConfigManager.load_api_key())

def on_progress(msg, cnt):
    parts = msg.split("|")
    if parts[0] == "SERVER_START":
        print(f"\n[{parts[1]}] ({parts[2]}/{parts[3]})")
    elif parts[0] == "PAGE":
        print(f"  [{parts[2]}] Sayfa {parts[3]} -> {parts[4]} item")
    elif parts[0] == "SERVER_DONE":
        print(f"  TAMAMLANDI - {parts[2]} item")

start = time.time()

results = client.fetch_all_servers(
    server_names=["ZERO 3"],
    progress_callback=on_progress,
    stop_event=None,
    levels=list(range(11)),
    reverse_levels=list(range(1, 22))
)

duration = time.time() - start
print(f"\n{'='*40}")
print(f"Sure: {int(duration//60)}dk {int(duration%60)}sn")
print(f"Toplam: {len(results)} kayit")

levels = {}
for r in results:
    lvl = r.get("Arti", "?")
    levels[lvl] = levels.get(lvl, 0) + 1

print("\nLevel dagilimi:")
for k, v in sorted(levels.items()):
    print(f"  {k}: {v}")
