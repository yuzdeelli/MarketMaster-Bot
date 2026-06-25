import sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

client = UskoApiClient(api_key=ConfigManager.load_api_key())

print("=== Normal seviyeler ===")
for lvl in [0, 1, 2, 3]:
    result = client.get_items(server="zero3", plus=lvl, limit=2)
    items = result.get("data", [])
    print(f"+{lvl}: {len(items)} kayit")
    for item in items[:1]:
        print(f"  {item.get('ItemName')} -> {item.get('ItemPrice'):,}")

print("\n=== Reverse seviyeler ===")
for lvl in [1, 2, 3]:
    result = client.get_items(server="zero3", plus=lvl, rebirth=1, limit=2)
    items = result.get("data", [])
    print(f"+{lvl}R: {len(items)} kayit")
    for item in items[:1]:
        print(f"  {item.get('ItemName')} -> {item.get('ItemPrice'):,}")
