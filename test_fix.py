import sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

client = UskoApiClient(api_key=ConfigManager.load_api_key())

# Test normal +7
result = client.get_items(server="zero3", plus=7, limit=2)
items = result.get("data", [])
print(f"Normal +7: {len(items)} kayit")
for i in items[:1]:
    print(f"  {i.get('ItemName')} Plus={i.get('Plus')}")

# Test reverse +1
result = client.get_items(server="zero3", plus=1, rebirth=1, limit=2)
items = result.get("data", [])
print(f"Reverse +1R: {len(items)} kayit")
for i in items[:1]:
    print(f"  {i.get('ItemName')} Plus={i.get('Plus')}")

# Test fetch_all_items with levels and reverse_levels
from core.usko_api import SERVER_MAP_REVERSE
parsed = client.fetch_all_items(
    "zero3", levels=[0, 7], reverse_levels=[1], limit=2,
    progress_callback=lambda m,c: None
)
print(f"\nfetch_all sonucu: {len(parsed)} kayit")
for p in parsed:
    print(f"  {p['İtem Adı']} -> {p['Artı']}")
