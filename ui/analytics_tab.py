import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                 QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
                                 QHeaderView, QLineEdit, QSplitter, QCompleter,
                                 QListWidget, QListWidgetItem, QInputDialog,
                                 QMessageBox, QGroupBox, QTabWidget, QFrame,
                                 QAbstractItemView, QMenu)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QAction
import sqlite3

SERVER_GROUPS = {
    "Tum Zero": ["ZERO 3", "ZERO 4", "ZERO 5", "ZERO 8"],
    "Tum Pandora": ["PANDORA 3", "PANDORA 4"],
    "Tum Agartha": ["AGARTHA 3", "AGARTHA 4"],
    "Tum Destan": ["DESTAN 2", "DESTAN 3"],
    "Tum Oreads": ["OREADS 2", "OREADS 3"],
}

LVL_OPTIONS = [f"+{i}" for i in range(11)] + [f"+{i}R" for i in range(1, 22)]

TABLE_STYLE = """
    QTableWidget { background:#000; color:#00ff41; gridline-color:#1a1a2e; font-family:Consolas; font-size:11px; border:none; selection-background-color:#0d3320; }
    QTableWidget::item:selected { background:#0d3320; }
    QHeaderView::section { background:#0a0a14; color:#2ecc71; border:1px solid #1a1a2e; padding:4px; font-weight:700; font-size:11px; }
"""

PANEL_STYLE = """
    QGroupBox { background:#0a0a14; border:1px solid #1a1a2e; border-radius:6px; margin-top:10px; padding-top:14px; color:#2ecc71; font-weight:700; font-size:11px; }
    QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 6px; }
"""

LIST_STYLE = """
    QListWidget { background:#000; color:#00ff41; border:1px solid #1a1a2e; font-family:Consolas; font-size:11px; }
    QListWidget::item { padding:4px 8px; border-bottom:1px solid #0a1a0a; }
    QListWidget::item:selected { background:#0d3320; color:#fff; }
    QListWidget::item:hover { background:#0a1a0a; }
"""


class BulkWorker(QThread):
    done = Signal(list)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, db_name, list_items, servers):
        super().__init__()
        self.db_name = db_name
        self.list_items = list_items
        self.servers = servers

    def run(self):
        try:
            import pandas as pd
            conn = sqlite3.connect(self.db_name, timeout=15)

            all_data = []
            for entry in self.list_items:
                if isinstance(entry, dict):
                    item_name = entry["name"]
                    item_lvl = entry["lvl"]
                else:
                    item_name = entry
                    item_lvl = None

                where_parts = ["item_name = ?"]
                params = [item_name]
                if item_lvl:
                    where_parts.append("item_lvl = ?")
                    params.append(item_lvl)
                if self.servers and len(self.servers) == 1:
                    where_parts.append("server = ?")
                    params.append(self.servers[0])
                elif self.servers:
                    placeholders = ",".join(["?"] * len(self.servers))
                    where_parts.append(f"server IN ({placeholders})")
                    params.extend(self.servers)
                where = " AND ".join(where_parts)
                rows = conn.execute(f"""
                    SELECT item_name, item_lvl, server, type, price FROM prices WHERE {where}
                """, params).fetchall()
                for r in rows:
                    all_data.append({"item": r[0], "lvl": r[1], "server": r[2], "type": r[3], "price": r[4]})
            conn.close()

            self.progress.emit(f"Veri hazir: {len(all_data)} satir, DataFrame isleniyor...")

            if not all_data:
                self.done.emit([])
                return

            df = pd.DataFrame(all_data)

            def smart_filter(prices):
                if len(prices) < 3:
                    return prices
                sorted_p = prices.sort_values()
                best_cv = 999
                best_med = sorted_p.iloc[0]
                for i in range(len(sorted_p)):
                    med = sorted_p.iloc[i]
                    cluster = prices[(prices >= med * 0.5) & (prices <= med * 2.0)]
                    if len(cluster) < 2:
                        continue
                    cv = cluster.std() / cluster.mean() if cluster.mean() > 0 else 999
                    if cv < best_cv:
                        best_cv = cv
                        best_med = med
                filtered = prices[(prices >= best_med * 0.5) & (prices <= best_med * 2.0)]
                return filtered if len(filtered) >= 2 else prices

            result_rows = []
            for entry in self.list_items:
                if isinstance(entry, dict):
                    item_name = entry["name"]
                    item_lvl = entry["lvl"]
                else:
                    item_name = entry
                    item_lvl = None

                idf = df[df["item"] == item_name]
                if idf.empty:
                    continue
                if item_lvl:
                    idf = idf[idf["lvl"] == item_lvl]
                    if idf.empty:
                        continue
                for srv in (self.servers or idf["server"].unique()):
                    sdf = idf[idf["server"] == srv]
                    sell_prices = smart_filter(sdf[sdf["type"] == "sell"]["price"])
                    buy_prices = smart_filter(sdf[sdf["type"] == "buy"]["price"])
                    sell_avg = int(sell_prices.mean()) if len(sell_prices) > 0 else 0
                    buy_avg = int(buy_prices.mean()) if len(buy_prices) > 0 else 0
                    makas = round((sell_avg - buy_avg) / buy_avg * 100, 1) if buy_avg > 0 and sell_avg > 0 else 0
                    cv_val = round(sell_prices.std() / sell_prices.mean() * 100, 1) if len(sell_prices) > 1 and sell_prices.mean() > 0 else 0
                    lvl_val = idf["lvl"].iloc[0] if len(idf) > 0 else ""
                    result_rows.append((
                        item_name, lvl_val, srv, sell_avg, buy_avg, makas, len(sdf), cv_val
                    ))

            result_rows.sort(key=lambda x: x[6], reverse=True)
            self.done.emit(result_rows)

        except Exception as e:
            self.error.emit(str(e))


class AnalyticsTab:
    def __init__(self, master, parent):
        self.master = master
        self.parent = parent
        self.all_items = []
        self.current_list_items = []
        self.current_list_id = None

        layout = QVBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        top = QHBoxLayout()

        lbl = QLabel("Sunucu:")
        lbl.setStyleSheet("color:#fff;font-size:11px;")
        top.addWidget(lbl)
        self.server_combo = QComboBox()
        self.server_combo.setFixedWidth(160)
        self.server_combo.setStyleSheet("background:#0a0a14;border:1px solid #1a1a2e;color:#fff;padding:4px 8px;")
        top.addWidget(self.server_combo)

        lbl2 = QLabel("Item:")
        lbl2.setStyleSheet("color:#fff;font-size:11px;")
        top.addWidget(lbl2)
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("Item ara... (orn. raptor)")
        self.item_search.setFixedWidth(280)
        self.item_search.setStyleSheet("background:#0a0a14;border:1px solid #1a1a2e;color:#00ff41;padding:4px 8px;font-family:Consolas;font-size:11px;")
        top.addWidget(self.item_search)

        self.completer = QCompleter([])
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.item_search.setCompleter(self.completer)

        lbl3 = QLabel("Lvl:")
        lbl3.setStyleSheet("color:#fff;font-size:11px;")
        top.addWidget(lbl3)
        self.lvl_combo = QComboBox()
        self.lvl_combo.setFixedWidth(60)
        self.lvl_combo.setStyleSheet("background:#0a0a14;border:1px solid #1a1a2e;color:#fff;padding:4px 8px;")
        self.lvl_combo.addItem("Tumu")
        self.lvl_combo.addItems(LVL_OPTIONS)
        top.addWidget(self.lvl_combo)

        btn = QPushButton("ANALIZ ET")
        btn.setFixedWidth(120)
        btn.setStyleSheet("background:#2ecc71;color:#fff;font-weight:700;border:none;padding:6px 12px;border-radius:4px;")
        btn.clicked.connect(self.load_analytics)
        top.addWidget(btn)

        top.addStretch()

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#888;font-size:11px;")
        top.addWidget(self.status_lbl)

        layout.addLayout(top)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet("QSplitter::handle { background:#1a1a2e; width:2px; }")

        left_panel = self._build_list_panel()
        main_splitter.addWidget(left_panel)

        right_panel = self._build_results_panel()
        main_splitter.addWidget(right_panel)

        main_splitter.setSizes([280, 900])

        layout.addWidget(main_splitter)

        self.load_servers()
        self.load_items()
        self.refresh_lists()

    def _build_list_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        grp = QGroupBox("KAYITLI LISTELER")
        grp.setStyleSheet(PANEL_STYLE)
        grp_layout = QVBoxLayout(grp)
        grp_layout.setSpacing(4)

        cat_row = QHBoxLayout()
        self.cat_combo = QComboBox()
        self.cat_combo.setStyleSheet("background:#0a0a14;border:1px solid #1a1a2e;color:#fff;padding:3px 6px;font-size:10px;")
        self.cat_combo.addItem("Tum Kategoriler")
        self.cat_combo.currentTextChanged.connect(self._filter_lists_by_category)
        cat_row.addWidget(self.cat_combo, 1)

        btn_new_cat = QPushButton("+Kategori")
        btn_new_cat.setFixedWidth(70)
        btn_new_cat.setStyleSheet("background:#1a1a2e;color:#aaa;border:1px solid #333;padding:3px;font-size:9px;border-radius:3px;")
        btn_new_cat.clicked.connect(self._add_category)
        cat_row.addWidget(btn_new_cat)
        grp_layout.addLayout(cat_row)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(LIST_STYLE)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._list_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._load_selected_list)
        grp_layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("Kaydet")
        btn_save.setStyleSheet("background:#2ecc71;color:#fff;border:none;padding:4px 8px;font-size:10px;border-radius:3px;")
        btn_save.clicked.connect(self._save_current_list)
        btn_row.addWidget(btn_save)

        btn_load = QPushButton("Yukle")
        btn_load.setStyleSheet("background:#2962FF;color:#fff;border:none;padding:4px 8px;font-size:10px;border-radius:3px;")
        btn_load.clicked.connect(self._load_selected_list)
        btn_row.addWidget(btn_load)

        btn_del = QPushButton("Sil")
        btn_del.setStyleSheet("background:#e74c3c;color:#fff;border:none;padding:4px 8px;font-size:10px;border-radius:3px;")
        btn_del.clicked.connect(self._delete_selected_list)
        btn_row.addWidget(btn_del)

        grp_layout.addLayout(btn_row)
        layout.addWidget(grp)

        grp2 = QGroupBox("LISTE ICERIGI (cift tikla: analiz et)")
        grp2.setStyleSheet(PANEL_STYLE)
        grp2_layout = QVBoxLayout(grp2)
        grp2_layout.setSpacing(4)

        self.item_list_widget = QListWidget()
        self.item_list_widget.setStyleSheet(LIST_STYLE)
        self.item_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.item_list_widget.customContextMenuRequested.connect(self._item_context_menu)
        self.item_list_widget.itemDoubleClicked.connect(self._analyze_single_item)
        grp2_layout.addWidget(self.item_list_widget)

        item_btn_row = QHBoxLayout()
        btn_add_item = QPushButton("+ Ekle")
        btn_add_item.setStyleSheet("background:#1a1a2e;color:#00ff41;border:1px solid #333;padding:3px 8px;font-size:10px;border-radius:3px;")
        btn_add_item.clicked.connect(self._add_item_to_list)
        item_btn_row.addWidget(btn_add_item)

        btn_rem_item = QPushButton("- Cikar")
        btn_rem_item.setStyleSheet("background:#1a1a2e;color:#e74c3c;border:1px solid #333;padding:3px 8px;font-size:10px;border-radius:3px;")
        btn_rem_item.clicked.connect(self._remove_item_from_list)
        item_btn_row.addWidget(btn_rem_item)

        btn_bulk = QPushButton("Toplu Analiz")
        btn_bulk.setStyleSheet("background:#a855f7;color:#fff;border:none;padding:3px 8px;font-size:10px;border-radius:3px;")
        btn_bulk.clicked.connect(self._bulk_analyze)
        item_btn_row.addWidget(btn_bulk)

        grp2_layout.addLayout(item_btn_row)
        layout.addWidget(grp2)

        return panel

    def _build_results_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.result_tabs = QTabWidget()
        self.result_tabs.setStyleSheet("""
            QTabWidget::pane { border:1px solid #1a1a2e; background:#000; }
            QTabBar::tab { background:#0a0a14; color:#888; border:1px solid #1a1a2e; padding:6px 14px; font-size:11px; }
            QTabBar::tab:selected { background:#1a1a2e; color:#00ff41; border-bottom-color:#00ff41; }
        """)

        tab_vol = self._make_tab_with_table(["Item", "Lvl", "Ort.", "Std", "CV%", "Min", "Max"])
        self.vol_table = tab_vol["table"]
        self.result_tabs.addTab(tab_vol["widget"], "Volatilite")

        tab_demand = self._make_tab_with_table(["Item", "Satici", "Ilan"])
        self.demand_table = tab_demand["table"]
        self.result_tabs.addTab(tab_demand["widget"], "Talep")

        tab_trend = self._make_tab_with_table(["Item", "Lvl", "Ilk Fiyat", "Son Fiyat", "Degisim %"])
        self.trend_table = tab_trend["table"]
        self.result_tabs.addTab(tab_trend["widget"], "Trend")

        tab_liq = self._make_tab_with_table(["Item", "Ilan", "Satici", "Ilk Tarih", "Son Tarih"])
        self.liq_table = tab_liq["table"]
        self.result_tabs.addTab(tab_liq["widget"], "Likidite")

        tab_detail = self._make_tab_with_table(["Item", "Sunucu", "Lvl", "Tip", "Fiyat", "Satici"])
        self.detail_table = tab_detail["table"]
        self.result_tabs.addTab(tab_detail["widget"], "Detay")

        tab_bulk = self._make_tab_with_table(["Item", "Lvl", "Sunucu", "Satis Ort", "Alis Ort", "Makas%", "Ilan", "CV%"])
        self.bulk_table = tab_bulk["table"]
        self.bulk_tab_widget = tab_bulk["widget"]
        self.result_tabs.addTab(self.bulk_tab_widget, "Toplu Analiz")

        layout.addWidget(self.result_tabs)

        return panel

    def _make_tab_with_table(self, headers):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(2, 2, 2, 2)
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setAlternatingRowColors(False)
        t.setStyleSheet(TABLE_STYLE)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        l.addWidget(t)
        return {"widget": w, "table": t}

    def load_servers(self):
        self.server_combo.addItem("Tum Sunucular")
        for group_name in SERVER_GROUPS:
            self.server_combo.addItem(group_name)
        try:
            conn = sqlite3.connect(self.master.db_name, timeout=15)
            rows = conn.execute(
                "SELECT DISTINCT server FROM prices WHERE server IS NOT NULL AND server != '' ORDER BY server"
            ).fetchall()
            conn.close()
            for r in rows:
                self.server_combo.addItem(r[0])
        except Exception:
            pass

    def load_items(self):
        try:
            conn = sqlite3.connect(self.master.db_name, timeout=15)
            rows = conn.execute(
                "SELECT DISTINCT item_name FROM prices WHERE item_name IS NOT NULL ORDER BY item_name"
            ).fetchall()
            conn.close()
            self.all_items = [r[0] for r in rows]
            self.completer.setModel(self.all_items)
        except Exception:
            self.all_items = []

    def _find_closest_item(self, search_text):
        if not search_text:
            return None
        lower = search_text.lower()
        for item in self.all_items:
            if item.lower() == lower:
                return item
        starts = [i for i in self.all_items if i.lower().startswith(lower)]
        if starts:
            return starts[0]
        contains = [i for i in self.all_items if lower in i.lower()]
        if contains:
            return contains[0]
        return search_text

    def _resolve_servers(self, selected):
        if selected == "Tum Sunucular":
            return None
        if selected in SERVER_GROUPS:
            return SERVER_GROUPS[selected]
        return [selected]

    def _get_item_lvl_filter(self):
        item_text = self.item_search.text().strip()
        lvl = self.lvl_combo.currentText().strip()
        if lvl == "Tumu":
            lvl = None
        item = self._find_closest_item(item_text) if item_text else None
        return item, lvl

    def load_analytics(self):
        server_text = self.server_combo.currentText()
        servers = self._resolve_servers(server_text)
        item, lvl = self._get_item_lvl_filter()

        self.status_lbl.setText("Hesaplaniyor...")
        for t in [self.vol_table, self.demand_table, self.trend_table, self.liq_table, self.detail_table]:
            t.setRowCount(0)

        try:
            from core.analytics import DataFrameAnalytics
            a = DataFrameAnalytics(self.master.db_name)

            if item:
                self._load_item_analysis(a, item, lvl, servers)
            else:
                self._load_general_analysis(a, servers)

            self.status_lbl.setText("Tamamlandi")

        except Exception as e:
            self.status_lbl.setText(f"Hata: {e}")

    def _load_general_analysis(self, a, servers):
        target = servers[0] if servers and len(servers) == 1 else None
        self._fill_vol_table(a.volatility(target).get("rows", []))
        self._fill_demand_table(a.demand(target).get("rows", []))
        self._fill_trend_table(a.trend(target).get("rows", []))
        self._fill_liq_table(a.liquidity(target).get("rows", []))

    def _load_item_analysis(self, a, item, lvl, servers):
        if servers and len(servers) > 1:
            self._fill_item_multi_server(item, lvl, servers)
        else:
            target = servers[0] if servers else None
            self._fill_item_single(item, lvl, target)

    def _fill_item_single(self, item, lvl, server):
        conn = sqlite3.connect(self.master.db_name, timeout=15)
        where_parts = ["item_name = ?"]
        params = [item]
        if server:
            where_parts.append("server = ?")
            params.append(server)
        if lvl:
            where_parts.append("item_lvl = ?")
            params.append(lvl)
        where = " AND ".join(where_parts)

        rows = conn.execute(f"""
            SELECT server, item_name, item_lvl, type, price, seller, timestamp
            FROM prices WHERE {where}
            ORDER BY timestamp DESC LIMIT 100
        """, params).fetchall()

        self.detail_table.setColumnCount(7)
        self.detail_table.setHorizontalHeaderLabels(["Item", "Sunucu", "Lvl", "Tip", "Fiyat", "Satici", "Tarih"])
        self.detail_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.detail_table.setItem(i, 0, QTableWidgetItem(str(r[1])))
            self.detail_table.setItem(i, 1, QTableWidgetItem(str(r[0])))
            self.detail_table.setItem(i, 2, QTableWidgetItem(str(r[2])))
            tip_item = QTableWidgetItem(str(r[3]))
            tip_item.setForeground(QColor("#2ecc71") if r[3] == "sell" else QColor("#e74c3c"))
            self.detail_table.setItem(i, 3, tip_item)
            self.detail_table.setItem(i, 4, QTableWidgetItem(f'{int(r[4]):,}'))
            self.detail_table.setItem(i, 5, QTableWidgetItem(str(r[5])[:25]))
            self.detail_table.setItem(i, 6, QTableWidgetItem(str(r[6])[:16] if r[6] else ""))

        prices = [r[4] for r in rows]
        self.vol_table.setColumnCount(5)
        self.vol_table.setHorizontalHeaderLabels(["Min", "Max", "Ort", "Adet", "Fark %"])
        if prices:
            min_p = int(min(prices))
            max_p = int(max(prices))
            avg_p = int(sum(prices) / len(prices))
            fark = round((max_p - min_p) / min_p * 100, 1) if min_p > 0 else 0
            self.vol_table.setRowCount(1)
            self.vol_table.setItem(0, 0, QTableWidgetItem(f'{min_p:,}'))
            self.vol_table.setItem(0, 1, QTableWidgetItem(f'{max_p:,}'))
            self.vol_table.setItem(0, 2, QTableWidgetItem(f'{avg_p:,}'))
            self.vol_table.setItem(0, 3, QTableWidgetItem(str(len(prices))))
            fark_item = QTableWidgetItem(f'%{fark}')
            fark_item.setForeground(QColor("#e74c3c") if fark > 20 else QColor("#f1c40f") if fark > 5 else QColor("#2ecc71"))
            self.vol_table.setItem(0, 4, fark_item)

        self.demand_table.setRowCount(0)
        self.trend_table.setRowCount(0)

        where_lp = ["item_name = ?"]
        params_lp = [item]
        if server:
            where_lp.append("server = ?")
            params_lp.append(server)
        if lvl:
            where_lp.append("item_lvl = ?")
            params_lp.append(lvl)
        where_l = " AND ".join(where_lp)
        liq_row = conn.execute(f"""
            SELECT server, COUNT(*), COUNT(DISTINCT seller), MIN(timestamp), MAX(timestamp)
            FROM prices WHERE {where_l}
        """, params_lp).fetchone()
        self.liq_table.setColumnCount(5)
        self.liq_table.setHorizontalHeaderLabels(["Sunucu", "Toplam Ilan", "Satici", "Ilk Tarih", "Son Tarih"])
        if liq_row and liq_row[1] > 0:
            self.liq_table.setRowCount(1)
            self.liq_table.setItem(0, 0, QTableWidgetItem(str(liq_row[0]) if liq_row[0] else "Tum"))
            self.liq_table.setItem(0, 1, QTableWidgetItem(str(liq_row[1])))
            self.liq_table.setItem(0, 2, QTableWidgetItem(str(liq_row[2])))
            self.liq_table.setItem(0, 3, QTableWidgetItem(str(liq_row[3])[:16] if liq_row[3] else ""))
            self.liq_table.setItem(0, 4, QTableWidgetItem(str(liq_row[4])[:16] if liq_row[4] else ""))
        conn.close()

    def _fill_item_multi_server(self, item, lvl, servers):
        import pandas as pd
        conn = sqlite3.connect(self.master.db_name, timeout=15)

        all_data = []
        for s in servers:
            where_parts = ["item_name = ?", "server = ?"]
            params = [item, s]
            if lvl:
                where_parts.append("item_lvl = ?")
                params.append(lvl)
            where = " AND ".join(where_parts)
            rows = conn.execute(f"""
                SELECT server, type, price FROM prices WHERE {where}
            """, params).fetchall()
            for r in rows:
                all_data.append({"server": r[0], "type": r[1], "price": r[2]})
        conn.close()

        if not all_data:
            for t in [self.vol_table, self.demand_table, self.trend_table, self.liq_table, self.detail_table]:
                t.setRowCount(0)
            return

        df = pd.DataFrame(all_data)

        def smart_filter(prices):
            if len(prices) < 3:
                return prices
            sorted_p = prices.sort_values()
            best_cv = 999
            best_med = sorted_p.iloc[0]
            best_count = 0
            for i in range(len(sorted_p)):
                med = sorted_p.iloc[i]
                cluster = prices[(prices >= med * 0.5) & (prices <= med * 2.0)]
                if len(cluster) < 2:
                    continue
                cv = cluster.std() / cluster.mean() if cluster.mean() > 0 else 999
                if cv < best_cv or (cv == best_cv and len(cluster) > best_count):
                    best_cv = cv
                    best_med = med
                    best_count = len(cluster)
            lower = best_med * 0.5
            upper = best_med * 2.0
            filtered = prices[(prices >= lower) & (prices <= upper)]
            return filtered if len(filtered) >= 2 else prices

        sell_df = df[df["type"] == "sell"].copy()
        buy_df = df[df["type"] == "buy"].copy()

        self.vol_table.setColumnCount(6)
        self.vol_table.setHorizontalHeaderLabels(["Sunucu", "Tip", "Ort. Fiyat", "Min", "Max", "Ilan"])
        vol_rows = []
        for srv in servers:
            srv_sell = smart_filter(sell_df[sell_df["server"] == srv]["price"])
            srv_buy = smart_filter(buy_df[buy_df["server"] == srv]["price"])
            if len(srv_sell) > 0:
                vol_rows.append((srv, "SATIS", int(srv_sell.mean()), int(srv_sell.min()), int(srv_sell.max()), len(srv_sell)))
            if len(srv_buy) > 0:
                vol_rows.append((srv, "ALIS", int(srv_buy.mean()), int(srv_buy.min()), int(srv_buy.max()), len(srv_buy)))
        vol_rows.sort(key=lambda x: x[2])
        self.vol_table.setRowCount(len(vol_rows))
        for i, (srv, tip, avg, mn, mx, cnt) in enumerate(vol_rows):
            self.vol_table.setItem(i, 0, QTableWidgetItem(srv))
            tip_item = QTableWidgetItem(tip)
            tip_item.setForeground(QColor("#2ecc71") if tip == "SATIS" else QColor("#e74c3c"))
            self.vol_table.setItem(i, 1, tip_item)
            self.vol_table.setItem(i, 2, QTableWidgetItem(f'{avg:,}'))
            self.vol_table.setItem(i, 3, QTableWidgetItem(f'{mn:,}'))
            self.vol_table.setItem(i, 4, QTableWidgetItem(f'{mx:,}'))
            self.vol_table.setItem(i, 5, QTableWidgetItem(str(cnt)))

        self.demand_table.setColumnCount(5)
        self.demand_table.setHorizontalHeaderLabels(["Sunucu", "Tip", "Ort. Fiyat", "En Dusuk", "Fark %"])
        sell_avgs = {}
        for srv in servers:
            srv_sell = smart_filter(sell_df[sell_df["server"] == srv]["price"])
            if len(srv_sell) > 0:
                sell_avgs[srv] = int(srv_sell.mean())
        sorted_svrs = sorted(sell_avgs.items(), key=lambda x: x[1])
        self.demand_table.setRowCount(len(sorted_svrs))
        if sorted_svrs:
            cheapest = sorted_svrs[0][1]
            for i, (srv, avg) in enumerate(sorted_svrs):
                self.demand_table.setItem(i, 0, QTableWidgetItem(srv))
                self.demand_table.setItem(i, 1, QTableWidgetItem("SATIS"))
                self.demand_table.setItem(i, 2, QTableWidgetItem(f'{avg:,}'))
                srv_sell = smart_filter(sell_df[sell_df["server"] == srv]["price"])
                self.demand_table.setItem(i, 3, QTableWidgetItem(f'{int(srv_sell.min()):,}'))
                fark = round((avg - cheapest) / cheapest * 100, 1) if cheapest > 0 else 0
                fark_item = QTableWidgetItem(f'+{fark}%' if fark > 0 else f'{fark}%')
                fark_item.setForeground(QColor("#e74c3c") if fark > 10 else QColor("#f1c40f") if fark > 0 else QColor("#2ecc71"))
                self.demand_table.setItem(i, 4, fark_item)

        self.trend_table.setColumnCount(4)
        self.trend_table.setHorizontalHeaderLabels(["Sunucu", "Alis (Ort)", "Satis (Ort)", "Makas %"])
        trend_rows = []
        for srv in servers:
            srv_sell = smart_filter(sell_df[sell_df["server"] == srv]["price"])
            srv_buy = smart_filter(buy_df[buy_df["server"] == srv]["price"])
            if len(srv_sell) > 0 and len(srv_buy) > 0:
                s_avg = int(srv_sell.mean())
                b_avg = int(srv_buy.mean())
                makas = round((s_avg - b_avg) / b_avg * 100, 1) if b_avg > 0 else 0
                trend_rows.append((srv, b_avg, s_avg, makas))
        trend_rows.sort(key=lambda x: x[3], reverse=True)
        self.trend_table.setRowCount(len(trend_rows))
        for i, (srv, b_avg, s_avg, makas) in enumerate(trend_rows):
            self.trend_table.setItem(i, 0, QTableWidgetItem(srv))
            self.trend_table.setItem(i, 1, QTableWidgetItem(f'{b_avg:,}'))
            self.trend_table.setItem(i, 2, QTableWidgetItem(f'{s_avg:,}'))
            makas_item = QTableWidgetItem(f'%{makas}')
            makas_item.setForeground(QColor("#2ecc71") if makas > 5 else QColor("#f1c40f") if makas > 0 else QColor("#e74c3c"))
            self.trend_table.setItem(i, 3, makas_item)

        self.liq_table.setColumnCount(5)
        self.liq_table.setHorizontalHeaderLabels(["Sunucu", "Toplam Ilan", "Satici", "Ilk Tarih", "Son Tarih"])
        liq_conn = sqlite3.connect(self.master.db_name, timeout=15)
        liq_rows = []
        for srv in servers:
            where_parts = ["item_name = ?", "server = ?"]
            params = [item, srv]
            if lvl:
                where_parts.append("item_lvl = ?")
                params.append(lvl)
            where = " AND ".join(where_parts)
            row = liq_conn.execute(f"""
                SELECT COUNT(*), COUNT(DISTINCT seller), MIN(timestamp), MAX(timestamp)
                FROM prices WHERE {where}
            """, params).fetchone()
            if row and row[0] > 0:
                liq_rows.append((srv, row[0], row[1], str(row[2])[:16] if row[2] else "", str(row[3])[:16] if row[3] else ""))
        liq_conn.close()
        liq_rows.sort(key=lambda x: x[1], reverse=True)
        self.liq_table.setRowCount(len(liq_rows))
        for i, (srv, cnt, satici, ilk, son) in enumerate(liq_rows):
            self.liq_table.setItem(i, 0, QTableWidgetItem(srv))
            self.liq_table.setItem(i, 1, QTableWidgetItem(str(cnt)))
            self.liq_table.setItem(i, 2, QTableWidgetItem(str(satici)))
            self.liq_table.setItem(i, 3, QTableWidgetItem(ilk))
            self.liq_table.setItem(i, 4, QTableWidgetItem(son))

        self.detail_table.setColumnCount(4)
        self.detail_table.setHorizontalHeaderLabels(["Sunucu", "Tip", "Ort Fiyat", "Ilan Sayisi"])
        self.detail_table.setRowCount(0)

    def _fill_vol_table(self, rows):
        self.vol_table.setColumnCount(7)
        self.vol_table.setHorizontalHeaderLabels(["Item", "Lvl", "Ort.", "Std", "CV%", "Min", "Max"])
        self.vol_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.vol_table.setItem(i, 0, QTableWidgetItem(r["item"]))
            self.vol_table.setItem(i, 1, QTableWidgetItem(str(r["lvl"])))
            self.vol_table.setItem(i, 2, QTableWidgetItem(f'{r["ortalama"]:,}'))
            self.vol_table.setItem(i, 3, QTableWidgetItem(f'{r["std"]:,.0f}'))
            cv_item = QTableWidgetItem(f'%{r["cv"]}')
            if r["cv"] > 50:
                cv_item.setForeground(QColor("#e74c3c"))
            elif r["cv"] > 20:
                cv_item.setForeground(QColor("#f1c40f"))
            else:
                cv_item.setForeground(QColor("#2ecc71"))
            self.vol_table.setItem(i, 4, cv_item)
            self.vol_table.setItem(i, 5, QTableWidgetItem(f'{r["min"]:,}'))
            self.vol_table.setItem(i, 6, QTableWidgetItem(f'{r["max"]:,}'))

    def _fill_demand_table(self, rows):
        self.demand_table.setColumnCount(3)
        self.demand_table.setHorizontalHeaderLabels(["Item", "Satici", "Ilan"])
        self.demand_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.demand_table.setItem(i, 0, QTableWidgetItem(r["item"]))
            self.demand_table.setItem(i, 1, QTableWidgetItem(str(r["satici"])))
            self.demand_table.setItem(i, 2, QTableWidgetItem(str(r["ilan"])))

    def _fill_trend_table(self, rows):
        self.trend_table.setColumnCount(5)
        self.trend_table.setHorizontalHeaderLabels(["Item", "Lvl", "Ilk Fiyat", "Son Fiyat", "Degisim %"])
        self.trend_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.trend_table.setItem(i, 0, QTableWidgetItem(r["item"]))
            self.trend_table.setItem(i, 1, QTableWidgetItem(str(r["lvl"])))
            self.trend_table.setItem(i, 2, QTableWidgetItem(f'{r["ilk_fiyat"]:,}'))
            self.trend_table.setItem(i, 3, QTableWidgetItem(f'{r["son_fiyat"]:,}'))
            deg = r["degisim"]
            deg_item = QTableWidgetItem(f'{"+" if deg > 0 else ""}{deg}%')
            if deg > 0:
                deg_item.setForeground(QColor("#2ecc71"))
            elif deg < 0:
                deg_item.setForeground(QColor("#e74c3c"))
            else:
                deg_item.setForeground(QColor("#888888"))
            self.trend_table.setItem(i, 4, deg_item)

    def _fill_liq_table(self, rows):
        self.liq_table.setColumnCount(5)
        self.liq_table.setHorizontalHeaderLabels(["Item", "Ilan", "Satici", "Ilk Tarih", "Son Tarih"])
        self.liq_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.liq_table.setItem(i, 0, QTableWidgetItem(r["item"]))
            self.liq_table.setItem(i, 1, QTableWidgetItem(str(r["ilan"])))
            self.liq_table.setItem(i, 2, QTableWidgetItem(str(r["satici"])))
            self.liq_table.setItem(i, 3, QTableWidgetItem(r["ilk"]))
            self.liq_table.setItem(i, 4, QTableWidgetItem(r["son"]))

    # ---- LIST MANAGEMENT ----

    def refresh_lists(self):
        self.list_widget.clear()
        try:
            from webapp.database import get_all_item_lists
            lists = get_all_item_lists()
            for lst in lists:
                item_text = f"[{lst['category']}] {lst['name']} ({len(lst['items'])} item)"
                lw = QListWidgetItem(item_text)
                lw.setData(Qt.UserRole, lst)
                self.list_widget.addItem(lw)
        except Exception:
            pass

        self.cat_combo.blockSignals(True)
        prev = self.cat_combo.currentText()
        self.cat_combo.clear()
        self.cat_combo.addItem("Tum Kategoriler")
        try:
            from webapp.database import get_list_categories
            for cat in get_list_categories():
                self.cat_combo.addItem(cat)
        except Exception:
            pass
        idx = self.cat_combo.findText(prev)
        if idx >= 0:
            self.cat_combo.setCurrentIndex(idx)
        self.cat_combo.blockSignals(False)

    def _filter_lists_by_category(self, cat):
        for i in range(self.list_widget.count()):
            lw = self.list_widget.item(i)
            data = lw.data(Qt.UserRole)
            if cat == "Tum Kategoriler":
                lw.setHidden(False)
            else:
                lw.setHidden(data.get("category", "") != cat)

    def _add_category(self):
        cat, ok = QInputDialog.getText(self.parent, "Yeni Kategori", "Kategori adi:")
        if ok and cat.strip():
            self.cat_combo.addItem(cat.strip())
            self.cat_combo.setCurrentText(cat.strip())

    def _save_current_list(self):
        if not self.current_list_items:
            QMessageBox.information(self.parent, "Bilgi", "Once liste icerigine item ekleyin.")
            return
        name, ok = QInputDialog.getText(self.parent, "Liste Kaydet", "Liste adi:")
        if not ok or not name.strip():
            return
        categories = []
        try:
            from webapp.database import get_list_categories
            categories = get_list_categories()
        except Exception:
            pass
        cat, ok2 = QInputDialog.getItem(self.parent, "Kategori", "Kategori secin:", ["Genel"] + categories, 0, False)
        if not ok2:
            cat = "Genel"

        try:
            from webapp.database import save_item_list
            save_item_list(name.strip(), cat, self.current_list_items)
            self.refresh_lists()
            self.status_lbl.setText(f"Liste kaydedildi: {name.strip()}")
        except Exception as e:
            QMessageBox.critical(self.parent, "Hata", str(e))

    def _load_selected_list(self):
        lw = self.list_widget.currentItem()
        if not lw:
            return
        data = lw.data(Qt.UserRole)
        self.current_list_id = data["id"]
        self.current_list_items = []
        for entry in data["items"]:
            if isinstance(entry, dict):
                self.current_list_items.append(entry)
            elif isinstance(entry, str):
                self.current_list_items.append({"name": entry, "lvl": "+0"})
        self._refresh_item_list_widget()

    def _delete_selected_list(self):
        lw = self.list_widget.currentItem()
        if not lw:
            return
        data = lw.data(Qt.UserRole)
        reply = QMessageBox.question(self.parent, "Sil", f"'{data['name']}' listesini silmek istediginden emin misin?")
        if reply == QMessageBox.Yes:
            try:
                from webapp.database import delete_item_list
                delete_item_list(data["id"])
                self.refresh_lists()
            except Exception as e:
                QMessageBox.critical(self.parent, "Hata", str(e))

    def _list_context_menu(self, pos):
        lw = self.list_widget.currentItem()
        if not lw:
            return
        menu = QMenu(self.parent)
        act_load = menu.addAction("Yukle")
        act_rename = menu.addAction("Yeniden Adlandir")
        act_del = menu.addAction("Sil")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))
        data = lw.data(Qt.UserRole)
        if action == act_load:
            self._load_selected_list()
        elif action == act_rename:
            name, ok = QInputDialog.getText(self.parent, "Yeniden Adlandir", "Yeni ad:", text=data["name"])
            if ok and name.strip():
                from webapp.database import update_item_list
                update_item_list(data["id"], name.strip(), data["category"], data["items"])
                self.refresh_lists()
        elif action == act_del:
            self._delete_selected_list()

    def _refresh_item_list_widget(self):
        self.item_list_widget.clear()
        for entry in self.current_list_items:
            if isinstance(entry, dict):
                self.item_list_widget.addItem(f"{entry['name']} {entry['lvl']}")
            else:
                self.item_list_widget.addItem(str(entry))

    def _add_item_to_list(self):
        text = self.item_search.text().strip()
        if not text:
            return
        item = self._find_closest_item(text)
        lvl = self.lvl_combo.currentText().strip()
        if lvl == "Tumu":
            lvl = "+0"
        entry = {"name": item, "lvl": lvl}
        already = any(e["name"] == item and e["lvl"] == lvl for e in self.current_list_items)
        if already:
            self.status_lbl.setText(f"Zaten listede: {item} {lvl}")
            return
        self.current_list_items.append(entry)
        self._refresh_item_list_widget()
        self.status_lbl.setText(f"Eklendi: {item} {lvl} ({len(self.current_list_items)} item)")

    def _remove_item_from_list(self):
        lw = self.item_list_widget.currentItem()
        if not lw:
            return
        idx = self.item_list_widget.row(lw)
        if 0 <= idx < len(self.current_list_items):
            removed = self.current_list_items.pop(idx)
            self._refresh_item_list_widget()
            self.status_lbl.setText(f"Cikarildi: {removed['name']} {removed['lvl']}")

    def _item_context_menu(self, pos):
        lw = self.item_list_widget.currentItem()
        if not lw:
            return
        menu = QMenu(self.parent)
        act_analyze = menu.addAction("Analiz Et")
        act_remove = menu.addAction("Listeden Cikar")
        action = menu.exec_(self.item_list_widget.mapToGlobal(pos))
        if action == act_analyze:
            self._analyze_single_item()
        elif action == act_remove:
            self._remove_item_from_list()

    def _analyze_single_item(self):
        lw = self.item_list_widget.currentItem()
        if not lw:
            return
        idx = self.item_list_widget.row(lw)
        if 0 <= idx < len(self.current_list_items):
            entry = self.current_list_items[idx]
            if isinstance(entry, dict):
                self.item_search.setText(entry["name"])
                lvl_text = entry["lvl"]
                lvl_idx = self.lvl_combo.findText(lvl_text)
                if lvl_idx >= 0:
                    self.lvl_combo.setCurrentIndex(lvl_idx)
            else:
                self.item_search.setText(str(entry))
            self.load_analytics()

    def _bulk_analyze(self):
        if not self.current_list_items:
            QMessageBox.information(self.parent, "Bilgi", "Listede item yok.")
            return

        self.status_lbl.setText(f"Toplu analiz: {len(self.current_list_items)} item...")
        self.result_tabs.setCurrentWidget(self.bulk_tab_widget)

        server_text = self.server_combo.currentText()
        servers = self._resolve_servers(server_text)

        self._bulk_worker = BulkWorker(self.master.db_name, self.current_list_items[:], servers)
        self._bulk_worker.done.connect(self._on_bulk_done)
        self._bulk_worker.error.connect(self._on_bulk_error)
        self._bulk_worker.progress.connect(lambda msg: self.status_lbl.setText(msg))
        self._bulk_worker.start()

    def _on_bulk_done(self, result_rows):
        self.bulk_table.setRowCount(len(result_rows))
        for i, (item, lv, srv, s_avg, b_avg, makas, cnt, cv) in enumerate(result_rows):
            self.bulk_table.setItem(i, 0, QTableWidgetItem(item))
            self.bulk_table.setItem(i, 1, QTableWidgetItem(str(lv)))
            self.bulk_table.setItem(i, 2, QTableWidgetItem(srv))
            self.bulk_table.setItem(i, 3, QTableWidgetItem(f'{s_avg:,}' if s_avg else "-"))
            self.bulk_table.setItem(i, 4, QTableWidgetItem(f'{b_avg:,}' if b_avg else "-"))
            makas_item = QTableWidgetItem(f'%{makas}')
            makas_item.setForeground(QColor("#2ecc71") if makas > 5 else QColor("#f1c40f") if makas > 0 else QColor("#e74c3c"))
            self.bulk_table.setItem(i, 5, makas_item)
            self.bulk_table.setItem(i, 6, QTableWidgetItem(str(cnt)))
            cv_item = QTableWidgetItem(f'%{cv}')
            cv_item.setForeground(QColor("#e74c3c") if cv > 50 else QColor("#f1c40f") if cv > 20 else QColor("#2ecc71"))
            self.bulk_table.setItem(i, 7, cv_item)
        self.status_lbl.setText(f"Toplu analiz tamamlandi: {len(result_rows)} satir")

    def _on_bulk_error(self, msg):
        self.status_lbl.setText(f"Toplu analiz hatasi: {msg}")
