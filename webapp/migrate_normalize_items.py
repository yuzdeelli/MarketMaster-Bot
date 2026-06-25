#!/usr/bin/env python3
"""Migration: normalize item names by removing trailing level suffixes like '(+1)' or '+1'
and populate `item_lvl` with the extracted '+N' value when available.
Creates a backup of the database before applying changes.
"""
import re
import shutil
import time
import sqlite3
from webapp import database as dbmod

DB_PATH = dbmod.DB_PATH

def backup_db(path):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = path + ".backup." + stamp
    shutil.copy(path, dest)
    return dest

def normalize_prices(conn):
    cur = conn.cursor()
    # ensure table exists
    tbl = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'").fetchone()
    if not tbl:
        print("Table 'prices' not found, skipping prices normalization.")
        return 0, 0
    rows = cur.execute("SELECT id, item_name, item_lvl FROM prices").fetchall()
    updated = 0
    for r in rows:
        id = r[0]
        name = (r[1] or '').strip()
        lvl = (r[2] or '').strip()
        if not name:
            continue
        m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)\)\s*$", name)
        if not m:
            m = re.search(r"^(.*?)[\s]*\+([0-9]+)\s*$", name)
        if m:
            new_name = m.group(1).strip()
            new_lvl = '+' + m.group(2)
            new_name = re.sub(r"\(\+?[0-9]+\)\s*$", "", new_name).strip()
            if new_name != name or (not lvl):
                cur.execute("UPDATE prices SET item_name=?, item_lvl=? WHERE id=?", (new_name, new_lvl, id))
                updated += 1
    return len(rows), updated

def normalize_search_history(conn):
    cur = conn.cursor()
    # ensure table exists
    tbl = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'").fetchone()
    if not tbl:
        print("Table 'search_history' not found, skipping search history normalization.")
        return 0, 0
    rows = cur.execute("SELECT id, item, lvl FROM search_history").fetchall()
    updated = 0
    for r in rows:
        id = r[0]
        name = (r[1] or '').strip()
        lvl = (r[2] or '').strip()
        if not name:
            continue
        m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)\)\s*$", name)
        if not m:
            m = re.search(r"^(.*?)[\s]*\+([0-9]+)\s*$", name)
        if m:
            new_name = m.group(1).strip()
            new_lvl = '+' + m.group(2)
            new_name = re.sub(r"\(\+?[0-9]+\)\s*$", "", new_name).strip()
            if new_name != name or (not lvl):
                cur.execute("UPDATE search_history SET item=?, lvl=? WHERE id=?", (new_name, new_lvl, id))
                updated += 1
    return len(rows), updated


def main():
    print("Backing up DB:", DB_PATH)
    bak = backup_db(DB_PATH)
    print("Backup created:", bak)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        p_total, p_updated = normalize_prices(conn)
        s_total, s_updated = normalize_search_history(conn)
        conn.commit()
        print(f"Prices: scanned {p_total}, updated {p_updated}")
        print(f"Search history: scanned {s_total}, updated {s_updated}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
