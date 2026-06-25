import os
import json
import base64
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QLabel, QLineEdit,
                                QPushButton, QCheckBox, QMessageBox, QWidget)
from PySide6.QtCore import Qt
from core.config import ConfigManager

REMEMBER_FILE = "remember.json"


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Master v3.0 - Giris")
        self.setFixedSize(420, 380)

        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        if ConfigManager.has_admin_password():
            self._show_login()
        else:
            self._show_first_run()

    def _setup_ui(self):
        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setAlignment(Qt.AlignCenter)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

    def _clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _show_first_run(self):
        self._clear_layout()
        self.setWindowTitle("Market Master v3.0 - Ilk Kurulum")

        title = QLabel("ILK KURULUM\nAdmin Sifresi Belirleyin")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9800;")
        self.layout.addWidget(title)
        self.layout.addSpacing(20)

        self.pass_entry = QLineEdit()
        self.pass_entry.setPlaceholderText("Sifre (min 8 karakter)")
        self.pass_entry.setEchoMode(QLineEdit.Password)
        self.pass_entry.setFixedWidth(260)
        self.pass_entry.setStyleSheet("padding: 8px; font-size: 14px;")
        self.layout.addWidget(self.pass_entry, alignment=Qt.AlignCenter)

        self.pass_entry2 = QLineEdit()
        self.pass_entry2.setPlaceholderText("Sifre (Tekrar)")
        self.pass_entry2.setEchoMode(QLineEdit.Password)
        self.pass_entry2.setFixedWidth(260)
        self.pass_entry2.setStyleSheet("padding: 8px; font-size: 14px;")
        self.layout.addWidget(self.pass_entry2, alignment=Qt.AlignCenter)

        self.layout.addSpacing(10)

        btn = QPushButton("SIFRE BELIRLE")
        btn.setFixedWidth(260)
        btn.setFixedHeight(36)
        btn.setStyleSheet("background-color: #ff9800; color: #000; font-size: 14px; font-weight: bold;")
        btn.clicked.connect(self._set_first_password)
        self.layout.addWidget(btn, alignment=Qt.AlignCenter)

    def _set_first_password(self):
        p1 = self.pass_entry.text()
        p2 = self.pass_entry2.text()

        if len(p1) < 8:
            QMessageBox.critical(self, "Hata", "Sifre en az 8 karakter olmali!")
            return
        if p1 != p2:
            QMessageBox.critical(self, "Hata", "Sifreler eslesmiyor!")
            return

        ConfigManager.save_admin_password(p1)
        QMessageBox.information(self, "Basarili", "Sifre kaydedildi! Giris yapabilirsiniz.")
        self._show_login()

    def _show_login(self):
        self._clear_layout()
        self.setWindowTitle("Market Master v3.0 - Giris")

        title = QLabel("MARKET MASTER v3.0\nDeep Analyzer")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #00d4ff;")
        self.layout.addWidget(title)
        self.layout.addSpacing(20)

        self.pass_entry = QLineEdit()
        self.pass_entry.setPlaceholderText("Sifre")
        self.pass_entry.setEchoMode(QLineEdit.Password)
        self.pass_entry.setFixedWidth(260)
        self.pass_entry.setStyleSheet("padding: 8px; font-size: 14px;")
        self.layout.addWidget(self.pass_entry, alignment=Qt.AlignCenter)

        self.remember_var = QCheckBox("Beni Hatirla")
        self.layout.addWidget(self.remember_var, alignment=Qt.AlignCenter)
        self.layout.addSpacing(10)

        btn = QPushButton("GIRIS YAP")
        btn.setFixedWidth(260)
        btn.setFixedHeight(36)
        btn.setStyleSheet("background-color: #00d4ff; color: #000; font-size: 14px; font-weight: bold;")
        btn.clicked.connect(self.attempt_login)
        self.layout.addWidget(btn, alignment=Qt.AlignCenter)

        self.pass_entry.returnPressed.connect(self.attempt_login)

        self._auto_login()

    def _auto_login(self):
        saved = self._load_remembered()
        if saved and saved.get("pass"):
            self.pass_entry.setText(saved["pass"])
            self.remember_var.setChecked(True)

    def attempt_login(self):
        password = self.pass_entry.text()

        if ConfigManager.verify_admin_password(password):
            if self.remember_var.isChecked():
                self._save_remembered(password)
            else:
                self._remove_remembered()

            from ui.main_window import KnightMarketMasterV3
            self.main_window = KnightMarketMasterV3()
            self.main_window.show()
            self.close()
        else:
            QMessageBox.critical(self, "Hata", "Hatali sifre!")

    def _save_remembered(self, passwd):
        try:
            data = base64.b64encode(json.dumps({"pass": passwd}).encode()).decode()
            with open(REMEMBER_FILE, "w") as f:
                f.write(data)
        except Exception:
            pass

    def _load_remembered(self):
        try:
            if not os.path.exists(REMEMBER_FILE):
                return None
            with open(REMEMBER_FILE, "r") as f:
                data = json.loads(base64.b64decode(f.read().strip()).decode())
            return data
        except:
            return None

    def _remove_remembered(self):
        try:
            if os.path.exists(REMEMBER_FILE):
                os.remove(REMEMBER_FILE)
        except:
            pass
