"""下载页面 - MC版本下载（客户端/服务端）"""

import os
import threading

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize, QEvent
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QCompleter, QScrollArea,
)
from PyQt5.QtGui import QFont

from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge
from gui.downloader import (
    fetch_version_manifest, find_version,
    download_client, download_server,
)


class DownloadWorker(QObject):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)
    version_list_signal = pyqtSignal(list)

    def fetch_versions(self):
        try:
            manifest = fetch_version_manifest()
            versions = manifest.get("versions", [])
            versions_sorted = sorted(versions, key=lambda v: v.get("releaseTime", ""), reverse=True)
            self.version_list_signal.emit(versions_sorted)
        except Exception as e:
            self.finished_signal.emit(False, f"获取版本列表失败: {e}")

    def download(self, version_id, save_dir, download_type):
        try:
            def cb(pct, info):
                if isinstance(info, int):
                    size_mb = info / 1048576
                    self.progress_signal.emit(pct, f"下载中 ({pct}%) {size_mb:.1f} MB")
                else:
                    self.progress_signal.emit(pct, info)

            if download_type == "client":
                success, msg = download_client(version_id, save_dir, cb)
            else:
                success, msg = download_server(version_id, save_dir, cb)

            if success:
                self.progress_signal.emit(100, msg)
            self.finished_signal.emit(success, msg)
        except Exception as e:
            self.finished_signal.emit(False, f"下载失败: {e}")


class DownloadPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from core.cli import get_project_root
        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.server_dir = os.path.join(get_project_root(), "server")
        self.versions = []
        self.download_type = "client"
        self.worker = DownloadWorker()
        self.worker.version_list_signal.connect(self._on_versions_loaded)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self._build_ui()

    def set_game_root(self, path):
        self.game_root = path

    def _build_ui(self):
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        main_layout = QVBoxLayout(content_widget)
        self._main_layout = main_layout
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle("版本下载")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("待获取", "info")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle("从 Mojang 官方源下载 Minecraft 客户端或服务端")
        main_layout.addWidget(sub)

        card1 = Card()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setSpacing(14)

        card1_title = QLabel("下载设置")
        card1_font = QFont()
        card1_font.setPointSize(13)
        card1_font.setBold(True)
        card1_title.setFont(card1_font)
        card1_layout.addWidget(card1_title)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("下载类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["客户端 (Client)", "服务端 (Server)"])
        self.type_combo.setMinimumHeight(36)
        type_font = QFont()
        type_font.setPointSize(11)
        self.type_combo.setFont(type_font)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()

        save_dir_row = QHBoxLayout()
        save_dir_row.addWidget(QLabel("保存目录:"))
        self.save_dir_edit = QLineEdit(self.game_root)
        self.save_dir_edit.setMinimumHeight(36)
        self.save_dir_edit.setFont(type_font)
        save_dir_row.addWidget(self.save_dir_edit)
        browse_btn = QPushButton("浏  览")
        browse_btn.setObjectName("btnSecondary")
        browse_btn.setFixedWidth(80)
        browse_btn.setMinimumHeight(36)
        browse_btn.setFont(type_font)
        browse_btn.clicked.connect(self._select_save_dir)
        save_dir_row.addWidget(browse_btn)

        card1_layout.addLayout(type_row)
        card1_layout.addLayout(save_dir_row)
        main_layout.addWidget(card1)

        card2 = Card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(14)

        card2_title = QLabel("选择版本")
        card2_title.setFont(card1_font)
        card2_layout.addWidget(card2_title)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("搜索版本:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入版本号搜索，如 1.21、26.2...")
        self.search_edit.setMinimumHeight(32)
        self.search_edit.setFont(type_font)
        self.search_edit.textChanged.connect(self._filter_versions)
        search_row.addWidget(self.search_edit)
        search_row.addStretch()
        card2_layout.addLayout(search_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("类型筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "正式版 (release)", "快照版 (snapshot)"])
        self.filter_combo.setMinimumHeight(32)
        self.filter_combo.setFont(type_font)
        self.filter_combo.currentIndexChanged.connect(self._filter_versions)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()

        self.fetch_btn = QPushButton("获取版本列表")
        self.fetch_btn.setObjectName("btnSecondary")
        self.fetch_btn.setMinimumHeight(36)
        self.fetch_btn.setFont(type_font)
        self.fetch_btn.clicked.connect(self._fetch_versions)
        filter_row.addWidget(self.fetch_btn)
        card2_layout.addLayout(filter_row)

        self.version_list = QListWidget()
        self.version_list.setMinimumHeight(250)
        self.version_list.setMaximumHeight(600)
        self.version_list.setFont(type_font)
        self.version_list.setAlternatingRowColors(True)
        self.version_list.itemClicked.connect(self._on_version_selected)
        card2_layout.addWidget(self.version_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.download_btn = QPushButton("下载选中版本")
        self.download_btn.setMinimumHeight(40)
        self.download_btn.setMinimumWidth(160)
        dl_font = QFont()
        dl_font.setPointSize(12)
        dl_font.setBold(True)
        self.download_btn.setFont(dl_font)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn)
        card2_layout.addLayout(btn_row)

        main_layout.addWidget(card2)

        card3 = Card()
        card3_layout = QVBoxLayout(card3)
        card3_layout.setSpacing(12)

        progress_title = QLabel("下载进度")
        progress_title.setFont(card1_font)
        card3_layout.addWidget(progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(24)
        card3_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("等待下载任务...")
        self.progress_label.setFont(type_font)
        card3_layout.addWidget(self.progress_label)

        main_layout.addWidget(card3)
        main_layout.addStretch()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)

        self.resizeEvent = self._on_resize

    def _on_resize(self, event):
        height = event.size().height()
        header_height = 120
        card1_height = 140
        card3_height = 120
        available = height - header_height - card1_height - card3_height - 80
        self.version_list.setMaximumHeight(max(250, available))
        event.accept()

    def _on_type_changed(self):
        idx = self.type_combo.currentIndex()
        self.download_type = "client" if idx == 0 else "server"
        if self.download_type == "server":
            self.save_dir_edit.setText(self.server_dir)
        else:
            self.save_dir_edit.setText(self.game_root)

    def _select_save_dir(self):
        from PyQt5.QtWidgets import QFileDialog
        selected = QFileDialog.getExistingDirectory(
            self, "选择保存目录", self.save_dir_edit.text()
        )
        if selected:
            self.save_dir_edit.setText(selected)

    def _fetch_versions(self):
        self.fetch_btn.setEnabled(False)
        self.status_badge.set_status("info", "获取中...")
        self.progress_label.setText("正在连接 Mojang API...")
        self.versions = []
        self.version_list.clear()
        thread = threading.Thread(target=self.worker.fetch_versions, daemon=True)
        thread.start()

    def _on_versions_loaded(self, versions):
        self.versions = versions
        self._filter_versions()
        self.fetch_btn.setEnabled(True)
        self.status_badge.set_status("normal", f"{len(versions)}个版本")

    def _filter_versions(self):
        self.version_list.clear()
        filter_type = self.filter_combo.currentText()
        search_text = self.search_edit.text().strip().lower()

        for v in self.versions:
            vtype = v.get("type", "")
            version_id = v["id"].lower()

            if search_text and search_text not in version_id:
                continue

            if "正式版" in filter_type and vtype != "release":
                continue
            if "快照版" in filter_type and vtype != "snapshot":
                continue

            item = QListWidgetItem()
            item.setText(f"{v['id']}  [{vtype}]  ({v.get('releaseTime', '')[:10]})")
            item.setData(Qt.UserRole, v)
            item.setSizeHint(item.sizeHint() + QSize(0, 6))
            self.version_list.addItem(item)

    def _on_version_selected(self, item):
        self.download_btn.setEnabled(True)
        v = item.data(Qt.UserRole)
        self.download_btn.setText(f"下载 {v['id']}")

    def _start_download(self):
        current = self.version_list.currentItem()
        if not current:
            return

        save_dir = self.save_dir_edit.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请设置保存目录")
            return

        version_info = current.data(Qt.UserRole)
        version_id = version_info["id"]

        self.download_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_badge.set_status("info", "下载中...")

        thread = threading.Thread(
            target=self.worker.download,
            args=(version_id, save_dir, self.download_type),
            daemon=True
        )
        thread.start()

    def _on_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.progress_label.setText(text)

    def _on_finished(self, success, msg):
        self.download_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        if success:
            self.status_badge.set_status("normal", "完成")
            QMessageBox.information(self, "下载完成", msg)
        else:
            self.status_badge.set_status("error", "失败")
            QMessageBox.critical(self, "下载失败", msg)