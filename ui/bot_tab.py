import threading
import time
import os
import json
import sqlite3
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QLineEdit, QTextEdit, QCheckBox,
                                QGroupBox, QGridLayout, QMessageBox, QFrame,
                                QTabWidget, QComboBox, QFileDialog)
from PySide6.QtCore import Qt, QTimer
from datetime import datetime

try:
    import requests as _req
except ImportError:
    _req = None

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DB_PATH = os.path.join(_base, "app_data.db")
WEB_DB_PATH = APP_DB_PATH
QS_DB_PATH = APP_DB_PATH
WEB_SERVER_URL = "http://127.0.0.1:8765"

try:
    config_path = os.path.join(_base, "analyzer_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as _f:
            _cfg = json.load(_f)
        WEB_SERVER_URL = f"http://127.0.0.1:{_cfg.get('web_port', 8765)}"
except:
    pass

COMPACT_STYLE = """
QGroupBox { font-size: 11px; font-weight: bold; border: 1px solid #555; border-radius: 4px; margin-top: 6px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QCheckBox { font-size: 11px; }
QLabel { font-size: 11px; }
QPushButton { font-size: 11px; padding: 4px 8px; }
QLineEdit { font-size: 11px; padding: 3px 6px; }
QTextEdit { font-size: 11px; }
QComboBox { font-size: 11px; }
"""


class BotTab:
    def __init__(self, master, parent_tab):
        self.master = master
        self.parent = parent_tab
        self.groups = {}
        self.setup_ui()
        self._load_items("app", "1")
        self._load_items("web", "1")
        self._load_items("quick", "1")

    def setup_ui(self):
        layout = QVBoxLayout(self.parent)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #444; background: #1a1a2e; }
            QTabBar::tab { background: #2d2d44; color: #aaa; padding: 6px 14px; margin-right: 2px; border-radius: 4px 4px 0 0; font-size: 11px; }
            QTabBar::tab:selected { background: #4a4a6a; color: #fff; font-weight: bold; }
        """)

        self.groups["app"] = self._build_group("APP", APP_DB_PATH, push_to_web=False)
        self.groups["web"] = self._build_group("WEB", WEB_DB_PATH, push_to_web=True)
        self.groups["quick"] = self._build_group("QUICK", QS_DB_PATH, push_to_web=False)
        tabs.addTab(self.groups["app"]["tab"], "APP Tarama")
        tabs.addTab(self.groups["web"]["tab"], "WEB Tarama")
        tabs.addTab(self.groups["quick"]["tab"], "Hizli Tarama")
        layout.addWidget(tabs)

    def _build_group(self, label, db_path, push_to_web=False):
        tab = QWidget()
        tab.setStyleSheet(COMPACT_STYLE)
        ml = QHBoxLayout(tab)
        ml.setSpacing(6)
        ml.setContentsMargins(6, 6, 6, 6)

        col1 = QVBoxLayout()
        col1.setSpacing(4)

        top_frame = QHBoxLayout()
        top_frame.setSpacing(6)

        db_frame = QHBoxLayout()
        db_frame.setSpacing(4)
        lbl = QLabel("DB:")
        lbl.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 11px;")
        db_frame.addWidget(lbl)
        db_combo = QComboBox()
        db_combo.setMinimumWidth(100)
        db_combo.setStyleSheet("background:#f0f0f0;padding:2px 6px;border-radius:4px;font-size:11px;")
        db_combo.addItem("app_data.db", APP_DB_PATH)
        db_combo.addItem("custom...")
        db_frame.addWidget(db_combo)
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(24)
        btn_browse.setStyleSheet("background:#666;color:white;font-weight:bold;font-size:10px;")
        db_frame.addWidget(btn_browse)
        db_path_label = QLabel(os.path.basename(db_path))
        db_path_label.setStyleSheet("color:#aaa;font-size:10px;")
        db_frame.addWidget(db_path_label)
        top_frame.addLayout(db_frame)

        slot_frame = QHBoxLayout()
        slot_frame.setSpacing(4)
        slot_lbl = QLabel("Kayit:")
        slot_lbl.setStyleSheet("color:#f39c12;font-weight:bold;font-size:11px;")
        slot_frame.addWidget(slot_lbl)
        slot_combo = QComboBox()
        slot_combo.setFixedWidth(60)
        slot_combo.setStyleSheet("background:#f0f0f0;padding:2px;border-radius:4px;font-size:11px;")
        slot_combo.addItem("1")
        slot_combo.addItem("2")
        slot_frame.addWidget(slot_combo)
        top_frame.addLayout(slot_frame)

        top_frame.addStretch()
        col1.addLayout(top_frame)

        srv_group = QGroupBox("Sunucu")
        sg = QGridLayout()
        sg.setSpacing(2)
        server_vars = {}
        for i, n in enumerate(self.master.server_targets.keys()):
            cb = QCheckBox(n)
            cb.setChecked(n.startswith("Tüm"))
            server_vars[n] = cb
            sg.addWidget(cb, i // 3, i % 3)
        srv_group.setLayout(sg)
        col1.addWidget(srv_group)

        lvl_group = QGroupBox("Seviye")
        lg = QGridLayout()
        lg.setSpacing(2)
        lvl_vars = {}
        for i, lvl in enumerate(self.master.lvl_options):
            cb = QCheckBox(lvl)
            lvl_vars[lvl] = cb
            lg.addWidget(cb, i // 6, i % 6)
        lvl_group.setLayout(lg)
        col1.addWidget(lvl_group)

        col2 = QVBoxLayout()
        col2.setSpacing(4)

        ef = QHBoxLayout()
        ef.setSpacing(4)
        ef.addWidget(QLabel("Item:"))
        entry = QLineEdit()
        entry.setPlaceholderText("Raptor, Iron Impact...")
        entry.setFixedHeight(26)
        ef.addWidget(entry)
        btn_add = QPushButton("+")
        btn_add.setFixedSize(26, 26)
        btn_add.setStyleSheet("background:#2ecc71;color:white;font-weight:bold;font-size:14px;")
        ef.addWidget(btn_add)
        col2.addLayout(ef)

        list_box = QTextEdit()
        list_box.setReadOnly(True)
        list_box.setPlaceholderText("Liste bos - item ekleyin")
        col2.addWidget(list_box)

        btn_clear = QPushButton("LISTEYI TEMIZLE")
        btn_clear.setFixedHeight(22)
        btn_clear.setStyleSheet("background:#e74c3c;color:white;font-size:10px;")
        col2.addWidget(btn_clear)

        rf = QFrame()
        rf.setFixedWidth(240)
        rl = QVBoxLayout(rf)
        rl.setSpacing(4)

        rl.addWidget(QLabel("Log"))
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        log_box.setStyleSheet("font-family:Consolas;font-size:10px;")
        rl.addWidget(log_box)

        btn_start = QPushButton("TARAMAYI BASLAT")
        btn_start.setFixedHeight(34)
        btn_start.setStyleSheet("font-size:11px;font-weight:bold;")
        rl.addWidget(btn_start)

        btn_stop = QPushButton("DURDUR")
        btn_stop.setFixedHeight(26)
        btn_stop.setStyleSheet("background:#e74c3c;color:white;font-size:10px;font-weight:bold;")
        btn_stop.setEnabled(False)
        rl.addWidget(btn_stop)

        af = QHBoxLayout()
        af.setSpacing(4)
        switch_auto = QCheckBox("Oto")
        auto_mode = QComboBox()
        auto_mode.addItems(["Liste Taramasi", "Tum Verileri Cek"])
        auto_mode.setStyleSheet("background:#f0f0f0;padding:2px;border-radius:4px;font-size:10px;")
        auto_mode.setFixedWidth(110)
        entry_time = QLineEdit("45")
        entry_time.setFixedWidth(32)
        entry_time.setFixedHeight(22)
        af.addWidget(switch_auto)
        af.addWidget(auto_mode)
        af.addWidget(entry_time)
        af.addWidget(QLabel("dk"))
        af.addStretch()
        rl.addLayout(af)

        rl.addWidget(QLabel("Toplu Cekme"))
        tf = QHBoxLayout()
        tf.setSpacing(4)
        btn_fetch = QPushButton("TÜM İTEMLARI ÇEK")
        btn_fetch.setFixedHeight(28)
        btn_fetch.setStyleSheet("background:#8e44ad;color:white;font-weight:bold;font-size:10px;")
        tf.addWidget(btn_fetch)
        switch_repeat = QCheckBox("Tekrar")
        switch_repeat.setStyleSheet("color:#e74c3c;font-weight:bold;font-size:10px;")
        tf.addWidget(switch_repeat)
        tf.addStretch()
        rl.addLayout(tf)

        lbl_status = QLabel("")
        lbl_status.setStyleSheet("color:#aaa;font-size:10px;")
        lbl_status.setWordWrap(True)
        rl.addWidget(lbl_status)

        ml.addLayout(col1)
        ml.addLayout(col2, stretch=1)
        ml.addWidget(rf)

        g = {
            "tab": tab, "key": label.lower(), "db_path": db_path, "push_to_web": push_to_web,
            "server_vars": server_vars, "lvl_vars": lvl_vars, "entry": entry,
            "list_box": list_box, "log_box": log_box, "btn_start": btn_start, "btn_stop": btn_stop,
            "btn_fetch": btn_fetch, "lbl_status": lbl_status, "switch_auto": switch_auto,
            "switch_repeat": switch_repeat,
            "entry_time": entry_time, "scan_queue": [], "stop": threading.Event(),
            "db_combo": db_combo, "btn_browse": btn_browse, "db_path_label": db_path_label,
            "auto_mode": auto_mode, "slot_combo": slot_combo,
        }
        tab._g = g

        list_box.mouseDoubleClickEvent = lambda e: self._remove_selected_item(g)

        btn_add.clicked.connect(lambda: self._add_item(g))
        btn_clear.clicked.connect(lambda: self._clear_list(g))
        btn_start.clicked.connect(lambda: self._start_scan(g))
        btn_stop.clicked.connect(lambda: self._stop_scan(g))
        btn_fetch.clicked.connect(lambda: self._start_fetch_all(g))
        switch_auto.stateChanged.connect(lambda: self._auto_scan_changed(g))
        db_combo.currentIndexChanged.connect(lambda: self._db_combo_changed(g))
        btn_browse.clicked.connect(lambda: self._browse_db(g))
        slot_combo.currentIndexChanged.connect(lambda: self._slot_changed(g))

        return g

    def _log(self, g, msg):
        formatted = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        if threading.current_thread() is threading.main_thread():
            g["log_box"].append(formatted)
        else:
            QTimer.singleShot(0, lambda m=formatted: g["log_box"].append(m))

    def _add_item(self, g):
        name = g["entry"].text().strip()
        lvls = [l for l, v in g["lvl_vars"].items() if v.isChecked()]
        if name and lvls:
            g["scan_queue"].append({"item": name, "lvls": lvls})
            g["list_box"].append(f"* {name} ({','.join(lvls)})")
            g["entry"].clear()
            self._save_items(g)

    def _remove_selected_item(self, g):
        cursor = g["list_box"].textCursor()
        cursor.select(cursor.SelectionType.BlockUnderCursor)
        selected = cursor.selectedText().strip()
        if not selected:
            return
        for i, task in enumerate(g["scan_queue"]):
            display = f"* {task['item']} ({','.join(task['lvls'])})"
            if display.strip() == selected.strip():
                g["scan_queue"].pop(i)
                self._refresh_list(g)
                self._save_items(g)
                self._log(g, f"Kaldirildi: {task['item']} ({','.join(task['lvls'])})")
                break

    def _refresh_list(self, g):
        g["list_box"].clear()
        for t in g["scan_queue"]:
            g["list_box"].append(f"* {t['item']} ({','.join(t['lvls'])})")

    def _clear_list(self, g):
        g["scan_queue"] = []
        g["list_box"].clear()
        self._save_items(g)

    def _save_items(self, g):
        try:
            slot = g["slot_combo"].currentText()
            path = os.path.join(self.master.BASE_DIR, f"kayitli_{g['key']}_{slot}.txt")
            with open(path, "w", encoding="utf-8") as f:
                for t in g["scan_queue"]:
                    f.write(f"{t['item']}:{','.join(t['lvls'])}\n")
        except:
            pass

    def _load_items(self, key, slot="1"):
        path = os.path.join(self.master.BASE_DIR, f"kayitli_{key}_{slot}.txt")
        if os.path.exists(path):
            try:
                g = self.groups[key]
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            it, ls = line.strip().split(":", 1)
                            g["scan_queue"].append({"item": it, "lvls": ls.split(",")})
                            g["list_box"].append(f"* {it} ({ls})")
            except:
                pass

    def _slot_changed(self, g):
        g["scan_queue"] = []
        g["list_box"].clear()
        slot = g["slot_combo"].currentText()
        self._load_items(g["key"], slot)
        self._log(g, f"Kayit slot {slot} yuklendi ({len(g['scan_queue'])} item)")

    def _check_api_key(self):
        if not self.master.engine.api_client.api_key:
            QMessageBox.warning(self.master, "Uyari", "API key tanimli degil!")
            return False
        return True

    def _start_scan(self, g):
        if not self._check_api_key():
            return
        g["stop"].clear()
        g["btn_stop"].setEnabled(True)
        threading.Thread(target=self._run_scan, args=(g,), daemon=True).start()

    def _stop_scan(self, g):
        self._log(g, "Durduruluyor...")
        g["stop"].set()
        g["btn_stop"].setEnabled(False)
        g["btn_stop"].setText("DURDURULUYOR...")
        g["btn_start"].setEnabled(True)
        g["btn_start"].setText("TARAMAYI BASLAT")
        g["btn_fetch"].setEnabled(True)
        g["btn_fetch"].setText("TÜM İTEMLARI ÇEK")

    def _run_scan(self, g, single_task=None):
        servers = [n for n, v in g["server_vars"].items() if v.isChecked()]
        queue = [single_task] if single_task else g["scan_queue"]
        if not servers or not queue:
            self._log(g, "Sunucu veya liste bos!")
            g["btn_stop"].setEnabled(False)
            return

        g["btn_start"].setEnabled(False)
        g["btn_start"].setText("TARANIYOR...")
        cancelled = False
        start_time = time.time()
        total_items = sum(len(t["lvls"]) for t in queue)

        self._log(g, "=" * 40)
        self._log(g, f"TARAMA BASLADI")
        self._log(g, f"  Item sayisi: {len(queue)} ({total_items} seviye)")
        self._log(g, f"  Sunucular: {', '.join(servers)}")
        self._log(g, f"  Hedef DB: {os.path.basename(g['db_path'])}")
        self._log(g, "=" * 40)

        server_results = {}
        server_counts = {}

        def worker(srv):
            nonlocal cancelled
            all_r = []
            self._log(g, f"[{srv}] Tarama basliyor...")
            scanned = 0
            for task in queue:
                if g["stop"].is_set():
                    cancelled = True
                    return
                for lvl in task["lvls"]:
                    if g["stop"].is_set():
                        cancelled = True
                        return
                    scanned += 1
                    try:
                        from core.engine import parse_level
                        plus_val, is_rev = parse_level(lvl)
                        res = self.master.engine.scan_single_server(srv, task["item"], plus_val if plus_val else None, g["stop"], rebirth=is_rev)
                        if res:
                            all_r.extend(res)
                    except Exception as e:
                        self._log(g, f"[{srv}] HATA: {task['item']} {lvl} -> {e}")
                    time.sleep(0.5)
            server_results[srv] = all_r
            server_counts[srv] = len(all_r)
            self._log(g, f"[{srv}] TAMAMLANDI - {len(all_r)} kayit")

        threads = [threading.Thread(target=worker, args=(s,), daemon=False) for s in servers]
        for t in threads:
            t.start()
        while any(t.is_alive() for t in threads) and not g["stop"].is_set():
            time.sleep(0.5)

        duration = time.time() - start_time
        total_results = sum(server_counts.values())

        self._log(g, "")
        self._log(g, "=" * 40)
        if not cancelled:
            self._log(g, f"TARAMA TAMAMLANDI!")
            self._log(g, f"  Sure: {int(duration // 60)}dk {int(duration % 60)}sn")
            self._log(g, f"  Toplam sonuc: {total_results} kayit")
            for srv, cnt in server_counts.items():
                self._log(g, f"    {srv}: {cnt} kayit")
            self._log(g, f"  Hedef: {os.path.basename(g['db_path'])}")

            all_results = []
            for srv_results in server_results.values():
                all_results.extend(srv_results)
            if all_results:
                self._log(g, f"  Veritabanina kaydediliyor...")
                self._save_to_db(all_results, g["db_path"], g["log_box"])
                if g["push_to_web"]:
                    self._log(g, f"  Web sunucusuna gonderiliyor...")
                    self._push_web(all_results)

            self._log(g, "=" * 40)
            self.master.update_autocomplete_data()
        else:
            self._log(g, f"TARAMA DURDURULDU! ({int(duration)}sn sonra)")
            self._log(g, f"  O ana kadar: {total_results} kayit")
            self._log(g, "=" * 40)

        with self.master.stats_cache_lock:
            self.master.stats_cache.clear()
        self.master.update_opportunity_list()
        g["btn_start"].setEnabled(True)
        g["btn_start"].setText("TARAMAYI BASLAT")
        g["btn_stop"].setEnabled(False)
        g["btn_stop"].setText("DURDUR")

    def _auto_scan_changed(self, g):
        if g["switch_auto"].isChecked():
            servers = [n for n, v in g["server_vars"].items() if v.isChecked()]
            if not servers:
                self._log(g, "Otomatik tarama: Once sunucu secin!")
                g["switch_auto"].setChecked(False)
                return
            self._log(g, "Otomatik tarama AKTIF edildi.")
            self._auto_loop(g)
        else:
            self._log(g, "Otomatik tarama pasif.")

    def _db_combo_changed(self, g):
        idx = g["db_combo"].currentIndex()
        text = g["db_combo"].currentText()
        if text == "custom...":
            self._browse_db(g)
            return
        new_path = g["db_combo"].itemData(idx)
        if new_path:
            g["db_path"] = new_path
            g["db_path_label"].setText(os.path.basename(new_path))
            self._log(g, f"DB degistirildi: {os.path.basename(new_path)}")

    def _browse_db(self, g):
        path, _ = QFileDialog.getOpenFileName(
            g["tab"], "Veritabani Sec", _base, "SQLite DB (*.db);;Tum Dosyalar (*)")
        if path:
            g["db_path"] = path
            g["db_path_label"].setText(os.path.basename(path))
            g["db_combo"].blockSignals(True)
            g["db_combo"].addItem(os.path.basename(path), path)
            g["db_combo"].setCurrentIndex(g["db_combo"].count() - 1)
            g["db_combo"].blockSignals(False)
            self._log(g, f"DB secildi: {os.path.basename(path)}")

    def _auto_loop(self, g):
        if not g["switch_auto"].isChecked():
            return
        try:
            mins = max(1, int(g["entry_time"].text()))
        except:
            mins = 45

        servers = [n for n, v in g["server_vars"].items() if v.isChecked()]
        if not servers:
            self._log(g, "Otomatik tarama: Sunucu secilmedi! Durduruldu.")
            g["switch_auto"].setChecked(False)
            return

        mode = g["auto_mode"].currentText()
        if mode == "Liste Taramasi":
            queue = g["scan_queue"]
            if not queue:
                self._log(g, "Otomatik tarama: Liste bos! Tarama listesine item ekleyin.")
                g["switch_auto"].setChecked(False)
                return
            self._log(g, f"Otomatik tarama: Listeden {len(queue)} item taranacak ({mins}dk aralikla)")
            self._start_scan(g)
        else:
            self._log(g, f"Otomatik tarama: Tum verileri cekilecek ({mins}dk aralikla)")
            self._start_fetch_all(g)

        QTimer.singleShot(mins * 60 * 1000, lambda: self._auto_loop(g))

    def _start_fetch_all(self, g):
        if not self._check_api_key():
            return
        g["btn_fetch"].setEnabled(False)
        g["btn_fetch"].setText("CEKILIYOR...")
        g["btn_stop"].setEnabled(True)
        g["btn_stop"].setText("DURDUR")
        g["stop"].clear()
        threading.Thread(target=self._run_fetch_all, args=(g,), daemon=True).start()

    def _run_fetch_all(self, g):
        start_time = time.time()
        servers = [n for n, v in g["server_vars"].items() if v.isChecked()]
        if not servers:
            self._log(g, "En az bir sunucu secin!")
            return

        self._log(g, "=" * 40)
        self._log(g, "TUM ITEMLAR CEKILIYOR")
        self._log(g, f"  Sunucular: {', '.join(servers)}")
        self._log(g, f"  Hedef DB: {os.path.basename(g['db_path'])}")
        self._log(g, "=" * 40)

        server_totals = {}

        def on_progress(msg, cnt):
            parts = msg.split("|")
            if parts[0] == "SERVER_START":
                srv = parts[1]
                idx = parts[2]
                total = parts[3]
                self._log(g, f"[{srv}] Taraniyor... ({idx}/{total})")
            elif parts[0] == "SERVER_DONE":
                srv = parts[1]
                count = int(parts[2])
                server_totals[srv] = count
                self._log(g, f"[{srv}] TAMAMLANDI - {count} item")
            QTimer.singleShot(0, lambda c=cnt: g["lbl_status"].setText(f"Toplam: {c} item"))

        try:
            results = self.master.engine.api_client.fetch_all_servers(
                server_names=servers, progress_callback=on_progress, stop_event=g["stop"],
                levels=list(range(11)), reverse_levels=list(range(1, 22)))
            duration = time.time() - start_time
            if results:
                self._log(g, "")
                self._log(g, "=" * 40)
                self._log(g, "TUM ITEMLAR TAMAMLANDI!")
                self._log(g, f"  Sure: {int(duration // 60)}dk {int(duration % 60)}sn")
                self._log(g, f"  Toplam: {len(results)} item cekildi")
                for srv, cnt in server_totals.items():
                    self._log(g, f"    {srv}: {cnt} item")
                self._log(g, f"  Hedef: {os.path.basename(g['db_path'])}")
                self._log(g, f"  Veritabanina kaydediliyor...")
                self._save_to_db(results, g["db_path"], g["log_box"])
                if g["push_to_web"]:
                    self._log(g, f"  Web sunucusuna gonderiliyor...")
                    self._push_web(results)
                self.master.update_autocomplete_data()
                self._log(g, "=" * 40)
            else:
                self._log(g, "Sonuc bulunamadi.")
        except Exception as e:
            self._log(g, f"Hata: {e}")
        finally:
            g["btn_fetch"].setEnabled(True)
            g["btn_fetch"].setText("TÜM İTEMLARI ÇEK")
            g["lbl_status"].setText("")
            if g.get("switch_repeat") and g["switch_repeat"].isChecked():
                self._log(g, "Tekrar basliyor...")
                QTimer.singleShot(3000, lambda: self._start_fetch_all(g))

    def _push_web(self, results):
        if not _req or not results:
            return
        batch = []
        for r in results:
            pt = "buy" if r.get("Pazar Tipi", "").lower() == "buy" else "sell"
            batch.append({
                "item": r.get("Item Adi", r.get("İtem Adı", "")),
                "lvl": r.get("Arti", r.get("Artı", "")),
                "price": r.get("Fiyat", 0),
                "type": pt,
                "server": r.get("Sunucu", ""),
            })
        try:
            token = self._get_token()
            headers = {"Content-Type": "application/json"}
            if token:
                headers["X-API-Token"] = token
            resp = _req.post(f"{WEB_SERVER_URL}/api/push", json={"prices": batch}, headers=headers, timeout=30)
            if resp.status_code == 200:
                self._log(self.groups["web"], f"Web'e {resp.json().get('inserted', 0)} kayit gonderildi.")
            else:
                self._log(self.groups["web"], f"Web hatasi: {resp.status_code}")
        except Exception as e:
            self._log(self.groups["web"], f"Web baglanti hatasi: {e}")

    def _get_token(self):
        try:
            sp = os.path.join(_base, "security.json")
            if os.path.exists(sp):
                with open(sp, "r") as f:
                    sec = json.load(f)
                t = sec.get("api_token", "")
                if sec.get("api_token_encrypted") and t:
                    from core.config import CryptoManager
                    t = CryptoManager.decrypt(t)
                return t
        except:
            pass
        return ""

    def _save_to_db(self, results, db_path, log_box):
        try:
            from core.engine import should_skip_record, is_reverse_level
            conn = sqlite3.connect(db_path, timeout=15)
            conn.execute("PRAGMA busy_timeout=15000")
            cur = conn.cursor()
            ins = 0
            skip = 0
            filtered = 0
            for r in results:
                name = (r.get("İtem Adı", "") or "").strip()
                if not name:
                    continue
                lvl = (r.get("Artı", "+0") or "+0").strip()
                if not lvl:
                    lvl = "+0"
                ptype = "buy" if (r.get("Pazar Tipi", "") or "").lower() == "buy" else "sell"
                price = r.get("Fiyat", 0)
                server = r.get("Sunucu", "")
                ts = r.get("Zaman", "")
                seller = str(r.get("UserID", "") or "").strip()
                m = re.search(r"^(.*?)[\s]*\+([0-9]+)(R?)\s*$", name)
                if m:
                    name = m.group(1).strip()
                    lvl = "+" + m.group(2) + m.group(3)
                name = re.sub(r"\(\+?[0-9]+R?\)\s*$", "", name).strip()

                if seller:
                    cur.execute("SELECT id, price FROM prices WHERE item_name=? AND item_lvl=? AND type=? AND server=? AND seller=?",
                                (name, lvl, ptype, server, seller))
                    ex = cur.fetchone()
                    if ex:
                        if price < ex[1]:
                            cur.execute("UPDATE prices SET price=?, last_seen=? WHERE id=?", (price, ts, ex[0]))
                        else:
                            cur.execute("UPDATE prices SET last_seen=? WHERE id=?", (ts, ex[0]))
                        skip += 1
                        continue
                cur.execute("SELECT COUNT(*) FROM prices WHERE item_name=? AND item_lvl=? AND type=? AND server=? AND price=? AND timestamp=?",
                            (name, lvl, ptype, server, price, ts))
                if cur.fetchone()[0] > 0:
                    skip += 1
                    continue
                cur.execute("INSERT INTO prices (server,type,item_name,item_lvl,price,timestamp,seller,last_seen) VALUES (?,?,?,?,?,?,?,?)",
                            (server, ptype, name, lvl, price, ts, seller, ts))
                ins += 1
            conn.commit()
            conn.close()
            log_box.append(f"[{datetime.now().strftime('%H:%M:%S')}] Yeni: {ins} | Tekrar: {skip} | Filtre(+0): {filtered}")
        except Exception as e:
            log_box.append(f"[{datetime.now().strftime('%H:%M:%S')}] DB hatasi: {e}")
