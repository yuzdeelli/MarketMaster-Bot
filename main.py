import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.login_window import LoginWindow
from ui.main_window import KnightMarketMasterV3

if __name__ == "__main__":
    app = QApplication(sys.argv)

    with open(os.path.join(os.path.dirname(__file__), "ui", "style.qss"), "r") as f:
        app.setStyleSheet(f.read())

    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
