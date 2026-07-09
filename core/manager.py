import os
import sys
import subprocess
import time
import threading
import re
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QMessageBox

class EasyTierManager(QObject):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool, str)
    ip_signal = pyqtSignal(str)
    peers_updated = pyqtSignal(list)

    def __init__(self, launcher_root):
        super().__init__()
        self.launcher_root = Path(launcher_root)
        self.tools_dir = self.launcher_root / "tools" / "easytier"
        self.tools_dir.mkdir(parents=True, exist_ok=True)

        if sys.platform == "win32":
            self.core_path = self.tools_dir / "easytier-core.exe"
            self.cli_path = self.tools_dir / "easytier-cli.exe"
        else:
            self.core_path = self.tools_dir / "easytier-core"
            self.cli_path = self.tools_dir / "easytier-cli"

        self.process = None
        self.running = False
        self.virtual_ip = ""
        self.network_name = ""
        self.network_secret = ""
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
            self.log_signal.emit(f"[EasyTier] 未找到 easytier-core，请放入 {self.tools_dir}")
            return False
        if not self.cli_path.exists():
            self.log_signal.emit(f"[EasyTier] 未找到 easytier-cli，请放入 {self.tools_dir}")
            return False
        return True

    def check_firewall(self, parent_widget=None):
        if sys.platform != "win32":
            return True
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5
            )
            if "off" in result.stdout.lower():
                return True
        except Exception:
            pass
        if parent_widget:
            msg = QMessageBox(parent_widget)
            msg.setWindowTitle("防火墙提示")
            msg.setIcon(QMessageBox.Warning)
            msg.setText(
                "EasyTier 联机需要网络通信权限，请确保：\n\n"
                "1. 临时关闭 Windows 防火墙（测试用）\n"
                "   或\n"
                "2. 将 EasyTier 加入防火墙白名单：\n"
                f"   {self.core_path}\n\n"
                "如果联机失败，请优先检查防火墙设置。"
            )
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            msg.button(QMessageBox.Ok).setText("已准备好，继续")
            msg.button(QMessageBox.Cancel).setText("先去设置防火墙")
            return msg.exec_() == QMessageBox.Ok
        return True

    def set_ports(self, listen_port=21010, rpc_port=21011):
        self._listen_port = listen_port
        self._rpc_port = rpc_port

    def start_host(self, network_name, network_secret, hostname=None, parent_widget=None, enable_relay=True, peer_addr=None):
        if not self.check_firewall(parent_widget):
            return False
        self._role = "host"
        self._ip_index = 0
        self._ip_candidates = []
        return self.start_node(network_name, network_secret, hostname, enable_relay, peer_addr)

    def start_join(self, network_name, network_secret, hostname=None, parent_widget=None, enable_relay=True, peer_addr=None):
        if not self.check_firewall(parent_widget):
            return False
        self._role = "join"
        self._ip_index = 0
        self._ip_candidates = []
        return self.start_node(network_name, network_secret, hostname, enable_relay, peer_addr)

    def start_node(self, network_name, network_secret, hostname=None, enable_relay=True, peer_addr=None):
        if not self.check_binaries():
            self.status_signal.emit(False, "EasyTier 内核缺失")
            return False

        if self.running:
            self.log_signal.emit("[EasyTier] 节点已在运行")
            return True

        self._stop_flag = False
        self.network_name = network_name
        self.network_secret = network_secret

        cmd = [
            str(self.core_path),
            "--network-name", network_name,
            "--network-secret", network_secret,
            "--listeners", f"tcp://0.0.0.0:{self._listen_port},udp://0.0.0.0:{self._listen_port}",
            "--rpc-portal", f"127.0.0.1:{self._rpc_port}",
        ]

        if peer_addr and peer_addr.strip():
            cmd.extend(["--peers", peer_addr.strip()])

        if not enable_relay:
            cmd.append("--p2p-only")

        if hostname:
            cmd.extend(["--hostname", hostname])

        self.log_signal.emit(f"[EasyTier] 启动节点: {network_name} ({self._role})，公共节点: {peer_addr if peer_addr else '默认'}，中继转发: {'启用' if enable_relay else '禁用'}")

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
                text=False,
                bufsize=1
            )
            self.running = True
            self.status_signal.emit(True, "节点启动中...")
            threading.Thread(target=self._read_output, daemon=False).start()
            threading.Thread(target=self._wait_for_ip, daemon=False).start()
            self.log_signal.emit("[EasyTier] 节点已启动")
            if self._role == "host":
                self._start_peer_polling()
            return True
        except Exception as e:
            self.log_signal.emit(f"[EasyTier] 启动失败: {e}")
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
        peers = self.get_peers()
        new_set = frozenset([(p.get('ip',''), p.get('hostname','')) for p in peers])
        old_set = frozenset([(p.get('ip',''), p.get('hostname','')) for p in self._peers])
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
                except:
                    text = str(line)
                if text:
                    self.log_signal.emit(f"[EasyTier] {text}")
                if self.process.poll() is not None:
                    break
        except Exception:
            pass
        self.running = False
        self.status_signal.emit(False, "节点已断开")
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

    def _wait_for_ip(self):
        max_attempts = 15
        for attempt in range(max_attempts):
            if self._stop_flag or not self.running:
                self.status_signal.emit(False, "已取消")
                return
            ips = self.get_virtual_ips()
            if ips:
                self.virtual_ip = ips[0]
                self._ip_candidates = ips
                self.ip_signal.emit(ips[0])
                self.status_signal.emit(True, f"已连接，虚拟IP: {ips[0]}")
                if len(ips) > 1:
                    self.log_signal.emit(f"[EasyTier] 备选IP: {', '.join(ips[1:])}")
                return
            time.sleep(1)

        if self._role == "host":
            self.status_signal.emit(True, "等待其他成员加入...")
            self.log_signal.emit("[EasyTier] 当前仅房主在线，等待其他成员加入后自动分配IP")
        else:
            self.status_signal.emit(False, "无法加入网络，请检查房间名和密码是否正确")
            self.log_signal.emit("[EasyTier] 加入者未能获取到IP，可能房间名/密码错误或房主未开房")

    def get_virtual_ips(self):
        if not self.cli_path.exists():
            return []
        try:
            result = subprocess.run(
                [str(self.cli_path), "--rpc-portal", f"127.0.0.1:{self._rpc_port}", "peer"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5
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

    def get_peers(self):
        if not self.cli_path.exists():
            return []
        try:
            result = subprocess.run(
                [str(self.cli_path), "--rpc-portal", f"127.0.0.1:{self._rpc_port}", "peer"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5
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
                    hostname = parts[1] if len(parts) > 1 else "未知"
                    if ip and ip.startswith("10."):
                        peers.append({"ip": ip, "hostname": hostname})
            return peers
        except Exception:
            return []

    def get_next_ip(self):
        if not self._ip_candidates:
            self._ip_candidates = self.get_virtual_ips()
            self._ip_index = 0
        if self._ip_index < len(self._ip_candidates):
            ip = self._ip_candidates[self._ip_index]
            self._ip_index += 1
            return ip
        return None

    def reset_ip_index(self):
        self._ip_index = 0
        self._ip_candidates = self.get_virtual_ips()

    def get_all_connection_addresses(self, port=25565):
        ips = self.get_virtual_ips()
        result = []
        for ip in ips:
            result.append(f"{ip}:{port}")
        return result

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
        self.virtual_ip = ""
        self._ip_index = 0
        self._ip_candidates = []
        self._peers = []
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None
        self.log_signal.emit("[EasyTier] 节点已停止")
        self.status_signal.emit(False, "已停止")
        return True

    def is_running(self):
        return self.running and self.process and self.process.poll() is None

    def get_public_ip(self):
        return self.virtual_ip if self.virtual_ip else None