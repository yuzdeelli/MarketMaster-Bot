import socket
import threading
import sys
import os
import json

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class WebServer:
    def __init__(self):
        self.is_running = False
        self.port = self._load_port()
        self.thread = None
        self._server = None

    def _load_port(self):
        try:
            config_path = os.path.join(_BASE_DIR, "analyzer_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                return cfg.get("web_port", 8765)
        except:
            pass
        return 8765

    def start(self):
        try:
            if self.is_running:
                return True

            mods_to_remove = [k for k in sys.modules if k.startswith('webapp')]
            for m in mods_to_remove:
                del sys.modules[m]

            sys.path.insert(0, _BASE_DIR)
            sys.path.insert(0, os.path.join(_BASE_DIR, "webapp"))

            from webapp.app import app
            from werkzeug.serving import make_server

            def _run():
                try:
                    self._server = make_server("0.0.0.0", self.port, app)
                    self._server.serve_forever()
                except Exception:
                    pass

            self.thread = threading.Thread(target=_run, daemon=True)
            self.thread.start()
            self.is_running = True
            return True
        except Exception as e:
            print(f"Web server baslatilamadi: {e}")
            return False

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
            except:
                pass
            self._server = None
        self.is_running = False
        self.thread = None

    def get_url(self):
        try:
            candidates = []
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip.startswith("127."):
                    continue
                candidates.append(ip)
            for ip in candidates:
                if ip.startswith("192.168."):
                    return f"http://{ip}:{self.port}"
            ip = candidates[0] if candidates else "127.0.0.1"
            return f"http://{ip}:{self.port}"
        except:
            return f"http://127.0.0.1:{self.port}"
