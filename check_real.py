import sqlite3

# app_data.db - gercek tarama verisi
conn = sqlite3.connect(r'C:\Users\hort\Desktop\Market Master V - 1\app_data.db')

rows = conn.execute("""
    SELECT item_name, item_lvl, COUNT(*) as cnt, AVG(price) as avg_price, MIN(timestamp) as first, MAX(timestamp) as last
    FROM prices
    WHERE item_name LIKE '%Mirage%'
    GROUP BY item_name, item_lvl
    ORDER BY item_name, item_lvl
""").fetchall()

print("=== app_data.db - Mirage varyantlari (GERCEK TARAMA) ===")
for r in rows:
    print(f"  {r[0]} {r[1]}: {r[2]} kayit, ort:{r[3]:,.0f}, ilk:{r[4]}, son:{r[5]}")

# web_market.db - simülasyon + eski veri
conn2 = sqlite3.connect(r'C:\Users\hort\Desktop\Market Master V - 1\web_market.db')
rows2 = conn2.execute("""
    SELECT item_name, item_lvl, COUNT(*) as cnt, MIN(timestamp) as first, MAX(timestamp) as last
    FROM prices
    WHERE item_name LIKE '%Mirage%'
    GROUP BY item_name, item_lvl
    ORDER BY item_name, item_lvl
""").fetchall()

print("\n=== web_market.db - Mirage varyantlari ===")
for r in rows2:
    print(f"  {r[0]} {r[1]}: {r[2]} kayit, ilk:{r[3]}, son:{r[4]}")

# Simülasyon verileri ne zaman basladigini bul
print("\n=== web_market.db - Simulasyon baslangic tarihi ===")
sim_start = conn2.execute("SELECT MIN(timestamp) FROM prices WHERE item_name IN ('Flame Ring', 'Iron Impact', 'Mirage Dagger', 'Raptor')").fetchone()
print(f"  Simulasyon baslangic: {sim_start[0]}")

# Mirage Dagger kayitlarinin timestamp'leri
print("\n=== web_market.db - Mirage Dagger timestamp ornekleri ===")
ts_rows = conn2.execute("SELECT item_lvl, timestamp, price FROM prices WHERE item_name='Mirage Dagger' ORDER BY id DESC LIMIT 10").fetchall()
for r in ts_rows:
    print(f"  +{r[0]} | {r[1]} | {r[2]:,}")

conn.close()
conn2.close()
