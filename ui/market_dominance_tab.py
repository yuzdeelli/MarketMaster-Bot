import sqlite3
import time
import threading
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QComboBox, QLineEdit, QTableWidget,
                                QTableWidgetItem, QHeaderView, QTextEdit, QFrame,
                                QGroupBox, QGridLayout, QSpinBox, QCheckBox,
                                QTabWidget)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont


class MarketDominanceTab:
    SERVER_LIST = [
        "ZERO 3", "ZERO 4", "ZERO 5", "ZERO 8",
        "PANDORA 3", "PANDORA 4",
        "AGARTHA 3", "AGARTHA 4",
        "FELIS 2",
        "DESTAN 3", "DESTAN 2",
        "MINARK 2", "DRYADS 2",
        "OREADS 2", "OREADS 3",
    ]

    def __init__(self, master, parent_tab):
        self.master = master
        self.content = parent_tab
        self.db_name = master.db_name
        self._init_db_tables()

        layout = QVBoxLayout(self.content)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("PIYASA HAKIMIYETI")
        header.setStyleSheet("color: #f1c40f; font-size: 18px; font-weight: bold; "
                            "letter-spacing: 3px; padding: 8px; "
                            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                            "stop:0 #1a1a2e, stop:1 #0c0e1a); "
                            "border: 1px solid #f39c12; border-radius: 6px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        top_bar.addWidget(QLabel("Sunucu:"))
        self.server_combo = QComboBox()
        self.server_combo.addItems(["Tum Sunucular"] + self.SERVER_LIST)
        self.server_combo.setFixedWidth(160)
        self.server_combo.currentTextChanged.connect(self._refresh_all)
        top_bar.addWidget(self.server_combo)

        top_bar.addWidget(QLabel("Item:"))
        self.item_entry = QLineEdit()
        self.item_entry.setPlaceholderText("Item adi (ornegin: Raptor)")
        self.item_entry.setFixedWidth(200)
        self.item_entry.returnPressed.connect(self._refresh_all)
        top_bar.addWidget(self.item_entry)

        self.refresh_btn = QPushButton("YENILE")
        self.refresh_btn.setFixedSize(90, 32)
        self.refresh_btn.setStyleSheet(
            "QPushButton { background:#1a3a2e; color:#2ecc71; border:1px solid #2ecc71; "
            "border-radius:5px; font-weight:bold; font-size:11px; } "
            "QPushButton:hover { background:#2a4a3e; }")
        self.refresh_btn.clicked.connect(self._refresh_all)
        top_bar.addWidget(self.refresh_btn)

        self.snapshot_btn = QPushButton("SNAPSHOT AL")
        self.snapshot_btn.setFixedSize(110, 32)
        self.snapshot_btn.setStyleSheet(
            "QPushButton { background:#1a2a3e; color:#3498db; border:1px solid #3498db; "
            "border-radius:5px; font-weight:bold; font-size:11px; } "
            "QPushButton:hover { background:#1e3348; }")
        self.snapshot_btn.clicked.connect(self._take_snapshot)
        top_bar.addWidget(self.snapshot_btn)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #1a1a2e; background: #0a0a14; } "
            "QTabBar::tab { background: #111122; color: #888; padding: 8px 16px; "
            "border: 1px solid #1a1a2e; border-bottom: none; margin-right: 2px; } "
            "QTabBar::tab:selected { background: #1a1a2e; color: #f1c40f; "
            "border-bottom: 2px solid #f1c40f; }")

        self._build_buy_wall_tab()
        self._build_seller_tab()
        self._build_supply_tab()
        self._build_alert_tab()
        self._build_strategy_tab()

        layout.addWidget(self.tab_widget)

        self._start_auto_refresh()

    def _init_db_tables(self):
        try:
            conn = sqlite3.connect(self.db_name, timeout=30)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    item_lvl TEXT,
                    server TEXT,
                    buy_median REAL,
                    sell_median REAL,
                    buy_count INTEGER,
                    sell_count INTEGER,
                    min_buy INTEGER,
                    max_buy INTEGER,
                    min_sell INTEGER,
                    max_sell INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS seller_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller TEXT,
                    item_name TEXT,
                    item_lvl TEXT,
                    server TEXT,
                    price INTEGER,
                    type TEXT,
                    first_seen DATETIME,
                    last_seen DATETIME,
                    count INTEGER DEFAULT 1
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    item_lvl TEXT,
                    server TEXT,
                    alert_type TEXT,
                    threshold INTEGER,
                    active INTEGER DEFAULT 1,
                    triggered INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _build_buy_wall_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(4)

        info = QLabel("Fiyat duvari: Piyasadaki alis/satis derinligini goruntule. "
                       "Hedef alis fiyatini belirle, rakiplerin ne kadar sattigini izle.")
        info.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.wall_table = QTableWidget()
        self.wall_table.setColumnCount(10)
        self.wall_table.setHorizontalHeaderLabels([
            "Item", "Lvl", "Min Alis", "Max Alis", "Medyan Alis",
            "Min Satis", "Max Satis", "Medyan Satis", "Spread", "F找rsat"
        ])
        self.wall_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.wall_table.verticalHeader().setVisible(False)
        self.wall_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.wall_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.wall_table.setAlternatingRowColors(True)
        self.wall_table.setStyleSheet(
            "QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; } "
            "QTableWidget::item { padding: 3px; } "
            "QTableWidget::item:selected { background: #1a3a5c; } "
            "QTableWidget::alternate { background: #0e1220; } "
            "QHeaderView::section { background: #111122; color: #f1c40f; "
            "font-weight: bold; font-size: 11px; padding: 5px; "
            "border-bottom: 2px solid #f39c12; border-right: 1px solid #1a1a2e; }")
        layout.addWidget(self.wall_table)

        self.wall_log = QTextEdit()
        self.wall_log.setReadOnly(True)
        self.wall_log.setMaximumHeight(120)
        self.wall_log.setStyleSheet(
            "background: #050508; color: #aaa; border: 1px solid #1a1a2e; "
            "font-family: Consolas; font-size: 10px;")
        layout.addWidget(self.wall_log)

        self.tab_widget.addTab(tab, "Fiyat Duvari")

    def _build_seller_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(4)

        info = QLabel("Rakip/satici takibi: Kim satiyor, ne fiyata, ne zamandan beri. "
                       "Yeni saticilari, fiyat degisikliklerini yakala.")
        info.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.seller_table = QTableWidget()
        self.seller_table.setColumnCount(8)
        self.seller_table.setHorizontalHeaderLabels([
            "Satici", "Item", "Lvl", "Sunucu", "Fiyat",
            "Tip", "Ilk Gorunum", "Son Gorunum"
        ])
        self.seller_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.seller_table.verticalHeader().setVisible(False)
        self.seller_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.seller_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.seller_table.setAlternatingRowColors(True)
        self.seller_table.setStyleSheet(
            "QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; } "
            "QTableWidget::item { padding: 3px; } "
            "QTableWidget::item:selected { background: #1a3a5c; } "
            "QTableWidget::alternate { background: #0e1220; } "
            "QHeaderView::section { background: #111122; color: #f39c12; "
            "font-weight: bold; font-size: 11px; padding: 5px; "
            "border-bottom: 2px solid #f39c12; border-right: 1px solid #1a1a2e; }")
        layout.addWidget(self.seller_table)

        self.tab_widget.addTab(tab, "Rakip Takibi")

    def _build_supply_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(4)

        info = QLabel("Arz takibi: Her sunucuda kac urun var, toplam arz ne kadar, "
                       "arz degisimi nasil. Arz dustukce fiyat yukselir.")
        info.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.supply_table = QTableWidget()
        self.supply_table.setColumnCount(7)
        self.supply_table.setHorizontalHeaderLabels([
            "Sunucu", "Alis Adet", "Satis Adet", "Toplam",
            "Ort. Alis Fiyati", "Ort. Satis Fiyati", "Spread"
        ])
        self.supply_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.supply_table.verticalHeader().setVisible(False)
        self.supply_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.supply_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.supply_table.setAlternatingRowColors(True)
        self.supply_table.setStyleSheet(
            "QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; } "
            "QTableWidget::item { padding: 3px; } "
            "QTableWidget::item:selected { background: #1a3a5c; } "
            "QTableWidget::alternate { background: #0e1220; } "
            "QHeaderView::section { background: #111122; color: #f39c12; "
            "font-weight: bold; font-size: 11px; padding: 5px; "
            "border-bottom: 2px solid #f39c12; border-right: 1px solid #1a1a2e; }")
        layout.addWidget(self.supply_table)

        self.supply_log = QTextEdit()
        self.supply_log.setReadOnly(True)
        self.supply_log.setMaximumHeight(120)
        self.supply_log.setStyleSheet(
            "background: #050508; color: #aaa; border: 1px solid #1a1a2e; "
            "font-family: Consolas; font-size: 10px;")
        layout.addWidget(self.supply_log)

        self.tab_widget.addTab(tab, "Arz Monitor")

    def _build_alert_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(4)

        info = QLabel("Fiyat alarlari: Fiyat belirli bir eserin altina/ustune dustugunde "
                       "uyari al. Piyasayi canli izle.")
        info.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        add_row.addWidget(QLabel("Item:"))
        self.alert_item = QLineEdit()
        self.alert_item.setPlaceholderText("Item adi")
        self.alert_item.setFixedWidth(150)
        add_row.addWidget(self.alert_item)

        add_row.addWidget(QLabel("Lvl:"))
        self.alert_lvl = QComboBox()
        self.alert_lvl.addItems(["", "+0", "+1", "+2", "+3", "+4", "+5", "+6", "+7", "+8", "+9", "+10"])
        self.alert_lvl.setFixedWidth(60)
        add_row.addWidget(self.alert_lvl)

        add_row.addWidget(QLabel("Tip:"))
        self.alert_type = QComboBox()
        self.alert_type.addItems(["Fiyat Dustu", "Fiyat Yukseldi", "Yeni Satici"])
        self.alert_type.setFixedWidth(130)
        add_row.addWidget(self.alert_type)

        add_row.addWidget(QLabel("Esik:"))
        self.alert_threshold = QSpinBox()
        self.alert_threshold.setRange(0, 999999)
        self.alert_threshold.setValue(100000)
        self.alert_threshold.setSuffix(" gold")
        self.alert_threshold.setFixedWidth(130)
        add_row.addWidget(self.alert_threshold)

        btn_add = QPushButton("Ekle")
        btn_add.setFixedSize(60, 30)
        btn_add.setStyleSheet(
            "QPushButton { background:#1a3a2e; color:#2ecc71; border:1px solid #2ecc71; "
            "border-radius:5px; font-weight:bold; } "
            "QPushButton:hover { background:#2a4a3e; }")
        btn_add.clicked.connect(self._add_alert)
        add_row.addWidget(btn_add)
        add_row.addStretch()
        layout.addLayout(add_row)

        self.alert_table = QTableWidget()
        self.alert_table.setColumnCount(7)
        self.alert_table.setHorizontalHeaderLabels([
            "ID", "Item", "Lvl", "Tip", "Esik", "Durum", "Olusturma"
        ])
        self.alert_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alert_table.verticalHeader().setVisible(False)
        self.alert_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.alert_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.alert_table.setAlternatingRowColors(True)
        self.alert_table.setStyleSheet(
            "QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; } "
            "QTableWidget::item { padding: 3px; } "
            "QTableWidget::item:selected { background: #1a3a5c; } "
            "QTableWidget::alternate { background: #0e1220; } "
            "QHeaderView::section { background: #111122; color: #f1c40f; "
            "font-weight: bold; font-size: 11px; padding: 5px; "
            "border-bottom: 2px solid #f39c12; border-right: 1px solid #1a1a2e; }")
        layout.addWidget(self.alert_table)

        btn_row = QHBoxLayout()
        btn_check = QPushButton("Alarlari Kontrol Et")
        btn_check.setStyleSheet(
            "QPushButton { background:#2a1a1a; color:#e74c3c; border:1px solid #e74c3c; "
            "border-radius:5px; font-weight:bold; padding: 6px 14px; } "
            "QPushButton:hover { background:#3a2a2a; }")
        btn_check.clicked.connect(self._check_alerts)
        btn_row.addWidget(btn_check)

        btn_delete = QPushButton("Secili Alarti Sil")
        btn_delete.setStyleSheet(
            "QPushButton { background:#1a1a2a; color:#9b59b6; border:1px solid #9b59b6; "
            "border-radius:5px; font-weight:bold; padding: 6px 14px; } "
            "QPushButton:hover { background:#2a2a3a; }")
        btn_delete.clicked.connect(self._delete_alert)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.alert_log = QTextEdit()
        self.alert_log.setReadOnly(True)
        self.alert_log.setMaximumHeight(100)
        self.alert_log.setStyleSheet(
            "background: #050508; color: #aaa; border: 1px solid #1a1a2e; "
            "font-family: Consolas; font-size: 10px;")
        layout.addWidget(self.alert_log)

        self.tab_widget.addTab(tab, "Fiyat Alarlari")

    def _build_strategy_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(4)

        info = QLabel("Hakimiyet stratejisi: Piyasayi nasil yonetirsin? "
                       "Alis fiyatini belirle, spread'i kontrol et, rakiplerin onde ol.")
        info.setStyleSheet("color: #888; font-size: 11px; padding: 4px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        strat_group = QGroupBox(" ALIS STRATEJISI ")
        strat_group.setStyleSheet(
            "QGroupBox { color: #f1c40f; font-weight: bold; border: 1px solid #2a3a4a; "
            "border-radius: 6px; margin-top: 10px; padding-top: 14px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }")
        strat_layout = QGridLayout(strat_group)
        strat_layout.setSpacing(8)

        strat_layout.addWidget(QLabel("Strateji:"), 0, 0)
        self.buy_strategy = QComboBox()
        self.buy_strategy.addItems([
            "Medyan * 0.90 (Agresif Dusuk)",
            "Medyan * 0.95 (Dusuk)",
            "Q1 * 0.97 (Sigorta)",
            "%95 Alt * 0.97 (Guvenli)",
            "Min * 0.97 (Minumum)",
            "Medyan (Piyasa Duzeyi)",
            "Max %3 Vergi (Satista)",
            "Manuel"
        ])
        self.buy_strategy.setFixedWidth(280)
        strat_layout.addWidget(self.buy_strategy, 0, 1)

        strat_layout.addWidget(QLabel("Max Alis Fiyati:"), 1, 0)
        self.max_buy_price = QSpinBox()
        self.max_buy_price.setRange(0, 99999999)
        self.max_buy_price.setSuffix(" gold")
        self.max_buy_price.setFixedWidth(200)
        strat_layout.addWidget(self.max_buy_price, 1, 1)

        strat_layout.addWidget(QLabel("Min Sat Spread:"), 2, 0)
        self.min_sell_spread = QSpinBox()
        self.min_sell_spread.setRange(0, 100)
        self.min_sell_spread.setValue(5)
        self.min_sell_spread.setSuffix(" %")
        self.min_sell_spread.setFixedWidth(200)
        strat_layout.addWidget(self.min_sell_spread, 2, 1)

        self.auto_adjust = QCheckBox("Otomatik Fiyat Ayarla (arz dustukce alis fiyatini yukselt)")
        self.auto_adjust.setStyleSheet("color: #2ecc71; font-weight: bold;")
        strat_layout.addWidget(self.auto_adjust, 3, 0, 1, 2)

        layout.addWidget(strat_group)

        self.strat_table = QTableWidget()
        self.strat_table.setColumnCount(8)
        self.strat_table.setHorizontalHeaderLabels([
            "Item", "Lvl", "Piyasa Medyan", "Senin Alis", "Hedef Alis",
            "Hedef Satis", "Beklenen Kar", "Oneri"
        ])
        self.strat_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.strat_table.verticalHeader().setVisible(False)
        self.strat_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.strat_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.strat_table.setAlternatingRowColors(True)
        self.strat_table.setStyleSheet(
            "QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; } "
            "QTableWidget::item { padding: 3px; } "
            "QTableWidget::item:selected { background: #1a3a5c; } "
            "QTableWidget::alternate { background: #0e1220; } "
            "QHeaderView::section { background: #111122; color: #f1c40f; "
            "font-weight: bold; font-size: 11px; padding: 5px; "
            "border-bottom: 2px solid #f39c12; border-right: 1px solid #1a1a2e; }")
        layout.addWidget(self.strat_table)

        self.strat_log = QTextEdit()
        self.strat_log.setReadOnly(True)
        self.strat_log.setMaximumHeight(100)
        self.strat_log.setStyleSheet(
            "background: #050508; color: #aaa; border: 1px solid #1a1a2e; "
            "font-family: Consolas; font-size: 10px;")
        layout.addWidget(self.strat_log)

        self.tab_widget.addTab(tab, "Strateji")

    def _get_db(self):
        try:
            if hasattr(self.master, 'analyzer'):
                return self.master.analyzer
        except Exception:
            pass
        return None

    def _get_server_filter(self):
        srv = self.server_combo.currentText()
        if srv == "Tum Sunucular":
            return None
        return srv

    def _get_item_filter(self):
        return self.item_entry.text().strip()

    def _refresh_all(self):
        self._refresh_wall()
        self._refresh_sellers()
        self._refresh_supply()
        self._refresh_alerts()
        self._refresh_strategy()

    def _refresh_wall(self):
        try:
            srv = self._get_server_filter()
            item_filter = self._get_item_filter()
            analyzer = self._get_db()
            if not analyzer:
                return

            self.wall_table.setRowCount(0)
            items = self._get_items_from_db(srv, item_filter)
            for item_name, item_lvl in items[:200]:
                stats = analyzer.get_item_stats(item_name=item_name, item_lvl=item_lvl, server=srv)
                if not stats:
                    continue
                buy = stats.get("buy") or {}
                sell = stats.get("sell") or {}
                if not buy and not sell:
                    continue

                buy_min = buy.get("min", 0)
                buy_max = buy.get("max", 0)
                buy_med = buy.get("median", 0)
                sell_min = sell.get("min", 0)
                sell_max = sell.get("max", 0)
                sell_med = sell.get("median", 0)

                spread = 0
                if buy_med > 0 and sell_med > 0:
                    spread = ((sell_med - buy_med) / buy_med) * 100

                opportunity = ""
                opp_color = "#888"
                if sell_med > 0 and buy_max > 0:
                    net = sell_med * 0.97 - buy_max
                    if net > 0:
                        opportunity = f"+{net:,.0f} gold"
                        opp_color = "#2ecc71"
                    elif net < 0:
                        opportunity = f"{net:,.0f} gold"
                        opp_color = "#e74c3c"
                    else:
                        opportunity = "Breakeven"

                row = self.wall_table.rowCount()
                self.wall_table.insertRow(row)
                self.wall_table.setItem(row, 0, QTableWidgetItem(item_name))
                self.wall_table.setItem(row, 1, QTableWidgetItem(str(item_lvl)))
                self.wall_table.setItem(row, 2, QTableWidgetItem(f"{buy_min:,.0f}" if buy_min else "-"))
                self.wall_table.setItem(row, 3, QTableWidgetItem(f"{buy_max:,.0f}" if buy_max else "-"))
                self.wall_table.setItem(row, 4, QTableWidgetItem(f"{buy_med:,.0f}" if buy_med else "-"))
                self.wall_table.setItem(row, 5, QTableWidgetItem(f"{sell_min:,.0f}" if sell_min else "-"))
                self.wall_table.setItem(row, 6, QTableWidgetItem(f"{sell_max:,.0f}" if sell_max else "-"))
                self.wall_table.setItem(row, 7, QTableWidgetItem(f"{sell_med:,.0f}" if sell_med else "-"))

                spread_item = QTableWidgetItem(f"%{spread:.1f}")
                if spread > 20:
                    spread_item.setForeground(QColor("#2ecc71"))
                elif spread > 10:
                    spread_item.setForeground(QColor("#f39c12"))
                else:
                    spread_item.setForeground(QColor("#e74c3c"))
                self.wall_table.setItem(row, 8, spread_item)

                opp_item = QTableWidgetItem(opportunity)
                opp_item.setForeground(QColor(opp_color))
                self.wall_table.setItem(row, 9, opp_item)

            self.wall_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Fiyat duvari guncellendi: "
                                f"{self.wall_table.rowCount()} item")
        except Exception as e:
            self.wall_log.append(f"Hata: {e}")

    def _refresh_sellers(self):
        try:
            srv = self._get_server_filter()
            item_filter = self._get_item_filter()

            self.seller_table.setRowCount(0)
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()

            query = "SELECT seller, item_name, item_lvl, server, price, type, first_seen, last_seen FROM seller_history"
            params = []
            conditions = []
            if srv:
                conditions.append("server = ?")
                params.append(srv)
            if item_filter:
                conditions.append("item_name LIKE ?")
                params.append(f"%{item_filter}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY last_seen DESC LIMIT 200"

            c.execute(query, params)
            rows = c.fetchall()
            conn.close()

            for row_data in rows:
                row = self.seller_table.rowCount()
                self.seller_table.insertRow(row)
                seller = row_data[0] or "Bilinmiyor"
                for col, val in enumerate(row_data):
                    item = QTableWidgetItem(str(val) if val else "-")
                    if col == 0:
                        item.setFont(QFont("Consolas", 10, QFont.Bold))
                        item.setForeground(QColor("#f39c12"))
                    self.seller_table.setItem(row, col, item)
        except Exception as e:
            pass

    def _refresh_supply(self):
        try:
            srv = self._get_server_filter()
            item_filter = self._get_item_filter()

            self.supply_table.setRowCount(0)
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()

            servers = [srv] if srv else self.SERVER_LIST
            for server in servers:
                buy_query = "SELECT COUNT(*), AVG(price) FROM prices WHERE server = ? AND type = 'buy'"
                sell_query = "SELECT COUNT(*), AVG(price) FROM prices WHERE server = ? AND type = 'sell'"
                params = [server]
                if item_filter:
                    buy_query += " AND item_name LIKE ?"
                    sell_query += " AND item_name LIKE ?"
                    params.append(f"%{item_filter}%")

                c.execute(buy_query, params)
                buy_count, buy_avg = c.fetchone()
                c.execute(sell_query, params)
                sell_count, sell_avg = c.fetchone()

                if buy_count == 0 and sell_count == 0:
                    continue

                total = buy_count + sell_count
                avg_buy = buy_avg or 0
                avg_sell = sell_avg or 0
                spread = 0
                if avg_buy > 0 and avg_sell > 0:
                    spread = ((avg_sell - avg_buy) / avg_buy) * 100

                row = self.supply_table.rowCount()
                self.supply_table.insertRow(row)
                self.supply_table.setItem(row, 0, QTableWidgetItem(server))
                self.supply_table.setItem(row, 1, QTableWidgetItem(str(buy_count)))
                self.supply_table.setItem(row, 2, QTableWidgetItem(str(sell_count)))
                self.supply_table.setItem(row, 3, QTableWidgetItem(str(total)))
                self.supply_table.setItem(row, 4, QTableWidgetItem(f"{avg_buy:,.0f}" if avg_buy else "-"))
                self.supply_table.setItem(row, 5, QTableWidgetItem(f"{avg_sell:,.0f}" if avg_sell else "-"))

                spread_item = QTableWidgetItem(f"%{spread:.1f}")
                if spread > 15:
                    spread_item.setForeground(QColor("#2ecc71"))
                elif spread > 5:
                    spread_item.setForeground(QColor("#f39c12"))
                else:
                    spread_item.setForeground(QColor("#e74c3c"))
                self.supply_table.setItem(row, 6, spread_item)

            conn.close()
            self.supply_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Arz guncellendi: "
                f"{self.supply_table.rowCount()} sunucu")
        except Exception as e:
            self.supply_log.append(f"Hata: {e}")

    def _refresh_alerts(self):
        try:
            self.alert_table.setRowCount(0)
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()
            c.execute("SELECT id, item_name, item_lvl, alert_type, threshold, active, created_at "
                      "FROM price_alerts ORDER BY created_at DESC")
            for row_data in c.fetchall():
                row = self.alert_table.rowCount()
                self.alert_table.insertRow(row)
                for col, val in enumerate(row_data):
                    item = QTableWidgetItem(str(val) if val is not None else "-")
                    if col == 5:
                        if val == 1:
                            item.setForeground(QColor("#2ecc71"))
                            item.setText("Aktif")
                        else:
                            item.setForeground(QColor("#e74c3c"))
                            item.setText("Tetiklendi")
                    self.alert_table.setItem(row, col, item)
            conn.close()
        except Exception:
            pass

    def _refresh_strategy(self):
        try:
            srv = self._get_server_filter()
            item_filter = self._get_item_filter()
            analyzer = self._get_db()
            if not analyzer:
                return

            self.strat_table.setRowCount(0)
            items = self._get_items_from_db(srv, item_filter)

            strategy_text = self.buy_strategy.currentText()
            max_buy = self.max_buy_price.value()
            min_spread = self.min_sell_spread.value() / 100

            for item_name, item_lvl in items[:200]:
                stats = analyzer.get_item_stats(item_name=item_name, item_lvl=item_lvl, server=srv)
                if not stats:
                    continue
                buy = stats.get("buy") or {}
                sell = stats.get("sell") or {}
                if not buy or not sell:
                    continue

                sell_med = sell.get("median", 0)
                buy_med = buy.get("median", 0)
                if sell_med <= 0 or buy_med <= 0:
                    continue

                hedef_alis = self._calc_strategy_price(buy, strategy_text)
                if max_buy > 0 and hedef_alis > max_buy:
                    hedef_alis = max_buy

                hedef_satis = sell_med * (1 + min_spread)

                net = hedef_satis * 0.97 - hedef_alis
                kar_pct = (net / hedef_alis * 100) if hedef_alis > 0 else 0

                oneri = ""
                oneri_color = "#888"
                if kar_pct > 20:
                    oneri = "GUC AL"
                    oneri_color = "#2ecc71"
                elif kar_pct > 5:
                    oneri = "ALINABILIR"
                    oneri_color = "#f39c12"
                elif kar_pct > 0:
                    oneri = "DUSUK KAR"
                    oneri_color = "#e67e22"
                else:
                    oneri = "ALMA"
                    oneri_color = "#e74c3c"

                row = self.strat_table.rowCount()
                self.strat_table.insertRow(row)
                self.strat_table.setItem(row, 0, QTableWidgetItem(item_name))
                self.strat_table.setItem(row, 1, QTableWidgetItem(str(item_lvl)))
                self.strat_table.setItem(row, 2, QTableWidgetItem(f"{buy_med:,.0f}"))
                self.strat_table.setItem(row, 3, QTableWidgetItem(f"{buy.get('min', 0):,.0f}"))
                self.strat_table.setItem(row, 4, QTableWidgetItem(f"{hedef_alis:,.0f}"))
                self.strat_table.setItem(row, 5, QTableWidgetItem(f"{hedef_satis:,.0f}"))

                kar_item = QTableWidgetItem(f"{net:,.0f} ({kar_pct:+.1f}%)")
                kar_item.setForeground(QColor("#2ecc71" if net > 0 else "#e74c3c"))
                self.strat_table.setItem(row, 6, kar_item)

                oneri_item = QTableWidgetItem(oneri)
                oneri_item.setForeground(QColor(oneri_color))
                oneri_item.setFont(QFont("Consolas", 10, QFont.Bold))
                self.strat_table.setItem(row, 7, oneri_item)

            self.strat_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Strateji guncellendi: "
                f"{self.strat_table.rowCount()} item")
        except Exception as e:
            self.strat_log.append(f"Hata: {e}")

    def _calc_strategy_price(self, buy_stats, strategy_text):
        if "Agresif" in strategy_text:
            return buy_stats.get("median", 0) * 0.90
        elif "0.95" in strategy_text:
            return buy_stats.get("median", 0) * 0.95
        elif "Q1" in strategy_text:
            return buy_stats.get("q1", 0) * 0.97
        elif "%95 Alt" in strategy_text:
            ci = buy_stats.get("ci_low", 0)
            return ci * 0.97 if ci > 0 else buy_stats.get("max", 0) * 0.95 * 0.97
        elif "Min" in strategy_text and "Max" not in strategy_text:
            return buy_stats.get("min", 0) * 0.97
        elif "Medyan" in strategy_text:
            return buy_stats.get("median", 0)
        elif "Max" in strategy_text:
            return buy_stats.get("max", 0)
        return buy_stats.get("median", 0)

    def _get_items_from_db(self, server=None, item_filter=None):
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()
            query = "SELECT DISTINCT item_name, item_lvl FROM prices"
            params = []
            conditions = []
            if server:
                conditions.append("server LIKE ?")
                params.append(f"%{server}%")
            if item_filter:
                conditions.append("item_name LIKE ?")
                params.append(f"%{item_filter}%")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY item_name, item_lvl"
            c.execute(query, params)
            items = c.fetchall()
            conn.close()
            return items
        except Exception:
            return []

    def _take_snapshot(self):
        try:
            srv = self._get_server_filter()
            item_filter = self._get_item_filter()
            analyzer = self._get_db()
            if not analyzer:
                return

            items = self._get_items_from_db(srv, item_filter)
            count = 0
            for item_name, item_lvl in items[:100]:
                stats = analyzer.get_item_stats(item_name=item_name, item_lvl=item_lvl, server=srv)
                if not stats:
                    continue
                buy = stats.get("buy") or {}
                sell = stats.get("sell") or {}
                if not buy and not sell:
                    continue

                conn = sqlite3.connect(self.db_name, timeout=15)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO market_snapshots
                    (item_name, item_lvl, server, buy_median, sell_median,
                     buy_count, sell_count, min_buy, max_buy, min_sell, max_sell)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_name, item_lvl, srv or "ALL",
                    buy.get("median", 0), sell.get("median", 0),
                    buy.get("count", 0), sell.get("count", 0),
                    buy.get("min", 0), buy.get("max", 0),
                    sell.get("min", 0), sell.get("max", 0)
                ))
                conn.commit()
                conn.close()
                count += 1

            self.wall_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Snapshot alindi: {count} item kaydedildi")
        except Exception as e:
            self.wall_log.append(f"Snapshot hatasi: {e}")

    def _add_alert(self):
        item = self.alert_item.text().strip()
        if not item:
            return
        lvl = self.alert_lvl.currentText()
        alert_type = self.alert_type.currentText()
        threshold = self.alert_threshold.value()
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()
            c.execute("""
                INSERT INTO price_alerts (item_name, item_lvl, alert_type, threshold)
                VALUES (?, ?, ?, ?)
            """, (item, lvl, alert_type, threshold))
            conn.commit()
            conn.close()
            self.alert_item.clear()
            self._refresh_alerts()
        except Exception:
            pass

    def _check_alerts(self):
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()
            c.execute("SELECT id, item_name, item_lvl, alert_type, threshold FROM price_alerts WHERE active = 1")
            alerts = c.fetchall()
            conn.close()

            triggered = 0
            for alert_id, item_name, item_lvl, alert_type, threshold in alerts:
                stats = self._get_item_stats_simple(item_name, item_lvl)
                if not stats:
                    continue

                current_price = 0
                if alert_type in ("Fiyat Dustu", "Fiyat Yukseldi"):
                    current_price = stats.get("sell_median", 0) or stats.get("buy_median", 0)
                elif alert_type == "Yeni Satici":
                    current_price = stats.get("seller_count", 0)

                triggered_this = False
                if alert_type == "Fiyat Dustu" and 0 < current_price <= threshold:
                    triggered_this = True
                elif alert_type == "Fiyat Yukseldi" and current_price >= threshold:
                    triggered_this = True
                elif alert_type == "Yeni Satici" and current_price >= threshold:
                    triggered_this = True

                if triggered_this:
                    triggered += 1
                    conn = sqlite3.connect(self.db_name, timeout=15)
                    c2 = conn.cursor()
                    c2.execute("UPDATE price_alerts SET triggered = 1, active = 0 WHERE id = ?", (alert_id,))
                    conn.commit()
                    conn.close()
                    self.alert_log.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] TETIKLENDI: "
                        f"{item_name} {item_lvl} - {alert_type} (Esik: {threshold}, "
                        f"Gercek: {current_price:,.0f})")

            if triggered == 0:
                self.alert_log.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Alarlar kontrol edildi: "
                    f"Tetiklenen yok")
            else:
                self._refresh_alerts()
        except Exception as e:
            self.alert_log.append(f"Kontrol hatasi: {e}")

    def _get_item_stats_simple(self, item_name, item_lvl):
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()
            c.execute("""
                SELECT type, price FROM prices
                WHERE item_name = ? AND item_lvl = ?
                ORDER BY timestamp DESC LIMIT 100
            """, (item_name, item_lvl))
            rows = c.fetchall()
            conn.close()

            buy_prices = [r[1] for r in rows if r[0] == 'buy']
            sell_prices = [r[1] for r in rows if r[0] == 'sell']

            import statistics
            result = {}
            if buy_prices:
                result["buy_median"] = statistics.median(buy_prices)
            if sell_prices:
                result["sell_median"] = statistics.median(sell_prices)
            return result
        except Exception:
            return {}

    def _delete_alert(self):
        rows = self.alert_table.selectionModel().selectedRows()
        if not rows:
            return
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            c = conn.cursor()
            for idx in rows:
                alert_id = self.alert_table.item(idx.row(), 0)
                if alert_id:
                    c.execute("DELETE FROM price_alerts WHERE id = ?", (int(alert_id.text()),))
            conn.commit()
            conn.close()
            self._refresh_alerts()
        except Exception:
            pass

    def _start_auto_refresh(self):
        self._auto_timer = QTimer()
        self._auto_timer.timeout.connect(self._refresh_all)
        self._auto_timer.start(60000)
