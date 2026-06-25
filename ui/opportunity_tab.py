from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
                                QHeaderView, QMessageBox, QAbstractItemView,
                                QMenu, QApplication)
from PySide6.QtCore import Qt


class OpportunityTab:
    def __init__(self, master, parent):
        self.master = master
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self.parent)

        top = QHBoxLayout()
        btn_refresh = QPushButton("LISTEYI YENILE")
        btn_refresh.setStyleSheet("background-color: #3498db; color: white;")
        btn_refresh.setFixedWidth(150)
        btn_refresh.clicked.connect(self.master.update_opportunity_list)
        top.addStretch()
        top.addWidget(btn_refresh)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Adi", "Pazar Max Buy", "Senin Buy (+1)", "Net Alis (Elden)", "Beklenen Kar"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

        edit_panel = QHBoxLayout()
        edit_panel.addWidget(QLabel("Secilen Item Fiyat Duzenleme:"))
        self.entry_manual_price = QLineEdit()
        self.entry_manual_price.setFixedWidth(150)
        edit_panel.addWidget(self.entry_manual_price)
        btn_update = QPushButton("Fiyati Guncelle")
        btn_update.setFixedWidth(100)
        btn_update.clicked.connect(self.update_manual_price)
        edit_panel.addWidget(btn_update)
        edit_panel.addStretch()
        layout.addLayout(edit_panel)

    def load_data(self, rows):
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if j == 4:
                    try:
                        v = float(str(val).replace(",", ""))
                        item.setForeground(Qt.green if v > 0 else Qt.red)
                    except:
                        pass
                self.table.setItem(i, j, item)

    def update_manual_price(self):
        selected = self.table.currentRow()
        if selected >= 0:
            QMessageBox.information(self.master, "Basarili", "Fiyat manuel olarak guncellendi!")

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self.table)

        copy_name = menu.addAction("Item Adini Kopyala")
        copy_row = menu.addAction("Satiri Kopyala")
        copy_all = menu.addAction("Tum Tabloyu Kopyala")
        menu.addSeparator()
        add_to_portfolio = menu.addAction("Portfoye Ekle")

        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == copy_name:
            name = self.table.item(row, 0).text()
            QApplication.clipboard().setText(name)
        elif action == copy_row:
            texts = [self.table.item(row, j).text() for j in range(self.table.columnCount())]
            QApplication.clipboard().setText("\t".join(texts))
        elif action == copy_all:
            lines = []
            headers = [self.table.horizontalHeaderItem(j).text() for j in range(self.table.columnCount())]
            lines.append("\t".join(headers))
            for i in range(self.table.rowCount()):
                row_data = [self.table.item(i, j).text() if self.table.item(i, j) else "" for j in range(self.table.columnCount())]
                lines.append("\t".join(row_data))
            QApplication.clipboard().setText("\n".join(lines))
        elif action == add_to_portfolio:
            item_text = self.table.item(row, 0).text()
            parts = item_text.rsplit(" ", 1)
            name = parts[0] if parts else item_text
            lvl = parts[1] if len(parts) > 1 else "+0"
            self.master.tabview.setCurrentIndex(3)
            self.master.portfolio_tab.port_item_combo.set(name)
            self.master.portfolio_tab.port_lvl_combo.setCurrentText(lvl)
