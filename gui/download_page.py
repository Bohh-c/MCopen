import os
import threading

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QProgressBar, QListWidget,
    QListWidgetItem, QMessageBox, QScrollArea, QFrame,
)
from PyQt5.QtGui import QFont

from gui.widgets import SectionTitle, SubTitle, StatusBadge
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

        content = QWidget()
        scroll_area.setWidget(content)

        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle("版本下载")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("待获取", "info")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle("从官方源下客户端或服务端")
        main_layout.addWidget(sub)

        block1_label = QLabel("下载设置")
        block1_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block1_label)

        block1 = QFrame()
        block1.setObjectName("card")
        block1.setFrameShape(QFrame.StyledPanel)
        block1_layout = QVBoxLayout(block1)
        block1_layout.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.setSpacing(10)
        type_row.addWidget(QLabel("下载类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["客户端", "服务端"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        block1_layout.addLayout(type_row)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)
        dir_row.addWidget(QLabel("保存目录:"))
        self.save_dir_edit = QLineEdit(self.game_root)
        dir_row.addWidget(self.save_dir_edit, 1)
        browse_btn = QPushButton("浏览")
        browse_btn.setObjectName("btnSecondary")
        browse_btn.clicked.connect(self._select_save_dir)
        dir_row.addWidget(browse_btn)
        block1_layout.addLayout(dir_row)

        main_layout.addWidget(block1)

        block2_label = QLabel("版本选择")
        block2_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block2_label)

        block2 = QFrame()
        block2.setObjectName("card")
        block2.setFrameShape(QFrame.StyledPanel)
        block2_layout = QVBoxLayout(block2)
        block2_layout.setSpacing(12)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        search_row.addWidget(QLabel("搜索版本:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输版本号，比如 1.21")
        self.search_edit.textChanged.connect(self._filter_versions)
        search_row.addWidget(self.search_edit, 1)
        block2_layout.addLayout(search_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        filter_row.addWidget(QLabel("类型筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "正式版", "快照版"])
        self.filter_combo.currentIndexChanged.connect(self._filter_versions)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()

        self.fetch_btn = QPushButton("刷出来")
        self.fetch_btn.setObjectName("btnSecondary")
        self.fetch_btn.clicked.connect(self._fetch_versions)
        filter_row.addWidget(self.fetch_btn)
        block2_layout.addLayout(filter_row)

        self.version_list = QListWidget()
        self.version_list.setMinimumHeight(250)
        self.version_list.setMaximumHeight(400)
        self.version_list.setAlternatingRowColors(True)
        self.version_list.itemClicked.connect(self._on_version_selected)
        block2_layout.addWidget(self.version_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.download_btn = QPushButton("下这个")
        dl_font = QFont()
        dl_font.setPointSize(12)
        dl_font.setBold(True)
        self.download_btn.setFont(dl_font)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn)
        block2_layout.addLayout(btn_row)

        main_layout.addWidget(block2)

        block3_label = QLabel("进度")
        block3_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block3_label)

        block3 = QFrame()
        block3.setObjectName("card")
        block3.setFrameShape(QFrame.StyledPanel)
        block3_layout = QVBoxLayout(block3)
        block3_layout.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        block3_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("等着呢...")
        block3_layout.addWidget(self.progress_label)

        main_layout.addWidget(block3)
        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

        self.resizeEvent = self._on_resize

    def _on_resize(self, event):
        height = event.size().height()
        header_height = 120
        card1_height = 140
        card3_height = 100
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
        self.progress_label.setText("连 Mojang 中...")
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
        self.download_btn.setText(f"下 {v['id']}")

    def _start_download(self):
        current = self.version_list.currentItem()
        if not current:
            return

        save_dir = self.save_dir_edit.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "设个保存目录")
            return

        version_info = current.data(Qt.UserRole)
        version_id = version_info["id"]

        self.download_btn.setEnabled(False)
        self.fetch_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_badge.set_status("info", "下着呢...")

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
            self.status_badge.set_status("normal", "完事")
            QMessageBox.information(self, "下好了", msg)
        else:
            self.status_badge.set_status("error", "完了")
            QMessageBox.critical(self, "下炸了", msg)