import sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

client = UskoApiClient(api_key=ConfigManager.load_api_key())

# 1. Normal seviye testi
print("=== NORMAL SEVIYELER ===")
for lvl in [0, 1, 2, 5, 7]:
    result = client.get_items(server="zero3", plus=lvl, limit=1)
    items = result.get("data", [])
    if items:
        i = items[0]
        print(f"  +{lvl}: {i.get('ItemName')} | Plus={i.get('Plus')}")
    else:
        print(f"  +{lvl}: bos")

# 2. Reverse seviye testi
print("\n=== REVERSE SEVIYELER ===")
for lvl in [1, 2, 3, 5]:
    result = client.get_items(server="zero3", plus=lvl, rebirth=1, limit=1)
    items = result.get("data", [])
    if items:
        i = items[0]
        print(f"  +{lvl}R: {i.get('ItemName')} | Plus={i.get('Plus')}")
    else:
        print(f"  +{lvl}R: bos")

# 3. fetch_all_items testi
print("\n=== FETCH_ALL_ITEMS ===")
parsed = client.fetch_all_items(
    "zero3", levels=[0, 1, 7], reverse_levels=[1, 2], limit=1,
    progress_callback=lambda m,c: None
)
for p in parsed:
    print(f"  {p['Arti']} {p['Ilem Adi'][:30]} -> {p['Fiyat']:,}")

print(f"\nToplam: {len(parsed)} kayit")
