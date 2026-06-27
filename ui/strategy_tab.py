from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QLineEdit, QTextEdit, QComboBox,
                                QGridLayout, QFrame, QDialog, QTableWidget,
                                QTableWidgetItem, QHeaderView, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from ui.searchable_combo import SearchableComboBox
import json
import urllib.request


class StrategyTab:
    SERVER_GROUPS = {
        "Tüm Zero": ["ZERO 3", "ZERO 4", "ZERO 5", "ZERO 8"],
        "Tüm Agartha": ["AGARTHA 3", "AGARTHA 4"],
        "Tüm Pandora": ["PANDORA 3", "PANDORA 4"],
        "Tüm Destan": ["DESTAN 2", "DESTAN 3"],
        "Tüm Oreads": ["OREADS 2", "OREADS 3"],
    }

    def __init__(self, master, parent):
        self.master = master
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self.parent)

        input_frame = QFrame()
        input_frame.setStyleSheet("QFrame { background: #12121e; border-radius: 8px; padding: 8px; }")
        input_layout = QGridLayout(input_frame)
        input_layout.setSpacing(6)

        input_layout.addWidget(QLabel("Item:"), 0, 0)
        self.it_combo = SearchableComboBox(values=self.master.all_items_list, width=280, placeholder_text="Item ara...")
        input_layout.addWidget(self.it_combo, 0, 1, 1, 2)

        input_layout.addWidget(QLabel("Level:"), 0, 3)
        self.lvl_combo = QComboBox()
        self.lvl_combo.addItems(self.master.lvl_options)
        self.lvl_combo.setCurrentText("+7")
        self.lvl_combo.setFixedWidth(80)
        input_layout.addWidget(self.lvl_combo, 0, 4)

        input_layout.addWidget(QLabel("Sunucu:"), 0, 5)
        self.server_combo = QComboBox()
        self.server_combo.addItems(["Tum Sunucular"] + list(self.master.server_targets.keys()))
        self.server_combo.setFixedWidth(140)
        input_layout.addWidget(self.server_combo, 0, 6)

        input_layout.addWidget(QLabel("Adet:"), 0, 7)
        self.count_entry = QLineEdit("1")
        self.count_entry.setPlaceholderText("Adet")
        self.count_entry.setFixedWidth(50)
        input_layout.addWidget(self.count_entry, 0, 8)

        input_layout.addWidget(QLabel("%% Indirim:"), 0, 9)
        self.off_percent_entry = QLineEdit("3")
        self.off_percent_entry.setFixedWidth(50)
        input_layout.addWidget(self.off_percent_entry, 0, 10)

        self.manual_price_entry = QLineEdit()
        self.manual_price_entry.setPlaceholderText("Manuel Alis Fiyati (Opsiyonel)")
        input_layout.addWidget(self.manual_price_entry, 1, 0, 1, 5)

        self.btn_analyze = QPushButton("STRATEJI KAR HESAPLA")
        self.btn_analyze.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 8px 12px;")
        self.btn_analyze.clicked.connect(self.run_deep_strategy)
        input_layout.addWidget(self.btn_analyze, 1, 5, 1, 3)

        self.btn_canli = QPushButton("CANLI ANALIZ")
        self.btn_canli.setStyleSheet("background-color: #26a69a; color: white; font-weight: bold; padding: 8px 12px;")
        self.btn_canli.clicked.connect(self.run_live_analysis)
        input_layout.addWidget(self.btn_canli, 1, 8, 1, 3)

        layout.addWidget(input_frame)

        self.strat_res_box = QTextEdit()
        self.strat_res_box.setReadOnly(True)
        self.strat_res_box.setStyleSheet("font-family: Consolas; font-size: 14px; border: 2px solid #3498db;")
        layout.addWidget(self.strat_res_box)

    def run_deep_strategy(self):
        name = self.it_combo.get().strip()
        lvl = self.lvl_combo.currentText().strip()
        server = self.server_combo.currentText().strip()
        try:
            count = int(self.count_entry.text())
        except ValueError:
            count = 1
        try:
            off_rate = (100 - float(self.off_percent_entry.text().replace(",", "."))) / 100
        except ValueError:
            off_rate = 0.97

        m_price_raw = self.manual_price_entry.text().replace(".", "").replace(",", "")
        manual_price = int(m_price_raw) if m_price_raw.isdigit() else None
        db_lvl = "" if lvl in ["+0", "0"] else lvl
        filter_params = self.master.get_active_filter_params()

        db_server = None
        display_server = server
        if server == "Tum Sunucular":
            db_server = None
            display_server = "Tum Sunucular"
        elif server in self.SERVER_GROUPS:
            db_server = server.replace("Tum ", "").strip()
            display_server = server
        else:
            db_server = server
            display_server = server

        stats = self.master.analyzer.get_item_stats(
            item_name=name, item_lvl=db_lvl,
            time_limit_minutes=filter_params["time_limit_minutes"],
            start_date=filter_params["start_date"],
            end_date=filter_params["end_date"],
            server=db_server)

        self.strat_res_box.clear()
        if not stats:
            self.strat_res_box.setPlainText(f"'{name} {lvl}' icin secilen zaman araliginda DB'de yeterli veri yok.")
            return

        report = f"DERIN ANALIZ: {name.upper()} {lvl} [{display_server}] (Adet: {count})\n"
        report += "=" * 75 + "\n"
        report += "Manipulasyon Duvari: %1.0 Aktif (Uc Degerler Temizlendi)\n\n"

        for mode in ("buy", "sell"):
            s = stats.get(mode)
            if not s:
                continue
            report += f"--- {mode.upper()} PAZARI ({s['count']} Ilan - Filtrelenmis) ---\n"
            report += f"  Min - Max:    {s['min']:,.0f} - {s['max']:,.0f}\n"
            report += f"  Medyan (Ort):  {s['median']:,.0f}\n"
            if "mode" in s:
                report += f"  Mod (En Sik):  {s['mode']:,.0f}\n"
            if "std_dev" in s:
                report += f"  Std. Sapma:    {s['std_dev']:,.0f} Coins\n"
            if "variance" in s:
                report += f"  Varyans:       {s['variance']:,.0f}\n"
            if "std_err" in s:
                report += f"  Std. Hata:     {s['std_err']:,.0f}\n"
                report += f"  %%95 Guven Araligi: {s['ci_low']:,.0f} - {s['ci_high']:,.0f}\n"
            report += f"  Kartiller:     Q1: {s['q1']:,.0f} | Q3: {s['q3']:,.0f}\n"
            report += f"  Dagitim (S/K): {s['skew']:.2f} | {s['kurt']:.2f}\n"
            report += f"  Olasilik:      {s.get('dist_type', 'Analiz Ediliyor...')}\n"
            if mode == "buy":
                report += f"  Net Alis (Max-%%3 Vergi): {s['max']*0.97:,.0f}\n"
            report += "-" * 50 + "\n"

        sell_val = stats["sell"]["median"] if stats.get("sell") else 0
        if manual_price:
            buy_val = manual_price
            source = "MANUEL FIYAT"
        else:
            max_buy = stats["buy"]["max"] if stats.get("buy") else sell_val * 0.85
            buy_val = max_buy * off_rate
            source = f"OTOMATIK %{100-(off_rate*100):.1f} TEKLIF"

        total_cost = buy_val * count
        total_rev = sell_val * count
        total_profit = total_rev - total_cost
        margin = (total_profit / total_cost * 100) if total_cost > 0 else 0
        opp = self.master.analyzer.calculate_opportunity_score(stats, buy_val)

        report += "\nTICARI TEKLIF VE STRATEJI\n"
        report += "--------------------------------------------\n"
        report += f"Pazar Alis Fiyati:  {buy_val/0.97:,.0f} (Vergi Dahil Kurman Gereken)\n"
        report += f"Elden Alis Teklifin: {buy_val:,.0f} ({source})\n"
        report += f"TOPLAM NET KAR:         {total_profit:,.0f}\n"
        report += f"Kar Marji:               %{margin:.2f}\n"
        status = "Karli / Firsat" if margin > 8 else ("Stabil" if margin > 3 else "Riskli / Dar Makas")
        report += f"\nDURUM: {status}\n"
        report += "\nOPPORTUNITY SCORE\n"
        report += "--------------------------------------------\n"
        report += f"  Firsat Skoru: {opp['score']}/100\n"
        report += f"  Degerlendirme: {opp['rating']}\n"
        report += f"  Market CV: %{opp['cv']*100:.1f}\n"

        warnings = []
        if stats.get("sell") and "mode" in stats["sell"]:
            s_mod = stats["sell"]["mode"]
            s_med = stats["sell"]["median"]
            diff = abs(s_mod - s_med) / (s_med if s_med > 0 else 1)
            if diff > 0.05:
                warnings.append("ANOMALI: Mod ve Medyan kopuk! Pazar manipule ediliyor olabilir.")
            if s_mod < s_med:
                warnings.append("BASK: Cogunluk daha ucuza satiyor, fiyat asagi yonelebilir.")
            elif s_mod > s_med:
                warnings.append("YUKSELIS: Ilanlar yuksek fiyatta kumelenmis, pazar yukari yonlu.")
        if warnings:
            report += "\nSISTEM UYARILARI\n--------------------------------------------\n"
            for w in warnings:
                report += f"{w}\n"

        try:
            from core.analytics import DataFrameAnalytics
            analytics = DataFrameAnalytics(self.master.db_name)
            vol = analytics.volatility()
            dem = analytics.demand()
            liq = analytics.liquidity()

            report += "\n\nVOLATILITE (FIYAT OYNAKLIGI)\n--------------------------------------------\n"
            for r in vol.get("rows", [])[:10]:
                report += f"  {r['item']} +{r['lvl']}: Ort={r['ortalama']:,.0f}  Std={r['std']:,.0f}  CV=%{r['cv']}  [{r['min']:,.0f}-{r['max']:,.0f}]\n"

            report += "\nTALEP YOGUNLUGU\n--------------------------------------------\n"
            for r in dem.get("rows", [])[:10]:
                report += f"  {r['item']}: {r['satici']} satici, {r['ilan']} ilan\n"

            report += "\nLIKIDITE (SATIS HIZI)\n--------------------------------------------\n"
            for r in liq.get("rows", [])[:10]:
                report += f"  {r['item']}: {r['ilan']} ilan, {r['satici']} satici  [{r['ilk']} - {r['son']}]\n"
        except Exception:
            pass

        self.strat_res_box.setPlainText(report)

    def run_live_analysis(self):
        name = self.it_combo.get().strip()
        lvl = self.lvl_combo.currentText().strip()
        server = self.server_combo.currentText().strip()
        if not name:
            QMessageBox.warning(self.parent, "Hata", "Item secin!")
            return

        self.btn_canli.setEnabled(False)
        self.btn_canli.setText("Hesaplaniyor...")

        try:
            from webapp.indicators import compute_all_indicators
            from webapp.database import get_ohlc_data, get_db

            db_lvl = "" if lvl in ["+0", "0"] else lvl

            if server == "Tum Sunucular":
                ohlc = get_ohlc_data(name, db_lvl, "auto", limit=2000)
                display_server = "Tum Sunucular"
            elif server in self.SERVER_GROUPS:
                servers = self.SERVER_GROUPS[server]
                all_ohlc = []
                for srv in servers:
                    all_ohlc.extend(get_ohlc_data(name, db_lvl, "auto", limit=500, server=srv))
                all_ohlc.sort(key=lambda x: x.get("time", 0))
                ohlc = all_ohlc[:2000]
                display_server = server
            else:
                ohlc = get_ohlc_data(name, db_lvl, "auto", limit=2000, server=server)
                display_server = server

            if not ohlc:
                self.strat_res_box.setPlainText(f"'{name} {lvl}' icin {display_server} verisi bulunamadi.")
                self.btn_canli.setEnabled(True)
                self.btn_canli.setText("CANLI ANALIZ")
                return

            result = compute_all_indicators(ohlc)
            self._show_live_dialog(name, lvl, result, ohlc, display_server)
        except Exception as e:
            self.strat_res_box.setPlainText(f"HATA: {e}")
        finally:
            self.btn_canli.setEnabled(True)
            self.btn_canli.setText("CANLI ANALIZ")

    def _show_live_dialog(self, name, lvl, result, ohlc, server="Tum"):
        dlg = QDialog(self.parent)
        dlg.setWindowTitle(f"CANLI ANALIZ: {name} {lvl} [{server}]")
        dlg.setMinimumSize(700, 600)
        dlg.setStyleSheet("QDialog { background: #1a1a2e; } QLabel { color: #e0e0e0; }")

        layout = QVBoxLayout(dlg)

        status = result.get("status", "?")
        bull = result.get("bull_signals", 0)
        bear = result.get("bear_signals", 0)

        status_color = "#26a69a" if status == "BULLISH" else ("#ef5350" if status == "BEARISH" else "#848e9c")
        header = QLabel(f"{name} {lvl} [{server}]  |  DURUM: {status}  (B:{bull} / S:{bear})")
        header.setStyleSheet(f"color: {status_color}; font-size: 16px; font-weight: bold; padding: 8px;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        ind = result.get("indicators", {})
        fib = result.get("fibonacci", {})

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Indicator", "Deger", "Sinyal"])
        table.horizontalHeader().setStyleSheet("color: #aaa; font-weight: bold;")
        table.verticalHeader().setVisible(False)
        table.setStyleSheet("""
            QTableWidget { background: #12121e; color: #e0e0e0; gridline-color: #2a2a3e; border: 1px solid #333; }
            QTableWidget::item { padding: 4px; }
        """)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        rows = []
        def add_row(label, val, signal=""):
            rows.append((label, val, signal))

        def fmt(v):
            if v is None: return "-"
            if isinstance(v, float): return f"{v:,.2f}"
            return str(v)

        vwap = ind.get("vwap", {})
        rsi = ind.get("rsi", {})
        ema9 = ind.get("ema9", {})
        ema21 = ind.get("ema21", {})
        sma5 = ind.get("sma5", {})
        sma20 = ind.get("sma20", {})
        macd = ind.get("macd", {})
        bb = ind.get("bollinger", {})
        cci = ind.get("cci", {})
        stoch = ind.get("stoch_rsi", {})
        atr = ind.get("atr", {})
        st = ind.get("supertrend", {})

        add_row("VWAP", fmt(vwap.get("current")))
        add_row("RSI (14)", fmt(rsi.get("current")),
                "AL" if rsi.get("current") and rsi["current"] < 30 else
                "SAT" if rsi.get("current") and rsi["current"] > 70 else "NOTR")
        add_row("EMA 9", fmt(ema9.get("current")))
        add_row("EMA 21", fmt(ema21.get("current")))
        add_row("SMA 5", fmt(sma5.get("current")))
        add_row("SMA 20", fmt(sma20.get("current")))
        add_row("MACD", fmt(macd.get("macd")))
        add_row("Signal", fmt(macd.get("signal")))
        add_row("Histogram", fmt(macd.get("histogram")),
                "AL" if macd.get("histogram") and macd["histogram"] > 0 else "SAT")
        add_row("BB Upper", fmt(bb.get("upper")))
        add_row("BB Lower", fmt(bb.get("lower")))
        add_row("CCI", fmt(cci.get("current")),
                "AL" if cci.get("current") and cci["current"] < -100 else
                "SAT" if cci.get("current") and cci["current"] > 100 else "NOTR")
        add_row("StochRSI K", fmt(stoch.get("k")))
        add_row("StochRSI D", fmt(stoch.get("d")))
        add_row("ATR", fmt(atr.get("current")))
        supertrend_val = st.get("current")
        add_row("Supertrend", "YUKARI" if supertrend_val == 1 else "ASAGI" if supertrend_val == -1 else "NOTR",
                "AL" if supertrend_val == 1 else "SAT" if supertrend_val == -1 else "")
        add_row("Son Fiyat", fmt(result.get("last_close")))

        table.setRowCount(len(rows))
        for i, (label, val, sig) in enumerate(rows):
            item_label = QTableWidgetItem(label)
            item_label.setForeground(QColor("#8888aa"))
            item_val = QTableWidgetItem(val)
            item_val.setForeground(QColor("#ffffff"))
            item_val.setFont(QFont("Consolas", 11, QFont.Bold))
            item_sig = QTableWidgetItem(sig)
            sig_color = "#26a69a" if sig == "AL" else ("#ef5350" if sig == "SAT" else "#848e9c")
            item_sig.setForeground(QColor(sig_color))
            table.setItem(i, 0, item_label)
            table.setItem(i, 1, item_val)
            table.setItem(i, 2, item_sig)

        layout.addWidget(table)

        if fib:
            fib_frame = QFrame()
            fib_frame.setStyleSheet("QFrame { background: #12121e; border: 1px solid #333; border-radius: 8px; padding: 8px; }")
            fib_layout = QHBoxLayout(fib_frame)
            fib_layout.addWidget(QLabel("FIBONACCI:"))
            for key in ["0.0", "0.236", "0.382", "0.5", "0.618", "0.786", "1.0"]:
                lbl = QLabel(f"%{key}: {fmt(fib.get(key))}")
                lbl.setStyleSheet("color: #ffd700; font-size: 11px;")
                fib_layout.addWidget(lbl)
            layout.addWidget(fib_frame)

        close_btn = QPushButton("Kapat")
        close_btn.setStyleSheet("background: #ef5350; color: white; padding: 8px 20px; font-weight: bold; border-radius: 6px;")
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

        dlg.exec()
