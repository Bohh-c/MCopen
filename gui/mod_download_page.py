import os
import threading
import requests
import urllib3

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QScrollArea, QMessageBox, QProgressBar, QFrame,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from core.mod_loader import scan_modrinth_mods, get_modrinth_versions, download_mod_file
from gui.widgets import SectionTitle, SubTitle, StatusBadge
from gui.i18n import tr

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SearchWorker(QObject):
    finished = pyqtSignal(list)

    def __init__(self, query, game_version, loader):
        super().__init__()
        self.query = query
        self.game_version = game_version
        self.loader = loader

    def run(self):
        mods = scan_modrinth_mods(self.query, self.game_version, self.loader)
        self.finished.emit(mods)


class DownloadWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path

    def run(self):
        def cb(pct, downloaded):
            self.progress.emit(pct, f"{downloaded // 1024} KB")
        success, result = download_mod_file(self.url, self.save_path, cb)
        self.finished.emit(success, result, self.save_path)


class ModDownloadPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.current_version = ""
        self.search_thread = None
        self.search_worker = None
        self.download_thread = None
        self.download_worker = None
        self._build_ui()
        self._refresh_versions()

    def set_game_root(self, path):
        self.game_root = path
        self._refresh_versions()

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
        title = SectionTitle(tr("mod_dl_title"))
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge(tr("mod_dl_title"), "info")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle(tr("mod_dl_subtitle"))
        main_layout.addWidget(sub)

        block1_label = QLabel("搜索")
        block1_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block1_label)

        block1 = QFrame()
        block1.setObjectName("card")
        block1.setFrameShape(QFrame.StyledPanel)
        block1_layout = QVBoxLayout(block1)
        block1_layout.setSpacing(12)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("mod_dl_search_placeholder"))
        self.search_edit.setMinimumHeight(34)
        self.search_edit.returnPressed.connect(self._search)
        search_row.addWidget(self.search_edit, 1)

        self.search_btn = QPushButton(tr("mod_dl_search_btn"))
        self.search_btn.setMinimumHeight(34)
        self.search_btn.setMinimumWidth(100)
        self.search_btn.clicked.connect(self._search)
        search_row.addWidget(self.search_btn)
        block1_layout.addLayout(search_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(tr("mod_dl_version_filter")))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumHeight(32)
        self.version_combo.setMinimumWidth(150)
        filter_row.addWidget(self.version_combo)

        filter_row.addSpacing(16)
        filter_row.addWidget(QLabel(tr("mod_dl_loader_filter")))
        self.loader_combo = QComboBox()
        self.loader_combo.setMinimumHeight(32)
        self.loader_combo.setMinimumWidth(120)
        self.loader_combo.addItem(tr("mod_dl_all"), "all")
        self.loader_combo.addItem("Forge", "forge")
        self.loader_combo.addItem("Fabric", "fabric")
        self.loader_combo.addItem("NeoForge", "neoforge")
        self.loader_combo.addItem("Quilt", "quilt")
        filter_row.addWidget(self.loader_combo)
        filter_row.addStretch()
        block1_layout.addLayout(filter_row)

        main_layout.addWidget(block1)

        block2_label = QLabel("结果")
        block2_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block2_label)

        block2 = QFrame()
        block2.setObjectName("card")
        block2.setFrameShape(QFrame.StyledPanel)
        block2_layout = QVBoxLayout(block2)
        block2_layout.setSpacing(12)

        self.mod_list = QListWidget()
        self.mod_list.setMinimumHeight(350)
        self.mod_list.setAlternatingRowColors(True)
        self.mod_list.itemClicked.connect(self._on_mod_selected)
        self.mod_list.setWordWrap(True)
        block2_layout.addWidget(self.mod_list)

        dl_row = QHBoxLayout()
        self.download_btn = QPushButton(tr("mod_dl_download"))
        self.download_btn.setMinimumHeight(36)
        self.download_btn.setMinimumWidth(140)
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected)
        dl_row.addWidget(self.download_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(24)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        dl_row.addWidget(self.progress_bar, 1)

        self.open_mods_btn = QPushButton(tr("mod_open_folder"))
        self.open_mods_btn.setObjectName("btnSecondary")
        self.open_mods_btn.setMinimumHeight(36)
        self.open_mods_btn.clicked.connect(self._open_mods_folder)
        dl_row.addWidget(self.open_mods_btn)

        block2_layout.addLayout(dl_row)

        main_layout.addWidget(block2)
        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

    def _refresh_versions(self):
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem(tr("mod_dl_all"), "")
        versions_dir = os.path.join(self.game_root, "versions")
        versions_added = set()
        if os.path.isdir(versions_dir):
            for d in sorted(os.listdir(versions_dir), reverse=True):
                full = os.path.join(versions_dir, d)
                if os.path.isdir(full) and d != "natives":
                    has_json = any(f.endswith(".json") for f in os.listdir(full))
                    if has_json:
                        mc_ver = self._extract_mc_version(d)
                        if mc_ver and mc_ver not in versions_added:
                            versions_added.add(mc_ver)
                            self.version_combo.addItem(mc_ver, mc_ver)
        self.version_combo.blockSignals(False)

    def _extract_mc_version(self, version_name):
        parts = version_name.split("-")
        for p in parts:
            if p[0].isdigit() and "." in p and "loader" not in p.lower():
                return p
        for p in parts:
            if p[0].isdigit() and "." in p:
                return p
        if version_name[0].isdigit():
            return version_name
        return ""

    def _search(self):
        query = self.search_edit.text().strip()
        game_version = self.version_combo.currentData() or ""
        loader = self.loader_combo.currentData() or "all"

        self.search_btn.setEnabled(False)
        self.search_btn.setText(tr("mod_dl_fetching"))
        self.mod_list.clear()
        self.download_btn.setEnabled(False)
        self.status_badge.set_status("info", tr("mod_dl_fetching"))

        self.search_thread = QThread()
        self.search_worker = SearchWorker(query, game_version, loader)
        self.search_worker.moveToThread(self.search_thread)
        self.search_thread.started.connect(self.search_worker.run)
        self.search_worker.finished.connect(self._on_search_finished)
        self.search_worker.finished.connect(self.search_thread.quit)
        self.search_worker.finished.connect(self.search_worker.deleteLater)
        self.search_thread.finished.connect(self.search_thread.deleteLater)
        self.search_thread.start()

    def _on_search_finished(self, mods):
        self.search_btn.setEnabled(True)
        self.search_btn.setText(tr("mod_dl_search_btn"))
        self.mod_list.clear()

        if not mods:
            item = QListWidgetItem(tr("mod_dl_no_results"))
            item.setFlags(Qt.NoItemFlags)
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(Qt.gray)
            self.mod_list.addItem(item)
            self.status_badge.set_status("warning", "0")
            return

        self.status_badge.set_status("normal", f"{len(mods)} 个")

        for hit in mods:
            title = hit.get("title", "Unknown")
            author = hit.get("author", "")
            downloads = hit.get("downloads", 0)
            followers = hit.get("follows", 0)
            categories = hit.get("categories", [])
            project_id = hit.get("project_id", "")
            description = hit.get("description", "")

            downloads_str = self._format_number(downloads)
            followers_str = self._format_number(followers)
            cats = ", ".join(categories[:5]) if categories else ""

            item = QListWidgetItem()
            item.setData(Qt.UserRole, {"project_id": project_id, "title": title})
            display = f"{title}"
            if author:
                display += f"  by {author}"
            display += f"\n  下载: {downloads_str}  关注: {followers_str}"
            if cats:
                display += f"\n  分类: {cats}"
            if description:
                short_desc = description[:120] + "..." if len(description) > 120 else description
                display += f"\n  {short_desc}"
            item.setText(display)
            item.setToolTip(description)
            hint = item.sizeHint()
            item.setSizeHint(QSize(hint.width(), max(hint.height() + 16, 72)))
            self.mod_list.addItem(item)

    def _format_number(self, n):
        if n >= 1000000:
            return f"{n/1000000:.1f}M"
        elif n >= 1000:
            return f"{n/1000:.1f}K"
        return str(n)

    def _on_mod_selected(self, item):
        data = item.data(Qt.UserRole)
        if data and isinstance(data, dict) and data.get("project_id"):
            self.download_btn.setEnabled(True)
        else:
            self.download_btn.setEnabled(False)

    def _download_selected(self):
        item = self.mod_list.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data or not data.get("project_id"):
            return

        project_id = data["project_id"]
        title = data.get("title", "mod")
        game_version = self.version_combo.currentData() or ""
        loader = self.loader_combo.currentData() or "all"

        versions = get_modrinth_versions(project_id, game_version, loader)
        if not versions:
            QMessageBox.warning(self, tr("error"), tr("mod_dl_no_results"))
            return

        ver = versions[0]
        files = ver.get("files", [])
        if not files:
            QMessageBox.warning(self, tr("error"), tr("mod_dl_no_results"))
            return

        file_info = files[0]
        url = file_info.get("url", "")
        filename = file_info.get("filename", f"{title}.jar")
        if not url:
            QMessageBox.warning(self, tr("error"), tr("msg_download_failed"))
            return

        mods_dir = os.path.join(self.game_root, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        save_path = os.path.join(mods_dir, filename)

        if os.path.exists(save_path):
            reply = QMessageBox.question(
                self, tr("tip"),
                f"'{filename}' 已经存在，覆盖吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self.download_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.status_badge.set_status("info", tr("mod_dl_downloading"))

        self.download_thread = QThread()
        self.download_worker = DownloadWorker(url, save_path)
        self.download_worker.moveToThread(self.download_thread)
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.finished.connect(self.download_thread.quit)
        self.download_worker.finished.connect(self.download_worker.deleteLater)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.start()

    def _on_download_progress(self, pct, info):
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{pct}% - {info}")

    def _on_download_finished(self, success, result, save_path):
        self.progress_bar.hide()
        self.download_btn.setEnabled(True)
        if success:
            self.status_badge.set_status("normal", tr("msg_download_success"))
            QMessageBox.information(self, tr("tip"), tr("msg_download_success"))
        else:
            self.status_badge.set_status("error", tr("msg_download_failed"))
            QMessageBox.warning(self, tr("error"), f"{tr('msg_download_failed')}: {result}")

    def _open_mods_folder(self):
        mods_dir = os.path.join(self.game_root, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        try:
            os.startfile(mods_dir)
        except Exception:
            QMessageBox.information(self, tr("tip"), f"模组目录:\n{mods_dir}")