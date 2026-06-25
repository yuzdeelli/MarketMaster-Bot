from PySide6.QtWidgets import (QWidget, QVBoxLayout, QComboBox,
                                QCompleter, QLineEdit)
from PySide6.QtCore import Qt, Signal


class SearchableComboBox(QWidget):
    itemSelected = Signal(str)

    def __init__(self, values=None, width=200, placeholder_text="Ara...", parent=None):
        super().__init__(parent)
        self._all_values = list(values) if values else []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setFixedWidth(width)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.completer().setFilterMode(Qt.MatchContains)
        self.combo.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.combo.setMaxVisibleItems(12)

        self.combo.lineEdit().setPlaceholderText(placeholder_text)
        self.combo.lineEdit().textChanged.connect(self._on_text_changed)
        self.combo.currentTextChanged.connect(self._on_current_changed)

        self._suppress = False

        layout.addWidget(self.combo)

        if self._all_values:
            self._populate()

    def _populate(self):
        self._suppress = True
        self.combo.clear()
        self.combo.addItems(self._all_values)
        self.combo.lineEdit().clear()
        self._suppress = False

    def _on_text_changed(self, text):
        if self._suppress:
            return
        self._suppress = True
        current = self.combo.currentText()
        if current != text:
            self.combo.setCurrentText(text)
        self._suppress = False

    def _on_current_changed(self, text):
        if self._suppress:
            return
        if text and text in self._all_values:
            self.itemSelected.emit(text)

    def get(self):
        return self.combo.currentText().strip()

    def set(self, value):
        self.combo.setCurrentText(value)

    def configure_values(self, values):
        self._all_values = list(values)
        self._populate()
