import sqlite3
import os
from collections import defaultdict
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QComboBox, QTableWidget, QTableWidgetItem,
                                QHeaderView, QLineEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class ArbitrageTab:
    def __init__(self, master, tab):
        self.master = master
        self.tab = tab
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self.tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("ARBITRAJ ANALIZ")
        title.setStyleSheet("font-size:16px;font-weight:900;color:#00ff41;font-family:'Consolas','Courier New',monospace;margin-bottom:4px")
        layout.addWidget(title)

        subtitle = QLabel("Alis ve satis fiyatlarini ayri ayri karsilastir. Ayni item farkli sunucularda kac para?")
        subtitle.setStyleSheet("color:#00aa2a;font-size:11px;margin-bottom:8px;font-family:'Consolas','Courier New',monospace")
        layout.addWidget(subtitle)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        filter_row.addWidget(QLabel("Tur:"))
        self.combo_type = QComboBox()
        self.combo_type.setMinimumWidth(90)
        self.combo_type.setStyleSheet(self._combo_style())
        self.combo_type.addItems(["Satis (Sell)", "Alis (Buy)", "Hepsi"])
        self.combo_type.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(self.combo_type)

        filter_row.addWidget(QLabel("Sunucu 1:"))
        self.combo_srv1 = QComboBox()
        self.combo_srv1.setMinimumWidth(110)
        self.combo_srv1.setStyleSheet(self._combo_style())
        self.combo_srv1.addItem("Tum Sunucular")
        self.combo_srv1.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(self.combo_srv1)

        vs_label = QLabel("vs")
        vs_label.setStyleSheet("color:#00ff41;font-weight:700;font-size:12px;font-family:'Consolas','Courier New',monospace")
        filter_row.addWidget(vs_label)

        filter_row.addWidget(QLabel("Sunucu 2:"))
        self.combo_srv2 = QComboBox()
        self.combo_srv2.setMinimumWidth(110)
        self.combo_srv2.setStyleSheet(self._combo_style())
        self.combo_srv2.addItem("Tum Sunucular")
        self.combo_srv2.currentTextChanged.connect(self._load_data)
        filter_row.addWidget(self.combo_srv2)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Item ara...")
        self.search_input.setStyleSheet(self._search_style())
        self.search_input.textChanged.connect(self._filter_table)
        self.search_input.setMaximumWidth(180)
        filter_row.addWidget(self.search_input)

        filter_row.addStretch()

        self.lbl_count = QLabel("0 sonuc")
        self.lbl_count.setStyleSheet("color:#00ff41;font-weight:700;font-size:12px;font-family:'Consolas','Courier New',monospace")
        filter_row.addWidget(self.lbl_count)

        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Item", "Level", "Tur", "En Ucuz Sunucu", "Fiyat", "En Pahali Sunucu", "Fiyat", "Fark %"
        ])
        self.table.setStyleSheet("""
            QTableWidget { background:#000000; color:#00ff41; gridline-color:#0d1f0d;
                           border:none; font-size:11px; font-family:'Consolas','Courier New',monospace }
            QTableWidget::item { padding:4px 6px; background:#000000 }
            QTableWidget::item:selected { background:#003300; color:#00ff41 }
            QTableWidget::item:hover { background:#001a00 }
            QHeaderView::section { background:#0a0a0a; color:#00ff41; font-size:10px;
                                   font-weight:700; padding:6px; border:1px solid #0d1f0d;
                                   font-family:'Consolas','Courier New',monospace }
            QScrollBar:vertical { background:#000; width:8px }
            QScrollBar::handle:vertical { background:#00ff41; border-radius:4px; min-height:30px; opacity:0.3 }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0 }
        """)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 8):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)
        self._load_servers()

    def _load_servers(self):
        db_path = self.master.db_name
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path, timeout=15)
            conn.execute("PRAGMA busy_timeout=15000")
            servers = [r[0] for r in conn.execute(
                "SELECT DISTINCT server FROM prices ORDER BY server"
            ).fetchall()]
            conn.close()
            for srv in servers:
                self.combo_srv1.addItem(srv)
                self.combo_srv2.addItem(srv)
        except Exception:
            pass

    def _load_data(self):
        type_text = self.combo_type.currentText()
        srv1 = self.combo_srv1.currentText()
        srv2 = self.combo_srv2.currentText()

        if "Buy" in type_text:
            ptype = "buy"
        elif "Sell" in type_text:
            ptype = "sell"
        else:
            ptype = None

        db_path = self.master.db_name
        if not os.path.exists(db_path):
            return

        try:
            conn = sqlite3.connect(db_path, timeout=15)
            conn.execute("PRAGMA busy_timeout=15000")

            servers_to_query = []
            if srv1 != "Tum Sunucular":
                servers_to_query.append(srv1)
            if srv2 != "Tum Sunucular":
                servers_to_query.append(srv2)

            if ptype:
                if servers_to_query:
                    q = "SELECT item_name, item_lvl, type, server, MIN(price) FROM prices WHERE type = ? AND server IN ({}) GROUP BY item_name, item_lvl, type, server".format(
                        ",".join("?" * len(servers_to_query)))
                    rows = conn.execute(q, [ptype] + servers_to_query).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT item_name, item_lvl, type, server, MIN(price) FROM prices WHERE type = ? GROUP BY item_name, item_lvl, type, server",
                        (ptype,)
                    ).fetchall()
            else:
                if servers_to_query:
                    q = "SELECT item_name, item_lvl, type, server, MIN(price) FROM prices WHERE server IN ({}) GROUP BY item_name, item_lvl, type, server".format(
                        ",".join("?" * len(servers_to_query)))
                    rows = conn.execute(q, servers_to_query).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT item_name, item_lvl, type, server, MIN(price) FROM prices GROUP BY item_name, item_lvl, type, server"
                    ).fetchall()
            conn.close()
        except Exception:
            return

        grouped = defaultdict(dict)
        for name, lvl, typ, server, price in rows:
            grouped[(name, lvl, typ)][server] = price

        results = []
        for (name, lvl, typ), servers in grouped.items():
            if len(servers) < 2:
                continue
            min_srv = min(servers, key=servers.get)
            max_srv = max(servers, key=servers.get)
            min_price = servers[min_srv]
            max_price = servers[max_srv]
            if min_price <= 0:
                continue
            fark = max_price - min_price
            yuzde = round(fark / min_price * 100, 1)
            results.append((name, lvl, typ, min_srv, min_price, max_srv, max_price, yuzde))

        results.sort(key=lambda x: x[7], reverse=True)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(results))
        for i, (name, lvl, typ, min_s, min_p, max_s, max_p, yuzde) in enumerate(results):
            self.table.setItem(i, 0, self._green_item(name))
            self.table.setItem(i, 1, self._green_item(lvl))
            t_item = self._green_item("Satis" if typ == "sell" else "Alis")
            self.table.setItem(i, 2, t_item)
            self.table.setItem(i, 3, self._green_item(min_s))
            self.table.setItem(i, 4, self._price_item(min_p))
            self.table.setItem(i, 5, self._green_item(max_s))
            self.table.setItem(i, 6, self._price_item(max_p))

            pct_item = QTableWidgetItem(f"%{yuzde}")
            pct_item.setForeground(QColor("#00ff41"))
            pct_item.setTextAlignment(Qt.AlignCenter)
            font = pct_item.font()
            font.setBold(True)
            pct_item.setFont(font)
            pct_item.setData(Qt.UserRole, yuzde)
            self.table.setItem(i, 7, pct_item)

        self.table.setSortingEnabled(True)
        self._all_data = results
        self.lbl_count.setText(f"{len(results)} sonuc")
        self._filter_table()

    def _filter_table(self):
        q = self.search_input.text().lower()
        visible = 0
        for i in range(self.table.rowCount()):
            name_item = self.table.item(i, 0)
            if name_item:
                match = q in name_item.text().lower() if q else True
                self.table.setRowHidden(i, not match)
                if match:
                    visible += 1
        self.lbl_count.setText(f"{visible} sonuc")

    def _green_item(self, text):
        item = QTableWidgetItem(str(text))
        item.setForeground(QColor("#00ff41"))
        return item

    def _price_item(self, price):
        text = f"{price:,.0f}".replace(",", ".")
        item = QTableWidgetItem(text)
        item.setForeground(QColor("#00ff41"))
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        item.setData(Qt.UserRole, price)
        return item

    def _combo_style(self):
        return """
            QComboBox { background:#000; border:1px solid #00ff41; padding:5px 10px;
                        border-radius:4px; color:#00ff41; font-size:11px; font-weight:600;
                        font-family:'Consolas','Courier New',monospace }
            QComboBox:hover { border-color:#00ff41; background:#001a00 }
            QComboBox::drop-down { border:none; width:20px }
            QComboBox::down-arrow { image:none; border-left:4px solid transparent;
                                    border-right:4px solid transparent; border-top:6px solid #00ff41 }
            QComboBox QAbstractItemView { background:#000; color:#00ff41; border:1px solid #00ff41;
                                          selection-background-color:#003300; font-size:11px;
                                          font-family:'Consolas','Courier New',monospace }
        """

    def _search_style(self):
        return """
            QLineEdit { background:#000; border:1px solid #00ff41; padding:5px 10px;
                        border-radius:4px; color:#00ff41; font-size:11px;
                        font-family:'Consolas','Courier New',monospace }
            QLineEdit:focus { border-color:#00ff41; background:#001a00 }
        """
