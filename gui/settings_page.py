import os
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QFileDialog,
    QSlider, QMessageBox, QFrame, QScrollArea,
)
from PyQt5.QtGui import QFont

from gui.widgets import SectionTitle, SubTitle
from gui.theme import THEMES, apply_theme
from gui.java_detector import find_java_paths
from gui.i18n import tr, set_lang


SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "launcher_settings.json")


class SettingsPage(QWidget):
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = "dark"
        self.ui_lang = "zh"
        self.java_path = ""
        self.mem_min = 2048
        self.mem_max = 4096
        self.game_lang = "zh_cn"
        self._build_ui()
        self._load_settings_to_ui()

    def _load_settings_to_ui(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                self.current_theme = settings.get("theme", "dark")
                self.ui_lang = settings.get("ui_lang", "zh")
                self.java_path = settings.get("java_path", "")
                self.mem_min = settings.get("mem_min", 2048)
                self.mem_max = settings.get("mem_max", 4096)
                self.game_lang = settings.get("game_lang", "zh_cn")

        idx = self.theme_combo.findData(self.current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        idx = self.lang_combo.findData(self.ui_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.java_edit.setText(self.java_path)
        self.min_mem_slider.setValue(self.mem_min)
        self.max_mem_slider.setValue(self.mem_max)
        self.min_mem_label.setText(f"{self.mem_min} MB")
        self.max_mem_label.setText(f"{self.mem_max} MB")
        idx = self.game_lang_combo.findData(self.game_lang)
        if idx >= 0:
            self.game_lang_combo.setCurrentIndex(idx)

    def showEvent(self, event):
        self._load_settings_to_ui()
        super().showEvent(event)

    def _save_settings_to_file(self):
        settings = {
            "theme": self.theme_combo.currentData(),
            "ui_lang": self.lang_combo.currentData(),
            "java_path": self.java_edit.text().strip(),
            "mem_min": self.min_mem_slider.value(),
            "mem_max": self.max_mem_slider.value(),
            "game_lang": self.game_lang_combo.currentData(),
        }
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def _build_ui(self):
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        scroll_area.setWidget(content)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle("设置")
        header.addWidget(title)
        header.addStretch()
        main_layout.addLayout(header)

        sub = SubTitle("调外观、配 Java、分内存，全在这")
        main_layout.addWidget(sub)

        block1_label = QLabel("外观")
        block1_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block1_label)

        block1 = QFrame()
        block1.setObjectName("card")
        block1.setFrameShape(QFrame.StyledPanel)
        block1_layout = QVBoxLayout(block1)
        block1_layout.setSpacing(12)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("主题:"))
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumHeight(34)
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme.name, key)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        block1_layout.addLayout(theme_row)

        ui_lang_row = QHBoxLayout()
        ui_lang_row.addWidget(QLabel("界面语言:"))
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumHeight(34)
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(self._on_ui_lang_changed)
        ui_lang_row.addWidget(self.lang_combo)
        ui_lang_row.addStretch()
        block1_layout.addLayout(ui_lang_row)

        main_layout.addWidget(block1)

        block2_label = QLabel("Java 环境")
        block2_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block2_label)

        block2 = QFrame()
        block2.setObjectName("card")
        block2.setFrameShape(QFrame.StyledPanel)
        block2_layout = QVBoxLayout(block2)
        block2_layout.setSpacing(12)

        java_row = QHBoxLayout()
        self.java_edit = QLineEdit()
        self.java_edit.setPlaceholderText("Java 可执行文件路径")
        self.java_edit.setMinimumHeight(34)
        java_row.addWidget(self.java_edit, 1)

        java_btn = QPushButton("选择")
        java_btn.setObjectName("btnSecondary")
        java_btn.setMinimumHeight(34)
        java_btn.setMinimumWidth(80)
        java_btn.clicked.connect(self._select_java)
        java_row.addWidget(java_btn)

        detect_btn = QPushButton("自动检测")
        detect_btn.setObjectName("btnSecondary")
        detect_btn.setMinimumHeight(34)
        detect_btn.setMinimumWidth(100)
        detect_btn.clicked.connect(self._detect_java)
        java_row.addWidget(detect_btn)

        block2_layout.addLayout(java_row)

        main_layout.addWidget(block2)

        block3_label = QLabel("内存分配")
        block3_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block3_label)

        block3 = QFrame()
        block3.setObjectName("card")
        block3.setFrameShape(QFrame.StyledPanel)
        block3_layout = QVBoxLayout(block3)
        block3_layout.setSpacing(12)

        min_row = QHBoxLayout()
        min_row.addWidget(QLabel("最小内存:"))
        self.min_mem_slider = QSlider(Qt.Horizontal)
        self.min_mem_slider.setRange(512, 16384)
        self.min_mem_slider.setTickInterval(1024)
        self.min_mem_slider.setTickPosition(QSlider.TicksBelow)
        min_row.addWidget(self.min_mem_slider, 1)
        self.min_mem_label = QLabel("2048 MB")
        self.min_mem_label.setFixedWidth(80)
        self.min_mem_label.setAlignment(Qt.AlignRight)
        self.min_mem_slider.valueChanged.connect(
            lambda v: self.min_mem_label.setText(f"{v} MB")
        )
        min_row.addWidget(self.min_mem_label)
        block3_layout.addLayout(min_row)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("最大内存:"))
        self.max_mem_slider = QSlider(Qt.Horizontal)
        self.max_mem_slider.setRange(1024, 32768)
        self.max_mem_slider.setTickInterval(2048)
        self.max_mem_slider.setTickPosition(QSlider.TicksBelow)
        max_row.addWidget(self.max_mem_slider, 1)
        self.max_mem_label = QLabel("4096 MB")
        self.max_mem_label.setFixedWidth(80)
        self.max_mem_label.setAlignment(Qt.AlignRight)
        self.max_mem_slider.valueChanged.connect(
            lambda v: self.max_mem_label.setText(f"{v} MB")
        )
        max_row.addWidget(self.max_mem_label)
        block3_layout.addLayout(max_row)

        main_layout.addWidget(block3)

        block4_label = QLabel("游戏语言")
        block4_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block4_label)

        block4 = QFrame()
        block4.setObjectName("card")
        block4.setFrameShape(QFrame.StyledPanel)
        block4_layout = QVBoxLayout(block4)
        block4_layout.setSpacing(12)

        game_lang_row = QHBoxLayout()
        game_lang_row.addWidget(QLabel("游戏语言:"))
        self.game_lang_combo = QComboBox()
        self.game_lang_combo.setMinimumHeight(34)
        self.game_lang_combo.addItem("中文", "zh_cn")
        self.game_lang_combo.addItem("English", "en_us")
        game_lang_row.addWidget(self.game_lang_combo)
        game_lang_row.addStretch()
        block4_layout.addLayout(game_lang_row)

        main_layout.addWidget(block4)

        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("保存设置")
        save_btn.setMinimumHeight(40)
        save_btn.setMinimumWidth(140)
        save_btn.clicked.connect(self._save_and_notify)
        save_row.addWidget(save_btn)
        save_row.addStretch()
        main_layout.addLayout(save_row)

        block5_label = QLabel("关于")
        block5_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block5_label)

        block5 = QFrame()
        block5.setObjectName("card")
        block5.setFrameShape(QFrame.StyledPanel)
        block5_layout = QVBoxLayout(block5)
        block5_layout.setSpacing(8)

        about_text = QLabel(
            "MCOpen 是纯自研 Minecraft Java 版全能启动内核。\n"
            "支持全版本兼容、离线登录、多模组加载器、ZeroTier 联机。\n"
            "采用四层分层架构，GUI 与核心完全解耦。"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("color: palette(mid); line-height: 1.6;")
        block5_layout.addWidget(about_text)

        main_layout.addWidget(block5)

        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

    def _select_java(self):
        current_path = self.java_edit.text().strip()
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择 Java", current_path,
            "可执行文件 (*.exe *.bat *.cmd)"
        )
        if selected:
            self.java_edit.setText(selected)

    def _detect_java(self):
        paths = find_java_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "未检测到 Java，请手动安装")
            return
        if len(paths) == 1:
            self.java_edit.setText(paths[0])
            QMessageBox.information(self, "提示", f"已检测到 Java:\n{paths[0]}")
        else:
            from gui.java_dialog import JavaDialog
            dialog = JavaDialog(paths, self)
            if dialog.exec_():
                self.java_edit.setText(dialog.selected_path)

    def _on_theme_changed(self):
        theme_key = self.theme_combo.currentData()
        if theme_key and theme_key != self.current_theme:
            self.current_theme = theme_key
            from PyQt5.QtWidgets import QApplication
            apply_theme(QApplication.instance(), theme_key)

    def _on_ui_lang_changed(self):
        lang = self.lang_combo.currentData()
        if lang and lang != self.ui_lang:
            self.ui_lang = lang
            set_lang(lang)

    def _save_and_notify(self):
        self._save_settings_to_file()
        self.settings_saved.emit()
        QMessageBox.information(self, "提示", "设置已保存")