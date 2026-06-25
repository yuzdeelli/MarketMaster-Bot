import time
import threading
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE_URL = "https://www.uskopazar.com/api"

SERVER_MAP = {
    "ZERO 3": "zero3", "ZERO 4": "zero4", "ZERO 5": "zero5", "ZERO 8": "zero8",
    "PANDORA 3": "pandora3", "PANDORA 4": "pandora4",
    "AGARTHA 3": "agartha3", "AGARTHA 4": "agartha4",
    "FELIS 2": "felis2",
    "DESTAN 3": "destan3", "DESTAN 2": "destan2",
    "MINARK 2": "minark2",
    "DRYADS 2": "dryads2",
    "OREADS 2": "oreads2", "OREADS 3": "oreads3",
}

SERVER_MAP_REVERSE = {v: k for k, v in SERVER_MAP.items()}

GROUP_MAP = {
    "Tüm Zero": ["zero3", "zero4", "zero5", "zero8"],
    "Tüm Agartha": ["agartha3", "agartha4"],
    "Tüm Pandora": ["pandora3", "pandora4"],
    "Tüm Destan": ["destan2", "destan3"],
    "Tüm Oreads": ["oreads2", "oreads3"],
}


class UskoApiClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key} if api_key else {})
        self._rate_lock = threading.Lock()
        self._last_request_time = 0
        self._min_interval = 0.0

    def set_api_key(self, api_key):
        self.api_key = api_key
        self.session.headers.update({"X-API-Key": api_key})

    def _rate_limit(self):
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request_time = time.time()

    def _request(self, method, path, **kwargs):
        self._rate_limit()
        url = f"{BASE_URL}{path}"
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"Rate limit! {retry_after}s bekleniyor...")
                time.sleep(retry_after)
                return self._request(method, path, **kwargs)
            if resp.status_code == 500:
                print(f"Sunucu 500 hatası, 5s bekleniyor...")
                time.sleep(5)
                return self._request(method, path, **kwargs)
            data = resp.json()
            if resp.status_code == 429:
                return {"success": False, "error": "Rate limit aşıldı. Biraz bekleyin.", "code": 429}
            if resp.status_code == 403:
                return {"success": False, "error": "API key geçersiz veya süresi dolmuş.", "code": 403}
            if resp.status_code == 401:
                return {"success": False, "error": "API key gönderilmedi.", "code": 401}
            return data
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Internet bağlantısı yok.", "code": 0}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "İstek zaman aşımına uğradı.", "code": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "code": 0}

    def activate(self):
        return self._request("POST", "/activate", data={"api_key": self.api_key})

    def get_status(self):
        return self._request("GET", "/status")

    def get_items(self, server, search=None, plus=None, item_type=-1,
                  order="date_desc", page=1, limit=20, rebirth=None):
        params = {"server": server, "page": page, "limit": limit, "order": order, "type": item_type}
        if search:
            params["search"] = search
        if plus is not None and plus != "":
            try:
                params["plus"] = int(plus)
            except (ValueError, TypeError):
                pass
        if rebirth:
            params["rebirth"] = 1
        return self._request("GET", "/items", params=params)

    def get_history(self, item_id, server=None):
        params = {"item_id": item_id}
        if server:
            params["server"] = server
        return self._request("GET", "/history", params=params)

    def resolve_server_code(self, display_name):
        if display_name in SERVER_MAP:
            return SERVER_MAP[display_name]
        if display_name in GROUP_MAP:
            return GROUP_MAP[display_name]
        return display_name.lower().replace(" ", "")

    def expand_servers(self, server_names):
        expanded = set()
        for name in server_names:
            if name in GROUP_MAP:
                expanded.update(GROUP_MAP[name])
            elif name in SERVER_MAP:
                expanded.add(SERVER_MAP[name])
            else:
                expanded.add(name.lower().replace(" ", ""))
        return list(expanded)

    def scan_item(self, server_display, item_name, plus=None, item_type=-1, limit=100, rebirth=False):
        server_code = self.resolve_server_code(server_display)

        if isinstance(server_code, list):
            all_parsed = []
            for code in server_code:
                result = self._scan_single_code(code, item_name, plus, item_type, limit, rebirth)
                all_parsed.extend(result)
            return all_parsed, None

        return self._scan_single_code(server_code, item_name, plus, item_type, limit, rebirth), None

    def _scan_single_code(self, server_code, item_name, plus, item_type, limit, rebirth=False):
        params = {"server": server_code, "search": item_name, "item_type": item_type, "limit": limit, "order": "date_desc"}
        if plus is not None and plus != "":
            try:
                params["plus"] = int(plus)
            except (ValueError, TypeError):
                pass
        if rebirth:
            params["rebirth"] = 1
        results = self._request("GET", "/items", params=params)
        if not results.get("success"):
            print(f"[{server_code}] Hata: {results.get('error', 'Bilinmeyen hata')}")
            return []
        items = results.get("data", [])
        parsed = []
        for item in items:
            raw_time = item.get("CreatedTime", "")
            try:
                if "T" in raw_time:
                    dt = raw_time.replace("T", " ").split(".")[0]
                else:
                    dt = raw_time
            except:
                dt = raw_time
            raw_name = item.get("ItemName", item_name).strip()
            raw_plus = item.get("Plus", plus if plus else 0)
            try:
                raw_plus = int(raw_plus)
            except:
                raw_plus = 0
            lvl_str = f"+{raw_plus}" if raw_plus else "+0"
            if rebirth and plus is not None:
                lvl_str = f"+{plus}R"
            parsed.append({
                "Sunucu": SERVER_MAP_REVERSE.get(server_code, server_code),
                "Pazar Tipi": "Sell" if item.get("iType") == 0 else "Buy",
                "İtem Adı": raw_name,
                "Artı": lvl_str,
                "Fiyat": item.get("ItemPrice", 0),
                "Zaman": dt,
                "ItemID": item.get("ItemID"),
                "UserID": item.get("UserID"),
            })
        return parsed

    def scan_item_multi_server(self, server_display_names, item_name, plus=None,
                                item_type=-1, limit=100, stop_event=None):
        all_results = []
        codes = self.expand_servers(server_display_names)
        for code in codes:
            if stop_event and stop_event.is_set():
                break
            display = SERVER_MAP_REVERSE.get(code, code)
            result, error = self.scan_item(display, item_name, plus, item_type, limit)
            if error:
                print(f"[{code}] Hata: {error}")
                continue
            all_results.extend(result)
            time.sleep(0.3)
        return all_results

    def fetch_all_items(self, server_code, item_type=-1, limit=100,
                        progress_callback=None, stop_event=None, levels=None, reverse_levels=None):
        all_parsed = []
        if levels is None:
            levels = [None]
        if reverse_levels is None:
            reverse_levels = []

        for level_val in levels:
            if stop_event and stop_event.is_set():
                break
            page = 1
            level_label = f"+{level_val}" if level_val is not None else "TUM"
            while True:
                if stop_event and stop_event.is_set():
                    break
                result = self.get_items(
                    server=server_code, item_type=item_type,
                    page=page, limit=limit, order="date_desc",
                    plus=level_val, rebirth=False
                )
                if not result.get("success"):
                    if progress_callback:
                        progress_callback(f"Hata: {result.get('error')}", 0)
                    break
                items = result.get("data", [])
                if not items:
                    break
                for item in items:
                    raw_time = item.get("CreatedTime", "")
                    try:
                        if "T" in raw_time:
                            dt = raw_time.replace("T", " ").split(".")[0]
                        else:
                            dt = raw_time
                    except:
                        dt = raw_time
                    raw_name = item.get("ItemName", "").strip()
                    raw_plus = item.get("Plus", 0)
                    try:
                        raw_plus = int(raw_plus)
                    except:
                        raw_plus = 0
                    if not raw_plus:
                        import re
                        m = re.search(r"\+(\d+)\)", raw_name)
                        if m:
                            raw_plus = int(m.group(1))
                    all_parsed.append({
                        "Sunucu": SERVER_MAP_REVERSE.get(server_code, server_code),
                        "Pazar Tipi": "Sell" if item.get("iType") == 0 else "Buy",
                        "İtem Adı": raw_name,
                        "Artı": f"+{raw_plus}" if raw_plus else "+0",
                        "Fiyat": item.get("ItemPrice", 0),
                        "Zaman": dt,
                        "ItemID": item.get("ItemID"),
                        "UserID": item.get("UserID"),
                    })
                if progress_callback:
                    display = SERVER_MAP_REVERSE.get(server_code, server_code)
                    progress_callback(f"PAGE|{display}|{level_label}|{page}|{len(all_parsed)}", len(all_parsed))
                if len(items) < limit:
                    break
                page += 1
                time.sleep(1.5)

        for rev_val in reverse_levels:
            if stop_event and stop_event.is_set():
                break
            page = 1
            rev_label = f"+{rev_val}R"
            while True:
                if stop_event and stop_event.is_set():
                    break
                result = self.get_items(
                    server=server_code, item_type=item_type,
                    page=page, limit=limit, order="date_desc",
                    plus=rev_val, rebirth=True
                )
                if not result.get("success"):
                    if progress_callback:
                        progress_callback(f"Hata: {result.get('error')}", 0)
                    break
                items = result.get("data", [])
                if not items:
                    break
                for item in items:
                    raw_time = item.get("CreatedTime", "")
                    try:
                        if "T" in raw_time:
                            dt = raw_time.replace("T", " ").split(".")[0]
                        else:
                            dt = raw_time
                    except:
                        dt = raw_time
                    raw_name = item.get("ItemName", "").strip()
                    all_parsed.append({
                        "Sunucu": SERVER_MAP_REVERSE.get(server_code, server_code),
                        "Pazar Tipi": "Sell" if item.get("iType") == 0 else "Buy",
                        "İtem Adı": raw_name,
                        "Artı": f"+{rev_val}R",
                        "Fiyat": item.get("ItemPrice", 0),
                        "Zaman": dt,
                        "ItemID": item.get("ItemID"),
                        "UserID": item.get("UserID"),
                    })
                if progress_callback:
                    display = SERVER_MAP_REVERSE.get(server_code, server_code)
                    progress_callback(f"PAGE|{display}|{rev_label}|{page}|{len(all_parsed)}", len(all_parsed))
                if len(items) < limit:
                    break
                page += 1
                time.sleep(1.5)

        return all_parsed

    def fetch_all_servers(self, server_names=None, item_type=-1, limit=100,
                          progress_callback=None, stop_event=None, levels=None, reverse_levels=None,
                          max_workers=5):
        if server_names is None:
            server_names = list(SERVER_MAP.keys())
        codes = self.expand_servers(server_names)
        total = len(codes)
        all_results = []
        done_count = [0]
        lock = threading.Lock()

        def fetch_one(i, code):
            display = SERVER_MAP_REVERSE.get(code, code)
            time.sleep(i * 1.5)
            if stop_event and stop_event.is_set():
                return []
            thread_client = UskoApiClient(api_key=self.api_key)
            if progress_callback:
                progress_callback(f"SERVER_START|{display}|{i+1}|{total}", 0)
            for attempt in range(3):
                if stop_event and stop_event.is_set():
                    return []
                try:
                    items = thread_client.fetch_all_items(
                        code, item_type=item_type, limit=limit,
                        progress_callback=progress_callback, stop_event=stop_event,
                        levels=levels, reverse_levels=reverse_levels
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        if progress_callback:
                            progress_callback(f"Retry {attempt+1}: {display} - {e}", 0)
                        time.sleep(5)
                    else:
                        items = []
                        if progress_callback:
                            progress_callback(f"Hata: {display} - {e} (3 deneme basarisiz)", 0)
            with lock:
                done_count[0] += 1
                all_results.extend(items)
                current_total = len(all_results)
            if progress_callback:
                progress_callback(f"SERVER_DONE|{display}|{len(items)}|{done_count[0]}/{total}", current_total)
            return items

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one, i, code): code for i, code in enumerate(codes)}
            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    break
                try:
                    future.result()
                except Exception as e:
                    code = futures[future]
                    display = SERVER_MAP_REVERSE.get(code, code)
                    if progress_callback:
                        progress_callback(f"Hata: {display} - {e}", 0)

        all_results.sort(key=lambda x: x.get("Zaman", ""), reverse=True)
        if progress_callback:
            progress_callback(f"ALL_DONE|{len(all_results)}", len(all_results))
        return all_results
