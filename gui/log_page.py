"""日志页面 - 查看和导出游戏日志"""

import os
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox, QComboBox, QFileDialog,
)

from gui.widgets import Card, SectionTitle, SubTitle


class LogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_root = ""
        self._build_ui()

    def set_game_root(self, path):
        self.game_root = path
        self._scan_log_files()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle("游戏日志")
        header.addWidget(title)
        header.addStretch()
        main_layout.addLayout(header)

        sub = SubTitle("查看和导出 Minecraft 游戏日志")
        main_layout.addWidget(sub)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        top_row = QHBoxLayout()
        self.file_combo = QComboBox()
        self.file_combo.setMinimumHeight(32)
        self.file_combo.currentIndexChanged.connect(self._load_selected_log)
        top_row.addWidget(self.file_combo)

        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setObjectName("btnSecondary")
        self.refresh_btn.setMinimumHeight(32)
        self.refresh_btn.clicked.connect(self._scan_log_files)
        top_row.addWidget(self.refresh_btn)

        top_row.addStretch()
        card_layout.addLayout(top_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(400)
        font = self.log_text.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.log_text.setFont(font)
        card_layout.addWidget(self.log_text)

        btn_row = QHBoxLayout()
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setObjectName("btnSecondary")
        self.clear_btn.clicked.connect(self._clear_log)
        btn_row.addWidget(self.clear_btn)
        self.copy_btn = QPushButton("复制日志")
        self.copy_btn.setObjectName("btnSecondary")
        self.copy_btn.clicked.connect(self._copy_log)
        btn_row.addWidget(self.copy_btn)
        self.export_btn = QPushButton("导出日志")
        self.export_btn.setObjectName("btnSecondary")
        self.export_btn.clicked.connect(self._export_log)
        btn_row.addWidget(self.export_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def _scan_log_files(self):
        self.file_combo.clear()
        if not self.game_root:
            return

        logs_dir = os.path.join(self.game_root, "logs")
        if not os.path.exists(logs_dir):
            return

        log_files = []
        for f in os.listdir(logs_dir):
            if f.endswith(".log"):
                fp = os.path.join(logs_dir, f)
                mt = os.path.getmtime(fp)
                log_files.append((mt, f))

        log_files.sort(key=lambda x: x[0], reverse=True)
        for mt, fname in log_files:
            date_str = datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M")
            self.file_combo.addItem(f"{fname} ({date_str})", fname)

        if self.file_combo.count() > 0:
            self._load_selected_log(0)

    def _load_selected_log(self, index):
        if index < 0:
            return

        fname = self.file_combo.itemData(index)
        if not fname:
            return

        logs_dir = os.path.join(self.game_root, "logs")
        fp = os.path.join(logs_dir, fname)

        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.log_text.setPlainText(content)
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self.log_text.setPlainText(f"读取日志失败: {e}")

    def _clear_log(self):
        self.log_text.clear()

    def _copy_log(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.log_text.toPlainText())

    def _export_log(self):
        log_text = self.log_text.toPlainText()
        if not log_text:
            QMessageBox.warning(self, "提示", "日志为空")
            return

        default_path = os.path.join(
            os.path.expanduser("~"),
            f"minecraft_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        selected, _ = QFileDialog.getSaveFileName(
            self, "保存日志", default_path,
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if selected:
            with open(selected, "w", encoding="utf-8") as f:
                f.write(log_text)
            QMessageBox.information(self, "导出成功", f"日志已保存到:\n{selected}")