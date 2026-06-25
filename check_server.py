import urllib.request
import json

# Dashboard test
r = urllib.request.urlopen('http://127.0.0.1:8765/dashboard', timeout=5)
html = r.read().decode()
print(f"Dashboard: {len(html)} byte")

# API test
r2 = urllib.request.urlopen('http://127.0.0.1:8765/api/items?limit=5', timeout=5)
d = json.loads(r2.read())
print(f"\nToplam item: {d['count']}")
for i in d['items'][:5]:
    print(f"  {i['item']} {i['lvl']}: {i['sell_med']:,}")

# +0 kontrol
r3 = urllib.request.urlopen('http://127.0.0.1:8765/api/items?limit=500', timeout=5)
d3 = json.loads(r3.read())
zero_items = [i for i in d3['items'] if i['lvl'] == '+0']
non_zero = [i for i in d3['items'] if i['lvl'] != '+0']
print(f"\n+0 item: {len(zero_items)}")
print(f"+0 olmayan: {len(non_zero)}")

# +0 olanlari listele
if zero_items:
    print("\n+0 olanlar:")
    for i in zero_items[:10]:
        print(f"  {i['item']} {i['lvl']}: {i['sell_med']:,}")
