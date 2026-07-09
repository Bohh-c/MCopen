import os
import threading
import subprocess

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFormLayout, QComboBox,
    QMessageBox, QSlider, QProgressBar, QFileDialog, QScrollArea,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from core.downloader import download_server, fetch_version_manifest, find_version
from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge


class ServerWorker(QObject):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.process = None

    def start_server(self, java_path, jar_path, server_dir, mem_min, mem_max, extra_args):
        try:
            env = os.environ.copy()
            args = [
                java_path,
                f"-Xms{mem_min}M", f"-Xmx{mem_max}M",
                "-jar", jar_path,
                "nogui"
            ]
            if extra_args.strip():
                args.extend(extra_args.strip().split())

            self.process = subprocess.Popen(
                args, cwd=server_dir, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=False,
                bufsize=1
            )
            self.status_signal.emit(True)
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                try:
                    text = line.decode('utf-8', errors='replace').rstrip()
                except:
                    text = str(line)
                if text:
                    self.log_signal.emit(text)
            self.process.stdout.close()
            self.process.wait()
            self.status_signal.emit(False)
            self.log_signal.emit("--- 服务器已停止 ---")
        except Exception as e:
            self.log_signal.emit(f"启动失败: {e}")
            self.status_signal.emit(False)

    def stop_server(self):
        if self.process and self.process.poll() is None:
            self.process.stdin.write("stop\n".encode('utf-8'))
            self.process.stdin.flush()

    def send_command(self, cmd):
        if self.process and self.process.poll() is None:
            self.process.stdin.write((cmd + "\n").encode('utf-8'))
            self.process.stdin.flush()


class DownloadServerWorker(QObject):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)
    version_list_signal = pyqtSignal(list)

    def fetch_versions(self):
        try:
            manifest = fetch_version_manifest()
            versions = manifest.get("versions", [])
            releases = [v for v in versions if v.get("type") == "release"]
            releases_sorted = sorted(releases, key=lambda v: v.get("releaseTime", ""), reverse=True)
            self.version_list_signal.emit(releases_sorted)
        except Exception as e:
            self.finished_signal.emit(False, f"获取版本列表失败: {e}")

    def download_server(self, version_id, server_dir):
        try:
            def cb(pct, info):
                if isinstance(info, int):
                    size_mb = info / 1048576
                    self.progress_signal.emit(pct, f"下载中 ({pct}%) {size_mb:.1f} MB")
                else:
                    self.progress_signal.emit(pct, info)

            success, msg = download_server(version_id, server_dir, cb)

            if success:
                self.progress_signal.emit(100, msg)
                eula_path = os.path.join(server_dir, "eula.txt")
                with open(eula_path, "w") as f:
                    f.write("eula=true\n")
                self.finished_signal.emit(True, os.path.join(server_dir, f"{version_id}-server.jar"))
            else:
                self.finished_signal.emit(False, msg)
        except Exception as e:
            self.finished_signal.emit(False, f"下载失败: {e}")


class ServerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.server_dir = os.path.join(get_project_root(), "server")
        self.java_path = ""
        self._find_java()
        self.server_jar = ""
        self.running = False
        self.worker = ServerWorker()
        self.worker.log_signal.connect(self._append_log)
        self.worker.status_signal.connect(self._on_status)
        self.dl_worker = DownloadServerWorker()
        self.dl_worker.version_list_signal.connect(self._on_version_list)
        self.dl_worker.progress_signal.connect(self._on_dl_progress)
        self.dl_worker.finished_signal.connect(self._on_dl_finished)
        self._build_ui()

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
        title = SectionTitle("服务器管理")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("已停止", "warning")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle("管理本地 Minecraft 服务器")
        main_layout.addWidget(sub)

        card1 = Card()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setSpacing(14)

        card1_title = QLabel("服务器配置")
        card1_font = QFont()
        card1_font.setPointSize(13)
        card1_font.setBold(True)
        card1_title.setFont(card1_font)
        card1_layout.addWidget(card1_title)

        form = QFormLayout()
        form.setSpacing(12)

        label_font = QFont()
        label_font.setPointSize(11)

        server_dir_row = QHBoxLayout()
        self.server_dir_edit = QLineEdit(self.server_dir)
        self.server_dir_edit.setPlaceholderText("服务器目录")
        self.server_dir_edit.setMinimumHeight(36)
        self.server_dir_edit.setFont(label_font)
        server_dir_btn = QPushButton("浏览")
        server_dir_btn.setObjectName("btnSecondary")
        server_dir_btn.setMinimumHeight(36)
        server_dir_btn.setMinimumWidth(80)
        server_dir_btn.setFont(label_font)
        server_dir_btn.clicked.connect(self._select_server_dir)
        server_dir_row.addWidget(self.server_dir_edit)
        server_dir_row.addWidget(server_dir_btn)
        form.addRow("服务器目录", server_dir_row)

        java_row = QHBoxLayout()
        self.java_edit = QLineEdit(self.java_path)
        self.java_edit.setPlaceholderText("Java 可执行文件")
        self.java_edit.setMinimumHeight(36)
        self.java_edit.setFont(label_font)
        java_btn = QPushButton("选择")
        java_btn.setObjectName("btnSecondary")
        java_btn.setMinimumHeight(36)
        java_btn.setMinimumWidth(80)
        java_btn.setFont(label_font)
        java_btn.clicked.connect(self._select_java)
        java_row.addWidget(self.java_edit)
        java_row.addWidget(java_btn)
        form.addRow("Java 路径", java_row)

        card1_layout.addLayout(form)
        main_layout.addWidget(card1)

        card_dl = Card()
        card_dl_layout = QVBoxLayout(card_dl)
        card_dl_layout.setSpacing(14)

        dl_title = QLabel("下载服务端核心")
        dl_title.setFont(card1_font)
        card_dl_layout.addWidget(dl_title)

        dl_row = QHBoxLayout()
        dl_row.addWidget(QLabel("选择版本:"))
        self.version_combo = QComboBox()
        self.version_combo.setMinimumHeight(36)
        self.version_combo.setFont(label_font)
        self.version_combo.setMinimumWidth(200)
        dl_row.addWidget(self.version_combo)

        self.fetch_ver_btn = QPushButton("获取版本")
        self.fetch_ver_btn.setObjectName("btnSecondary")
        self.fetch_ver_btn.setMinimumHeight(36)
        self.fetch_ver_btn.setFont(label_font)
        self.fetch_ver_btn.clicked.connect(self._fetch_versions)
        dl_row.addWidget(self.fetch_ver_btn)

        dl_row.addStretch()

        self.download_btn = QPushButton("下载服务端核心")
        self.download_btn.setMinimumHeight(40)
        self.download_btn.setMinimumWidth(160)
        dl_font = QFont()
        dl_font.setPointSize(12)
        dl_font.setBold(True)
        self.download_btn.setFont(dl_font)
        self.download_btn.clicked.connect(self._download_server)
        dl_row.addWidget(self.download_btn)
        card_dl_layout.addLayout(dl_row)

        self.dl_progress = QProgressBar()
        self.dl_progress.setValue(0)
        self.dl_progress.setVisible(False)
        self.dl_progress.setMinimumHeight(24)
        card_dl_layout.addWidget(self.dl_progress)

        self.dl_label = QLabel("")
        self.dl_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        self.dl_label.setVisible(False)
        card_dl_layout.addWidget(self.dl_label)

        main_layout.addWidget(card_dl)

        card2 = Card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(14)

        card2_title = QLabel("内存 & 参数")
        card2_title.setFont(card1_font)
        card2_layout.addWidget(card2_title)

        mem_row = QHBoxLayout()
        mem_label = QLabel("最小内存")
        mem_label.setFixedWidth(70)
        mem_label.setFont(label_font)
        mem_row.addWidget(mem_label)
        self.min_mem_slider = QSlider(Qt.Horizontal)
        self.min_mem_slider.setRange(512, 32768)
        self.min_mem_slider.setValue(2048)
        self.min_mem_label = QLabel("2048 MB")
        self.min_mem_label.setFixedWidth(80)
        self.min_mem_label.setAlignment(Qt.AlignRight)
        self.min_mem_label.setFont(label_font)
        self.min_mem_slider.valueChanged.connect(lambda v: self.min_mem_label.setText(f"{v} MB"))
        mem_row.addWidget(self.min_mem_slider)
        mem_row.addWidget(self.min_mem_label)
        card2_layout.addLayout(mem_row)

        mem_row2 = QHBoxLayout()
        mem_label2 = QLabel("最大内存")
        mem_label2.setFixedWidth(70)
        mem_label2.setFont(label_font)
        mem_row2.addWidget(mem_label2)
        self.max_mem_slider = QSlider(Qt.Horizontal)
        self.max_mem_slider.setRange(1024, 65536)
        self.max_mem_slider.setValue(4096)
        self.max_mem_label = QLabel("4096 MB")
        self.max_mem_label.setFixedWidth(80)
        self.max_mem_label.setAlignment(Qt.AlignRight)
        self.max_mem_label.setFont(label_font)
        self.max_mem_slider.valueChanged.connect(lambda v: self.max_mem_label.setText(f"{v} MB"))
        mem_row2.addWidget(self.max_mem_slider)
        mem_row2.addWidget(self.max_mem_label)
        card2_layout.addLayout(mem_row2)

        extra_row = QHBoxLayout()
        extra_row.addWidget(QLabel("额外参数:"))
        self.extra_args_edit = QLineEdit()
        self.extra_args_edit.setPlaceholderText("如: --port 25566")
        self.extra_args_edit.setMinimumHeight(36)
        self.extra_args_edit.setFont(label_font)
        extra_row.addWidget(self.extra_args_edit)
        card2_layout.addLayout(extra_row)

        main_layout.addWidget(card2)

        card3 = Card()
        card3_layout = QVBoxLayout(card3)
        card3_layout.setSpacing(14)

        card3_title = QLabel("控制台")
        card3_title.setFont(card1_font)
        card3_layout.addWidget(card3_title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.start_btn = QPushButton("启动服务器")
        start_font = QFont()
        start_font.setPointSize(12)
        start_font.setBold(True)
        self.start_btn.setFont(start_font)
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setMinimumWidth(140)
        self.start_btn.clicked.connect(self._start_server)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止服务器")
        self.stop_btn.setObjectName("btnDanger")
        self.stop_btn.setFont(start_font)
        self.stop_btn.setMinimumHeight(44)
        self.stop_btn.setMinimumWidth(140)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_server)
        btn_row.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.setObjectName("btnSecondary")
        self.clear_btn.setMinimumHeight(44)
        self.clear_btn.setMinimumWidth(120)
        clear_font = QFont()
        clear_font.setPointSize(11)
        self.clear_btn.setFont(clear_font)
        self.clear_btn.clicked.connect(self._clear_log)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        card3_layout.addLayout(btn_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(280)
        self.log_text.setMaximumHeight(800)
        log_font = QFont("Consolas", 10)
        self.log_text.setFont(log_font)
        card3_layout.addWidget(self.log_text)

        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(10)
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText("输入服务器命令...")
        self.cmd_edit.setMinimumHeight(38)
        self.cmd_edit.setFont(label_font)
        self.cmd_edit.returnPressed.connect(self._send_command)
        cmd_row.addWidget(self.cmd_edit)
        self.cmd_btn = QPushButton("发送")
        self.cmd_btn.setMinimumHeight(38)
        self.cmd_btn.setMinimumWidth(90)
        self.cmd_btn.setFont(label_font)
        self.cmd_btn.setEnabled(False)
        self.cmd_btn.clicked.connect(self._send_command)
        cmd_row.addWidget(self.cmd_btn)
        card3_layout.addLayout(cmd_row)

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
        card_dl_height = 120
        card2_height = 160
        cmd_height = 60
        available = height - header_height - card1_height - card_dl_height - card2_height - cmd_height - 100
        self.log_text.setMaximumHeight(max(280, available))
        event.accept()

    def _fetch_versions(self):
        thread = threading.Thread(target=self.dl_worker.fetch_versions, daemon=True)
        thread.start()

    def _on_version_list(self, versions):
        self.version_combo.clear()
        default_idx = 0
        for i, v in enumerate(versions):
            self.version_combo.addItem(f"{v['id']}  ({v.get('releaseTime', '')[:10]})", v)
            if v["id"] == "26.2":
                default_idx = i
        self.version_combo.setCurrentIndex(default_idx)

    def _download_server(self):
        version_info = self.version_combo.currentData()
        if not version_info:
            return
        version_id = version_info["id"]
        server_dir = self.server_dir_edit.text().strip()

        self.download_btn.setEnabled(False)
        self.dl_progress.setVisible(True)
        self.dl_progress.setValue(0)
        self.dl_label.setVisible(True)
        self.dl_label.setText("正在连接 Mojang...")

        thread = threading.Thread(
            target=self.dl_worker.download_server,
            args=(version_id, server_dir),
            daemon=True
        )
        thread.start()

    def _on_dl_progress(self, value, text):
        self.dl_progress.setValue(value)
        self.dl_label.setText(text)

    def _on_dl_finished(self, success, result):
        self.download_btn.setEnabled(True)
        if success:
            self.dl_progress.setValue(100)
            self.dl_label.setText("下载完成!")
            self.server_jar = result
            self._append_log(f"服务端核心已下载: {os.path.basename(result)}")
        else:
            self.dl_progress.setVisible(False)
            self.dl_label.setText(result)
            QMessageBox.critical(self, "下载失败", result)

    def _select_server_dir(self):
        selected = QFileDialog.getExistingDirectory(self, "选择服务器目录", self.server_dir)
        if selected:
            self.server_dir = selected
            self.server_dir_edit.setText(selected)

    def _select_java(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择 Java", self.java_path,
            "可执行文件 (*.exe *.bat *.cmd)"
        )
        if selected:
            self.java_path = selected
            self.java_edit.setText(selected)

    def _start_server(self):
        if self.running:
            return
        if not self.server_jar or not os.path.exists(self.server_jar):
            QMessageBox.warning(self, "提示", "请先下载或选择服务端核心")
            return
        java_path = self.java_edit.text().strip()
        if not java_path:
            QMessageBox.warning(self, "提示", "请设置 Java 路径")
            return
        server_dir = self.server_dir_edit.text().strip()
        if not os.path.isdir(server_dir):
            QMessageBox.warning(self, "提示", "请选择有效的服务器目录")
            return

        mem_min = self.min_mem_slider.value()
        mem_max = self.max_mem_slider.value()
        extra = self.extra_args_edit.text().strip()

        self.log_text.clear()
        self._append_log("正在启动服务器...")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.cmd_btn.setEnabled(True)

        thread = threading.Thread(
            target=self.worker.start_server,
            args=(java_path, self.server_jar, server_dir, mem_min, mem_max, extra),
            daemon=True
        )
        thread.start()

    def _stop_server(self):
        self._append_log("正在发送停止命令...")
        self.worker.stop_server()

    def _send_command(self):
        cmd = self.cmd_edit.text().strip()
        if cmd:
            self._append_log(f"> {cmd}")
            self.worker.send_command(cmd)
            self.cmd_edit.clear()

    def _append_log(self, text):
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_log(self):
        self.log_text.clear()

    def _find_java(self):
        import os
        candidates = [
            r"C:\Program Files\Microsoft\jdk-25.0.2.10-hotspot\bin\java.exe",
            r"C:\Program Files\Zulu\zulu-17\bin\java.exe",
            r"C:\Program Files\Java\jdk-17\bin\java.exe",
            r"C:\Program Files\Java\jre1.8.0_391\bin\java.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                self.java_path = path
                return
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            self.java_path = os.path.join(java_home, "bin", "java.exe")

    def _on_status(self, running):
        self.running = running
        if running:
            self.status_badge.set_status("normal", "运行中")
        else:
            self.status_badge.set_status("warning", "已停止")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.cmd_btn.setEnabled(False)