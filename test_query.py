import sqlite3
import pandas as pd
from datetime import datetime, timedelta

db_path = r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db"

# Simulate what get_item_stats does with server="AGARTHA" and time_filter="Tumu"
item_name = "Chitin Helmet"
item_lvl = ""
server = "AGARTHA"

conn = sqlite3.connect(db_path)

# No time filter (Tumu)
query = "SELECT type, price FROM prices WHERE item_name = ? AND (item_lvl = '' OR item_lvl IS NULL OR item_lvl = '+0' OR item_lvl = '0')"
params = [item_name]

if server:
    query += " AND server LIKE ?"
    params.append(f"%{server}%")

df = pd.read_sql_query(query, conn, params=tuple(params))
print(f"Server={server}, Tumu: {len(df)} rows")

# With 60 min filter
cutoff = (datetime.utcnow() - timedelta(minutes=60)).strftime('%Y-%m-%d %H:%M:%S')
query2 = query + " AND timestamp >= ?"
params2 = params + [cutoff]
df2 = pd.read_sql_query(query2, conn, params=tuple(params2))
print(f"Server={server}, 60dk: {len(df2)} rows, cutoff={cutoff}")

# Now "Tum Sunucular" (no server filter)
query3 = "SELECT type, price FROM prices WHERE item_name = ? AND (item_lvl = '' OR item_lvl IS NULL OR item_lvl = '+0' OR item_lvl = '0')"
params3 = [item_name]
df3 = pd.read_sql_query(query3, conn, params=tuple(params3))
print(f"Server=None, Tumu: {len(df3)} rows")

conn.close()
