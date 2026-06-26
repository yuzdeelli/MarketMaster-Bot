# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from webapp.database import init_db, get_all_items, get_item_stats, get_item_stats_for_server, get_all_items_for_server, get_price_history, get_ohlc_data, get_db_stats, get_unique_servers, insert_prices_batch, get_all_item_names, cleanup_stale_listings
from webapp.analytics import get_full_analytics
from webapp.security import load_security, authenticate_user, register_user, check_ip_whitelist, verify_api_token, check_login_attempts, record_login_attempt, clear_login_attempts, check_session_timeout, change_password, log_audit_event, get_audit_logs, list_users, toggle_user_active, delete_user, is_admin_user, log_api_request, get_api_logs, clear_api_logs, get_api_log_stats, scan_request_data, scan_user_agent, log_threat, get_threats, get_threat_stats, clear_threats

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_secret_file = os.path.join(_project_root, ".flask_secret")
try:
    if os.path.exists(_secret_file):
        with open(_secret_file, "rb") as _f:
            app.secret_key = _f.read()
    else:
        sk = secrets.token_bytes(32)
        app.secret_key = sk
        with open(_secret_file, "wb") as _f:
            _f.write(sk)
except Exception:
    app.secret_key = secrets.token_bytes(32)

_rate_data = {}
_burst_data = {}
RATE_WINDOW = 6
BURST_THRESHOLD = 3
BURST_BLOCK_AFTER = 900
LOCAL_PROXIES = {"127.0.0.1", "::1", "192.168.1.102"}
IS_PYTHONANYWHERE = "PYTHONANYWHERE_DOMAIN" in os.environ


def _get_client_ip():
    remote = request.remote_addr or "127.0.0.1"
    if remote not in LOCAL_PROXIES:
        return remote
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return remote

_cache = {}
def cache_get(key, ttl=300):
    if key in _cache:
        val, ts = _cache[key]
        if time.time() - ts < ttl:
            return val
    return None
def cache_set(key, val):
    _cache[key] = (val, time.time())


def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf_token():
    token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
    if not token or token != session.get('_csrf_token'):
        return False
    return True


app.jinja_env.globals['csrf_token'] = generate_csrf_token


@app.before_request
def security_check():
    request._start_time = time.time()
    ip = _get_client_ip()

    if not check_ip_whitelist(ip):
        log_audit_event("IP_BLOCKED", ip_address=ip)
        return jsonify({"error": "IP engellendi"}), 403

    if request.path.startswith("/static"):
        return

    if request.endpoint in ("login_page", "login_post", "register_page", "static"):
        return

    now = time.time()

    is_local = ip.startswith("127.") or ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168.") or ip == "::1"

    if not is_local and not IS_PYTHONANYWHERE:
        now = time.time()
        if ip not in _rate_data:
            _rate_data[ip] = {"count": 1, "first": now}
        else:
            d = _rate_data[ip]
            if now - d["first"] > RATE_WINDOW:
                d["count"] = 1
                d["first"] = now
            else:
                d["count"] += 1

        if ip not in _burst_data:
            _burst_data[ip] = {"last": now, "fast_since": now}
        else:
            b = _burst_data[ip]
            gap = now - b["last"]
            b["last"] = now
            if gap < BURST_THRESHOLD:
                if now - b["fast_since"] >= BURST_BLOCK_AFTER:
                    log_audit_event("BURST_BLOCK", ip_address=ip)
                    return jsonify({"error": "10 dk boyunca surekli hizli istek - engellendi"}), 429
            else:
                b["fast_since"] = now

        if len(_burst_data) > 500:
            stale = [k for k, v in _burst_data.items() if now - v["last"] > 600]
            for k in stale:
                del _burst_data[k]

    # === THREAT DETECTION ===
    username = session.get("username") if session.get("logged_in") else None
    endpoint = request.endpoint or request.path

    ua_threats = scan_user_agent(request.headers.get("User-Agent", ""))
    for t in ua_threats:
        log_threat(t["type"], t["severity"], ip, endpoint, username, t["payload"], blocked=True)

    if request.path.startswith("/static"):
        return

    all_threats = []
    if request.args:
        all_threats.extend(scan_request_data(dict(request.args), source="query"))

    if request.is_json:
        try:
            json_data = request.get_json(silent=True)
            if json_data:
                all_threats.extend(scan_request_data(json_data, source="json"))
        except:
            pass

    if request.form:
        all_threats.extend(scan_request_data(dict(request.form), source="form"))

    for t in all_threats:
        log_threat(t["type"], t["severity"], ip, endpoint, username, t["payload"], blocked=False)

    if any(t["severity"] == "critical" for t in all_threats):
        return jsonify({"error": "Tehlikeli istek algilandi ve engellendi", "threats": [t["type"] for t in all_threats]}), 403

    if session.get("logged_in"):
        if not check_session_timeout(session):
            session.clear()
            log_audit_event("SESSION_TIMEOUT", username=session.get("username"), ip_address=ip)
            if request.path.startswith("/api/"):
                return jsonify({"error": "Oturum suresi doldu"}), 401
            return redirect(url_for("login_page"))

    if request.path.startswith("/api/push") or request.path == "/api/live":
        if request.path.startswith("/api/push"):
            token = request.headers.get("X-API-Token", "")
            if not verify_api_token(token):
                return jsonify({"error": "Unauthorized"}), 401
        return

    if request.path.startswith("/api/"):
        if not session.get("logged_in"):
            public_apis = ("/api/items", "/api/ohlc/", "/api/stats", "/api/servers", "/api/top-items", "/api/live", "/api/item/", "/api/analytics/", "/api/search", "/api/autocomplete", "/api/price-changes", "/api/endeks-data", "/api/analiz/", "/endeks")
            is_public = any(request.path.startswith(p) for p in public_apis)
            if not is_public:
                token = request.headers.get("X-API-Token", "")
                if not verify_api_token(token):
                    return jsonify({"error": "Unauthorized"}), 401

    if request.method == "POST" and request.path not in ("/login", "/api/push", "/api/search") and not request.path.startswith("/api/admin/"):
        if not validate_csrf_token():
            return jsonify({"error": "CSRF token gecersiz"}), 403


@app.after_request
def security_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


@app.after_request
def log_api(response):
    if request.path.startswith("/static"):
        return response
    ip = _get_client_ip()
    username = session.get("username") if session.get("logged_in") else None
    endpoint = request.endpoint or request.path
    response_time_ms = int((time.time() - getattr(request, '_start_time', time.time())) * 1000)
    log_api_request(
        method=request.method,
        endpoint=endpoint,
        ip_address=ip,
        status_code=response.status_code,
        username=username,
        response_time_ms=response_time_ms,
    )
    return response


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        ip = request.remote_addr or "127.0.0.1"
        if not check_login_attempts(ip):
            return render_template("login.html", error="Cok fazla deneme. 15 dakika bekleyin.")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        success, user_data = authenticate_user(username, password)
        if success:
            session_data = {
                "logged_in": True,
                "user_id": user_data["id"],
                "username": user_data["username"],
                "login_time": datetime.now().isoformat(),
                "ip": ip,
            }
            session.clear()
            session.update(session_data)
            session.permanent = True
            clear_login_attempts(ip)
            return redirect(url_for("dashboard"))
        else:
            record_login_attempt(ip)
            return render_template("login.html", error="Hatali kullanici adi veya sifre!")

    return render_template("login.html", error=None)


@app.route("/register", methods=["GET", "POST"])
def register_page():
    from webapp.security import load_security
    sec = load_security()
    if not sec.get("registration_enabled", False):
        return render_template("register.html", error="Kayit sistemi su an kapali."), 403

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if password != password2:
            return render_template("register.html", error="Sifreler eslesmiyor!")

        success, message = register_user(username, password)
        if success:
            return render_template("register.html", success="Kayit basarili! Giris yapabilirsiniz.")
        else:
            return render_template("register.html", error=message)

    return render_template("register.html", error=None, success=None)


@app.route("/logout")
def logout_page():
    log_audit_event("LOGOUT", username=session.get("username"), ip_address=request.remote_addr)
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        new_password2 = request.form.get("new_password2", "")

        if new_password != new_password2:
            return render_template("change_password.html", error="Yeni sifreler eslesmiyor!")

        success, message = change_password(session["username"], old_password, new_password)
        if success:
            return render_template("change_password.html", success="Sifre degistirildi!")
        else:
            return render_template("change_password.html", error=message)

    return render_template("change_password.html", error=None, success=None)


@app.route("/api/push", methods=["POST"])
def api_push():
    data = request.get_json(silent=True)
    if not data or "prices" not in data:
        return jsonify({"error": "prices array required"}), 400
    prices = data["prices"]
    if not isinstance(prices, list) or len(prices) == 0:
        return jsonify({"error": "empty prices"}), 400
    if len(prices) > 1000:
        return jsonify({"error": "Cok fazla veri (max 1000)"}), 400
    validated = []
    for p in prices:
        if not isinstance(p, dict):
            continue
        item = p.get("item", "").strip()
        ptype = p.get("type", "").strip().lower()
        if not item or ptype not in ("buy", "sell"):
            continue
        try:
            price = int(p["price"])
            if price <= 0 or price > 999999999:
                continue
        except (ValueError, TypeError, KeyError):
            continue
        validated.append({
            "item": item,
            "lvl": p.get("lvl", "").strip(),
            "price": price,
            "type": ptype,
            "server": p.get("server", "").strip(),
            "seller": p.get("seller", "").strip(),
        })
    if not validated:
        return jsonify({"error": "Gecerli veri yok"}), 400
    insert_prices_batch(validated)
    return jsonify({"ok": True, "inserted": len(validated)})


@app.route("/api/items")
def api_items():
    server = request.args.get("server", "")
    if server:
        items = get_all_items_for_server(server)
    else:
        items = get_all_items()
    result = []
    for it in items:
        if server:
            stats = get_item_stats_for_server(it["item"], it["lvl"], server)
        else:
            stats = get_item_stats(it["item"], it["lvl"])
        result.append({
            "item": it["item"],
            "lvl": it["lvl"],
            "buy_min": stats["buy"]["min"] if stats and stats.get("buy") else None,
            "buy_med": stats["buy"]["median"] if stats and stats.get("buy") else None,
            "buy_max": stats["buy"]["max"] if stats and stats.get("buy") else None,
            "sell_min": stats["sell"]["min"] if stats and stats.get("sell") else None,
            "sell_med": stats["sell"]["median"] if stats and stats.get("sell") else None,
            "sell_max": stats["sell"]["max"] if stats and stats.get("sell") else None,
        })
    result.sort(key=lambda x: x["sell_max"] or 0, reverse=True)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    start = (page - 1) * per_page
    end = start + per_page
    return jsonify({"count": len(result), "items": result[start:end]})


@app.route("/api/item/<path:item>")
def api_item_detail(item):
    lvl = request.args.get("lvl", "")
    lvl = lvl.replace(" ", "").replace("(", "").replace(")", "").strip()
    if lvl == "0" or lvl == "+0" or lvl == "":
        lvl = "+0"
    elif not lvl.startswith("+"):
        lvl = "+" + lvl
    lvl = lvl.replace(" ", "")
    stats = get_item_stats(item, lvl)
    prices = get_price_history(item, lvl, limit=200)
    analytics = get_full_analytics(item, lvl)
    return jsonify({
        "item": item,
        "lvl": lvl,
        "stats": stats,
        "analytics": analytics,
        "prices": prices,
        "price_count": len(prices),
    })


@app.route("/api/ohlc/<path:item>")
def api_ohlc(item):
    lvl = request.args.get("lvl", "")
    lvl = lvl.replace(" ", "").replace("(", "").replace(")", "").strip()
    if lvl == "0" or lvl == "+0" or lvl == "":
        lvl = "+0"
    elif not lvl.startswith("+"):
        lvl = "+" + lvl
    lvl = lvl.replace(" ", "")
    interval = request.args.get("interval", "auto")
    limit = request.args.get("limit", 500, type=int)
    server = request.args.get("server", "").strip() or None
    ptype = request.args.get("type", "sell").strip() or "sell"
    if interval == "all":
        ohlc = get_ohlc_data(item, lvl, "auto", limit=2000, server=server, ptype=ptype)
    else:
        ohlc = get_ohlc_data(item, lvl, interval, limit, server=server, ptype=ptype)
    return jsonify({"item": item, "lvl": lvl, "interval": interval, "ohlc": ohlc, "count": len(ohlc)})


@app.route("/api/live_analysis/<path:item>")
def api_live_analysis(item):
    """Sunucu tarafindaki tum indicator hesaplamalarini yapar, tek seferde doner.
    Params: lvl, server, type, hours (varsayilan 24)
    """
    from webapp.indicators import compute_all_indicators
    lvl = request.args.get("lvl", "")
    lvl = lvl.replace(" ", "").replace("(", "").replace(")", "").strip()
    if lvl == "0" or lvl == "+0" or lvl == "":
        lvl = "+0"
    elif not lvl.startswith("+"):
        lvl = "+" + lvl
    lvl = lvl.replace(" ", "")
    server = request.args.get("server", "").strip() or None
    ptype = request.args.get("type", "sell").strip() or "sell"
    hours = request.args.get("hours", 24, type=int)

    ohlc = get_ohlc_data(item, lvl, "auto", limit=2000, server=server, ptype=ptype)

    if not ohlc:
        return jsonify({"item": item, "lvl": lvl, "count": 0, "error": "Veri bulunamadi"})

    result = compute_all_indicators(ohlc)
    result["item"] = item
    result["lvl"] = lvl
    result["ohlc"] = ohlc
    return jsonify(result)


@app.route("/api/servers")
def api_servers():
    return jsonify({"servers": get_unique_servers()})


@app.route("/api/items/names")
def api_item_names():
    names = get_all_item_names()
    return jsonify({"names": names, "count": len(names)})


@app.route("/api/stats")
def api_stats():
    return jsonify(get_db_stats())


@app.route("/api/top-items")
def api_top_items():
    from webapp.database import get_db
    limit = request.args.get("limit", 20, type=int)
    with get_db() as db:
        rows = db.execute("""
            SELECT item_name, item_lvl, COUNT(*) as cnt,
                   SUM(CASE WHEN type='sell' THEN 1 ELSE 0 END) as sell_cnt,
                   SUM(CASE WHEN type='buy' THEN 1 ELSE 0 END) as buy_cnt
            FROM prices
            GROUP BY item_name, item_lvl
            ORDER BY cnt DESC
            LIMIT ?
        """, (limit,)).fetchall()
        items = []
        for r in rows:
            stats = get_item_stats(r["item_name"], r["item_lvl"])
            sell_med = stats["sell"]["median"] if stats and stats.get("sell") else 0
            buy_med = stats["buy"]["median"] if stats and stats.get("buy") else 0
            profit = int(sell_med * 0.97 - buy_med) if sell_med > 0 and buy_med > 0 else 0
            items.append({
                "item": r["item_name"],
                "lvl": r["item_lvl"],
                "count": r["cnt"],
                "sell_med": sell_med,
                "buy_med": buy_med,
                "profit": profit,
            })
    return jsonify({"items": items, "count": len(items)})


@app.route("/api/price-changes")
def api_price_changes():
    from webapp.database import get_db
    HOURS = 24
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    prev_cutoff = (now - timedelta(hours=HOURS * 2)).strftime("%Y-%m-%d %H:%M:%S")
    changes = {}
    with get_db() as db:
        items = db.execute("SELECT DISTINCT item_name AS item, item_lvl AS lvl FROM prices WHERE timestamp >= ?", (prev_cutoff,)).fetchall()
        for item_name, lvl in items:
            for ptype in ("buy", "sell"):
                recent = db.execute(
                    "SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)=? AND timestamp >= ?",
                    (item_name, lvl, ptype, cutoff),
                ).fetchall()
                previous = db.execute(
                    "SELECT price FROM prices WHERE item_name=? AND item_lvl=? AND LOWER(type)=? AND timestamp >= ? AND timestamp < ?",
                    (item_name, lvl, ptype, prev_cutoff, cutoff),
                ).fetchall()
                recent_prices = [r[0] for r in recent]
                previous_prices = [r[0] for r in previous]
                if not recent_prices and not previous_prices:
                    continue
                def median(vals):
                    if not vals:
                        return 0
                    s = sorted(vals)
                    n = len(s)
                    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2
                recent_med = median(recent_prices)
                previous_med = median(previous_prices)
                change_pct = 0
                if previous_med > 0 and recent_med > 0:
                    change_pct = round((recent_med - previous_med) / previous_med * 100, 1)
                elif recent_med > 0:
                    change_pct = 100.0
                key = f"{item_name}|{lvl}"
                if key not in changes:
                    changes[key] = {"sell_change": 0, "current": 0, "previous": 0}
                if ptype == "sell":
                    changes[key]["sell_change"] = change_pct
                    changes[key]["current"] = recent_med
                    changes[key]["previous"] = previous_med
    return jsonify(changes)


@app.route("/api/tech-summary")
def api_tech_summary():
    items = get_all_items()
    results = []
    for it in items:
        item_name = it["item"]
        lvl = it["lvl"]
        prices = get_price_history(item_name, lvl, limit=200)
        if not prices or len(prices) < 5:
            continue
        sell_prices = [p["price"] for p in prices if p.get("type", "").lower() == "sell"]
        all_prices = [p["price"] for p in prices]
        if len(sell_prices) < 5:
            sell_prices = all_prices
        rsi_val = None
        macd_signal = None
        ema_signal = None
        bb_signal = None
        sentiment = 50
        if len(sell_prices) >= 15:
            from webapp.analytics import rsi as calc_rsi
            rsi_val = calc_rsi([{"price": p} for p in sell_prices], 14)
        if len(all_prices) >= 26:
            ema_fast = _calc_ema(all_prices, 9)
            ema_slow = _calc_ema(all_prices, 21)
            if ema_fast is not None and ema_slow is not None:
                ema_signal = "buy" if ema_fast > ema_slow else "sell"
            macd_line, signal_line = _calc_macd(all_prices)
            if macd_line is not None and signal_line is not None:
                macd_signal = "buy" if macd_line > signal_line else "sell"
        if len(all_prices) >= 20:
            sma20 = sum(all_prices[:20]) / 20
            std20 = (sum((p - sma20) ** 2 for p in all_prices[:20]) / 20) ** 0.5
            last_price = all_prices[0]
            upper = sma20 + 2 * std20
            lower = sma20 - 2 * std20
            if last_price >= upper:
                bb_signal = "sell"
            elif last_price <= lower:
                bb_signal = "buy"
            else:
                bb_signal = "neutral"
        signals = [s for s in [rsi_signal_from_val(rsi_val), macd_signal, ema_signal, bb_signal] if s]
        buy_count = signals.count("buy")
        sell_count = signals.count("sell")
        if buy_count > sell_count:
            sentiment = 60 + min(20, (buy_count - sell_count) * 10)
        elif sell_count > buy_count:
            sentiment = 40 - min(20, (sell_count - buy_count) * 10)
        else:
            sentiment = 50
        results.append({
            "item": item_name, "lvl": lvl,
            "rsi": rsi_val, "macd": macd_signal, "ema": ema_signal,
            "bollinger": bb_signal, "sentiment": sentiment,
        })
    buy_total = sum(1 for r in results if r["sentiment"] > 55)
    sell_total = sum(1 for r in results if r["sentiment"] < 45)
    neutral_total = len(results) - buy_total - sell_total
    avg_sentiment = sum(r["sentiment"] for r in results) / max(1, len(results))
    return jsonify({
        "items": results,
        "summary": {
            "buy_signals": buy_total, "sell_signals": sell_total,
            "neutral_signals": neutral_total, "avg_sentiment": round(avg_sentiment, 1),
            "total": len(results),
        },
    })


def rsi_signal_from_val(rsi_val):
    if rsi_val is None:
        return None
    if rsi_val > 70:
        return "sell"
    if rsi_val < 30:
        return "buy"
    return "neutral"


def _calc_ema(prices, period):
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def _calc_macd(prices):
    if len(prices) < 26:
        return None, None
    ema12 = _calc_ema(prices, 12)
    ema26 = _calc_ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None
    macd_line = ema12 - ema26
    signal_line = macd_line * 0.8
    return macd_line, signal_line


# ---- PAGES ---- #

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    from webapp.database import get_db, get_db_stats
    stats = get_db_stats()
    server = request.args.get("server", "ZERO").strip()
    cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    now = datetime.utcnow()

    with get_db() as db:
        if server:
            rows = db.execute("""
                SELECT item_name, item_lvl, price,
                       MAX(last_seen) OVER (PARTITION BY item_name, item_lvl) as latest_seen,
                       type
                FROM prices
                WHERE item_lvl IS NOT NULL AND TRIM(item_lvl) != ''
                  AND LOWER(TRIM(server)) LIKE LOWER(?)
                  AND last_seen >= ?
                ORDER BY item_name, item_lvl, price
            """, (f"%{server}%", cutoff_24h)).fetchall()
        else:
            rows = db.execute("""
                SELECT item_name, item_lvl, price,
                       MAX(last_seen) OVER (PARTITION BY item_name, item_lvl) as latest_seen,
                       type
                FROM prices
                WHERE item_lvl IS NOT NULL AND TRIM(item_lvl) != ''
                  AND last_seen >= ?
                ORDER BY item_name, item_lvl, price
            """, (cutoff_24h,)).fetchall()

        item_data = defaultdict(lambda: {"sell_prices": [], "buy_prices": [], "latest": ""})
        for r in rows:
            key = (r["item_name"], r["item_lvl"])
            if r["type"] and r["type"].lower() == "sell":
                item_data[key]["sell_prices"].append(r["price"])
            elif r["type"] and r["type"].lower() == "buy":
                item_data[key]["buy_prices"].append(r["price"])
            if r["latest_seen"] and r["latest_seen"] > item_data[key]["latest"]:
                item_data[key]["latest"] = r["latest_seen"]

        def median(arr):
            if not arr: return 0
            arr = sorted(arr)
            n = len(arr)
            if n % 2 == 1:
                return arr[n // 2]
            return (arr[n // 2 - 1] + arr[n // 2]) // 2

        def calc_hours_ago(latest):
            is_active = False
            hours_ago = 999
            if latest:
                try:
                    seen_dt = datetime.strptime(latest, "%Y-%m-%d %H:%M:%S")
                    hours_ago = (now - seen_dt).total_seconds() / 3600
                    is_active = hours_ago < 24
                except:
                    is_active = True
                    hours_ago = 0
            return is_active, round(hours_ago, 1)

        top_items = []
        for (name, lvl), data in item_data.items():
            sell_med = median(data["sell_prices"])
            buy_med = median(data["buy_prices"])
            if sell_med <= 0: continue
            sc = len(data["sell_prices"])
            profit = int(sell_med * 0.97 - buy_med) if buy_med > 0 else 0
            is_active, hours_ago = calc_hours_ago(data["latest"])
            top_items.append({"item": name, "lvl": lvl, "count": sc, "sell_med": sell_med, "buy_med": buy_med, "profit": profit, "is_active": is_active, "hours_ago": hours_ago})
        top_items.sort(key=lambda x: x["sell_med"], reverse=True)
        top_items = top_items[:50]

        high_rows = db.execute("""
            SELECT item_name, item_lvl, price, type, last_seen FROM prices
            WHERE item_lvl IS NOT NULL AND TRIM(item_lvl) != ''
              AND LOWER(TRIM(server)) LIKE LOWER(?)
              AND (item_lvl LIKE '%+8%' OR item_lvl LIKE '%+5R%' OR item_lvl LIKE '%+6R%' OR item_lvl LIKE '%+7R%')
            ORDER BY item_name, item_lvl, price
        """, (f"%{server}%",)).fetchall()
        high_data = defaultdict(lambda: {"sell_prices": [], "buy_prices": [], "latest": ""})
        for r in high_rows:
            key = (r["item_name"], r["item_lvl"])
            if r["type"] and r["type"].lower() == "sell": high_data[key]["sell_prices"].append(r["price"])
            elif r["type"] and r["type"].lower() == "buy": high_data[key]["buy_prices"].append(r["price"])
            if r["last_seen"] and r["last_seen"] > high_data[key]["latest"]: high_data[key]["latest"] = r["last_seen"]
        high_items = []
        for (name, lvl), data in high_data.items():
            sell_med = median(data["sell_prices"])
            buy_med = median(data["buy_prices"])
            if sell_med <= 0: continue
            is_active, hours_ago = calc_hours_ago(data["latest"])
            high_items.append({"item": name, "lvl": lvl, "count": len(data["sell_prices"]), "sell_med": sell_med, "buy_med": buy_med, "profit": int(sell_med * 0.97 - buy_med) if buy_med > 0 else 0, "is_active": is_active, "hours_ago": hours_ago})
        high_items.sort(key=lambda x: x["sell_med"], reverse=True)

        mid_rows = db.execute("""
            SELECT item_name, item_lvl, price, type, last_seen FROM prices
            WHERE item_lvl IS NOT NULL AND TRIM(item_lvl) != ''
              AND LOWER(TRIM(server)) LIKE LOWER(?)
              AND (item_lvl LIKE '%+7%' OR item_lvl LIKE '%+1R%' OR item_lvl LIKE '%+2R%' OR item_lvl LIKE '%+3R%' OR item_lvl LIKE '%+4R%')
            ORDER BY item_name, item_lvl, price
        """, (f"%{server}%",)).fetchall()
        mid_data = defaultdict(lambda: {"sell_prices": [], "buy_prices": [], "latest": ""})
        for r in mid_rows:
            key = (r["item_name"], r["item_lvl"])
            if r["type"] and r["type"].lower() == "sell": mid_data[key]["sell_prices"].append(r["price"])
            elif r["type"] and r["type"].lower() == "buy": mid_data[key]["buy_prices"].append(r["price"])
            if r["last_seen"] and r["last_seen"] > mid_data[key]["latest"]: mid_data[key]["latest"] = r["last_seen"]
        mid_items = []
        for (name, lvl), data in mid_data.items():
            sell_med = median(data["sell_prices"])
            buy_med = median(data["buy_prices"])
            if sell_med <= 0: continue
            is_active, hours_ago = calc_hours_ago(data["latest"])
            mid_items.append({"item": name, "lvl": lvl, "count": len(data["sell_prices"]), "sell_med": sell_med, "buy_med": buy_med, "profit": int(sell_med * 0.97 - buy_med) if buy_med > 0 else 0, "is_active": is_active, "hours_ago": hours_ago})
        mid_items.sort(key=lambda x: x["sell_med"], reverse=True)

        vol_rows = db.execute("""
            SELECT item_name, item_lvl, price, type, last_seen FROM prices
            WHERE item_lvl IS NOT NULL AND TRIM(item_lvl) != ''
              AND LOWER(TRIM(server)) LIKE LOWER(?)
            ORDER BY item_name, item_lvl, price
        """, (f"%{server}%",)).fetchall()
        vol_data = defaultdict(lambda: {"sell_prices": [], "buy_prices": [], "latest": ""})
        for r in vol_rows:
            key = (r["item_name"], r["item_lvl"])
            if r["type"] and r["type"].lower() == "sell": vol_data[key]["sell_prices"].append(r["price"])
            elif r["type"] and r["type"].lower() == "buy": vol_data[key]["buy_prices"].append(r["price"])
            if r["last_seen"] and r["last_seen"] > vol_data[key]["latest"]: vol_data[key]["latest"] = r["last_seen"]
        vol_items = []
        for (name, lvl), data in vol_data.items():
            sell_med = median(data["sell_prices"])
            buy_med = median(data["buy_prices"])
            total_listings = len(data["sell_prices"]) + len(data["buy_prices"])
            if sell_med <= 0 and buy_med <= 0: continue
            is_active, hours_ago = calc_hours_ago(data["latest"])
            vol_items.append({"name": name, "lvl": lvl, "count": total_listings, "sell": sell_med, "buy": buy_med, "profit": int(sell_med * 0.97 - buy_med) if sell_med > 0 and buy_med > 0 else 0, "active": is_active, "hours": hours_ago})
        vol_items.sort(key=lambda x: x["count"], reverse=True)
        vol_items = vol_items[:50]

    from webapp.database import get_all_item_names
    all_items = get_all_item_names()

    return render_template("dashboard.html", top_items=top_items, high_items=high_items, mid_items=mid_items, vol_items=vol_items, stats=stats, current_server=server, ticker_items=[], all_items=all_items)


@app.route("/item")
def item_index():
    from webapp.database import get_all_item_names
    all_items = get_all_item_names()
    return render_template("item_index.html", all_items=all_items)


@app.route("/item/<path:item>")
def item_detail(item):
    from webapp.database import get_db, get_all_item_names
    server = request.args.get("server", "").strip()
    lvl = request.args.get("lvl", "")
    lvl = lvl.replace(" ", "").replace("(", "").replace(")", "").strip()
    if lvl == "0" or lvl == "+0" or lvl == "":
        lvl = "+0"
    elif not lvl.startswith("+") and not lvl.lower().endswith("r"):
        lvl = "+" + lvl
    elif not lvl.startswith("+") and lvl.lower().endswith("r"):
        lvl = "+" + lvl
    lvl = lvl.replace(" ", "")

    all_items = get_all_item_names()
    item_lower = item.lower()
    matched = item
    for name in all_items:
        if name.lower() == item_lower:
            matched = name
            break

    stats = get_item_stats(matched, lvl)
    analytics = get_full_analytics(matched, lvl)
    prices = get_price_history(matched, lvl, limit=200)

    sell_prices = [p["price"] for p in prices if p.get("type") == "sell" and p.get("price")]
    buy_prices = [p["price"] for p in prices if p.get("type") == "buy" and p.get("price")]
    if len(sell_prices) >= 2:
        recent = sell_prices[-1]
        previous = sell_prices[-2]
        analytics["change_pct"] = round((recent - previous) / previous * 100, 1) if previous > 0 else 0
    else:
        analytics["change_pct"] = 0

    analytics["sell_vol"] = len(sell_prices)
    analytics["buy_vol"] = len(buy_prices)
    analytics["total_vol"] = len(sell_prices) + len(buy_prices)

    with get_db() as db:
        seller_rows = db.execute(
            """SELECT seller, COUNT(*) as cnt FROM prices
               WHERE item_name=? AND item_lvl=? AND LOWER(type)='sell' AND seller IS NOT NULL AND seller != ''
               GROUP BY seller""", (item, lvl)
        ).fetchall()
    analytics["seller_count"] = len(seller_rows)
    analytics["top_seller_cnt"] = seller_rows[0]["cnt"] if seller_rows else 0

    if len(sell_prices) >= 10:
        recent_5 = sell_prices[-5:]
        prev_5 = sell_prices[-10:-5]
        avg_recent = sum(recent_5) / 5
        avg_prev = sum(prev_5) / 5
        momentum = round((avg_recent - avg_prev) / avg_prev * 100, 1) if avg_prev > 0 else 0
    elif len(sell_prices) >= 2:
        momentum = analytics["change_pct"]
    else:
        momentum = 0
    analytics["momentum"] = momentum

    rsi_val = analytics.get("rsi_sell")
    if rsi_val is not None and momentum != 0:
        if rsi_val < 30 and momentum < -2:
            buy_signal, buy_signal_color = "SATIN AL", "#26a69a"
        elif rsi_val < 40 and momentum < 0:
            buy_signal, buy_signal_color = "BEKLE", "#ff9800"
        elif rsi_val > 70 and momentum > 2:
            buy_signal, buy_signal_color = "BEKLE", "#ff9800"
        elif rsi_val > 80:
            buy_signal, buy_signal_color = "SAT", "#ef5350"
        else:
            buy_signal, buy_signal_color = "NOTRAL", "#787b86"
    else:
        buy_signal, buy_signal_color = "YETERSIZ VERI", "#787b86"
    analytics["buy_signal"] = buy_signal
    analytics["buy_signal_color"] = buy_signal_color

    with get_db() as db:
        rows = db.execute("SELECT item_lvl AS lvl, COUNT(*) as cnt FROM prices WHERE item_name=? GROUP BY item_lvl", (matched,)).fetchall()
    lvl_map = {}
    for r in rows:
        raw = (r["lvl"] or "").strip()
        norm = "+0" if raw in ("", "0", "+0") else raw
        lvl_map[norm] = lvl_map.get(norm, 0) + r["cnt"]
    all_levels = [{"lvl": k, "cnt": v} for k, v in lvl_map.items()]

    def _lvl_sort_key(lv):
        l = lv["lvl"] or "+0"
        is_rev = l.upper().endswith("R")
        try:
            num = int(l.rstrip("Rr+"))
        except ValueError:
            num = 0
        return (1 if is_rev else 0, num, l)
    all_levels.sort(key=_lvl_sort_key)

    from webapp.database import get_all_item_names
    all_items = get_all_item_names()

    return render_template("item.html", item=matched, item_name=matched, lvl=lvl, stats=stats, analytics=analytics, prices=prices, all_levels=all_levels, current_server=server, all_items=all_items)


@app.route("/admin/users")
def admin_users():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    if not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    users = list_users()
    return render_template("admin_users.html", users=users)


@app.route("/admin/user/toggle", methods=["POST"])
def admin_toggle_user():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    if not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    username = request.form.get("username", "")
    if username != session.get("username"):
        toggle_user_active(username)
    return redirect(url_for("admin_users"))


@app.route("/admin/user/delete", methods=["POST"])
def admin_delete_user():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    if not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    username = request.form.get("username", "")
    if username != session.get("username"):
        delete_user(username)
    return redirect(url_for("admin_users"))


@app.route("/admin/audit")
def admin_audit():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    if not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    event_type = request.args.get("type", "")
    logs = get_audit_logs(limit=200, event_type=event_type if event_type else None)
    return render_template("admin_audit.html", logs=logs, event_type=event_type)


# ---- ADMIN API: API LOGS ---- #
@app.route("/api/admin/api-logs")
def admin_api_logs():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    limit = request.args.get("limit", 200, type=int)
    method = request.args.get("method", "")
    endpoint = request.args.get("endpoint", "")
    ip = request.args.get("ip", "")
    logs = get_api_logs(limit=limit, method=method or None, endpoint=endpoint or None, ip_address=ip or None)
    return jsonify({"logs": logs, "count": len(logs)})


@app.route("/api/admin/api-logs/stats")
def admin_api_log_stats():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    return jsonify(get_api_log_stats())


@app.route("/api/admin/api-logs/clear", methods=["POST"])
def admin_api_logs_clear():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    clear_api_logs()
    return jsonify({"ok": True})


# ---- ADMIN API: USER PERMISSIONS ---- #
@app.route("/api/admin/users")
def admin_api_users():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    users = list_users()
    return jsonify({"users": users})


@app.route("/api/admin/users/<int:user_id>/admin", methods=["POST"])
def admin_api_toggle_admin(user_id):
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    from webapp.security import get_auth_db
    conn = get_auth_db()
    user = conn.execute("SELECT username, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Kullanici bulunamadi"}), 404
    if user["username"] == session.get("username"):
        conn.close()
        return jsonify({"error": "Kendi admin yetkinizi degistiremezsiniz"}), 400
    new_val = 0 if user["is_admin"] else 1
    conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (new_val, user_id))
    conn.commit()
    conn.close()
    log_audit_event("ADMIN_TOGGLED", username=session.get("username"), details=f"{user['username']}: admin={'acik' if new_val else 'kapali'}")
    return jsonify({"ok": True, "is_admin": new_val})


@app.route("/api/admin/users/<int:user_id>/active", methods=["POST"])
def admin_api_toggle_active(user_id):
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    from webapp.security import get_auth_db
    conn = get_auth_db()
    user = conn.execute("SELECT username, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Kullanici bulunamadi"}), 404
    if user["username"] == session.get("username"):
        conn.close()
        return jsonify({"error": "Kendi hesabinizi devre disi birakamazsiniz"}), 400
    new_val = 0 if user["is_active"] else 1
    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_val, user_id))
    conn.commit()
    conn.close()
    log_audit_event("USER_TOGGLED", username=session.get("username"), details=f"{user['username']}: aktif={'acik' if new_val else 'kapali'}")
    return jsonify({"ok": True, "is_active": new_val})


@app.route("/api/admin/users/<int:user_id>/delete", methods=["POST"])
def admin_api_delete_user(user_id):
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    from webapp.security import get_auth_db
    conn = get_auth_db()
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Kullanici bulunamadi"}), 404
    if user["username"] == session.get("username"):
        conn.close()
        return jsonify({"error": "Kendi hesabinizi silemezsiniz"}), 400
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    log_audit_event("USER_DELETED", username=session.get("username"), details=f"{user['username']} silindi")
    return jsonify({"ok": True})


# ---- ADMIN API: THREAT DETECTION ---- #
@app.route("/api/admin/threats")
def admin_threats():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    limit = request.args.get("limit", 200, type=int)
    threat_type = request.args.get("type", "")
    severity = request.args.get("severity", "")
    ip = request.args.get("ip", "")
    threats = get_threats(limit=limit, threat_type=threat_type or None, severity=severity or None, ip_address=ip or None)
    return jsonify({"threats": threats, "count": len(threats)})


@app.route("/api/admin/threats/stats")
def admin_threat_stats():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    return jsonify(get_threat_stats())


@app.route("/api/admin/threats/clear", methods=["POST"])
def admin_threats_clear():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    clear_threats()
    return jsonify({"ok": True})


@app.route("/api/admin/settings", methods=["GET"])
def admin_settings_get():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    sec = load_security()
    return jsonify({
        "ip_whitelist_enabled": sec.get("ip_whitelist_enabled", False),
        "ip_whitelist": sec.get("ip_whitelist", []),
        "registration_enabled": sec.get("registration_enabled", False),
        "max_login_attempts": sec.get("max_login_attempts", 5),
        "lockout_minutes": sec.get("lockout_minutes", 15),
    })


@app.route("/api/admin/settings", methods=["POST"])
def admin_settings_post():
    if not session.get("logged_in") or not is_admin_user(session.get("username", "")):
        return jsonify({"error": "Yetkiniz yok"}), 403
    data = request.get_json(silent=True) or {}
    sec = load_security()
    for key in ("ip_whitelist_enabled", "ip_whitelist", "registration_enabled", "max_login_attempts", "lockout_minutes"):
        if key in data:
            sec[key] = data[key]
    import json
    sec_path = os.path.join(_project_root, "security.json")
    with open(sec_path, "w", encoding="utf-8") as f:
        json.dump(sec, f, indent=2, ensure_ascii=False)
    return jsonify({"ok": True})


@app.route("/api/live")
def api_live():
    from webapp.database import get_db
    server = request.args.get("server", "").strip()
    limit = request.args.get("limit", 50, type=int)
    with get_db() as db:
        query = """
            SELECT item_name, item_lvl, price, type, server, timestamp, seller,
                   MAX(id) OVER (PARTITION BY item_name, item_lvl, type, server) as max_id
            FROM prices
        """
        params = []
        if server:
            query += " WHERE LOWER(TRIM(server)) LIKE LOWER(?)"
            params.append(f"%{server}%")
        query += " ORDER BY id DESC"
        rows = db.execute(query, params).fetchall()

        seen = set()
        latest = []
        for r in rows:
            key = f"{r['item_name']}|{r['item_lvl']}|{r['type']}|{r['server']}"
            if key not in seen:
                seen.add(key)
                latest.append(dict(r))
            if len(latest) >= limit:
                break

        prev_query = """
            SELECT item_name, item_lvl, type, server,
                   AVG(price) as avg_price, COUNT(*) as cnt
            FROM prices
            WHERE timestamp >= datetime('now', '-2 hour') AND timestamp < datetime('now', '-1 hour')
        """
        if server:
            prev_query += " AND LOWER(TRIM(server)) LIKE LOWER(?)"
            prev_params = [f"%{server}%"]
        else:
            prev_params = []
        prev_query += " GROUP BY item_name, item_lvl, type, server"
        prev_rows = db.execute(prev_query, prev_params).fetchall()
        prev_map = {}
        for p in prev_rows:
            k = f"{p['item_name']}|{p['item_lvl']}|{p['type']}|{p['server']}"
            prev_map[k] = p['avg_price']

        curr_query = """
            SELECT item_name, item_lvl, type, server,
                   AVG(price) as avg_price, COUNT(*) as cnt
            FROM prices
            WHERE timestamp >= datetime('now', '-1 hour')
        """
        if server:
            curr_query += " AND LOWER(TRIM(server)) LIKE LOWER(?)"
            curr_params = [f"%{server}%"]
        else:
            curr_params = []
        curr_query += " GROUP BY item_name, item_lvl, type, server"
        curr_rows = db.execute(curr_query, curr_params).fetchall()
        curr_map = {}
        for c in curr_rows:
            k = f"{c['item_name']}|{c['item_lvl']}|{c['type']}|{c['server']}"
            curr_map[k] = c['avg_price']

        changes = []
        for item in latest:
            key = f"{item['item_name']}|{item['item_lvl']}|{item['type']}|{item['server']}"
            prev = prev_map.get(key)
            curr = curr_map.get(key)
            if prev and curr and prev > 0:
                pct = ((curr - prev) / prev) * 100
                item['change_pct'] = round(pct, 2)
                item['prev_price'] = round(prev)
            else:
                item['change_pct'] = 0
                item['prev_price'] = 0

        stats = db.execute("SELECT COUNT(*) as total, MAX(timestamp) as last_update FROM prices").fetchone()
        servers = db.execute("SELECT DISTINCT server FROM prices ORDER BY server").fetchall()

    return jsonify({
        "items": latest,
        "total": stats['total'] if stats else 0,
        "last_update": stats['last_update'] if stats else "",
        "servers": [s['server'] for s in servers],
    })


@app.route("/api/search", methods=["POST"])
def api_search():
    from webapp.database import search_items
    data = request.get_json(silent=True) or {}
    q = (data.get("item") or "").strip()
    if len(q) < 1:
        return jsonify({"ok": False, "error": "En az 1 harf girin"})
    results = search_items(q)
    return jsonify({"ok": True, "results": results[:30]})


@app.route("/api/autocomplete")
def api_autocomplete():
    from webapp.database import get_all_item_names
    q = request.args.get("q", "").strip().lower()
    if len(q) < 1:
        return jsonify({"items": []})
    all_items = get_all_item_names()
    matched = [i for i in all_items if q in i.lower()]
    matched.sort(key=lambda x: (not x.lower().startswith(q), x.lower()))
    return jsonify({"items": matched[:20]})


@app.route("/api/analytics/all")
def api_analytics_all():
    from core.analytics import DataFrameAnalytics
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_data.db")
    a = DataFrameAnalytics(db_path)
    server = request.args.get("server", "").strip() or None
    server2 = request.args.get("server2", "").strip() or None
    result = a.all(server)
    result["arbitrage"] = a.arbitrage(server, server2)
    return jsonify(result)


@app.route("/api/analytics/<chart_type>")
def api_analytics_chart(chart_type):
    from core.analytics import DataFrameAnalytics
    import os
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_data.db")
    a = DataFrameAnalytics(db_path)
    item = request.args.get("item", None)
    server = request.args.get("server", "").strip() or None
    server2 = request.args.get("server2", "").strip() or None

    charts = {
        "servers": lambda: a.server_distribution(server),
        "types": lambda: a.type_distribution(server),
        "levels": lambda: a.level_distribution(server),
        "top-items": lambda: a.top_items(int(request.args.get("limit", 20)), server),
        "price-by-server": lambda: a.price_by_server(item),
        "item-prices": lambda: a.item_prices_by_level(server),
        "arbitrage": lambda: a.arbitrage(server, server2),
        "all-stats": lambda: a.all_stats_table(server),
        "price-stats": lambda: a.price_stats(item, server),
        "volatility": lambda: a.volatility(server),
        "demand": lambda: a.demand(server),
        "distribution": lambda: a.distribution(server),
        "trend": lambda: a.trend(server),
        "liquidity": lambda: a.liquidity(server),
    }
    fn = charts.get(chart_type)
    if not fn:
        return jsonify({"error": f"Unknown chart type: {chart_type}"}), 400
    return jsonify(fn())


@app.route("/live")
def live_page():
    return render_template("live.html")


@app.route("/api/endeks-data")
def api_endeks_data():
    from webapp.database import get_db
    from flask import request
    HOURS = 24
    now = datetime.utcnow()
    cutoff = (now - timedelta(hours=HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    prev_cutoff = (now - timedelta(hours=HOURS * 2)).strftime("%Y-%m-%d %H:%M:%S")
    filter_server = request.args.get("server", "").strip()
    filter_item = request.args.get("item", "").strip()
    filter_level = request.args.get("level", "").strip()

    def med(vals):
        if not vals:
            return 0
        s = sorted(vals)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2

    def calc_stats(vals):
        if not vals:
            return {"min": 0, "max": 0, "std": 0, "var": 0, "q1": 0, "q3": 0, "iqr": 0, "count": 0, "mean": 0}
        s = sorted(vals)
        n = len(s)
        mn, mx = s[0], s[-1]
        mean = sum(s) / n
        variance = sum((x - mean) ** 2 for x in s) / n if n > 1 else 0
        std = variance ** 0.5
        def percentile(data, p):
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (k - f) * (data[c] - data[f])
        q1 = percentile(s, 25)
        q3 = percentile(s, 75)
        return {"min": int(mn), "max": int(mx), "std": round(std), "var": round(variance),
                "q1": round(q1), "q3": round(q3), "iqr": round(q3 - q1), "count": n, "mean": round(mean)}

    with get_db() as db:
        # Get all servers and build group map
        all_server_rows = db.execute("SELECT DISTINCT server FROM prices WHERE server != ''").fetchall()
        all_servers_list = [r["server"] for r in all_server_rows]
        server_groups = {}
        for s in all_servers_list:
            parts = s.rsplit(" ", 1)
            base = parts[0] if len(parts) == 2 and parts[1].isdigit() else s
            if base not in server_groups:
                server_groups[base] = []
            server_groups[base].append(s)

        # Resolve filter: "ZERO" -> ["ZERO 3","ZERO 4","ZERO 5","ZERO 8"]
        matched_servers = []
        is_group = False
        if filter_server:
            if filter_server in server_groups:
                matched_servers = server_groups[filter_server]
                is_group = True
            else:
                matched_servers = [filter_server]

        # Build WHERE clause
        where_extra = ""
        params_extra = []
        if matched_servers:
            ph = ",".join("?" * len(matched_servers))
            where_extra += f" AND server IN ({ph})"
            params_extra.extend(matched_servers)
        if filter_item:
            where_extra += " AND LOWER(item_name) LIKE ?"
            params_extra.append(f"%{filter_item.lower()}%")

        # 1) All prices into memory
        rows = db.execute(
            f"SELECT server, item_name, item_lvl, type, price FROM prices WHERE price > 0{where_extra}",
            params_extra
        ).fetchall()

        srv_prices = {}
        srv_item_prices = {}
        all_item_prices = {}
        for r in rows:
            srv, t, name, lvl, p = r["server"], r["type"], r["item_name"], r["item_lvl"], r["price"]
            if srv:
                if srv not in srv_prices:
                    srv_prices[srv] = {"sell": [], "buy": []}
                srv_prices[srv][t].append(p)
                sikey = (srv, name, lvl)
                if sikey not in srv_item_prices:
                    srv_item_prices[sikey] = {"sell": [], "buy": []}
                srv_item_prices[sikey][t].append(p)
            akey = (name, lvl)
            if akey not in all_item_prices:
                all_item_prices[akey] = {"sell": [], "buy": []}
            all_item_prices[akey][t].append(p)

        # 2) Server metadata - group level or individual level
        if is_group:
            servers = []
            for s in sorted(matched_servers):
                meta = db.execute(
                    "SELECT COUNT(*) as cnt, COUNT(DISTINCT item_name||item_lvl) as items, MIN(timestamp) as fs, MAX(timestamp) as ls FROM prices WHERE server=?",
                    (s,)
                ).fetchone()
                servers.append({
                    "server": s, "total": meta["cnt"], "items": meta["items"],
                    "first_scan": meta["fs"] or "", "last_scan": meta["ls"] or "",
                    "med_sell": int(med(srv_prices.get(s, {}).get("sell", []))),
                    "med_buy": int(med(srv_prices.get(s, {}).get("buy", []))),
                })
        else:
            servers = []
            for base, members in sorted(server_groups.items()):
                all_sell = []
                all_buy = []
                total = 0
                for m in members:
                    all_sell.extend(srv_prices.get(m, {}).get("sell", []))
                    all_buy.extend(srv_prices.get(m, {}).get("buy", []))
                    total += len(srv_prices.get(m, {}).get("sell", [])) + len(srv_prices.get(m, {}).get("buy", []))
                servers.append({
                    "server": base, "count": len(members), "members": sorted(members),
                    "total": total,
                    "med_sell": int(med(all_sell)),
                    "med_buy": int(med(all_buy)),
                })

        # 3) Per-server top items (only when group is selected)
        server_top = {}
        if is_group:
            for srv in matched_servers:
                items = {}
                for (s, name, lvl), v in srv_item_prices.items():
                    if s != srv:
                        continue
                    if filter_item and filter_item.lower() not in name.lower():
                        continue
                    cnt = len(v["sell"]) + len(v["buy"])
                    items[(name, lvl)] = {"sell": v["sell"], "buy": v["buy"], "count": cnt}
                ranked = sorted(items.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
                server_top[srv] = [{
                    "item": k[0], "lvl": k[1],
                    "med_sell": int(med(v["sell"])), "med_buy": int(med(v["buy"])),
                    "count": v["count"]
                } for k, v in ranked]

        # 4) Top items overall
        ranked_all = sorted(all_item_prices.items(),
            key=lambda x: len(x[1]["sell"]) + len(x[1]["buy"]), reverse=True)[:30]
        if filter_item:
            ranked_all = [(k, v) for k, v in ranked_all if filter_item.lower() in k[0].lower()]
        top_items = []
        for k, v in ranked_all:
            srv_list = []
            for (s, name, lvl), sv in srv_item_prices.items():
                if name == k[0] and lvl == k[1]:
                    srv_list.append(s)
            sell_stats = calc_stats(v["sell"])
            buy_stats = calc_stats(v["buy"])
            top_items.append({
                "item": k[0], "lvl": k[1],
                "med_sell": int(med(v["sell"])), "med_buy": int(med(v["buy"])),
                "count": len(v["sell"]) + len(v["buy"]),
                "servers": sorted(set(srv_list)),
                "sell": sell_stats, "buy": buy_stats,
            })

        # 4b) Top items per-server breakdown (no filter = stacked chart)
        top_by_server = {}
        if not filter_server:
            for item_data in top_items[:15]:
                key = f"{item_data['item']}|{item_data['lvl']}"
                per_srv = []
                for (s, name, lvl), v in srv_item_prices.items():
                    if name == item_data["item"] and lvl == item_data["lvl"]:
                        cnt = len(v["sell"]) + len(v["buy"])
                        per_srv.append({"server": s, "med_sell": int(med(v["sell"])),
                                        "med_buy": int(med(v["buy"])), "count": cnt})
                per_srv.sort(key=lambda x: x["count"], reverse=True)
                top_by_server[key] = per_srv

        # 5) Item search result
        item_servers = []
        item_all_levels = []
        if filter_item:
            for (s, name, lvl), v in srv_item_prices.items():
                if filter_item.lower() not in name.lower():
                    continue
                sell_stats = calc_stats(v["sell"])
                buy_stats = calc_stats(v["buy"])
                cnt = sell_stats["count"] + buy_stats["count"]
                entry = {
                    "server": s, "item": name, "lvl": lvl, "count": cnt,
                    "med_sell": int(med(v["sell"])), "med_buy": int(med(v["buy"])),
                    "sell": sell_stats, "buy": buy_stats,
                }
                item_all_levels.append(entry)
                if not filter_level or lvl == filter_level:
                    item_servers.append(entry)
            item_servers.sort(key=lambda x: x["count"], reverse=True)
            item_all_levels.sort(key=lambda x: x["count"], reverse=True)

        # 6) Price changes (24h)
        change_where = "WHERE timestamp >= ?"
        change_params = [prev_cutoff]
        if matched_servers:
            ph = ",".join("?" * len(matched_servers))
            change_where += f" AND server IN ({ph})"
            change_params.extend(matched_servers)
        if filter_item:
            change_where += " AND LOWER(item_name) LIKE ?"
            change_params.append(f"%{filter_item.lower()}%")
        change_rows = db.execute(f"SELECT item_name, item_lvl, type, timestamp, price FROM prices {change_where}", change_params).fetchall()
        ch = {}
        for r in change_rows:
            key = f"{r['item_name'].lower()}|{r['item_lvl']}"
            if key not in ch:
                ch[key] = {"r": [], "p": []}
            if r["type"] == "sell":
                bucket = ch[key]["r"] if r["timestamp"] >= cutoff else ch[key]["p"]
                bucket.append(r["price"])
        processed = {}
        for key, v in ch.items():
            rm = med(v["r"])
            pm = med(v["p"])
            pct = 0
            if pm > 0 and rm > 0:
                pct = round((rm - pm) / pm * 100, 1)
            elif rm > 0:
                pct = 100.0
            processed[key] = {"sell_change": pct, "current": rm, "previous": pm}

    return jsonify({
        "servers": servers, "server_top": server_top,
        "top_items": top_items, "top_by_server": top_by_server,
        "changes": processed, "item_servers": item_servers,
        "item_all_levels": item_all_levels,
        "filters": {"server": filter_server, "item": filter_item, "level": filter_level},
        "server_groups": server_groups,
    })


@app.route("/endeks")
def endeks_page():
    return render_template("endeks.html")


@app.route("/api/analiz/<path:item_name>")
def api_analiz(item_name):
    from webapp.database import get_item_stats, get_db, get_all_item_names, _calc_stats
    all_items = get_all_item_names()
    matched = item_name
    item_lower = item_name.lower()
    for name in all_items:
        if name.lower() == item_lower:
            matched = name
            break

    server = request.args.get("server", "").strip()
    level = request.args.get("level", "").strip()

    with get_db() as db:
        all_server_rows = db.execute(
            "SELECT DISTINCT server FROM prices WHERE item_name=? ORDER BY server",
            (matched,)
        ).fetchall()
        all_servers = [r["server"] for r in all_server_rows]

    server_groups = {}
    for s in all_servers:
        parts = s.rsplit(" ", 1)
        base = parts[0] if len(parts) == 2 and parts[1].isdigit() else s
        if base not in server_groups:
            server_groups[base] = []
        server_groups[base].append(s)

    resolved_servers = []
    if server:
        if server in server_groups:
            resolved_servers = server_groups[server]
        else:
            resolved_servers = [server]
    else:
        resolved_servers = all_servers

    with get_db() as db:
        ph = ",".join("?" * len(resolved_servers))
        lvl_rows = db.execute(
            f"SELECT DISTINCT item_lvl FROM prices WHERE item_name=? AND server IN ({ph}) ORDER BY item_lvl",
            [matched] + resolved_servers
        ).fetchall()
        levels = [r["item_lvl"] for r in lvl_rows]

    def sort_lvl(l):
        if l.startswith("+") and l.endswith("R"):
            return (2, int(l[1:-1]))
        elif l.startswith("+"):
            return (1, int(l[1:]))
        return (0, l)
    levels.sort(key=sort_lvl)

    if level:
        levels = [l for l in levels if l == level]

    per_server_level = {}
    for srv in resolved_servers:
        with get_db() as db:
            if level:
                srv_levels = [level]
            else:
                lvl_rows2 = db.execute(
                    "SELECT DISTINCT item_lvl FROM prices WHERE item_name=? AND server=? ORDER BY item_lvl",
                    (matched, srv)
                ).fetchall()
                srv_levels = [r["item_lvl"] for r in lvl_rows2]

        srv_data = {"levels": {}, "total_sell": 0, "total_buy": 0}
        for lvl in srv_levels:
            with get_db() as db:
                buy_s = _calc_stats(db, matched, lvl, "buy", server=srv)
                sell_s = _calc_stats(db, matched, lvl, "sell", server=srv)

            srv_data["levels"][lvl] = {"buy": buy_s, "sell": sell_s}
            if sell_s:
                srv_data["total_sell"] += sell_s["count"]
            if buy_s:
                srv_data["total_buy"] += buy_s["count"]
        if srv_data["levels"]:
            per_server_level[srv] = srv_data

    stats_all = get_item_stats(matched, server=server if server else None)

    return jsonify({
        "item_name": matched,
        "stats_all": stats_all,
        "per_server_level": per_server_level,
        "levels": levels,
        "servers": all_servers,
        "server_groups": server_groups,
    })


@app.route("/analiz/<path:item_name>")
def item_analysis_page(item_name):
    from webapp.database import get_item_stats, get_db, get_all_item_names, _calc_stats
    all_items = get_all_item_names()
    matched = item_name
    item_lower = item_name.lower()
    for name in all_items:
        if name.lower() == item_lower:
            matched = name
            break

    with get_db() as db:
        srv_rows = db.execute(
            "SELECT DISTINCT server FROM prices WHERE item_name=? ORDER BY server",
            (matched,)
        ).fetchall()
        all_servers = [r["server"] for r in srv_rows]

    server_groups = {}
    for s in all_servers:
        parts = s.rsplit(" ", 1)
        base = parts[0] if len(parts) == 2 and parts[1].isdigit() else s
        if base not in server_groups:
            server_groups[base] = []
        server_groups[base].append(s)

    with get_db() as db:
        lvl_rows = db.execute(
            "SELECT DISTINCT item_lvl FROM prices WHERE item_name=? ORDER BY item_lvl",
            (matched,)
        ).fetchall()
        levels = [r["item_lvl"] for r in lvl_rows]

    def sort_lvl(l):
        if l.startswith("+") and l.endswith("R"):
            return (2, int(l[1:-1]))
        elif l.startswith("+"):
            return (1, int(l[1:]))
        return (0, l)
    levels.sort(key=sort_lvl)

    stats_all = get_item_stats(matched)

    per_server_level = {}
    for srv in all_servers:
        with get_db() as db:
            lvl_rows2 = db.execute(
                "SELECT DISTINCT item_lvl FROM prices WHERE item_name=? AND server=? ORDER BY item_lvl",
                (matched, srv)
            ).fetchall()
            srv_levels = [r["item_lvl"] for r in lvl_rows2]

        srv_data = {"levels": {}, "total_sell": 0, "total_buy": 0}
        for lvl in srv_levels:
            with get_db() as db:
                buy_s = _calc_stats(db, matched, lvl, "buy", server=srv)
                sell_s = _calc_stats(db, matched, lvl, "sell", server=srv)
            srv_data["levels"][lvl] = {"buy": buy_s, "sell": sell_s}
            if sell_s:
                srv_data["total_sell"] += sell_s["count"]
            if buy_s:
                srv_data["total_buy"] += buy_s["count"]
        if srv_data["levels"]:
            per_server_level[srv] = srv_data

    return render_template("analiz.html",
        item_name=matched,
        stats_all=stats_all,
        per_server_level=per_server_level,
        levels=levels,
        servers=all_servers,
        server_groups=server_groups,
        all_items=all_items,
    )
