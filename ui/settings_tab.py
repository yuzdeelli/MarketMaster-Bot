import webbrowser
import socket
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QLabel, QLineEdit, QGroupBox, QMessageBox,
                                QScrollArea, QFrame)
from PySide6.QtCore import Qt, QTimer
from core.config import ConfigManager
from web_server import WebServer


class SettingsTab:
    def __init__(self, master, parent):
        self.master = master
        self.parent = parent
        self.web_server = WebServer()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self.parent)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self._setup_api_key_section(scroll_layout)
        self._setup_web_server_section(scroll_layout)

        scroll_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _setup_api_key_section(self, layout):
        section = QGroupBox("USKOPAZAR API Ayarlari")
        section.setStyleSheet("QGroupBox { color: #e94560; }")
        s_layout = QVBoxLayout()

        lbl = QLabel("Pazar verilerini API uzerinden cekmek icin API key'inizi girin.\nSatin almak icin: https://www.haydargame.com/uskopazar-key-c-88")
        lbl.setStyleSheet("color: #888;")
        s_layout.addWidget(lbl)

        key_frame = QHBoxLayout()
        key_frame.addWidget(QLabel("API Key:"))
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setPlaceholderText("usk_xxxxxxxxxxxx...")
        self.api_key_entry.setFixedWidth(350)
        key_frame.addWidget(self.api_key_entry)

        saved_key = ConfigManager.load_api_key()
        if saved_key:
            masked = saved_key[:6] + "..." + saved_key[-4:] if len(saved_key) > 10 else saved_key
            self.api_key_entry.setText(saved_key)
            lbl = QLabel(f"Kayitli: {masked}")
            lbl.setStyleSheet("color: #2ecc71;")
            key_frame.addWidget(lbl)
            QTimer.singleShot(500, self._check_api_status)
        key_frame.addStretch()
        s_layout.addLayout(key_frame)

        btn_frame = QHBoxLayout()
        btn_save = QPushButton("Kaydet")
        btn_save.setFixedWidth(100)
        btn_save.setStyleSheet("background-color: #2ecc71; color: white;")
        btn_save.clicked.connect(self._save_api_key)
        btn_frame.addWidget(btn_save)

        btn_del = QPushButton("Sil")
        btn_del.setFixedWidth(80)
        btn_del.setStyleSheet("background-color: #e74c3c; color: white;")
        btn_del.clicked.connect(self._delete_api_key)
        btn_frame.addWidget(btn_del)

        btn_act = QPushButton("Aktive Et")
        btn_act.setFixedWidth(100)
        btn_act.setStyleSheet("background-color: #e67e22; color: white;")
        btn_act.clicked.connect(self._activate_api_key)
        btn_frame.addWidget(btn_act)

        btn_status = QPushButton("Durum Kontrol")
        btn_status.setFixedWidth(120)
        btn_status.setStyleSheet("background-color: #3498db; color: white;")
        btn_status.clicked.connect(self._check_api_status)
        btn_frame.addWidget(btn_status)
        btn_frame.addStretch()
        s_layout.addLayout(btn_frame)

        self.lbl_api_status = QLabel("")
        self.lbl_api_status.setStyleSheet("font-family: Consolas; color: #aaa;")
        s_layout.addWidget(self.lbl_api_status)

        section.setLayout(s_layout)
        layout.addWidget(section)

    def _save_api_key(self):
        key = self.api_key_entry.text().strip()
        if not key:
            QMessageBox.warning(self.master, "Hata", "API key bos olamaz!")
            return
        if not key.startswith("usk_"):
            QMessageBox.warning(self.master, "Uyari", "API key 'usk_' ile baslamali.")
            return
        ConfigManager.save_api_key(key)
        self.master.engine.set_api_key(key)
        QMessageBox.information(self.master, "Basarili", "API key kaydedildi!")

    def _delete_api_key(self):
        reply = QMessageBox.question(self.master, "Onay", "API key silinecek. Emin misiniz?")
        if reply == QMessageBox.Yes:
            ConfigManager.delete_api_key()
            self.master.engine.set_api_key(None)
            self.api_key_entry.clear()
            self.lbl_api_status.setText("API key silindi.")
            QMessageBox.information(self.master, "Silindi", "API key kalici olarak silindi.")

    def _activate_api_key(self):
        key = self.api_key_entry.text().strip()
        if not key:
            QMessageBox.warning(self.master, "Hata", "Once API key girin!")
            return
        self.lbl_api_status.setText("Aktive ediliyor...")
        self.lbl_api_status.setStyleSheet("color: #f39c12;")
        self.master.engine.set_api_key(key)
        result = self.master.engine.activate_api_key()
        if result.get("success"):
            expire = result.get("data", {}).get("expire_time", "Bilinmiyor")
            self.lbl_api_status.setText(f"Aktive edildi! Bitis: {expire}")
            self.lbl_api_status.setStyleSheet("color: #2ecc71;")
            ConfigManager.save_api_key(key)
            QMessageBox.information(self.master, "Basarili", f"API key aktive edildi!\nBitis tarihi: {expire}")
        else:
            error = result.get("error", "Bilinmeyen hata")
            self.lbl_api_status.setText(f"Hata: {error}")
            self.lbl_api_status.setStyleSheet("color: #e74c3c;")
            QMessageBox.critical(self.master, "Hata", f"Aktivasyon basarisiz:\n{error}")

    def _check_api_status(self):
        key = self.api_key_entry.text().strip()
        if not key:
            QMessageBox.warning(self.master, "Hata", "Once API key girin!")
            return
        self.lbl_api_status.setText("Kontrol ediliyor...")
        self.lbl_api_status.setStyleSheet("color: #f39c12;")
        self.master.engine.set_api_key(key)
        result = self.master.engine.check_api_status()
        if result.get("success"):
            data = result.get("data", {})
            status = data.get("status", "?")
            expire = data.get("expire_time", "?")
            daily = data.get("daily_quota", "?")
            used = data.get("used_today", "?")
            plan = data.get("plan", "?")
            status_text = f"Durum: {status.upper()}  |  Plan: {plan}  |  Bitis: {expire}\nGunluk Kota: {used}/{daily}"
            color = "#2ecc71" if status == "active" else "#e74c3c"
            self.lbl_api_status.setText(status_text)
            self.lbl_api_status.setStyleSheet(f"color: {color};")
        else:
            error = result.get("error", "Baglanti hatasi")
            self.lbl_api_status.setText(f"Hata: {error}")
            self.lbl_api_status.setStyleSheet("color: #e74c3c;")

    def _setup_web_server_section(self, layout):
        section = QGroupBox("Web Panel (Piyasa Analiz)")
        section.setStyleSheet("QGroupBox { color: #e94560; }")
        s_layout = QVBoxLayout()

        lbl = QLabel("Tarayicida pazar verilerini goruntulemek icin web sunucusunu baslatin.")
        lbl.setStyleSheet("color: #888;")
        s_layout.addWidget(lbl)

        port_frame = QHBoxLayout()
        port_frame.addWidget(QLabel("Port:"))
        default_port = "8765"
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analyzer_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                default_port = str(cfg.get("web_port", 8765))
        except:
            pass
        self.port_entry = QLineEdit(default_port)
        self.port_entry.setFixedWidth(60)
        port_frame.addWidget(self.port_entry)

        self.btn_web_server = QPushButton("Sunucuyu Baslat")
        self.btn_web_server.setStyleSheet("background-color: #e67e22; color: white;")
        self.btn_web_server.clicked.connect(self.toggle_web_server)
        port_frame.addWidget(self.btn_web_server)
        port_frame.addStretch()
        s_layout.addLayout(port_frame)

        ip_frame = QHBoxLayout()
        ip_frame.addWidget(QLabel("Bu PC IP:"))
        self.lbl_local_ip = QLabel(self._get_local_ip())
        self.lbl_local_ip.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 13px;")
        ip_frame.addWidget(self.lbl_local_ip)
        btn_copy_ip = QPushButton("Kopyala")
        btn_copy_ip.setFixedWidth(60)
        btn_copy_ip.clicked.connect(lambda: self._copy_text(self.lbl_local_ip.text()))
        ip_frame.addWidget(btn_copy_ip)
        ip_frame.addStretch()
        s_layout.addLayout(ip_frame)

        lbl_hint = QLabel("Diger PC'den: http://" + self._get_local_ip() + ":<port>")
        lbl_hint.setStyleSheet("color: #888; font-style: italic;")
        s_layout.addWidget(lbl_hint)

        self.lbl_web_status = QLabel("Durum: DURDU")
        self.lbl_web_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        s_layout.addWidget(self.lbl_web_status)

        url_frame = QHBoxLayout()
        self.lbl_web_url = QLabel("")
        self.lbl_web_url.setStyleSheet("color: #3498db;")
        url_frame.addWidget(self.lbl_web_url)

        self.btn_copy_url = QPushButton("Kopyala")
        self.btn_copy_url.setFixedWidth(60)
        self.btn_copy_url.setEnabled(False)
        self.btn_copy_url.clicked.connect(self._copy_url)
        url_frame.addWidget(self.btn_copy_url)

        self.btn_open_browser = QPushButton("Tarayicida Ac")
        self.btn_open_browser.setFixedWidth(100)
        self.btn_open_browser.setEnabled(False)
        self.btn_open_browser.clicked.connect(self._open_browser)
        url_frame.addWidget(self.btn_open_browser)
        url_frame.addStretch()
        s_layout.addLayout(url_frame)

        section.setLayout(s_layout)
        layout.addWidget(section)

    def toggle_web_server(self):
        if self.web_server.is_running:
            self.web_server.stop()
            self.btn_web_server.setText("Sunucuyu Baslat")
            self.btn_web_server.setStyleSheet("background-color: #e67e22; color: white;")
            self.lbl_web_status.setText("Durum: DURDU")
            self.lbl_web_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.lbl_web_url.setText("")
            self.btn_copy_url.setEnabled(False)
            self.btn_open_browser.setEnabled(False)
        else:
            try:
                port = int(self.port_entry.text().strip())
                self.web_server.port = port
            except ValueError:
                QMessageBox.warning(self.master, "Hata", "Gecerli bir port numarasi girin.")
                return
            success = self.web_server.start()
            if success:
                url = self.web_server.get_url()
                self.btn_web_server.setText("Sunucuyu Durdur")
                self.btn_web_server.setStyleSheet("background-color: #e74c3c; color: white;")
                self.lbl_web_status.setText("Durum: CALISIYOR")
                self.lbl_web_status.setStyleSheet("color: #2ecc71; font-weight: bold;")
                self.lbl_web_url.setText(url)
                self.btn_copy_url.setEnabled(True)
                self.btn_open_browser.setEnabled(True)
            else:
                QMessageBox.critical(self.master, "Hata", "Web sunucusu baslatilamadi!")

    def _copy_url(self):
        url = self.lbl_web_url.text()
        if url:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(url)

    def _open_browser(self):
        url = self.lbl_web_url.text()
        if url:
            webbrowser.open(url)

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            candidates = []
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip.startswith("127."):
                    continue
                if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    candidates.append(ip)
            s.close()
            if candidates:
                for ip in candidates:
                    if ip.startswith("192.168."):
                        return ip
                return candidates[0]
            return "127.0.0.1"
        except:
            return "127.0.0.1"

    def _copy_text(self, text):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
