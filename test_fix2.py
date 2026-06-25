import sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

client = UskoApiClient(api_key=ConfigManager.load_api_key())

# Test reverse +1
result = client.get_items(server="zero3", plus=1, rebirth=1, limit=2)
items = result.get("data", [])
print(f"Reverse +1R: {len(items)} kayit")
for i in items[:1]:
    print(f"  ItemName: {i.get('ItemName')}")
    print(f"  Plus: {i.get('Plus')}")
