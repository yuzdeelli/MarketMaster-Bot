import sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

client = UskoApiClient(api_key=ConfigManager.load_api_key())

for lvl in [0, 1, 2, 3]:
    result = client.get_items(server="zero3", plus=lvl, limit=3)
    items = result.get("data", [])
    print(f"+{lvl}: {len(items)} kayit")
    for item in items[:2]:
        print(f"  {item.get('ItemName')} +{item.get('Plus')} -> {item.get('ItemPrice'):,}")
