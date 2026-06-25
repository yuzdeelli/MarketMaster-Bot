import sqlite3
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulation import ITEMS, REVERSE_ITEMS, LVLMULTI

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
inserted = 0
skipped = 0

servers = ["ZERO 3", "ZERO 4", "ZERO 5", "ZERO 8", "PANDORA 3", "PANDORA 4", "AGARTHA 3", "AGARTHA 4", "FELIS 2", "DESTAN 3", "DESTAN 2"]

for name, info in {**ITEMS, **REVERSE_ITEMS}.items():
    base = info["base"]
    var = info["var"]
    for lvl in info["lvls"]:
        mult = LVLMULTI.get(lvl, 1.0)
        est_price = int(base * mult * random.uniform(1 - var, 1 + var))
        
        for srv in random.sample(servers, min(3, len(servers))):
            for ptype in ["sell", "buy"]:
                seller = f"sim_{name[:8]}"
                cur.execute("SELECT id FROM prices WHERE item_name=? AND item_lvl=? AND type=? AND server=? AND seller=?",
                            (name, lvl, ptype, srv, seller))
                if cur.fetchone():
                    skipped += 1
                    continue
                cur.execute("INSERT INTO prices (server, type, item_name, item_lvl, price, timestamp, seller, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                            (srv, ptype, name, lvl, est_price, now, seller, now))
                inserted += 1

conn.commit()
conn.close()
print(f"Tamamlandi! Eklenen: {inserted} | Atlanan: {skipped}")
