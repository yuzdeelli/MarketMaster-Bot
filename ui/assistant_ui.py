import math
import threading
import time
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QLineEdit, QPushButton, QTextEdit,
                                QScrollArea, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from core.config import ConfigManager

try:
    import speech_recognition as sr
except ImportError:
    sr = None


class AnimatedCore(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self.animation_angle = 0
        self.pulse_direction = 1
        self.pulse_radius = 50
        self.assistant_state = "sleeping"

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(33)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx, cy = 70, 70
        state_config = {
            "sleeping": (0.02, QColor(0x22, 0x22, 0x22), QColor(0x11, 0x11, 0x11)),
            "listening": (0.08, QColor(0x2e, 0xcc, 0x71), QColor(0x27, 0xae, 0x60)),
            "thinking": (0.15, QColor(0x34, 0x98, 0xdb), QColor(0x29, 0x80, 0xb9)),
            "speaking": (0.05, QColor(0x9b, 0x59, 0xb6), QColor(0x8e, 0x44, 0xad)),
        }
        speed, color, secondary = state_config.get(self.assistant_state, state_config["sleeping"])
        self.animation_angle += speed

        if self.assistant_state == "listening":
            self.pulse_radius += self.pulse_direction * 1.5
            if self.pulse_radius > 62 or self.pulse_radius < 45:
                self.pulse_direction *= -1
            r1 = self.pulse_radius
            r2 = r1 - 12
        elif self.assistant_state == "thinking":
            r1 = 52 + math.sin(self.animation_angle) * 3
            r2 = 40 + math.cos(self.animation_angle) * 3
        else:
            r1 = 50 + math.sin(self.animation_angle) * 2
            r2 = 38 + math.cos(self.animation_angle * 1.5) * 2

        pen = QPen(secondary, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(cx - int(r1), cy - int(r1), int(r1 * 2), int(r1 * 2))

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(cx - int(r2), cy - int(r2), int(r2 * 2), int(r2 * 2))

        if self.assistant_state in ("thinking", "speaking"):
            px = cx + r1 * math.cos(self.animation_angle)
            py = cy + r1 * math.sin(self.animation_angle)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(int(px) - 4, int(py) - 4, 8, 8)

        painter.end()


class MasterAssistantWindow(QMainWindow):
    def __init__(self, master=None):
        super().__init__(master)
        self.setWindowTitle("MASTER-V")
        self.setFixedSize(400, 600)
        self.setStyleSheet("background-color: #000000;")

        self.assistant_state = "sleeping"
        self.is_listening_to_mic = False

        central = QWidget()
        central.setStyleSheet("background-color: #000000;")
        layout = QVBoxLayout(central)

        self.lbl_status = QLabel("UYKU MODU ('Hey Master' Bekleniyor)")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-family: Consolas; font-size: 12px; font-weight: bold; color: #555555;")
        layout.addWidget(self.lbl_status)

        self.core_widget = AnimatedCore()
        core_container = QHBoxLayout()
        core_container.addStretch()
        core_container.addWidget(self.core_widget)
        core_container.addStretch()
        layout.addLayout(core_container)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("background: #050505; border: 1px solid #111111; border-radius: 10px; color: #fff;")
        layout.addWidget(self.chat_area, stretch=1)

        bottom = QHBoxLayout()
        self.entry_message = QLineEdit()
        self.entry_message.setPlaceholderText("Yazin veya konusun...")
        self.entry_message.setStyleSheet("background: #0a0a0a; color: #fff; border: 1px solid #222; padding: 8px;")
        self.entry_message.returnPressed.connect(self.send_text_message)
        bottom.addWidget(self.entry_message)

        btn_send = QPushButton("GONDER")
        btn_send.setFixedSize(40, 40)
        btn_send.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold;")
        btn_send.clicked.connect(self.send_text_message)
        bottom.addWidget(btn_send)
        layout.addLayout(bottom)

        self.setCentralWidget(central)

        self.recognizer = None
        if sr:
            self.recognizer = sr.Recognizer()
        self.start_microphone_listener()

    def start_microphone_listener(self):
        if self.is_listening_to_mic or not sr:
            return
        self.is_listening_to_mic = True
        threading.Thread(target=self._listen_to_mic_loop, daemon=True).start()

    def _listen_to_mic_loop(self):
        selected_mic_idx = ConfigManager.load_mic_index()
        try:
            with sr.Microphone(device_index=selected_mic_idx) as source:
                QTimer.singleShot(0, lambda: self.add_chat_bubble("Sistem", "Mikrofon kalibre ediliyor..."))
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                QTimer.singleShot(0, lambda: self.add_chat_bubble("Sistem", "Mikrofon aktif. 'Hey Master' komutunu dinliyorum."))
                QTimer.singleShot(0, lambda: self.set_assistant_state("sleeping"))

                while self.is_listening_to_mic:
                    try:
                        QTimer.singleShot(0, lambda: self.set_assistant_state("listening"))
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                        QTimer.singleShot(0, lambda: self.set_assistant_state("thinking"))
                        text = self.recognizer.recognize_google(audio, language="tr-TR")
                        if text:
                            QTimer.singleShot(0, lambda t=text: self.add_chat_bubble("Siz (Ses)", t, is_user=True))
                            if "hey master" in text.lower() or "master" in text.lower():
                                QTimer.singleShot(0, lambda: self.set_assistant_state("speaking"))
                                QTimer.singleShot(0, lambda: self.add_chat_bubble("Master", "Sizi dinliyorum, ne islem yapmami istersiniz?"))
                                time.sleep(2)
                            else:
                                QTimer.singleShot(0, lambda: self.set_assistant_state("sleeping"))
                    except sr.WaitTimeoutError:
                        QTimer.singleShot(0, lambda: self.set_assistant_state("sleeping"))
                    except sr.UnknownValueError:
                        QTimer.singleShot(0, lambda: self.set_assistant_state("sleeping"))
                    except Exception as e:
                        QTimer.singleShot(0, lambda: self.add_chat_bubble("Sistem", f"Donanim Hatasi: {e}"))
                        self.is_listening_to_mic = False
                        break
        except Exception as e:
            QTimer.singleShot(0, lambda: self.add_chat_bubble("Sistem", f"Mikrofon hatasi: {e}"))
            self.is_listening_to_mic = False

    def set_assistant_state(self, state):
        self.assistant_state = state
        self.core_widget.assistant_state = state
        labels = {
            "sleeping": ("UYKU MODU ('Hey Master' Bekleniyor)", "#555555"),
            "listening": ("DINLIYORUM... (Sizi Duyabiliyorum)", "#2ecc71"),
            "thinking": ("DUSUNUYORUM... (Veriler Analiz Ediliyor)", "#3498db"),
            "speaking": ("KONUSUYORUM... (Sesli Cevap Veriliyor)", "#9b59b6"),
        }
        text, color = labels.get(state, ("Bilinmiyor", "#555555"))
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"font-family: Consolas; font-size: 12px; font-weight: bold; color: {color};")

    def add_chat_bubble(self, sender, text, is_user=False):
        color = "#2ecc71" if is_user else "#8e44ad"
        border = "#252525" if is_user else "#1e132b"
        bg = "#161616" if is_user else "#0f0f15"
        prefix = "<div style='margin:2px; padding:6px; background:{}; border:1px solid {}; border-radius:6px;'>".format(bg, border)
        prefix += f"<span style='color:{color}; font-weight:bold; font-size:10px;'>{sender}</span><br>"
        prefix += f"<span style='color:#fff; font-size:12px;'>{text}</span></div>"
        self.chat_area.append(prefix)
        scrollbar = self.chat_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def send_text_message(self):
        user_text = self.entry_message.text().strip()
        if not user_text:
            return
        self.add_chat_bubble("Siz", user_text, is_user=True)
        self.entry_message.clear()
        self.set_assistant_state("thinking")

        def simulate_response():
            time.sleep(1.2)
            QTimer.singleShot(0, lambda: self.set_assistant_state("speaking"))
            QTimer.singleShot(0, lambda: self.add_chat_bubble("Master", f"'{user_text}' komutunu manuel olarak aldim."))
            time.sleep(1.5)
            QTimer.singleShot(0, lambda: self.set_assistant_state("sleeping"))

        threading.Thread(target=simulate_response, daemon=True).start()
