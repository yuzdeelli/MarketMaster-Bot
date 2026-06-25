import sqlite3
import os

DB_FILES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'market_history.db'),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'market_history - Kopya.db'),
]

for path in DB_FILES:
    print('Checking:', path)
    if not os.path.exists(path):
        print('  Not found')
        continue
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'")
        found = cur.fetchone()
        if not found:
            print('  search_history: MISSING')
        else:
            print('  search_history: PRESENT')
            cur.execute('SELECT COUNT(*) FROM search_history')
            cnt = cur.fetchone()[0]
            print(f'  rows: {cnt}')
    except Exception as e:
        print('  ERROR:', e)
    finally:
        try:
            conn.close()
        except:
            pass
