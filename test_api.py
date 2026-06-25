import json, os, sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
os.chdir(r"C:\Users\hort\Desktop\Market Master V - 1")

from core.config import ConfigManager
api_key = ConfigManager.load_api_key()
print(f"API Key var: {'EVET' if api_key else 'HAYIR'}")
print(f"API Key: {api_key[:10]}..." if api_key and len(api_key) > 10 else f"API Key: {api_key}")

from core.usko_api import UskoApiClient
client = UskoApiClient(api_key=api_key)

print("\n--- API Durumu ---")
status = client.get_status()
print(f"Status: {status}")

print("\n--- Tarama Testi (Iron Impact +1, ZERO 3) ---")
result, error = client.scan_item(
    server_display="ZERO 3",
    item_name="Iron Impact",
    plus=1,
    item_type=-1,
    limit=5
)
if error:
    print(f"HATA: {error}")
else:
    print(f"Sonuc: {len(result)} kayit")
    for r in result[:3]:
        print(f"  {r}")
