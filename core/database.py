import os
import stat
import sqlite3
import threading
from contextlib import contextmanager

from utils.logger import get_logger

logger = get_logger()


def fix_write_permissions(path):
    if os.path.exists(path):
        try:
            os.chmod(path, stat.S_IWRITE)
        except PermissionError:
            pass


def initialize_database(db_path):
    try:
        if os.path.exists(db_path):
            os.chmod(db_path, stat.S_IWRITE)

        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server TEXT,
                type TEXT,
                item_name TEXT,
                item_lvl TEXT,
                price INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                seller TEXT,
                last_seen DATETIME
            )
        """)
        for col, typ in [("seller", "TEXT"), ("last_seen", "DATETIME")]:
            try:
                cursor.execute(f"ALTER TABLE prices ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.commit()
        conn.close()
        logger.info("Veritabani dogrulandi.")
    except Exception as e:
        logger.exception(f"SQL hazirlama hatasi: {e}")


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=60000")
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self):
        initialize_database(self.db_path)

    def get_unique_servers(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT server FROM prices ORDER BY server ASC")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.exception(f"Sunucu listesi alinamadi: {e}")
            return []

    def insert_price(self, data):
        with self.lock:
            try:
                import re
                from core.engine import should_skip_record, is_reverse_level
                name = (data.get("İtem Adı", "") or "").strip()
                level = (data.get("Artı", "") or "").strip()
                if not level:
                    m = re.search(r"^(.*?)[\s]*\(\+?([0-9]+)(R?)\)\s*$", name)
                    if not m:
                        m = re.search(r"^(.*?)[\s]*\+([0-9]+)(R?)\s*$", name)
                    if m:
                        name = m.group(1).strip()
                        level = '+' + m.group(2) + m.group(3)
                name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()
                seller = str(data.get("UserID", "") or "").strip()

                timestamp = data.get("Zaman")
                if not timestamp:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with self.get_connection() as conn:
                    conn.execute(
                        """INSERT INTO prices (server, type, item_name, item_lvl, price, timestamp, seller, last_seen)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (data["Sunucu"], data["Pazar Tipi"],
                         name, level, data["Fiyat"], timestamp, seller, timestamp),
                    )
                    conn.commit()
            except Exception as e:
                logger.exception(f"DB insert error: {e}")

    def get_all_unique_items(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT item_name, item_lvl FROM prices")
                rows = cursor.fetchall()
                return [
                    {
                        "name": row[0].strip() if row[0] else row[0],
                        "lvl": row[1].strip() if row[1] else row[1],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.exception(f"Item listesi alinamadi: {e}")
            return []

    def get_unique_item_names(self):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT item_name FROM prices ORDER BY item_name ASC")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.exception(f"Item isim listesi alinamadi: {e}")
            return []

    def get_prices(self, item_name, item_lvl="", limit=100):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if item_lvl in ["+0", "0", "", None]:
                    cursor.execute("""
                        SELECT server, type, item_name, item_lvl, price, timestamp
                        FROM prices WHERE item_name = ?
                        AND (item_lvl = '' OR item_lvl IS NULL OR item_lvl = '+0' OR item_lvl = '0')
                        ORDER BY timestamp DESC LIMIT ?
                    """, (item_name, limit))
                else:
                    cursor.execute("""
                        SELECT server, type, item_name, item_lvl, price, timestamp
                        FROM prices WHERE item_name = ? AND item_lvl = ?
                        ORDER BY timestamp DESC LIMIT ?
                    """, (item_name, item_lvl, limit))
                return [
                    {
                        "server": r[0], "type": r[1], "item_name": r[2],
                        "item_lvl": r[3], "price": r[4], "timestamp": r[5]
                    }
                    for r in cursor.fetchall()
                ]
        except Exception as e:
            logger.exception(f"Fiyat listesi alinamadi: {e}")
            return []
