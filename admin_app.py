import sys
import os
import sqlite3
import shutil
import json
import urllib.request
import urllib.error
import bcrypt
import secrets
from datetime import datetime
from core.config import CryptoManager
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
                              QComboBox, QLabel, QTabWidget, QMessageBox, QHeaderView,
                              QFrame, QSplitter, QGroupBox, QFormLayout, QSpinBox, QTextEdit)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyzer_config.json")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyzer_config.json")
WEB_URL = "http://127.0.0.1:8765"
try:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as _f:
            _cfg2 = json.load(_f)
        WEB_URL = f"http://127.0.0.1:{_cfg2.get('web_port', 8765)}"
except:
    pass

def _get_local_ip():
    try:
        candidates = []
        for info in __import__('socket').getaddrinfo(__import__('socket').gethostname(), None, __import__('socket').AF_INET):
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

DARK_STYLE = """
QMainWindow { background: #0a0a12; }
QWidget { background: #0a0a12; color: #e0e0e0; font-family: 'Segoe UI'; }
QTabWidget::pane { border: 1px solid #1e1e2e; background: #0a0a12; }
QTabBar::tab { background: #12121e; color: #888; padding: 8px 20px; border: 1px solid #1e1e2e; border-bottom: none; border-radius: 6px 6px 0 0; margin-right: 2px; }
QTabBar::tab:selected { background: #1a1a2e; color: #00d4ff; border-bottom: 2px solid #00d4ff; }
QTabBar::tab:hover { background: #1a1a2e; color: #ccc; }
QTableWidget { background: #0d0d1a; gridline-color: #1e1e2e; border: 1px solid #1e1e2e; border-radius: 8px; selection-background-color: #1a1a3e; color: #e0e0e0; }
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background: #1a1a3e; color: #00d4ff; }
QHeaderView::section { background: #12121e; color: #00d4ff; padding: 6px 10px; border: 1px solid #1e1e2e; font-weight: bold; font-size: 11px; }
QPushButton { background: #1a1a2e; color: #e0e0e0; border: 1px solid #2a2a3e; padding: 8px 16px; border-radius: 6px; font-weight: bold; }
QPushButton:hover { background: #2a2a3e; border-color: #00d4ff; }
QPushButton:pressed { background: #00d4ff; color: #000; }
QPushButton#danger { background: #3a1520; color: #ff4757; border-color: #ff4757; }
QPushButton#danger:hover { background: #ff4757; color: #fff; }
QPushButton#success { background: #0a2a1a; color: #00ff96; border-color: #00ff96; }
QPushButton#success:hover { background: #00ff96; color: #000; }
QPushButton#warn { background: #2a2010; color: #ffa502; border-color: #ffa502; }
QPushButton#warn:hover { background: #ffa502; color: #000; }
QLineEdit { background: #0d0d1a; color: #e0e0e0; border: 1px solid #1e1e2e; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
QLineEdit:focus { border-color: #00d4ff; }
QComboBox { background: #0d0d1a; color: #e0e0e0; border: 1px solid #1e1e2e; padding: 8px 12px; border-radius: 6px; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: #12121e; color: #e0e0e0; selection-background-color: #1a1a3e; }
QLabel { color: #e0e0e0; }
QGroupBox { border: 1px solid #1e1e2e; border-radius: 8px; margin-top: 12px; padding-top: 16px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; padding: 0 8px; color: #00d4ff; }
QTextEdit { background: #0d0d1a; color: #e0e0e0; border: 1px solid #1e1e2e; border-radius: 8px; font-family: Consolas; font-size: 12px; }
QSpinBox { background: #0d0d1a; color: #e0e0e0; border: 1px solid #1e1e2e; padding: 6px; border-radius: 6px; }
"""


class AdminLoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Master - Admin Giris")
        self.setFixedSize(380, 250)
        self.setStyleSheet(DARK_STYLE)

        container = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        container.setLayout(layout)
        self.setCentralWidget(container)

        title = QLabel("ADMIN PANEL GIRIS")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00d4ff;")
        layout.addWidget(title)
        layout.addSpacing(20)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Admin Sifresi")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setFixedWidth(280)
        self.pass_input.setStyleSheet("padding: 10px; font-size: 14px;")
        self.pass_input.returnPressed.connect(self.attempt_login)
        layout.addWidget(self.pass_input, alignment=Qt.AlignCenter)

        layout.addSpacing(10)

        btn = QPushButton("GIRIS YAP")
        btn.setFixedWidth(280)
        btn.setFixedHeight(36)
        btn.setStyleSheet("background-color: #00d4ff; color: #000; font-size: 14px; font-weight: bold;")
        btn.clicked.connect(self.attempt_login)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

    def attempt_login(self):
        password = self.pass_input.text()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyzer_config.json")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            stored = config.get("admin_password", "")
            if not stored:
                QMessageBox.critical(self, "Hata", "Sifre tanimlanmamis!")
                return
            try:
                valid = bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except:
                valid = password == stored
            if valid:
                self.admin_panel = AdminPanel()
                self.admin_panel.show()
                self.close()
            else:
                QMessageBox.critical(self, "Hata", "Hatali sifre!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))


class AdminPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Master - Admin Panel")
        self.setGeometry(100, 100, 1200, 750)
        self.setStyleSheet(DARK_STYLE)

        self._idle_timer = QTimer()
        self._idle_timer.timeout.connect(self._on_idle)
        self._idle_timer.start(30 * 60 * 1000)
        self._last_activity = datetime.now()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.create_items_tab()
        self.create_prices_tab()
        self.create_sellers_tab()
        self.create_cleanup_tab()
        self.create_backup_tab()
        self.create_ratelimit_tab()
        self.create_api_logs_tab()
        self.create_threats_tab()
        self.create_permissions_tab()
        self.create_settings_tab()

        self.tabs.currentChanged.connect(self.on_tab_changed)

    def _on_idle(self):
        elapsed = (datetime.now() - self._last_activity).total_seconds()
        if elapsed > 30 * 60:
            reply = QMessageBox.question(self, "Oturum Zaman Asimi",
                "30 dakika aktivite yok. Cikis yapilsin mi?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.close()
            else:
                self._last_activity = datetime.now()

    def eventFilter(self, obj, event):
        self._last_activity = datetime.now()
        return super().eventFilter(obj, event)

    def mouseMoveEvent(self, event):
        self._last_activity = datetime.now()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        self._last_activity = datetime.now()
        super().keyPressEvent(event)

    def get_db(self):
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def get_servers(self):
        try:
            conn = self.get_db()
            rows = conn.execute("SELECT DISTINCT server FROM prices ORDER BY server").fetchall()
            conn.close()
            return [r[0] for r in rows]
        except:
            return []

    def on_tab_changed(self, idx):
        tab_names = ["items", "prices", "sellers", "cleanup", "backup", "ratelimit", "apilogs", "threats", "permissions", "settings"]
        if idx < len(tab_names):
            name = tab_names[idx]
            if name == "backup":
                self.load_backups()
            elif name == "ratelimit":
                self.load_rate_stats()
            elif name == "apilogs":
                self.load_api_logs()
            elif name == "threats":
                self.load_threats()
            elif name == "permissions":
                self.load_permissions()

    # ========== ITEMS TAB ==========
    def create_items_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QHBoxLayout()
        lbl = QLabel("Item Yonetimi")
        lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl.setStyleSheet("color: #00d4ff;")
        header.addWidget(lbl)
        header.addStretch()
        layout.addLayout(header)

        # Search bar
        search_frame = QGroupBox("Sorgula")
        search_layout = QHBoxLayout()

        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Item adi (orn: raptor, draki...)")
        search_layout.addWidget(self.item_search, 3)

        self.item_server_filter = QComboBox()
        self.item_server_filter.addItem("Tum Sunucular")
        self.item_server_filter.addItems(self.get_servers())
        self.item_server_filter.setMaximumWidth(150)
        search_layout.addWidget(self.item_server_filter, 1)

        self.item_type_filter = QComboBox()
        self.item_type_filter.addItems(["Tumu", "SELL", "BUY"])
        self.item_type_filter.setMaximumWidth(80)
        search_layout.addWidget(self.item_type_filter, 1)

        btn_search = QPushButton("Sorgula")
        btn_search.setObjectName("success")
        btn_search.clicked.connect(self.search_items)
        search_layout.addWidget(btn_search)

        search_frame.setLayout(search_layout)
        layout.addWidget(search_frame)

        # Result info
        self.item_result_label = QLabel("Sonuc yok - yukaridaki alandan sorgulayin")
        self.item_result_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.item_result_label)

        # Table
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(6)
        self.item_table.setHorizontalHeaderLabels(["Item", "Lvl", "Sunucu", "Tip", "En Son Fiyat", "Kayit"])
        self.item_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.item_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.item_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        layout.addWidget(self.item_table)

        btn_row = QHBoxLayout()
        btn_del = QPushButton("Secileni Sil")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self.delete_selected_item)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)

        self.all_items = []
        self.tabs.addTab(tab, "Item Yonetimi")

    def search_items(self):
        q = self.item_search.text().strip()
        server = self.item_server_filter.currentText()
        tip = self.item_type_filter.currentText()

        query = """
            SELECT item_name, item_lvl, server, type,
                   (SELECT price FROM prices p2 WHERE p2.item_name=p1.item_name AND p2.item_lvl=p1.item_lvl AND p2.server=p1.server AND p2.type=p1.type ORDER BY timestamp DESC LIMIT 1) as price,
                   COUNT(*) as count
            FROM prices p1
            WHERE 1=1
        """
        params = []

        if q:
            query += " AND item_name LIKE ?"
            params.append(f"%{q}%")
        if server != "Tum Sunucular":
            query += " AND server = ?"
            params.append(server)
        if tip != "Tumu":
            query += " AND type = ?"
            params.append(tip.lower())

        query += " GROUP BY item_name, item_lvl, server, type ORDER BY item_name LIMIT 200"

        try:
            conn = self.get_db()
            rows = conn.execute(query, params).fetchall()
            conn.close()
            self.all_items = [dict(r) for r in rows]
            self.render_items(self.all_items)
            self.item_result_label.setText(f"{len(self.all_items)} sonuc bulundu")
            self.item_result_label.setStyleSheet("color: #00ff96; padding: 5px;" if self.all_items else "color: #ff4757; padding: 5px;")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def render_items(self, items):
        self.item_table.setRowCount(len(items))
        for i, item in enumerate(items):
            self.item_table.setItem(i, 0, QTableWidgetItem(item["item_name"] or ""))
            self.item_table.setItem(i, 1, QTableWidgetItem(item["item_lvl"] or "Temel"))
            self.item_table.setItem(i, 2, QTableWidgetItem(item["server"] or ""))
            tip = QTableWidgetItem((item["type"] or "").upper())
            tip.setForeground(QColor("#00d4ff") if item["type"] == "sell" else QColor("#ff4757"))
            self.item_table.setItem(i, 3, tip)
            self.item_table.setItem(i, 4, QTableWidgetItem(f"{(item['price'] or 0):,}"))
            self.item_table.setItem(i, 5, QTableWidgetItem(str(item["count"])))

    def delete_selected_item(self):
        row = self.item_table.currentRow()
        if row < 0:
            return
        item = self.all_items[row] if row < len(self.all_items) else None
        if not item:
            return
        reply = QMessageBox.question(self, "Silme Onayi",
                                     f"{item['item_name']} ({item['server']}) silinecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                conn = self.get_db()
                conn.execute("DELETE FROM prices WHERE item_name=? AND item_lvl=? AND server=? AND type=?",
                             (item["item_name"], item["item_lvl"], item["server"], item["type"]))
                conn.commit()
                conn.close()
                self.search_items()
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    # ========== PRICES TAB ==========
    def create_prices_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("Fiyat Kontrolu")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        # Search
        search_group = QGroupBox("Fiyat Sorgula")
        search_layout = QHBoxLayout()

        self.pr_search = QLineEdit()
        self.pr_search.setPlaceholderText("Item adi")
        search_layout.addWidget(self.pr_search, 3)

        self.pr_server_filter = QComboBox()
        self.pr_server_filter.addItem("Tum Sunucular")
        self.pr_server_filter.addItems(self.get_servers())
        self.pr_server_filter.setMaximumWidth(150)
        search_layout.addWidget(self.pr_server_filter, 1)

        btn_pr_search = QPushButton("Sorgula")
        btn_pr_search.setObjectName("success")
        btn_pr_search.clicked.connect(self.search_prices)
        search_layout.addWidget(btn_pr_search)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        self.pr_result_label = QLabel("Sonuc yok")
        self.pr_result_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.pr_result_label)

        self.price_table = QTableWidget()
        self.price_table.setColumnCount(7)
        self.price_table.setHorizontalHeaderLabels(["ID", "Item", "Lvl", "Fiyat", "Tip", "Sunucu", "Zaman"])
        self.price_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.price_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.price_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.price_table.verticalHeader().setVisible(False)
        layout.addWidget(self.price_table)

        btn_row = QHBoxLayout()
        btn_del = QPushButton("Secileni Sil")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self.delete_selected_price)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)

        self.all_prices = []
        self.tabs.addTab(tab, "Fiyat Kontrolu")

    def search_prices(self):
        q = self.pr_search.text().strip()
        server = self.pr_server_filter.currentText()

        query = "SELECT id, item_name, item_lvl, price, type, server, timestamp FROM prices WHERE 1=1"
        params = []

        if q:
            query += " AND item_name LIKE ?"
            params.append(f"%{q}%")
        if server != "Tum Sunucular":
            query += " AND server = ?"
            params.append(server)

        query += " ORDER BY timestamp DESC LIMIT 200"

        try:
            conn = self.get_db()
            rows = conn.execute(query, params).fetchall()
            conn.close()
            self.all_prices = [dict(r) for r in rows]
            self.render_prices(self.all_prices)
            self.pr_result_label.setText(f"{len(self.all_prices)} sonuc bulundu")
            self.pr_result_label.setStyleSheet("color: #00ff96; padding: 5px;" if self.all_prices else "color: #ff4757; padding: 5px;")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def render_prices(self, rows):
        self.price_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.price_table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.price_table.setItem(i, 1, QTableWidgetItem(r["item_name"] or ""))
            self.price_table.setItem(i, 2, QTableWidgetItem(r["item_lvl"] or "Temel"))
            self.price_table.setItem(i, 3, QTableWidgetItem(f"{r['price']:,}"))
            tip = QTableWidgetItem((r["type"] or "").upper())
            tip.setForeground(QColor("#00d4ff") if r["type"] == "sell" else QColor("#ff4757"))
            self.price_table.setItem(i, 4, tip)
            self.price_table.setItem(i, 5, QTableWidgetItem(r["server"] or ""))
            self.price_table.setItem(i, 6, QTableWidgetItem(r["timestamp"] or ""))

    def delete_selected_price(self):
        row = self.price_table.currentRow()
        if row < 0:
            return
        price_id = self.price_table.item(row, 0).text()
        try:
            conn = self.get_db()
            conn.execute("DELETE FROM prices WHERE id=?", (price_id,))
            conn.commit()
            conn.close()
            self.search_prices()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    # ========== SELLERS TAB ==========
    def create_sellers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QHBoxLayout()
        lbl = QLabel("Seller Izleme")
        lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl.setStyleSheet("color: #00d4ff;")
        header.addWidget(lbl)
        header.addStretch()
        layout.addLayout(header)

        # Search
        search_group = QGroupBox("Seller Sorgula")
        search_layout = QHBoxLayout()

        self.seller_search = QLineEdit()
        self.seller_search.setPlaceholderText("Satisci adi (orn: Xyphen)")
        search_layout.addWidget(self.seller_search, 3)

        self.seller_server_filter = QComboBox()
        self.seller_server_filter.addItem("Tum Sunucular")
        self.seller_server_filter.addItems(self.get_servers())
        self.seller_server_filter.setMaximumWidth(150)
        search_layout.addWidget(self.seller_server_filter, 1)

        btn_seller_search = QPushButton("Sorgula")
        btn_seller_search.setObjectName("success")
        btn_seller_search.clicked.connect(self.search_sellers)
        search_layout.addWidget(btn_seller_search)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        self.seller_result_label = QLabel("Sonuc yok")
        self.seller_result_label.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(self.seller_result_label)

        self.seller_table = QTableWidget()
        self.seller_table.setColumnCount(4)
        self.seller_table.setHorizontalHeaderLabels(["Satisci ID", "Kayit", "Unique Item", "Son Gorunme"])
        self.seller_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.seller_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.seller_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.seller_table.verticalHeader().setVisible(False)
        layout.addWidget(self.seller_table)

        btn_row = QHBoxLayout()
        btn_del = QPushButton("Secileni Sil")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self.delete_selected_seller)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)

        self.all_sellers = []
        self.tabs.addTab(tab, "Seller Izleme")

    def search_sellers(self):
        q = self.seller_search.text().strip()
        server = self.seller_server_filter.currentText()

        query = """
            SELECT seller, COUNT(*) as cnt,
                   COUNT(DISTINCT item_name || item_lvl) as items,
                   MAX(last_seen) as last_seen
            FROM prices WHERE seller != '' AND seller IS NOT NULL
        """
        params = []

        if q:
            query += " AND seller LIKE ?"
            params.append(f"%{q}%")
        if server != "Tum Sunucular":
            query += " AND server = ?"
            params.append(server)

        query += " GROUP BY seller ORDER BY cnt DESC LIMIT 200"

        try:
            conn = self.get_db()
            rows = conn.execute(query, params).fetchall()
            conn.close()
            self.all_sellers = [dict(r) for r in rows]
            self.render_sellers(self.all_sellers)
            self.seller_result_label.setText(f"{len(self.all_sellers)} seller bulundu")
            self.seller_result_label.setStyleSheet("color: #00ff96; padding: 5px;" if self.all_sellers else "color: #ff4757; padding: 5px;")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def render_sellers(self, sellers):
        self.seller_table.setRowCount(len(sellers))
        for i, s in enumerate(sellers):
            self.seller_table.setItem(i, 0, QTableWidgetItem(s["seller"] or ""))
            self.seller_table.setItem(i, 1, QTableWidgetItem(str(s["cnt"])))
            self.seller_table.setItem(i, 2, QTableWidgetItem(str(s["items"])))
            self.seller_table.setItem(i, 3, QTableWidgetItem(str(s["last_seen"])[:16] if s["last_seen"] else ""))

    def delete_selected_seller(self):
        row = self.seller_table.currentRow()
        if row < 0:
            return
        seller = self.seller_table.item(row, 0).text()
        reply = QMessageBox.question(self, "Silme Onayi", f"{seller} tum kayitlari silinecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                conn = self.get_db()
                conn.execute("DELETE FROM prices WHERE seller=?", (seller,))
                conn.commit()
                conn.close()
                self.search_sellers()
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    # ========== CLEANUP TAB ==========
    def create_cleanup_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("Veri Temizligi")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        dup_group = QGroupBox("Tekrarlanan Kayitlari Temizle")
        dup_layout = QVBoxLayout()
        dup_layout.addWidget(QLabel("Ayni satisci+item icin en ucuz fiyati korur, digerlerini siler."))
        btn_dup = QPushButton("Temizle")
        btn_dup.setObjectName("warn")
        btn_dup.clicked.connect(self.cleanup_duplicates)
        dup_layout.addWidget(btn_dup)
        dup_group.setLayout(dup_layout)
        layout.addWidget(dup_group)

        old_group = QGroupBox("Eski Kayitlari Sil")
        old_layout = QHBoxLayout()
        old_layout.addWidget(QLabel("Gun sayisi:"))
        self.cleanup_days = QSpinBox()
        self.cleanup_days.setValue(30)
        self.cleanup_days.setMaximumWidth(100)
        old_layout.addWidget(self.cleanup_days)
        btn_old = QPushButton("Sil")
        btn_old.setObjectName("danger")
        btn_old.clicked.connect(self.cleanup_old)
        old_layout.addWidget(btn_old)
        old_layout.addStretch()
        old_group.setLayout(old_layout)
        layout.addWidget(old_group)

        del_group = QGroupBox("Item Sil (Isim ile)")
        del_layout = QHBoxLayout()
        self.del_item_name = QLineEdit()
        self.del_item_name.setPlaceholderText("Item adi")
        del_layout.addWidget(self.del_item_name)
        btn_del = QPushButton("Bu Itemi Sil")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self.delete_item_by_name)
        del_layout.addWidget(btn_del)
        del_group.setLayout(del_layout)
        layout.addWidget(del_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Veri Temizligi")

    def cleanup_duplicates(self):
        try:
            conn = self.get_db()
            c1 = conn.execute("""
                DELETE FROM prices WHERE id NOT IN (
                    SELECT MIN(id) FROM prices
                    WHERE seller != '' AND seller IS NOT NULL
                    GROUP BY seller, item_name, item_lvl, server, type
                ) AND seller != '' AND seller IS NOT NULL
            """).rowcount
            c2 = conn.execute("""
                DELETE FROM prices WHERE id NOT IN (
                    SELECT MIN(id) FROM prices
                    WHERE seller = '' OR seller IS NULL
                    GROUP BY item_name, item_lvl, server, type, price
                ) AND (seller = '' OR seller IS NULL)
            """).rowcount
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Tamamlandi", f"{c1 + c2} tekrarlanan kayit silindi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def cleanup_old(self):
        try:
            days = self.cleanup_days.value()
            conn = self.get_db()
            c = conn.execute("DELETE FROM prices WHERE timestamp < date('now', ?)", (f"-{days} days",)).rowcount
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Tamamlandi", f"{c} eski kayit silindi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def delete_item_by_name(self):
        name = self.del_item_name.text().strip()
        if not name:
            return
        reply = QMessageBox.question(self, "Silme Onayi", f"'{name}' tum kayitlari silinecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                conn = self.get_db()
                c = conn.execute("DELETE FROM prices WHERE item_name=?", (name,)).rowcount
                conn.commit()
                conn.close()
                self.del_item_name.clear()
                QMessageBox.information(self, "Tamamlandi", f"{c} kayit silindi.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    # ========== BACKUP TAB ==========
    def create_backup_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("DB Yedekleme")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        btn_backup = QPushButton("Yedek Olustur")
        btn_backup.setObjectName("success")
        btn_backup.clicked.connect(self.create_backup)
        layout.addWidget(btn_backup)

        self.backup_table = QTableWidget()
        self.backup_table.setColumnCount(2)
        self.backup_table.setHorizontalHeaderLabels(["Dosya", "Boyut"])
        self.backup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.backup_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.backup_table.verticalHeader().setVisible(False)
        layout.addWidget(self.backup_table)

        self.tabs.addTab(tab, "DB Yedekleme")

    def load_backups(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")], reverse=True)
        self.backup_table.setRowCount(len(files))
        for i, f in enumerate(files):
            size = os.path.getsize(os.path.join(BACKUP_DIR, f))
            self.backup_table.setItem(i, 0, QTableWidgetItem(f))
            self.backup_table.setItem(i, 1, QTableWidgetItem(f"{size/1024/1024:.1f} MB"))

    def create_backup(self):
        try:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = os.path.join(BACKUP_DIR, f"backup_{ts}.db")
            shutil.copy2(DB_PATH, dst)
            self.load_backups()
            QMessageBox.information(self, "Basarili", f"Yedek olusturuldu: backup_{ts}.db")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    # ========== API HELPER ==========
    def api_call(self, endpoint, method="GET", data=None):
        url = WEB_URL + endpoint
        try:
            if data:
                body = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
            else:
                req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e)}

    # ========== RATE LIMITER TAB ==========
    def create_ratelimit_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("IP Engelleme & Rate Limiting")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        # Config
        cfg_group = QGroupBox("Limit Ayarlari")
        cfg_layout = QHBoxLayout()
        cfg_layout.addWidget(QLabel("Dakikada max istek:"))
        self.rl_limit = QSpinBox()
        self.rl_limit.setValue(100)
        self.rl_limit.setMaximum(10000)
        self.rl_limit.setMaximumWidth(100)
        cfg_layout.addWidget(self.rl_limit)
        cfg_layout.addWidget(QLabel("Pencere (sn):"))
        self.rl_window = QSpinBox()
        self.rl_window.setValue(60)
        self.rl_window.setMaximum(600)
        self.rl_window.setMaximumWidth(100)
        cfg_layout.addWidget(self.rl_window)
        btn_cfg = QPushButton("Guncelle")
        btn_cfg.setObjectName("success")
        btn_cfg.clicked.connect(self.update_rate_config)
        cfg_layout.addWidget(btn_cfg)
        cfg_layout.addStretch()
        cfg_group.setLayout(cfg_layout)
        layout.addWidget(cfg_group)

        # Manual block
        block_group = QGroupBox("IP Engelle / Kaldir")
        block_layout = QHBoxLayout()
        self.rl_ip_input = QLineEdit()
        self.rl_ip_input.setPlaceholderText("IP adresi (orn: 192.168.1.1)")
        block_layout.addWidget(self.rl_ip_input)
        btn_block = QPushButton("Engelle")
        btn_block.setObjectName("danger")
        btn_block.clicked.connect(self.block_ip)
        block_layout.addWidget(btn_block)
        btn_unblock = QPushButton("Engeli Kaldir")
        btn_unblock.setObjectName("warn")
        btn_unblock.clicked.connect(self.unblock_ip)
        block_layout.addWidget(btn_unblock)
        block_group.setLayout(block_layout)
        layout.addWidget(block_group)

        # Stats table
        self.rl_table = QTableWidget()
        self.rl_table.setColumnCount(4)
        self.rl_table.setHorizontalHeaderLabels(["IP", "Istek Sayisi", "Baslangic", "Durum"])
        self.rl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.rl_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rl_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rl_table.verticalHeader().setVisible(False)
        layout.addWidget(self.rl_table)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_rate_stats)
        btn_row.addWidget(btn_refresh)
        btn_unblock_all = QPushButton("Tum Engelleri Kaldir")
        btn_unblock_all.setObjectName("warn")
        btn_unblock_all.clicked.connect(self.unblock_all_ips)
        btn_row.addWidget(btn_unblock_all)
        btn_clear = QPushButton("Sayaclari Sifirla")
        btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self.clear_rate_counters)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "IP Engelleme")

    def load_rate_stats(self):
        data = self.api_call("/api/admin/rate/stats")
        if "error" in data:
            self.rl_table.setRowCount(1)
            self.rl_table.setItem(0, 0, QTableWidgetItem("Sunucuya baglanamadi"))
            return

        self.rl_limit.setValue(data.get("limit", 100))
        self.rl_window.setValue(data.get("window", 60))

        stats = data.get("stats", [])
        self.rl_table.setRowCount(len(stats))
        for i, s in enumerate(stats):
            self.rl_table.setItem(i, 0, QTableWidgetItem(s["ip"]))
            self.rl_table.setItem(i, 1, QTableWidgetItem(str(s["count"])))
            self.rl_table.setItem(i, 2, QTableWidgetItem(s["first"]))
            durum = QTableWidgetItem("ENGELLI" if s["blocked"] else "Aktif")
            durum.setForeground(QColor("#ff4757") if s["blocked"] else QColor("#00ff96"))
            self.rl_table.setItem(i, 3, durum)

    def update_rate_config(self):
        data = self.api_call("/api/admin/rate/config", "POST", {
            "limit": self.rl_limit.value(),
            "window": self.rl_window.value()
        })
        QMessageBox.information(self, "Basarili", "Limit ayarlari guncellendi!")

    def block_ip(self):
        ip = self.rl_ip_input.text().strip()
        if not ip:
            return
        self.api_call("/api/admin/rate/block", "POST", {"ip": ip})
        self.rl_ip_input.clear()
        self.load_rate_stats()

    def unblock_ip(self):
        ip = self.rl_ip_input.text().strip()
        if not ip:
            return
        self.api_call("/api/admin/rate/unblock", "POST", {"ip": ip})
        self.rl_ip_input.clear()
        self.load_rate_stats()

    def unblock_all_ips(self):
        reply = QMessageBox.question(self, "Onay", "Tum engeller kaldirilsin mi?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.api_call("/api/admin/rate/unblock-all", "POST")
            self.load_rate_stats()

    def clear_rate_counters(self):
        self.api_call("/api/admin/rate/clear", "POST")
        self.load_rate_stats()

    # ========== API LOGS TAB ==========
    def create_api_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("API Loglari")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        # Stats
        stats_group = QGroupBox("Istatistikler")
        stats_layout = QHBoxLayout()
        self.al_total_label = QLabel("Toplam: 0")
        self.al_total_label.setStyleSheet("color: #00d4ff; font-weight: bold;")
        stats_layout.addWidget(self.al_total_label)
        self.al_2xx_label = QLabel("2xx: 0")
        self.al_2xx_label.setStyleSheet("color: #00ff96;")
        stats_layout.addWidget(self.al_2xx_label)
        self.al_4xx_label = QLabel("4xx: 0")
        self.al_4xx_label.setStyleSheet("color: #ffa502;")
        stats_layout.addWidget(self.al_4xx_label)
        self.al_5xx_label = QLabel("5xx: 0")
        self.al_5xx_label.setStyleSheet("color: #ff4757;")
        stats_layout.addWidget(self.al_5xx_label)
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Filters
        filter_group = QGroupBox("Filtrele")
        filter_layout = QHBoxLayout()
        self.al_filter_method = QComboBox()
        self.al_filter_method.addItems(["Tumu", "GET", "POST", "PUT", "DELETE"])
        self.al_filter_method.setMaximumWidth(100)
        filter_layout.addWidget(QLabel("Method:"))
        filter_layout.addWidget(self.al_filter_method)
        self.al_filter_endpoint = QLineEdit()
        self.al_filter_endpoint.setPlaceholderText("Endpoint (orn: dashboard)")
        filter_layout.addWidget(self.al_filter_endpoint)
        self.al_filter_ip = QLineEdit()
        self.al_filter_ip.setPlaceholderText("IP adresi")
        self.al_filter_ip.setMaximumWidth(150)
        filter_layout.addWidget(self.al_filter_ip)
        btn_filter = QPushButton("Filtrele")
        btn_filter.setObjectName("success")
        btn_filter.clicked.connect(self.load_api_logs)
        filter_layout.addWidget(btn_filter)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Table
        self.al_table = QTableWidget()
        self.al_table.setColumnCount(6)
        self.al_table.setHorizontalHeaderLabels(["Zaman", "Method", "Endpoint", "IP", "Status", "Sure(ms)"])
        self.al_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.al_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.al_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.al_table.verticalHeader().setVisible(False)
        layout.addWidget(self.al_table)

        # Buttons
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_api_logs)
        btn_row.addWidget(btn_refresh)
        btn_clear = QPushButton("Loglari Temizle")
        btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self.clear_api_logs)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "API Loglari")

    def load_api_logs(self):
        # Stats
        stats = self.api_call("/api/admin/api-logs/stats")
        if "error" not in stats:
            self.al_total_label.setText(f"Toplam: {stats.get('total', 0)}")
            by_status = stats.get("by_status", [])
            s2 = sum(s["cnt"] for s in by_status if 200 <= s["status_code"] < 300)
            s4 = sum(s["cnt"] for s in by_status if 400 <= s["status_code"] < 500)
            s5 = sum(s["cnt"] for s in by_status if 500 <= s["status_code"] < 600)
            self.al_2xx_label.setText(f"2xx: {s2}")
            self.al_4xx_label.setText(f"4xx: {s4}")
            self.al_5xx_label.setText(f"5xx: {s5}")

        # Logs
        method = self.al_filter_method.currentText()
        endpoint = self.al_filter_endpoint.text().strip()
        ip = self.al_filter_ip.text().strip()
        params = "?limit=200"
        if method != "Tumu":
            params += f"&method={method}"
        if endpoint:
            params += f"&endpoint={endpoint}"
        if ip:
            params += f"&ip={ip}"

        data = self.api_call(f"/api/admin/api-logs{params}")
        if "error" in data:
            self.al_table.setRowCount(1)
            self.al_table.setItem(0, 0, QTableWidgetItem("Sunucuya baglanamadi"))
            return

        logs = data.get("logs", [])
        self.al_table.setRowCount(len(logs))
        for i, log in enumerate(logs):
            self.al_table.setItem(i, 0, QTableWidgetItem(log.get("timestamp", "")[:19]))
            method_item = QTableWidgetItem(log.get("method", ""))
            if log.get("method") == "POST":
                method_item.setForeground(QColor("#ffa502"))
            elif log.get("method") == "DELETE":
                method_item.setForeground(QColor("#ff4757"))
            self.al_table.setItem(i, 1, method_item)
            self.al_table.setItem(i, 2, QTableWidgetItem(log.get("endpoint", "")))
            self.al_table.setItem(i, 3, QTableWidgetItem(log.get("ip_address", "")))
            status = log.get("status_code", 0)
            status_item = QTableWidgetItem(str(status))
            if 200 <= status < 300:
                status_item.setForeground(QColor("#00ff96"))
            elif 400 <= status < 500:
                status_item.setForeground(QColor("#ffa502"))
            elif status >= 500:
                status_item.setForeground(QColor("#ff4757"))
            self.al_table.setItem(i, 4, status_item)
            self.al_table.setItem(i, 5, QTableWidgetItem(str(log.get("response_time_ms", ""))))

    def clear_api_logs(self):
        reply = QMessageBox.question(self, "Onay", "Tum API loglari silinecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.api_call("/api/admin/api-logs/clear", "POST")
            self.load_api_logs()

    # ========== THREATS TAB ==========
    def create_threats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("Guvenlik Uyarilari & Tehdit Analizi")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #ff4757;")
        layout.addWidget(header)

        # Stats
        stats_group = QGroupBox("Istatistikler")
        stats_layout = QHBoxLayout()
        self.th_total_label = QLabel("Toplam: 0")
        self.th_total_label.setStyleSheet("color: #ff4757; font-weight: bold;")
        stats_layout.addWidget(self.th_total_label)
        self.th_critical_label = QLabel("Kritik: 0")
        self.th_critical_label.setStyleSheet("color: #ff0000; font-weight: bold;")
        stats_layout.addWidget(self.th_critical_label)
        self.th_high_label = QLabel("Yuksek: 0")
        self.th_high_label.setStyleSheet("color: #ffa502;")
        stats_layout.addWidget(self.th_high_label)
        self.th_medium_label = QLabel("Orta: 0")
        self.th_medium_label.setStyleSheet("color: #ffd700;")
        stats_layout.addWidget(self.th_medium_label)
        self.th_blocked_label = QLabel("Son 24s Engellenen: 0")
        self.th_blocked_label.setStyleSheet("color: #00ff96;")
        stats_layout.addWidget(self.th_blocked_label)
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Filters
        filter_group = QGroupBox("Filtrele")
        filter_layout = QHBoxLayout()
        self.th_filter_type = QComboBox()
        self.th_filter_type.addItems(["Tumu", "SQL_INJECTION", "XSS", "PATH_TRAVERSAL", "COMMAND_INJECTION", "SUSPICIOUS_UA"])
        self.th_filter_type.setMaximumWidth(180)
        filter_layout.addWidget(QLabel("Tip:"))
        filter_layout.addWidget(self.th_filter_type)
        self.th_filter_severity = QComboBox()
        self.th_filter_severity.addItems(["Tumu", "critical", "high", "medium", "low"])
        self.th_filter_severity.setMaximumWidth(100)
        filter_layout.addWidget(QLabel("Onem:"))
        filter_layout.addWidget(self.th_filter_severity)
        self.th_filter_ip = QLineEdit()
        self.th_filter_ip.setPlaceholderText("IP adresi")
        self.th_filter_ip.setMaximumWidth(150)
        filter_layout.addWidget(self.th_filter_ip)
        btn_filter = QPushButton("Filtrele")
        btn_filter.setObjectName("success")
        btn_filter.clicked.connect(self.load_threats)
        filter_layout.addWidget(btn_filter)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Table
        self.th_table = QTableWidget()
        self.th_table.setColumnCount(7)
        self.th_table.setHorizontalHeaderLabels(["Zaman", "Tip", "Onem", "IP", "Endpoint", "Payload", "Engellendi"])
        self.th_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.th_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.th_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.th_table.verticalHeader().setVisible(False)
        layout.addWidget(self.th_table)

        # Buttons
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_threats)
        btn_row.addWidget(btn_refresh)
        btn_clear = QPushButton("Tehdit Loglarini Temizle")
        btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self.clear_threats)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "Uyarilar")

    def load_threats(self):
        # Stats
        stats = self.api_call("/api/admin/threats/stats")
        if "error" not in stats:
            self.th_total_label.setText(f"Toplam: {stats.get('total', 0)}")
            self.th_blocked_label.setText(f"Son 24s Engellenen: {stats.get('recent_blocked_24h', 0)}")
            by_severity = stats.get("by_severity", [])
            sev_map = {s["severity"]: s["cnt"] for s in by_severity}
            self.th_critical_label.setText(f"Kritik: {sev_map.get('critical', 0)}")
            self.th_high_label.setText(f"Yuksek: {sev_map.get('high', 0)}")
            self.th_medium_label.setText(f"Orta: {sev_map.get('medium', 0)}")

        # Threats
        threat_type = self.th_filter_type.currentText()
        severity = self.th_filter_severity.currentText()
        ip = self.th_filter_ip.text().strip()
        params = "?limit=200"
        if threat_type != "Tumu":
            params += f"&type={threat_type}"
        if severity != "Tumu":
            params += f"&severity={severity}"
        if ip:
            params += f"&ip={ip}"

        data = self.api_call(f"/api/admin/threats{params}")
        if "error" in data:
            self.th_table.setRowCount(1)
            self.th_table.setItem(0, 0, QTableWidgetItem("Sunucuya baglanamadi"))
            return

        threats = data.get("threats", [])
        self.th_table.setRowCount(len(threats))
        for i, t in enumerate(threats):
            self.th_table.setItem(i, 0, QTableWidgetItem(t.get("timestamp", "")[:19]))

            type_item = QTableWidgetItem(t.get("threat_type", ""))
            type_colors = {
                "SQL_INJECTION": QColor("#ff0000"),
                "XSS": QColor("#ff4757"),
                "PATH_TRAVERSAL": QColor("#ffa502"),
                "COMMAND_INJECTION": QColor("#ff0000"),
                "SUSPICIOUS_UA": QColor("#ffd700"),
            }
            type_item.setForeground(type_colors.get(t.get("threat_type"), QColor("#888")))
            self.th_table.setItem(i, 1, type_item)

            sev_item = QTableWidgetItem(t.get("severity", ""))
            sev_colors = {"critical": QColor("#ff0000"), "high": QColor("#ff4757"), "medium": QColor("#ffa502"), "low": QColor("#ffd700")}
            sev_item.setForeground(sev_colors.get(t.get("severity"), QColor("#888")))
            self.th_table.setItem(i, 2, sev_item)

            self.th_table.setItem(i, 3, QTableWidgetItem(t.get("ip_address", "")))
            self.th_table.setItem(i, 4, QTableWidgetItem(t.get("endpoint", "")))

            payload = t.get("payload", "") or ""
            payload_item = QTableWidgetItem(payload[:80] + ("..." if len(payload) > 80 else ""))
            payload_item.setToolTip(payload)
            self.th_table.setItem(i, 5, payload_item)

            blocked_item = QTableWidgetItem("EVET" if t.get("blocked") else "HAYIR")
            blocked_item.setForeground(QColor("#00ff96") if t.get("blocked") else QColor("#888"))
            self.th_table.setItem(i, 6, blocked_item)

    def clear_threats(self):
        reply = QMessageBox.question(self, "Onay", "Tum tehdit loglari silinecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.api_call("/api/admin/threats/clear", "POST")
            self.load_threats()

    # ========== PERMISSIONS TAB ==========
    def create_permissions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("Izin Yonetimi")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        # Info
        info = QLabel("Web sitesi kullanicilarini ve yetkilerini yonetin.")
        info.setStyleSheet("color: #888; padding: 5px;")
        layout.addWidget(info)

        # Table
        self.perm_table = QTableWidget()
        self.perm_table.setColumnCount(7)
        self.perm_table.setHorizontalHeaderLabels(["ID", "Kullanici", "Admin", "Aktif", "Son Giris", "Giris Sayisi", "Kayit"])
        self.perm_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.perm_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.perm_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.perm_table.verticalHeader().setVisible(False)
        layout.addWidget(self.perm_table)

        # Buttons
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self.load_permissions)
        btn_row.addWidget(btn_refresh)
        btn_toggle_admin = QPushButton("Admin Yetkisi Degistir")
        btn_toggle_admin.setObjectName("warn")
        btn_toggle_admin.clicked.connect(self.toggle_admin_permission)
        btn_row.addWidget(btn_toggle_admin)
        btn_toggle_active = QPushButton("Aktif/Pasif Degistir")
        btn_toggle_active.clicked.connect(self.toggle_active_permission)
        btn_row.addWidget(btn_toggle_active)
        btn_delete = QPushButton("Kullaniciyi Sil")
        btn_delete.setObjectName("danger")
        btn_delete.clicked.connect(self.delete_user_permission)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "Izin Yonetimi")

    def load_permissions(self):
        data = self.api_call("/api/admin/users")
        if "error" in data:
            self.perm_table.setRowCount(1)
            self.perm_table.setItem(0, 0, QTableWidgetItem("Sunucuya baglanamadi"))
            return

        users = data.get("users", [])
        self.perm_table.setRowCount(len(users))
        for i, u in enumerate(users):
            self.perm_table.setItem(i, 0, QTableWidgetItem(str(u.get("id", ""))))
            self.perm_table.setItem(i, 1, QTableWidgetItem(u.get("username", "")))

            admin_item = QTableWidgetItem("EVET" if u.get("is_admin") else "HAYIR")
            admin_item.setForeground(QColor("#00ff96") if u.get("is_admin") else QColor("#888"))
            self.perm_table.setItem(i, 2, admin_item)

            active_item = QTableWidgetItem("AKTIF" if u.get("is_active") else "PASIF")
            active_item.setForeground(QColor("#00ff96") if u.get("is_active") else QColor("#ff4757"))
            self.perm_table.setItem(i, 3, active_item)

            self.perm_table.setItem(i, 4, QTableWidgetItem((u.get("last_login") or "-")[:16]))
            self.perm_table.setItem(i, 5, QTableWidgetItem(str(u.get("login_count", 0))))
            self.perm_table.setItem(i, 6, QTableWidgetItem((u.get("created_at") or "")[:16]))

    def _get_selected_user_id(self):
        row = self.perm_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Uyari", "Bir kullanici secin!")
            return None
        user_id = self.perm_table.item(row, 0).text()
        username = self.perm_table.item(row, 1).text()
        return user_id, username

    def toggle_admin_permission(self):
        sel = self._get_selected_user_id()
        if not sel:
            return
        user_id, username = sel
        reply = QMessageBox.question(self, "Onay", f"{username} kullanicisinin admin yetkisi degistirilecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            result = self.api_call(f"/api/admin/users/{user_id}/admin", "POST")
            if "error" in result:
                QMessageBox.critical(self, "Hata", result["error"])
            else:
                self.load_permissions()

    def toggle_active_permission(self):
        sel = self._get_selected_user_id()
        if not sel:
            return
        user_id, username = sel
        reply = QMessageBox.question(self, "Onay", f"{username} kullanicisinin aktif durumu degistirilecek. Emin misin?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            result = self.api_call(f"/api/admin/users/{user_id}/active", "POST")
            if "error" in result:
                QMessageBox.critical(self, "Hata", result["error"])
            else:
                self.load_permissions()

    def delete_user_permission(self):
        sel = self._get_selected_user_id()
        if not sel:
            return
        user_id, username = sel
        reply = QMessageBox.question(self, "Silme Onayi", f"{username} kullaniciyi silmek istediginize emin misin?\nBu islem geri alinamaz!",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            result = self.api_call(f"/api/admin/users/{user_id}/delete", "POST")
            if "error" in result:
                QMessageBox.critical(self, "Hata", result["error"])
            else:
                self.load_permissions()

    # ========== SETTINGS TAB ==========
    def create_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        header = QLabel("Ayarlar & Guvenlik")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        header.setStyleSheet("color: #00d4ff;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Vertical)

        # API Settings
        api_group = QGroupBox("API Ayarlari")
        api_layout = QFormLayout()

        self.s_api_key = QLineEdit()
        self.s_api_key.setEchoMode(QLineEdit.Password)
        self.s_api_key.setMinimumWidth(400)
        api_layout.addRow("UskoPazar API Key:", self.s_api_key)

        self.s_auto_scan = QSpinBox()
        self.s_auto_scan.setValue(60)
        self.s_auto_scan.setMaximum(1440)
        self.s_auto_scan.setSuffix(" dakika")
        api_layout.addRow("Otomatik Tarama:", self.s_auto_scan)

        api_group.setLayout(api_layout)
        splitter.addWidget(api_group)

        # Port Settings
        port_group = QGroupBox("Sunucu Portlari")
        port_layout = QFormLayout()

        self.s_web_port = QSpinBox()
        self.s_web_port.setValue(8765)
        self.s_web_port.setRange(1024, 65535)
        self.s_web_port.setSuffix(" (Web/Pazar)")
        port_layout.addRow("Web Port:", self.s_web_port)

        self.s_portfolio_port = QSpinBox()
        self.s_portfolio_port.setValue(9000)
        self.s_portfolio_port.setRange(1024, 65535)
        self.s_portfolio_port.setSuffix(" (Portfoy)")
        port_layout.addRow("Portfoy Port:", self.s_portfolio_port)

        port_group.setLayout(port_layout)
        splitter.addWidget(port_group)

        # Security Settings
        sec_group = QGroupBox("Guvenlik Ayarlari")
        sec_layout = QFormLayout()

        self.s_api_token = QLineEdit()
        self.s_api_token.setEchoMode(QLineEdit.Password)
        self.s_api_token.setMinimumWidth(400)
        sec_layout.addRow("API Token (Web):", self.s_api_token)

        btn_gen_token = QPushButton("Yeni Token Olustur")
        btn_gen_token.setObjectName("warn")
        btn_gen_token.clicked.connect(self.generate_token)
        sec_layout.addRow("", btn_gen_token)

        self.s_web_password = QLineEdit()
        self.s_web_password.setEchoMode(QLineEdit.Password)
        self.s_web_password.setMinimumWidth(400)
        sec_layout.addRow("Web Giris Sifresi:", self.s_web_password)

        self.s_max_attempts = QSpinBox()
        self.s_max_attempts.setValue(5)
        self.s_max_attempts.setMaximum(20)
        sec_layout.addRow("Max Yanlis Deneme:", self.s_max_attempts)

        self.s_lockout = QSpinBox()
        self.s_lockout.setValue(15)
        self.s_lockout.setMaximum(120)
        self.s_lockout.setSuffix(" dakika")
        sec_layout.addRow("Engelleme Suresi:", self.s_lockout)

        sec_group.setLayout(sec_layout)
        splitter.addWidget(sec_group)

        # IP Whitelist
        ip_group = QGroupBox("IP Beyaz Liste")
        ip_layout = QVBoxLayout()

        self.s_ip_whitelist = QTextEdit()
        self.s_ip_whitelist.setPlaceholderText("IP adreslerini satir satir girin\nOrnek: 192.168.1.100")
        self.s_ip_whitelist.setMaximumHeight(100)
        ip_layout.addWidget(self.s_ip_whitelist)

        ip_group.setLayout(ip_layout)
        splitter.addWidget(ip_group)

        layout.addWidget(splitter)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("Tum Ayarlari Kaydet")
        btn_save.setObjectName("success")
        btn_save.clicked.connect(self.save_security_settings)
        btn_row.addWidget(btn_save)
        btn_save_ports = QPushButton("Portlari Kaydet & Yeniden Baslat")
        btn_save_ports.setObjectName("warn")
        btn_save_ports.clicked.connect(self.save_ports)
        btn_row.addWidget(btn_save_ports)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tabs.addTab(tab, "Guvenlik")
        self.load_settings()
        self.load_security_settings()

    def load_settings(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                if config.get("uskopazar_api_key_encrypted"):
                    self.s_api_key.setText(CryptoManager.decrypt(config.get("uskopazar_api_key", "")))
                else:
                    self.s_api_key.setText(config.get("uskopazar_api_key", ""))
                self.s_auto_scan.setValue(config.get("auto_scan_minutes", 60))
                self.s_web_port.setValue(config.get("web_port", 8765))
                self.s_portfolio_port.setValue(config.get("portfolio_port", 9000))
        except:
            pass

    def load_security_settings(self):
        try:
            sec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security.json")
            if os.path.exists(sec_path):
                with open(sec_path, "r") as f:
                    sec = json.load(f)
                if sec.get("api_token_encrypted"):
                    self.s_api_token.setText(CryptoManager.decrypt(sec.get("api_token", "")))
                else:
                    self.s_api_token.setText(sec.get("api_token", ""))
                self.s_max_attempts.setValue(sec.get("max_login_attempts", 5))
                self.s_lockout.setValue(sec.get("lockout_minutes", 15))
                whitelist = sec.get("ip_whitelist", [])
                self.s_ip_whitelist.setPlainText("\n".join(whitelist))
        except:
            pass

    def generate_token(self):
        token = secrets.token_hex(32)
        self.s_api_token.setText(token)
        QMessageBox.information(self, "Token", f"Yeni token olusturuldu:\n\n{token[:20]}...")

    def save_settings(self):
        try:
            config = {}
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
            api_key = self.s_api_key.text().strip()
            if api_key:
                config["uskopazar_api_key"] = CryptoManager.encrypt(api_key)
                config["uskopazar_api_key_encrypted"] = True
            config["auto_scan_minutes"] = self.s_auto_scan.value()
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
            QMessageBox.information(self, "Basarili", "API ayarlari kaydedildi!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def save_security_settings(self):
        try:
            sec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security.json")
            sec = {}
            if os.path.exists(sec_path):
                with open(sec_path, "r") as f:
                    sec = json.load(f)

            token = self.s_api_token.text().strip()
            if token:
                sec["api_token"] = CryptoManager.encrypt(token)
                sec["api_token_encrypted"] = True
            sec["max_login_attempts"] = self.s_max_attempts.value()
            sec["lockout_minutes"] = self.s_lockout.value()

            whitelist_text = self.s_ip_whitelist.toPlainText().strip()
            sec["ip_whitelist"] = [ip.strip() for ip in whitelist_text.split("\n") if ip.strip()]

            with open(sec_path, "w") as f:
                json.dump(sec, f, indent=2)

            web_pass = self.s_web_password.text().strip()
            if web_pass:
                web_users_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_users.db")
                conn = sqlite3.connect(web_users_path)
                pw_hash = bcrypt.hashpw(web_pass.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
                conn.execute("UPDATE users SET password_hash = ?", (pw_hash,))
                conn.commit()
                conn.close()

            QMessageBox.information(self, "Basarili", "Guvenlik ayarlari kaydedildi!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def save_ports(self):
        try:
            new_web = self.s_web_port.value()
            new_portfolio = self.s_portfolio_port.value()

            config = {}
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)

            old_web = config.get("web_port", 8765)
            old_portfolio = config.get("portfolio_port", 9000)

            config["web_port"] = new_web
            config["portfolio_port"] = new_portfolio
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)

            if old_web != new_web or old_portfolio != new_portfolio:
                reply = QMessageBox.question(self, "Sunucu Yeniden Baslatma",
                    f"Port degisikligi kaydedildi!\n\nEski: {old_web}/{old_portfolio}\nYeni: {new_web}/{new_portfolio}\n\nSunuculari simdi yeniden baslatmak ister misin?",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self._restart_servers(new_web, new_portfolio)
            else:
                QMessageBox.information(self, "Basarili", "Port ayarlari kaydedildi!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _restart_servers(self, web_port, portfolio_port):
        import subprocess, time
        try:
            for proc in subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            ).stdout.strip().split("\n")[1:]:
                if proc:
                    pid = proc.split(",")[1].strip('"')
                    subprocess.run(["taskkill", "/PID", pid, "/F"],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

            time.sleep(2)
            base = os.path.dirname(os.path.abspath(__file__))
            subprocess.Popen([sys.executable, "main.py"], cwd=base,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(3)
            subprocess.Popen([sys.executable, "start_web.py"], cwd=base,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            time.sleep(1)
            subprocess.Popen([sys.executable, "portfolio_server.py"], cwd=base,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            QMessageBox.information(self, "Basarili",
                f"Sunucular yeniden baslatildi!\nWeb: http://127.0.0.1:{web_port}\nPortfoy: http://127.0.0.1:{portfolio_port}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeniden baslatma hatasi: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    login = AdminLoginWindow()
    login.show()
    sys.exit(app.exec_())
