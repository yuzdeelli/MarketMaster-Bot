import requests, sqlite3
token = '7628b6d2eb3f90bfb598bec5036aca85aa1cb8b31473f4269c4202e6d047cb7c'
h = {'Authorization': 'Token ' + token}
r = requests.get('https://www.pythonanywhere.com/api/v0/user/marketmaster/files/path/home/marketmaster/app_data.db', headers=h, timeout=60)
open('temp_pa.db', 'wb').write(r.content)
conn = sqlite3.connect('temp_pa.db')
tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)
if 'snapshots' in tables:
    cnt = conn.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0]
    print(f'Snapshots: {cnt}')
    row = conn.execute('SELECT item_name, item_lvl, server FROM snapshots WHERE item_name LIKE "%Draki%" LIMIT 3').fetchall()
    print('Draki samples:', row)
conn.close()
