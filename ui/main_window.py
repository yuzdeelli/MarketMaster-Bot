import os
import sys
import io
import contextlib
import sqlite3
import threading
import platform
from PySide6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout,
                                QHBoxLayout, QPushButton, QLabel, QComboBox,
                                QLineEdit, QCheckBox, QFileDialog, QMessageBox,
                                QTableWidget, QTableWidgetItem, QHeaderView,
                                QScrollArea, QFrame, QApplication)
from PySide6.QtCore import Qt, QTimer
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from core.config import ConfigManager
from core.database import DatabaseManager, initialize_database, fix_write_permissions
from core.engine import MarketEngine
from core.analyzer import MarketAnalyzer
from core.predictor import MarketPredictor
from ui.bot_tab import BotTab
from ui.strategy_tab import StrategyTab
from ui.opportunity_tab import OpportunityTab
from ui.portfolio_tab import PortfolioTab
from ui.arbitrage_tab import ArbitrageTab
from ui.analytics_tab import AnalyticsTab
from ui.settings_tab import SettingsTab
from ui.assistant_ui import MasterAssistantWindow


from ui.searchable_combo import SearchableComboBox


if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class KnightMarketMasterV3(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Knight Market Master v3.0 - Deep Analyzer")
        self.setMinimumSize(1600, 800)

        self.db_name = os.path.join(BASE_DIR, "app_data.db")

        initialize_database(self.db_name)
        fix_write_permissions(self.db_name)

        self.BASE_DIR = BASE_DIR
        self.db_manager = DatabaseManager(self.db_name)
        api_key = ConfigManager.load_api_key()
        self.engine = MarketEngine(db_name=self.db_name, db_insert_callback=self.db_manager.insert_price, api_key=api_key)
        self.analyzer = MarketAnalyzer(self.db_manager)

        self.stats_cache = {}
        self.stats_cache_lock = threading.Lock()
        self.all_items_list = []
        self.server_targets = {
            "ZERO 3": "btn_zero3", "ZERO 4": "btn_zero4", "ZERO 5": "btn_zero5", "ZERO 8": "btn_zero8",
            "PANDORA 3": "btn_pandora3", "PANDORA 4": "btn_pandora4",
            "AGARTHA 3": "btn_agartha3", "AGARTHA 4": "btn_agartha4",
            "FELIS 2": "btn_felis2",
            "DESTAN 3": "btn_destan3", "DESTAN 2": "btn_destan2",
            "MINARK 2": "btn_minark2",
            "DRYADS 2": "btn_dryads2",
            "OREADS 2": "btn_oreads2", "OREADS 3": "btn_oreads3",
            "Tüm Zero": "btn_grp_zero",
            "Tüm Agartha": "btn_grp_agartha",
            "Tüm Pandora": "btn_grp_pandora",
            "Tüm Destan": "btn_grp_destan",
            "Tüm Oreads": "btn_grp_oreads",
        }
        self.lvl_options = (
            [f"+{i}" for i in range(11)] +
            [f"+{i}R" for i in range(1, 22)]
        )
        self.assistant_window = None
        self.web_server_running = False
        self.web_server_process = None
        self.portfolio_server_running = False
        self.portfolio_server_process = None

        self.setup_main_ui()
        self.update_autocomplete_data()
        self.update_opportunity_list()

    def setup_main_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        top = QHBoxLayout()

        btn_ai = QPushButton("AI CORE (Uyandir)")
        btn_ai.setFixedWidth(140)
        btn_ai.setStyleSheet("background-color: #8e44ad; color: white;")
        btn_ai.clicked.connect(self.toggle_assistant_window)
        top.addWidget(btn_ai)

        self.btn_web_server = QPushButton("SUNUCUYU BASLAT")
        self.btn_web_server.setFixedWidth(140)
        self.btn_web_server.setStyleSheet("background-color: #27ae60; color: white;")
        self.btn_web_server.clicked.connect(self.toggle_web_server)
        top.addWidget(self.btn_web_server)

        self.btn_web_reset = QPushButton("RESET")
        self.btn_web_reset.setFixedWidth(60)
        self.btn_web_reset.setStyleSheet("background-color: #e67e22; color: white;")
        self.btn_web_reset.clicked.connect(self.reset_web_server)
        top.addWidget(self.btn_web_reset)

        self.btn_portfolio_server = QPushButton("PORTFOY SUNUCU")
        self.btn_portfolio_server.setFixedWidth(130)
        self.btn_portfolio_server.setStyleSheet("background-color: #2980b9; color: white;")
        self.btn_portfolio_server.clicked.connect(self.toggle_portfolio_server)
        top.addWidget(self.btn_portfolio_server)

        self.btn_portfolio_reset = QPushButton("RESET")
        self.btn_portfolio_reset.setFixedWidth(60)
        self.btn_portfolio_reset.setStyleSheet("background-color: #e67e22; color: white;")
        self.btn_portfolio_reset.clicked.connect(self.reset_portfolio_server)
        top.addWidget(self.btn_portfolio_reset)

        top.addStretch()

        bugun = datetime.now().date()
        tarihler = [(bugun - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10)]
        saatler = [f"{str(h).zfill(2)}:00" for h in range(24)]

        lbl = QLabel("Zaman:")
        lbl.setStyleSheet("font-size: 11px;")
        top.addWidget(lbl)
        self.combo_time_filter = QComboBox()
        self.combo_time_filter.addItems(["5 dk", "10 dk", "15 dk", "30 dk", "1 saat", "2 saat", "3 saat", "Tumu"])
        self.combo_time_filter.setCurrentText("Tumu")
        self.combo_time_filter.setFixedWidth(80)
        self.combo_time_filter.currentTextChanged.connect(self.on_filter_changed)
        top.addWidget(self.combo_time_filter)

        lbl = QLabel("Bas:")
        lbl.setStyleSheet("font-size: 11px;")
        top.addWidget(lbl)
        self.combo_start_date = QComboBox()
        self.combo_start_date.setEditable(True)
        self.combo_start_date.addItems(tarihler)
        self.combo_start_date.setFixedWidth(110)
        self.combo_start_date.currentTextChanged.connect(self.on_filter_changed)
        top.addWidget(self.combo_start_date)
        self.combo_start_hour = QComboBox()
        self.combo_start_hour.setEditable(True)
        self.combo_start_hour.addItems(saatler)
        self.combo_start_hour.setCurrentText("00:00")
        self.combo_start_hour.setFixedWidth(70)
        self.combo_start_hour.currentTextChanged.connect(self.on_filter_changed)
        top.addWidget(self.combo_start_hour)

        lbl = QLabel("Bit:")
        lbl.setStyleSheet("font-size: 11px;")
        top.addWidget(lbl)
        self.combo_end_date = QComboBox()
        self.combo_end_date.setEditable(True)
        self.combo_end_date.addItems(tarihler)
        self.combo_end_date.setFixedWidth(110)
        self.combo_end_date.currentTextChanged.connect(self.on_filter_changed)
        top.addWidget(self.combo_end_date)
        self.combo_end_hour = QComboBox()
        self.combo_end_hour.setEditable(True)
        self.combo_end_hour.addItems(saatler)
        self.combo_end_hour.setCurrentText("23:59")
        self.combo_end_hour.setFixedWidth(70)
        self.combo_end_hour.currentTextChanged.connect(self.on_filter_changed)
        top.addWidget(self.combo_end_hour)

        main_layout.addLayout(top)

        self.tabview = QTabWidget()
        self.tabview.setStyleSheet("QTabWidget::pane { border: 1px solid #1a1a2e; }")
        main_layout.addWidget(self.tabview)

        tab_bot = QWidget()
        tab_strategy = QWidget()
        tab_opportunity = QWidget()
        tab_arbitrage = QWidget()
        tab_analytics = QWidget()
        tab_excel = QWidget()
        tab_settings = QWidget()

        self.tabview.addTab(tab_bot, "Pazar Tarayici (Bot)")
        self.tabview.addTab(tab_strategy, "Derin Strateji & Kar Analizi")
        self.tabview.addTab(tab_opportunity, "CANLI FIRSAT LISTESI")
        self.tabview.addTab(tab_arbitrage, "ARBITRAJ")
        self.tabview.addTab(tab_analytics, "ANALIZ")
        self.tabview.addTab(tab_excel, "Excel Export")
        self.tabview.addTab(tab_settings, "Ayarlar")

        self.bot_tab = BotTab(self, tab_bot)
        self.strategy_tab = StrategyTab(self, tab_strategy)
        self.opportunity_tab = OpportunityTab(self, tab_opportunity)
        self.arbitrage_tab = ArbitrageTab(self, tab_arbitrage)
        self.analytics_tab = AnalyticsTab(self, tab_analytics)
        self.portfolio_tab = PortfolioTab(self, tab_excel)
        self.settings_tab = SettingsTab(self, tab_settings)

    def update_autocomplete_data(self):
        if not os.path.exists(self.db_name):
            return
        try:
            conn = sqlite3.connect(self.db_name, timeout=15)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT item_name FROM prices ORDER BY item_name ASC")
            self.all_items_list = [row[0] for row in cursor.fetchall()]
            conn.close()
            if hasattr(self, 'strategy_tab') and hasattr(self.strategy_tab, 'it_combo'):
                self.strategy_tab.it_combo.configure_values(self.all_items_list)
            if hasattr(self, 'portfolio_tab') and hasattr(self.portfolio_tab, 'port_item_combo'):
                self.portfolio_tab.port_item_combo.configure_values(self.all_items_list)
        except Exception as e:
            print(e)

    def get_time_filter_minutes(self):
        val = self.combo_time_filter.currentText()
        mapping = {"5 dk": 5, "10 dk": 10, "15 dk": 15, "30 dk": 30,
                   "1 saat": 60, "2 saat": 120, "3 saat": 180}
        return mapping.get(val, None)

    def get_active_filter_params(self):
        minutes = self.get_time_filter_minutes()
        start_dt = None
        end_dt = None
        today_str = datetime.now().date().strftime("%Y-%m-%d")

        if hasattr(self, 'combo_start_date') and self.combo_start_date.currentText():
            raw_start = self.combo_start_date.currentText()
            is_default_start = (raw_start == today_str)
            if minutes is not None or not is_default_start:
                start_dt = f"{raw_start} {self.combo_start_hour.currentText()}:00"

        if hasattr(self, 'combo_end_date') and self.combo_end_date.currentText():
            raw_end = self.combo_end_date.currentText()
            is_default_end = (raw_end == today_str)
            if minutes is not None or not is_default_end:
                end_dt = f"{raw_end} {self.combo_end_hour.currentText()}:00"

        return {"time_limit_minutes": minutes, "start_date": start_dt, "end_date": end_dt}

    def get_cached_stats(self, name, lvl, server=None):
        params = self.get_active_filter_params()
        key = (name, lvl, params["time_limit_minutes"], params["start_date"], params["end_date"], server or "")
        with self.stats_cache_lock:
            if key not in self.stats_cache:
                self.stats_cache[key] = self.analyzer.get_item_stats(
                    item_name=name, item_lvl=lvl,
                    time_limit_minutes=params["time_limit_minutes"],
                    start_date=params["start_date"], end_date=params["end_date"],
                    server=server)
                return self.stats_cache[key]
            return self.stats_cache[key]

    def calculate_auto_sell(self, stats, buy_price):
        if not stats or not stats.get('sell'):
            return 0, "Veri Yok", 0
        s = stats['sell']
        spread_limit = 0.25
        try:
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analyzer_config.json")
            if os.path.exists(cfg_path):
                import json
                with open(cfg_path, "r") as f:
                    cfg = json.load(f)
                spread_limit = float(cfg.get("spread_lower", 25)) / 100.0
        except:
            pass
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
        for name, sell_price in metrics:
            if sell_price <= 0:
                continue
            net = sell_price * 0.97
            profit = net - buy_price
            if profit > 0:
                profit_candidates.append((name, sell_price, profit))
            else:
                loss_pct = abs(profit) / buy_price if buy_price > 0 else 0
                if loss_pct <= spread_limit:
                    loss_candidates.append((name, sell_price, abs(profit)))
        if profit_candidates:
            profit_candidates.sort(key=lambda x: x[1])
            best = profit_candidates[0]
            return best[1], best[0], best[2]
        if loss_candidates:
            loss_candidates.sort(key=lambda x: x[2])
            best = loss_candidates[0]
            return best[1], f"{best[0]}", -(best[2])
        return s.get('max', 0), "Max", (s.get('max', 0) * 0.97) - buy_price

    def update_opportunity_list(self):
        if not hasattr(self, 'opportunity_tab'):
            return

        params = self.get_active_filter_params()

        def _bg():
            all_items = self.analyzer.get_all_unique_items()
            rows = []
            for item in all_items:
                key = (item['name'], item['lvl'], params["time_limit_minutes"], params["start_date"], params["end_date"])
                with self.stats_cache_lock:
                    if key not in self.stats_cache:
                        self.stats_cache[key] = self.analyzer.get_item_stats(
                            item_name=item['name'], item_lvl=item['lvl'],
                            time_limit_minutes=params["time_limit_minutes"],
                            start_date=params["start_date"], end_date=params["end_date"])
                    stats = self.stats_cache[key]
                if stats and stats.get('buy') and stats.get('sell'):
                    max_buy = stats['buy']['max']
                    sell_med = stats['sell']['median']
                    your_buy = max_buy + 1
                    elden_offer = max_buy * 0.97
                    profit = sell_med - elden_offer
                    rows.append((
                        f"{item['name']} {item['lvl']}",
                        f"{max_buy:,.0f}", f"{your_buy:,.0f}",
                        f"{elden_offer:,.0f}", f"{profit:,.0f}"))
            QTimer.singleShot(0, lambda: self._populate_opportunity_table(rows))

        threading.Thread(target=_bg, daemon=True).start()

    def _populate_opportunity_table(self, rows):
        self.opportunity_tab.load_data(rows)

    def run_ai_prediction(self):
        item_name = self.portfolio_tab.port_item_combo.get().strip()
        item_lvl = self.portfolio_tab.port_lvl_combo.currentText().strip()
        if not item_name:
            QMessageBox.warning(self, "Hata", "Gecerli bir Item Adi secin.")
            return
        filtreler = self.get_active_filter_params()
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            predictor = MarketPredictor(self.db_manager)
            predictor.train_and_evaluate(item_name, item_lvl,
                                         start_date=filtreler.get("start_date"),
                                         end_date=filtreler.get("end_date"))
        rapor = f.getvalue()
        if rapor.strip() and "yetersiz veri var" not in rapor:
            dosya_adi = f"{item_name}_{item_lvl.replace('+', 'plus_')}_AI_Raporu.txt"
            with open(dosya_adi, "w", encoding="utf-8") as file:
                file.write(f"=== MARKET MASTER v3 - AI TAHMIN RAPORU ===\n")
                file.write(f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
                file.write(f"Hedef Item: {item_name} {item_lvl}\n{'='*50}\n\n{rapor}")
            os.startfile(dosya_adi)
            QMessageBox.information(self, "AI Analizi Tamamlandi", f"Rapor '{dosya_adi}' kaydedildi!")
        else:
            QMessageBox.warning(self, "Yetersiz Veri", rapor.strip())

    def show_ai_graph(self):
        import matplotlib
        matplotlib.use('Qt5Agg')
        import matplotlib.pyplot as plt
        item_name = self.portfolio_tab.port_item_combo.get().strip()
        item_lvl = self.portfolio_tab.port_lvl_combo.currentText().strip()
        predictor = MarketPredictor(self.db_manager)
        filtreler = self.get_active_filter_params()
        X, y = predictor.load_and_prepare_data(item_name, item_lvl,
                                                start_date=filtreler.get("start_date"),
                                                end_date=filtreler.get("end_date"))
        if X is None or len(X) < 2:
            QMessageBox.warning(self, "Yetersiz Veri", "Grafik icin yeterli veri yok.")
            return
        buy_data = X[X['is_sell'] == 0] if 'is_sell' in X.columns else None
        sell_data = X[X['is_sell'] == 1] if 'is_sell' in X.columns else None
        buy_y = y[X['is_sell'] == 0] if buy_data is not None else None
        sell_y = y[X['is_sell'] == 1] if sell_data is not None else None

        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        if buy_data is not None and not buy_data.empty:
            ax1.scatter(buy_data['hour'], buy_data['price'], c=buy_y, cmap='RdYlGn', s=80, alpha=0.7)
            ax1.set_title("BUY (ALIM) ANALIZI", color='#00ff00', fontsize=12)
        else:
            ax1.text(0.5, 0.5, 'Veri Yok', ha='center', color='gray')
        if sell_data is not None and not sell_data.empty:
            ax2.scatter(sell_data['hour'], sell_data['price'], c=sell_y, cmap='RdYlGn', s=80, alpha=0.7)
            ax2.set_title("SELL (SATIM) ANALIZI", color='#ff0000', fontsize=12)
        else:
            ax2.text(0.5, 0.5, 'Veri Yok', ha='center', color='gray')
        for ax in [ax1, ax2]:
            ax.set_xlabel("Gunun Saati")
            ax.set_ylabel("Fiyat")
            ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
            ax.grid(True, linestyle='--', alpha=0.2)
        fig.suptitle(f"{item_name} {item_lvl} - Buy/Sell Karsilastirmasi", fontsize=14, color='white')
        plt.tight_layout()
        plt.show()

    def toggle_assistant_window(self):
        if self.assistant_window is None or not self.assistant_window.isVisible():
            self.assistant_window = MasterAssistantWindow(self)
            self.assistant_window.show()
        else:
            self.assistant_window.activateWindow()

    def toggle_web_server(self):
        if self.web_server_running:
            if self.web_server_process:
                try:
                    self.web_server_process.stop()
                except:
                    pass
                self.web_server_process = None
            self.web_server_running = False
            self.btn_web_server.setText("SUNUCUYU BASLAT")
            self.btn_web_server.setStyleSheet("background-color: #27ae60; color: white;")
        else:
            try:
                from web_server import WebServer
                self.web_server_process = WebServer()
                success = self.web_server_process.start()
                if success:
                    self.web_server_running = True
                    self.btn_web_server.setText("SUNUCUYU DURDUR")
                    self.btn_web_server.setStyleSheet("background-color: #c0392b; color: white;")
                else:
                    QMessageBox.warning(self, "Hata", "Web sunucusu baslatilamadi!")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Web sunucusu baslatilamadi: {e}")

    def reset_web_server(self):
        if self.web_server_running:
            if self.web_server_process:
                try:
                    self.web_server_process.stop()
                except:
                    pass
                self.web_server_process = None
            self.web_server_running = False
        try:
            from web_server import WebServer
            self.web_server_process = WebServer()
            success = self.web_server_process.start()
            if success:
                self.web_server_running = True
                self.btn_web_server.setText("SUNUCUYU DURDUR")
                self.btn_web_server.setStyleSheet("background-color: #c0392b; color: white;")
            else:
                QMessageBox.warning(self, "Hata", "Web sunucusu baslatilamadi!")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Web sunucusu baslatilamadi: {e}")

    def toggle_portfolio_server(self):
        if self.portfolio_server_running:
            if self.portfolio_server_process:
                try:
                    self.portfolio_server_process.stop()
                except:
                    pass
                self.portfolio_server_process = None
            self.portfolio_server_running = False
            self.btn_portfolio_server.setText("PORTFOY SUNUCU")
            self.btn_portfolio_server.setStyleSheet("background-color: #2980b9; color: white;")
        else:
            try:
                from portfolio_web_server import PortfolioWebServer
                self.portfolio_server_process = PortfolioWebServer()
                success = self.portfolio_server_process.start()
                if success:
                    self.portfolio_server_running = True
                    self.btn_portfolio_server.setText("PORTFOY DURDUR")
                    self.btn_portfolio_server.setStyleSheet("background-color: #c0392b; color: white;")
                else:
                    QMessageBox.warning(self, "Hata", "Portfoy sunucusu baslatilamadi!")
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"Portfoy sunucusu baslatilamadi: {e}")

    def reset_portfolio_server(self):
        if self.portfolio_server_running:
            if self.portfolio_server_process:
                try:
                    self.portfolio_server_process.stop()
                except:
                    pass
                self.portfolio_server_process = None
            self.portfolio_server_running = False
        try:
            from portfolio_web_server import PortfolioWebServer
            self.portfolio_server_process = PortfolioWebServer()
            success = self.portfolio_server_process.start()
            if success:
                self.portfolio_server_running = True
                self.btn_portfolio_server.setText("PORTFOY DURDUR")
                self.btn_portfolio_server.setStyleSheet("background-color: #c0392b; color: white;")
            else:
                QMessageBox.warning(self, "Hata", "Portfoy sunucusu baslatilamadi!")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Portfoy sunucusu baslatilamadi: {e}")

    def on_filter_changed(self, choice=None):
        if hasattr(self, '_filter_timer') and self._filter_timer is not None:
            self._filter_timer.stop()
        self._filter_timer = QTimer()
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._do_filter)
        self._filter_timer.start(300)

    def _do_filter(self):
        with self.stats_cache_lock:
            self.stats_cache.clear()
        self.update_opportunity_list()
        if hasattr(self, 'portfolio_tab'):
            self.portfolio_tab.render_portfolio_ui()
