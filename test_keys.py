import sys
sys.path.insert(0, r"C:\Users\hort\Desktop\Market Master V - 1")
from core.config import ConfigManager
from core.usko_api import UskoApiClient

c = UskoApiClient(api_key=ConfigManager.load_api_key())
r = c.fetch_all_items("zero3", levels=[7], reverse_levels=[1], limit=1, progress_callback=lambda m,n: None)
if r:
    print("Keys:", list(r[0].keys()))
    print("Sample:", r[0])
