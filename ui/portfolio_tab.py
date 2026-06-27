import os
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QLineEdit, QComboBox, QTableWidget,
                                QTableWidgetItem, QHeaderView, QAbstractItemView,
                                QMenu, QMessageBox, QFileDialog, QDialog,
                                QGridLayout, QCheckBox, QApplication, QCheckBox as QCheckBoxWidget)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QAction, QShortcut, QKeySequence
import pandas as pd
import numpy as np
from datetime import datetime
from ui.searchable_combo import SearchableComboBox


class PortfolioTab:
    SERVER_NAMES = ["ZERO", "PANDORA", "AGARTHA", "FELIS", "DESTAN", "MINARK", "DRYADS", "OREADS"]
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
        self.parent = parent_tab
        self.portfolio = []
        self._updating = False
        self.setup_ui()
        self.load_settings()
        self.load_portfolio_from_text()

    def setup_ui(self):
        layout = QVBoxLayout(self.parent)
        layout.setSpacing(2)
        layout.setContentsMargins(3, 3, 3, 3)

        btn_style = "font-size:11px; padding:2px 6px;"
        btn_sm = "font-size:11px; padding:2px 6px;"

        srv_frame = QHBoxLayout(); srv_frame.setSpacing(4)
        srv_frame.addWidget(QLabel("Sunucu:"))
        self.server_price_combo = QComboBox()
        self.server_price_combo.blockSignals(True)
        self.server_price_combo.addItems(["Tum Sunucular"] + [f"{n} (Tumu)" for n in self.SERVER_NAMES] + self.SERVER_LIST)
        self.server_price_combo.setFixedWidth(140)
        self.server_price_combo.blockSignals(False)
        def on_server_changed():
            self.master.stats_cache.clear()
            self.render_portfolio_ui()
        self.server_price_combo.currentTextChanged.connect(on_server_changed)
        srv_frame.addWidget(self.server_price_combo)
        srv_frame.addStretch()
        layout.addLayout(srv_frame)

        top = QHBoxLayout(); top.setSpacing(4)
        top.addWidget(QLabel("Item:"))
        self.port_item_combo = SearchableComboBox(values=self.master.all_items_list, width=140, placeholder_text="Item ara..."); top.addWidget(self.port_item_combo)
        top.addWidget(QLabel("Lvl:"))
        self.port_lvl_combo = QComboBox(); self.port_lvl_combo.addItems([str(opt) for opt in self.master.lvl_options]);
        if "+0" in self.master.lvl_options:
            self.port_lvl_combo.setCurrentText("+0")
        else:
            self.port_lvl_combo.setCurrentIndex(0)
        self.port_lvl_combo.setCurrentText("+0"); self.port_lvl_combo.setMinimumWidth(50)
        top.addWidget(self.port_lvl_combo)
        top.addWidget(QLabel("Adet:"))
        self.port_count_entry = QLineEdit("1"); self.port_count_entry.setFixedWidth(40)
        top.addWidget(self.port_count_entry)
        top.addWidget(QLabel("Alis:"))
        buy_strategies = ["Auto", "Kar Odaklı", "Spread Filtreli", "Min-Max Rastgele", "Otonom", "Min", "Min-Max Ortasi", "Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar", "Max %3 Vergi", "Q1", "Medyan", "Mod", "Q3", "Max", "%95 Alt", "%95 Ust", "Manuel"]
        self.port_buy_strat_combo = QComboBox(); self.port_buy_strat_combo.addItems(buy_strategies); self.port_buy_strat_combo.setCurrentText("Medyan"); self.port_buy_strat_combo.setFixedWidth(100)
        top.addWidget(self.port_buy_strat_combo)
        self.port_buy_entry = QLineEdit(); self.port_buy_entry.setPlaceholderText("Manuel"); self.port_buy_entry.setFixedWidth(60)
        top.addWidget(self.port_buy_entry)
        top.addWidget(QLabel("Satis:"))
        sell_strategies = ["Auto", "Kar Odaklı", "Spread Filtreli", "Min-Max Rastgele", "Otonom", "Min", "Q1", "Medyan", "Mod", "Q3", "Max", "%95 Alt", "%95 Ust", "Manuel"]
        self.port_sell_strat_combo = QComboBox(); self.port_sell_strat_combo.addItems(sell_strategies); self.port_sell_strat_combo.setCurrentText("Auto"); self.port_sell_strat_combo.setFixedWidth(100)
        top.addWidget(self.port_sell_strat_combo)
        self.port_sell_entry = QLineEdit(); self.port_sell_entry.setPlaceholderText("Manuel"); self.port_sell_entry.setFixedWidth(60)
        top.addWidget(self.port_sell_entry)
        btn_add = QPushButton("+ Ekle"); btn_add.setStyleSheet(f"background:#2ecc71; color:white; {btn_sm}"); btn_add.setFixedWidth(45); btn_add.clicked.connect(self.add_portfolio_item)
        top.addWidget(btn_add)
        top.addStretch()
        layout.addLayout(top)

        actions = QHBoxLayout(); actions.setSpacing(4)
        b = QPushButton("Kaydet"); b.setStyleSheet(f"background:#f39c12; color:white; {btn_style}"); b.clicked.connect(self.save_portfolio_manual); actions.addWidget(b)
        b = QPushButton("Yenile"); b.setStyleSheet(f"background:teal; color:white; {btn_style}"); b.clicked.connect(self.refresh_analysis_data); actions.addWidget(b)
        b = QPushButton("Sil"); b.setStyleSheet(f"background:#e74c3c; color:white; {btn_style}"); b.clicked.connect(self._delete_selected_rows); actions.addWidget(b)
        b = QPushButton("\u2191"); b.setStyleSheet(f"background:#555; color:white; {btn_style}"); b.setFixedWidth(28); b.clicked.connect(self._move_up); actions.addWidget(b)
        b = QPushButton("\u2193"); b.setStyleSheet(f"background:#555; color:white; {btn_style}"); b.setFixedWidth(28); b.clicked.connect(self._move_down); actions.addWidget(b)
        b = QPushButton("\u21E8"); b.setStyleSheet(f"background:#444; color:white; {btn_style}"); b.setFixedWidth(28); b.setToolTip("En Uste Tas (Ctrl+Home)"); b.clicked.connect(self._move_to_top); actions.addWidget(b)
        b = QPushButton("\u21E9"); b.setStyleSheet(f"background:#444; color:white; {btn_style}"); b.setFixedWidth(28); b.setToolTip("En Alta Tas (Ctrl+End)"); b.clicked.connect(self._move_to_bottom); actions.addWidget(b)
        actions.addWidget(QLabel("Sir:"))
        self.move_index_entry = QLineEdit(); self.move_index_entry.setFixedWidth(35); self.move_index_entry.setPlaceholderText("#"); self.move_index_entry.returnPressed.connect(self._move_to_index); actions.addWidget(self.move_index_entry)
        b = QPushButton("Excel"); b.setStyleSheet(f"background:#3498db; color:white; {btn_style}"); b.clicked.connect(self.export_portfolio_excel); actions.addWidget(b)
        b = QPushButton("AI Analiz"); b.setStyleSheet(f"background:#2ca02c; color:white; {btn_style}"); b.clicked.connect(self.master.run_ai_prediction); actions.addWidget(b)
        b = QPushButton("Grafik"); b.setStyleSheet(f"background:#1f77b4; color:white; {btn_style}"); b.clicked.connect(self.master.show_ai_graph); actions.addWidget(b)
        actions.addSpacing(10)
        actions.addWidget(QLabel("Liste:"))
        self.saved_list_combo = QComboBox(); self.saved_list_combo.setFixedWidth(95); self._refresh_saved_lists(); actions.addWidget(self.saved_list_combo)
        b = QPushButton("Yukle"); b.setStyleSheet(f"background:#8e44ad; color:white; {btn_sm}"); b.clicked.connect(self._load_selected_list); actions.addWidget(b)
        b = QPushButton("Kaydet2"); b.setStyleSheet(f"background:#e67e22; color:white; {btn_sm}"); b.clicked.connect(self._save_as_new_list); actions.addWidget(b)
        b = QPushButton("Sil"); b.setStyleSheet(f"background:#e74c3c; color:white; {btn_sm}"); b.clicked.connect(self._delete_selected_list); actions.addWidget(b)
        actions.addStretch()
        layout.addLayout(actions)

        settings_row = QHBoxLayout(); settings_row.setSpacing(6)
        settings_row.addWidget(QLabel("Makas:"))
        self.spread_lower = QLineEdit("25"); self.spread_lower.setFixedWidth(35)
        settings_row.addWidget(self.spread_lower)
        settings_row.addWidget(QLabel("/"))
        self.spread_upper = QLineEdit("75"); self.spread_upper.setFixedWidth(35)
        settings_row.addWidget(self.spread_upper)
        settings_row.addSpacing(8)
        settings_row.addWidget(QLabel("IQR:"))
        self.iqr_entry = QLineEdit(self._load_iqr_config()); self.iqr_entry.setFixedWidth(35); self.iqr_entry.setStyleSheet("background:#fff3cd;padding:2px;border-radius:3px;font-weight:bold;")
        settings_row.addWidget(self.iqr_entry)
        b = QPushButton("Kaydet"); b.setStyleSheet(f"background:#ffc107;color:#000;{btn_sm}"); b.setFixedWidth(45); b.clicked.connect(self._save_iqr_config); settings_row.addWidget(b)
        settings_row.addSpacing(8)
        b = QPushButton("TETIKLE"); b.setStyleSheet(f"background:#e74c3c;color:white;font-weight:bold;{btn_sm}"); b.setFixedWidth(60); b.clicked.connect(self._trigger_analysis); settings_row.addWidget(b)
        settings_row.addStretch()
        layout.addLayout(settings_row)

        sell_strategies = ["Auto", "Kar Odaklı", "Spread Filtreli", "Min-Max Rastgele", "Otonom", "Min", "Q1", "Medyan", "Mod", "Q3", "Max", "%95 Alt", "%95 Ust", "Manuel"]
        bulk1 = QHBoxLayout(); bulk1.setSpacing(4)
        bulk1.addWidget(QLabel("Alis:"))
        self.bulk_buy_combo = QComboBox(); self.bulk_buy_combo.addItems(buy_strategies); self.bulk_buy_combo.setCurrentText("Medyan"); self.bulk_buy_combo.setFixedWidth(80)
        bulk1.addWidget(self.bulk_buy_combo)
        self.bulk_buy_entry = QLineEdit(); self.bulk_buy_entry.setPlaceholderText("Manuel"); self.bulk_buy_entry.setFixedWidth(60)
        bulk1.addWidget(self.bulk_buy_entry)
        b = QPushButton("Secili"); b.setStyleSheet(f"background:#8e44ad; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_bulk_logic("buy", False)); bulk1.addWidget(b)
        b = QPushButton("Tumu"); b.setStyleSheet(f"background:#9b59b6; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_bulk_logic("buy", True)); bulk1.addWidget(b)
        bulk1.addWidget(QLabel("Kar%:"))
        self.entry_buy_margin = QLineEdit("20"); self.entry_buy_margin.setFixedWidth(40); bulk1.addWidget(self.entry_buy_margin)
        bulk1.addWidget(QLabel("Satis:"))
        self.bulk_sell_combo = QComboBox(); self.bulk_sell_combo.addItems(sell_strategies); self.bulk_sell_combo.setCurrentText("Auto"); self.bulk_sell_combo.setFixedWidth(80)
        bulk1.addWidget(self.bulk_sell_combo)
        self.bulk_sell_entry = QLineEdit(); self.bulk_sell_entry.setPlaceholderText("Manuel"); self.bulk_sell_entry.setFixedWidth(60)
        bulk1.addWidget(self.bulk_sell_entry)
        b = QPushButton("Secili"); b.setStyleSheet(f"background:#2980b9; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_bulk_logic("sell", False)); bulk1.addWidget(b)
        b = QPushButton("Tumu"); b.setStyleSheet(f"background:#3498db; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_bulk_logic("sell", True)); bulk1.addWidget(b)
        self.entry_custom_margin = QLineEdit(); self.entry_custom_margin.setPlaceholderText("15"); self.entry_custom_margin.setFixedWidth(40); bulk1.addWidget(self.entry_custom_margin)
        b = QPushButton("% Uygula"); b.setStyleSheet(f"background:#2e7d32; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_percentage_margin(True)); bulk1.addWidget(b)
        bulk1.addStretch()
        layout.addLayout(bulk1)

        bulk2 = QHBoxLayout(); bulk2.setSpacing(4)
        b = QPushButton("^"); b.setStyleSheet(btn_sm); b.clicked.connect(self.move_item_up); bulk2.addWidget(b)
        b = QPushButton("v"); b.setStyleSheet(btn_sm); b.clicked.connect(self.move_item_down); bulk2.addWidget(b)
        b = QPushButton("Secili Kopyala"); b.setStyleSheet(f"background:#7f8c8d; color:white; {btn_sm}"); b.clicked.connect(self._copy_selected_rows); bulk2.addWidget(b)
        b = QPushButton("Tumu Kopyala"); b.setStyleSheet(f"background:#95a5a6; color:white; {btn_sm}"); b.clicked.connect(self._copy_all_rows); bulk2.addWidget(b)
        b = QPushButton("Alis Sabit"); b.setStyleSheet(f"background:#e67e22; color:white; {btn_sm}"); b.clicked.connect(lambda: self._toggle_all_fix("buy", True)); bulk2.addWidget(b)
        b = QPushButton("Alis Kaldir"); b.setStyleSheet(f"background:#d35400; color:white; {btn_sm}"); b.clicked.connect(lambda: self._toggle_all_fix("buy", False)); bulk2.addWidget(b)
        b = QPushButton("Satis Sabit"); b.setStyleSheet(f"background:#2980b9; color:white; {btn_sm}"); b.clicked.connect(lambda: self._toggle_all_fix("sell", True)); bulk2.addWidget(b)
        b = QPushButton("Satis Kaldir"); b.setStyleSheet(f"background:#2471a3; color:white; {btn_sm}"); b.clicked.connect(lambda: self._toggle_all_fix("sell", False)); bulk2.addWidget(b)
        bulk2.addStretch()
        layout.addLayout(bulk2)

        search_frame = QHBoxLayout()
        search_frame.addWidget(QLabel("Item Ara:"))
        self.port_search_entry = QLineEdit()
        self.port_search_entry.setPlaceholderText("Filtrelemek istediginiz item adini yazin...")
        self.port_search_entry.textChanged.connect(self.render_portfolio_ui)
        search_frame.addWidget(self.port_search_entry)
        layout.addLayout(search_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(15)
        self.table.setHorizontalHeaderLabels([
            "Item", "Lvl", "Adet", "Alis Fiyati", "Alis Stratejisi", "Top. Maliyet",
            "Satis Fiyati", "Satis Stratejisi", "Beklenen Kar", "Durum", "Sunucu",
            "Gecmis Dusuk", "Gecmis Yuksek", "Alis Sabit", "Satis Sabit"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 150)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.double_click_edit)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellChanged.connect(self._on_cell_changed)
        delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.table)
        delete_shortcut.activated.connect(self._delete_selected_rows)
        up_shortcut = QShortcut(QKeySequence("Ctrl+Up"), self.table)
        up_shortcut.activated.connect(self._move_up)
        down_shortcut = QShortcut(QKeySequence("Ctrl+Down"), self.table)
        down_shortcut.activated.connect(self._move_down)
        top_shortcut = QShortcut(QKeySequence("Ctrl+Home"), self.table)
        top_shortcut.activated.connect(self._move_to_top)
        bottom_shortcut = QShortcut(QKeySequence("Ctrl+End"), self.table)
        bottom_shortcut.activated.connect(self._move_to_bottom)
        cut_shortcut = QShortcut(QKeySequence("Ctrl+X"), self.table)
        cut_shortcut.activated.connect(self._cut_selected)
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self.table)
        paste_shortcut.activated.connect(self._paste_cut)
        layout.addWidget(self.table)

        self.render_portfolio_ui()

    def _get_selected_server(self):
        text = self.server_price_combo.currentText()
        if text == "Tum Sunucular" or text.endswith("(Tumu)"):
            return text
        return text

    def _get_filtered_server(self):
        return self.server_price_combo.currentText()

    def _item_matches_filter(self, item, filter_server):
        if filter_server == "Tum Sunucular":
            return True
        item_server = item.get("server", "")
        if not item_server:
            return True
        if filter_server.endswith("(Tumu)"):
            return item_server.startswith(filter_server.replace(" (Tumu)", ""))
        return item_server == filter_server

    def add_portfolio_item(self):
        name = self.port_item_combo.get().strip()
        lvl = self.port_lvl_combo.currentText().strip()
        buy_strat = self.port_buy_strat_combo.currentText()
        sell_strat = self.port_sell_strat_combo.currentText()
        server = self._get_selected_server()

        try:
            count = int(self.port_count_entry.text())
        except:
            count = 1

        buy_price = 0
        manual_val = self.port_buy_entry.text().replace(".", "").replace(",", "")

        if buy_strat == "Manuel" and manual_val:
            try:
                buy_price = float(manual_val)
            except:
                QMessageBox.warning(self.master, "Hata", "Lutfen gecerli bir manuel alis fiyati girin.")
                return
        else:
            db_lvl = "" if lvl in ["+0", "0"] else lvl
            stats = self.master.analyzer.get_item_stats(name, db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=server)
            if buy_strat in ("Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar"):
                if stats and stats.get('sell'):
                    key_map = {"Min*0.97+%Kar": "min", "Q1*0.97+%Kar": "q1", "%95 Alt*0.97+%Kar": "ci_low"}
                    base = stats['sell'].get(key_map[buy_strat], 0)
                    try:
                        margin = float(self.entry_buy_margin.text().strip())
                    except ValueError:
                        margin = 0
                    buy_price = base * 0.97 / (1 + margin / 100)
            elif stats and stats.get('buy'):
                if buy_strat == "Min-Max Ortasi":
                    buy_price = (stats['buy'].get("min", 0) + stats['buy'].get("max", 0)) / 2
                elif buy_strat == "Auto":
                    b = stats['buy']
                    b_min = b.get("min", 0)
                    b_q1 = b.get("q1", 0)
                    b_max = b.get("max", 0)
                    net_max = b_max * 0.97
                    if net_max <= 0:
                        buy_price = 0
                    elif net_max <= b_min:
                        buy_price = b_min
                    else:
                        buy_price = b_q1
                elif buy_strat == "Kar Odaklı":
                    b = stats.get("buy", {})
                    s = stats.get("sell", {})
                    best_profit = -999999999
                    best_price = 0
                    for mv in [b.get("min",0), b.get("q1",0), b.get("median",0), b.get("mode",0), b.get("q3",0), b.get("max",0), b.get("ci_low",0), b.get("ci_high",0)]:
                        if mv <= 0: continue
                        profit = (s.get("q3", 0) * 0.97) - mv
                        if profit > best_profit:
                            best_profit = profit
                            best_price = mv
                    buy_price = best_price
                elif buy_strat == "Spread Filtreli":
                    raw_b = stats.get('buy_raw')
                    if raw_b is not None and not raw_b.empty:
                        pct = float(self.spread_lower.text().strip()) / 100.0
                        buy_price = float(np.percentile(raw_b, pct * 100))
                    else:
                        buy_price = stats['buy'].get('q1', 0)
                elif buy_strat == "Min-Max Rastgele":
                    import random
                    b_min = stats['buy'].get("min", 0)
                    b_max = stats['buy'].get("max", 0)
                    if b_min > 0 and b_max > b_min:
                        buy_price = random.randint(int(b_min), int(b_max))
                    else:
                        buy_price = b_min
                elif buy_strat == "Otonom":
                    b = stats['buy']
                    if b.get("min", 0) > 0 and b.get("q1", 0) > b.get("min", 0):
                        buy_price = b.get("q1", 0)
                    else:
                        buy_price = b.get("min", 0)
                elif buy_strat == "Max %3 Vergi":
                    buy_price = stats['buy'].get("max", 0) * 0.97
                else:
                    s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
                    buy_price = stats['buy'].get(s_map.get(buy_strat, "median"), 0)

        sell_price = 0
        sell_manual_val = self.port_sell_entry.text().replace(".", "").replace(",", "")
        if sell_strat == "Manuel" and sell_manual_val:
            try:
                sell_price = float(sell_manual_val)
            except:
                QMessageBox.warning(self.master, "Hata", "Lutfen gecerli bir manuel satis fiyati girin.")
                return

        self.portfolio.append({
            "name": name, "lvl": lvl, "buy_price": buy_price,
            "buy_strategy": buy_strat, "sell_strategy": sell_strat,
            "count": count, "sell_price": sell_price, "server": server
        })
        self.auto_save()
        self.render_portfolio_ui()

    def save_portfolio_to_text(self):
        try:
            file_path = os.path.join(self.master.BASE_DIR, "portfolio_data.json")
            data = []
            for item in self.portfolio:
                data.append({
                    "name": item["name"],
                    "lvl": item.get("lvl", ""),
                    "buy_price": int(item.get("buy_price", 0)),
                    "buy_strategy": item.get("buy_strategy", "Auto"),
                    "count": int(item.get("count", 1)),
                    "sell_strategy": item.get("sell_strategy", "Auto"),
                    "sell_price": int(item.get("sell_price", 0)),
                    "server": item.get("server", ""),
                    "buy_fixed": item.get("buy_fixed", False),
                    "sell_fixed": item.get("sell_fixed", False),
                })
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Portfoy kaydedilirken hata: {e}")

    def auto_save(self):
        self.save_portfolio_to_text()

    def save_portfolio_manual(self):
        self.save_portfolio_to_text()
        QMessageBox.information(self.master, "Basari", "Portfoy listeniz portfolio_data.json dosyasina kaydedildi!")

    def load_portfolio_from_text(self):
        json_path = os.path.join(self.master.BASE_DIR, "portfolio_data.json")
        txt_path = os.path.join(self.master.BASE_DIR, "excel_export_item_list.txt")

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    self.portfolio = json.load(f)
                return
            except Exception as e:
                print(f"JSON portfoy yuklenirken hata: {e}")

        if os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    self.portfolio = []
                    for line in f:
                        parts = line.strip().split("|")
                        if len(parts) >= 3:
                            self.portfolio.append({
                                "name": parts[0], "lvl": parts[1],
                                "buy_price": float(parts[2]),
                                "buy_strategy": parts[3] if len(parts) > 3 else "Auto",
                                "count": int(parts[4]) if len(parts) > 4 else 1,
                                "sell_strategy": parts[5] if len(parts) > 5 else "Auto",
                                "sell_price": float(parts[6]) if len(parts) > 6 and parts[6] else 0,
                                "server": parts[7] if len(parts) > 7 else "",
                                "buy_fixed": parts[8] == "1" if len(parts) > 8 else False,
                                "sell_fixed": parts[9] == "1" if len(parts) > 9 else False,
                            })
                self.save_portfolio_to_text()
                print("Eski txt dosyasi JSON'a cevirildi.")
            except Exception as e:
                print(f"Portfoy yuklenirken hata: {e}")

    def _resolve_db_server(self, filter_server):
        if not filter_server or filter_server == "Tum Sunucular":
            return None
        if filter_server.endswith("(Tumu)"):
            return filter_server.replace(" (Tumu)", "")
        return filter_server

    def render_portfolio_ui(self):
        self._updating = True
        self.table.setRowCount(0)
        search_term = self.port_search_entry.text().strip().lower() if hasattr(self, 'port_search_entry') else ""
        filter_server = self._get_filtered_server()
        db_server = self._resolve_db_server(filter_server)

        try:
            lower_percentile = float(self.spread_lower.text().strip()) / 100.0
        except ValueError:
            lower_percentile = 0.25
        try:
            upper_percentile = float(self.spread_upper.text().strip()) / 100.0
        except ValueError:
            upper_percentile = 0.75

        s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}

        from webapp.database import get_historical_extremes, get_previous_prices

        for i, item in enumerate(self.portfolio):
            if search_term and search_term not in item["name"].lower():
                continue
            if not self._item_matches_filter(item, filter_server):
                continue

            buy_fixed = item.get("buy_fixed", False)
            sell_fixed = item.get("sell_fixed", False)
            buy_strat = item.get("buy_strategy", "Manuel")
            sell_strat = item.get("sell_strategy", "Auto")
            count = item.get("count", 1)

            db_lvl = "" if item["lvl"] in ["+0", "0"] else item["lvl"]
            stats = self.master.get_cached_stats(item["name"], db_lvl, server=db_server)

            if buy_fixed or buy_strat == "Manuel":
                current_buy_price = item["buy_price"]
                auto_buy_detail = item.get('auto_buy_detail', '')
            elif stats and stats.get("buy"):
                if buy_strat == "Min-Max Ortasi":
                    current_buy_price = (stats["buy"].get("min", 0) + stats["buy"].get("max", 0)) / 2
                    auto_buy_detail = ''
                elif buy_strat == "Auto":
                    b = stats.get("buy", {})
                    b_min = b.get("min", 0)
                    b_q1 = b.get("q1", 0)
                    b_max = b.get("max", 0)
                    net_max = b_max * 0.97
                    if net_max <= 0:
                        current_buy_price = 0
                        auto_buy_detail = "Veri Yok"
                    elif net_max <= b_min:
                        current_buy_price = b_min
                        auto_buy_detail = "Min Alim"
                    else:
                        current_buy_price = b_q1
                        auto_buy_detail = "Q1 Alim"
                    item['auto_buy_detail'] = auto_buy_detail
                elif buy_strat == "Kar Odaklı":
                    b = stats.get("buy", {})
                    s = stats.get("sell", {})
                    best_profit = -999999999
                    best_price = 0
                    best_name = ""
                    for mk, mv in [("min", b.get("min",0)), ("Q1", b.get("q1",0)), ("Medyan", b.get("median",0)), ("Mod", b.get("mode",0)), ("Q3", b.get("q3",0)), ("Max", b.get("max",0)), ("%95 Alt", b.get("ci_low",0)), ("%95 Ust", b.get("ci_high",0))]:
                        if mv <= 0: continue
                        sell_q3 = s.get("q3", 0)
                        profit = (sell_q3 * 0.97) - mv
                        if profit > best_profit:
                            best_profit = profit
                            best_price = mv
                            best_name = mk
                    current_buy_price = best_price
                    auto_buy_detail = f"Kar/{best_name}" if best_name else "Veri Yok"
                    item['auto_buy_detail'] = auto_buy_detail
                elif buy_strat == "Spread Filtreli":
                    raw_b = stats.get('buy_raw')
                    if raw_b is not None and not raw_b.empty:
                        pct = float(self.spread_lower.text().strip()) / 100.0
                        current_buy_price = float(np.percentile(raw_b, pct * 100))
                        auto_buy_detail = f"Spread/%{pct*100:.0f}"
                    else:
                        current_buy_price = stats["buy"].get("q1", 0)
                        auto_buy_detail = "Spread/Q1"
                    item['auto_buy_detail'] = auto_buy_detail
                elif buy_strat == "Min-Max Rastgele":
                    import random
                    b_min = stats["buy"].get("min", 0)
                    b_max = stats["buy"].get("max", 0)
                    if b_min > 0 and b_max > b_min:
                        current_buy_price = random.randint(int(b_min), int(b_max))
                    else:
                        current_buy_price = b_min
                    auto_buy_detail = "Rastgele"
                    item['auto_buy_detail'] = auto_buy_detail
                elif buy_strat == "Otonom":
                    b = stats.get("buy", {})
                    b_min = b.get("min", 0)
                    b_q1 = b.get("q1", 0)
                    b_med = b.get("median", 0)
                    b_q3 = b.get("q3", 0)
                    b_max = b.get("max", 0)
                    if b_min > 0 and b_q1 > b_min:
                        current_buy_price = b_q1
                        auto_buy_detail = "Otonom/Q1"
                    elif b_min > 0:
                        current_buy_price = b_min
                        auto_buy_detail = "Otonom/Min"
                    else:
                        current_buy_price = 0
                        auto_buy_detail = "Veri Yok"
                    item['auto_buy_detail'] = auto_buy_detail
                elif buy_strat == "Max %3 Vergi":
                    current_buy_price = stats['buy'].get("max", 0) * 0.97
                    auto_buy_detail = "Max*0.97"
                    item['auto_buy_detail'] = auto_buy_detail
                elif buy_strat in ("Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar") and stats.get("sell"):
                    key_map = {"Min*0.97+%Kar": "min", "Q1*0.97+%Kar": "q1", "%95 Alt*0.97+%Kar": "ci_low"}
                    try:
                        margin = float(self.entry_buy_margin.text().strip())
                    except ValueError:
                        margin = 0
                    base = stats["sell"].get(key_map[buy_strat], 0)
                    current_buy_price = base * 0.97 / (1 + margin / 100)
                    auto_buy_detail = ''
                else:
                    current_buy_price = stats['buy'].get(s_map.get(buy_strat, "median"), 0)
                    auto_buy_detail = ''
            else:
                current_buy_price = item["buy_price"]
                auto_buy_detail = ''

            if not buy_fixed:
                item["buy_price"] = current_buy_price

            if sell_fixed:
                sell_price = item.get('sell_price', 0)
                auto_detail = item.get('auto_sell_detail', '')
            elif stats and stats.get("sell"):
                if sell_strat == "Auto":
                    raw_s = stats.get('sell_raw')
                    if raw_s is not None and not raw_s.empty:
                        pct = float(self.spread_upper.text().strip()) / 100.0
                        raw_price = float(np.percentile(raw_s, pct * 100))
                        sell_price = raw_price
                        auto_detail = f"Auto/%{pct*100:.0f}"
                    elif stats["sell"].get("q3", 0) > 0:
                        sell_price = stats["sell"]["q3"]
                        auto_detail = "Q3 Satis"
                    else:
                        sell_price = stats["sell"].get("max", 0)
                        auto_detail = "Max Satis"
                    item['auto_sell_detail'] = auto_detail
                elif sell_strat == "Kar Odaklı":
                    b = stats.get("buy", {})
                    s = stats.get("sell", {})
                    buy_price = item.get("buy_price", 0)
                    best_profit = -999999999
                    best_price = 0
                    best_name = ""
                    for mk, mv in [("min", s.get("min",0)), ("Q1", s.get("q1",0)), ("Medyan", s.get("median",0)), ("Mod", s.get("mode",0)), ("Q3", s.get("q3",0)), ("Max", s.get("max",0)), ("%95 Alt", s.get("ci_low",0)), ("%95 Ust", s.get("ci_high",0))]:
                        if mv <= 0: continue
                        profit = (mv * 0.97) - buy_price
                        if profit > best_profit:
                            best_profit = profit
                            best_price = mv
                            best_name = mk
                    sell_price = best_price
                    auto_detail = f"Kar/{best_name}" if best_name else "Veri Yok"
                    item['auto_sell_detail'] = auto_detail
                elif sell_strat == "Spread Filtreli":
                    raw_s = stats.get('sell_raw')
                    if raw_s is not None and not raw_s.empty:
                        pct = float(self.spread_upper.text().strip()) / 100.0
                        sell_price = float(np.percentile(raw_s, pct * 100))
                        auto_detail = f"Spread/%{pct*100:.0f}"
                    else:
                        sell_price = stats["sell"].get("q3", 0)
                        auto_detail = "Spread/Q3"
                    item['auto_sell_detail'] = auto_detail
                elif sell_strat == "Min-Max Rastgele":
                    import random
                    s_min = stats["sell"].get("min", 0)
                    s_max = stats["sell"].get("max", 0)
                    if s_min > 0 and s_max > s_min:
                        sell_price = random.randint(int(s_min), int(s_max))
                    else:
                        sell_price = s_max
                    auto_detail = "Rastgele"
                    item['auto_sell_detail'] = auto_detail
                elif sell_strat == "Otonom":
                    s = stats.get("sell", {})
                    s_min = s.get("min", 0)
                    s_q1 = s.get("q1", 0)
                    s_med = s.get("median", 0)
                    s_q3 = s.get("q3", 0)
                    s_max = s.get("max", 0)
                    if s_max > 0 and s_q3 < s_max:
                        sell_price = s_q3
                        auto_detail = "Otonom/Q3"
                    elif s_max > 0:
                        sell_price = s_max
                        auto_detail = "Otonom/Max"
                    else:
                        sell_price = 0
                        auto_detail = "Veri Yok"
                    item['auto_sell_detail'] = auto_detail
                elif "%" in str(sell_strat):
                    try:
                        profit_margin = float(sell_strat.replace("%", "").strip())
                        sell_price = (item["buy_price"] * (1 + (profit_margin / 100))) / 0.97
                    except ValueError:
                        sell_price = item["buy_price"] * 1.10
                    auto_detail = ''
                else:
                    sell_price = stats["sell"].get(s_map.get(sell_strat, "median"), 0)
                    auto_detail = ''
                if not sell_fixed:
                    item['sell_price'] = sell_price
            else:
                sell_price = item.get('sell_price', 0)
                auto_detail = item.get('auto_sell_detail', '')

            total_cost = item["buy_price"] * count
            if stats and stats.get("sell") and stats.get("buy"):
                unit_profit = (sell_price * 0.97) - item["buy_price"]
                total_profit = unit_profit * count
                status = "Kar" if total_profit > 0 else "Zarar"
                row_color = QColor(0x2e, 0xcc, 0x71) if total_profit > 0 else QColor(0xe7, 0x4c, 0x3c)
                if item["buy_price"] > 0 and not buy_fixed:
                    loss_pct = abs(unit_profit) / item["buy_price"]
                    spread_range = upper_percentile - lower_percentile
                    if total_profit < 0 and loss_pct > spread_range:
                        continue
            else:
                total_profit = 0
                status = ""
                row_color = QColor(0xf3, 0x9c, 0x12)

            hist = get_historical_extremes(item["name"], db_lvl, server=db_server)
            prev = get_previous_prices(item["name"], db_lvl, server=db_server)

            row = self.table.rowCount()
            self.table.insertRow(row)
            display_server = item.get("server", "") or "Tum"
            buy_metric = item.get('auto_buy_metric', buy_strat) if buy_strat == "Auto" else buy_strat
            sell_metric = item.get('auto_sell_metric', sell_strat) if sell_strat == "Auto" else sell_strat
            vals = [
                item["name"], item["lvl"], str(count), f"{item['buy_price']:,.0f}",
                buy_strat, f"{total_cost:,.0f}",
                f"{sell_price:,.0f}", sell_strat, f"{total_profit:,.0f}", status, display_server,
                f"{min(hist['buy']['min'], hist['sell']['min']):,.0f}" if hist['buy']['min'] and hist['sell']['min'] else (f"{hist['buy']['min']:,.0f}" if hist['buy']['min'] else (f"{hist['sell']['min']:,.0f}" if hist['sell']['min'] else "-")),
                f"{max(hist['buy']['max'], hist['sell']['max']):,.0f}" if hist['buy']['max'] and hist['sell']['max'] else (f"{hist['buy']['max']:,.0f}" if hist['buy']['max'] else (f"{hist['sell']['max']:,.0f}" if hist['sell']['max'] else "-")),
            ]
            for j, val in enumerate(vals):
                cell = QTableWidgetItem(str(val))
                if j in (8, 9):
                    cell.setForeground(row_color)
                self.table.setItem(row, j, cell)

            cb_buy = QTableWidgetItem()
            cb_buy.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb_buy.setCheckState(Qt.Checked if buy_fixed else Qt.Unchecked)
            cb_buy.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 13, cb_buy)

            cb_sell = QTableWidgetItem()
            cb_sell.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb_sell.setCheckState(Qt.Checked if sell_fixed else Qt.Unchecked)
            cb_sell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 14, cb_sell)

        self._updating = False

    def eventFilter(self, obj, event):
        if obj == self.table and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Delete:
            self._delete_selected_rows()
            return True
        return super().eventFilter(obj, event)

    def _delete_selected_rows(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        visible_rows = self._get_visible_rows()
        deleted_row = min(s.row() for s in selected)
        rows_to_delete = sorted([s.row() for s in selected], reverse=True)
        for row in rows_to_delete:
            if row < len(visible_rows):
                idx = visible_rows[row]
                if 0 <= idx < len(self.portfolio):
                    del self.portfolio[idx]
        self.auto_save()
        self._updating = True
        self.render_portfolio_ui()
        self._updating = False
        new_count = self.table.rowCount()
        if new_count > 0:
            select_row = min(deleted_row, new_count - 1)
            self.table.selectRow(select_row)

    def _move_up(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if row <= 0:
            return
        visible_rows = self._get_visible_rows()
        if row < len(visible_rows) and row - 1 < len(visible_rows):
            idx = visible_rows[row]
            prev_idx = visible_rows[row - 1]
            self.portfolio[idx], self.portfolio[prev_idx] = self.portfolio[prev_idx], self.portfolio[idx]
            self.auto_save()
            self._updating = True
            self.render_portfolio_ui()
            self._updating = False
            self.table.selectRow(row - 1)

    def _move_down(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        visible_rows = self._get_visible_rows()
        if row < len(visible_rows) - 1 and row < len(visible_rows):
            idx = visible_rows[row]
            next_idx = visible_rows[row + 1]
            self.portfolio[idx], self.portfolio[next_idx] = self.portfolio[next_idx], self.portfolio[idx]
            self.auto_save()
            self._updating = True
            self.render_portfolio_ui()
            self._updating = False
            self.table.selectRow(row + 1)

    def _move_to_top(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        visible_rows = self._get_visible_rows()
        if row < len(visible_rows):
            idx = visible_rows[row]
            item = self.portfolio.pop(idx)
            self.portfolio.insert(0, item)
            self.auto_save()
            self._updating = True
            self.render_portfolio_ui()
            self._updating = False
            self.table.selectRow(0)

    def _move_to_bottom(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        visible_rows = self._get_visible_rows()
        if row < len(visible_rows):
            idx = visible_rows[row]
            item = self.portfolio.pop(idx)
            self.portfolio.append(item)
            self.auto_save()
            self._updating = True
            self.render_portfolio_ui()
            self._updating = False
            self.table.selectRow(self.table.rowCount() - 1)

    def _move_to_index(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        visible_rows = self._get_visible_rows()
        try:
            target = int(self.move_index_entry.text().strip()) - 1
        except ValueError:
            return
        if row < len(visible_rows) and 0 <= target < len(self.portfolio):
            idx = visible_rows[row]
            item = self.portfolio.pop(idx)
            target = min(target, len(self.portfolio))
            self.portfolio.insert(target, item)
            self.auto_save()
            self._updating = True
            self.render_portfolio_ui()
            self._updating = False
            self.table.selectRow(target)
        self.move_index_entry.clear()

    def _cut_selected(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        visible_rows = self._get_visible_rows()
        row = selected[0].row()
        if row < len(visible_rows):
            self._clipboard_idx = visible_rows[row]

    def _paste_cut(self):
        if not hasattr(self, '_clipboard_idx') or self._clipboard_idx is None:
            return
        if self._clipboard_idx >= len(self.portfolio):
            return
        selected = self.table.selectionModel().selectedRows()
        visible_rows = self._get_visible_rows()
        if selected:
            target_row = selected[0].row()
            if target_row < len(visible_rows):
                target_idx = visible_rows[target_row]
            else:
                target_idx = len(self.portfolio)
        else:
            target_idx = len(self.portfolio)
        item = self.portfolio.pop(self._clipboard_idx)
        if self._clipboard_idx < target_idx:
            target_idx -= 1
        target_idx = min(target_idx, len(self.portfolio))
        self.portfolio.insert(target_idx, item)
        self._clipboard_idx = None
        self.auto_save()
        self._updating = True
        self.render_portfolio_ui()
        self._updating = False
        self.table.selectRow(target_idx)

    def _load_iqr_config(self):
        try:
            cfg_path = os.path.join(self.master.BASE_DIR, "analyzer_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
                return str(cfg.get("iqr_multiplier", "1.0"))
        except:
            pass
        return "1.0"

    def _save_iqr_config(self):
        val = self.iqr_entry.text().strip()
        try:
            float(val)
        except:
            QMessageBox.warning(self.master, "Hata", "IQR carpani sayi olmali!")
            return
        cfg_path = os.path.join(self.master.BASE_DIR, "analyzer_config.json")
        cfg = {}
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                cfg = json.load(f)
        cfg["iqr_multiplier"] = float(val)
        with open(cfg_path, "w") as f:
            json.dump(cfg, f, indent=2)
        self.master.engine.analyzer.iqr_multiplier = float(val)
        QMessageBox.information(self.master, "Kayitli", f"IQR carpani {val} olarak ayarlandi.")

    def _trigger_analysis(self):
        self._save_iqr_config()
        self.refresh_analysis_data()
        QMessageBox.information(self.master, "Tamam", "Analiz tetiklendi ve veriler yenilendi.")

    def _auto_buy_calc(self, stats):
        s = stats.get('sell', {})
        b = stats.get('buy', {})
        max_buy = b.get('max', 0)
        if max_buy <= 0:
            return 0, "Veri Yok"
        net_max = max_buy * 0.97
        metrics = [
            ("Min", b.get('min', 0)),
            ("%95 Alt", b.get('ci_low', 0)),
            ("Q1", b.get('q1', 0)),
            ("Mod", b.get('mode', 0)),
            ("Medyan", b.get('median', 0)),
            ("%95 Ust", b.get('ci_high', 0)),
            ("Q3", b.get('q3', 0)),
            ("Max", max_buy),
        ]
        best = None
        for name, price in metrics:
            if price <= 0:
                continue
            if net_max >= price:
                best = (name, price)
        if best:
            return best[1], f"{best[0]} Alim"
        return b.get('min', 0), "Min Alim"

    def _auto_sell_calc(self, stats, buy_price):
        s = stats.get('sell', {})
        try:
            spread_limit = float(self.spread_lower.text().strip()) / 100.0
        except:
            spread_limit = 0.25
        metrics = [
            ("Min", s.get('min', 0)),
            ("%95 Alt", s.get('ci_low', 0)),
            ("Q1", s.get('q1', 0)),
            ("Mod", s.get('mode', 0)),
            ("Medyan", s.get('median', 0)),
            ("%95 Ust", s.get('ci_high', 0)),
            ("Q3", s.get('q3', 0)),
            ("Max", s.get('max', 0)),
        ]
        profit_candidates = []
        loss_candidates = []
        for name, price in metrics:
            if price <= 0:
                continue
            net = price * 0.97
            profit = net - buy_price
            if profit > 0:
                profit_candidates.append((name, price, profit))
            else:
                loss_pct = abs(profit) / buy_price if buy_price > 0 else 0
                if loss_pct <= spread_limit:
                    loss_candidates.append((name, price, abs(profit)))
        if profit_candidates:
            profit_candidates.sort(key=lambda x: x[1])
            best = profit_candidates[0]
            return best[1], f"Auto/{best[0]}"
        if loss_candidates:
            loss_candidates.sort(key=lambda x: x[2])
            best = loss_candidates[0]
            return best[1], f"Auto/{best[0]}"
        return s.get('max', 0), "Auto/Max"

    def export_portfolio_excel(self):
        filter_server = self._get_filtered_server()
        visible_items = [item for item in self.portfolio if self._item_matches_filter(item, filter_server)]
        if not visible_items:
            QMessageBox.warning(self.master, "Uyari", f"Bu sunucuda disa aktarilacak item yok.")
            return
        export_data = []
        db_server = self._resolve_db_server(filter_server)
        from webapp.database import get_historical_extremes, get_previous_prices
        for item in visible_items:
            db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
            stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
            sell_strat = item.get('sell_strategy', 'Auto')
            sell_price = 0
            strat_str = sell_strat
            if stats and stats.get('sell'):
                if sell_strat == "Auto":
                    sell_price, strat_str, _ = self.master.calculate_auto_sell(stats, item['buy_price'])
                else:
                    s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
                    sell_price = stats['sell'].get(s_map.get(sell_strat, "median"), 0)
            count = item.get('count', 1)
            hist = get_historical_extremes(item['name'], db_lvl, server=db_server)
            prev = get_previous_prices(item['name'], db_lvl, server=db_server)
            export_data.append({
                "Item Adi": item['name'], "Seviye": item['lvl'], "Adet": count,
                "Birim Alis Maliyeti": item['buy_price'], "Alis Stratejisi": item.get('buy_strategy', 'Manuel'),
                "Toplam Alis Maliyeti": item['buy_price'] * count, "Satis Stratejisi": strat_str,
                "Birim Hedef Satis Fiyati": sell_price,
                "Vergi Dusulmus Net Kasa (Birim)": sell_price * 0.97 if sell_price > 0 else 0,
                "Toplam Beklenen Net Kar": ((sell_price * 0.97) - item['buy_price']) * count,
                "Gecmis En Dusuk Alis": hist['buy']['min'] or 0,
                "Gecmis En Yuksek Alis": hist['buy']['max'] or 0,
                "Onceki Alis": prev['buy']['previous'] or 0,
                "Onceki Satis": prev['sell']['previous'] or 0,
            })
        df = pd.DataFrame(export_data)
        file_path, _ = QFileDialog.getSaveFileName(self.master, "Excel Kaydet", f"Fiyat_Listesi_{datetime.now().strftime('%H%M')}.xlsx", "Excel (*.xlsx)")
        if file_path:
            try:
                df.to_excel(file_path, index=False)
                QMessageBox.information(self.master, "Basari", "Portfoy listeniz Excel'e aktarildi!")
                os.startfile(file_path)
            except Exception as e:
                QMessageBox.critical(self.master, "Hata", f"Excel'e aktarilamadi: {e}")

    def refresh_analysis_data(self):
        self.master.stats_cache.clear()
        filter_server = self._get_filtered_server()
        try:
            lower_percentile = float(self.spread_lower.text().strip()) / 100.0
        except ValueError:
            lower_percentile = 0.25
        s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
        db_server = self._resolve_db_server(filter_server)
        for item in self.portfolio:
            if not self._item_matches_filter(item, filter_server):
                continue
            if item.get("buy_fixed", False):
                continue
            strat = item.get("buy_strategy", "Manuel")
            if strat != "Manuel":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                if strat in ("Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar"):
                    if stats and stats.get('sell'):
                        key_map = {"Min*0.97+%Kar": "min", "Q1*0.97+%Kar": "q1", "%95 Alt*0.97+%Kar": "ci_low"}
                        base = stats['sell'].get(key_map[strat], 0)
                        try:
                            margin = float(self.entry_buy_margin.text().strip())
                        except ValueError:
                            margin = 0
                        item['buy_price'] = base * 0.97 / (1 + margin / 100)
                elif stats and stats.get('buy'):
                    if strat == "Min-Max Ortasi":
                        item['buy_price'] = (stats['buy'].get("min", 0) + stats['buy'].get("max", 0)) / 2
                    elif strat == "Auto":
                        raw_b = stats.get('buy_raw')
                        if raw_b is not None and not raw_b.empty:
                            item['buy_price'] = np.percentile(raw_b, lower_percentile * 100)
                        else:
                            item['buy_price'] = stats['buy'].get('median', 0)
                    elif strat == "Max %3 Vergi":
                        item['buy_price'] = stats['buy'].get("max", 0) * 0.97
                    else:
                        item['buy_price'] = stats['buy'].get(s_map.get(strat, "median"), 0)
                else:
                    item['buy_price'] = 0
        self.render_portfolio_ui()
        self.master.update_opportunity_list()
        self.auto_save()

    def apply_bulk_logic(self, target_type, apply_to_all):
        if not self.portfolio:
            return
        if apply_to_all:
            target_indices = range(len(self.portfolio))
        else:
            selected = self.table.selectionModel().selectedRows()
            if not selected:
                QMessageBox.warning(self.master, "Uyari", "Lutfen secin veya 'Tumune' kullanin.")
                return
            target_indices = [s.row() for s in selected]

        db_server = self._resolve_db_server(self._get_filtered_server())

        strat = self.bulk_buy_combo.currentText() if target_type == "buy" else self.bulk_sell_combo.currentText()
        manual_entry = self.bulk_buy_entry if target_type == "buy" else self.bulk_sell_entry
        s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}

        manual_price = 0
        if strat == "Manuel":
            manual_val = manual_entry.text().replace(".", "").replace(",", "")
            if not manual_val:
                QMessageBox.warning(self.master, "Uyari", "Manuel secili ama deger girilmemis!")
                return
            try:
                manual_price = float(manual_val)
            except:
                QMessageBox.warning(self.master, "Hata", "Gecersiz sayi!")
                return

        for idx in target_indices:
            item = self.portfolio[idx]
            if target_type == "sell":
                item['sell_strategy'] = strat
                if strat == "Manuel":
                    item['sell_price'] = manual_price
                elif strat == "Auto":
                    item['sell_price'] = 0
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('sell') and item.get('buy_price', 0) > 0:
                        item['sell_price'], item['sell_strategy'] = self._auto_sell_calc(stats, item['buy_price'])
                elif strat == "Kar Odaklı":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('sell') and item.get('buy_price', 0) > 0:
                        s = stats.get("sell", {})
                        buy_p = item.get("buy_price", 0)
                        best_profit = -999999999
                        best_price = 0
                        for mv in [s.get("min",0), s.get("q1",0), s.get("median",0), s.get("mode",0), s.get("q3",0), s.get("max",0), s.get("ci_low",0), s.get("ci_high",0)]:
                            if mv <= 0: continue
                            profit = (mv * 0.97) - buy_p
                            if profit > best_profit:
                                best_profit = profit
                                best_price = mv
                        item['sell_price'] = best_price
                elif strat == "Spread Filtreli":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats:
                        raw_s = stats.get('sell_raw')
                        try:
                            upper_percentile = float(self.spread_upper.text().strip()) / 100.0
                        except:
                            upper_percentile = 0.75
                        if raw_s is not None and not raw_s.empty:
                            item['sell_price'] = float(np.percentile(raw_s, upper_percentile * 100))
                        elif stats.get('sell'):
                            item['sell_price'] = stats['sell'].get("q3", 0)
                elif strat == "Min-Max Rastgele":
                    import random
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('sell'):
                        s_min = stats['sell'].get("min", 0)
                        s_max = stats['sell'].get("max", 0)
                        if s_min > 0 and s_max > s_min:
                            item['sell_price'] = random.randint(int(s_min), int(s_max))
                elif strat == "Otonom":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('sell'):
                        s = stats['sell']
                        if s.get("max", 0) > 0 and s.get("q3", 0) < s.get("max", 0):
                            item['sell_price'] = s.get("q3", 0)
                        else:
                            item['sell_price'] = s.get("max", 0)
                else:
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('sell'):
                        item['sell_price'] = stats['sell'].get(s_map.get(strat, "median"), 0)

            elif target_type == "buy":
                item['buy_strategy'] = strat
                if strat == "Manuel":
                    item['buy_price'] = manual_price
                elif strat == "Auto":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('buy'):
                        b = stats['buy']
                        b_min = b.get("min", 0)
                        b_q1 = b.get("q1", 0)
                        b_max = b.get("max", 0)
                        net_max = b_max * 0.97
                        if net_max <= 0:
                            item['buy_price'] = 0
                        elif net_max <= b_min:
                            item['buy_price'] = b_min
                        else:
                            item['buy_price'] = b_q1
                elif strat == "Kar Odaklı":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('buy') and stats.get('sell'):
                        b = stats.get("buy", {})
                        s = stats.get("sell", {})
                        best_profit = -999999999
                        best_price = 0
                        for mv in [b.get("min",0), b.get("q1",0), b.get("median",0), b.get("mode",0), b.get("q3",0), b.get("max",0), b.get("ci_low",0), b.get("ci_high",0)]:
                            if mv <= 0: continue
                            profit = (s.get("q3", 0) * 0.97) - mv
                            if profit > best_profit:
                                best_profit = profit
                                best_price = mv
                        item['buy_price'] = best_price
                elif strat == "Spread Filtreli":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats:
                        raw_b = stats.get('buy_raw')
                        try:
                            lower_percentile = float(self.spread_lower.text().strip()) / 100.0
                        except:
                            lower_percentile = 0.25
                        if raw_b is not None and not raw_b.empty:
                            item['buy_price'] = float(np.percentile(raw_b, lower_percentile * 100))
                        elif stats.get('buy'):
                            item['buy_price'] = stats['buy'].get("q1", 0)
                elif strat == "Min-Max Rastgele":
                    import random
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('buy'):
                        b_min = stats['buy'].get("min", 0)
                        b_max = stats['buy'].get("max", 0)
                        if b_min > 0 and b_max > b_min:
                            item['buy_price'] = random.randint(int(b_min), int(b_max))
                elif strat == "Otonom":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('buy'):
                        b = stats['buy']
                        if b.get("min", 0) > 0 and b.get("q1", 0) > b.get("min", 0):
                            item['buy_price'] = b.get("q1", 0)
                        else:
                            item['buy_price'] = b.get("min", 0)
                elif strat in ("Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar"):
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('sell'):
                        key_map = {"Min*0.97+%Kar": "min", "Q1*0.97+%Kar": "q1", "%95 Alt*0.97+%Kar": "ci_low"}
                        base = stats['sell'].get(key_map[strat], 0)
                        try:
                            margin = float(self.entry_buy_margin.text().strip())
                        except ValueError:
                            margin = 0
                        item['buy_price'] = base * 0.97 / (1 + margin / 100)
                elif strat == "Max %3 Vergi":
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('buy'):
                        item['buy_price'] = stats['buy'].get("max", 0) * 0.97
                else:
                    db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                    stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
                    if stats and stats.get('buy'):
                        if strat == "Min-Max Ortasi":
                            item['buy_price'] = (stats['buy'].get("min", 0) + stats['buy'].get("max", 0)) / 2
                        else:
                            item['buy_price'] = stats['buy'].get(s_map.get(strat, "median"), item.get('buy_price', 0))
        self.auto_save()
        self.render_portfolio_ui()
        QMessageBox.information(self.master, "Basari", "Strateji ve makas filtreleri uygulandi!")

    def apply_percentage_margin(self, apply_to_all):
        if not self.portfolio:
            return
        if apply_to_all:
            target_indices = range(len(self.portfolio))
        else:
            selected = self.table.selectionModel().selectedRows()
            if not selected:
                QMessageBox.warning(self.master, "Uyari", "Lutfen islem yapilacak ogeleri secin.")
                return
            target_indices = [s.row() for s in selected]

        margin_value = self.entry_custom_margin.text().strip()
        if not margin_value:
            QMessageBox.warning(self.master, "Uyari", "Lutfen uygulanacak bir % kar degeri girin.")
            return
        for idx in target_indices:
            self.portfolio[idx]['sell_strategy'] = f"%{margin_value}"
            self.portfolio[idx]['sell_price'] = 0
        self.auto_save()
        self.render_portfolio_ui()
        QMessageBox.information(self.master, "Basari", f"Satis stratejileri %{margin_value} kar hedefiyle guncellendi!")

    def move_item_up(self):
        selected = self.table.currentRow()
        if selected > 0:
            self.portfolio[selected], self.portfolio[selected - 1] = self.portfolio[selected - 1], self.portfolio[selected]
            self.auto_save()
            self.render_portfolio_ui()
            self.table.selectRow(selected - 1)

    def move_item_down(self):
        selected = self.table.currentRow()
        if 0 <= selected < len(self.portfolio) - 1:
            self.portfolio[selected], self.portfolio[selected + 1] = self.portfolio[selected + 1], self.portfolio[selected]
            self.auto_save()
            self.render_portfolio_ui()
            self.table.selectRow(selected + 1)

    def delete_selected_items(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        visible_rows = self._get_visible_rows()
        indices = sorted([s.row() for s in selected], reverse=True)
        for row in indices:
            if row < len(visible_rows):
                idx = visible_rows[row]
                if 0 <= idx < len(self.portfolio):
                    del self.portfolio[idx]
        self.auto_save()
        self._updating = True
        self.render_portfolio_ui()
        self._updating = False

    def double_click_edit(self, index):
        visible_rows = self._get_visible_rows()
        row = index.row()
        if row < len(visible_rows):
            self.open_buy_edit_popup(visible_rows[row])

    def open_buy_edit_popup(self, index):
        item = self.portfolio[index]
        dialog = QDialog(self.master)
        dialog.setWindowTitle(f"Duzenle: {item['name']} {item['lvl']}")
        dialog.setFixedSize(400, 520)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"Mevcut Alis: {item['buy_price']:,.0f}"))
        layout.addWidget(QLabel("Adet:"))
        count_entry = QLineEdit(str(item.get('count', 1)))
        layout.addWidget(count_entry)

        layout.addWidget(QLabel("Alis Stratejisi:"))
        buy_strat_combo = QComboBox()
        buy_strat_combo.addItems(["Auto", "Kar Odaklı", "Spread Filtreli", "Min-Max Rastgele", "Otonom", "Min", "Min-Max Ortasi", "Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar", "Max %3 Vergi", "Q1", "Medyan", "Mod", "Q3", "Max", "%95 Alt", "%95 Ust", "Manuel"])
        buy_strat_combo.setCurrentText(item.get("buy_strategy", "Medyan"))
        layout.addWidget(buy_strat_combo)

        buy_entry = QLineEdit()
        buy_entry.setPlaceholderText("Manuel Secilirse Fiyat Girin")
        layout.addWidget(buy_entry)

        layout.addWidget(QLabel(f"Mevcut Satis: {item.get('sell_price', 0):,.0f}"))
        layout.addWidget(QLabel("Satis Stratejisi:"))
        sell_strat_combo = QComboBox()
        sell_strat_combo.addItems(["Auto", "Kar Odaklı", "Spread Filtreli", "Min-Max Rastgele", "Otonom", "Min", "Q1", "Medyan", "Mod", "Q3", "Max", "%95 Alt", "%95 Ust", "Manuel"])
        sell_strat_combo.setCurrentText(item.get("sell_strategy", "Auto"))
        layout.addWidget(sell_strat_combo)

        sell_entry = QLineEdit()
        sell_entry.setPlaceholderText("Manuel Secilirse Fiyat Girin")
        layout.addWidget(sell_entry)

        def save_changes():
            buy_strat = buy_strat_combo.currentText()
            new_buy_price = item.get('buy_price', 0)
            try:
                new_count = int(count_entry.text())
                item['count'] = new_count if new_count > 0 else 1
            except:
                pass

            if buy_strat == "Manuel":
                val = buy_entry.text().replace(",", "").replace(".", "")
                if val:
                    try:
                        new_buy_price = float(val)
                    except ValueError:
                        QMessageBox.warning(dialog, "Hata", "Gecerli bir alis fiyati girin.")
                        return
            elif buy_strat in ("Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar"):
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('sell'):
                    key_map = {"Min*0.97+%Kar": "min", "Q1*0.97+%Kar": "q1", "%95 Alt*0.97+%Kar": "ci_low"}
                    base = stats['sell'].get(key_map[buy_strat], 0)
                    try:
                        margin = float(self.entry_buy_margin.text().strip())
                    except ValueError:
                        margin = 0
                    new_buy_price = base * 0.97 / (1 + margin / 100)
            elif buy_strat == "Auto":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('buy'):
                    b = stats['buy']
                    b_min = b.get("min", 0)
                    b_q1 = b.get("q1", 0)
                    b_max = b.get("max", 0)
                    net_max = b_max * 0.97
                    if net_max <= 0:
                        new_buy_price = 0
                    elif net_max <= b_min:
                        new_buy_price = b_min
                    else:
                        new_buy_price = b_q1
            elif buy_strat == "Kar Odaklı":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('buy') and stats.get('sell'):
                    b = stats.get("buy", {})
                    s = stats.get("sell", {})
                    best_profit = -999999999
                    best_price = 0
                    for mv in [b.get("min",0), b.get("q1",0), b.get("median",0), b.get("mode",0), b.get("q3",0), b.get("max",0), b.get("ci_low",0), b.get("ci_high",0)]:
                        if mv <= 0: continue
                        profit = (s.get("q3", 0) * 0.97) - mv
                        if profit > best_profit:
                            best_profit = profit
                            best_price = mv
                    new_buy_price = best_price
            elif buy_strat == "Spread Filtreli":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats:
                    raw_b = stats.get('buy_raw')
                    try:
                        lower_percentile = float(self.spread_lower.text().strip()) / 100.0
                    except:
                        lower_percentile = 0.25
                    if raw_b is not None and not raw_b.empty:
                        new_buy_price = float(np.percentile(raw_b, lower_percentile * 100))
                    elif stats.get('buy'):
                        new_buy_price = stats['buy'].get("q1", 0)
            elif buy_strat == "Min-Max Rastgele":
                import random
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('buy'):
                    b_min = stats['buy'].get("min", 0)
                    b_max = stats['buy'].get("max", 0)
                    if b_min > 0 and b_max > b_min:
                        new_buy_price = random.randint(int(b_min), int(b_max))
            elif buy_strat == "Otonom":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('buy'):
                    b = stats['buy']
                    if b.get("min", 0) > 0 and b.get("q1", 0) > b.get("min", 0):
                        new_buy_price = b.get("q1", 0)
                    else:
                        new_buy_price = b.get("min", 0)
            elif buy_strat == "Max %3 Vergi":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('buy'):
                    new_buy_price = stats['buy'].get("max", 0) * 0.97
            else:
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('buy'):
                    s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
                    new_buy_price = stats['buy'].get(s_map.get(buy_strat, "median"), new_buy_price)

            sell_strat = sell_strat_combo.currentText()
            new_sell_price = item.get('sell_price', 0)

            if sell_strat == "Manuel":
                val = sell_entry.text().replace(",", "").replace(".", "")
                if val:
                    try:
                        new_sell_price = float(val)
                    except ValueError:
                        QMessageBox.warning(dialog, "Hata", "Gecerli bir satis fiyati girin.")
                        return
            elif sell_strat == "Auto":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('sell') and new_buy_price > 0:
                    new_sell_price, _ = self._auto_sell_calc(stats, new_buy_price)
            elif sell_strat == "Kar Odaklı":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('sell'):
                    s = stats.get("sell", {})
                    best_profit = -999999999
                    best_price = 0
                    for mv in [s.get("min",0), s.get("q1",0), s.get("median",0), s.get("mode",0), s.get("q3",0), s.get("max",0), s.get("ci_low",0), s.get("ci_high",0)]:
                        if mv <= 0: continue
                        profit = (mv * 0.97) - new_buy_price
                        if profit > best_profit:
                            best_profit = profit
                            best_price = mv
                    new_sell_price = best_price
            elif sell_strat == "Spread Filtreli":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats:
                    raw_s = stats.get('sell_raw')
                    try:
                        upper_percentile = float(self.spread_upper.text().strip()) / 100.0
                    except:
                        upper_percentile = 0.75
                    if raw_s is not None and not raw_s.empty:
                        new_sell_price = float(np.percentile(raw_s, upper_percentile * 100))
                    elif stats.get('sell'):
                        new_sell_price = stats['sell'].get("q3", 0)
            elif sell_strat == "Min-Max Rastgele":
                import random
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('sell'):
                    s_min = stats['sell'].get("min", 0)
                    s_max = stats['sell'].get("max", 0)
                    if s_min > 0 and s_max > s_min:
                        new_sell_price = random.randint(int(s_min), int(s_max))
            elif sell_strat == "Otonom":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('sell'):
                    s = stats['sell']
                    if s.get("max", 0) > 0 and s.get("q3", 0) < s.get("max", 0):
                        new_sell_price = s.get("q3", 0)
                    else:
                        new_sell_price = s.get("max", 0)
            else:
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes())
                if stats and stats.get('sell'):
                    s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
                    new_sell_price = stats['sell'].get(s_map.get(sell_strat, "median"), new_sell_price)

            self.portfolio[index]['buy_strategy'] = buy_strat
            self.portfolio[index]['buy_price'] = new_buy_price
            self.portfolio[index]['sell_strategy'] = sell_strat
            self.portfolio[index]['sell_price'] = new_sell_price
            self.auto_save()
            self.render_portfolio_ui()
            dialog.accept()

        btn = QPushButton("Degisikligi Uygula")
        btn.setStyleSheet("background-color: #2ecc71; color: white;")
        btn.clicked.connect(save_changes)
        layout.addWidget(btn)

        dialog.exec()

    def edit_selected_item(self):
        selected = self.table.currentRow()
        if selected >= 0:
            visible_rows = self._get_visible_rows()
            if selected < len(visible_rows):
                self.open_buy_edit_popup(visible_rows[selected])

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        col = self.table.columnAt(pos.x())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self.table)

        copy_name = menu.addAction("Item Adini Kopyala")
        copy_cell = menu.addAction("Secili Degeri Kopyala")
        copy_row = menu.addAction("Satiri Kopyala")
        menu.addSeparator()
        edit_action = menu.addAction("Duzenle")
        delete_action = menu.addAction("Seciliyi Sil")
        menu.addSeparator()
        move_up = menu.addAction("Yukari Tas")
        move_down = menu.addAction("Asagi Tas")
        menu.addSeparator()
        add_to_list = menu.addAction("Portfoye Ekle (Yeni Kopya)")

        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action is None:
            return
        visible_rows = self._get_visible_rows()
        print(f"Context menu action: {action.text()}, row={row}")
        if action == copy_name:
            name = self.table.item(row, 0).text()
            QApplication.clipboard().setText(name)
        elif action == copy_cell:
            cell = self.table.item(row, col)
            if cell:
                QApplication.clipboard().setText(cell.text())
        elif action == copy_row:
            texts = [self.table.item(row, j).text() if self.table.item(row, j) else "" for j in range(self.table.columnCount())]
            QApplication.clipboard().setText("\t".join(texts))
        elif action == edit_action:
            if row < len(visible_rows):
                self.open_buy_edit_popup(visible_rows[row])
        elif action == delete_action:
            self._delete_row(row)
        elif action == move_up:
            if row > 0 and row < len(visible_rows):
                idx = visible_rows[row]
                prev_idx = visible_rows[row - 1]
                self.portfolio[idx], self.portfolio[prev_idx] = self.portfolio[prev_idx], self.portfolio[idx]
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False
        elif action == move_down:
            if row < len(visible_rows) - 1:
                idx = visible_rows[row]
                next_idx = visible_rows[row + 1]
                self.portfolio[idx], self.portfolio[next_idx] = self.portfolio[next_idx], self.portfolio[idx]
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False
        elif action == add_to_list:
            if row < len(visible_rows):
                item = self.portfolio[visible_rows[row]]
                self.portfolio.append(item.copy())
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False


    def _on_cell_changed(self, row, col):
        if self._updating:
            return
        if col not in (13, 14):
            return
        item_widget = self.table.item(row, col)
        if item_widget is None:
            return
        checked = item_widget.checkState() == Qt.Checked
        visible_rows = self._get_visible_rows()
        if row >= len(visible_rows):
            return
        idx = visible_rows[row]
        if col == 13:
            self.portfolio[idx]["buy_fixed"] = checked
        elif col == 14:
            self.portfolio[idx]["sell_fixed"] = checked
        self.auto_save()
        self._updating = True
        self.render_portfolio_ui()
        self._updating = False


    def _get_visible_rows(self):
        indices = []
        search_term = self.port_search_entry.text().strip().lower() if hasattr(self, 'port_search_entry') else ""
        filter_server = self._get_filtered_server()
        for i, item in enumerate(self.portfolio):
            if search_term and search_term not in item["name"].lower():
                continue
            if not self._item_matches_filter(item, filter_server):
                continue
            indices.append(i)
        return indices

    def _delete_row(self, row):
        visible_rows = self._get_visible_rows()
        if row < len(visible_rows):
            idx = visible_rows[row]
            if 0 <= idx < len(self.portfolio):
                del self.portfolio[idx]
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False
                new_count = self.table.rowCount()
                if new_count > 0:
                    select_row = min(row, new_count - 1)
                    self.table.selectRow(select_row)

    def save_settings(self):
        settings = {
            "buy_strategy": self.port_buy_strat_combo.currentText(),
            "sell_strategy": self.bulk_sell_combo.currentText(),
            "bulk_buy": self.bulk_buy_combo.currentText(),
            "bulk_sell": self.bulk_sell_combo.currentText(),
            "buy_margin": self.entry_buy_margin.text(),
            "custom_margin": self.entry_custom_margin.text(),
            "spread_lower": self.spread_lower.text(),
            "spread_upper": self.spread_upper.text(),
            "count": self.port_count_entry.text(),
            "server": self.server_price_combo.currentText(),
        }
        path = os.path.join(self.master.BASE_DIR, "portfolio_settings.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ayarlar kaydedilemedi: {e}")

    def load_settings(self):
        path = os.path.join(self.master.BASE_DIR, "portfolio_settings.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self.port_buy_strat_combo.setCurrentText(settings.get("buy_strategy", "Medyan"))
            self.bulk_sell_combo.setCurrentText(settings.get("sell_strategy", "Auto"))
            self.bulk_buy_combo.setCurrentText(settings.get("bulk_buy", "Medyan"))
            self.bulk_sell_combo.setCurrentText(settings.get("bulk_sell", "Auto"))
            self.entry_buy_margin.setText(settings.get("buy_margin", "20"))
            self.entry_custom_margin.setText(settings.get("custom_margin", "15"))
            self.spread_lower.setText(settings.get("spread_lower", "25"))
            self.spread_upper.setText(settings.get("spread_upper", "75"))
            self.port_count_entry.setText(settings.get("count", "1"))
            srv = settings.get("server", "Tum Sunucular")
            idx = self.server_price_combo.findText(srv)
            if idx >= 0:
                self.server_price_combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"Ayarlar yuklenemedi: {e}")

    def save_named_list(self, name):
        if not name.strip():
            return
        lists_dir = os.path.join(self.master.BASE_DIR, "saved_lists")
        os.makedirs(lists_dir, exist_ok=True)
        path = os.path.join(lists_dir, f"{name.strip()}.json")
        data = {
            "items": self.portfolio,
            "settings": {
                "buy_strategy": self.port_buy_strat_combo.currentText(),
                "sell_strategy": self.bulk_sell_combo.currentText(),
                "bulk_buy": self.bulk_buy_combo.currentText(),
                "bulk_sell": self.bulk_sell_combo.currentText(),
                "buy_margin": self.entry_buy_margin.text(),
                "custom_margin": self.entry_custom_margin.text(),
                "spread_lower": self.spread_lower.text(),
                "spread_upper": self.spread_upper.text(),
                "count": self.port_count_entry.text(),
                "server": self.server_price_combo.currentText(),
            }
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Liste kaydedilemedi: {e}")

    def load_named_list(self, name):
        lists_dir = os.path.join(self.master.BASE_DIR, "saved_lists")
        path = os.path.join(lists_dir, f"{name}.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.portfolio = data.get("items", [])
            settings = data.get("settings", {})
            self.port_buy_strat_combo.setCurrentText(settings.get("buy_strategy", "Medyan"))
            self.bulk_sell_combo.setCurrentText(settings.get("sell_strategy", "Auto"))
            self.bulk_buy_combo.setCurrentText(settings.get("bulk_buy", "Medyan"))
            self.bulk_sell_combo.setCurrentText(settings.get("bulk_sell", "Auto"))
            self.entry_buy_margin.setText(settings.get("buy_margin", "20"))
            self.entry_custom_margin.setText(settings.get("custom_margin", "15"))
            self.spread_lower.setText(settings.get("spread_lower", "25"))
            self.spread_upper.setText(settings.get("spread_upper", "75"))
            self.port_count_entry.setText(settings.get("count", "1"))
            srv = settings.get("server", "Tum Sunucular")
            idx = self.server_price_combo.findText(srv)
            if idx >= 0:
                self.server_price_combo.setCurrentIndex(idx)
            self.auto_save()
            self.render_portfolio_ui()
        except Exception as e:
            print(f"Liste yuklenemedi: {e}")

    def delete_named_list(self, name):
        lists_dir = os.path.join(self.master.BASE_DIR, "saved_lists")
        path = os.path.join(lists_dir, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)

    def get_saved_list_names(self):
        lists_dir = os.path.join(self.master.BASE_DIR, "saved_lists")
        if not os.path.exists(lists_dir):
            return []
        return [f.replace(".json", "") for f in os.listdir(lists_dir) if f.endswith(".json")]

    def _refresh_saved_lists(self):
        self.saved_list_combo.clear()
        names = self.get_saved_list_names()
        self.saved_list_combo.addItems(names)

    def _load_selected_list(self):
        name = self.saved_list_combo.currentText()
        if name:
            self.load_named_list(name)
            QMessageBox.information(self.master, "Basari", f"'{name}' listesi yuklendi!")

    def _save_as_new_list(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.master, "Liste Kaydet", "Liste adi girin:")
        if ok and name.strip():
            self.save_named_list(name.strip())
            self._refresh_saved_lists()
            self.saved_list_combo.setCurrentText(name.strip())
            QMessageBox.information(self.master, "Basari", f"'{name.strip()}' listesi kaydedildi!")

    def _delete_selected_list(self):
        name = self.saved_list_combo.currentText()
        if not name:
            return
        reply = QMessageBox.question(self.master, "Silme Onayi", f"'{name}' listesini silmek istediginize emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.delete_named_list(name)
            self._refresh_saved_lists()
            QMessageBox.information(self.master, "Basari", f"'{name}' listesi silindi!")

    def _save_current_settings(self):
        self.save_settings()
        QMessageBox.information(self.master, "Basari", "Mevcut ayarlar kaydedildi!")

    def _copy_selected_rows(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        lines = []
        for s in selected:
            row = s.row()
            texts = [self.table.item(row, j).text() if self.table.item(row, j) else "" for j in range(17)]
            lines.append("\t".join(texts))
        QApplication.clipboard().setText("\n".join(lines))

    def _copy_all_rows(self):
        lines = []
        headers = [self.table.horizontalHeaderItem(j).text() for j in range(17)]
        lines.append("\t".join(headers))
        for i in range(self.table.rowCount()):
            texts = [self.table.item(i, j).text() if self.table.item(i, j) else "" for j in range(17)]
            lines.append("\t".join(texts))
        QApplication.clipboard().setText("\n".join(lines))

    def _toggle_all_fix(self, fix_type, state):
        col = 13 if fix_type == "buy" else 14
        key = "buy_fixed" if fix_type == "buy" else "sell_fixed"
        price_key = "buy_price" if fix_type == "buy" else "sell_price"
        strat_key = "buy_strategy" if fix_type == "buy" else "sell_strategy"

        visible_rows = self._get_visible_rows()

        self.table.cellChanged.disconnect(self._on_cell_changed)
        for i in range(self.table.rowCount()):
            cell = self.table.item(i, col)
            if cell:
                cell.setCheckState(Qt.Checked if state else Qt.Unchecked)
        for idx in visible_rows:
            item = self.portfolio[idx]
            item[key] = state
            if state and fix_type == "sell":
                if item.get(price_key, 0) <= 0:
                    item[strat_key] = "Manuel"
        self.table.cellChanged.connect(self._on_cell_changed)
        self.auto_save()
        self.render_portfolio_ui()
