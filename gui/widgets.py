"""自定义Widget组件 - 包含行布局工具函数"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton
from PyQt5.QtGui import QFont


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.StyledPanel)


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


def make_tool_row(title, desc, btn_text, callback, color_hex):
    """生成一行功能项：色条 + 标题/描述 + 按钮"""
    row = QHBoxLayout()
    row.setSpacing(12)

    color_bar = QLabel()
    color_bar.setFixedSize(6, 48)
    color_bar.setStyleSheet(f"background-color: {color_hex}; border-radius: 3px;")
    row.addWidget(color_bar)

    text_widget = QWidget()
    text_layout = QVBoxLayout(text_widget)
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(2)

    title_label = QLabel(title)
    title_label.setFont(QFont("", 12, QFont.Bold))
    text_layout.addWidget(title_label)

    desc_label = QLabel(desc)
    desc_label.setWordWrap(True)
    desc_label.setStyleSheet("color: palette(mid); font-size: 11px;")
    text_layout.addWidget(desc_label)

    row.addWidget(text_widget, 1)

    btn = QPushButton(btn_text)
    btn.setMinimumHeight(34)
    btn.setMinimumWidth(100)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {color_hex};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{ background-color: {color_hex}dd; }}
        QPushButton:pressed {{ background-color: {color_hex}bb; }}
    """)
    btn.clicked.connect(callback)
    row.addWidget(btn)

    return row


def make_tool_row_with_widget(title, desc, widget, color_hex):
    """生成一行：色条 + 标题/描述 + 自定义控件（如 QComboBox 或 QLineEdit）"""
    row = QHBoxLayout()
    row.setSpacing(12)

    color_bar = QLabel()
    color_bar.setFixedSize(6, 48)
    color_bar.setStyleSheet(f"background-color: {color_hex}; border-radius: 3px;")
    row.addWidget(color_bar)

    text_widget = QWidget()
    text_layout = QVBoxLayout(text_widget)
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(2)

    title_label = QLabel(title)
    title_label.setFont(QFont("", 12, QFont.Bold))
    text_layout.addWidget(title_label)

    desc_label = QLabel(desc)
    desc_label.setWordWrap(True)
    desc_label.setStyleSheet("color: palette(mid); font-size: 11px;")
    text_layout.addWidget(desc_label)

    row.addWidget(text_widget, 1)

    row.addWidget(widget)

    return row