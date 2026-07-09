"""主题系统 - 3种可切换颜色主题 + 自适应布局"""


#待确定：是否保留主题切换


from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor


class ThemeColors:
    def __init__(self, name, bg_primary, bg_secondary, bg_tertiary,
                 text_primary, text_secondary, text_disabled,
                 border_color, accent, accent_hover, accent_pressed,
                 accent_alpha, danger, danger_hover, scrollbar_handle):
        self.name = name
        self.bg_primary = bg_primary
        self.bg_secondary = bg_secondary
        self.bg_tertiary = bg_tertiary
        self.text_primary = text_primary
        self.text_secondary = text_secondary
        self.text_disabled = text_disabled
        self.border_color = border_color
        self.accent = accent
        self.accent_hover = accent_hover
        self.accent_pressed = accent_pressed
        self.accent_alpha = accent_alpha
        self.danger = danger
        self.danger_hover = danger_hover
        self.scrollbar_handle = scrollbar_handle


DARK = ThemeColors(
    "暗夜黑",
    "#1a1a2e", "#16213e", "#0f3460",
    "#e0e0e0", "#8892b0", "#555555",
    "#2a2a4a", "#e94560", "#ff6b81", "#c0392b",
    "#E9456020", "#e74c3c", "#c0392b", "#3a3a5a"
)

LIGHT = ThemeColors(
    "素月白",
    "#f0f2f5", "#ffffff", "#e4e6eb",
    "#1c1e21", "#65676b", "#bcc0c4",
    "#dadde1", "#6c5ce7", "#a29bfe", "#5a4bd1",
    "#6C5CE720", "#e74c3c", "#c0392b", "#cccccc"
)

OCEAN = ThemeColors(
    "海洋蓝",
    "#0c1929", "#112240", "#1a365d",
    "#ccd6f6", "#64ffda", "#4a5568",
    "#2d4a7a", "#00b4d8", "#48cae4", "#0096c7",
    "#00B4D820", "#e74c3c", "#c0392b", "#2d4a7a"
)

THEMES = {"dark": DARK, "light": LIGHT, "ocean": OCEAN}
DEFAULT_THEME = "dark"


def build_stylesheet(c):
    return f"""
        QMainWindow {{
            background-color: {c.bg_primary};
        }}
        QWidget {{
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            font-size: 13px;
        }}
        QLabel {{
            color: {c.text_primary};
            background: transparent;
        }}
        QLineEdit {{
            background-color: {c.bg_tertiary};
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 6px;
            padding: 8px 12px;
            selection-background-color: {c.accent};
        }}
        QLineEdit:focus {{
            border: 1px solid {c.accent};
        }}
        QComboBox {{
            background-color: {c.bg_tertiary};
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 6px;
            padding: 8px 12px;
            min-height: 20px;
        }}
        QComboBox:hover {{
            border: 1px solid {c.accent};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid {c.text_secondary};
            margin-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c.bg_secondary};
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 4px;
            selection-background-color: {c.accent};
            selection-color: #FFFFFF;
            outline: none;
        }}
        QSpinBox {{
            background-color: {c.bg_tertiary};
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 6px;
            padding: 8px 12px;
        }}
        QSpinBox:focus {{
            border: 1px solid {c.accent};
        }}
        QPushButton {{
            background-color: {c.accent};
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {c.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {c.accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {c.bg_tertiary};
            color: {c.text_disabled};
        }}
        QPushButton#btnSecondary {{
            background-color: transparent;
            color: {c.accent};
            border: 1.5px solid {c.accent};
            font-weight: bold;
        }}
        QPushButton#btnSecondary:hover {{
            background-color: {c.accent_alpha};
        }}
        QPushButton#btnDanger {{
            background-color: {c.danger};
            color: #FFFFFF;
        }}
        QPushButton#btnDanger:hover {{
            background-color: {c.danger_hover};
        }}
        QPushButton#navBtn {{
            background-color: transparent;
            color: {c.text_secondary};
            border: none;
            border-radius: 8px;
            padding: 10px 16px;
            text-align: left;
            font-weight: normal;
            font-size: 14px;
        }}
        QPushButton#navBtn:hover {{
            background-color: {c.accent_alpha};
            color: {c.text_primary};
        }}
        QPushButton#navBtnActive {{
            background-color: {c.accent};
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 10px 16px;
            text-align: left;
            font-weight: bold;
            font-size: 14px;
        }}
        QFrame#card {{
            background-color: {c.bg_secondary};
            border: 1px solid {c.border_color};
            border-radius: 12px;
            padding: 16px;
        }}
        QWidget#sidebar {{
            background-color: {c.bg_primary};
            border-right: 1px solid {c.border_color};
        }}
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollBar:vertical {{
            background-color: {c.bg_primary};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {c.scrollbar_handle};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {c.text_secondary};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background-color: {c.bg_primary};
            height: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {c.scrollbar_handle};
            border-radius: 4px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {c.text_secondary};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QProgressBar {{
            background-color: {c.bg_tertiary};
            border: none;
            border-radius: 6px;
            text-align: center;
            color: {c.text_primary};
            font-weight: bold;
            height: 20px;
        }}
        QProgressBar::chunk {{
            background-color: {c.accent};
            border-radius: 6px;
        }}
        QSlider::groove:horizontal {{
            background-color: {c.bg_tertiary};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background-color: {c.accent};
            width: 16px;
            height: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background-color: {c.accent_hover};
        }}
        QSlider::sub-page:horizontal {{
            background-color: {c.accent};
            border-radius: 3px;
        }}
        QListWidget {{
            background-color: {c.bg_tertiary};
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 6px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 6px 12px;
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background-color: {c.accent};
            color: #FFFFFF;
        }}
        QListWidget::item:hover {{
            background-color: {c.accent_alpha};
        }}
        QGroupBox {{
            font-weight: bold;
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }}
        QTextEdit {{
            background-color: {c.bg_tertiary};
            color: {c.text_primary};
            border: 1px solid {c.border_color};
            border-radius: 6px;
            padding: 8px;
        }}
    """


def apply_theme(app, theme_key):
    c = THEMES.get(theme_key, DARK)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(c.bg_primary))
    palette.setColor(QPalette.WindowText, QColor(c.text_primary))
    palette.setColor(QPalette.Base, QColor(c.bg_secondary))
    palette.setColor(QPalette.AlternateBase, QColor(c.bg_tertiary))
    palette.setColor(QPalette.ToolTipBase, QColor(c.bg_secondary))
    palette.setColor(QPalette.ToolTipText, QColor(c.text_primary))
    palette.setColor(QPalette.Text, QColor(c.text_primary))
    palette.setColor(QPalette.Button, QColor(c.bg_tertiary))
    palette.setColor(QPalette.ButtonText, QColor(c.text_primary))
    palette.setColor(QPalette.BrightText, QColor(c.accent))
    palette.setColor(QPalette.Link, QColor(c.accent))
    palette.setColor(QPalette.Highlight, QColor(c.accent))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(c.text_disabled))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(c.text_disabled))
    app.setPalette(palette)
    ss = build_stylesheet(c)
    app.setStyleSheet(ss)
    for widget in app.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    return ss