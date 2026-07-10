import os
import sys
import subprocess
import threading
import re
import time
import socket
import json
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QCheckBox, QComboBox,
    QMessageBox, QScrollArea, QProgressBar,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge
from gui.i18n import tr
from core.e4mc_manager import E4MCManager


class EasyTierWorker(QObject):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool, str)
    ip_signal = pyqtSignal(str)
    peers_updated = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        launcher_root = get_project_root()
        self.tools_dir = Path(launcher_root) / "tools" / "easytier"
        if sys.platform == "win32":
            self.core_path = self.tools_dir / "easytier-core.exe"
            self.cli_path = self.tools_dir / "easytier-cli.exe"
        else:
            self.core_path = self.tools_dir / "easytier-core"
            self.cli_path = self.tools_dir / "easytier-cli"

        self.process = None
        self.running = False
        self._stop_flag = False
        self._lock = threading.Lock()
        self._rpc_port = 22015
        self._listen_port = 22014
        self._role = ""
        self._ip_candidates = []
        self._ip_index = 0
        self._peers = []
        self._poll_timer = None
        self.virtual_ip = ""
        self._exit_code = None

    def check_binaries(self):
        if not self.core_path.exists():
            self.log_signal.emit(f"[EasyTier] Missing easytier-core in {self.tools_dir}")
            self.error_signal.emit(f"Missing easytier-core in {self.tools_dir}")
            return False
        if not self.cli_path.exists():
            self.log_signal.emit(f"[EasyTier] Missing easytier-cli in {self.tools_dir}")
            self.error_signal.emit(f"Missing easytier-cli in {self.tools_dir}")
            return False
        return True

    def _is_port_open(self, port, timeout=1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                result = s.connect_ex(("127.0.0.1", port))
                return result == 0
        except Exception:
            return False

    def _find_available_rpc_port(self):
        for offset in range(0, 50):
            port = self._rpc_port + offset
            if not self._is_port_open(port):
                self._rpc_port = port
                self._listen_port = port - 1
                return True
        return False

    def check_firewall(self, parent_widget=None):
        if sys.platform != "win32":
            return True
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5
            )
            if "off" in result.stdout.lower():
                return True
        except Exception:
            pass
        if parent_widget:
            msg = QMessageBox(parent_widget)
            msg.setWindowTitle(tr("mp_firewall_title"))
            msg.setIcon(QMessageBox.Warning)
            msg.setText(
                "EasyTier requires network access. Please ensure:\n\n"
                "1. Temporarily disable Windows Firewall (for testing)\n"
                "   OR\n"
                "2. Add EasyTier to firewall whitelist:\n"
                f"   {self.core_path}\n\n"
                "If connection fails, check firewall settings first."
            )
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            msg.button(QMessageBox.Ok).setText(tr("btn_confirm"))
            msg.button(QMessageBox.Cancel).setText(tr("btn_cancel"))
            return msg.exec_() == QMessageBox.Ok
        return True

    def start_host(self, network_name, network_secret, hostname=None, parent_widget=None, enable_relay=True):
        if not self.check_firewall(parent_widget):
            return False
        return self._do_start("host", network_name, network_secret, hostname, enable_relay)

    def start_join(self, network_name, network_secret, hostname=None, parent_widget=None, enable_relay=True):
        if not self.check_firewall(parent_widget):
            return False
        return self._do_start("join", network_name, network_secret, hostname, enable_relay)

    def _do_start(self, role, network_name, network_secret, hostname=None, enable_relay=True):
        with self._lock:
            if self.running:
                self.log_signal.emit("[EasyTier] Node already running")
                return True
            if not self.check_binaries():
                return False

            if not self._find_available_rpc_port():
                self.error_signal.emit("No available RPC port found")
                return False

            self._role = role
            self._ip_index = 0
            self._ip_candidates = []
            self._exit_code = None
            self._stop_flag = False
            self.virtual_ip = ""

            cmd = [
                str(self.core_path),
                "--network-name", network_name,
                "--network-secret", network_secret,
                "--listeners", f"tcp://0.0.0.0:{self._listen_port},udp://0.0.0.0:{self._listen_port}",
                "--rpc-portal", f"127.0.0.1:{self._rpc_port}",
            ]
            if not enable_relay:
                cmd.append("--p2p-only")
            if hostname:
                cmd.extend(["--hostname", hostname])

            self.log_signal.emit(f"[EasyTier] Starting node: {network_name} ({role})")
            self.log_signal.emit(f"[EasyTier] RPC port: {self._rpc_port}")

            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    startupinfo=startupinfo, text=False, bufsize=0
                )
                self.running = True
                self.status_signal.emit(True, tr("mp_starting"))
                threading.Thread(target=self._read_output, daemon=True).start()
                threading.Thread(target=self._wait_for_ip, daemon=True).start()
                self.log_signal.emit("[EasyTier] Node started")
                self._start_peer_polling()
                return True
            except Exception as e:
                self.log_signal.emit(f"[EasyTier] Start failed: {e}")
                self.status_signal.emit(False, str(e))
                self.error_signal.emit(str(e))
                self.running = False
                return False

    def _start_peer_polling(self):
        if self._poll_timer is None:
            self._poll_timer = QTimer()
            self._poll_timer.setInterval(3000)
            self._poll_timer.timeout.connect(self._poll_peers)
            self._poll_timer.start()
            self._poll_peers()

    def _poll_peers(self):
        if not self.running or self._stop_flag:
            return
        peers = self._get_peers()
        new_set = frozenset([(p.get('ip', ''), p.get('hostname', '')) for p in peers])
        old_set = frozenset([(p.get('ip', ''), p.get('hostname', '')) for p in self._peers])
        if new_set != old_set:
            self._peers = peers
            self.peers_updated.emit(peers)

    def _parse_own_ip_from_log(self, text):
        if self.virtual_ip:
            return
        patterns = [
            r'assign ipv4[:\s]+(\d+\.\d+\.\d+\.\d+)',
            r'local virtual ip[:\s]+(\d+\.\d+\.\d+\.\d+)',
            r'virtual ip[:\s]+(\d+\.\d+\.\d+\.\d+)',
            r'ipv4[:\s]+(\d+\.\d+\.\d+\.\d+)',
            r'(?i)ip[:\s]+(10\.\d+\.\d+\.\d+)',
            r'(?i)ip[:\s]+(172\.1[6-9]\.\d+\.\d+|172\.2[0-9]\.\d+\.\d+|172\.3[01]\.\d+\.\d+)',
            r'(?i)ip[:\s]+(192\.168\.\d+\.\d+)',
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                ip = match.group(1)
                if self._is_private_ip(ip):
                    self.virtual_ip = ip
                    self._ip_candidates = [ip]
                    self.ip_signal.emit(ip)
                    self.status_signal.emit(True, f"{tr('mp_connected')} - {ip}")
                    return

    def _read_output(self):
        if not self.process:
            return
        try:
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                try:
                    text = line.decode('utf-8', errors='replace').strip()
                except Exception:
                    text = str(line)
                if text:
                    self.log_signal.emit(f"[EasyTier] {text}")
                    self._parse_own_ip_from_log(text)
        except Exception:
            pass

        with self._lock:
            self._exit_code = self.process.poll() if self.process else None
            self.running = False
            self._stop_flag = True

        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

        if self._exit_code is not None and self._exit_code != 0:
            self.log_signal.emit(f"[EasyTier] Process exited with code {self._exit_code}")
            self.status_signal.emit(False, f"{tr('mp_disconnected')} (code {self._exit_code})")
            self.error_signal.emit(f"EasyTier exited with code {self._exit_code}")
        else:
            self.status_signal.emit(False, tr("mp_disconnected"))

    def _wait_for_ip(self):
        max_wait = 30
        interval = 1.5
        elapsed = 0
        while elapsed < max_wait and not self._stop_flag:
            time.sleep(interval)
            elapsed += interval
            if self.virtual_ip:
                return
            ips = self._get_virtual_ips()
            if ips:
                self.virtual_ip = ips[0]
                self._ip_candidates = ips
                self.ip_signal.emit(ips[0])
                self.status_signal.emit(True, f"{tr('mp_connected')} - {ips[0]}")
                return
            if elapsed >= 6 and self._role == "join":
                self.status_signal.emit(True, tr("mp_connecting"))
                self.log_signal.emit("[EasyTier] Still connecting...")

        if not self._stop_flag and not self.virtual_ip:
            if self._role == "host":
                self.status_signal.emit(True, tr("mp_connecting"))
                self.log_signal.emit("[EasyTier] Waiting for peers...")
            else:
                self.status_signal.emit(False, "Cannot join network, check room name/password")
                self.error_signal.emit("Join timeout: check room name/password/firewall")

    def _get_virtual_ips(self):
        if not self.cli_path.exists():
            return []
        try:
            result = subprocess.run(
                [str(self.cli_path), "--rpc-portal", f"127.0.0.1:{self._rpc_port}", "peer"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5
            )
            if result.returncode != 0:
                return []
            ips = []
            for line in result.stdout.splitlines():
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    ip = match.group(1)
                    if self._is_private_ip(ip):
                        ips.append(ip)
            return ips
        except Exception:
            return []

    def _get_peers(self):
        if not self.cli_path.exists():
            return []
        try:
            result = subprocess.run(
                [str(self.cli_path), "--rpc-portal", f"127.0.0.1:{self._rpc_port}", "peer"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5
            )
            if result.returncode != 0:
                return []
            lines = result.stdout.splitlines()
            peers = []
            header_skipped = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if not header_skipped:
                    if "virtual ip" in line.lower() or "hostname" in line.lower():
                        header_skipped = True
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0] if parts[0] != "-" else None
                    hostname = parts[1] if len(parts) > 1 else "Unknown"
                    if ip and self._is_private_ip(ip):
                        peers.append({"ip": ip, "hostname": hostname})
            return peers
        except Exception:
            return []

    @staticmethod
    def _is_private_ip(ip):
        if ip.startswith("10."):
            return True
        if ip.startswith("192.168."):
            return True
        if ip.startswith("172."):
            try:
                second = int(ip.split(".")[1])
                if 16 <= second <= 31:
                    return True
            except (ValueError, IndexError):
                pass
        return False

    def get_next_ip(self):
        if not self._ip_candidates:
            self._ip_candidates = self._get_virtual_ips()
            self._ip_index = 0
        if self._ip_index < len(self._ip_candidates):
            ip = self._ip_candidates[self._ip_index]
            self._ip_index += 1
            return ip
        return None

    def reset_ip_index(self):
        self._ip_index = 0
        self._ip_candidates = self._get_virtual_ips()

    def stop_node(self):
        with self._lock:
            self._stop_flag = True
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=1)
                except Exception as e:
                    self.log_signal.emit(f"[EasyTier] Stop error: {e}")
                finally:
                    self.process = None
            self.running = False
            self._ip_index = 0
            self._ip_candidates = []
            self._peers = []
            if self._poll_timer:
                self._poll_timer.stop()
                self._poll_timer = None
        self.log_signal.emit("[EasyTier] Node stopped")
        self.status_signal.emit(False, tr("mp_not_running"))
        return True


class MultiplayerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.game_root = os.path.join(get_project_root(), ".minecraft")
        self.e4mc = E4MCManager(self.game_root)
        self.e4mc.progress.connect(self._on_e4mc_progress)
        self.e4mc.finished.connect(self._on_e4mc_finished)

        self.worker = EasyTierWorker()
        self.worker.log_signal.connect(self._append_log)
        self.worker.status_signal.connect(self._on_easytier_status)
        self.worker.ip_signal.connect(self._on_easytier_ip)
        self.worker.peers_updated.connect(self._on_peers_updated)
        self.worker.error_signal.connect(self._on_error)

        self._current_e4mc_version = None
        self._current_loader_type = None

        self._build_ui()
        self._load_installed_versions()

    def _create_labeled_row(self, label_text, widget, label_width=100):
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(label_text)
        label.setFixedWidth(label_width)
        label_font = QFont()
        label_font.setPointSize(11)
        label.setFont(label_font)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

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
        title = SectionTitle("联机大厅")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("未开启", "warning")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle("选择联机方式，一键开启多人游戏")
        main_layout.addWidget(sub)

        e4mc_card = Card()
        e4mc_layout = QVBoxLayout(e4mc_card)
        e4mc_layout.setSpacing(12)

        e4mc_title = QLabel("e4mc 模组联机")
        e4mc_title.setFont(QFont("", 13, QFont.Bold))
        e4mc_layout.addWidget(e4mc_title)

        e4mc_desc = QLabel(
            "基于 e4mc 模组，房主自动生成公网地址，朋友直接连接。\n"
            "支持 Forge/Fabric/NeoForge/Quilt，无需公网IP。"
        )
        e4mc_desc.setWordWrap(True)
        e4mc_desc.setStyleSheet("color: palette(mid); font-size: 11px; padding: 4px 0;")
        e4mc_layout.addWidget(e4mc_desc)

        self.e4mc_version_combo = QComboBox()
        self.e4mc_version_combo.setMinimumHeight(34)
        self.e4mc_version_combo.currentIndexChanged.connect(self._on_e4mc_version_selected)
        e4mc_layout.addLayout(self._create_labeled_row("游戏版本", self.e4mc_version_combo))

        self.e4mc_loader_combo = QComboBox()
        self.e4mc_loader_combo.setMinimumHeight(34)
        self.e4mc_loader_combo.addItem("Fabric", "fabric")
        self.e4mc_loader_combo.addItem("Quilt", "quilt")
        self.e4mc_loader_combo.addItem("Forge", "forge")
        self.e4mc_loader_combo.addItem("NeoForge", "neoforge")
        e4mc_layout.addLayout(self._create_labeled_row("模组加载器", self.e4mc_loader_combo))

        self.e4mc_version_info = QLabel("")
        self.e4mc_version_info.setStyleSheet("color: palette(mid); font-size: 11px;")
        self.e4mc_version_info.setWordWrap(True)
        e4mc_layout.addWidget(self.e4mc_version_info)

        e4mc_btn_row = QHBoxLayout()
        self.e4mc_host_btn = QPushButton("开启联机")
        self.e4mc_host_btn.setMinimumHeight(38)
        self.e4mc_host_btn.setMinimumWidth(130)
        self.e4mc_host_btn.clicked.connect(self._start_e4mc)

        self.e4mc_stop_btn = QPushButton("关闭联机")
        self.e4mc_stop_btn.setObjectName("btnDanger")
        self.e4mc_stop_btn.setMinimumHeight(38)
        self.e4mc_stop_btn.setMinimumWidth(130)
        self.e4mc_stop_btn.setEnabled(False)
        self.e4mc_stop_btn.clicked.connect(self._stop_e4mc)

        self.e4mc_status_label = QLabel("未开启")
        self.e4mc_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #5b7a9a; color: #ffffff; border-radius: 4px;")

        self.e4mc_progress = QProgressBar()
        self.e4mc_progress.setValue(0)
        self.e4mc_progress.setVisible(False)
        self.e4mc_progress.setMinimumHeight(20)

        e4mc_btn_row.addWidget(self.e4mc_host_btn)
        e4mc_btn_row.addWidget(self.e4mc_stop_btn)
        e4mc_btn_row.addWidget(self.e4mc_status_label)
        e4mc_btn_row.addStretch()
        e4mc_layout.addLayout(e4mc_btn_row)
        e4mc_layout.addWidget(self.e4mc_progress)

        self.e4mc_copy_btn = QPushButton("复制地址")
        self.e4mc_copy_btn.setObjectName("btnSecondary")
        self.e4mc_copy_btn.setMinimumHeight(30)
        self.e4mc_copy_btn.setMinimumWidth(120)
        self.e4mc_copy_btn.setVisible(False)
        self.e4mc_copy_btn.clicked.connect(self._copy_address)

        e4mc_copy_row = QHBoxLayout()
        e4mc_copy_row.addWidget(self.e4mc_copy_btn)
        e4mc_copy_row.addStretch()
        e4mc_layout.addLayout(e4mc_copy_row)

        main_layout.addWidget(e4mc_card)

        easytier_card = Card()
        easytier_layout = QVBoxLayout(easytier_card)
        easytier_layout.setSpacing(12)

        easytier_title = QLabel("EasyTier P2P 联机")
        easytier_title.setFont(QFont("", 13, QFont.Bold))
        easytier_layout.addWidget(easytier_title)

        easytier_desc = QLabel(
            "基于 EasyTier P2P 技术，无需服务器中转，完全免费。\n"
            "双方需使用相同房间名和密码。"
        )
        easytier_desc.setWordWrap(True)
        easytier_desc.setStyleSheet("color: palette(mid); font-size: 11px; padding: 4px 0;")
        easytier_layout.addWidget(easytier_desc)

        self.et_room_edit = QLineEdit()
        self.et_room_edit.setPlaceholderText("输入房间名 (如: MCOpenRoom)")
        self.et_room_edit.setMinimumHeight(34)
        self.et_room_edit.setText("MCOpenRoom")
        easytier_layout.addLayout(self._create_labeled_row("房间名", self.et_room_edit))

        self.et_password_edit = QLineEdit()
        self.et_password_edit.setPlaceholderText("设置联机密码")
        self.et_password_edit.setMinimumHeight(34)
        self.et_password_edit.setText("123456")
        easytier_layout.addLayout(self._create_labeled_row("密码", self.et_password_edit))

        relay_row = QHBoxLayout()
        relay_row.setSpacing(10)
        relay_spacer = QLabel("")
        relay_spacer.setFixedWidth(100)
        relay_row.addWidget(relay_spacer)
        self.et_relay_check = QCheckBox("启用中继转发 (保底方案)")
        self.et_relay_check.setChecked(True)
        relay_row.addWidget(self.et_relay_check)
        relay_row.addStretch()
        easytier_layout.addLayout(relay_row)

        et_btn_row = QHBoxLayout()
        self.et_host_btn = QPushButton("房主开房")
        self.et_host_btn.setMinimumHeight(38)
        self.et_host_btn.setMinimumWidth(130)
        self.et_host_btn.clicked.connect(self._start_easytier_host)

        self.et_join_btn = QPushButton("加入房间")
        self.et_join_btn.setObjectName("btnSecondary")
        self.et_join_btn.setMinimumHeight(38)
        self.et_join_btn.setMinimumWidth(130)
        self.et_join_btn.clicked.connect(self._start_easytier_join)

        self.et_stop_btn = QPushButton("关闭联机")
        self.et_stop_btn.setObjectName("btnDanger")
        self.et_stop_btn.setMinimumHeight(38)
        self.et_stop_btn.setMinimumWidth(130)
        self.et_stop_btn.setEnabled(False)
        self.et_stop_btn.clicked.connect(self._stop_easytier)

        self.et_status_label = QLabel("未开启")
        self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #5b7a9a; color: #ffffff; border-radius: 4px;")

        et_btn_row.addWidget(self.et_host_btn)
        et_btn_row.addWidget(self.et_join_btn)
        et_btn_row.addWidget(self.et_stop_btn)
        et_btn_row.addWidget(self.et_status_label)
        et_btn_row.addStretch()
        easytier_layout.addLayout(et_btn_row)

        self.et_copy_btn = QPushButton("复制地址")
        self.et_copy_btn.setObjectName("btnSecondary")
        self.et_copy_btn.setMinimumHeight(30)
        self.et_copy_btn.setMinimumWidth(120)
        self.et_copy_btn.setVisible(False)
        self.et_copy_btn.clicked.connect(self._copy_address)

        et_copy_row = QHBoxLayout()
        et_copy_row.addWidget(self.et_copy_btn)
        et_copy_row.addStretch()
        easytier_layout.addLayout(et_copy_row)

        self.et_peer_label = QLabel("在线成员:")
        self.et_peer_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        self.et_peer_label.setVisible(False)
        easytier_layout.addWidget(self.et_peer_label)

        self.et_peer_list = QLabel("暂无其他成员")
        self.et_peer_list.setWordWrap(True)
        self.et_peer_list.setStyleSheet("font-size: 11px; color: palette(mid); padding: 8px; background: palette(dark); border-radius: 6px;")
        self.et_peer_list.setVisible(False)
        easytier_layout.addWidget(self.et_peer_list)

        main_layout.addWidget(easytier_card)

        self.et_ip_label = QLabel("联机地址: 未获取")
        self.et_ip_label.setStyleSheet("font-size: 13px; color: #2d7d2d; font-weight: bold;")
        main_layout.addWidget(self.et_ip_label)

        self.et_help_label = QLabel("")
        self.et_help_label.setStyleSheet("font-size: 11px; color: palette(mid);")
        main_layout.addWidget(self.et_help_label)

        log_card = Card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setSpacing(10)
        log_title = QLabel("日志")
        log_title.setFont(QFont("", 13, QFont.Bold))
        log_layout.addWidget(log_title)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        self.log_text.setMaximumHeight(200)
        log_font = QFont("Consolas", 10)
        self.log_text.setFont(log_font)
        log_layout.addWidget(self.log_text)

        log_btn_row = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.setObjectName("btnSecondary")
        self.clear_log_btn.setMinimumHeight(32)
        self.clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_btn_row.addWidget(self.clear_log_btn)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        main_layout.addWidget(log_card)
        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

        self._update_help_text()

    def _load_installed_versions(self):
        self.e4mc_version_combo.clear()
        versions_dir = Path(self.game_root) / "versions"
        if not versions_dir.exists():
            self.e4mc_version_combo.addItem("未找到任何版本", None)
            return

        for dir_item in versions_dir.iterdir():
            if not dir_item.is_dir() or dir_item.name == "natives":
                continue
            self.e4mc_version_combo.addItem(dir_item.name, dir_item.name)

        if self.e4mc_version_combo.count() == 0:
            self.e4mc_version_combo.addItem("未找到任何版本", None)

    def _is_version_supported(self, version_id):
        try:
            import re
            match = re.search(r'(\d+)\.(\d+)', version_id)
            if match:
                major = int(match.group(1))
                minor = int(match.group(2))
                if major > 1 or (major == 1 and minor >= 18):
                    return True
            return False
        except:
            return False

    def _on_e4mc_version_selected(self, index):
        version_id = self.e4mc_version_combo.currentData()
        if not version_id:
            self.e4mc_version_info.setText("请选择有效版本")
            self.e4mc_host_btn.setEnabled(False)
            return

        supports = self._is_version_supported(version_id)
        if supports:
            self.e4mc_version_info.setText(f"已选版本: {version_id}")
            self.e4mc_version_info.setStyleSheet("color: #4a8c5c; font-weight: bold;")
            self.e4mc_host_btn.setEnabled(True)
        else:
            self.e4mc_version_info.setText(
                f"Minecraft {version_id} 可能不支持 e4mc 联机（需要 1.18 及以上版本）"
            )
            self.e4mc_version_info.setStyleSheet("color: #a0525a; font-weight: bold;")
            self.e4mc_host_btn.setEnabled(False)

    def _update_help_text(self):
        self.et_help_label.setText("e4mc：进入游戏后点击「对局域网开放」生成地址 | EasyTier：朋友加入后输入虚拟IP")

    def _start_e4mc(self):
        version_id = self.e4mc_version_combo.currentData()
        if not version_id:
            QMessageBox.warning(self, "提示", "请选择一个游戏版本")
            return
        if not self._is_version_supported(version_id):
            QMessageBox.warning(self, "提示", "该版本可能不支持 e4mc 联机（需要 1.18 及以上版本）")
            return

        loader_type = self.e4mc_loader_combo.currentData()
        if not loader_type:
            loader_type = "fabric"

        self.e4mc_host_btn.setEnabled(False)
        self.e4mc_status_label.setText("正在下载模组...")
        self.e4mc_copy_btn.setVisible(False)
        self.et_ip_label.setText("联机地址: 未获取")
        self.e4mc_progress.setVisible(True)
        self.e4mc_progress.setValue(0)
        self._current_e4mc_version = version_id
        self._current_loader_type = loader_type
        self._append_log(f"[e4mc] 开始下载 e4mc-{version_id}.jar ({loader_type})")

        self.e4mc.install_async(version_id, loader_type)

    def _on_e4mc_progress(self, pct, msg):
        self.e4mc_progress.setVisible(True)
        self.e4mc_progress.setValue(pct)
        self.e4mc_status_label.setText(msg)

    def _on_e4mc_finished(self, success, msg):
        self.e4mc_progress.setVisible(False)
        self.e4mc_host_btn.setEnabled(True)
        version_id = self._current_e4mc_version
        if success:
            self.e4mc_status_label.setText("就绪，启动游戏")
            self.e4mc_stop_btn.setEnabled(True)
            if version_id:
                self.et_ip_label.setText(f"联机地址: e4mc-{version_id}.e4mc.com")
            self.e4mc_copy_btn.setVisible(True)
            self._append_log(f"[e4mc] {msg}")
            self._append_log("[e4mc] 进入游戏后点击「对局域网开放」即可生成公网地址")
            self.status_badge.set_status("normal", "已就绪")
            self.e4mc_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #4a8c5c; color: #ffffff; border-radius: 4px;")
        else:
            self.e4mc_status_label.setText("下载失败")
            self.e4mc_stop_btn.setEnabled(False)
            self.e4mc_copy_btn.setVisible(False)
            self.e4mc_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #a0525a; color: #ffffff; border-radius: 4px;")
            QMessageBox.warning(self, "下载失败", msg)
            self.status_badge.set_status("error", "下载失败")

    def _stop_e4mc(self):
        self.e4mc.cancel()
        self.e4mc.cleanup()
        self.e4mc_host_btn.setEnabled(True)
        self.e4mc_stop_btn.setEnabled(False)
        self.e4mc_status_label.setText("已关闭")
        self.e4mc_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #5b7a9a; color: #ffffff; border-radius: 4px;")
        self.et_ip_label.setText("联机地址: 未获取")
        self.e4mc_progress.setVisible(False)
        self.e4mc_copy_btn.setVisible(False)
        self.status_badge.set_status("warning", "已关闭")
        self._append_log("[e4mc] 联机关闭")

    def _start_easytier_host(self):
        room = self.et_room_edit.text().strip()
        password = self.et_password_edit.text().strip()
        enable_relay = self.et_relay_check.isChecked()
        if not room:
            QMessageBox.warning(self, "提示", "请输入房间名")
            return
        if not password:
            password = "123456"

        self.et_host_btn.setEnabled(False)
        self.et_join_btn.setEnabled(False)
        self.et_status_label.setText("正在开房...")
        self.et_copy_btn.setVisible(False)
        self.et_ip_label.setText("联机地址: 未获取")
        self.et_peer_label.setVisible(True)
        self.et_peer_list.setVisible(True)
        self._append_log(f"[EasyTier] 房主开房: {room}")

        success = self.worker.start_host(room, password, "MCOpen_Host", self, enable_relay)
        if not success:
            self.et_host_btn.setEnabled(True)
            self.et_join_btn.setEnabled(True)
            self.et_status_label.setText("开房失败")
            self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #a0525a; color: #ffffff; border-radius: 4px;")
            self.status_badge.set_status("error", "开房失败")

    def _start_easytier_join(self):
        room = self.et_room_edit.text().strip()
        password = self.et_password_edit.text().strip()
        enable_relay = self.et_relay_check.isChecked()
        if not room:
            QMessageBox.warning(self, "提示", "请输入房间名")
            return
        if not password:
            password = "123456"

        self.et_host_btn.setEnabled(False)
        self.et_join_btn.setEnabled(False)
        self.et_status_label.setText("正在加入...")
        self.et_copy_btn.setVisible(False)
        self.et_ip_label.setText("联机地址: 未获取")
        self._append_log(f"[EasyTier] 加入房间: {room}")

        success = self.worker.start_join(room, password, "MCOpen_Join", self, enable_relay)
        if not success:
            self.et_host_btn.setEnabled(True)
            self.et_join_btn.setEnabled(True)
            self.et_status_label.setText("加入失败")
            self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #a0525a; color: #ffffff; border-radius: 4px;")
            self.status_badge.set_status("error", "加入失败")
        else:
            QMessageBox.information(self, "加入房间教程",
                "已成功加入虚拟网络！\n\n"
                "请在游戏内按以下步骤操作：\n"
                "1. 向房主索要他的虚拟 IP\n"
                "2. 启动 Minecraft 客户端，进入多人游戏\n"
                "3. 点击「添加服务器」或「直接连接」\n"
                "4. 输入房主的虚拟 IP（例如 10.126.126.1）\n"
                "5. 点击「加入」即可联机！\n\n"
                "提示：房主的虚拟 IP 可在他的启动器联机卡片上查看。"
            )

    def _stop_easytier(self):
        self.worker.stop_node()
        self.et_host_btn.setEnabled(True)
        self.et_join_btn.setEnabled(True)
        self.et_stop_btn.setEnabled(False)
        self.et_status_label.setText("已关闭")
        self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #5b7a9a; color: #ffffff; border-radius: 4px;")
        self.et_ip_label.setText("联机地址: 未获取")
        self.et_peer_label.setVisible(False)
        self.et_peer_list.setVisible(False)
        self.et_copy_btn.setVisible(False)
        self.status_badge.set_status("warning", "已关闭")
        self._append_log("[EasyTier] 联机关闭")

    def _on_easytier_status(self, running, msg):
        if running:
            self.et_status_label.setText(msg)
            self.et_host_btn.setEnabled(False)
            self.et_join_btn.setEnabled(False)
            self.et_stop_btn.setEnabled(True)
            if "已连接" in msg or "虚拟IP" in msg:
                self.et_copy_btn.setVisible(True)
                self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #4a8c5c; color: #ffffff; border-radius: 4px;")
                self.status_badge.set_status("normal", "已连接")
            else:
                self.et_copy_btn.setVisible(False)
                self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #c48a4a; color: #ffffff; border-radius: 4px;")
                self.status_badge.set_status("info", "连接中")
        else:
            if "断开" in msg or "停止" in msg:
                self.et_host_btn.setEnabled(True)
                self.et_join_btn.setEnabled(True)
                self.et_stop_btn.setEnabled(False)
                self.et_status_label.setText("已断开")
                self.et_status_label.setStyleSheet("font-size: 12px; padding: 6px 12px; background: #a0525a; color: #ffffff; border-radius: 4px;")
                self.status_badge.set_status("warning", "已断开")
                self.et_peer_label.setVisible(False)
                self.et_peer_list.setVisible(False)

    def _on_easytier_ip(self, ip):
        self.et_ip_label.setText(f"联机地址: {ip}")
        self._append_log(f"[EasyTier] 虚拟IP: {ip}")
        self._append_log(f"[EasyTier] 朋友在游戏内输入 {ip} 即可加入")

    def _on_peers_updated(self, peers):
        if not peers:
            self.et_peer_list.setText("暂无其他成员")
            return
        lines = []
        for peer in peers:
            ip = peer.get("ip", "")
            hostname = peer.get("hostname", "未知")
            if ip:
                lines.append(f"{hostname}  -  {ip}")
            else:
                lines.append(f"{hostname}  -  未获取到IP")
        self.et_peer_list.setText("\n".join(lines))

    def _on_error(self, msg):
        self._append_log(f"[错误] {msg}")
        self.status_badge.set_status("error", "错误")

    def _copy_address(self):
        text = self.et_ip_label.text().replace("联机地址: ", "").strip()
        if text and text != "未获取":
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.e4mc_status_label.setText("地址已复制")
            self.et_status_label.setText("地址已复制")
            self._append_log(f"[联机] 已复制地址: {text}")

    def _append_log(self, text):
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())