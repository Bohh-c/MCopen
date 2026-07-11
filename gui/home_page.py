import os
import json
import threading

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QMessageBox,
    QProgressBar, QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root, scan_all_versions, launch_selected_version
from core.crash_detector import CrashDetector
from gui.widgets import SectionTitle, SubTitle, StatusBadge
from gui.account_page import get_default_account
from gui.i18n import tr


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
        self.game_process = None
        self.crash_detector = CrashDetector(self.game_root)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(3000)
        self.monitor_timer.timeout.connect(self._check_game_status)
        self.launch_worker = LaunchWorker()
        self.launch_worker.progress_signal.connect(self._on_launch_progress)
        self.launch_worker.finished_signal.connect(self._on_launch_finished)
        self._build_ui()
        self.refresh_current_account()
        self.refresh_versions()

    def _get_java_path(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                return settings.get("java_path", "")
        return ""

    def _get_mem_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                return settings.get("mem_min", 2048), settings.get("mem_max", 4096)
        return 2048, 4096

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
        title = SectionTitle("启动")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("就绪", "normal")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle("选好版本，点一下就能开玩")
        main_layout.addWidget(sub)

        block = QFrame()
        block.setObjectName("card")
        block.setFrameShape(QFrame.StyledPanel)
        block_layout = QVBoxLayout(block)
        block_layout.setSpacing(16)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(QLabel("版本:"))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumHeight(36)
        self.version_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1.addWidget(self.version_combo, 1)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("btnSecondary")
        refresh_btn.setMinimumHeight(34)
        refresh_btn.setMinimumWidth(60)
        refresh_btn.clicked.connect(self.refresh_versions)
        row1.addWidget(refresh_btn)

        row1.addWidget(QLabel("玩家:"))
        self.player_label = QLabel("TestPlayer")
        self.player_label.setStyleSheet("font-weight: bold;")
        self.player_label.setMinimumWidth(80)
        row1.addWidget(self.player_label)

        self.switch_account_btn = QPushButton("换号")
        self.switch_account_btn.setObjectName("btnSecondary")
        self.switch_account_btn.setMinimumHeight(34)
        self.switch_account_btn.clicked.connect(lambda: self.switch_to_account.emit())
        row1.addWidget(self.switch_account_btn)

        block_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addStretch()
        self.launch_btn = QPushButton("开始")
        self.launch_btn.setMinimumHeight(48)
        self.launch_btn.setMinimumWidth(200)
        launch_font = QFont()
        launch_font.setPointSize(15)
        launch_font.setBold(True)
        self.launch_btn.setFont(launch_font)
        self.launch_btn.clicked.connect(self._launch_game)
        row2.addWidget(self.launch_btn)
        row2.addStretch()
        block_layout.addLayout(row2)

        main_layout.addWidget(block)

        self.launch_progress = QProgressBar()
        self.launch_progress.setValue(0)
        self.launch_progress.setTextVisible(True)
        self.launch_progress.setMinimumHeight(24)
        self.launch_progress.hide()
        main_layout.addWidget(self.launch_progress)

        self.launch_progress_label = QLabel("")
        self.launch_progress_label.setFont(QFont("", 11))
        self.launch_progress_label.hide()
        main_layout.addWidget(self.launch_progress_label)

        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

    def refresh_current_account(self):
        acc = get_default_account()
        if acc:
            self.player_label.setText(acc["name"])
        else:
            self.player_label.setText("TestPlayer")

    def refresh_versions(self):
        self.version_combo.clear()
        game_root = self.game_root
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
            QMessageBox.warning(self, "提示", "先选个版本")
            return

        java_path = self._get_java_path()
        if not java_path or not os.path.exists(java_path):
            QMessageBox.warning(self, "提示", "请先在设置页面配置 Java 路径")
            return

        game_root = self.game_root
        mem_min, mem_max = self._get_mem_settings()
        player_name = self.player_label.text().strip() or "TestPlayer"

        self.launch_btn.setEnabled(False)
        self.launch_progress.show()
        self.launch_progress_label.show()
        self.launch_progress.setValue(0)
        self.launch_progress_label.setText("准备启动...")

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
            self.crash_detector = CrashDetector(self.game_root)
            self.crash_detector.monitor_process(proc)
            self.monitor_timer.start()
            self.status_badge.set_status("normal", "玩着呢")
            self.launch_progress.setValue(100)
            self.launch_progress.setFormat("游戏运行中")
            self.launch_progress_label.setText("起来了，玩吧")
        else:
            self.launch_btn.setEnabled(True)
            self.launch_progress.hide()
            self.launch_progress_label.hide()
            self.status_badge.set_status("error", "没起来")
            QMessageBox.critical(self, "没起来", msg)

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
                    self.status_badge.set_status("error", "崩了")
                elif exit_code is not None and exit_code != 0:
                    self.status_badge.set_status("error", f"闪了 ({exit_code})")
                    QMessageBox.warning(self, "闪了", f"Exit code: {exit_code}")
                else:
                    self.status_badge.set_status("normal", "停了")
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
        msg = "崩了!\n\n"
        msg += f"Type: {analysis.get('type', 'unknown')}\n"
        msg += f"Description: {analysis.get('description', '')}\n"
        if analysis.get('suggestion'):
            msg += f"Suggestion: {analysis.get('suggestion')}\n\n"
        msg += "Report:\n" + (report[:2000] if report else "N/A")

        reply = QMessageBox.critical(
            self, "崩了", msg,
            QMessageBox.Ok | QMessageBox.Save,
            QMessageBox.Ok
        )
        if reply == QMessageBox.Save:
            self._export_logs()

    def _export_logs(self):
        game_root = self.game_root
        detector = CrashDetector(game_root)
        export_dir, files = detector.export_logs()
        QMessageBox.information(
            self, "导好了",
            f"导好了:\n{export_dir}\n\nFiles:\n" + "\n".join(files)
        )