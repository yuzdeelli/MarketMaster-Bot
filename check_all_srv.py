import sqlite3
conn = sqlite3.connect(r"C:\Users\hort\Desktop\Market Master V - 1\app_data.db")
c = conn.cursor()

# Her sunucuda toplam kayit ve buy/satis dagilimi
c.execute("""
    SELECT 
        CASE 
            WHEN server LIKE '%ZERO%' THEN 'ZERO'
            WHEN server LIKE '%PANDORA%' THEN 'PANDORA'
            WHEN server LIKE '%AGARTHA%' THEN 'AGARTHA'
            WHEN server LIKE '%DESTAN%' THEN 'DESTAN'
            WHEN server LIKE '%FELIS%' THEN 'FELIS'
            WHEN server LIKE '%MINARK%' THEN 'MINARK'
            WHEN server LIKE '%DRYADS%' THEN 'DRYADS'
            WHEN server LIKE '%OREADS%' THEN 'OREADS'
            ELSE 'OTHER'
        END as srv_group,
        type,
        COUNT(*) as cnt,
        MIN(timestamp) as min_ts,
        MAX(timestamp) as max_ts
    FROM prices
    GROUP BY srv_group, type
    ORDER BY srv_group, type
""")
for r in c.fetchall():
    print(f"{r[0]:10s} {r[1]:5s}: {r[2]:5d} kayit | {r[3]} -> {r[4]}")
conn.close()
