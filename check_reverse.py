import sqlite3

conn = sqlite3.connect(r'C:\Users\hort\Desktop\Market Master V - 1\web_market.db')

# Iron Impact tum verileri
rows = conn.execute("""
    SELECT item_name, item_lvl, price, seller, timestamp
    FROM prices
    WHERE item_name = 'Iron Impact'
    ORDER BY item_lvl, price
""").fetchall()

print("=== Iron Impact Tum Veriler ===")
print(f"{'Item':<20} {'Lvl':>5} {'Fiyat':>15} {'Satici':<18} {'Zaman'}")
print("-" * 80)
for r in rows:
    print(f"{r[0]:<20} {r[1]:>5} {r[2]:>15,} {r[3]:<18} {r[4]}")

# Level bazli ozet
print("\n=== Level bazli ozet ===")
rows2 = conn.execute("""
    SELECT item_lvl, COUNT(*) as cnt, MIN(price) as min_p, AVG(price) as avg_p, MAX(price) as max_p
    FROM prices WHERE item_name = 'Iron Impact'
    GROUP BY item_lvl ORDER BY item_lvl
""").fetchall()
for r in rows2:
    print(f"  {r[0]:>5} | {r[1]:>4} kayit | min: {r[2]:>12,} | ort: {r[3]:>12,} | max: {r[4]:>12,}")

# Reverse icerigi kontrol
print("\n=== Reverse kontrol ===")
rev = conn.execute("""
    SELECT item_name, item_lvl, COUNT(*) as cnt
    FROM prices
    WHERE item_name LIKE '%reverse%' OR item_name LIKE '%Reverse%'
    GROUP BY item_name, item_lvl
""").fetchall()
for r in rev:
    print(f"  {r[0]:<30} {r[1]:>5} | {r[2]:>5} kayit")

# Tum +1 verilerinin fiyat dagilimi
print("\n=== Tum +1 verileri (Iron Impact) ===")
rows3 = conn.execute("""
    SELECT price FROM prices WHERE item_name = 'Iron Impact' AND item_lvl = '+1' ORDER BY price
""").fetchall()
prices = [r[0] for r in rows3]
if prices:
    print(f"  Min: {min(prices):,}")
    print(f"  Max: {max(prices):,}")
    print(f"  Ort: {sum(prices)//len(prices):,}")
    print(f"  Medyan: {prices[len(prices)//2]:,}")

conn.close()
