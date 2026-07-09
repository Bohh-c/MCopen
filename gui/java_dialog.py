"""Java选择对话框"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton,
)
from PyQt5.QtGui import QFont

from gui.java_detector import get_java_version


class JavaDialog(QDialog):
    def __init__(self, java_paths, parent=None):
        super().__init__(parent)
        self.java_paths = java_paths
        self.selected_path = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("选择 Java")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        label = QLabel("检测到多个 Java 版本，请选择一个:")
        font = QFont()
        font.setPointSize(12)
        label.setFont(font)
        layout.addWidget(label)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(200)
        for path in self.java_paths:
            ver = get_java_version(path)
            item = QListWidgetItem(f"{ver}\n{path}")
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("btnSecondary")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def accept(self):
        idx = self.list_widget.currentRow()
        if idx >= 0:
            self.selected_path = self.java_paths[idx]
        super().accept()