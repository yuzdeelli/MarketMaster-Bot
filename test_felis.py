import sqlite3
import pandas as pd

db_path = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"
conn = sqlite3.connect(db_path)

item = "Superior Draki Supply Box"
lvl = ""

# Simulate what get_item_stats does with server="FELIS"
server = "FELIS"
query = "SELECT type, price FROM prices WHERE item_name = ? AND (item_lvl = '' OR item_lvl IS NULL OR item_lvl = '+0' OR item_lvl = '0')"
params = [item]
if server:
    query += " AND server LIKE ?"
    params.append(f"%{server}%")

print(f"Query: {query}")
print(f"Params: {params}")
df = pd.read_sql_query(query, conn, params=tuple(params))
print(f"Results: {len(df)} rows")
if not df.empty:
    sell = df[df['type'].str.capitalize() == 'Sell']['price']
    buy = df[df['type'].str.capitalize() == 'Buy']['price']
    print(f"  Buy: {len(buy)} rows, median={buy.median() if not buy.empty else 'N/A'}")
    print(f"  Sell: {len(sell)} rows, median={sell.median() if not sell.empty else 'N/A'}")
else:
    print("  NO DATA!")

# Also check without server filter
print("\n--- Without server filter ---")
query2 = "SELECT type, price FROM prices WHERE item_name = ? AND (item_lvl = '' OR item_lvl IS NULL OR item_lvl = '+0' OR item_lvl = '0')"
df2 = pd.read_sql_query(query2, conn, params=(item,))
print(f"Results: {len(df2)} rows")
if not df2.empty:
    sell2 = df2[df2['type'].str.capitalize() == 'Sell']['price']
    buy2 = df2[df2['type'].str.capitalize() == 'Buy']['price']
    print(f"  Buy: {len(buy2)} rows, median={buy2.median() if not buy2.empty else 'N/A'}")
    print(f"  Sell: {len(sell2)} rows, median={sell2.median() if not sell2.empty else 'N/A'}")

conn.close()
