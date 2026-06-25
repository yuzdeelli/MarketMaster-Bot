import os
import sys
import json
import hashlib
import secrets
import time
import sqlite3
import base64
import hmac
import re
import bcrypt
from datetime import datetime, timedelta
from functools import wraps

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECURITY_FILE = os.path.join(BASE_DIR, "security.json")
AUTH_DB_PATH = os.path.join(BASE_DIR, "web_users.db")
ENCRYPT_KEY_FILE = os.path.join(BASE_DIR, ".secret_key")
AUDIT_DB_PATH = os.path.join(BASE_DIR, "audit.db")

DEFAULT_SECURITY = {
    "api_token": "",
    "ip_whitelist": [],
    "ip_whitelist_enabled": False,
    "session_secret": "",
    "max_login_attempts": 5,
    "lockout_minutes": 15,
    "api_rate_limit": 60,
    "require_api_auth": True,
    "session_timeout_minutes": 30,
    "password_min_length": 8,
    "password_require_upper": True,
    "password_require_lower": True,
    "password_require_digit": True,
    "password_require_special": False,
    "brute_force_persist": True
}


def _get_encrypt_key():
    if os.path.exists(ENCRYPT_KEY_FILE):
        with open(ENCRYPT_KEY_FILE, "rb") as f:
            return f.read()
    key = secrets.token_bytes(32)
    with open(ENCRYPT_KEY_FILE, "wb") as f:
        f.write(key)
    return key


def encrypt_value(value):
    key = _get_encrypt_key()
    msg = value.encode("utf-8")
    signature = hmac.new(key, msg, hashlib.sha256).digest()
    payload = signature + msg
    return base64.b64encode(payload).decode("utf-8")


def decrypt_value(encrypted):
    try:
        key = _get_encrypt_key()
        payload = base64.b64decode(encrypted)
        signature = payload[:32]
        msg = payload[32:]
        expected = hmac.new(key, msg, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        return msg.decode("utf-8")
    except:
        return None


def get_auth_db():
    conn = sqlite3.connect(AUTH_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_auth_db():
    conn = get_auth_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT,
            login_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT
        )
    """)
    existing = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    migrations = [
        ("last_login", "ALTER TABLE users ADD COLUMN last_login TEXT"),
        ("login_count", "ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0"),
        ("is_active", "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1"),
        ("failed_attempts", "ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0"),
        ("locked_until", "ALTER TABLE users ADD COLUMN locked_until TEXT"),
        ("is_admin", "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"),
    ]
    for col, sql in migrations:
        if col not in existing:
            conn.execute(sql)
    conn.commit()
    conn.close()


def init_audit_db():
    conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            username TEXT,
            ip_address TEXT,
            details TEXT,
            success INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brute_force_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            username TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            blocked INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            method TEXT,
            endpoint TEXT,
            ip_address TEXT,
            status_code INTEGER,
            username TEXT,
            response_time_ms INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            threat_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            ip_address TEXT,
            endpoint TEXT,
            username TEXT,
            payload TEXT,
            blocked INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_logs_ts ON api_logs(timestamp DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_logs_ip ON api_logs(ip_address)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_threats_ts ON threat_logs(timestamp DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_threats_type ON threat_logs(threat_type)")
    conn.commit()
    conn.close()


def log_audit_event(event_type, username=None, ip_address=None, details=None, success=1):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.execute(
            "INSERT INTO audit_log (event_type, username, ip_address, details, success) VALUES (?, ?, ?, ?, ?)",
            (event_type, username, ip_address, details, success)
        )
        conn.commit()
        conn.close()
    except:
        pass


def log_api_request(method, endpoint, ip_address, status_code, username=None, response_time_ms=None):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.execute(
            "INSERT INTO api_logs (method, endpoint, ip_address, status_code, username, response_time_ms) VALUES (?, ?, ?, ?, ?, ?)",
            (method, endpoint, ip_address, status_code, username, response_time_ms)
        )
        conn.commit()
        conn.close()
    except:
        pass


def get_api_logs(limit=200, method=None, endpoint=None, ip_address=None):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM api_logs WHERE 1=1"
        params = []
        if method:
            query += " AND method = ?"
            params.append(method)
        if endpoint:
            query += " AND endpoint LIKE ?"
            params.append(f"%{endpoint}%")
        if ip_address:
            query += " AND ip_address = ?"
            params.append(ip_address)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []


def clear_api_logs():
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.execute("DELETE FROM api_logs")
        conn.commit()
        conn.close()
        return True
    except:
        return False


def get_api_log_stats():
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) as cnt FROM api_logs").fetchone()["cnt"]
        by_method = [dict(r) for r in conn.execute(
            "SELECT method, COUNT(*) as cnt FROM api_logs GROUP BY method ORDER BY cnt DESC"
        ).fetchall()]
        by_endpoint = [dict(r) for r in conn.execute(
            "SELECT endpoint, COUNT(*) as cnt FROM api_logs GROUP BY endpoint ORDER BY cnt DESC LIMIT 10"
        ).fetchall()]
        by_status = [dict(r) for r in conn.execute(
            "SELECT status_code, COUNT(*) as cnt FROM api_logs GROUP BY status_code ORDER BY cnt DESC"
        ).fetchall()]
        by_ip = [dict(r) for r in conn.execute(
            "SELECT ip_address, COUNT(*) as cnt FROM api_logs GROUP BY ip_address ORDER BY cnt DESC LIMIT 10"
        ).fetchall()]
        conn.close()
        return {
            "total": total,
            "by_method": by_method,
            "by_endpoint": by_endpoint,
            "by_status": by_status,
            "by_ip": by_ip,
        }
    except:
        return {"total": 0, "by_method": [], "by_endpoint": [], "by_status": [], "by_ip": []}


def validate_password_strength(password, sec=None):
    if sec is None:
        sec = load_security()

    min_len = sec.get("password_min_length", 8)
    require_upper = sec.get("password_require_upper", True)
    require_lower = sec.get("password_require_lower", True)
    require_digit = sec.get("password_require_digit", True)
    require_special = sec.get("password_require_special", False)

    errors = []
    if len(password) < min_len:
        errors.append(f"En az {min_len} karakter")
    if require_upper and not re.search(r'[A-Z]', password):
        errors.append("Buyuk harf gerekli (A-Z)")
    if require_lower and not re.search(r'[a-z]', password):
        errors.append("Kucuk harf gerekli (a-z)")
    if require_digit and not re.search(r'\d', password):
        errors.append("Rakam gerekli (0-9)")
    if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Ozel karakter gerekli")

    return len(errors) == 0, errors


def hash_password(password):
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password, stored_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except:
        return False


def register_user(username, password):
    if not username or len(username) < 3:
        return False, "Kullanici adi en az 3 karakter olmali"

    valid, errors = validate_password_strength(password)
    if not valid:
        return False, ", ".join(errors)

    try:
        conn = get_auth_db()
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        conn.close()
        log_audit_event("REGISTER", username=username, details="Kayit basarili")
        return True, "Kayit basarili"
    except sqlite3.IntegrityError:
        return False, "Bu kullanici zaten var"
    except Exception as e:
        return False, f"Kayit hatasi: {e}"


def authenticate_user(username, password):
    conn = get_auth_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        log_audit_event("LOGIN_FAIL", username=username, details="Kullanici bulunamadi", success=0)
        conn.close()
        return False, None

    if not user["is_active"]:
        log_audit_event("LOGIN_FAIL", username=username, details="Hesap devre disi", success=0)
        conn.close()
        return False, None

    if user["locked_until"]:
        try:
            locked_until = datetime.fromisoformat(user["locked_until"])
            if datetime.now() < locked_until:
                remaining = (locked_until - datetime.now()).seconds // 60
                log_audit_event("LOGIN_FAIL", username=username, details=f"Hesap kilitli, {remaining} dk kaldi", success=0)
                conn.close()
                return False, None
            else:
                conn.execute("UPDATE users SET locked_until = NULL, failed_attempts = 0 WHERE id = ?", (user["id"],))
                conn.commit()
        except:
            pass

    if verify_password(password, user["password_hash"]):
        conn.execute(
            "UPDATE users SET last_login = ?, login_count = login_count + 1, failed_attempts = 0 WHERE id = ?",
            (datetime.now().isoformat(), user["id"])
        )
        conn.commit()
        conn.close()
        log_audit_event("LOGIN_SUCCESS", username=username, details="Giris basarili")
        return True, {"id": user["id"], "username": user["username"]}
    else:
        new_attempts = user["failed_attempts"] + 1
        sec = load_security()
        max_attempts = sec.get("max_login_attempts", 5)
        lockout_mins = sec.get("lockout_minutes", 15)

        if new_attempts >= max_attempts:
            locked_until = (datetime.now() + timedelta(minutes=lockout_mins)).isoformat()
            conn.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                (new_attempts, locked_until, user["id"])
            )
            log_audit_event("ACCOUNT_LOCKED", username=username, details=f"{new_attempts} basarisiz deneme, {lockout_mins} dk kilit")
        else:
            conn.execute(
                "UPDATE users SET failed_attempts = ? WHERE id = ?",
                (new_attempts, user["id"])
            )
            log_audit_event("LOGIN_FAIL", username=username, details=f"Basarisiz deneme {new_attempts}/{max_attempts}", success=0)

        conn.commit()
        conn.close()
        return False, None


def change_password(username, old_password, new_password):
    conn = get_auth_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user:
        conn.close()
        return False, "Kullanici bulunamadi"

    if not verify_password(old_password, user["password_hash"]):
        log_audit_event("PASSWORD_CHANGE_FAIL", username=username, details="Eski sifre hatali", success=0)
        conn.close()
        return False, "Eski sifre hatali"

    valid, errors = validate_password_strength(new_password)
    if not valid:
        conn.close()
        return False, ", ".join(errors)

    if old_password == new_password:
        conn.close()
        return False, "Yeni sifre eskisiyle ayni olamaz"

    new_hash = hash_password(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user["id"])
    )
    conn.commit()
    conn.close()
    log_audit_event("PASSWORD_CHANGE", username=username, details="Sifre degistirildi")
    return True, "Sifre degistirildi"


def load_security():
    if os.path.exists(SECURITY_FILE):
        try:
            with open(SECURITY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, val in DEFAULT_SECURITY.items():
                    if key not in data:
                        data[key] = val
                return data
        except:
            pass
    return DEFAULT_SECURITY.copy()


def save_security(data):
    with open(SECURITY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_api_token():
    token = secrets.token_hex(32)
    sec = load_security()
    sec["api_token"] = token
    save_security(sec)
    return token


def check_ip_whitelist(ip):
    sec = load_security()
    if not sec.get("ip_whitelist_enabled"):
        return True
    whitelist = sec.get("ip_whitelist", [])
    if not whitelist:
        return False
    return ip in whitelist or ip == "127.0.0.1"


def verify_api_token(token):
    sec = load_security()
    expected = sec.get("api_token", "")
    if not expected:
        return False
    if sec.get("api_token_encrypted"):
        from core.config import CryptoManager
        expected = CryptoManager.decrypt(expected)
    return secrets.compare_digest(token, expected)


_login_attempts = {}


def check_login_attempts(ip):
    sec = load_security()
    max_attempts = sec.get("max_login_attempts", 5)
    lockout = sec.get("lockout_minutes", 15)

    if ip not in _login_attempts:
        return True

    attempts, first_time = _login_attempts[ip]
    if time.time() - first_time > lockout * 60:
        _login_attempts.pop(ip, None)
        return True

    return attempts < max_attempts


def record_login_attempt(ip):
    if ip not in _login_attempts:
        _login_attempts[ip] = (1, time.time())
    else:
        attempts, first_time = _login_attempts[ip]
        _login_attempts[ip] = (attempts + 1, first_time)


def clear_login_attempts(ip):
    _login_attempts.pop(ip, None)


def check_session_timeout(session_data):
    sec = load_security()
    timeout_mins = sec.get("session_timeout_minutes", 30)

    login_time = session_data.get("login_time")
    if not login_time:
        return True

    try:
        login_dt = datetime.fromisoformat(login_time)
        if datetime.now() - login_dt > timedelta(minutes=timeout_mins):
            return False
        return True
    except:
        return True


def get_audit_logs(limit=100, event_type=None):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        if event_type:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []


def get_brute_force_logs(limit=50):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM brute_force_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []


def delete_user(username):
    try:
        conn = get_auth_db()
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        log_audit_event("USER_DELETED", username=username, details="Hesap silindi")
        return True
    except:
        return False


def list_users():
    try:
        conn = get_auth_db()
        rows = conn.execute(
            "SELECT id, username, created_at, last_login, login_count, is_active, failed_attempts, locked_until, is_admin FROM users"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []


def set_user_admin(username, is_admin=True):
    try:
        conn = get_auth_db()
        conn.execute("UPDATE users SET is_admin = ? WHERE username = ?", (1 if is_admin else 0, username))
        conn.commit()
        conn.close()
        return True
    except:
        return False


def is_admin_user(username):
    try:
        conn = get_auth_db()
        user = conn.execute("SELECT is_admin FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        return user and user["is_admin"]
    except:
        return False


def toggle_user_active(username):
    try:
        conn = get_auth_db()
        user = conn.execute("SELECT is_active FROM users WHERE username = ?", (username,)).fetchone()
        if user:
            new_status = 0 if user["is_active"] else 1
            conn.execute("UPDATE users SET is_active = ? WHERE username = ?", (new_status, username))
            conn.commit()
            conn.close()
            log_audit_event("USER_TOGGLED", username=username, details=f"Durum: {'aktif' if new_status else 'devre disi'}")
            return True
        conn.close()
        return False
    except:
        return False


# ===== THREAT DETECTION SYSTEM =====

SQL_INJECTION_PATTERNS = [
    r"(?i)(\bunion\b.*\bselect\b)",
    r"(?i)(\bselect\b.*\bfrom\b)",
    r"(?i)(\binsert\b.*\binto\b)",
    r"(?i)(\bdelete\b.*\bfrom\b)",
    r"(?i)(\bdrop\b.*\btable\b)",
    r"(?i)(\bupdate\b.*\bset\b)",
    r"(?i)(\bor\b\s+[\d\w]+\s*=\s*[\d\w]+)",
    r"(?i)(\band\b\s+[\d\w]+\s*=\s*[\d\w]+)",
    r"(?i)(;\s*--)",
    r"(?i)(;\s*drop\b)",
    r"(?i)(\'\s*or\s*\')",
    r"(?i)(1\s*=\s*1)",
    r"(?i)(1\s*'\s*=\s*'1)",
    r"(?i)(\bexec\b.*\bxp_)",
    r"(?i)(\bsleep\s*\(\d+\))",
    r"(?i)(\bbenchmark\s*\()",
]

XSS_PATTERNS = [
    r"<script[\s>]",
    r"javascript\s*:",
    r"on\w+\s*=\s*['\"]",
    r"<iframe[\s>]",
    r"<object[\s>]",
    r"<embed[\s>]",
    r"<applet[\s>]",
    r"<form[\s>].*on\w+",
    r"<img[\s>].*onerror",
    r"<svg[\s>].*onload",
    r"<body[\s>].*onload",
    r"<link[\s>].*rel\s*=\s*['\"]import",
    r"expression\s*\(",
    r"url\s*\(\s*['\"]?\s*data\s*:",
    r"<\s*script",
    r"&#\d+;",  # HTML entity encoding bypass
    r"%3[Cc]script",
    r"%0[0Dd]",
]

PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.\\",
    r"%2[eE]%2[eE]%2[fF]",
    r"%2[eE]%2[eE]%5[cC]",
    r"\.\.%2[fF]",
    r"\.\.%5[cC]",
    r"/etc/passwd",
    r"/etc/shadow",
    r"boot\.ini",
    r"win\.ini",
    r"system32",
    r"/proc/self",
]

COMMAND_INJECTION_PATTERNS = [
    r"[;&|`]",
    r"\$\(.*\)",
    r"`.*`",
    r"\bcat\s+/etc",
    r"\bls\s+/",
    r"\bwhoami\b",
    r"\bping\s+-c",
    r"\bwget\s+",
    r"\bcurl\s+",
    r"\bchmod\s+",
    r"\brm\s+-rf",
    r"\bmkfs\b",
    r"\bdd\s+if=",
]

SUSPICIOUS_UA_PATTERNS = [
    r"(?i)(sqlmap)",
    r"(?i)(nikto)",
    r"(?i)(nessus)",
    r"(?i)(openvas)",
    r"(?i)(havij)",
    r"(?i)(acunetix)",
    r"(?i)(netsparker)",
    r"(?i)(w3af)",
    r"(?i)(skipfish)",
    r"(?i)(burpsuite)",
    r"(?i)(zmeu)",
    r"(?i)(morfeus)",
]


def _check_patterns(text, patterns):
    if not text:
        return False, []
    matches = []
    for pat in patterns:
        if re.search(pat, text):
            matches.append(pat)
    return len(matches) > 0, matches


def scan_input(value, source=""):
    threats = []
    if not isinstance(value, str):
        value = str(value)

    detected, matches = _check_patterns(value, SQL_INJECTION_PATTERNS)
    if detected:
        threats.append({
            "type": "SQL_INJECTION",
            "severity": "critical",
            "source": source,
            "payload": value[:500],
            "matched": len(matches),
        })

    detected, matches = _check_patterns(value, XSS_PATTERNS)
    if detected:
        threats.append({
            "type": "XSS",
            "severity": "high",
            "source": source,
            "payload": value[:500],
            "matched": len(matches),
        })

    detected, matches = _check_patterns(value, PATH_TRAVERSAL_PATTERNS)
    if detected:
        threats.append({
            "type": "PATH_TRAVERSAL",
            "severity": "high",
            "source": source,
            "payload": value[:500],
            "matched": len(matches),
        })

    detected, matches = _check_patterns(value, COMMAND_INJECTION_PATTERNS)
    if detected:
        threats.append({
            "type": "COMMAND_INJECTION",
            "severity": "critical",
            "source": source,
            "payload": value[:500],
            "matched": len(matches),
        })

    return threats


def scan_request_data(data, source="request"):
    all_threats = []
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str):
                t = scan_input(val, source=f"{source}.{key}")
                all_threats.extend(t)
            elif isinstance(val, (dict, list)):
                all_threats.extend(scan_request_data(val, source=f"{source}.{key}"))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str):
                t = scan_input(item, source=f"{source}[{i}]")
                all_threats.extend(t)
            elif isinstance(item, (dict, list)):
                all_threats.extend(scan_request_data(item, source=f"{source}[{i}]"))
    elif isinstance(data, str):
        t = scan_input(data, source=source)
        all_threats.extend(t)
    return all_threats


def log_threat(threat_type, severity, ip_address, endpoint, username=None, payload=None, blocked=False):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.execute(
            "INSERT INTO threat_logs (threat_type, severity, ip_address, endpoint, username, payload, blocked) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (threat_type, severity, ip_address, endpoint, username, payload[:2000] if payload else None, 1 if blocked else 0)
        )
        conn.commit()
        conn.close()
    except:
        pass


def get_threats(limit=200, threat_type=None, severity=None, ip_address=None):
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM threat_logs WHERE 1=1"
        params = []
        if threat_type:
            query += " AND threat_type = ?"
            params.append(threat_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if ip_address:
            query += " AND ip_address = ?"
            params.append(ip_address)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except:
        return []


def get_threat_stats():
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) as cnt FROM threat_logs").fetchone()["cnt"]
        by_type = [dict(r) for r in conn.execute(
            "SELECT threat_type, COUNT(*) as cnt FROM threat_logs GROUP BY threat_type ORDER BY cnt DESC"
        ).fetchall()]
        by_severity = [dict(r) for r in conn.execute(
            "SELECT severity, COUNT(*) as cnt FROM threat_logs GROUP BY severity ORDER BY cnt DESC"
        ).fetchall()]
        by_ip = [dict(r) for r in conn.execute(
            "SELECT ip_address, COUNT(*) as cnt FROM threat_logs GROUP BY ip_address ORDER BY cnt DESC LIMIT 10"
        ).fetchall()]
        recent_blocked = conn.execute(
            "SELECT COUNT(*) as cnt FROM threat_logs WHERE blocked = 1 AND timestamp >= datetime('now', '-24 hours')"
        ).fetchone()["cnt"]
        conn.close()
        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_ip": by_ip,
            "recent_blocked_24h": recent_blocked,
        }
    except:
        return {"total": 0, "by_type": [], "by_severity": [], "by_ip": [], "recent_blocked_24h": 0}


def clear_threats():
    try:
        conn = sqlite3.connect(AUDIT_DB_PATH, timeout=15)
        conn.execute("DELETE FROM threat_logs")
        conn.commit()
        conn.close()
        return True
    except:
        return False


def scan_user_agent(user_agent):
    if not user_agent:
        return []
    threats = []
    detected, matches = _check_patterns(user_agent, SUSPICIOUS_UA_PATTERNS)
    if detected:
        threats.append({
            "type": "SUSPICIOUS_UA",
            "severity": "medium",
            "source": "User-Agent",
            "payload": user_agent[:500],
            "matched": len(matches),
        })
    return threats


init_auth_db()
init_audit_db()
