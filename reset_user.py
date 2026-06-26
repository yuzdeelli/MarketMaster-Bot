import sqlite3, os

try:
    import bcrypt
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "bcrypt"])
    import bcrypt

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_users.db")
conn = sqlite3.connect(db_path)

password = "onur1234"
pwd_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

conn.execute("UPDATE users SET failed_attempts=0, locked_until=NULL")
conn.execute("UPDATE users SET password_hash=?, is_admin=1, is_active=1 WHERE username=?", (pwd_hash, "onur006"))
conn.commit()

user = conn.execute("SELECT username, is_admin FROM users WHERE username='onur006'").fetchone()
print(f"Kullanici: {user[0]}, Admin: {user[1]}")
print("Sifre 'onur1234' olarak ayarlandi!")
conn.close()
