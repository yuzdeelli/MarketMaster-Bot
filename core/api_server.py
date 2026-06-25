import hashlib
import json
import os
import random
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, quote
from core.config import ConfigManager
from core.database import DatabaseManager


def get_local_ip():
    try:
        candidates = []
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            candidates.append(ip)
        for ip in candidates:
            if ip.startswith("192.168."):
                return ip
        return candidates[0] if candidates else "127.0.0.1"
    except:
        return "127.0.0.1"


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market Master</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
    background: #0a0a14;
    color: #e0e0e0;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
  }
  .hero {
    text-align: center;
  }
  .hero .logo {
    font-size: 72px;
    font-weight: 900;
    letter-spacing: 8px;
    text-transform: uppercase;
    background: linear-gradient(135deg, #e94560 0%, #ff6b81 40%, #e94560 80%, #ff6b81 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0 0 30px rgba(233,69,96,0.25));
    animation: pulse 3s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { filter: drop-shadow(0 0 20px rgba(233,69,96,0.2)); }
    50% { filter: drop-shadow(0 0 40px rgba(233,69,96,0.4)); }
  }
  .hero .subtitle {
    font-size: 14px;
    color: #555;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-top: 8px;
  }
  .hero .loading-dots {
    margin-top: 30px;
    display: flex;
    justify-content: center;
    gap: 8px;
  }
  .hero .loading-dots span {
    width: 8px;
    height: 8px;
    background: #e94560;
    border-radius: 50%;
    animation: bounce 1.4s ease-in-out infinite;
  }
  .hero .loading-dots span:nth-child(2) { animation-delay: 0.2s; }
  .hero .loading-dots span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
    40% { transform: scale(1); opacity: 1; }
  }
</style>
</head>
<body>
<div class="hero">
  <div class="logo">MARKET MASTER</div>
  <div class="subtitle">Knight Online Pazar Analiz</div>
  <div class="loading-dots">
    <span></span><span></span><span></span>
  </div>
</div>
</body>
</html>"""


class APIHandler(BaseHTTPRequestHandler):
    db = None
    base_dir = None
    _sessions = {}
    _admin_pass = ""

    @classmethod
    def refresh_admin_password(cls):
        cls._admin_pass = ConfigManager.load_admin_password()

    def _gen_token(self):
        return hashlib.sha256(str(random.getrandbits(256)).encode()).hexdigest()

    def _check_session(self, parsed_cookies):
        token = parsed_cookies.get("token", [None])[0]
        if token and token in self.__class__._sessions:
            return True
        return False

    def _parse_cookies(self):
        raw = self.headers.get("Cookie", "")
        result = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.strip()] = [v.strip()]
        return result

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _send_html(self, html, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _get_db(self):
        return self.__class__.db

    def _get_base_dir(self):
        return self.__class__.base_dir

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)
        db = self._get_db()

        if path == "/" or path == "":
            self._send_html(DASHBOARD_HTML)
        elif path == "/api/all":
            self._api_all(db)
        elif path == "/api/portfolio":
            self._api_portfolio(db)
        elif path == "/api/items":
            self._api_items(db)
        elif path == "/api/servers":
            self._api_servers(db)
        elif path == "/api/prices":
            self._api_prices(db, params)
        elif path == "/api/stats":
            self._api_stats(db, params)
        elif path == "/admin":
            cookies = self._parse_cookies()
            if self._check_session(cookies):
                self._send_html(ADMIN_DASHBOARD_HTML)
            else:
                self._send_html(ADMIN_LOGIN_HTML)
        elif path == "/admin/api/dashboard":
            if not self._check_session(self._parse_cookies()):
                return self._send_json({"error": "Yetkisiz"}, 401)
            self._admin_api_dashboard(db)
        elif path == "/admin/api/queue":
            if not self._check_session(self._parse_cookies()):
                return self._send_json({"error": "Yetkisiz"}, 401)
            self._admin_api_queue()
        elif path == "/admin/api/logs":
            if not self._check_session(self._parse_cookies()):
                return self._send_json({"error": "Yetkisiz"}, 401)
            self._admin_api_logs()
        elif path == "/admin/logout":
            cookies = self._parse_cookies()
            token = cookies.get("token", [None])[0]
            if token and token in self.__class__._sessions:
                del self.__class__._sessions[token]
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.end_headers()
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len else ""
        post_params = parse_qs(body)

        if path == "/admin/login":
            self._admin_login(post_params)
        elif path == "/admin/api/queue/add":
            if not self._check_session(self._parse_cookies()):
                return self._send_json({"error": "Yetkisiz"}, 401)
            self._admin_queue_add(post_params)
        elif path == "/admin/api/queue/remove":
            if not self._check_session(self._parse_cookies()):
                return self._send_json({"error": "Yetkisiz"}, 401)
            self._admin_queue_remove(post_params)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _load_portfolio_file(self):
        base = self._get_base_dir()
        if not base:
            return []

        json_path = os.path.join(base, "portfolio_data.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass

        txt_path = os.path.join(base, "excel_export_item_list.txt")
        if os.path.exists(txt_path):
            result = []
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split("|")
                        if len(parts) >= 3:
                            result.append({
                                "name": parts[0],
                                "lvl": parts[1],
                                "buy_price": float(parts[2]) if parts[2] else 0,
                                "buy_strategy": parts[3] if len(parts) > 3 else "Auto",
                                "count": int(parts[4]) if len(parts) > 4 else 1,
                                "sell_strategy": parts[5] if len(parts) > 5 else "Auto",
                            })
            except:
                pass
            return result

        return []

    def _api_portfolio(self, db):
        port = self._load_portfolio_file()
        from core.analyzer import MarketAnalyzer
        analyzer = MarketAnalyzer(db)
        items = []
        for idx, p in enumerate(port):
            db_lvl = "" if p["lvl"] in ["+0", "0"] else p["lvl"]
            stats = analyzer.get_item_stats(p["name"], db_lvl)
            sell_price = 0
            if stats and stats.get("sell"):
                s = stats["sell"]
                strat = p.get("sell_strategy", "Auto")
                if strat == "Auto":
                    sell_price = s.get("median", 0)
                elif strat == "Min*0.97+%Kar":
                    try:
                        margin = float(p.get("margin", 0))
                    except:
                        margin = 0
                    sell_price = s.get("min", 0) * 0.97 * (1 + margin / 100)
                else:
                    s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
                    sell_price = s.get(s_map.get(strat, "median"), 0)
            elif stats and stats.get("sell"):
                sell_price = stats["sell"].get("median", 0)

            vergi_sonrasi = sell_price * 0.97 if sell_price > 0 else 0
            birim_kar = vergi_sonrasi - p["buy_price"]
            toplam_kar = birim_kar * p["count"]
            yatirim = p["buy_price"] * p["count"]
            durum = "Kar" if toplam_kar > 0 else ("Zarar" if toplam_kar < 0 else "Basaraba")

            items.append({
                "sira": idx + 1,
                "item": p["name"],
                "lvl": p["lvl"],
                "adet": p["count"],
                "alis": p["buy_price"],
                "satis": sell_price,
                "vergi_sonrasi": round(vergi_sonrasi),
                "birim_kar": round(birim_kar),
                "toplam_kar": round(toplam_kar),
                "yatirim": round(yatirim),
                "durum": durum,
            })
        self._send_json({"count": len(items), "items": items})

    def _api_all(self, db):
        items = db.get_all_unique_items() if hasattr(db, 'get_all_unique_items') else []
        from core.analyzer import MarketAnalyzer
        analyzer = MarketAnalyzer(db)
        result = []
        for it in items:
            stats = analyzer.get_item_stats(it["name"], it["lvl"])
            result.append({
                "item": it["name"],
                "lvl": it["lvl"],
                "buy_min": stats["buy"]["min"] if stats and stats.get("buy") else None,
                "buy_med": stats["buy"]["median"] if stats and stats.get("buy") else None,
                "buy_max": stats["buy"]["max"] if stats and stats.get("buy") else None,
                "sell_min": stats["sell"]["min"] if stats and stats.get("sell") else None,
                "sell_med": stats["sell"]["median"] if stats and stats.get("sell") else None,
                "sell_max": stats["sell"]["max"] if stats and stats.get("sell") else None,
            })
        self._send_json({"count": len(result), "items": result})

    def _api_items(self, db):
        names = db.get_unique_item_names() if hasattr(db, 'get_unique_item_names') else []
        self._send_json({"count": len(names), "items": names})

    def _api_servers(self, db):
        servers = db.get_unique_servers() if hasattr(db, 'get_unique_servers') else []
        self._send_json({"count": len(servers), "servers": servers})

    def _api_prices(self, db, params):
        item = params.get("item", [None])[0]
        lvl = params.get("lvl", [""])[0]
        limit = int(params.get("limit", [100])[0])
        if not item:
            return self._send_json({"error": "item parametresi gerekli"}, 400)
        try:
            prices = db.get_prices(item, lvl, limit=limit)
            self._send_json({"count": len(prices), "prices": prices})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _api_stats(self, db, params):
        item = params.get("item", [None])[0]
        lvl = params.get("lvl", [""])[0]
        if not item:
            return self._send_json({"error": "item parametresi gerekli"}, 400)
        try:
            from core.analyzer import MarketAnalyzer
            analyzer = MarketAnalyzer(db)
            stats = analyzer.get_item_stats(item, lvl)
            self._send_json(stats if stats else {"error": "Veri yok"})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


    # ---- Admin methods ----
    def _admin_login(self, params):
        pw = params.get("password", [""])[0]
        if not self.__class__._admin_pass:
            self._send_html(ADMIN_LOGIN_HTML.replace(
                '<form method="POST" action="/admin/login">',
                '<form method="POST" action="/admin/login"><p style="color:#e74c3c;margin-bottom:8px">Admin sifresi tanimlanmamis!</p>'
            ))
            return
        if pw == self.__class__._admin_pass:
            token = self._gen_token()
            self.__class__._sessions[token] = datetime.now()
            self.send_response(302)
            self.send_header("Set-Cookie", f"token={token}; path=/")
            self.send_header("Location", "/admin")
            self.end_headers()
        else:
            self._send_html(ADMIN_LOGIN_HTML.replace(
                '<form method="POST" action="/admin/login">',
                '<form method="POST" action="/admin/login"><p style="color:#e74c3c;margin-bottom:8px">Hatali sifre!</p>'
            ))

    def _admin_api_dashboard(self, db):
        stats = {"total_items": 0, "total_servers": 0, "total_prices": 0, "queue_count": 0}
        try:
            if hasattr(db, 'get_all_unique_items'):
                stats["total_items"] = len(db.get_all_unique_items())
            if hasattr(db, 'get_unique_servers'):
                stats["total_servers"] = len(db.get_unique_servers())
            try:
                rows = db.execute_query("SELECT COUNT(*) FROM prices")
                stats["total_prices"] = rows[0][0] if rows else 0
            except:
                stats["total_prices"] = 0
        except:
            pass
        queue = self._read_queue_file()
        stats["queue_count"] = len(queue)
        stats["server_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._send_json(stats)

    def _admin_api_queue(self):
        queue = self._read_queue_file()
        self._send_json({"count": len(queue), "items": queue})

    def _admin_queue_add(self, params):
        name = params.get("name", [""])[0].strip()
        lvls = params.get("lvls", [""])[0].strip()
        if not name:
            return self._send_json({"error": "Item adi gerekli"}, 400)
        entry = f"{name}:{lvls}" if lvls else name
        queue = self._read_queue_file()
        queue.append({"name": name, "lvls": lvls})
        self._write_queue_file(queue)
        self._send_json({"success": True, "message": f"{name} eklendi"})

    def _admin_queue_remove(self, params):
        idx = params.get("index", [None])[0]
        if idx is None:
            return self._send_json({"error": "index gerekli"}, 400)
        queue = self._read_queue_file()
        idx = int(idx)
        if 0 <= idx < len(queue):
            removed = queue.pop(idx)
            self._write_queue_file(queue)
            self._send_json({"success": True, "message": f"{removed['name']} silindi"})
        else:
            self._send_json({"error": "Gecersiz index"}, 400)

    def _admin_api_logs(self):
        log_file = os.path.join(os.path.dirname(__file__), "..", "scan_log.txt") if self._get_base_dir() else "scan_log.txt"
        lines = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except:
                pass
        self._send_json({"count": len(lines), "logs": lines[-200:]})

    def _read_queue_file(self):
        base = self._get_base_dir()
        path = os.path.join(base, "kayitli_itemlar.txt") if base else "kayitli_itemlar.txt"
        items = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        if ":" in line:
                            name, lvls = line.split(":", 1)
                            items.append({"name": name.strip(), "lvls": lvls.strip()})
                        else:
                            items.append({"name": line, "lvls": ""})
            except:
                pass
        return items

    def _write_queue_file(self, items):
        base = self._get_base_dir()
        path = os.path.join(base, "kayitli_itemlar.txt") if base else "kayitli_itemlar.txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                for it in items:
                    if it["lvls"]:
                        f.write(f"{it['name']}:{it['lvls']}\n")
                    else:
                        f.write(f"{it['name']}\n")
        except:
            pass


# ---- Admin HTML ----
ADMIN_LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KMM v3 - Admin Giris</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;background:#0f0f1a;color:#ddd;display:flex;justify-content:center;align-items:center;height:100vh;}
  .login-box{background:#1a1a2e;padding:40px;border-radius:12px;border:1px solid #333;width:340px;}
  .login-box h2{color:#e94560;margin-bottom:20px;text-align:center;}
  .login-box input{width:100%;padding:12px;margin-bottom:12px;border:1px solid #333;border-radius:6px;background:#16213e;color:#ddd;font-size:14px;}
  .login-box button{width:100%;padding:12px;background:#e94560;color:#fff;border:none;border-radius:6px;font-size:15px;cursor:pointer;font-weight:600;}
  .login-box button:hover{background:#d63850;}
  .login-box a{display:block;text-align:center;margin-top:12px;color:#666;font-size:12px;text-decoration:none;}
</style>
</head>
<body>
<div class="login-box">
  <h2>Admin Paneli</h2>
  <form method="POST" action="/admin/login">
    <input type="password" name="password" placeholder="Yonetici sifresi" required autofocus>
    <button type="submit">Giris</button>
  </form>
  <a href="/">Ana Sayfa</a>
</div>
</body>
</html>"""

ADMIN_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KMM v3 - Admin Panel</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box;}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial;background:#0f0f1a;color:#ddd;}
  .header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:15px 20px;border-bottom:2px solid #e94560;display:flex;justify-content:space-between;align-items:center;}
  .header h1{color:#e94560;font-size:18px;}
  .header .links{display:flex;gap:12px;align-items:center;}
  .header .links a{color:#888;text-decoration:none;font-size:12px;}
  .header .links a:hover{color:#e94560;}
  .container{max-width:1200px;margin:0 auto;padding:20px;}
  .stats-row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px;}
  .stat-card{background:#16213e;padding:16px;border-radius:8px;flex:1;min-width:140px;border:1px solid #1a2744;}
  .stat-card .label{color:#888;font-size:11px;text-transform:uppercase;}
  .stat-card .value{font-size:24px;font-weight:bold;margin-top:6px;color:#2ecc71;}
  .section{background:#1a1a2e;border-radius:8px;padding:15px;margin-bottom:20px;}
  .section h3{color:#e94560;margin-bottom:12px;font-size:15px;}
  .add-form{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;}
  .add-form input{flex:1;padding:8px 12px;border:1px solid #333;border-radius:4px;background:#16213e;color:#ddd;min-width:120px;}
  .add-form button{padding:8px 16px;background:#e94560;color:#fff;border:none;border-radius:4px;cursor:pointer;font-weight:600;}
  .add-form button:hover{background:#d63850;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th{background:#16213e;color:#e94560;padding:8px 6px;text-align:left;font-weight:600;}
  td{padding:6px;border-bottom:1px solid #1a1a2e;}
  tr:hover{background:#16213e;}
  .btn-del{padding:3px 10px;background:#e74c3c;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:11px;}
  .btn-del:hover{background:#c0392b;}
  .empty{color:#666;text-align:center;padding:20px;}
  .logs-box{max-height:300px;overflow-y:auto;background:#0f0f1a;padding:10px;border-radius:4px;font-family:monospace;font-size:11px;line-height:1.6;}
  .logs-box .ts{color:#666;}
  .toast{position:fixed;bottom:20px;right:20px;background:#2ecc71;color:#fff;padding:12px 20px;border-radius:6px;display:none;font-size:13px;}
  .toast.err{background:#e74c3c;}
</style>
</head>
<body>
<div class="header">
  <h1>KMM v3 Admin Paneli</h1>
  <div class="links">
    <a href="/">Ana Sayfa</a>
    <a href="/admin/logout">Cikis</a>
  </div>
</div>
<div class="container">
  <div class="stats-row" id="stats"></div>

  <div class="section">
    <h3>Tarama Kuyrugu</h3>
    <div class="add-form">
      <input id="qname" placeholder="Item adi">
      <input id="qlvls" placeholder="Seviyeler (bos, +1,+5,+10)">
      <button onclick="addQueue()">Ekle</button>
    </div>
    <div style="overflow-x:auto">
      <table><thead><tr><th>#</th><th>Item</th><th>Seviyeler</th><th></th></tr></thead>
      <tbody id="queue-body"></tbody></table>
    </div>
  </div>

  <div class="section">
    <h3>Son Loglar</h3>
    <div class="logs-box" id="logs"></div>
  </div>
</div>
<div id="toast" class="toast"></div>

<script>
async function loadStats() {
  const r=await fetch('/admin/api/dashboard');
  if(r.status===401){window.location='/admin';return;}
  const d=await r.json();
  document.getElementById('stats').innerHTML=
    `<div class="stat-card"><div class="label">DB Item</div><div class="value">${d.total_items}</div></div>
     <div class="stat-card"><div class="label">Sunucu</div><div class="value">${d.total_servers}</div></div>
     <div class="stat-card"><div class="label">Fiyat Kaydi</div><div class="value">${d.total_prices}</div></div>
     <div class="stat-card"><div class="label">Kuyruk</div><div class="value">${d.queue_count}</div></div>
     <div class="stat-card"><div class="label">Saat</div><div class="value" style="font-size:14px;color:#888">${d.server_time}</div></div>`;
}

async function loadQueue() {
  const r=await fetch('/admin/api/queue');
  if(r.status===401){window.location='/admin';return;}
  const d=await r.json();
  document.getElementById('queue-body').innerHTML=d.items.map((it,i)=>
    `<tr><td>${i+1}</td><td>${it.name}</td><td>${it.lvls||'-'}</td>
     <td><button class="btn-del" onclick="removeQueue(${i})">Sil</button></td></tr>`
  ).join('')||'<tr><td colspan="4" class="empty">Kuyruk bos</td></tr>';
}

async function loadLogs() {
  const r=await fetch('/admin/api/logs');
  if(r.status===401){window.location='/admin';return;}
  const d=await r.json();
  document.getElementById('logs').innerHTML=d.logs.map(l=>`<div>${l}</div>`).join('')||'<div class="empty">Log yok</div>';
}

async function addQueue() {
  const name=document.getElementById('qname').value.trim();
  const lvls=document.getElementById('qlvls').value.trim();
  if(!name){showToast('Item adi gerekli',true);return;}
  const r=await fetch('/admin/api/queue/add',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'name='+encodeURIComponent(name)+'&lvls='+encodeURIComponent(lvls)});
  const d=await r.json();
  if(d.success){showToast(d.message);document.getElementById('qname').value='';document.getElementById('qlvls').value='';loadQueue();}
  else showToast(d.error||'Hata',true);
}

async function removeQueue(idx) {
  const r=await fetch('/admin/api/queue/remove',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'index='+idx});
  const d=await r.json();
  if(d.success){showToast(d.message);loadQueue();}
  else showToast(d.error||'Hata',true);
}

function showToast(msg,err){const t=document.getElementById('toast');t.textContent=msg;t.className='toast'+(err?' err':'');t.style.display='block';setTimeout(()=>t.style.display='none',3000);}

loadStats();loadQueue();loadLogs();
setInterval(loadStats,10000);setInterval(loadQueue,30000);
</script>
</body>
</html>"""


class ApiServer:
    def __init__(self, db_manager: DatabaseManager, port=8765, base_dir=None):
        self.db_manager = db_manager
        self.port = port
        self.base_dir = base_dir
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        if self.running:
            return
        APIHandler.db = self.db_manager
        APIHandler.base_dir = self.base_dir
        APIHandler.refresh_admin_password()
        self.server = HTTPServer(("0.0.0.0", self.port), APIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.running = True

    def stop(self):
        if self.server and self.running:
            self.server.shutdown()
            self.server.server_close()
        self.running = False
        self.server = None
        self.thread = None

    def get_url(self):
        ip = get_local_ip()
        return f"http://{ip}:{self.port}"

    def get_admin_url(self):
        return f"{self.get_url()}/admin"
