"""模组加载器安装页面"""

import os
import threading
import requests
import urllib3

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QScrollArea,
    QMessageBox, QProgressBar, QSplitter, QFrame,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from core.mod_loader import (
    fetch_fabric_versions, fetch_quilt_versions, fetch_forge_versions,
    fetch_neoforge_versions, fetch_all_mc_versions,
    install_fabric, install_quilt, install_forge, install_neoforge,
    get_installed_loaders, uninstall_loader,
)
from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge
from gui.i18n import tr

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FetchVersionsWorker(QObject):
    finished = pyqtSignal(list, str)

    def __init__(self, loader_type, mc_version):
        super().__init__()
        self.loader_type = loader_type
        self.mc_version = mc_version

    def run(self):
        versions = []
        try:
            if self.loader_type == "fabric":
                data = fetch_fabric_versions(self.mc_version)
                versions = [v.get("loader", {}).get("version", "") for v in data if v.get("loader")]
            elif self.loader_type == "quilt":
                data = fetch_quilt_versions(self.mc_version)
                versions = [v.get("loader", {}).get("version", "") for v in data if v.get("loader")]
            elif self.loader_type == "forge":
                data = fetch_forge_versions(self.mc_version)
                versions = [v.get("version", "") for v in data if v.get("version")]
            elif self.loader_type == "neoforge":
                data = fetch_neoforge_versions(self.mc_version)
                versions = [v if isinstance(v, str) else v.get("version", "") for v in data]
                versions = [v for v in versions if v]
        except Exception:
            pass
        self.finished.emit(versions[:50], self.loader_type)


class InstallWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, game_root, loader_type, mc_version, loader_version):
        super().__init__()
        self.game_root = game_root
        self.loader_type = loader_type
        self.mc_version = mc_version
        self.loader_version = loader_version

    def run(self):
        def cb(pct, msg):
            self.progress.emit(pct, msg)
        try:
            if self.loader_type == "fabric":
                success, result = install_fabric(self.game_root, self.mc_version, self.loader_version, cb)
            elif self.loader_type == "quilt":
                success, result = install_quilt(self.game_root, self.mc_version, self.loader_version, cb)
            elif self.loader_type == "forge":
                success, result = install_forge(self.game_root, self.mc_version, self.loader_version, cb)
            elif self.loader_type == "neoforge":
                success, result = install_neoforge(self.game_root, self.mc_version, self.loader_version, cb)
            else:
                success, result = False, "Unknown loader"
            self.finished.emit(success, str(result), self.loader_type)
        except Exception as e:
            self.finished.emit(False, str(e), self.loader_type)


LOADERS = [
    {"id": "forge", "name": "Forge", "icon": "", "desc_zh": "最流行的模组加载器，兼容性强", "desc_en": "Most popular mod loader, great compatibility"},
    {"id": "fabric", "name": "Fabric", "icon": "", "desc_zh": "轻量级，更新快，模组丰富", "desc_en": "Lightweight, fast updates, rich mod ecosystem"},
    {"id": "neoforge", "name": "NeoForge", "icon": "", "desc_zh": "Forge的现代分支，性能优化", "desc_en": "Modern fork of Forge, performance optimized"},
    {"id": "quilt", "name": "Quilt", "icon": "", "desc_zh": "Fabric的社区分支，注重模块化", "desc_en": "Community fork of Fabric, focused on modularity"},
]


class LoaderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.current_loader = "forge"
        self.current_mc_version = ""
        self.fetch_thread = None
        self.fetch_worker = None
        self.install_thread = None
        self.install_worker = None
        self._build_ui()
        self._refresh_installed()

    def set_game_root(self, path):
        self.game_root = path
        self._refresh_installed()
        self._refresh_mc_versions()

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
        title = SectionTitle(tr("loader_title"))
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("", "normal")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle(tr("loader_subtitle"))
        main_layout.addWidget(sub)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        card_title_font = QFont()
        card_title_font.setPointSize(13)
        card_title_font.setBold(True)

        inst_title = QLabel(tr("loader_installed"))
        inst_title.setFont(card_title_font)
        card_layout.addWidget(inst_title)

        self.installed_list = QListWidget()
        self.installed_list.setMaximumHeight(120)
        self.installed_list.setAlternatingRowColors(True)
        card_layout.addWidget(self.installed_list)

        inst_btn_row = QHBoxLayout()
        self.refresh_inst_btn = QPushButton(tr("loader_fetch_versions"))
        self.refresh_inst_btn.setObjectName("btnSecondary")
        self.refresh_inst_btn.setMinimumHeight(30)
        self.refresh_inst_btn.clicked.connect(self._refresh_installed)
        inst_btn_row.addWidget(self.refresh_inst_btn)

        self.uninstall_btn = QPushButton(tr("loader_uninstall"))
        self.uninstall_btn.setObjectName("btnDanger")
        self.uninstall_btn.setMinimumHeight(30)
        self.uninstall_btn.setEnabled(False)
        self.uninstall_btn.clicked.connect(self._uninstall_selected)
        inst_btn_row.addWidget(self.uninstall_btn)
        inst_btn_row.addStretch()
        card_layout.addLayout(inst_btn_row)

        main_layout.addWidget(card)

        card2 = Card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(14)

        avail_title = QLabel(tr("loader_available"))
        avail_title.setFont(card_title_font)
        card2_layout.addWidget(avail_title)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)

        selector_row.addWidget(QLabel(tr("loader_select_mc_version")))
        self.mc_version_combo = QComboBox()
        self.mc_version_combo.setMinimumHeight(32)
        self.mc_version_combo.setMinimumWidth(150)
        self.mc_version_combo.currentIndexChanged.connect(self._on_mc_version_changed)
        selector_row.addWidget(self.mc_version_combo)
        selector_row.addStretch()
        card2_layout.addLayout(selector_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        loader_list_frame = QFrame()
        loader_list_layout = QVBoxLayout(loader_list_frame)
        loader_list_layout.setContentsMargins(0, 0, 8, 0)
        loader_list_layout.setSpacing(8)
        loader_list_label = QLabel("Loaders")
        loader_list_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        loader_list_layout.addWidget(loader_list_label)

        self.loader_list = QListWidget()
        self.loader_list.setMinimumWidth(160)
        for loader in LOADERS:
            item = QListWidgetItem(f"{loader['icon']} {loader['name']}")
            item.setData(Qt.UserRole, loader["id"])
            item.setSizeHint(QSize(0, 44))
            self.loader_list.addItem(item)
        self.loader_list.setCurrentRow(0)
        self.loader_list.currentRowChanged.connect(self._on_loader_selected)
        loader_list_layout.addWidget(self.loader_list)

        self.loader_desc = QLabel("")
        self.loader_desc.setWordWrap(True)
        self.loader_desc.setStyleSheet("color: palette(mid); font-size: 11px; padding: 6px;")
        loader_list_layout.addWidget(self.loader_desc)

        splitter.addWidget(loader_list_frame)

        version_frame = QFrame()
        version_layout = QVBoxLayout(version_frame)
        version_layout.setContentsMargins(8, 0, 0, 0)
        version_layout.setSpacing(8)
        version_label = QLabel(tr("loader_select_version"))
        version_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        version_layout.addWidget(version_label)

        self.version_list = QListWidget()
        self.version_list.setAlternatingRowColors(True)
        version_layout.addWidget(self.version_list)

        fetch_btn_row = QHBoxLayout()
        self.fetch_ver_btn = QPushButton(tr("loader_fetch_versions"))
        self.fetch_ver_btn.setObjectName("btnSecondary")
        self.fetch_ver_btn.setMinimumHeight(32)
        self.fetch_ver_btn.clicked.connect(self._fetch_versions)
        fetch_btn_row.addWidget(self.fetch_ver_btn)
        fetch_btn_row.addStretch()
        version_layout.addLayout(fetch_btn_row)

        splitter.addWidget(version_frame)
        splitter.setSizes([200, 500])
        card2_layout.addWidget(splitter, 1)

        install_row = QHBoxLayout()
        self.install_btn = QPushButton(tr("loader_install"))
        self.install_btn.setMinimumHeight(40)
        self.install_btn.setMinimumWidth(180)
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self._install_selected)
        install_row.addWidget(self.install_btn)

        self.install_progress = QProgressBar()
        self.install_progress.setMinimumHeight(24)
        self.install_progress.setValue(0)
        self.install_progress.hide()
        install_row.addWidget(self.install_progress, 1)

        install_row.addStretch()
        card2_layout.addLayout(install_row)

        main_layout.addWidget(card2, 1)
        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

        self._refresh_mc_versions()
        self._update_loader_desc()

    def _refresh_mc_versions(self):
        self.mc_version_combo.blockSignals(True)
        self.mc_version_combo.clear()

        versions_dir = os.path.join(self.game_root, "versions")
        local_versions = set()
        if os.path.isdir(versions_dir):
            for d in sorted(os.listdir(versions_dir), reverse=True):
                full = os.path.join(versions_dir, d)
                if os.path.isdir(full) and d != "natives":
                    mc_ver = self._extract_mc_version(d)
                    if mc_ver:
                        local_versions.add(mc_ver)

        for v in sorted(local_versions, reverse=True):
            self.mc_version_combo.addItem(v + " (local)", v)

        remote_versions = fetch_all_mc_versions()
        for v in remote_versions:
            if v not in local_versions:
                self.mc_version_combo.addItem(v, v)

        self.mc_version_combo.blockSignals(False)
        if self.mc_version_combo.count() > 0:
            self.current_mc_version = self.mc_version_combo.itemData(0)
        else:
            self.current_mc_version = "1.21.4"

    def _extract_mc_version(self, version_name):
        if "-forge-" in version_name:
            return version_name.split("-forge-")[0]
        if "-neoforge-" in version_name:
            return version_name.split("-neoforge-")[0]
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

    def _on_mc_version_changed(self, idx):
        self.current_mc_version = self.mc_version_combo.itemData(idx) or ""
        self.version_list.clear()
        self.install_btn.setEnabled(False)

    def _on_loader_selected(self, row):
        item = self.loader_list.item(row)
        if item:
            self.current_loader = item.data(Qt.UserRole)
            self._update_loader_desc()
            self.version_list.clear()
            self.install_btn.setEnabled(False)

    def _update_loader_desc(self):
        from gui.i18n import LANG
        for loader in LOADERS:
            if loader["id"] == self.current_loader:
                if LANG == "zh":
                    self.loader_desc.setText(loader["desc_zh"])
                else:
                    self.loader_desc.setText(loader["desc_en"])
                break

    def _fetch_versions(self):
        if not self.current_mc_version:
            QMessageBox.warning(self, tr("tip"), tr("msg_select_version"))
            return

        self.fetch_ver_btn.setEnabled(False)
        self.fetch_ver_btn.setText(tr("dl_fetching"))
        self.version_list.clear()
        self.install_btn.setEnabled(False)
        self.status_badge.set_status("info", tr("dl_fetching_loaders"))

        self.fetch_thread = QThread()
        self.fetch_worker = FetchVersionsWorker(self.current_loader, self.current_mc_version)
        self.fetch_worker.moveToThread(self.fetch_thread)
        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self._on_fetch_finished)
        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
        self.fetch_thread.start()

    def _on_fetch_finished(self, versions, loader_type):
        self.fetch_ver_btn.setEnabled(True)
        self.fetch_ver_btn.setText(tr("loader_fetch_versions"))
        self.version_list.clear()

        if not versions:
            item = QListWidgetItem(tr("loader_no_versions"))
            item.setFlags(Qt.NoItemFlags)
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(Qt.gray)
            self.version_list.addItem(item)
            self.status_badge.set_status("warning", tr("loader_no_versions"))
            return

        for v in versions:
            item = QListWidgetItem(v)
            item.setData(Qt.UserRole, v)
            item.setSizeHint(QSize(0, 32))
            self.version_list.addItem(item)

        self.status_badge.set_status("normal", f"{len(versions)} versions")
        self.version_list.itemSelectionChanged.connect(self._on_version_selected)

    def _on_version_selected(self):
        items = self.version_list.selectedItems()
        self.install_btn.setEnabled(len(items) > 0)

    def _install_selected(self):
        items = self.version_list.selectedItems()
        if not items or not self.current_mc_version:
            return
        loader_version = items[0].data(Qt.UserRole)
        if not loader_version:
            return

        versions_dir = os.path.join(self.game_root, "versions")
        mc_jar = os.path.join(versions_dir, self.current_mc_version, f"{self.current_mc_version}.jar")
        if not os.path.exists(mc_jar):
            reply = QMessageBox.question(
                self, tr("tip"),
                f"Minecraft {self.current_mc_version} client not found locally.\n"
                f"It is recommended to download the version first in Download page.\n\n"
                f"Continue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self.install_btn.setEnabled(False)
        self.fetch_ver_btn.setEnabled(False)
        self.install_progress.show()
        self.install_progress.setValue(0)
        self.status_badge.set_status("info", tr("loader_installing"))

        self.install_thread = QThread()
        self.install_worker = InstallWorker(
            self.game_root, self.current_loader, self.current_mc_version, loader_version
        )
        self.install_worker.moveToThread(self.install_thread)
        self.install_thread.started.connect(self.install_worker.run)
        self.install_worker.progress.connect(self._on_install_progress)
        self.install_worker.finished.connect(self._on_install_finished)
        self.install_worker.finished.connect(self.install_thread.quit)
        self.install_worker.finished.connect(self.install_worker.deleteLater)
        self.install_thread.finished.connect(self.install_thread.deleteLater)
        self.install_thread.start()

    def _on_install_progress(self, pct, msg):
        self.install_progress.setValue(pct)
        self.install_progress.setFormat(f"{pct}% - {msg[:30]}")

    def _on_install_finished(self, success, result, loader_type):
        self.install_progress.hide()
        self.install_btn.setEnabled(True)
        self.fetch_ver_btn.setEnabled(True)
        if success:
            self.status_badge.set_status("normal", tr("msg_install_success"))
            QMessageBox.information(self, tr("tip"), f"{tr('msg_install_success')}!\n{result}")
            self._refresh_installed()
        else:
            self.status_badge.set_status("error", tr("msg_install_failed"))
            QMessageBox.warning(self, tr("error"), f"{tr('msg_install_failed')}: {result}")

    def _refresh_installed(self):
        self.installed_list.clear()
        self.uninstall_btn.setEnabled(False)
        loaders = get_installed_loaders(self.game_root)
        if not loaders:
            item = QListWidgetItem(tr("loader_no_versions"))
            item.setFlags(Qt.NoItemFlags)
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(Qt.gray)
            self.installed_list.addItem(item)
            self.status_badge.set_status("info", "0")
            return

        self.status_badge.set_status("normal", f"{len(loaders)}")
        type_names = {"forge": "Forge", "fabric": "Fabric", "neoforge": "NeoForge", "quilt": "Quilt"}
        for loader in loaders:
            lt = loader.get("loader_type", "")
            mc_v = loader.get("mc_version", "")
            ld_v = loader.get("loader_version", "")
            name = type_names.get(lt, lt)
            display = f"{name}  -  MC {mc_v}  -  {ld_v}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, loader.get("path", ""))
            item.setSizeHint(QSize(0, 32))
            self.installed_list.addItem(item)

        self.installed_list.itemSelectionChanged.connect(self._on_installed_selected)

    def _on_installed_selected(self):
        items = self.installed_list.selectedItems()
        self.uninstall_btn.setEnabled(len(items) > 0)

    def _uninstall_selected(self):
        items = self.installed_list.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.UserRole)
        if not path or not os.path.isdir(path):
            return
        reply = QMessageBox.question(
            self, tr("warning"),
            tr("loader_confirm_uninstall"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        success, msg = uninstall_loader(path)
        if success:
            QMessageBox.information(self, tr("tip"), msg)
            self._refresh_installed()
        else:
            QMessageBox.warning(self, tr("error"), msg)
