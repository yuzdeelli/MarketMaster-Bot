import os
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QLineEdit, QComboBox, QTableWidget,
                                QTableWidgetItem, QHeaderView, QAbstractItemView,
                                QMenu, QMessageBox, QFileDialog, QDialog,
                                QGridLayout, QCheckBox, QApplication, QCheckBox as QCheckBoxWidget,
                                QFrame, QScrollArea)
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QFont, QAction, QShortcut, QKeySequence
import pandas as pd
import numpy as np
from datetime import datetime
from ui.searchable_combo import SearchableComboBox


class PriceGuideDialog(QDialog):
    STRATS = ["Min", "Q1", "%95 Alt", "Medyan", "Mod", "%95 Ust", "Q3", "Max", "Max %3 Vergi"]
    BUY_ZONES = [
        ("Min→Q1", "Min", "Q1", "#0d2818", "#1a5c2a", "Süper Fırsat"),
        ("Q1→95", "Q1", "%95 Alt", "#0e2a1a", "#1a7a2e", "İyi Fiyat"),
        ("95→Med", "%95 Alt", "Medyan", "#1a2a1e", "#2a8a3a", "Normal"),
        ("Med→Max", "Medyan", "Max", "#2a2a1a", "#4a6a2a", "Pahalı"),
    ]
    SELL_ZONES = [
        ("Min→Q1", "Min", "Q1", "#1a0d0d", "#8a2a2a", "Baskı Altı"),
        ("Q1→Med", "Q1", "Medyan", "#1a1a0d", "#8a7a2a", "Normal Satış"),
        ("Med→95", "Medyan", "%95 Ust", "#0d1a1a", "#2a8a8a", "Yüksek Kar"),
        ("95→Max", "%95 Ust", "Max", "#0d1a2a", "#2a5a9a", "Çok Yüksek"),
    ]

    def _gradient_color(self, value, all_values, buy_mode=True, invert=False, danger_below=0):
        valid = [(i, v) for i, v in enumerate(all_values) if v > 0]
        if len(valid) < 2 or value <= 0:
            return "#888", "#0f1522"
        if danger_below > 0 and value < danger_below:
            return "#ff4444", "#3a0a0a"
        valid_sorted = sorted(valid, key=lambda x: x[1])
        rank_map = {orig_idx: rank for rank, (orig_idx, val) in enumerate(valid_sorted)}
        orig_idx = all_values.index(value)
        rank = rank_map.get(orig_idx, 0)
        total = len(valid_sorted)
        t = rank / (total - 1) if total > 1 else 0
        if not buy_mode:
            t = 1.0 - t
        if invert:
            t = 1.0 - t
        r = int(231 * t + 46 * (1 - t))
        g = int(76 * t + 204 * (1 - t))
        b = int(60 * t + 113 * (1 - t))
        fg = f"#{r:02x}{g:02x}{b:02x}"
        bg_t = t * 0.18
        br = int(18 * (1 - bg_t) + r * bg_t)
        bg_g = int(24 * (1 - bg_t) + g * bg_t)
        bg_b = int(36 * (1 - bg_t) + b * bg_t)
        bg = f"#{br:02x}{bg_g:02x}{bg_b:02x}"
        return fg, bg

    def __init__(self, portfolio_tab, parent=None):
        super().__init__(parent)
        self.ptab = portfolio_tab
        self.setWindowTitle("Fiyat Rehberi")
        self.setMinimumSize(1100, 600)
        self.resize(1400, 950)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog { background:#0c0e1a; color:#eee; border:1px solid #1e2a3a; border-radius:10px; }")
        self._row_map = {}
        self._search_term = ""
        self._drag_pos = None
        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self._pre_max_geo = None

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(3)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(4, 2, 4, 2)
        drag_area = QLabel("  FIYAT REHBERI")
        drag_area.setStyleSheet("color:#f1c40f; font-size:13px; font-weight:bold; letter-spacing:2px; background:transparent;")
        title_bar.addWidget(drag_area)
        title_bar.addStretch()

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Item ara...")
        self.search_entry.setFixedWidth(150)
        self.search_entry.setStyleSheet("QLineEdit{background:#111828;color:#eee;border:1px solid #2a3a4a;border-radius:4px;padding:3px 6px;font-size:11px;}QLineEdit:focus{border:1px solid #f39c12;}")
        self.search_entry.textChanged.connect(self._on_search)
        title_bar.addWidget(self.search_entry)

        for txt, color, fn in [("Yenile", "#f39c12", self.refresh), ("Kaydet", "#2ecc71", self._save), ("+ Yeni Kayıt", "#3498db", self._new_record)]:
            b = QPushButton(txt)
            b.setFixedSize(65 if "Yeni" in txt else 55, 24)
            b.setStyleSheet(f"QPushButton{{background:#1a2a3e;color:{color};border:1px solid #2a3a4a;border-radius:3px;font-weight:bold;font-size:10px;}}QPushButton:hover{{background:#1e3348;}}")
            b.clicked.connect(fn)
            title_bar.addWidget(b)

        for txt, color, bgc, brc in [("-", "#f39c12", "#1a2a3e", "#2a3a4a"), ("□", "#f39c12", "#1a2a3e", "#2a3a4a"), ("X", "#e74c3c", "#3a1a1a", "#4a2a2a")]:
            b = QPushButton(txt)
            b.setFixedSize(24, 24)
            b.setStyleSheet(f"QPushButton{{background:{bgc};color:{color};border:1px solid {brc};border-radius:3px;font-weight:bold;font-size:11px;}}QPushButton:hover{{background:#4a2020;}}")
            b.clicked.connect(self.showMinimized if txt == "-" else (self._toggle_maximize if txt == "□" else self.close))
            title_bar.addWidget(b)
        root.addLayout(title_bar)

        headers = ["Item", "Lvl", ""] + self.STRATS + ["Sec.Alis", "Sec.Satis", "Kar", "Spread", "Adet"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setStyleSheet("QTableWidget{background:#0a0a14;color:#eee;border:1px solid #1a1a2e;}QTableWidget::item{padding:1px 2px;border:none;}QTableWidget::item:selected{background:#1a3a5c;}QHeaderView::section{background:#111122;color:#f1c40f;font-weight:bold;font-size:9px;padding:3px 2px;border-bottom:2px solid #f39c12;border-right:1px solid #1a1a2e;}")
        self.table.cellClicked.connect(self._on_cell_click)
        header = self.table.horizontalHeader()
        widths = [130, 30, 16, 60, 60, 60, 60, 60, 60, 60, 60, 66, 70, 70, 68, 60, 32]
        for c in range(len(headers)):
            header.setSectionResizeMode(c, QHeaderView.Fixed)
            header.resizeSection(c, widths[c])
        self.table.setRowCount(0)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self.table)

    def _show_context_menu(self, pos):
        selected = self.table.currentRow()
        if selected < 0 or selected not in self._row_map:
            return
        idx, mode, buy_prices, sell_prices = self._row_map[selected]
        item = self.ptab.portfolio[idx]
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#111828;color:#eee;border:1px solid #2a3a4a;}QMenu::item:selected{background:#1a3a5c;}")
        act_history = menu.addAction("Fiyat Gecmisi")
        act_history.triggered.connect(lambda: self._show_price_history(item))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_price_history(self, item):
        item_name = item.get("name", "")
        item_lvl = item.get("lvl", "")
        db_lvl = "" if item_lvl in ["+0", "0"] else item_lvl
        records = self.ptab.master.analyzer.db.get_manual_price_history(item_name, db_lvl)
        dlg = PriceHistoryDialog(item_name, item_lvl, records, self)
        dlg.exec()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            if self._pre_max_geo:
                self.setGeometry(self._pre_max_geo)
        else:
            self._pre_max_geo = self.geometry()
            self.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            e = 8
            r = self.rect()
            edge = (pos.x() > r.width() - e, pos.y() > r.height() - e, pos.x() < e, pos.y() < e)
            if any(edge):
                self._resizing = True
                self._resize_edge = edge
                self._drag_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                event.accept()
                return
            tb = self.rect().adjusted(0, 0, 0, -self.rect().height() + 34)
            if tb.contains(pos):
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                event.accept()

    def mouseMoveEvent(self, event):
        gp = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        if self._dragging and self._drag_pos:
            self.move(self.pos() + gp - self._drag_pos)
            self._drag_pos = gp
            event.accept()
        elif self._resizing and self._drag_pos:
            diff = gp - self._drag_pos
            geo = self.geometry()
            ri, bo, le, to = self._resize_edge
            if ri: geo.setRight(geo.right() + diff.x())
            if bo: geo.setBottom(geo.bottom() + diff.y())
            if le: geo.setLeft(geo.left() + diff.x())
            if to: geo.setTop(geo.top() + diff.y())
            if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
            self._drag_pos = gp
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            tb = self.rect().adjusted(0, 0, 0, -self.rect().height() + 34)
            if tb.contains(pos):
                self._toggle_maximize()

    def _on_search(self, text):
        self._search_term = text.strip().lower()
        self.refresh()

    def refresh(self):
        try:
            filter_server = self.ptab._get_filtered_server()
            db_server = self.ptab._resolve_db_server(filter_server)
            self._row_map.clear()

            items_to_show = []
            for idx, item in enumerate(self.ptab.portfolio):
                if not self.ptab._item_matches_filter(item, filter_server):
                    continue
                if self._search_term and self._search_term not in (item.get("name") or "").lower():
                    continue
                db_lvl = "" if item.get("lvl", "") in ["+0", "0"] else item.get("lvl", "")
                try:
                    stats = self.ptab.master.get_cached_stats(item.get("name", ""), db_lvl, server=db_server)
                except Exception:
                    stats = None
                items_to_show.append((idx, item, stats))

            self.table.setRowCount(len(items_to_show) * 4)

            for rp, (idx, item, stats) in enumerate(items_to_show):
                try:
                    r_a = rp * 4
                    r_tax = r_a + 1
                    r_zone = r_a + 2
                    r_s = r_a + 3

                    db_lvl = "" if item.get("lvl", "") in ["+0", "0"] else item.get("lvl", "")
                    item_name = item.get("name", "")
                    buy_strat = item.get("buy_strategy", "Medyan") or "Medyan"
                    sell_strat = item.get("sell_strategy", "Auto") or "Auto"
                    buy_prices = {s: self.ptab._calc_strategy_price(item_name, db_lvl, s, "buy", stats) for s in self.STRATS}
                    sell_prices = {s: self.ptab._calc_strategy_price(item_name, db_lvl, s, "sell", stats) for s in self.STRATS}
                    buy_vals = [buy_prices.get(s, 0) for s in self.STRATS]
                    sell_vals = [sell_prices.get(s, 0) for s in self.STRATS]
                    selected_buy = item.get("buy_price", 0) or 0
                    selected_sell = item.get("sell_price", 0) or 0
                    count = item.get("count", 1) or 1

                    self._row_map[r_a] = (idx, "buy", buy_prices, sell_prices)
                    self._row_map[r_tax] = (idx, "tax", buy_prices, sell_prices)
                    self._row_map[r_zone] = (idx, "zone", buy_prices, sell_prices)
                    self._row_map[r_s] = (idx, "sell", buy_prices, sell_prices)

                    even = rp % 2 == 0
                    bg_a = "#111828" if even else "#0f1522"
                    bg_s = "#0c1118" if even else "#0a0e16"
                    bg_z = "#0a0c14"
                    bg_t = "#0a0e18"

                    def _cell(val, fg, font, bg, align=Qt.AlignCenter, tip=None):
                        c = QTableWidgetItem(str(val) if val else "-")
                        c.setForeground(QColor(fg))
                        c.setFont(font)
                        c.setBackground(QColor(bg))
                        c.setTextAlignment(align)
                        if tip:
                            c.setToolTip(str(tip))
                        return c

                    f8 = QFont("Consolas", 8, QFont.Bold)
                    f8n = QFont("Consolas", 8)
                    f7 = QFont("Consolas", 7)
                    f7b = QFont("Consolas", 7, QFont.Bold)
                    f9b = QFont("Segoe UI", 9, QFont.Bold)
                    f8b = QFont("Segoe UI", 8, QFont.Bold)

                    name_tip = f"{item_name} {item.get('lvl','')} | {count} adet"

                    self.table.setItem(r_a, 0, _cell(f"  {item_name}", "#f1c40f", f9b, bg_a, Qt.AlignLeft | Qt.AlignVCenter, name_tip))
                    self.table.setItem(r_a, 1, _cell(item.get("lvl", ""), "#777", f8n, bg_a))
                    self.table.setItem(r_a, 2, _cell("A", "#f39c12", f8b, bg_a))

                    for si, strat in enumerate(self.STRATS):
                        bp = buy_prices.get(strat, 0) or 0
                        fg, bgc = self._gradient_color(bp, buy_vals, buy_mode=True, invert=(buy_strat == "Max %3 Vergi"))
                        if strat == buy_strat:
                            self.table.setItem(r_a, 3 + si, _cell(f"{bp:,.0f}" if bp > 0 else "-", "#f39c12", f8, "#1a3a5c", tip=f"{strat}: {bp:,.0f}"))
                        else:
                            self.table.setItem(r_a, 3 + si, _cell(f"{bp:,.0f}" if bp > 0 else "-", fg, f8, bgc, tip=f"{strat}: {bp:,.0f}"))

                    self.table.setItem(r_a, 12, _cell(f"{selected_buy:,.0f}" if selected_buy > 0 else "-", "#f39c12", f8, bg_a))
                    self.table.setItem(r_a, 13, _cell(f"{selected_sell:,.0f}" if selected_sell > 0 else "-", "#3498db", f8, bg_a))

                    if selected_buy > 0 and selected_sell > 0:
                        profit = (selected_sell * 0.97) - selected_buy
                        pct = (profit / selected_buy * 100) if selected_buy else 0
                        pc = "#2ecc71" if profit > 0 else "#e74c3c"
                        pi = "▲" if profit > 0 else "▼"
                        self.table.setItem(r_a, 14, _cell(f"{pi}{profit:,.0f}(%{pct:.0f}%)", pc, f8, bg_a))
                        spread = selected_sell - selected_buy
                        sp_pct = (spread / selected_buy * 100) if selected_buy else 0
                        sc = "#2ecc71" if sp_pct > 10 else ("#f39c12" if sp_pct > 3 else "#e74c3c")
                        self.table.setItem(r_a, 15, _cell(f"{spread:,.0f}(%{sp_pct:.0f}%)", sc, f8, bg_a))
                        self.table.setItem(r_a, 16, _cell(str(count) if count > 1 else "", "#888", f7, bg_a))
                    else:
                        for cc in [14, 15, 16]:
                            self.table.setItem(r_a, cc, _cell("", "#888", f7, bg_a))

                    sell_stats = (stats or {}).get("sell", {}) or {}
                    buy_stats = (stats or {}).get("buy", {}) or {}
                    max_buy_val = buy_stats.get("max", 0) or 0
                    min_sell_val = int(max_buy_val * 0.97) if max_buy_val > 0 else 0

                    tax_tip = f"Max Alis: {max_buy_val:,.0f}\nMax%3Vergi(min satis): {min_sell_val:,.0f}"
                    self.table.setItem(r_tax, 0, _cell("MAX A", "#e74c3c", f7b, bg_t, tip=tax_tip))
                    self.table.setItem(r_tax, 1, _cell(f"{max_buy_val:,.0f}" if max_buy_val > 0 else "-", "#f39c12", f7b, bg_t))
                    self.table.setItem(r_tax, 2, _cell(f"{min_sell_val:,.0f}" if min_sell_val > 0 else "-", "#2ecc71", f7b, bg_t))

                    s_map_tax = {"Min": "min", "Q1": "q1", "%95 Alt": "ci_low", "Medyan": "median", "Mod": "mode", "%95 Ust": "ci_high", "Q3": "q3", "Max": "max", "Max %3 Vergi": "max"}
                    for si, strat in enumerate(self.STRATS):
                        stat_key = s_map_tax.get(strat, "")
                        sp = sell_stats.get(stat_key, 0) or 0
                        if sp > 0 and min_sell_val > 0:
                            diff = sp - min_sell_val
                            pct = (diff / min_sell_val * 100) if min_sell_val else 0
                            pc = "#2ecc71" if diff >= 0 else "#e74c3c"
                            self.table.setItem(r_tax, 3 + si, _cell(f"{sp:,.0f}({pct:+.0f}%)", pc, f7b, bg_t))
                        else:
                            self.table.setItem(r_tax, 3 + si, _cell("-", "#444", f7b, bg_t))

                    for cc in [12, 13, 14, 15, 16]:
                        self.table.setItem(r_tax, cc, _cell("", "#444", f7, bg_t))

                    self.table.setItem(r_zone, 2, _cell("Z", "#888", f7b, bg_z))

                    for zi, (zname, zlo_key, zhi_key, zbg, zfg, zlabel) in enumerate(self.BUY_ZONES):
                        zlo = buy_prices.get(zlo_key, 0) or 0
                        zhi = buy_prices.get(zhi_key, 0) or 0
                        zval = (zlo + zhi) / 2 if zlo > 0 and zhi > 0 else (zhi if zhi > 0 else zlo)
                        txt = f"{zname} {zval:,.0f} {zlabel}" if zval > 0 else f"{zname} -"
                        tip = f"Alis {zlabel}\n{zlo:,.0f} - {zhi:,.0f} = {zval:,.0f}"
                        self.table.setItem(r_zone, 3 + zi, _cell(txt, zfg, f7b, zbg, tip=tip))

                    for zi, (zname, zlo_key, zhi_key, zbg, zfg, zlabel) in enumerate(self.SELL_ZONES):
                        zlo = sell_prices.get(zlo_key, 0) or 0
                        zhi = sell_prices.get(zhi_key, 0) or 0
                        zval = (zlo + zhi) / 2 if zlo > 0 and zhi > 0 else (zhi if zhi > 0 else zlo)
                        txt = f"{zname} {zval:,.0f} {zlabel}" if zval > 0 else f"{zname} -"
                        tip = f"Satis {zlabel}\n{zlo:,.0f} - {zhi:,.0f} = {zval:,.0f}"
                        self.table.setItem(r_zone, 7 + zi, _cell(txt, zfg, f7b, zbg, tip=tip))

                    self.table.setItem(r_zone, 11, _cell("", "#444", f7, bg_z))
                    for cc in [0, 1] + list(range(12, 17)):
                        self.table.setItem(r_zone, cc, _cell("", "#333", f7, bg_z))

                    self.table.setItem(r_s, 0, _cell(f"  {item_name}", "#444", f7, bg_s, Qt.AlignLeft | Qt.AlignVCenter))
                    self.table.setItem(r_s, 1, _cell(item.get("lvl", ""), "#333", f7, bg_s))
                    self.table.setItem(r_s, 2, _cell("S", "#3498db", f7b, bg_s))

                    for si, strat in enumerate(self.STRATS):
                        sp = sell_prices.get(strat, 0) or 0
                        fg, bgc = self._gradient_color(sp, sell_vals, buy_mode=False, danger_below=selected_buy)
                        if strat == sell_strat:
                            self.table.setItem(r_s, 3 + si, _cell(f"{sp:,.0f}" if sp > 0 else "-", "#3498db", f8n, "#1a3a5c"))
                        else:
                            self.table.setItem(r_s, 3 + si, _cell(f"{sp:,.0f}" if sp > 0 else "-", fg, f8n, bgc))

                    for cc in [12, 13, 14, 15, 16]:
                        self.table.setItem(r_s, cc, _cell("", "#444", f7, bg_s))

                    self.table.setRowHeight(r_a, 22)
                    self.table.setRowHeight(r_tax, 20)
                    self.table.setRowHeight(r_zone, 22)
                    self.table.setRowHeight(r_s, 20)

                except Exception:
                    import traceback
                    traceback.print_exc()
                    continue

        except Exception:
            import traceback
            traceback.print_exc()

    def _on_cell_click(self, row, col):
        try:
            if row not in self._row_map or col < 2:
                return
            idx, ptype, buy_prices, sell_prices = self._row_map[row]
            item = self.ptab.portfolio[idx]

            if ptype == "buy" and col <= 11:
                si = col - 3
                if 0 <= si < len(self.STRATS):
                    self.ptab._on_guide_item_strat_click(idx, self.STRATS[si], "buy")
                    self.refresh()
            elif ptype == "sell" and col <= 11:
                si = col - 3
                if 0 <= si < len(self.STRATS):
                    self.ptab._on_guide_item_strat_click(idx, self.STRATS[si], "sell")
                    self.refresh()
            elif ptype == "zone":
                if 3 <= col <= 6:
                    zi = col - 3
                    if zi < len(self.BUY_ZONES):
                        _, zlo_key, zhi_key, _, _, _ = self.BUY_ZONES[zi]
                        zlo = buy_prices.get(zlo_key, 0)
                        zhi = buy_prices.get(zhi_key, 0)
                        zval = (zlo + zhi) / 2 if zlo > 0 and zhi > 0 else (zhi if zhi > 0 else zlo)
                        if zval > 0:
                            item["buy_price"] = int(zval)
                            item["buy_strategy"] = "Manuel"
                            item["buy_fixed"] = True
                            self.ptab.auto_save()
                            self.ptab.render_portfolio_ui()
                            self.refresh()
                elif 7 <= col <= 10:
                    zi = col - 7
                    if zi < len(self.SELL_ZONES):
                        _, zlo_key, zhi_key, _, _, _ = self.SELL_ZONES[zi]
                        zlo = sell_prices.get(zlo_key, 0)
                        zhi = sell_prices.get(zhi_key, 0)
                        zval = (zlo + zhi) / 2 if zlo > 0 and zhi > 0 else (zhi if zhi > 0 else zlo)
                        if zval > 0:
                            item["sell_price"] = int(zval)
                            item["sell_strategy"] = "Manuel"
                            item["sell_fixed"] = True
                            self.ptab.auto_save()
                            self.ptab.render_portfolio_ui()
                            self.refresh()
            elif ptype == "tax" and 3 <= col <= 11:
                si = col - 3
                if 0 <= si < len(self.STRATS):
                    s_map_tax = {"Min": "min", "Q1": "q1", "%95 Alt": "ci_low", "Medyan": "median", "Mod": "mode", "%95 Ust": "ci_high", "Q3": "q3", "Max": "max", "Max %3 Vergi": "max"}
                    stat_key = s_map_tax.get(self.STRATS[si], "")
                    db_lvl = "" if item["lvl"] in ["+0", "0"] else item["lvl"]
                    stats = self.ptab.master.get_cached_stats(item["name"], db_lvl, server=self.ptab._resolve_db_server(self.ptab._get_filtered_server()))
                    sell_stat = stats.get("sell", {}).get(stat_key, 0) if stats else 0
                    if sell_stat > 0:
                        item["buy_price"] = int(sell_stat)
                        item["buy_strategy"] = "Manuel"
                        item["buy_fixed"] = True
                        self.ptab.auto_save()
                        self.ptab.render_portfolio_ui()
                        self.refresh()
        except Exception:
            import traceback
            traceback.print_exc()

    def _save(self):
        self.ptab.save_portfolio_manual()
        self.ptab.render_portfolio_ui()

    def _new_record(self):
        selected = self.table.currentRow()
        if selected < 0 or selected not in self._row_map:
            QMessageBox.information(self, "Bilgi", "Once bir item secin (A veya S satiri)")
            return
        idx, mode, buy_prices, sell_prices = self._row_map[selected]
        item = self.ptab.portfolio[idx]
        dlg = PriceRecordDialog(item, self.ptab, self)
        dlg.exec()


class PriceRecordDialog(QDialog):
    def __init__(self, item, ptab, parent=None):
        super().__init__(parent)
        self.item = item
        self.ptab = ptab
        self.setWindowTitle("Yeni Fiyat Kaydi")
        self.setFixedSize(360, 260)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog{background:#0c0e1a;color:#eee;border:1px solid #1e2a3a;border-radius:8px;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title_bar = QHBoxLayout()
        title_label = QLabel("  YENI FIYAT KAYDI")
        title_label.setStyleSheet("color:#f1c40f;font-size:12px;font-weight:bold;background:transparent;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        close_btn = QPushButton("X")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton{background:#3a1a1a;color:#e74c3c;border:1px solid #4a2a2a;border-radius:3px;font-weight:bold;}QPushButton:hover{background:#4a2020;}")
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        root.addLayout(title_bar)

        info = QLabel(f"{item.get('name', '')} {item.get('lvl', '')}")
        info.setStyleSheet("color:#f1c40f;font-size:13px;font-weight:bold;background:transparent;")
        root.addWidget(info)

        form = QGridLayout()
        form.setSpacing(6)

        form.addWidget(QLabel("Islem:"), 0, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Alis", "Satis"])
        self.type_combo.setStyleSheet("QComboBox{background:#111828;color:#eee;border:1px solid #2a3a4a;border-radius:3px;padding:3px 6px;}QComboBox::drop-down{border:none;}")
        form.addWidget(self.type_combo, 0, 1)

        form.addWidget(QLabel("Sunucu:"), 1, 0)
        self.server_combo = QComboBox()
        self.server_combo.setEditable(True)
        self._load_servers()
        form.addWidget(self.server_combo, 1, 1)

        form.addWidget(QLabel("Fiyat:"), 2, 0)
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Ornek: 150000")
        self.price_input.setStyleSheet("QLineEdit{background:#111828;color:#eee;border:1px solid #2a3a4a;border-radius:3px;padding:3px 6px;}QLineEdit:focus{border:1px solid #f39c12;}")
        form.addWidget(self.price_input, 2, 1)

        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Kaydet")
        save_btn.setFixedSize(80, 28)
        save_btn.setStyleSheet("QPushButton{background:#2ecc71;color:white;border:1px solid #27ae60;border-radius:4px;font-weight:bold;}QPushButton:hover{background:#27ae60;}")
        save_btn.clicked.connect(self._save_record)
        btn_row.addWidget(save_btn)
        cancel_btn = QPushButton("Iptal")
        cancel_btn.setFixedSize(80, 28)
        cancel_btn.setStyleSheet("QPushButton{background:#1a2a3e;color:#888;border:1px solid #2a3a4a;border-radius:4px;}QPushButton:hover{background:#2a3a4e;}")
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

    def _load_servers(self):
        servers = ["Zero", "Pandora", "Agartha", "Felis", "Destan", "Minark", "Dryads", "Oreads"]
        self.server_combo.addItems(servers)
        item_server = self.item.get("server", "")
        if item_server:
            idx = self.server_combo.findText(item_server, Qt.MatchExactly)
            if idx >= 0:
                self.server_combo.setCurrentIndex(idx)
            else:
                self.server_combo.setEditText(item_server)

    def _save_record(self):
        ptype = self.type_combo.currentText()
        server = self.server_combo.currentText().strip()
        price_text = self.price_input.text().strip().replace(".", "").replace(",", "")

        if not server:
            QMessageBox.warning(self, "Hata", "Sunucu secin!")
            return
        if not price_text or not price_text.isdigit():
            QMessageBox.warning(self, "Hata", "Gecerli bir fiyat girin!")
            return

        price = int(price_text)
        item_name = self.item.get("name", "")
        item_lvl = self.item.get("lvl", "")
        db_lvl = "" if item_lvl in ["+0", "0"] else item_lvl

        ok = self.ptab.master.analyzer.db.insert_manual_price(item_name, db_lvl, server, price, ptype)
        if ok:
            QMessageBox.information(self, "Kaydedildi", f"{item_name} {item_lvl} - {ptype} - {server} - {price:,.0f}")
            self.close()
        else:
            QMessageBox.warning(self, "Hata", "Kayit basarisiz!")



class PriceHistoryDialog(QDialog):
    def __init__(self, item_name, item_lvl, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Fiyat Gecmisi - {item_name} {item_lvl}")
        self.setMinimumSize(500, 400)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("QDialog{background:#0c0e1a;color:#eee;border:1px solid #1e2a3a;border-radius:8px;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        title_bar = QHBoxLayout()
        title_label = QLabel(f"  FIYAT GECMISI - {item_name} {item_lvl}")
        title_label.setStyleSheet("color:#f1c40f;font-size:12px;font-weight:bold;background:transparent;")
        title_bar.addWidget(title_label)
        title_bar.addStretch()
        close_btn = QPushButton("X")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("QPushButton{background:#3a1a1a;color:#e74c3c;border:1px solid #4a2a2a;border-radius:3px;font-weight:bold;}QPushButton:hover{background:#4a2020;}")
        close_btn.clicked.connect(self.close)
        title_bar.addWidget(close_btn)
        root.addLayout(title_bar)

        if not records:
            no_data = QLabel("Henuz kayit yok. Rehberden '+ Yeni Kayit' butonuyla kayit ekleyin.")
            no_data.setStyleSheet("color:#666;font-style:italic;background:transparent;")
            no_data.setAlignment(Qt.AlignCenter)
            root.addWidget(no_data)
        else:
            stats_label = QLabel(f"Toplam {len(records)} kayit")
            stats_label.setStyleSheet("color:#888;font-size:10px;background:transparent;")
            root.addWidget(stats_label)

            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["#","Tarih","Sunucu","Fiyat","Tur"])
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setShowGrid(False)
            table.setStyleSheet("QTableWidget{background:#0a0a14;color:#eee;border:1px solid #1a1a2e;}QTableWidget::item{padding:2px 4px;}QHeaderView::section{background:#111122;color:#f1c40f;font-weight:bold;font-size:9px;padding:3px;border-bottom:2px solid #f39c12;}")
            header = table.horizontalHeader()
            for c, w in enumerate([30, 140, 80, 100, 60]):
                header.setSectionResizeMode(c, QHeaderView.Fixed)
                header.resizeSection(c, w)
            table.setRowCount(len(records))
            for i, rec in enumerate(records):
                ptype = rec.get("type", "")
                pcolor = "#2ecc71" if ptype == "Alis" else "#3498db"
                pbg = "#0d2818" if ptype == "Alis" else "#0d1a2a"
                def _cell(val, fg, bg):
                    c = QTableWidgetItem(str(val))
                    c.setForeground(QColor(fg))
                    c.setBackground(QColor(bg))
                    c.setTextAlignment(Qt.AlignCenter)
                    return c
                table.setItem(i, 0, _cell(str(i+1), "#888", "#0a0a14"))
                table.setItem(i, 1, _cell(rec.get("timestamp", ""), "#eee", "#0a0a14"))
                table.setItem(i, 2, _cell(rec.get("server", ""), "#f39c12", "#0a0a14"))
                table.setItem(i, 3, _cell(f"{rec.get('price', 0):,.0f}", pcolor, pbg))
                table.setItem(i, 4, _cell(ptype, pcolor, pbg))
                table.setRowHeight(i, 22)
            root.addWidget(table)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn2 = QPushButton("Kapat")
        close_btn2.setFixedSize(80, 26)
        close_btn2.setStyleSheet("QPushButton{background:#1a2a3e;color:#888;border:1px solid #2a3a4a;border-radius:4px;}QPushButton:hover{background:#2a3a4e;}")
        close_btn2.clicked.connect(self.close)
        close_row.addWidget(close_btn2)
        root.addLayout(close_row)



class ExcelPreviewDialog(QDialog):
    COLS = ["Item", "Lvl", "Adet", "Alis Fiyati", "Alis Stratejisi", "Satis Fiyati", "Satis Stratejisi", "Kar", "Kar %", "Durum", "Maliyet", "Net Kasa"]

    def __init__(self, portfolio_tab, parent=None):
        super().__init__(parent)
        self.ptab = portfolio_tab
        self.setWindowTitle("Excel Onizleme - Portfoy Ozet")
        self.setMinimumSize(1200, 650)
        self.resize(1400, 750)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background: #0c0e1a;
                color: #eee;
                border: 1px solid #1e2a3a;
                border-radius: 10px;
            }
        """)
        self._items = []
        self._search_term = ""

        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(10, 10, 10, 10)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(6, 4, 6, 4)
        drag_area = QLabel("  EXCEL ONIZLEME")
        drag_area.setStyleSheet("color: #f1c40f; font-size: 15px; font-weight: bold; letter-spacing: 2px; background: transparent;")
        title_bar.addWidget(drag_area)
        title_bar.addStretch()
        self.total_lbl = QLabel("")
        self.total_lbl.setStyleSheet("color: #2ecc71; font-size: 12px; font-weight: bold; background: transparent;")
        title_bar.addWidget(self.total_lbl)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Item ara...")
        self.search_entry.setFixedWidth(180)
        self.search_entry.setStyleSheet("""
            QLineEdit {
                background: #111828; color: #eee; border: 1px solid #2a3a4a;
                border-radius: 5px; padding: 6px 10px; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #f39c12; }
        """)
        self.search_entry.textChanged.connect(self._on_search)
        title_bar.addWidget(self.search_entry)

        btn_refresh = QPushButton("Yenile")
        btn_refresh.setFixedSize(70, 30)
        btn_refresh.setStyleSheet("QPushButton { background:#1a2a3e; color:#f39c12; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:11px; } QPushButton:hover { background:#1e3348; }")
        btn_refresh.clicked.connect(self.refresh)
        title_bar.addWidget(btn_refresh)

        btn_rehber = QPushButton("Rehber")
        btn_rehber.setFixedSize(70, 30)
        btn_rehber.setStyleSheet("QPushButton { background:#1a2a3e; color:#8e44ad; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:11px; } QPushButton:hover { background:#1e3348; }")
        btn_rehber.clicked.connect(self._toggle_detail)
        title_bar.addWidget(btn_rehber)

        btn_export = QPushButton("Excel")
        btn_export.setFixedSize(60, 30)
        btn_export.setStyleSheet("QPushButton { background:#1a2a3e; color:#3498db; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:11px; } QPushButton:hover { background:#1e3348; }")
        btn_export.clicked.connect(self._export)
        title_bar.addWidget(btn_export)

        btn_min = QPushButton("-")
        btn_min.setFixedSize(30, 30)
        btn_min.setStyleSheet("QPushButton { background:#1a2a3e; color:#f39c12; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:14px; } QPushButton:hover { background:#1e3348; }")
        btn_min.clicked.connect(self.showMinimized)
        title_bar.addWidget(btn_min)

        self._btn_max = QPushButton("□")
        self._btn_max.setFixedSize(30, 30)
        self._btn_max.setStyleSheet("QPushButton { background:#1a2a3e; color:#f39c12; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:14px; } QPushButton:hover { background:#1e3348; }")
        self._btn_max.clicked.connect(self._toggle_maximize)
        title_bar.addWidget(self._btn_max)

        btn_close = QPushButton("X")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("QPushButton { background:#3a1a1a; color:#e74c3c; border:1px solid #4a2a2a; border-radius:5px; font-weight:bold; font-size:12px; } QPushButton:hover { background:#4a2020; }")
        btn_close.clicked.connect(self.close)
        title_bar.addWidget(btn_close)

        root.addLayout(title_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; }
            QTableWidget::item { padding: 3px 4px; border: none; }
            QTableWidget::item:selected { background: #1a3a5c; }
            QTableWidget::alternate { background: #0e1220; }
            QHeaderView::section {
                background: #111122; color: #f1c40f; font-weight: bold; font-size: 11px;
                padding: 6px 4px; border-bottom: 2px solid #f39c12; border-right: 1px solid #1a1a2e;
            }
        """)
        header = self.table.horizontalHeader()
        widths = [150, 40, 40, 100, 90, 100, 90, 90, 60, 80, 100, 100]
        for c in range(len(self.COLS)):
            header.setSectionResizeMode(c, QHeaderView.Fixed)
            header.resizeSection(c, widths[c])
        header.setSectionResizeMode(len(self.COLS) - 1, QHeaderView.Stretch)
        self.table.setRowCount(0)
        self.table.cellClicked.connect(self._on_row_select)
        root.addWidget(self.table)

        self.detail_panel = QFrame()
        self.detail_panel.setStyleSheet("QFrame { background: #0d1020; border: 1px solid #222; border-radius: 6px; }")
        self.detail_panel.setVisible(False)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(10, 8, 10, 8)
        detail_layout.setSpacing(4)

        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet("color: #f1c40f; font-size: 14px; font-weight: bold;")
        detail_layout.addWidget(self.detail_title)

        self.detail_info = QLabel("")
        self.detail_info.setStyleSheet("color: #aaa; font-size: 11px;")
        detail_layout.addWidget(self.detail_info)

        tables_layout = QHBoxLayout()
        tables_layout.setSpacing(10)

        buy_table_frame = QVBoxLayout()
        buy_lbl = QLabel("  ALIS FIYATLARI  ")
        buy_lbl.setStyleSheet("color: #f39c12; font-weight: bold; font-size: 11px; padding: 3px; background: #1a2a3e; border-radius: 3px;")
        buy_table_frame.addWidget(buy_lbl)
        self.detail_buy_table = QTableWidget()
        self.detail_buy_table.setStyleSheet("""
            QTableWidget { background: #0a0e18; color: #eee; border: 1px solid #1a1a2e; }
            QTableWidget::item { padding: 3px 4px; border: none; }
            QHeaderView::section {
                background: #111122; color: #f39c12; font-weight: bold; font-size: 10px;
                padding: 4px 3px; border-bottom: 1px solid #333; border-right: 1px solid #1a1a2e;
            }
        """)
        self.detail_buy_table.verticalHeader().setVisible(False)
        self.detail_buy_table.setShowGrid(False)
        self.detail_buy_table.setEditTriggers(QTableWidget.NoEditTriggers)
        buy_table_frame.addWidget(self.detail_buy_table)
        tables_layout.addLayout(buy_table_frame)

        sell_table_frame = QVBoxLayout()
        sell_lbl = QLabel("  SATIS FIYATLARI  ")
        sell_lbl.setStyleSheet("color: #3498db; font-weight: bold; font-size: 11px; padding: 3px; background: #1a2a3e; border-radius: 3px;")
        sell_table_frame.addWidget(sell_lbl)
        self.detail_sell_table = QTableWidget()
        self.detail_sell_table.setStyleSheet("""
            QTableWidget { background: #0a0e18; color: #eee; border: 1px solid #1a1a2e; }
            QTableWidget::item { padding: 3px 4px; border: none; }
            QHeaderView::section {
                background: #111122; color: #3498db; font-weight: bold; font-size: 10px;
                padding: 4px 3px; border-bottom: 1px solid #333; border-right: 1px solid #1a1a2e;
            }
        """)
        self.detail_sell_table.verticalHeader().setVisible(False)
        self.detail_sell_table.setShowGrid(False)
        self.detail_sell_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sell_table_frame.addWidget(self.detail_sell_table)
        tables_layout.addLayout(sell_table_frame)

        detail_layout.addLayout(tables_layout)

        self.detail_suggestion = QLabel("")
        self.detail_suggestion.setStyleSheet("color: #2ecc71; font-size: 12px; font-weight: bold; padding: 4px;")
        detail_layout.addWidget(self.detail_suggestion)

        root.addWidget(self.detail_panel)

        self._drag_pos = None
        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self._pre_max_geo = None

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            if self._pre_max_geo:
                self.setGeometry(self._pre_max_geo)
        else:
            self._pre_max_geo = self.geometry()
            self.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            edge_size = 8
            rect = self.rect()
            at_right = pos.x() > rect.width() - edge_size
            at_bottom = pos.y() > rect.height() - edge_size
            at_left = pos.x() < edge_size
            at_top = pos.y() < edge_size

            if at_right or at_bottom or at_left or at_top:
                self._resizing = True
                self._resize_edge = (at_right, at_bottom, at_left, at_top)
                self._drag_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                event.accept()
                return

            title_bar_rect = self.rect().adjusted(0, 0, 0, -self.rect().height() + 40)
            if title_bar_rect.contains(pos):
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_pos:
            diff = (event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()) - self._drag_pos
            self.move(self.pos() + diff)
            self._drag_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
            event.accept()
        elif self._resizing and self._drag_pos:
            global_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
            diff = global_pos - self._drag_pos
            geo = self.geometry()
            right, bottom, left, top = self._resize_edge
            if right:
                geo.setRight(geo.right() + diff.x())
            if bottom:
                geo.setBottom(geo.bottom() + diff.y())
            if left:
                geo.setLeft(geo.left() + diff.x())
            if top:
                geo.setTop(geo.top() + diff.y())
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            if geo.width() >= min_w and geo.height() >= min_h:
                self.setGeometry(geo)
            self._drag_pos = global_pos
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._resizing = False
        self._resize_edge = None
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            title_bar_rect = self.rect().adjusted(0, 0, 0, -self.rect().height() + 40)
            pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            if title_bar_rect.contains(pos):
                self._toggle_maximize()

    def _toggle_detail(self):
        if self.detail_panel.isVisible():
            self.detail_panel.setVisible(False)
        else:
            selected = self.table.selectionModel().selectedRows()
            if selected:
                self._show_detail(selected[0].row())
            else:
                self.detail_panel.setVisible(False)

    def _on_row_select(self, row, col):
        if self.detail_panel.isVisible() and row < len(self._items):
            self._show_detail(row)

    def _show_detail(self, row):
        if row < 0 or row >= len(self._items):
            self.detail_panel.setVisible(False)
            return

        item = self._items[row]
        filter_server = self.ptab._get_filtered_server()
        db_server = self.ptab._resolve_db_server(filter_server)
        db_lvl = "" if item["lvl"] in ["+0", "0"] else item["lvl"]

        stats = self.ptab.master.get_cached_stats(item["name"], db_lvl, server=db_server)
        if not stats:
            self.detail_panel.setVisible(False)
            return

        buy_price = item.get("buy_price", 0)
        sell_price = item.get("sell_price", 0)
        buy_strat = item.get("buy_strategy", "Manuel")
        sell_strat = item.get("sell_strategy", "Auto")
        count = item.get("count", 1)

        self.detail_title.setText(f"{item['name']}  {item['lvl']}  ({count} adet)")
        info_parts = []
        if buy_price > 0:
            info_parts.append(f"Secilen Alis: {buy_price:,.0f} ({buy_strat})")
        if sell_price > 0:
            info_parts.append(f"Secilen Satis: {sell_price:,.0f} ({sell_strat})")
        if buy_price > 0 and sell_price > 0:
            profit = (sell_price * 0.97) - buy_price
            pct = (profit / buy_price * 100) if buy_price else 0
            pc = "Kar" if profit > 0 else "Zarar"
            info_parts.append(f"Kar: {profit:,.0f} (%{pct:.1f}) - {pc}")
        self.detail_info.setText("  |  ".join(info_parts))

        group_servers = self.ptab._get_group_servers(filter_server) if filter_server.endswith("(Tumu)") else []
        if not group_servers:
            group_servers = self.ptab.SERVER_LIST

        stat_cols = ["Min", "Q1", "%95 Alt", "Medyan", "Mod", "%95 Ust", "Q3", "Max", "Secilen"]
        stat_keys = ["min", "q1", "ci_low", "median", "mode", "ci_high", "q3", "max"]
        headers = ["Sunucu"] + stat_cols

        for detail_table, price_key, label_fg in [
            (self.detail_buy_table, "buy", "#f39c12"),
            (self.detail_sell_table, "sell", "#3498db"),
        ]:
            detail_table.setColumnCount(len(headers))
            detail_table.setHorizontalHeaderLabels(headers)
            detail_table.setRowCount(len(group_servers) + 1)

            d_header = detail_table.horizontalHeader()
            for c in range(len(headers)):
                d_header.setSectionResizeMode(c, QHeaderView.Fixed)
                d_header.resizeSection(c, 100 if c == 0 else 78)
            d_header.setSectionResizeMode(len(headers) - 1, QHeaderView.Fixed)
            d_header.resizeSection(len(headers) - 1, 80)

        def _dcell(text, fg="#eee", bg="#0a0e18", bold=False, fs=9):
            c = QTableWidgetItem(str(text))
            c.setTextAlignment(Qt.AlignCenter)
            c.setFont(QFont("Consolas", fs, QFont.Bold if bold else QFont.Normal))
            c.setForeground(QColor(fg))
            c.setBackground(QColor(bg))
            return c

        all_buy_vals = []
        all_sell_vals = []
        server_data_cache = []
        for srv in group_servers:
            srv_stats = self.ptab.master.get_cached_stats(item["name"], db_lvl, server=srv)
            srv_buy = srv_stats.get("buy", {}) if srv_stats else {}
            srv_sell = srv_stats.get("sell", {}) if srv_stats else {}
            server_data_cache.append((srv, srv_buy, srv_sell))
            for k in stat_keys:
                bv = srv_buy.get(k, 0)
                sv = srv_sell.get(k, 0)
                if bv > 0:
                    all_buy_vals.append(bv)
                if sv > 0:
                    all_sell_vals.append(sv)

        for ri, (srv, srv_buy, srv_sell) in enumerate(server_data_cache):
            bg = "#111828" if ri % 2 == 0 else "#0c1118"

            self.detail_buy_table.setItem(ri, 0, _dcell(srv, "#f1c40f", bg, True, 9))
            for ci, key in enumerate(stat_keys):
                val = srv_buy.get(key, 0)
                gc = "#888"
                if self.ptab._guide_dialog and all_buy_vals:
                    gc, _ = self.ptab._guide_dialog._gradient_color(val, all_buy_vals, buy_mode=True, invert=(buy_strat == "Max %3 Vergi"))
                self.detail_buy_table.setItem(ri, ci + 1, _dcell(f"{val:,.0f}" if val > 0 else "-", gc, bg, False, 9))
            sel_buy_val = buy_price
            sel_buy_gc = "#f39c12"
            self.detail_buy_table.setItem(ri, len(stat_keys) + 1, _dcell(f"{sel_buy_val:,.0f}" if sel_buy_val > 0 else "-", sel_buy_gc, bg, True, 9))
            self.detail_buy_table.setRowHeight(ri, 24)

            self.detail_sell_table.setItem(ri, 0, _dcell(srv, "#f1c40f", bg, True, 9))
            for ci, key in enumerate(stat_keys):
                val = srv_sell.get(key, 0)
                gc = "#888"
                if self.ptab._guide_dialog and all_sell_vals:
                    gc, _ = self.ptab._guide_dialog._gradient_color(val, all_sell_vals, buy_mode=False, danger_below=buy_price)
                self.detail_sell_table.setItem(ri, ci + 1, _dcell(f"{val:,.0f}" if val > 0 else "-", gc, bg, False, 9))
            sel_sell_val = sell_price
            sel_sell_gc = "#3498db"
            self.detail_sell_table.setItem(ri, len(stat_keys) + 1, _dcell(f"{sel_sell_val:,.0f}" if sel_sell_val > 0 else "-", sel_sell_gc, bg, True, 9))
            self.detail_sell_table.setRowHeight(ri, 24)

        sel_bg = "#1a3a5c"
        sel_row = len(group_servers)
        self.detail_buy_table.setItem(sel_row, 0, _dcell("SECILEN", "#f1c40f", sel_bg, True, 9))
        for ci in range(len(stat_keys)):
            self.detail_buy_table.setItem(sel_row, ci + 1, _dcell("", "#888", sel_bg))
        self.detail_buy_table.setItem(sel_row, len(stat_keys) + 1, _dcell(f"{buy_price:,.0f}" if buy_price > 0 else "-", "#f39c12", sel_bg, True, 9))
        self.detail_buy_table.setRowHeight(sel_row, 26)

        self.detail_sell_table.setItem(sel_row, 0, _dcell("SECILEN", "#f1c40f", sel_bg, True, 9))
        for ci in range(len(stat_keys)):
            self.detail_sell_table.setItem(sel_row, ci + 1, _dcell("", "#888", sel_bg))
        self.detail_sell_table.setItem(sel_row, len(stat_keys) + 1, _dcell(f"{sell_price:,.0f}" if sell_price > 0 else "-", "#3498db", sel_bg, True, 9))
        self.detail_sell_table.setRowHeight(sel_row, 26)

        suggestions = []
        if buy_price > 0 and sell_price > 0:
            profit = (sell_price * 0.97) - buy_price
            if profit > 0:
                pct = (profit / buy_price * 100)
                suggestions.append(f"Karli: %{pct:.1f} kâr marjini")
            else:
                suggestions.append(f"Zararli: %{abs(profit/buy_price*100):.1f} zarar")
        if buy_price > 0 and stats.get("buy", {}).get("median", 0) > 0:
            diff = abs(buy_price - stats["buy"]["median"]) / stats["buy"]["median"] * 100
            if diff <= 5:
                suggestions.append("Alis fiyati guvenli (Medyana yakin)")
            elif diff <= 15:
                suggestions.append(f"Alis fiyati supheli (Medyandan %{diff:.1f} fark)")
            else:
                suggestions.append(f"Alis fiyati manipule edilmis olabilir (Medyandan %{diff:.1f} fark)")
        if sell_price > 0 and buy_price > 0 and sell_price < buy_price:
            suggestions.append("Satis fiyati alis fiyatindan dusuk - zarar!")

        self.detail_suggestion.setText("  |  ".join(suggestions) if suggestions else "")
        sc = "#2ecc71" if not any("zarar" in s.lower() for s in suggestions) else "#e74c3c"
        self.detail_suggestion.setStyleSheet(f"color: {sc}; font-size: 11px; font-weight: bold; padding: 4px;")

        self.detail_panel.setVisible(True)

    def _on_search(self, text):
        self._search_term = text.strip().lower()
        self.refresh()

    def refresh(self):
        try:
            filter_server = self.ptab._get_filtered_server()
            db_server = self.ptab._resolve_db_server(filter_server)
            self.table.setRowCount(0)
            self._items = []

            for item in self.ptab.portfolio:
                if not self.ptab._item_matches_filter(item, filter_server):
                    continue
                if self._search_term and self._search_term not in item["name"].lower():
                    continue
                self._items.append(item)

            self.table.setRowCount(len(self._items))

            total_cost = 0
            total_revenue = 0
            total_profit = 0

            for row, item in enumerate(self._items):
                db_lvl = "" if item["lvl"] in ["+0", "0"] else item["lvl"]
                stats = self.ptab.master.get_cached_stats(item["name"], db_lvl, server=db_server)
                buy_price = item.get("buy_price", 0)
                buy_strat = item.get("buy_strategy", "Manuel")
                sell_strat = item.get("sell_strategy", "Auto")
                count = item.get("count", 1)

                sell_price = 0
                if stats and stats.get('sell'):
                    if sell_strat == "Auto":
                        sell_price, _, _ = self.ptab.master.calculate_auto_sell(stats, buy_price)
                    else:
                        s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
                        sell_price = stats['sell'].get(s_map.get(sell_strat, "median"), 0)

                net_sell = sell_price * 0.97 if sell_price > 0 else 0
                profit = (net_sell - buy_price) * count if buy_price > 0 and net_sell > 0 else 0
                profit_pct = ((net_sell / buy_price - 1) * 100) if buy_price > 0 and net_sell > 0 else 0
                cost = buy_price * count
                net_kasa = net_sell * count

                total_cost += cost
                total_revenue += net_kasa
                total_profit += profit

                bg = "#0e1220" if row % 2 == 0 else "#0a0e16"

                def _cell(text, fg="#eee", font_size=10, bold=False, bg_c=bg):
                    c = QTableWidgetItem(str(text))
                    c.setTextAlignment(Qt.AlignCenter)
                    f = QFont("Consolas", font_size, QFont.Bold if bold else QFont.Normal)
                    c.setFont(f)
                    c.setForeground(QColor(fg))
                    c.setBackground(QColor(bg_c))
                    return c

                self.table.setItem(row, 0, _cell(item['name'], "#f1c40f", 10, True))
                self.table.setItem(row, 1, _cell(item['lvl'], "#888"))
                self.table.setItem(row, 2, _cell(count, "#aaa"))
                self.table.setItem(row, 3, _cell(f"{buy_price:,.0f}" if buy_price > 0 else "-", "#f39c12", 10, True))
                self.table.setItem(row, 4, _cell(buy_strat, "#f39c12"))

                sell_fg = "#2ecc71" if net_sell > buy_price else ("#e74c3c" if net_sell > 0 and net_sell < buy_price else "#888")
                self.table.setItem(row, 5, _cell(f"{sell_price:,.0f}" if sell_price > 0 else "-", sell_fg, 10, True))
                self.table.setItem(row, 6, _cell(sell_strat, "#3498db"))

                kar_fg = "#2ecc71" if profit > 0 else "#e74c3c"
                self.table.setItem(row, 7, _cell(f"{profit:,.0f}" if profit != 0 else "-", kar_fg, 10, True))
                self.table.setItem(row, 8, _cell(f"%{profit_pct:.1f}" if profit_pct != 0 else "-", kar_fg, 9, True))

                if profit > 0:
                    durum = "KAR"
                    durum_fg = "#2ecc71"
                elif profit < 0:
                    durum = "ZARAR"
                    durum_fg = "#e74c3c"
                else:
                    durum = "-"
                    durum_fg = "#888"
                self.table.setItem(row, 9, _cell(durum, durum_fg, 10, True))

                self.table.setItem(row, 10, _cell(f"{cost:,.0f}" if cost > 0 else "-", "#f39c12"))
                self.table.setItem(row, 11, _cell(f"{net_kasa:,.0f}" if net_kasa > 0 else "-", "#2ecc71"))

                self.table.setRowHeight(row, 30)

            total_profit_pct = ((total_revenue / total_cost - 1) * 100) if total_cost > 0 and total_revenue > 0 else 0
            tp_fg = "#2ecc71" if total_profit > 0 else "#e74c3c"
            self.total_lbl.setText(
                f"Toplam: {len(self._items)} item  |  Maliyet: {total_cost:,.0f}  |  Net Kasa: {total_revenue:,.0f}  |  "
                f"Kar: {total_profit:,.0f}  (%{total_profit_pct:.1f})"
            )
            self.total_lbl.setStyleSheet(f"color: {tp_fg}; font-size: 13px; font-weight: bold;")

            if self.detail_panel.isVisible():
                selected = self.table.selectionModel().selectedRows()
                if selected:
                    self._show_detail(selected[0].row())
                else:
                    self.detail_panel.setVisible(False)

        except Exception:
            pass

    def _export(self):
        self.ptab.export_portfolio_excel()


class PriceListDialog(QDialog):
    COLS = ["Item", "Lvl", "Adet", "Alis", "Alis Stratejisi", "Satis", "Satis Stratejisi", "Kar", "Kar %", "Durum"]

    def __init__(self, portfolio_tab, parent=None):
        super().__init__(parent)
        self.ptab = portfolio_tab
        self.setWindowTitle("Fiyat Listesi")
        self.setMinimumSize(1100, 600)
        self.resize(1300, 700)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QDialog {
                background: #0c0e1a;
                color: #eee;
                border: 1px solid #1e2a3a;
                border-radius: 10px;
            }
        """)
        self._items = []
        self._sorted_items = []
        self._page_size = 25
        self._page = 0
        self._sort_col = -1
        self._sort_asc = True
        self._search_term = ""

        root = QVBoxLayout(self)
        root.setSpacing(4)
        root.setContentsMargins(10, 10, 10, 10)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(6, 4, 6, 4)
        drag_area = QLabel("  FIYAT LISTESI")
        drag_area.setStyleSheet("color: #f1c40f; font-size: 15px; font-weight: bold; letter-spacing: 2px; background: transparent;")
        title_bar.addWidget(drag_area)
        title_bar.addStretch()
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color: #aaa; font-size: 12px; background: transparent;")
        title_bar.addWidget(self.count_lbl)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Item ara...")
        self.search_entry.setFixedWidth(180)
        self.search_entry.setStyleSheet("""
            QLineEdit {
                background: #111828; color: #eee; border: 1px solid #2a3a4a;
                border-radius: 5px; padding: 6px 10px; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #f39c12; }
        """)
        self.search_entry.textChanged.connect(self._on_search)
        title_bar.addWidget(self.search_entry)

        self.size_combo = QComboBox()
        self.size_combo.addItems(["25", "50", "100"])
        self.size_combo.setCurrentText("25")
        self.size_combo.setFixedWidth(60)
        self.size_combo.setStyleSheet("background:#111828; color:#f1c40f; border:1px solid #2a3a4a; border-radius:5px; padding:4px; font-weight:bold; font-size:11px;")
        self.size_combo.currentTextChanged.connect(self._on_size_change)
        title_bar.addWidget(QLabel("  Satir:"))
        title_bar.addWidget(self.size_combo)

        btn_refresh = QPushButton("Yenile")
        btn_refresh.setFixedSize(70, 30)
        btn_refresh.setStyleSheet("QPushButton { background:#1a2a3e; color:#f39c12; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:11px; } QPushButton:hover { background:#1e3348; }")
        btn_refresh.clicked.connect(self.refresh)
        title_bar.addWidget(btn_refresh)

        btn_export = QPushButton("Excel")
        btn_export.setFixedSize(60, 30)
        btn_export.setStyleSheet("QPushButton { background:#1a2a3e; color:#3498db; border:1px solid #2a3a4a; border-radius:5px; font-weight:bold; font-size:11px; } QPushButton:hover { background:#1e3348; }")
        btn_export.clicked.connect(self._export)
        title_bar.addWidget(btn_export)

        btn_close = QPushButton("X")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("QPushButton { background:#3a1a1a; color:#e74c3c; border:1px solid #4a2a2a; border-radius:5px; font-weight:bold; font-size:12px; } QPushButton:hover { background:#4a2020; }")
        btn_close.clicked.connect(self.close)
        title_bar.addWidget(btn_close)

        root.addLayout(title_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setStyleSheet("""
            QTableWidget { background: #0a0a14; color: #eee; border: 1px solid #1a1a2e; }
            QTableWidget::item { padding: 3px 4px; border: none; }
            QTableWidget::item:selected { background: #1a3a5c; }
            QTableWidget::alternate { background: #0e1220; }
            QHeaderView::section {
                background: #111122; color: #f1c40f; font-weight: bold; font-size: 11px;
                padding: 5px 4px; border-bottom: 1px solid #333; border-right: 1px solid #1a1a2e;
                cursor: pointer;
            }
            QHeaderView::section:hover { background: #1a1a3e; }
        """)
        self.table.horizontalHeader().sectionClicked.connect(self._on_sort)
        root.addWidget(self.table)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.prev_btn = QPushButton("<< Onceki")
        self.prev_btn.setStyleSheet("QPushButton { background:#34495e; color:white; border:none; border-radius:4px; padding:6px 14px; font-weight:bold; } QPushButton:hover { background:#4a6a8a; } QPushButton:disabled { background:#222; color:#555; }")
        self.prev_btn.clicked.connect(self._prev_page)
        footer.addWidget(self.prev_btn)
        self.page_lbl = QLabel("")
        self.page_lbl.setStyleSheet("color:#f1c40f; font-weight:bold; font-size:12px; padding:0 10px;")
        footer.addWidget(self.page_lbl)
        self.next_btn = QPushButton("Sonraki >>")
        self.next_btn.setStyleSheet("QPushButton { background:#34495e; color:white; border:none; border-radius:4px; padding:6px 14px; font-weight:bold; } QPushButton:hover { background:#4a6a8a; } QPushButton:disabled { background:#222; color:#555; }")
        self.next_btn.clicked.connect(self._next_page)
        footer.addWidget(self.next_btn)
        footer.addStretch()
        self.total_lbl = QLabel("")
        self.total_lbl.setStyleSheet("color:#2ecc71; font-size:12px; font-weight:bold;")
        footer.addWidget(self.total_lbl)
        root.addLayout(footer)

    def _on_search(self, text):
        self._search_term = text.strip().lower()
        self._apply_search_filter()
        self._page = 0
        self._render_page()

    def _apply_search_filter(self):
        if not self._search_term:
            self._items = list(self.ptab.portfolio) if hasattr(self.ptab, 'portfolio') else []
        else:
            all_items = list(self.ptab.portfolio) if hasattr(self.ptab, 'portfolio') else []
            self._items = [i for i in all_items if self._search_term in i.get("name", "").lower()]

    def refresh(self):
        self._apply_search_filter()
        self._page = 0
        self._sort_col = -1
        self._sort_asc = True
        self._apply_sort()
        self._render_page()

    def _apply_sort(self):
        if self._sort_col < 0:
            self._sorted_items = list(self._items)
            return
        col = self._sort_col
        key_map = {
            0: lambda x: x.get("name", ""),
            1: lambda x: x.get("lvl", ""),
            2: lambda x: x.get("count", 0),
            3: lambda x: x.get("buy_price", 0),
            4: lambda x: x.get("buy_strategy", ""),
            5: lambda x: x.get("sell_price", 0),
            6: lambda x: x.get("sell_strategy", ""),
            7: lambda x: (x.get("sell_price", 0) * 0.97 - x.get("buy_price", 0)) if x.get("buy_price", 0) > 0 and x.get("sell_price", 0) > 0 else -999999,
            8: lambda x: ((x.get("sell_price", 0) * 0.97 - x.get("buy_price", 0)) / x.get("buy_price", 1) * 100) if x.get("buy_price", 0) > 0 and x.get("sell_price", 0) > 0 else -999999,
            9: lambda x: (
                "Kar" if x.get("sell_price", 0) > 0 and x.get("buy_price", 0) > 0 and (x.get("sell_price", 0) * 0.97 - x.get("buy_price", 0)) > 0
                else "Zarar" if x.get("sell_price", 0) > 0 and x.get("buy_price", 0) > 0
                else "-"
            ),
        }
        key_fn = key_map.get(col, lambda x: "")
        try:
            self._sorted_items = sorted(self._items, key=key_fn, reverse=not self._sort_asc)
        except Exception:
            self._sorted_items = list(self._items)

    def _on_sort(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._apply_sort()
        self._render_page()

    def _on_size_change(self, text):
        try:
            self._page_size = int(text)
        except ValueError:
            self._page_size = 25
        self._page = 0
        self._render_page()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def _next_page(self):
        total_pages = max(1, (len(self._sorted_items) + self._page_size - 1) // self._page_size)
        if self._page < total_pages - 1:
            self._page += 1
            self._render_page()

    def _render_page(self):
        total = len(self._sorted_items)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        if self._page >= total_pages:
            self._page = total_pages - 1
        start = self._page * self._page_size
        end = min(start + self._page_size, total)
        page_items = self._sorted_items[start:end]

        self.table.setRowCount(len(page_items))
        self.table.setSortingEnabled(False)

        total_cost = 0
        total_net = 0

        for ri, item in enumerate(page_items):
            bg = "#0e1220" if ri % 2 == 0 else "#0a0e18"
            name = item.get("name", "")
            lvl = item.get("lvl", "")
            count = item.get("count", 1)
            buy_p = item.get("buy_price", 0)
            buy_s = item.get("buy_strategy", "Manuel")
            sell_p = item.get("sell_price", 0)
            sell_s = item.get("sell_strategy", "Auto")

            kar = (sell_p * 0.97 - buy_p) if buy_p > 0 and sell_p > 0 else 0
            kar_pct = (kar / buy_p * 100) if buy_p > 0 else 0
            cost = buy_p * count
            total_cost += cost
            total_net += sell_p * count if sell_p > 0 else cost

            if kar > 0:
                durum, durum_fg = "Karli", "#2ecc71"
            elif kar < 0:
                durum, durum_fg = "Zarar", "#e74c3c"
            else:
                durum, durum_fg = "-", "#888"

            kar_fg = "#2ecc71" if kar > 0 else ("#e74c3c" if kar < 0 else "#888")

            vals = [
                (name, "#eee", True),
                (lvl, "#f1c40f", False),
                (str(count), "#aaa", False),
                (f"{buy_p:,.0f}" if buy_p > 0 else "-", "#f39c12", False),
                (buy_s, "#aaa", False),
                (f"{sell_p:,.0f}" if sell_p > 0 else "-", "#3498db", False),
                (sell_s, "#aaa", False),
                (f"{kar:,.0f}" if kar != 0 else "-", kar_fg, False),
                (f"%{kar_pct:.1f}" if kar != 0 else "-", kar_fg, False),
                (durum, durum_fg, True),
            ]

            for ci, (val, fg, bold) in enumerate(vals):
                c = QTableWidgetItem(val)
                c.setTextAlignment(Qt.AlignCenter)
                c.setFont(QFont("Consolas", 9, QFont.Bold if bold else QFont.Normal))
                c.setForeground(QColor(fg))
                c.setBackground(QColor(bg))
                self.table.setItem(ri, ci, c)

            self.table.setRowHeight(ri, 26)

        self.table.setSortingEnabled(True)

        self.count_lbl.setText(f"{total} item")
        self.page_lbl.setText(f"Sayfa {self._page + 1} / {total_pages}  (Gosterilen: {start + 1}-{end})")
        self.total_lbl.setText(f"Toplam Maliyet: {total_cost:,.0f}  |  Net Kasa: {total_net:,.0f}  |  Kar: {total_net - total_cost:,.0f}")
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)

    def _export(self):
        self.ptab.export_portfolio_excel()


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
        self.port_buy_status = QLabel("--"); self.port_buy_status.setFixedWidth(110); self.port_buy_status.setStyleSheet("font-size:10px; padding:2px; color:#888; background:#222; border-radius:3px;"); top.addWidget(self.port_buy_status)
        self.port_buy_entry = QLineEdit(); self.port_buy_entry.setPlaceholderText("Manuel"); self.port_buy_entry.setFixedWidth(60)
        top.addWidget(self.port_buy_entry)
        top.addWidget(QLabel("Satis:"))
        sell_strategies = ["Auto", "Kar Odaklı", "Spread Filtreli", "Min-Max Rastgele", "Otonom", "Min", "Q1", "Medyan", "Mod", "Q3", "Max", "%95 Alt", "%95 Ust", "Manuel"]
        self.port_sell_strat_combo = QComboBox(); self.port_sell_strat_combo.addItems(sell_strategies); self.port_sell_strat_combo.setCurrentText("Auto"); self.port_sell_strat_combo.setFixedWidth(100)
        top.addWidget(self.port_sell_strat_combo)
        self.port_sell_status = QLabel("--"); self.port_sell_status.setFixedWidth(110); self.port_sell_status.setStyleSheet("font-size:10px; padding:2px; color:#888; background:#222; border-radius:3px;"); top.addWidget(self.port_sell_status)
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
        b = QPushButton("Rehber"); b.setStyleSheet(f"background:#8e44ad; color:white; {btn_style}"); b.clicked.connect(self._open_guide); actions.addWidget(b)
        b = QPushButton("Rehber 2"); b.setStyleSheet(f"background:#6c3483; color:white; {btn_style}"); b.clicked.connect(self._open_excel_preview); actions.addWidget(b)
        b = QPushButton("Fiyat Listesi"); b.setStyleSheet(f"background:#e67e22; color:white; {btn_style}"); b.clicked.connect(self._open_price_list); actions.addWidget(b)
        b = QPushButton("Fiyatlari Yenile"); b.setStyleSheet(f"background:#f39c12; color:white; {btn_style}"); b.clicked.connect(self._refresh_all_windows); actions.addWidget(b)
        actions.addSpacing(10)
        actions.addWidget(QLabel("Liste:"))
        self.saved_list_combo = QComboBox(); self.saved_list_combo.setFixedWidth(180); self._refresh_saved_lists(); actions.addWidget(self.saved_list_combo)
        b = QPushButton("Yukle"); b.setStyleSheet(f"background:#8e44ad; color:white; {btn_sm}"); b.clicked.connect(self._load_selected_list); actions.addWidget(b)
        b = QPushButton("Kaydet"); b.setStyleSheet(f"background:#e67e22; color:white; {btn_sm}"); b.clicked.connect(self._save_as_new_list); actions.addWidget(b)
        b = QPushButton("Sil"); b.setStyleSheet(f"background:#e74c3c; color:white; {btn_sm}"); b.clicked.connect(self._delete_selected_list); actions.addWidget(b)
        actions.addStretch()
        layout.addLayout(actions)

        settings_row = QHBoxLayout(); settings_row.setSpacing(6)
        settings_row.addWidget(QLabel("Makas:"))
        self.spread_lower = QLineEdit("49"); self.spread_lower.setFixedWidth(35)
        settings_row.addWidget(self.spread_lower)
        settings_row.addWidget(QLabel("/"))
        self.spread_upper = QLineEdit("51"); self.spread_upper.setFixedWidth(35)
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
        self.bulk_buy_status = QLabel("--"); self.bulk_buy_status.setFixedWidth(90); self.bulk_buy_status.setStyleSheet("font-size:10px; padding:2px; color:#888; background:#222; border-radius:3px;"); bulk1.addWidget(self.bulk_buy_status)
        self.bulk_buy_entry = QLineEdit(); self.bulk_buy_entry.setPlaceholderText("Manuel"); self.bulk_buy_entry.setFixedWidth(60)
        bulk1.addWidget(self.bulk_buy_entry)
        b = QPushButton("Secili"); b.setStyleSheet(f"background:#8e44ad; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_bulk_logic("buy", False)); bulk1.addWidget(b)
        b = QPushButton("Tumu"); b.setStyleSheet(f"background:#9b59b6; color:white; {btn_sm}"); b.clicked.connect(lambda: self.apply_bulk_logic("buy", True)); bulk1.addWidget(b)
        bulk1.addWidget(QLabel("Kar%:"))
        self.entry_buy_margin = QLineEdit("20"); self.entry_buy_margin.setFixedWidth(40); bulk1.addWidget(self.entry_buy_margin)
        bulk1.addWidget(QLabel("Satis:"))
        self.bulk_sell_combo = QComboBox(); self.bulk_sell_combo.addItems(sell_strategies); self.bulk_sell_combo.setCurrentText("Auto"); self.bulk_sell_combo.setFixedWidth(80)
        bulk1.addWidget(self.bulk_sell_combo)
        self.bulk_sell_status = QLabel("--"); self.bulk_sell_status.setFixedWidth(90); self.bulk_sell_status.setStyleSheet("font-size:10px; padding:2px; color:#888; background:#222; border-radius:3px;"); bulk1.addWidget(self.bulk_sell_status)
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

        self.port_buy_strat_combo.currentTextChanged.connect(lambda: self._update_strategy_status("buy"))
        self.port_sell_strat_combo.currentTextChanged.connect(lambda: self._update_strategy_status("sell"))
        self.bulk_buy_combo.currentTextChanged.connect(lambda: self._update_strategy_status("bulk_buy"))
        self.bulk_sell_combo.currentTextChanged.connect(lambda: self._update_strategy_status("bulk_sell"))
        self.port_item_combo.itemSelected.connect(lambda: self._update_all_strategy_status())

        self.table = QTableWidget()
        self.table.setColumnCount(15)
        self.table.setHorizontalHeaderLabels([
            "Item", "Lvl", "Adet", "Alis Fiyati", "Alis Stratejisi", "Top. Maliyet",
            "Satis Fiyati", "Satis Stratejisi", "Beklenen Kar", "Durum",
            "Alis Sabit", "Satis Sabit", "Sunucu",
            "Gecmis Dusuk", "Gecmis Yuksek"
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

        self._guide_dialog = None
        self._excel_preview_dialog = None
        self._price_list_dialog = None
        self._saved_list_map = {}

        self._auto_refresh_timer = None
        self._start_auto_refresh()

        self.render_portfolio_ui()
        self._update_all_strategy_status()

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

    def _is_manipulated(self, target_price, server_price, threshold_pct=3.0):
        if target_price <= 0 or server_price <= 0:
            return False
        threshold = target_price * (threshold_pct / 100)
        return server_price < (target_price - threshold)

    def _get_price_color(self, target_price, server_price):
        if target_price <= 0 or server_price <= 0:
            return None, 0
        diff_pct = abs(server_price - target_price) / target_price * 100
        if diff_pct <= 3:
            return QColor(0x2e, 0xcc, 0x71), diff_pct
        elif diff_pct <= 10:
            return QColor(0xf3, 0x9c, 0x12), diff_pct
        else:
            return QColor(0xe7, 0x4c, 0x3c), diff_pct

    def _detect_manipulation(self, server_prices):
        if len(server_prices) < 2:
            return {}
        prices = [p for p in server_prices.values() if p > 0]
        if not prices:
            return {}
        prices_sorted = sorted(prices)
        n = len(prices_sorted)
        if n % 2 == 0:
            median = (prices_sorted[n//2 - 1] + prices_sorted[n//2]) / 2
        else:
            median = prices_sorted[n//2]
        result = {}
        for srv, price in server_prices.items():
            if price <= 0:
                result[srv] = (None, 0, "")
                continue
            diff_pct = abs(price - median) / median * 100 if median > 0 else 0
            if diff_pct <= 5:
                color = QColor(0x2e, 0xcc, 0x71)
                label = "Normal"
            elif diff_pct <= 15:
                color = QColor(0xf3, 0x9c, 0x12)
                label = "Şüpheli"
            else:
                color = QColor(0xe7, 0x4c, 0x3c)
                label = "Manipüle"
            result[srv] = (color, diff_pct, label)
        return result

    def _detect_price_spike(self, item_name, item_lvl, server, current_price, minutes=10, threshold=20):
        if current_price <= 0:
            return None, 0, ""
        cache_key = f"{item_name}|{item_lvl}|{server}|{current_price}"
        if hasattr(self, '_spike_cache') and cache_key in self._spike_cache:
            return self._spike_cache[cache_key]
        try:
            from webapp.database import get_price_history
            recent = get_price_history(item_name, item_lvl, server=server, minutes=minutes, limit=10)
            if len(recent) < 2:
                result = (None, 0, "")
                if hasattr(self, '_spike_cache'):
                    self._spike_cache[cache_key] = result
                return result
            recent_prices = [r['price'] for r in recent if r['price'] and r['price'] > 0]
            if len(recent_prices) < 2:
                result = (None, 0, "")
                if hasattr(self, '_spike_cache'):
                    self._spike_cache[cache_key] = result
                return result
            old_avg = sum(recent_prices[1:]) / len(recent_prices[1:])
            if old_avg <= 0:
                result = (None, 0, "")
                if hasattr(self, '_spike_cache'):
                    self._spike_cache[cache_key] = result
                return result
            change_pct = (current_price - old_avg) / old_avg * 100
            if abs(change_pct) <= threshold * 0.5:
                color = QColor(0x2e, 0xcc, 0x71)
                label = "Stabil"
            elif abs(change_pct) <= threshold:
                color = QColor(0xf3, 0x9c, 0x12)
                label = "Değişim"
            else:
                color = QColor(0xe7, 0x4c, 0x3c)
                label = "Ani Değişim"
            result = (color, change_pct, label)
            if hasattr(self, '_spike_cache'):
                self._spike_cache[cache_key] = result
            return result
        except Exception:
            result = (None, 0, "")
            if hasattr(self, '_spike_cache'):
                self._spike_cache[cache_key] = result
            return result

    def _get_group_servers(self, filter_server):
        if not filter_server or not filter_server.endswith("(Tumu)"):
            return []
        base = filter_server.replace(" (Tumu)", "")
        return [s for s in self.SERVER_LIST if s.startswith(base + " ")]

    def _calc_strategy_price(self, item_name, item_lvl, strategy, price_type="buy", stats=None, spread_lower=None, spread_upper=None, current_buy_price=None):
        if not stats:
            return 0
        s_map = {"Min": "min", "Q1": "q1", "Medyan": "median", "Mod": "mode", "Q3": "q3", "Max": "max", "%95 Alt": "ci_low", "%95 Ust": "ci_high"}
        data = stats.get(price_type, {})
        if not data:
            return 0
        if strategy in ("Manuel",):
            return current_buy_price if current_buy_price is not None else 0
        elif strategy == "Auto":
            if price_type == "buy":
                raw = stats.get('buy_raw')
                if raw is not None and not raw.empty:
                    return float(np.percentile(raw, 49))
                return data.get("q1", 0)
            else:
                raw = stats.get('sell_raw')
                if raw is not None and not raw.empty:
                    return float(np.percentile(raw, 51))
                return data.get("q3", 0)
        elif strategy == "Kar Odaklı":
            if price_type == "buy":
                b, s = stats.get("buy", {}), stats.get("sell", {})
                best = -999999999
                bp = 0
                for mk, mv in [("min", b.get("min",0)), ("Q1", b.get("q1",0)), ("Medyan", b.get("median",0)), ("Mod", b.get("mode",0)), ("Q3", b.get("q3",0)), ("Max", b.get("max",0)), ("%95 Alt", b.get("ci_low",0)), ("%95 Ust", b.get("ci_high",0))]:
                    if mv <= 0: continue
                    p = (s.get("q3", 0) * 0.97) - mv
                    if p > best: best = p; bp = mv
                return bp
            else:
                b, s = stats.get("buy", {}), stats.get("sell", {})
                best = -999999999
                bp = 0
                buy_p = current_buy_price if current_buy_price is not None else b.get("min", 0)
                for mk, mv in [("min", s.get("min",0)), ("Q1", s.get("q1",0)), ("Medyan", s.get("median",0)), ("Mod", s.get("mode",0)), ("Q3", s.get("q3",0)), ("Max", s.get("max",0)), ("%95 Alt", s.get("ci_low",0)), ("%95 Ust", s.get("ci_high",0))]:
                    if mv <= 0: continue
                    p = (mv * 0.97) - buy_p
                    if p > best: best = p; bp = mv
                return bp
        elif strategy == "Spread Filtreli":
            raw = stats.get(f'{price_type}_raw')
            if raw is not None and not raw.empty:
                if price_type == "buy":
                    pct = float(spread_lower) if spread_lower is not None else 49.0
                else:
                    pct = float(spread_upper) if spread_upper is not None else 51.0
                return float(np.percentile(raw, pct))
            return data.get("q1" if price_type == "buy" else "q3", 0)
        elif strategy == "Min-Max Ortasi":
            return (data.get("min", 0) + data.get("max", 0)) / 2
        elif strategy == "Min-Max Rastgele":
            import random
            b_min = data.get("min", 0)
            b_max = data.get("max", 0)
            if b_min > 0 and b_max > b_min:
                return random.randint(int(b_min), int(b_max))
            return b_min
        elif strategy == "Otonom":
            if price_type == "buy":
                if data.get("min", 0) > 0 and data.get("q1", 0) > data.get("min", 0):
                    return data.get("q1", 0)
                elif data.get("min", 0) > 0:
                    return data.get("min", 0)
                return 0
            else:
                if data.get("max", 0) > 0 and data.get("q3", 0) < data.get("max", 0):
                    return data.get("q3", 0)
                elif data.get("max", 0) > 0:
                    return data.get("max", 0)
                return 0
        elif strategy in ("Min*0.97+%Kar", "Q1*0.97+%Kar", "%95 Alt*0.97+%Kar") and price_type == "buy":
            key_map = {"Min*0.97+%Kar": "min", "Q1*0.97+%Kar": "q1", "%95 Alt*0.97+%Kar": "ci_low"}
            base = stats.get("sell", {}).get(key_map[strategy], 0)
            try:
                margin = float(self.entry_buy_margin.text().strip())
            except: margin = 0
            return base * 0.97 / (1 + margin / 100)
        elif strategy == "Max %3 Vergi" and price_type == "buy":
            return data.get("max", 0) * 0.97
        elif strategy == "%95 Ust":
            val = data.get("ci_high", 0)
            if val <= 0:
                return data.get("max", 0) * 0.95
            return val
        elif strategy in s_map:
            return data.get(s_map[strategy], 0)
        elif "%" in str(strategy) and price_type == "sell":
            try:
                profit_margin = float(strategy.replace("%", "").strip())
                bp = current_buy_price if current_buy_price is not None else 0
                return (bp * (1 + (profit_margin / 100))) / 0.97
            except ValueError:
                bp = current_buy_price if current_buy_price is not None else 0
                return bp * 1.10
        return 0

    def _get_price_safety(self, price, server_prices):
        if price <= 0 or not server_prices:
            return None, 0, ""
        valid = [p for p in server_prices.values() if p > 0]
        if not valid:
            return None, 0, ""
        valid_sorted = sorted(valid)
        n = len(valid_sorted)
        median = (valid_sorted[n//2 - 1] + valid_sorted[n//2]) / 2 if n % 2 == 0 else valid_sorted[n//2]
        if median <= 0:
            return None, 0, ""
        diff_pct = abs(price - median) / median * 100
        if diff_pct <= 5:
            return QColor(0x2e, 0xcc, 0x71), diff_pct, "Güvenli"
        elif diff_pct <= 15:
            return QColor(0xf3, 0x9c, 0x12), diff_pct, "Şüpheli"
        else:
            return QColor(0xe7, 0x4c, 0x3c), diff_pct, "Manipüle"

    def _update_strategy_status(self, mode="buy"):
        try:
            item_name = self.port_item_combo.get() if hasattr(self, 'port_item_combo') else ""
            item_lvl = self.port_lvl_combo.currentText() if hasattr(self, 'port_lvl_combo') else "+0"
            if not item_name:
                return
            db_lvl = "" if item_lvl in ["+0", "0"] else item_lvl
            filter_server = self._get_filtered_server()
            group_servers = self._get_group_servers(filter_server)
            all_servers = group_servers if group_servers else ([self._resolve_db_server(filter_server)] if self._resolve_db_server(filter_server) else [])

            srv_prices = {}
            for srv in all_servers:
                stats = self.master.get_cached_stats(item_name, db_lvl, server=srv)
                if stats:
                    srv_prices[srv] = stats.get("buy", {}).get("median", 0) or stats.get("sell", {}).get("median", 0)

            if mode == "buy":
                strat = self.port_buy_strat_combo.currentText()
                stats = self.master.get_cached_stats(item_name, db_lvl, server=self._resolve_db_server(filter_server))
                price = self._calc_strategy_price(item_name, db_lvl, strat, "buy", stats)
                color, diff, label = self._get_price_safety(price, srv_prices)
                if color:
                    self.port_buy_status.setStyleSheet(f"color: {color.name()}; font-size:10px; font-weight:bold; padding:2px; background:#222; border-radius:3px;")
                    self.port_buy_status.setText(f"{label} (%{diff:.1f})")
                else:
                    self.port_buy_status.setStyleSheet("color: #888; font-size:10px; padding:2px; background:#222; border-radius:3px;")
                    self.port_buy_status.setText("Veri yok")
                self._update_price_guide(item_name, item_lvl, strat, "buy", stats, srv_prices)
            elif mode == "sell":
                strat = self.port_sell_strat_combo.currentText()
                stats = self.master.get_cached_stats(item_name, db_lvl, server=self._resolve_db_server(filter_server))
                price = self._calc_strategy_price(item_name, db_lvl, strat, "sell", stats)
                color, diff, label = self._get_price_safety(price, srv_prices)
                if color:
                    self.port_sell_status.setStyleSheet(f"color: {color.name()}; font-size:10px; font-weight:bold; padding:2px; background:#222; border-radius:3px;")
                    self.port_sell_status.setText(f"{label} (%{diff:.1f})")
                else:
                    self.port_sell_status.setStyleSheet("color: #888; font-size:10px; padding:2px; background:#222; border-radius:3px;")
                    self.port_sell_status.setText("Veri yok")
                self._update_price_guide(item_name, item_lvl, strat, "sell", stats, srv_prices)
            elif mode == "bulk_buy":
                strat = self.bulk_buy_combo.currentText()
                stats = self.master.get_cached_stats(item_name, db_lvl, server=self._resolve_db_server(filter_server))
                price = self._calc_strategy_price(item_name, db_lvl, strat, "buy", stats)
                color, diff, label = self._get_price_safety(price, srv_prices)
                if color:
                    self.bulk_buy_status.setStyleSheet(f"color: {color.name()}; font-size:10px; font-weight:bold; padding:2px; background:#222; border-radius:3px;")
                    self.bulk_buy_status.setText(f"{label} (%{diff:.1f})")
                else:
                    self.bulk_buy_status.setStyleSheet("color: #888; font-size:10px; padding:2px; background:#222; border-radius:3px;")
                    self.bulk_buy_status.setText("Veri yok")
            elif mode == "bulk_sell":
                strat = self.bulk_sell_combo.currentText()
                stats = self.master.get_cached_stats(item_name, db_lvl, server=self._resolve_db_server(filter_server))
                price = self._calc_strategy_price(item_name, db_lvl, strat, "sell", stats)
                color, diff, label = self._get_price_safety(price, srv_prices)
                if color:
                    self.bulk_sell_status.setStyleSheet(f"color: {color.name()}; font-size:10px; font-weight:bold; padding:2px; background:#222; border-radius:3px;")
                    self.bulk_sell_status.setText(f"{label} (%{diff:.1f})")
                else:
                    self.bulk_sell_status.setStyleSheet("color: #888; font-size:10px; padding:2px; background:#222; border-radius:3px;")
                    self.bulk_sell_status.setText("Veri yok")
        except Exception:
            pass

    def _update_all_strategy_status(self):
        try:
            self._update_strategy_status("buy")
            self._update_strategy_status("sell")
        except Exception:
            pass

    def _on_guide_item_strat_click(self, item_idx, strat, ptype):
        try:
            if item_idx < 0 or item_idx >= len(self.portfolio):
                return
            item = self.portfolio[item_idx]
            if ptype == "buy":
                item["buy_strategy"] = strat
                if strat == "Manuel":
                    return
                item["buy_fixed"] = False
                db_lvl = "" if item["lvl"] in ["+0", "0"] else item["lvl"]
                filter_server = self._get_filtered_server()
                db_server = self._resolve_db_server(filter_server)
                stats = self.master.get_cached_stats(item["name"], db_lvl, server=db_server)
                price = self._calc_strategy_price(item["name"], db_lvl, strat, "buy", stats)
                if price > 0:
                    item["buy_price"] = price
            else:
                item["sell_strategy"] = strat
                if strat == "Manuel":
                    return
                item["sell_fixed"] = False
                db_lvl = "" if item["lvl"] in ["+0", "0"] else item["lvl"]
                filter_server = self._get_filtered_server()
                db_server = self._resolve_db_server(filter_server)
                stats = self.master.get_cached_stats(item["name"], db_lvl, server=db_server)
                price = self._calc_strategy_price(item["name"], db_lvl, strat, "sell", stats)
                if price > 0:
                    item["sell_price"] = price
            self.auto_save()
            self.render_portfolio_ui()
        except Exception:
            pass

    def _open_guide(self):
        if self._guide_dialog is None:
            self._guide_dialog = PriceGuideDialog(self, self.master)
        self._guide_dialog.refresh()
        self._guide_dialog.show()
        self._guide_dialog.raise_()
        self._guide_dialog.activateWindow()

    def _open_excel_preview(self):
        if self._excel_preview_dialog is None:
            self._excel_preview_dialog = ExcelPreviewDialog(self, self.master)
        self._excel_preview_dialog.refresh()
        self._excel_preview_dialog.show()
        self._excel_preview_dialog.raise_()
        self._excel_preview_dialog.activateWindow()

    def _open_price_list(self):
        if self._price_list_dialog is None:
            self._price_list_dialog = PriceListDialog(self, self.master)
        self._price_list_dialog.refresh()
        self._price_list_dialog.show()
        self._price_list_dialog.raise_()
        self._price_list_dialog.activateWindow()

    def _refresh_guide_multi(self):
        if self._guide_dialog and self._guide_dialog.isVisible():
            self._guide_dialog.refresh()
        if self._excel_preview_dialog and self._excel_preview_dialog.isVisible():
            self._excel_preview_dialog.refresh()
        if self._price_list_dialog and self._price_list_dialog.isVisible():
            self._price_list_dialog.refresh()

    def _refresh_all_windows(self):
        self.master.stats_cache.clear()
        self.render_portfolio_ui()
        if self._guide_dialog and self._guide_dialog.isVisible():
            self._guide_dialog.refresh()
        if self._excel_preview_dialog and self._excel_preview_dialog.isVisible():
            self._excel_preview_dialog.refresh()
        if self._price_list_dialog and self._price_list_dialog.isVisible():
            self._price_list_dialog.refresh()

    def _start_auto_refresh(self):
        from PySide6.QtCore import QTimer
        self._auto_refresh_timer = QTimer(self.master)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_tick)
        self._auto_refresh_timer.start(30000)

    def _auto_refresh_tick(self):
        if not self.isVisible():
            return
        has_open = (
            (self._guide_dialog and self._guide_dialog.isVisible()) or
            (self._excel_preview_dialog and self._excel_preview_dialog.isVisible()) or
            (self._price_list_dialog and self._price_list_dialog.isVisible())
        )
        if has_open:
            self.master.stats_cache.clear()
            if self._guide_dialog and self._guide_dialog.isVisible():
                self._guide_dialog.refresh()
            if self._excel_preview_dialog and self._excel_preview_dialog.isVisible():
                self._excel_preview_dialog.refresh()
            if self._price_list_dialog and self._price_list_dialog.isVisible():
                self._price_list_dialog.refresh()

    def _update_price_guide(self, item_name, item_lvl, strategy, price_type, stats, srv_prices):
        self._refresh_guide_multi()

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

    def render_portfolio_ui(self):
        self._updating = True
        self.table.setRowCount(0)
        self._spike_cache = {}
        search_term = self.port_search_entry.text().strip().lower() if hasattr(self, 'port_search_entry') else ""
        filter_server = self._get_filtered_server()
        db_server = self._resolve_db_server(filter_server)
        group_servers = self._get_group_servers(filter_server)
        is_group = len(group_servers) > 0

        if is_group:
            extra_cols = []
            for srv in group_servers:
                extra_cols.extend([f"{srv} Alis", f"{srv} Satis"])
            headers = (["Item", "Lvl", "Adet", "Alis Fiyati", "Alis Stratejisi", "Top. Maliyet",
                        "Satis Fiyati", "Satis Stratejisi", "Beklenen Kar", "Durum"] +
                       extra_cols +
                       ["Alis Sabit", "Satis Sabit", "Sunucu", "Gecmis Dusuk", "Gecmis Yuksek"])
            n_servers = len(group_servers)
        else:
            headers = ["Item", "Lvl", "Adet", "Alis Fiyati", "Alis Stratejisi", "Top. Maliyet",
                       "Satis Fiyati", "Satis Stratejisi", "Beklenen Kar", "Durum",
                       "Alis Sabit", "Satis Sabit", "Sunucu", "Gecmis Dusuk", "Gecmis Yuksek"]
            n_servers = 0

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        col_fix_buy = 10 + 2 * n_servers
        col_fix_sell = 11 + 2 * n_servers
        col_server = 12 + 2 * n_servers
        col_hist1 = 13 + 2 * n_servers
        col_hist2 = 14 + 2 * n_servers

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
            elif stats:
                current_buy_price = self._calc_strategy_price(item["name"], db_lvl, buy_strat, "buy", stats,
                    spread_lower=self.spread_lower.text().strip())
            else:
                current_buy_price = item["buy_price"]

            if not buy_fixed:
                item["buy_price"] = current_buy_price

            if sell_fixed:
                sell_price = item.get('sell_price', 0)
            elif stats:
                sell_price = self._calc_strategy_price(item["name"], db_lvl, sell_strat, "sell", stats,
                    spread_upper=self.spread_upper.text().strip(),
                    current_buy_price=item.get("buy_price", 0))
                if not sell_fixed:
                    item['sell_price'] = sell_price
            else:
                sell_price = item.get('sell_price', 0)

            total_cost = item["buy_price"] * count
            total_profit = 0
            status = ""
            row_color = QColor(0xf3, 0x9c, 0x12)
            if stats and stats.get("sell") and stats.get("buy"):
                unit_profit = (sell_price * 0.97) - item["buy_price"]
                total_profit = unit_profit * count
                status = "Kar" if total_profit > 0 else "Zarar"
                row_color = QColor(0x2e, 0xcc, 0x71) if total_profit > 0 else QColor(0xe7, 0x4c, 0x3c)

            hist = get_historical_extremes(item["name"], db_lvl, server=db_server)

            row = self.table.rowCount()
            self.table.insertRow(row)

            raw_server = item.get("server", "") or "Tum"
            if filter_server.endswith("(Tumu)"):
                display_server = filter_server.replace(" (Tumu)", "")
            else:
                display_server = raw_server

            vals = [
                item["name"], item["lvl"], str(count), f"{item['buy_price']:,.0f}",
                buy_strat, f"{total_cost:,.0f}",
                f"{sell_price:,.0f}", sell_strat, f"{total_profit:,.0f}", status,
            ]

            if is_group:
                target_buy = item.get("buy_price", 0)
                srv_buy_prices = {}
                srv_sell_prices = {}
                srv_buy_stats = {}
                srv_sell_stats = {}
                for srv in group_servers:
                    srv_stats = self.master.get_cached_stats(item["name"], db_lvl, server=srv)
                    if srv_stats and srv_stats.get("buy"):
                        if buy_fixed or buy_strat == "Manuel":
                            srv_buy = item["buy_price"]
                        elif buy_strat == "Auto":
                            b = srv_stats.get("buy", {})
                            net_max = b.get("max", 0) * 0.97
                            if net_max <= 0: srv_buy = 0
                            elif net_max <= b.get("min", 0): srv_buy = b.get("min", 0)
                            else: srv_buy = b.get("q1", 0)
                        else:
                            srv_buy = srv_stats['buy'].get(s_map.get(buy_strat, "median"), 0)
                    else:
                        srv_buy = 0
                    if srv_stats and srv_stats.get("sell"):
                        if sell_fixed:
                            srv_sell = item.get('sell_price', 0)
                        elif sell_strat == "Auto":
                            raw_s = srv_stats.get('sell_raw')
                            if raw_s is not None and not raw_s.empty:
                                pct = float(self.spread_upper.text().strip()) / 100.0
                                srv_sell = float(np.percentile(raw_s, pct * 100))
                            else:
                                srv_sell = srv_stats["sell"].get("q3", 0)
                        else:
                            srv_sell = srv_stats["sell"].get(s_map.get(sell_strat, "median"), 0)
                    else:
                        srv_sell = 0
                    srv_buy_prices[srv] = srv_buy
                    srv_sell_prices[srv] = srv_sell
                    srv_buy_stats[srv] = srv_buy
                    srv_sell_stats[srv] = srv_sell

                buy_manip = self._detect_manipulation(srv_buy_prices)
                sell_manip = self._detect_manipulation(srv_sell_prices)

                for srv in group_servers:
                    srv_buy = srv_buy_stats[srv]
                    srv_sell = srv_sell_stats[srv]
                    buy_color, buy_diff, buy_label = buy_manip.get(srv, (None, 0, ""))
                    sell_color, sell_diff, sell_label = sell_manip.get(srv, (None, 0, ""))

                    buy_spike_color, buy_spike_pct, buy_spike_label = self._detect_price_spike(
                        item["name"], db_lvl, srv, srv_buy, minutes=10, threshold=20
                    )
                    sell_spike_color, sell_spike_pct, sell_spike_label = self._detect_price_spike(
                        item["name"], db_lvl, srv, srv_sell, minutes=10, threshold=20
                    )

                    def _merge_color(manip_color, spike_color, manip_diff, spike_pct, manip_label, spike_label):
                        if spike_color and manip_color:
                            if abs(spike_pct) > manip_diff:
                                return spike_color, abs(spike_pct), spike_label
                            else:
                                return manip_color, manip_diff, manip_label
                        elif spike_color:
                            return spike_color, abs(spike_pct), spike_label
                        elif manip_color:
                            return manip_color, manip_diff, manip_label
                        return None, 0, ""

                    final_buy_color, final_buy_diff, final_buy_label = _merge_color(
                        buy_color, buy_spike_color, buy_diff, buy_spike_pct, buy_label, buy_spike_label
                    )
                    final_sell_color, final_sell_diff, final_sell_label = _merge_color(
                        sell_color, sell_spike_color, sell_diff, sell_spike_pct, sell_label, sell_spike_label
                    )

                    cell_buy = QTableWidgetItem(f"{srv_buy:,.0f}" if srv_buy else "-")
                    cell_sell = QTableWidgetItem(f"{srv_sell:,.0f}" if srv_sell else "-")
                    if final_buy_color:
                        cell_buy.setForeground(final_buy_color)
                        if final_buy_label not in ("Normal", "Stabil", ""):
                            cell_buy.setToolTip(f"{srv} Alis: {final_buy_label} (%{final_buy_diff:.1f})")
                    if final_sell_color:
                        cell_sell.setForeground(final_sell_color)
                        if final_sell_label not in ("Normal", "Stabil", ""):
                            cell_sell.setToolTip(f"{srv} Satis: {final_sell_label} (%{final_sell_diff:.1f})")
                    vals.append(cell_buy)
                    vals.append(cell_sell)

            hist_min = "-"
            hist_max = "-"
            if hist['buy']['min'] and hist['sell']['min']:
                hist_min = f"{min(hist['buy']['min'], hist['sell']['min']):,.0f}"
            elif hist['buy']['min']:
                hist_min = f"{hist['buy']['min']:,.0f}"
            elif hist['sell']['min']:
                hist_min = f"{hist['sell']['min']:,.0f}"
            if hist['buy']['max'] and hist['sell']['max']:
                hist_max = f"{max(hist['buy']['max'], hist['sell']['max']):,.0f}"
            elif hist['buy']['max']:
                hist_max = f"{hist['buy']['max']:,.0f}"
            elif hist['sell']['max']:
                hist_max = f"{hist['sell']['max']:,.0f}"
            vals.extend([display_server, hist_min, hist_max])

            for j, val in enumerate(vals):
                if isinstance(val, QTableWidgetItem):
                    val.setTextAlignment(Qt.AlignCenter)
                    if j == 8:
                        val.setForeground(row_color)
                    self.table.setItem(row, j, val)
                else:
                    cell = QTableWidgetItem(str(val))
                    if j in (8, 9):
                        cell.setForeground(row_color)
                    self.table.setItem(row, j, cell)

            cb_buy = QTableWidgetItem()
            cb_buy.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb_buy.setCheckState(Qt.Checked if buy_fixed else Qt.Unchecked)
            cb_buy.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col_fix_buy, cb_buy)

            cb_sell = QTableWidgetItem()
            cb_sell.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            cb_sell.setCheckState(Qt.Checked if sell_fixed else Qt.Unchecked)
            cb_sell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col_fix_sell, cb_sell)

        self._spike_cache = {}
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
        deleted_row = min(s.row() for s in selected)
        rows_to_delete = sorted([s.row() for s in selected], reverse=True)
        indices = []
        for row in rows_to_delete:
            idx = self._table_to_idx(row)
            if idx is not None and 0 <= idx < len(self.portfolio):
                indices.append(idx)
        for idx in sorted(indices, reverse=True):
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
        idx = self._table_to_idx(row)
        if idx is None:
            return
        prev_idx = None
        for r in range(row - 1, -1, -1):
            prev_idx = self._table_to_idx(r)
            if prev_idx is not None:
                break
        if prev_idx is None:
            return
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
        idx = self._table_to_idx(row)
        if idx is None:
            return
        next_idx = None
        for r in range(row + 1, self.table.rowCount()):
            next_idx = self._table_to_idx(r)
            if next_idx is not None:
                break
        if next_idx is None:
            return
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
        idx = self._table_to_idx(row)
        if idx is None:
            return
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
        idx = self._table_to_idx(row)
        if idx is None:
            return
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
        idx = self._table_to_idx(row)
        if idx is None:
            return
        try:
            target = int(self.move_index_entry.text().strip()) - 1
        except ValueError:
            return
        if 0 <= target < len(self.portfolio):
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
        row = selected[0].row()
        idx = self._table_to_idx(row)
        if idx is not None:
            self._clipboard_idx = idx

    def _paste_cut(self):
        if not hasattr(self, '_clipboard_idx') or self._clipboard_idx is None:
            return
        if self._clipboard_idx >= len(self.portfolio):
            return
        selected = self.table.selectionModel().selectedRows()
        if selected:
            target_idx = self._table_to_idx(selected[0].row())
            if target_idx is None:
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
            db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
            stats = self.master.get_cached_stats(item['name'], db_lvl, server=db_server)
            if target_type == "sell":
                item['sell_strategy'] = strat
                if strat == "Manuel":
                    item['sell_price'] = manual_price
                elif stats:
                    item['sell_price'] = self._calc_strategy_price(item['name'], db_lvl, strat, "sell", stats,
                        spread_upper=self.spread_upper.text().strip(),
                        current_buy_price=item.get("buy_price", 0))

            elif target_type == "buy":
                item['buy_strategy'] = strat
                if strat == "Manuel":
                    item['buy_price'] = manual_price
                elif stats:
                    item['buy_price'] = self._calc_strategy_price(item['name'], db_lvl, strat, "buy", stats,
                        spread_lower=self.spread_lower.text().strip())
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
        indices = sorted([s.row() for s in selected], reverse=True)
        p_indices = []
        for row in indices:
            idx = self._table_to_idx(row)
            if idx is not None and 0 <= idx < len(self.portfolio):
                p_indices.append(idx)
        for idx in sorted(p_indices, reverse=True):
            del self.portfolio[idx]
        self.auto_save()
        self._updating = True
        self.render_portfolio_ui()
        self._updating = False

    def double_click_edit(self, index):
        idx = self._table_to_idx(index.row())
        if idx is not None:
            self.open_buy_edit_popup(idx)

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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
                if stats and stats.get('buy'):
                    b_min = stats['buy'].get("min", 0)
                    b_max = stats['buy'].get("max", 0)
                    if b_min > 0 and b_max > b_min:
                        new_buy_price = random.randint(int(b_min), int(b_max))
            elif buy_strat == "Otonom":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
                if stats and stats.get('buy'):
                    b = stats['buy']
                    if b.get("min", 0) > 0 and b.get("q1", 0) > b.get("min", 0):
                        new_buy_price = b.get("q1", 0)
                    else:
                        new_buy_price = b.get("min", 0)
            elif buy_strat == "Max %3 Vergi":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
                if stats and stats.get('buy'):
                    new_buy_price = stats['buy'].get("max", 0) * 0.97
            else:
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
                if stats and stats.get('sell') and new_buy_price > 0:
                    new_sell_price, _ = self._auto_sell_calc(stats, new_buy_price)
            elif sell_strat == "Kar Odaklı":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
                if stats and stats.get('sell'):
                    s_min = stats['sell'].get("min", 0)
                    s_max = stats['sell'].get("max", 0)
                    if s_min > 0 and s_max > s_min:
                        new_sell_price = random.randint(int(s_min), int(s_max))
            elif sell_strat == "Otonom":
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
                if stats and stats.get('sell'):
                    s = stats['sell']
                    if s.get("max", 0) > 0 and s.get("q3", 0) < s.get("max", 0):
                        new_sell_price = s.get("q3", 0)
                    else:
                        new_sell_price = s.get("max", 0)
            else:
                db_lvl = "" if item['lvl'] in ["+0", "0"] else item['lvl']
                stats = self.master.analyzer.get_item_stats(item['name'], db_lvl, time_limit_minutes=self.master.get_time_filter_minutes(), server=item.get("server", ""))
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
            idx = self._table_to_idx(selected)
            if idx is not None:
                self.open_buy_edit_popup(idx)

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
            idx = self._table_to_idx(row)
            if idx is not None:
                self.open_buy_edit_popup(idx)
        elif action == delete_action:
            self._delete_row(row)
        elif action == move_up:
            idx = self._table_to_idx(row)
            prev_idx = None
            for r in range(row - 1, -1, -1):
                prev_idx = self._table_to_idx(r)
                if prev_idx is not None:
                    break
            if idx is not None and prev_idx is not None:
                self.portfolio[idx], self.portfolio[prev_idx] = self.portfolio[prev_idx], self.portfolio[idx]
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False
        elif action == move_down:
            idx = self._table_to_idx(row)
            next_idx = None
            for r in range(row + 1, self.table.rowCount()):
                next_idx = self._table_to_idx(r)
                if next_idx is not None:
                    break
            if idx is not None and next_idx is not None:
                self.portfolio[idx], self.portfolio[next_idx] = self.portfolio[next_idx], self.portfolio[idx]
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False
        elif action == add_to_list:
            idx = self._table_to_idx(row)
            if idx is not None:
                item = self.portfolio[idx]
                self.portfolio.append(item.copy())
                self.auto_save()
                self._updating = True
                self.render_portfolio_ui()
                self._updating = False


    def _on_cell_changed(self, row, col):
        if self._updating:
            return
        if col not in (10, 11):
            return
        item_widget = self.table.item(row, col)
        if item_widget is None:
            return
        checked = item_widget.checkState() == Qt.Checked
        idx = self._table_to_idx(row)
        if idx is None:
            return
        if col == 10:
            self.portfolio[idx]["buy_fixed"] = checked
        elif col == 11:
            self.portfolio[idx]["sell_fixed"] = checked
        self._updating = True
        self.render_portfolio_ui()
        self._updating = False
        self.auto_save()

    def _table_to_idx(self, table_row):
        visible_rows = self._get_visible_rows()
        if 0 <= table_row < len(visible_rows):
            return visible_rows[table_row]
        return None

    def _delete_row(self, row):
        idx = self._table_to_idx(row)
        if idx is not None and 0 <= idx < len(self.portfolio):
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
            self.spread_lower.setText(settings.get("spread_lower", "49"))
            self.spread_upper.setText(settings.get("spread_upper", "51"))
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
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        file_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        display_name = f"{name.strip()} - {now_str}"
        file_name = f"{name.strip()}_{file_str}"
        path = os.path.join(lists_dir, f"{file_name}.json")
        data = {
            "items": self.portfolio,
            "display_name": display_name,
            "saved_at": now_str,
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
            self.spread_lower.setText(settings.get("spread_lower", "49"))
            self.spread_upper.setText(settings.get("spread_upper", "51"))
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
        names = []
        for f in sorted(os.listdir(lists_dir), reverse=True):
            if f.endswith(".json"):
                try:
                    path = os.path.join(lists_dir, f)
                    with open(path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    display = data.get("display_name", f.replace(".json", ""))
                    names.append((f.replace(".json", ""), display))
                except Exception:
                    names.append((f.replace(".json", ""), f.replace(".json", "")))
        return names

    def _refresh_saved_lists(self):
        self.saved_list_combo.clear()
        self._saved_list_map = {}
        names = self.get_saved_list_names()
        for file_key, display in names:
            self.saved_list_combo.addItem(display)
            self._saved_list_map[display] = file_key

    def _load_selected_list(self):
        display = self.saved_list_combo.currentText()
        if display:
            file_key = self._saved_list_map.get(display, display)
            self.load_named_list(file_key)
            QMessageBox.information(self.master, "Basari", f"'{display}' listesi yuklendi!")

    def _save_as_new_list(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.master, "Liste Kaydet", "Liste adi girin:")
        if ok and name.strip():
            self.save_named_list(name.strip())
            self._refresh_saved_lists()
            QMessageBox.information(self.master, "Basari", f"Liste kaydedildi!")

    def _delete_selected_list(self):
        display = self.saved_list_combo.currentText()
        if not display:
            return
        file_key = self._saved_list_map.get(display, display)
        reply = QMessageBox.question(self.master, "Silme Onayi", f"'{display}' listesini silmek istediginize emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.delete_named_list(file_key)
            self._refresh_saved_lists()
            QMessageBox.information(self.master, "Basari", f"'{display}' listesi silindi!")

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
        col = 10 if fix_type == "buy" else 11
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
