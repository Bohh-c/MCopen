import os
import shutil
import zipfile
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QComboBox, QScrollArea, QFrame,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from gui.widgets import SectionTitle, SubTitle, StatusBadge
from gui.i18n import tr


class ModInfo:
    def __init__(self, file_path):
        self.path = file_path
        self.name = os.path.basename(file_path)
        self.version = ""
        self.author = ""
        self.description = ""
        self.enabled = not self.name.endswith(".disabled")
        self.size = 0
        self._parse()

    def _parse(self):
        try:
            self.size = os.path.getsize(self.path)
        except Exception:
            pass

        actual_name = self.name
        if self.name.endswith(".disabled"):
            actual_name = self.name[:-9]

        if actual_name.endswith(".jar") or actual_name.endswith(".zip"):
            try:
                with zipfile.ZipFile(self.path, "r") as zf:
                    for candidate in ["fabric.mod.json", "quilt.mod.json", "META-INF/mods.toml", "mcmod.info"]:
                        if candidate in zf.namelist():
                            try:
                                import json
                                with zf.open(candidate) as f:
                                    if candidate.endswith(".json"):
                                        data = json.loads(f.read().decode("utf-8", errors="replace"))
                                        if isinstance(data, list) and len(data) > 0:
                                            data = data[0]
                                        self.name = data.get("name", actual_name)
                                        self.version = data.get("version", "")
                                        self.author = data.get("authors", "")
                                        if isinstance(self.author, list):
                                            self.author = ", ".join(
                                                a.get("name", str(a)) if isinstance(a, dict) else str(a)
                                                for a in self.author
                                            )
                                        self.description = data.get("description", "")
                                    elif candidate.endswith(".toml"):
                                        content = f.read().decode("utf-8", errors="replace")
                                        for line in content.splitlines():
                                            line = line.strip()
                                            if line.startswith("displayName"):
                                                self.name = line.split("=", 1)[1].strip().strip('"').strip("'")
                                            elif line.startswith("version") and "versionRange" not in line:
                                                self.version = line.split("=", 1)[1].strip().strip('"').strip("'")
                                            elif line.startswith("authors"):
                                                self.author = line.split("=", 1)[1].strip().strip('"').strip("'")
                                            elif line.startswith("description"):
                                                self.description = line.split("=", 1)[1].strip().strip('"').strip("'")
                            except Exception:
                                pass
                            break
            except Exception:
                pass

        if self.name == actual_name or not self.name:
            clean = actual_name
            for ext in [".jar", ".zip", ".disabled"]:
                if clean.endswith(ext):
                    clean = clean[:-len(ext)]
            self.name = clean

    def get_size_str(self):
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        else:
            return f"{self.size / (1024 * 1024):.1f} MB"


class ModPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.current_version = ""
        self.mods_dir = ""
        self.mods = []
        self._build_ui()

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
        title = SectionTitle(tr("mod_title"))
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("0 " + tr("mod_count"), "normal")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle(tr("mod_subtitle"))
        main_layout.addWidget(sub)

        block1_label = QLabel("模组列表")
        block1_label.setFont(QFont("", 13, QFont.Bold))
        main_layout.addWidget(block1_label)

        block1 = QFrame()
        block1.setObjectName("card")
        block1.setFrameShape(QFrame.StyledPanel)
        block1_layout = QVBoxLayout(block1)
        block1_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.addWidget(QLabel(tr("mod_select_version")))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumWidth(200)
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        top_row.addWidget(self.version_combo)
        top_row.addStretch()

        self.add_btn = QPushButton(tr("mod_add"))
        self.add_btn.setMinimumWidth(80)
        self.add_btn.clicked.connect(self._add_mod)
        top_row.addWidget(self.add_btn)

        self.open_folder_btn = QPushButton(tr("mod_open_folder"))
        self.open_folder_btn.setObjectName("btnSecondary")
        self.open_folder_btn.setMinimumWidth(110)
        self.open_folder_btn.clicked.connect(self._open_mods_folder)
        top_row.addWidget(self.open_folder_btn)

        self.refresh_btn = QPushButton(tr("mod_refresh"))
        self.refresh_btn.setObjectName("btnSecondary")
        self.refresh_btn.setMinimumWidth(70)
        self.refresh_btn.clicked.connect(self.refresh_mods)
        top_row.addWidget(self.refresh_btn)

        block1_layout.addLayout(top_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.enable_btn = QPushButton(tr("mod_enable"))
        self.enable_btn.setObjectName("btnSecondary")
        self.enable_btn.setEnabled(False)
        self.enable_btn.clicked.connect(self._enable_mod)
        btn_row.addWidget(self.enable_btn)

        self.disable_btn = QPushButton(tr("mod_disable"))
        self.disable_btn.setObjectName("btnSecondary")
        self.disable_btn.setEnabled(False)
        self.disable_btn.clicked.connect(self._disable_mod)
        btn_row.addWidget(self.disable_btn)

        self.delete_btn = QPushButton(tr("mod_delete"))
        self.delete_btn.setObjectName("btnDanger")
        self.delete_btn.setMinimumWidth(50)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_mod)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        self.mod_count_label = QLabel("")
        self.mod_count_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        btn_row.addWidget(self.mod_count_label)

        block1_layout.addLayout(btn_row)

        self.mod_list = QListWidget()
        self.mod_list.setMinimumHeight(400)
        self.mod_list.setAlternatingRowColors(True)
        self.mod_list.itemClicked.connect(self._on_mod_selected)
        self.mod_list.itemDoubleClicked.connect(self._toggle_mod)
        block1_layout.addWidget(self.mod_list)

        main_layout.addWidget(block1)
        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

        self._refresh_versions()

    def _refresh_versions(self):
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        versions_dir = os.path.join(self.game_root, "versions")
        if os.path.isdir(versions_dir):
            for d in sorted(os.listdir(versions_dir)):
                full = os.path.join(versions_dir, d)
                if os.path.isdir(full) and d != "natives":
                    has_json = any(f.endswith(".json") for f in os.listdir(full))
                    if has_json:
                        self.version_combo.addItem(d, d)
        self.version_combo.blockSignals(False)
        if self.version_combo.count() > 0:
            self._on_version_changed(0)

    def _on_version_changed(self, idx):
        version = self.version_combo.itemData(idx)
        if version:
            self.current_version = version
            self.mods_dir = os.path.join(self.game_root, "mods")
            self.refresh_mods()

    def refresh_mods(self):
        self.mod_list.clear()
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.mods = []

        if not self.mods_dir:
            self._show_no_mods()
            return

        os.makedirs(self.mods_dir, exist_ok=True)

        enabled_count = 0
        disabled_count = 0

        for f in sorted(os.listdir(self.mods_dir)):
            path = os.path.join(self.mods_dir, f)
            if not os.path.isfile(path):
                continue
            is_disabled = f.endswith(".disabled")
            base_name = f[:-9] if is_disabled else f
            if not (base_name.endswith(".jar") or base_name.endswith(".zip")):
                continue

            mod = ModInfo(path)
            self.mods.append(mod)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, mod)

            status_icon = "🟢" if mod.enabled else "🔴"
            status_text = tr("mod_enabled") if mod.enabled else tr("mod_disabled_tag")
            display_text = f"{status_icon} {mod.name}"
            if mod.version:
                display_text += f"  [{mod.version}]"
            display_text += f"  ({mod.get_size_str()})"
            item.setText(display_text)
            item.setToolTip(
                f"{tr('mod_name')}: {mod.name}\n"
                f"{tr('mod_version')}: {mod.version or '-'}\n"
                f"{tr('mod_author')}: {mod.author or '-'}\n"
                f"{tr('mod_size')}: {mod.get_size_str()}\n"
                f"{tr('mod_description')}: {(mod.description[:200] + '...') if len(mod.description) > 200 else (mod.description or '-')}\n"
                f"File: {os.path.basename(mod.path)}"
            )
            hint = item.sizeHint()
            item.setSizeHint(QSize(hint.width(), max(hint.height() + 8, 36)))

            if mod.enabled:
                enabled_count += 1
            else:
                disabled_count += 1

            self.mod_list.addItem(item)

        total = enabled_count + disabled_count
        self.status_badge.set_status("normal", f"{total} {tr('mod_count')}")
        self.mod_count_label.setText(
            f"{tr('mod_enabled')}: {enabled_count}  |  {tr('mod_disabled_tag')}: {disabled_count}"
        )

        if total == 0:
            self._show_no_mods()

    def _show_no_mods(self):
        item = QListWidgetItem(tr("mod_no_mods"))
        item.setFlags(Qt.NoItemFlags)
        item.setTextAlignment(Qt.AlignCenter)
        item.setForeground(Qt.gray)
        self.mod_list.addItem(item)
        self.mod_count_label.setText("")

    def _add_mod(self):
        if not self.mods_dir:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("mod_add"), "",
            "Jar/Zip Files (*.jar *.zip);;Jar Files (*.jar);;Zip Files (*.zip)"
        )
        if not files:
            return
        os.makedirs(self.mods_dir, exist_ok=True)
        added = 0
        for f in files:
            name = os.path.basename(f)
            dest = os.path.join(self.mods_dir, name)
            if name.endswith(".disabled"):
                dest = os.path.join(self.mods_dir, name)
            if os.path.exists(dest):
                reply = QMessageBox.question(
                    self, tr("tip"),
                    f"Mod '{name}' already exists. Overwrite?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    continue
            try:
                shutil.copy2(f, dest)
                added += 1
            except Exception as e:
                QMessageBox.warning(self, tr("error"), f"Failed to add {name}: {e}")
        self.refresh_mods()

    def _enable_mod(self):
        item = self.mod_list.currentItem()
        if not item:
            return
        mod = item.data(Qt.UserRole)
        if not isinstance(mod, ModInfo):
            return
        if mod.enabled:
            return
        if mod.path.endswith(".disabled"):
            new_path = mod.path[:-9]
            try:
                os.rename(mod.path, new_path)
            except Exception as e:
                QMessageBox.warning(self, tr("error"), str(e))
                return
        self.refresh_mods()

    def _disable_mod(self):
        item = self.mod_list.currentItem()
        if not item:
            return
        mod = item.data(Qt.UserRole)
        if not isinstance(mod, ModInfo):
            return
        if not mod.enabled:
            return
        if not mod.path.endswith(".disabled"):
            new_path = mod.path + ".disabled"
            try:
                os.rename(mod.path, new_path)
            except Exception as e:
                QMessageBox.warning(self, tr("error"), str(e))
                return
        self.refresh_mods()

    def _toggle_mod(self, item):
        mod = item.data(Qt.UserRole)
        if not isinstance(mod, ModInfo):
            return
        if mod.enabled:
            self._disable_mod()
        else:
            self._enable_mod()

    def _delete_mod(self):
        item = self.mod_list.currentItem()
        if not item:
            return
        mod = item.data(Qt.UserRole)
        if not isinstance(mod, ModInfo):
            return
        reply = QMessageBox.question(
            self, tr("warning"),
            f"{tr('mod_confirm_delete')} '{mod.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            os.remove(mod.path)
        except Exception as e:
            QMessageBox.warning(self, tr("error"), str(e))
            return
        self.refresh_mods()

    def _on_mod_selected(self, item):
        mod = item.data(Qt.UserRole)
        if not isinstance(mod, ModInfo):
            self.enable_btn.setEnabled(False)
            self.disable_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        self.enable_btn.setEnabled(not mod.enabled)
        self.disable_btn.setEnabled(mod.enabled)
        self.delete_btn.setEnabled(True)

    def _open_mods_folder(self):
        if not self.mods_dir:
            return
        os.makedirs(self.mods_dir, exist_ok=True)
        try:
            import subprocess
            os.startfile(self.mods_dir)
        except Exception:
            QMessageBox.information(self, tr("tip"), f"Mods folder:\n{self.mods_dir}")