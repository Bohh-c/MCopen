import os
import json

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QMessageBox,
    QSlider, QFormLayout, QProgressBar,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root, scan_all_versions, launch_selected_version
from core.crash_detector import CrashDetector
from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge
from gui.java_detector import find_recommended_java, find_java_paths
from gui.account_page import get_default_account
from gui.i18n import tr

import threading

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "launcher_settings.json")


class LaunchWorker(QObject):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str, object)
    game_started_signal = pyqtSignal()

    def launch(self, game_root, java_path, selected_item, mem_min, mem_max, player_name):
        try:
            def progress_cb(pct, info):
                self.progress_signal.emit(pct, info)

            proc = launch_selected_version(
                game_root, java_path, selected_item,
                mem_min=mem_min, mem_max=mem_max, player_name=player_name,
                progress_callback=progress_cb,
            )

            if proc:
                self.progress_signal.emit(100, "游戏启动完成")
                self.game_started_signal.emit()
                self.finished_signal.emit(True, "游戏已启动", proc)
            else:
                self.finished_signal.emit(False, "进程未创建", None)
        except FileNotFoundError as e:
            self.finished_signal.emit(False, f"文件不存在: {e}", None)
        except PermissionError as e:
            self.finished_signal.emit(False, f"权限不足: {e}", None)
        except Exception as exc:
            self.finished_signal.emit(False, f"{type(exc).__name__}: {exc}", None)


class HomePage(QWidget):
    switch_to_account = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.java_path = self._find_java()
        self.game_process = None
        self.crash_detector = CrashDetector(self.game_root)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(3000)
        self.monitor_timer.timeout.connect(self._check_game_status)
        self.launch_worker = LaunchWorker()
        self.launch_worker.progress_signal.connect(self._on_launch_progress)
        self.launch_worker.finished_signal.connect(self._on_launch_finished)
        self.game_lang = "zh_cn"
        self._load_settings()
        self._build_ui()
        self.refresh_current_account()
        self.refresh_versions()

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                self.game_lang = settings.get("game_lang", "zh_cn")

    def _save_game_lang(self):
        settings = {}
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        settings["game_lang"] = self.game_lang
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def _find_java(self):
        path, ver = find_recommended_java()
        if path:
            return path
        return r"C:\Program Files\Zulu\zulu-17\bin\java.exe"

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle(tr("home_title"))
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge(tr("home_ready"), "normal")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle(tr("home_subtitle"))
        main_layout.addWidget(sub)

        card1 = Card()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setSpacing(14)

        card1_title = QLabel(tr("home_basic"))
        card1_font = QFont()
        card1_font.setPointSize(13)
        card1_font.setBold(True)
        card1_title.setFont(card1_font)
        card1_layout.addWidget(card1_title)

        form = QFormLayout()
        form.setSpacing(10)

        label_font = QFont()
        label_font.setPointSize(11)

        game_row = QHBoxLayout()
        self.game_dir_edit = QLineEdit(self.game_root)
        self.game_dir_edit.setPlaceholderText(".minecraft")
        self.game_dir_edit.setMinimumHeight(36)
        self.game_dir_edit.setFont(label_font)
        game_btn = QPushButton(tr("home_browse"))
        game_btn.setObjectName("btnSecondary")
        game_btn.setFixedWidth(80)
        game_btn.setMinimumHeight(36)
        game_btn.setFont(label_font)
        game_btn.clicked.connect(self._select_game_dir)
        game_row.addWidget(self.game_dir_edit)
        game_row.addWidget(game_btn)
        form.addRow(tr("home_game_dir"), game_row)

        java_row = QHBoxLayout()
        self.java_edit = QLineEdit(self.java_path)
        self.java_edit.setPlaceholderText("Java 可执行文件路径")
        self.java_edit.setMinimumHeight(36)
        self.java_edit.setFont(label_font)
        java_btn = QPushButton(tr("home_select"))
        java_btn.setObjectName("btnSecondary")
        java_btn.setFixedWidth(80)
        java_btn.setMinimumHeight(36)
        java_btn.setFont(label_font)
        java_btn.clicked.connect(self._select_java)
        java_row.addWidget(self.java_edit)
        java_row.addWidget(java_btn)

        detect_btn = QPushButton(tr("home_auto_detect"))
        detect_btn.setObjectName("btnSecondary")
        detect_btn.setFixedWidth(80)
        detect_btn.setMinimumHeight(36)
        detect_btn.setFont(label_font)
        detect_btn.clicked.connect(self._detect_java)
        java_row.addWidget(detect_btn)
        form.addRow(tr("home_java_path"), java_row)

        self.version_combo = QComboBox()
        self.version_combo.setMinimumHeight(36)
        self.version_combo.setFont(label_font)
        form.addRow(tr("home_version"), self.version_combo)

        card1_layout.addLayout(form)
        main_layout.addWidget(card1)

        card2 = Card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(14)

        card2_title = QLabel(tr("home_player_mem"))
        card2_title.setFont(card1_font)
        card2_layout.addWidget(card2_title)

        form2 = QFormLayout()
        form2.setSpacing(10)

        account_row = QHBoxLayout()
        self.player_label = QLabel("TestPlayer")
        self.player_label.setMinimumHeight(36)
        self.player_label.setFont(label_font)
        self.player_label.setStyleSheet("font-weight: bold;")
        account_row.addWidget(self.player_label)
        account_row.addStretch()
        self.switch_account_btn = QPushButton(tr("home_switch_account"))
        self.switch_account_btn.setObjectName("btnSecondary")
        self.switch_account_btn.setMinimumHeight(36)
        self.switch_account_btn.setFont(label_font)
        self.switch_account_btn.clicked.connect(lambda: self.switch_to_account.emit())
        account_row.addWidget(self.switch_account_btn)
        form2.addRow(tr("home_player"), account_row)

        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumHeight(36)
        self.lang_combo.setFont(label_font)
        self.lang_combo.addItem("中文", "zh_cn")
        self.lang_combo.addItem("English", "en_us")
        idx = self.lang_combo.findData(self.game_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        form2.addRow(tr("home_game_lang"), self.lang_combo)

        mem_widget = QWidget()
        mem_layout = QVBoxLayout(mem_widget)
        mem_layout.setContentsMargins(0, 0, 0, 0)

        mem_slider_layout = QHBoxLayout()
        mem_label = QLabel(tr("home_min_mem"))
        mem_label.setFixedWidth(70)
        mem_label.setFont(label_font)
        mem_slider_layout.addWidget(mem_label)
        self.min_mem_slider = QSlider(Qt.Horizontal)
        self.min_mem_slider.setRange(512, 16384)
        self.min_mem_slider.setValue(2048)
        self.min_mem_slider.setTickInterval(1024)
        self.min_mem_slider.setTickPosition(QSlider.TicksBelow)
        self.min_mem_label = QLabel("2048 MB")
        self.min_mem_label.setFixedWidth(80)
        self.min_mem_label.setAlignment(Qt.AlignRight)
        self.min_mem_label.setFont(label_font)
        self.min_mem_slider.valueChanged.connect(
            lambda v: self.min_mem_label.setText(f"{v} MB")
        )
        mem_slider_layout.addWidget(self.min_mem_slider)
        mem_slider_layout.addWidget(self.min_mem_label)
        mem_layout.addLayout(mem_slider_layout)

        mem_slider_layout2 = QHBoxLayout()
        mem_label2 = QLabel(tr("home_max_mem"))
        mem_label2.setFixedWidth(70)
        mem_label2.setFont(label_font)
        mem_slider_layout2.addWidget(mem_label2)
        self.max_mem_slider = QSlider(Qt.Horizontal)
        self.max_mem_slider.setRange(1024, 32768)
        self.max_mem_slider.setValue(4096)
        self.max_mem_slider.setTickInterval(2048)
        self.max_mem_slider.setTickPosition(QSlider.TicksBelow)
        self.max_mem_label = QLabel("4096 MB")
        self.max_mem_label.setFixedWidth(80)
        self.max_mem_label.setAlignment(Qt.AlignRight)
        self.max_mem_label.setFont(label_font)
        self.max_mem_slider.valueChanged.connect(
            lambda v: self.max_mem_label.setText(f"{v} MB")
        )
        mem_slider_layout2.addWidget(self.max_mem_slider)
        mem_slider_layout2.addWidget(self.max_mem_label)
        mem_layout.addLayout(mem_slider_layout2)

        form2.addRow(tr("home_mem_alloc"), mem_widget)

        card2_layout.addLayout(form2)
        main_layout.addWidget(card2)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.refresh_btn = QPushButton(tr("home_refresh"))
        self.refresh_btn.setObjectName("btnSecondary")
        self.refresh_btn.setMinimumHeight(36)
        self.refresh_btn.setFont(label_font)
        self.refresh_btn.clicked.connect(self.refresh_versions)
        btn_layout.addWidget(self.refresh_btn)

        self.export_log_btn = QPushButton(tr("home_export_log"))
        self.export_log_btn.setObjectName("btnSecondary")
        self.export_log_btn.setMinimumHeight(36)
        self.export_log_btn.setFont(label_font)
        self.export_log_btn.clicked.connect(self._export_logs)
        btn_layout.addWidget(self.export_log_btn)

        self.launch_btn = QPushButton(tr("home_launch"))
        self.launch_btn.setMinimumHeight(44)
        self.launch_btn.setMinimumWidth(160)
        launch_font = QFont()
        launch_font.setPointSize(14)
        launch_font.setBold(True)
        self.launch_btn.setFont(launch_font)
        self.launch_btn.clicked.connect(self._launch_game)
        btn_layout.addWidget(self.launch_btn)
        main_layout.addLayout(btn_layout)

        self.launch_progress = QProgressBar()
        self.launch_progress.setValue(0)
        self.launch_progress.setTextVisible(True)
        self.launch_progress.setMinimumHeight(24)
        self.launch_progress.hide()
        main_layout.addWidget(self.launch_progress)

        self.launch_progress_label = QLabel("")
        self.launch_progress_label.setFont(label_font)
        self.launch_progress_label.hide()
        main_layout.addWidget(self.launch_progress_label)

        main_layout.addStretch()

    def _select_game_dir(self):
        selected = QFileDialog.getExistingDirectory(self, "选择游戏目录", self.game_root)
        if selected:
            self.game_root = selected
            self.game_dir_edit.setText(selected)
            self.crash_detector = CrashDetector(self.game_root)
            self.refresh_versions()

    def _select_java(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择 Java 可执行文件", self.java_path,
            "可执行文件 (*.exe *.bat *.cmd)"
        )
        if selected:
            self.java_path = selected
            self.java_edit.setText(selected)

    def _detect_java(self):
        paths = find_java_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "未检测到 Java，请手动安装")
            return
        if len(paths) == 1:
            self.java_path = paths[0]
            self.java_edit.setText(paths[0])
            QMessageBox.information(self, "提示", f"已检测到 Java:\n{paths[0]}")
        else:
            from gui.java_dialog import JavaDialog
            dialog = JavaDialog(paths, self)
            if dialog.exec_():
                self.java_path = dialog.selected_path
                self.java_edit.setText(dialog.selected_path)

    def _on_lang_changed(self, idx):
        self.game_lang = self.lang_combo.itemData(idx)
        self._save_game_lang()

    def refresh_current_account(self):
        acc = get_default_account()
        if acc:
            self.player_label.setText(acc["name"])
        else:
            self.player_label.setText("TestPlayer")

    def _write_options_txt(self, game_root):
        options_path = os.path.join(game_root, "options.txt")
        options = {}
        if os.path.exists(options_path):
            with open(options_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if ":" in line:
                        key, value = line.split(":", 1)
                        options[key.strip()] = value.strip()
        options["lang"] = self.game_lang
        options["narrator"] = "0"
        options["narratorHotkey"] = "false"
        options["soundDevice"] = ""
        with open(options_path, "w", encoding="utf-8") as f:
            for key, value in options.items():
                f.write(f"{key}:{value}\n")

    def refresh_versions(self):
        self.version_combo.clear()
        game_root = self.game_dir_edit.text().strip() or self.game_root
        versions = scan_all_versions(game_root)
        if not versions:
            self.status_badge.set_status("warning", "无版本")
            return
        for item in versions:
            self.version_combo.addItem(item["folder_name"], item)
        self.status_badge.set_status("normal", f"{len(versions)}个版本")

    def _launch_game(self):
        selected_item = self.version_combo.currentData()
        if not selected_item:
            QMessageBox.warning(self, tr("tip"), tr("msg_select_version"))
            return

        game_root = self.game_dir_edit.text().strip() or self.game_root
        java_path = self.java_edit.text().strip() or self.java_path
        player_name = self.player_label.text().strip() or "TestPlayer"
        mem_min = self.min_mem_slider.value()
        mem_max = self.max_mem_slider.value()

        if mem_min > mem_max:
            QMessageBox.warning(self, tr("tip"), tr("msg_mem_error"))
            return

        if not os.path.exists(java_path):
            QMessageBox.warning(self, tr("tip"), tr("msg_java_not_found") + f": {java_path}")
            return

        if not os.path.isdir(game_root):
            QMessageBox.warning(self, tr("tip"), tr("msg_game_dir_not_found") + f": {game_root}")
            return

        self._write_options_txt(game_root)

        self.launch_btn.setEnabled(False)
        self.launch_progress.show()
        self.launch_progress_label.show()
        self.launch_progress.setValue(0)
        self.launch_progress_label.setText(tr("home_preparing"))

        thread = threading.Thread(
            target=self.launch_worker.launch,
            args=(game_root, java_path, selected_item, mem_min, mem_max, player_name),
            daemon=True
        )
        thread.start()

    def _on_launch_progress(self, value, text):
        self.launch_progress.show()
        self.launch_progress_label.show()
        self.launch_progress.setValue(value)
        self.launch_progress.setFormat(f"%v% - {text[:30]}...")
        self.launch_progress_label.setText(text)

    def _on_launch_finished(self, success, msg, proc):
        if success and proc:
            self.game_process = proc
            self.crash_detector = CrashDetector(self.game_dir_edit.text().strip() or self.game_root)
            self.crash_detector.monitor_process(proc)
            self.monitor_timer.start()
            self.status_badge.set_status("normal", tr("home_running"))
            self.launch_progress.setValue(100)
            self.launch_progress.setFormat(tr("home_game_running"))
            self.launch_progress_label.setText(tr("home_game_started"))
        else:
            self.launch_btn.setEnabled(True)
            self.launch_progress.hide()
            self.launch_progress_label.hide()
            self.status_badge.set_status("error", tr("home_launch_fail"))
            QMessageBox.critical(self, tr("msg_launch_failed"), msg)

    def _check_game_status(self):
        if not self.game_process:
            self.monitor_timer.stop()
            return

        try:
            if not self.crash_detector.is_running():
                exit_code = self.crash_detector.get_exit_code()
                self.monitor_timer.stop()
                self.launch_btn.setEnabled(True)
                self.launch_progress.hide()
                self.launch_progress_label.hide()

                crash_file = self.crash_detector.check_for_crash()
                if crash_file:
                    report = self.crash_detector.get_crash_report(crash_file)
                    analysis = self.crash_detector.analyze_crash(report)
                    self._show_crash_dialog(report, analysis)
                    self.status_badge.set_status("error", tr("home_crash"))
                elif exit_code is not None and exit_code != 0:
                    self.status_badge.set_status("error", f"{tr('home_abnormal_exit')} ({exit_code})")
                    QMessageBox.warning(self, tr("home_abnormal_exit"), f"Exit code: {exit_code}")
                else:
                    self.status_badge.set_status("normal", tr("home_stopped"))
                self.game_process = None
        except Exception as e:
            print(f"状态检查异常: {e}")
            self.monitor_timer.stop()
            self.launch_btn.setEnabled(True)
            self.launch_progress.hide()
            self.launch_progress_label.hide()
            self.status_badge.set_status("error", "状态检查异常")
            self.game_process = None

    def _show_crash_dialog(self, report, analysis):
        msg = tr("msg_crash_detected") + "\n\n"
        msg += f"Type: {analysis.get('type', 'unknown')}\n"
        msg += f"Description: {analysis.get('description', '')}\n"
        if analysis.get('suggestion'):
            msg += f"Suggestion: {analysis.get('suggestion')}\n\n"
        msg += "Report:\n" + (report[:2000] if report else "N/A")

        reply = QMessageBox.critical(
            self, tr("home_crash"), msg,
            QMessageBox.Ok | QMessageBox.Save,
            QMessageBox.Ok
        )
        if reply == QMessageBox.Save:
            self._export_logs()

    def _export_logs(self):
        game_root = self.game_dir_edit.text().strip() or self.game_root
        detector = CrashDetector(game_root)
        export_dir, files = detector.export_logs()
        QMessageBox.information(
            self, tr("msg_export_success"),
            f"{tr('msg_export_success')}:\n{export_dir}\n\nFiles:\n" + "\n".join(files)
        )