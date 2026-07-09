"""自定义Widget组件"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from PyQt5.QtGui import QFont


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.StyledPanel)

    def set_layout(self, layout):
        self.setLayout(layout)


class SectionTitle(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.setFont(font)


class SubTitle(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        font = QFont()
        font.setPointSize(11)
        self.setFont(font)
        self.setStyleSheet("color: palette(mid);")


class StatusBadge(QLabel):
    def __init__(self, text="", status="normal", parent=None):
        super().__init__(text, parent)
        self.status = status
        self.setFixedHeight(26)
        self.setMinimumWidth(60)
        self.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.setFont(font)
        self._update_style()

    def set_status(self, status, text=""):
        self.status = status
        if text:
            self.setText(text)
        self._update_style()

    def _update_style(self):
        colors = {
            "normal": ("#27ae60", "#1e8449"),
            "warning": ("#f39c12", "#d68910"),
            "error": ("#e74c3c", "#c0392b"),
            "info": ("#3498db", "#2980b9"),
        }
        bg, _ = colors.get(self.status, colors["normal"])
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: #FFFFFF;
                border-radius: 13px;
                padding: 2px 12px;
            }}
        """)


class Separator(QFrame):
    def __init__(self, vertical=False, parent=None):
        super().__init__(parent)
        if vertical:
            self.setFixedWidth(1)
            self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().Expanding)
        else:
            self.setFixedHeight(1)
            self.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().horizontalPolicy())
        self.setStyleSheet("background-color: palette(mid);")


class IconLabel(QWidget):
    def __init__(self, icon_text, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.icon = QLabel(icon_text)
        self.icon.setStyleSheet("font-size: 18px;")
        self.label = QLabel(text)
        layout.addWidget(self.icon)
        layout.addWidget(self.label)
        layout.addStretch()

    def set_text(self, text):
        self.label.setText(text)