import sqlite3

db = sqlite3.connect("app_data.db")

before = db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
print(f"Once: {before} kayit")

# Remove buy price=1 placeholders
r1 = db.execute("DELETE FROM prices WHERE type='buy' AND price=1").rowcount
print(f"Buy price=1 silindi: {r1}")

# For remaining duplicates (same item+server+price+type, different levels), keep only min(id)
dups = db.execute("""
    SELECT item_name, server, price, type, COUNT(DISTINCT item_lvl) as cnt
    FROM prices
    GROUP BY item_name, server, price, type
    HAVING cnt > 1
""").fetchall()
print(f"Hala {len(dups)} grup duplicate var")

for row in dups:
    name, srv, price, ptype, cnt = row
    # Get all ids for this group, keep only the first one
    ids = db.execute(
        "SELECT id FROM prices WHERE item_name=? AND server=? AND price=? AND type=? ORDER BY id",
        (name, srv, price, ptype)
    ).fetchall()
    keep_id = ids[0][0]
    del_ids = [str(i[0]) for i in ids[1:]]
    if del_ids:
        db.execute(f"DELETE FROM prices WHERE id IN ({','.join(del_ids)})")

after = db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
print(f"Sonra: {after} kayit (silinen: {before - r1 - after + r1})")

remaining_dups = db.execute("""
    SELECT COUNT(*) FROM (
        SELECT item_name, server, price, type FROM prices
        GROUP BY item_name, server, price, type
        HAVING COUNT(DISTINCT item_lvl) > 1
    )
""").fetchone()[0]
print(f"Kalan duplicate: {remaining_dups}")

db.commit()
db.close()
