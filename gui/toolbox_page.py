import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QMessageBox, QTextEdit, QFrame,
)
from PyQt5.QtGui import QFont, QPalette, QColor

from gui.widgets import SectionTitle, SubTitle, make_tool_row
from core.cli import get_project_root


class ToolboxPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

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
        title = SectionTitle("工具箱")
        header.addWidget(title)
        header.addStretch()
        main_layout.addLayout(header)

        sub = SubTitle("一些顺手的小工具，按需使用")
        main_layout.addWidget(sub)

        tools_layout = QVBoxLayout()
        tools_layout.setSpacing(12)

        tools_layout.addLayout(make_tool_row(
            "种子世界管理器",
            "把你收藏的好种子存起来，一键导入，不用再翻浏览器了。",
            "打开",
            self._open_seed_manager,
            "#4a7db5"
        ))

        tools_layout.addLayout(make_tool_row(
            "世界备份",
            "把你的存档打包带走，防手滑防崩溃。",
            "备份",
            self._open_world_backup,
            "#c48a4a"
        ))

        main_layout.addLayout(tools_layout)
        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

    def _open_seed_manager(self):
        QMessageBox.information(self, "种子世界管理器", "这个功能正在鼓捣中，下次更新就能用了。")

    def _open_world_backup(self):
        saves_dir = Path(get_project_root()) / ".minecraft" / "saves"
        if not saves_dir.exists():
            QMessageBox.warning(self, "提示", "还没找到存档目录，你先玩一会儿游戏再说吧。")
            return
        QMessageBox.information(self, "世界备份", f"存档在这：{saves_dir}\n\n备份功能还在写，先手动拷吧。")