"""联机大厅页面 - EasyTier P2P 虚拟局域网联机"""

import os
import sys
import subprocess
import threading
import re
import time
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QCheckBox,
    QMessageBox, QScrollArea,
)
from PyQt5.QtGui import QFont

from core.cli import get_project_root
from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge
from gui.i18n import tr


class EasyTierWorker(QObject):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool, str)
    ip_signal = pyqtSignal(str)
    peers_updated = pyqtSignal(list)

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
        self._rpc_port = 21011
        self._listen_port = 21010
        self._role = ""
        self._ip_candidates = []
        self._ip_index = 0
        self._peers = []
        self._poll_timer = None

    def check_binaries(self):
        if not self.core_path.exists():
            self.log_signal.emit(f"[EasyTier] Missing easytier-core in {self.tools_dir}")
            return False
        if not self.cli_path.exists():
            self.log_signal.emit(f"[EasyTier] Missing easytier-cli in {self.tools_dir}")
            return False
        return True

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
        self._role = "host"
        self._ip_index = 0
        self._ip_candidates = []
        return self._start_node(network_name, network_secret, hostname, enable_relay)

    def start_join(self, network_name, network_secret, hostname=None, parent_widget=None, enable_relay=True):
        if not self.check_firewall(parent_widget):
            return False
        self._role = "join"
        self._ip_index = 0
        self._ip_candidates = []
        return self._start_node(network_name, network_secret, hostname, enable_relay)

    def _start_node(self, network_name, network_secret, hostname=None, enable_relay=True):
        if not self.check_binaries():
            self.status_signal.emit(False, "EasyTier core missing")
            return False
        if self.running:
            self.log_signal.emit("[EasyTier] Node already running")
            return True

        self._stop_flag = False
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

        self.log_signal.emit(f"[EasyTier] Starting node: {network_name} ({self._role})")

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                startupinfo=startupinfo, text=False, bufsize=1
            )
            self.running = True
            self.status_signal.emit(True, tr("mp_starting"))
            threading.Thread(target=self._read_output, daemon=False).start()
            threading.Thread(target=self._wait_for_ip, daemon=False).start()
            self.log_signal.emit("[EasyTier] Node started")
            if self._role == "host":
                self._start_peer_polling()
            return True
        except Exception as e:
            self.log_signal.emit(f"[EasyTier] Start failed: {e}")
            self.status_signal.emit(False, str(e))
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
                if self.process.poll() is not None:
                    break
        except Exception:
            pass
        self.running = False
        self.status_signal.emit(False, tr("mp_disconnected"))
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

    def _wait_for_ip(self):
        time.sleep(3)
        if not self._stop_flag:
            ips = self._get_virtual_ips()
            if ips:
                self.virtual_ip = ips[0]
                self._ip_candidates = ips
                self.ip_signal.emit(ips[0])
                self.status_signal.emit(True, f"{tr('mp_connected')} - {ips[0]}")
            else:
                if self._role == "host":
                    self.status_signal.emit(True, tr("mp_connecting"))
                    self.log_signal.emit("[EasyTier] Waiting for peers...")
                else:
                    self.status_signal.emit(False, "Cannot join network, check room name/password")

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
                    if ip.startswith("10.") or ip.startswith("192.168."):
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
            if len(lines) < 2:
                return []
            peers = []
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0] if parts[0] != "-" else None
                    hostname = parts[1] if len(parts) > 1 else "Unknown"
                    if ip and ip.startswith("10."):
                        peers.append({"ip": ip, "hostname": hostname})
            return peers
        except Exception:
            return []

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
        self._stop_flag = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
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
        self.worker = EasyTierWorker()
        self.worker.log_signal.connect(self._append_log)
        self.worker.status_signal.connect(self._on_status)
        self.worker.ip_signal.connect(self._on_ip)
        self.worker.peers_updated.connect(self._on_peers_updated)
        self._current_port = "25565"
        self._build_ui()

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
        title = SectionTitle(tr("mp_title"))
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge(tr("mp_not_running"), "warning")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle(tr("mp_subtitle"))
        main_layout.addWidget(sub)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        card_title_font = QFont()
        card_title_font.setPointSize(13)
        card_title_font.setBold(True)

        et_title = QLabel("EasyTier " + tr("mp_title"))
        et_title.setFont(card_title_font)
        card_layout.addWidget(et_title)

        et_desc = QLabel(tr("mp_desc"))
        et_desc.setWordWrap(True)
        et_desc.setStyleSheet("color: palette(mid); font-size: 11px; padding: 4px 0;")
        card_layout.addWidget(et_desc)

        self.et_room_edit = QLineEdit()
        self.et_room_edit.setPlaceholderText(tr("mp_room_placeholder"))
        self.et_room_edit.setMinimumHeight(34)
        self.et_room_edit.setText("MCOpenRoom")
        card_layout.addLayout(self._create_labeled_row(tr("mp_room_name"), self.et_room_edit))

        self.et_password_edit = QLineEdit()
        self.et_password_edit.setPlaceholderText(tr("mp_password_placeholder"))
        self.et_password_edit.setMinimumHeight(34)
        self.et_password_edit.setText("123456")
        card_layout.addLayout(self._create_labeled_row(tr("mp_password"), self.et_password_edit))

        self.et_port_edit = QLineEdit()
        self.et_port_edit.setPlaceholderText(tr("mp_port_placeholder"))
        self.et_port_edit.setMinimumHeight(34)
        self.et_port_edit.setText("25565")
        card_layout.addLayout(self._create_labeled_row(tr("mp_port"), self.et_port_edit))

        relay_row = QHBoxLayout()
        relay_row.setSpacing(10)
        relay_spacer = QLabel("")
        relay_spacer.setFixedWidth(100)
        relay_row.addWidget(relay_spacer)
        self.et_relay_check = QCheckBox(tr("mp_relay"))
        self.et_relay_check.setChecked(True)
        relay_row.addWidget(self.et_relay_check)
        relay_row.addStretch()
        card_layout.addLayout(relay_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.et_host_btn = QPushButton(tr("mp_host"))
        self.et_host_btn.setMinimumHeight(38)
        self.et_host_btn.setMinimumWidth(130)
        self.et_host_btn.clicked.connect(self._start_host)
        btn_row.addWidget(self.et_host_btn)

        self.et_join_btn = QPushButton(tr("mp_join"))
        self.et_join_btn.setObjectName("btnSecondary")
        self.et_join_btn.setMinimumHeight(38)
        self.et_join_btn.setMinimumWidth(130)
        self.et_join_btn.clicked.connect(self._start_join)
        btn_row.addWidget(self.et_join_btn)

        self.et_stop_btn = QPushButton(tr("mp_stop"))
        self.et_stop_btn.setObjectName("btnDanger")
        self.et_stop_btn.setMinimumHeight(38)
        self.et_stop_btn.setMinimumWidth(130)
        self.et_stop_btn.setEnabled(False)
        self.et_stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.et_stop_btn)

        self.et_status_label = QLabel(tr("mp_not_running"))
        self.et_status_label.setStyleSheet(
            "font-size: 12px; padding: 6px 12px; background: #fd7e14; color: #ffffff; border-radius: 4px;"
        )
        btn_row.addWidget(self.et_status_label)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        self.et_ip_label = QLabel(f"{tr('mp_virtual_ip')} {tr('mp_not_obtained')}")
        self.et_ip_label.setStyleSheet("font-size: 13px; color: #2d7d2d; font-weight: bold;")
        card_layout.addWidget(self.et_ip_label)

        self.et_help_label = QLabel(tr("mp_join_help"))
        self.et_help_label.setStyleSheet("font-size: 11px; color: palette(mid);")
        card_layout.addWidget(self.et_help_label)

        ip_btn_row = QHBoxLayout()
        self.et_try_btn = QPushButton(tr("mp_try_ip"))
        self.et_try_btn.setObjectName("btnSecondary")
        self.et_try_btn.setMinimumHeight(30)
        self.et_try_btn.setMinimumWidth(120)
        self.et_try_btn.setVisible(False)
        self.et_try_btn.clicked.connect(self._try_next_ip)
        ip_btn_row.addWidget(self.et_try_btn)

        self.et_copy_btn = QPushButton(tr("mp_copy_addr"))
        self.et_copy_btn.setObjectName("btnSecondary")
        self.et_copy_btn.setMinimumHeight(30)
        self.et_copy_btn.setMinimumWidth(120)
        self.et_copy_btn.setVisible(False)
        self.et_copy_btn.clicked.connect(self._copy_address)
        ip_btn_row.addWidget(self.et_copy_btn)
        ip_btn_row.addStretch()
        card_layout.addLayout(ip_btn_row)

        self.et_peer_label = QLabel(f"{tr('mp_peers')}")
        self.et_peer_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 8px;")
        card_layout.addWidget(self.et_peer_label)

        self.et_peer_list = QLabel(tr("mp_no_peers"))
        self.et_peer_list.setWordWrap(True)
        self.et_peer_list.setStyleSheet("font-size: 11px; color: palette(mid); padding: 8px; background: palette(dark); border-radius: 6px;")
        card_layout.addWidget(self.et_peer_list)

        main_layout.addWidget(card)

        log_card = Card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setSpacing(10)
        log_title = QLabel("Log")
        log_title.setFont(card_title_font)
        log_layout.addWidget(log_title)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(180)
        self.log_text.setMaximumHeight(300)
        log_font = QFont("Consolas", 10)
        self.log_text.setFont(log_font)
        log_layout.addWidget(self.log_text)

        log_btn_row = QHBoxLayout()
        self.clear_log_btn = QPushButton(tr("srv_clear_log"))
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

    def _start_host(self):
        room = self.et_room_edit.text().strip()
        password = self.et_password_edit.text().strip()
        port = self.et_port_edit.text().strip()
        enable_relay = self.et_relay_check.isChecked()
        if not room:
            QMessageBox.warning(self, tr("tip"), tr("mp_room_required"))
            return
        if not password:
            password = "123456"
        if not port:
            port = "25565"
        try:
            int(port)
        except ValueError:
            QMessageBox.warning(self, tr("tip"), tr("mp_port_invalid"))
            return

        self.et_host_btn.setEnabled(False)
        self.et_join_btn.setEnabled(False)
        self.et_status_label.setText(tr("mp_starting"))
        self.et_try_btn.setVisible(False)
        self.et_copy_btn.setVisible(False)
        self._current_port = port
        success = self.worker.start_host(room, password, "MCOpen_Host", self, enable_relay)
        if not success:
            self.et_host_btn.setEnabled(True)
            self.et_join_btn.setEnabled(True)
            self.et_status_label.setText("Failed")

    def _start_join(self):
        room = self.et_room_edit.text().strip()
        password = self.et_password_edit.text().strip()
        enable_relay = self.et_relay_check.isChecked()
        if not room:
            QMessageBox.warning(self, tr("tip"), tr("mp_room_required"))
            return
        if not password:
            password = "123456"

        self.et_host_btn.setEnabled(False)
        self.et_join_btn.setEnabled(False)
        self.et_status_label.setText(tr("mp_connecting"))
        self.et_try_btn.setVisible(False)
        self.et_copy_btn.setVisible(False)

        success = self.worker.start_join(room, password, "MCOpen_Join", self, enable_relay)
        if not success:
            self.et_host_btn.setEnabled(True)
            self.et_join_btn.setEnabled(True)
            self.et_status_label.setText("Failed")
        else:
            QMessageBox.information(self, tr("mp_join_tutorial_title"), tr("mp_join_tutorial"))

    def _stop(self):
        self.worker.stop_node()

    def _on_status(self, running, msg):
        if running:
            self.et_status_label.setText(msg)
            self.et_host_btn.setEnabled(False)
            self.et_join_btn.setEnabled(False)
            self.et_stop_btn.setEnabled(True)
            if tr("mp_connected") in msg or "10." in msg:
                self.et_try_btn.setVisible(True)
                self.et_copy_btn.setVisible(True)
                self.et_status_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 12px; background: #28a745; color: #ffffff; border-radius: 4px;"
                )
                self.status_badge.set_status("normal", tr("mp_connected"))
            else:
                self.et_try_btn.setVisible(False)
                self.et_copy_btn.setVisible(False)
                self.et_status_label.setStyleSheet(
                    "font-size: 12px; padding: 6px 12px; background: #ffc107; color: #000000; border-radius: 4px;"
                )
                self.status_badge.set_status("info", tr("mp_connecting"))
        else:
            self.et_host_btn.setEnabled(True)
            self.et_join_btn.setEnabled(True)
            self.et_stop_btn.setEnabled(False)
            self.et_try_btn.setVisible(False)
            self.et_copy_btn.setVisible(False)
            self.et_status_label.setText(msg)
            self.et_status_label.setStyleSheet(
                "font-size: 12px; padding: 6px 12px; background: #dc3545; color: #ffffff; border-radius: 4px;"
            )
            self.status_badge.set_status("warning", tr("mp_disconnected"))

    def _on_ip(self, ip):
        port = self.et_port_edit.text().strip() or "25565"
        self.et_ip_label.setText(f"{tr('mp_virtual_ip')} {ip}")
        self._append_log(f"[MP] Virtual IP: {ip}")
        self._append_log(f"[MP] Friends join with {ip}:{port}")

    def _on_peers_updated(self, peers):
        if not peers:
            self.et_peer_list.setText(tr("mp_no_peers"))
            return
        port = self.et_port_edit.text().strip() or "25565"
        lines = []
        for peer in peers:
            ip = peer.get("ip", "")
            hostname = peer.get("hostname", "Unknown")
            if ip:
                lines.append(f"{hostname}  -  {ip}:{port}")
            else:
                lines.append(f"{hostname}  -  ...")
        self.et_peer_list.setText("\n".join(lines))

    def _try_next_ip(self):
        ip = self.worker.get_next_ip()
        if ip:
            port = self.et_port_edit.text().strip() or "25565"
            self.et_ip_label.setText(f"{tr('mp_virtual_ip')} {ip} (alt)")
        else:
            self.worker.reset_ip_index()
            ip = self.worker.get_next_ip()
            if ip:
                port = self.et_port_edit.text().strip() or "25565"
                self.et_ip_label.setText(f"{tr('mp_virtual_ip')} {ip} (alt)")

    def _copy_address(self):
        text = self.et_ip_label.text().replace(f"{tr('mp_virtual_ip')} ", "").replace(" (alt)", "").strip()
        port = self.et_port_edit.text().strip() or "25565"
        if text and text != tr("mp_not_obtained"):
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(f"{text}:{port}")
            self.et_status_label.setText(tr("mp_addr_copied"))

    def _append_log(self, text):
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
