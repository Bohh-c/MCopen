"""主窗口 - 侧边栏导航 + 页面切换 + 自适应布局 + i18n"""

import os
import json

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QComboBox, QScrollArea,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from gui.theme import THEMES, DEFAULT_THEME, apply_theme
from gui.home_page import HomePage
from gui.download_page import DownloadPage
from gui.account_page import AccountPage
from gui.mod_page import ModPage
from gui.mod_download_page import ModDownloadPage
from gui.loader_page import LoaderPage
from gui.multiplayer_page import MultiplayerPage
from gui.server_page import ServerPage
from gui.widgets import Card, SectionTitle, SubTitle
from gui.i18n import tr, set_lang, LANG as i18n_lang


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "launcher_settings.json")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("app_title"))
        self.resize(1080, 720)
        self.setMinimumSize(820, 580)

        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.current_theme = DEFAULT_THEME
        self.ui_lang = "zh"
        self._load_settings()

        self._build_sidebar()
        self._build_pages()
        self._switch_page(0)

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                self.current_theme = settings.get("theme", DEFAULT_THEME)
                self.game_root = settings.get("game_root", self.game_root)
                self.ui_lang = settings.get("ui_lang", "zh")
                set_lang(self.ui_lang)

    def _save_settings(self):
        settings = {
            "theme": self.current_theme,
            "game_root": self.game_root,
            "ui_lang": self.ui_lang,
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def _rebuild_sidebar(self):
        self._build_sidebar()
        central = self.centralWidget()
        central_layout = central.layout()
        old_sidebar = central_layout.itemAt(0).widget()
        central_layout.removeWidget(old_sidebar)
        old_sidebar.deleteLater()
        central_layout.insertWidget(0, self.sidebar_widget)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(4)

        logo_label = QLabel("MCOpen")
        logo_font = QFont()
        logo_font.setPointSize(22)
        logo_font.setBold(True)
        logo_label.setFont(logo_font)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("padding: 12px 0; margin-bottom: 8px;")
        sidebar_layout.addWidget(logo_label)

        ver_label = QLabel(tr("version"))
        ver_label.setAlignment(Qt.AlignCenter)
        ver_label.setStyleSheet("color: palette(mid); font-size: 11px; margin-bottom: 16px;")
        sidebar_layout.addWidget(ver_label)

        self.nav_buttons = []
        nav_items = [
            (tr("nav_home"), 0),
            (tr("nav_download"), 1),
            (tr("nav_loader"), 2),
            (tr("nav_mod"), 3),
            (tr("nav_mod_download"), 4),
            (tr("nav_multiplayer"), 5),
            (tr("nav_server"), 6),
            (tr("nav_account"), 7),
            (tr("nav_log"), 8),
            (tr("nav_settings"), 9),
        ]

        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            self.nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        footer = QLabel(tr("footer"))
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: palette(mid); font-size: 10px; padding: 10px 0;")
        sidebar_layout.addWidget(footer)

        self.sidebar_widget = sidebar

    def _build_pages(self):
        self.page_stack = QStackedWidget()

        self.home_page = HomePage()
        self.home_page.launch_worker.game_started_signal.connect(self._on_game_started)
        self.home_page.switch_to_account.connect(lambda: self._switch_page(7))
        self.page_stack.addWidget(self.home_page)

        self.download_page = DownloadPage()
        self.download_page.set_game_root(self.game_root)
        self.page_stack.addWidget(self.download_page)

        self.loader_page = LoaderPage()
        self.loader_page.set_game_root(self.game_root)
        self.page_stack.addWidget(self.loader_page)

        self.mod_page = ModPage()
        self.mod_page.set_game_root(self.game_root)
        self.page_stack.addWidget(self.mod_page)

        self.mod_download_page = ModDownloadPage()
        self.mod_download_page.set_game_root(self.game_root)
        self.page_stack.addWidget(self.mod_download_page)

        self.multiplayer_page = MultiplayerPage()
        self.page_stack.addWidget(self.multiplayer_page)

        self.server_page = ServerPage()
        self.page_stack.addWidget(self.server_page)

        self.account_page = AccountPage()
        self.account_page.accounts_changed.connect(self._on_accounts_changed)
        self.page_stack.addWidget(self.account_page)

        from gui.log_page import LogPage
        self.log_page = LogPage()
        self.page_stack.addWidget(self.log_page)

        self.settings_page = self._build_settings_page()
        self.page_stack.addWidget(self.settings_page)

        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.sidebar_widget)
        central_layout.addWidget(self.page_stack)
        self.setCentralWidget(central)

    def _on_accounts_changed(self):
        self.home_page.refresh_current_account()

    def _rebuild_all_pages(self):
        current_idx = self.page_stack.currentIndex()
        self.page_stack.removeWidget(self.home_page)
        self.page_stack.removeWidget(self.download_page)
        self.page_stack.removeWidget(self.loader_page)
        self.page_stack.removeWidget(self.mod_page)
        self.page_stack.removeWidget(self.mod_download_page)
        self.page_stack.removeWidget(self.multiplayer_page)
        self.page_stack.removeWidget(self.server_page)
        self.page_stack.removeWidget(self.account_page)
        self.page_stack.removeWidget(self.log_page)
        self.page_stack.removeWidget(self.settings_page)

        self.home_page = HomePage()
        self.home_page.launch_worker.game_started_signal.connect(self._on_game_started)
        self.home_page.switch_to_account.connect(lambda: self._switch_page(7))
        self.page_stack.insertWidget(0, self.home_page)

        self.download_page = DownloadPage()
        self.download_page.set_game_root(self.game_root)
        self.page_stack.insertWidget(1, self.download_page)

        self.loader_page = LoaderPage()
        self.loader_page.set_game_root(self.game_root)
        self.page_stack.insertWidget(2, self.loader_page)

        self.mod_page = ModPage()
        self.mod_page.set_game_root(self.game_root)
        self.page_stack.insertWidget(3, self.mod_page)

        self.mod_download_page = ModDownloadPage()
        self.mod_download_page.set_game_root(self.game_root)
        self.page_stack.insertWidget(4, self.mod_download_page)

        self.multiplayer_page = MultiplayerPage()
        self.page_stack.insertWidget(5, self.multiplayer_page)

        self.server_page = ServerPage()
        self.page_stack.insertWidget(6, self.server_page)

        self.account_page = AccountPage()
        self.account_page.accounts_changed.connect(self._on_accounts_changed)
        self.page_stack.insertWidget(7, self.account_page)

        from gui.log_page import LogPage
        self.log_page = LogPage()
        self.page_stack.insertWidget(8, self.log_page)

        self.settings_page = self._build_settings_page()
        self.page_stack.insertWidget(9, self.settings_page)

        self.page_stack.setCurrentIndex(current_idx)

    def _build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle(tr("settings_title"))
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        sub = SubTitle(tr("settings_subtitle"))
        layout.addWidget(sub)

        card1 = Card()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setSpacing(12)

        card1_title = QLabel(tr("settings_appearance"))
        card1_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        card1_layout.addWidget(card1_title)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel(tr("settings_current_theme") + ":"))
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumHeight(32)
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme.name, key)
        idx = self.theme_combo.findData(self.current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        card1_layout.addLayout(theme_row)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("settings_ui_lang") + ":"))
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumHeight(32)
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("English", "en")
        idx = self.lang_combo.findData(self.ui_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_ui_lang_changed)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        card1_layout.addLayout(lang_row)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)
        for key, theme in THEMES.items():
            color_box = QLabel()
            color_box.setFixedSize(60, 40)
            color_box.setStyleSheet(f"""
                background-color: {theme.accent};
                border-radius: 8px;
                border: 2px solid {theme.bg_secondary};
            """)
            color_box.setAlignment(Qt.AlignCenter)
            color_box.setText(theme.name[:1])
            color_box.setStyleSheet(color_box.styleSheet() + "color: white; font-weight: bold;")
            preview_row.addWidget(color_box)
        preview_row.addStretch()
        card1_layout.addLayout(preview_row)

        layout.addWidget(card1)

        card2 = Card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(8)

        about_title = QLabel(tr("settings_about"))
        about_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        card2_layout.addWidget(about_title)

        about_text = QLabel(tr("settings_about_text"))
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: palette(mid); line-height: 1.6;")
        card2_layout.addWidget(about_text)

        layout.addWidget(card2)
        layout.addStretch()

        return page

    def _switch_page(self, index):
        self.page_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.setObjectName("navBtnActive")
            else:
                btn.setObjectName("navBtn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
        if index == 8:
            self.log_page.set_game_root(self.game_root)

    def _on_game_started(self):
        self._switch_page(8)

    def _on_theme_changed(self):
        theme_key = self.theme_combo.currentData()
        if theme_key and theme_key != self.current_theme:
            self.current_theme = theme_key
            self._save_settings()
            from PyQt5.QtWidgets import QApplication
            apply_theme(QApplication.instance(), theme_key)

    def _on_ui_lang_changed(self):
        lang = self.lang_combo.currentData()
        if lang and lang != self.ui_lang:
            self.ui_lang = lang
            set_lang(lang)
            self._save_settings()
            self.setWindowTitle(tr("app_title"))
            self._rebuild_sidebar()
            self._rebuild_all_pages()
            self._switch_page(self.page_stack.currentIndex())

    def apply_theme(self, app):
        apply_theme(app, self.current_theme)

    def closeEvent(self, event):
        self._save_settings()
        try:
            self.multiplayer_page.worker.stop_node()
        except Exception:
            pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.width()
        sidebar_width = min(max(180, width // 6), 240)
        self.sidebar_widget.setFixedWidth(sidebar_width)
