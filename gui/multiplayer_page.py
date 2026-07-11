import subprocess
import sys
import re
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QScrollArea, QFrame,
)
from PyQt5.QtGui import QFont

from gui.widgets import SectionTitle, SubTitle, StatusBadge


class MultiplayerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.zt_network_id = ""
        self.zt_virtual_ip = ""
        self.zt_joined = False
        self.zt_poll_timer = None
        self._build_ui()
        self._check_zerotier_installed()

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
        title = SectionTitle("辅助联机")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("未连接", "warning")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle("用 ZeroTier 和朋友组虚拟局域网，一起玩")
        main_layout.addWidget(sub)

        block = QFrame()
        block.setObjectName("card")
        block.setFrameShape(QFrame.StyledPanel)
        block_layout = QVBoxLayout(block)
        block_layout.setSpacing(14)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(QLabel("Network ID:"))
        self.zt_network_input = QLineEdit()
        self.zt_network_input.setPlaceholderText("输入 Network ID，比如 884c8f5e...")
        self.zt_network_input.setMinimumHeight(34)
        row1.addWidget(self.zt_network_input, 1)

        self.zt_join_btn = QPushButton("加入网络")
        self.zt_join_btn.setMinimumHeight(36)
        self.zt_join_btn.setMinimumWidth(120)
        self.zt_join_btn.setStyleSheet("""
            QPushButton {
                background-color: #8a5c9e;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7a4c8e; }
            QPushButton:pressed { background-color: #6a3c7e; }
            QPushButton:disabled {
                background-color: #5a5a6a;
                color: #c0c0c0;
            }
        """)
        self.zt_join_btn.clicked.connect(self._zt_join)
        row1.addWidget(self.zt_join_btn)

        self.zt_leave_btn = QPushButton("离开网络")
        self.zt_leave_btn.setMinimumHeight(36)
        self.zt_leave_btn.setMinimumWidth(120)
        self.zt_leave_btn.setStyleSheet("""
            QPushButton {
                background-color: #b54a4a;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 6px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #a53a3a; }
            QPushButton:pressed { background-color: #952a2a; }
            QPushButton:disabled {
                background-color: #5a5a6a;
                color: #c0c0c0;
            }
        """)
        self.zt_leave_btn.setEnabled(False)
        self.zt_leave_btn.clicked.connect(self._zt_leave)
        row1.addWidget(self.zt_leave_btn)

        block_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(QLabel("状态:"))
        self.zt_status_label = QLabel("未连接")
        self.zt_status_label.setStyleSheet("font-weight: bold;")
        row2.addWidget(self.zt_status_label)

        row2.addSpacing(20)
        row2.addWidget(QLabel("虚拟IP:"))
        self.zt_ip_label = QLabel("未获取")
        self.zt_ip_label.setStyleSheet("font-weight: bold; color: #2d7d2d;")
        row2.addWidget(self.zt_ip_label)

        row2.addStretch()

        self.zt_copy_btn = QPushButton("复制地址")
        self.zt_copy_btn.setMinimumHeight(30)
        self.zt_copy_btn.setMinimumWidth(100)
        self.zt_copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a8c5c;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3a7c4c; }
            QPushButton:pressed { background-color: #2a6c3c; }
            QPushButton:disabled {
                background-color: #5a5a6a;
                color: #c0c0c0;
            }
        """)
        self.zt_copy_btn.setVisible(False)
        self.zt_copy_btn.clicked.connect(self._copy_address)
        row2.addWidget(self.zt_copy_btn)

        block_layout.addLayout(row2)

        self.zt_install_label = QLabel("")
        self.zt_install_label.setOpenExternalLinks(True)
        self.zt_install_label.setWordWrap(True)
        self.zt_install_label.setStyleSheet("font-size: 11px; padding: 4px 0;")
        block_layout.addWidget(self.zt_install_label)

        main_layout.addWidget(block)

        log_title = QLabel("日志")
        log_title.setFont(QFont("", 11, QFont.Bold))
        main_layout.addWidget(log_title)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        self.log_text.setMaximumHeight(180)
        log_font = QFont("Consolas", 10)
        self.log_text.setFont(log_font)
        main_layout.addWidget(self.log_text)

        clear_btn = QPushButton("清空日志")
        clear_btn.setMinimumHeight(30)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c6c6c;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 4px 16px;
            }
            QPushButton:hover { background-color: #5c5c5c; }
            QPushButton:pressed { background-color: #4c4c4c; }
        """)
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        main_layout.addWidget(clear_btn)

        main_layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll_area)

    def _check_zerotier_installed(self):
        try:
            result = subprocess.run(
                ["zerotier-cli", "--version"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                ver = result.stdout.strip()
                self._append_log(f"ZeroTier 已安装: {ver}")
                self.zt_install_label.setText("✓ ZeroTier 客户端已安装")
                self.zt_install_label.setStyleSheet("color: #4a8c5c; font-size: 11px;")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        self.zt_install_label.setText(
            "✗ 未检测到 ZeroTier 客户端，请前往 <a href='https://www.zerotier.com/download/'>下载页面</a> 下载安装"
        )
        self.zt_install_label.setStyleSheet("color: #a0525a; font-size: 11px;")
        self._append_log("ZeroTier 客户端未安装")
        return False

    def _zt_join(self):
        network_id = self.zt_network_input.text().strip()
        if not network_id:
            QMessageBox.warning(self, "提示", "请输入 Network ID")
            return
        if not self._check_zerotier_installed():
            QMessageBox.warning(self, "提示", "请先安装 ZeroTier 客户端")
            return

        self.zt_join_btn.setEnabled(False)
        self.zt_status_label.setText("正在加入...")
        self.zt_ip_label.setText("获取中...")
        self.zt_copy_btn.setVisible(False)

        self._append_log(f"加入 ZeroTier 网络: {network_id}")
        try:
            result = subprocess.run(
                ["zerotier-cli", "join", network_id],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout + result.stderr
            if "200" in output or "already" in output.lower():
                self.zt_joined = True
                self.zt_network_id = network_id
                self.zt_status_label.setText("已加入，等待授权...")
                self.zt_leave_btn.setEnabled(True)
                self._append_log("成功加入网络，请前往 ZeroTier Central 授权此设备")
                self._start_ip_polling()
            else:
                self.zt_join_btn.setEnabled(True)
                self.zt_status_label.setText("加入失败")
                self._append_log(f"加入失败: {output}")
                QMessageBox.warning(self, "加入失败", f"无法加入网络:\n{output}")
        except Exception as e:
            self.zt_join_btn.setEnabled(True)
            self.zt_status_label.setText("错误")
            self._append_log(f"错误: {e}")
            QMessageBox.warning(self, "错误", str(e))

    def _zt_leave(self):
        if not self.zt_joined:
            return
        self.zt_leave_btn.setEnabled(False)
        self._append_log(f"离开网络: {self.zt_network_id}")
        try:
            subprocess.run(
                ["zerotier-cli", "leave", self.zt_network_id],
                capture_output=True, timeout=5
            )
        except:
            pass
        self._stop_ip_polling()
        self.zt_joined = False
        self.zt_virtual_ip = ""
        self.zt_network_id = ""
        self.zt_ip_label.setText("未获取")
        self.zt_status_label.setText("已离开")
        self.zt_join_btn.setEnabled(True)
        self.zt_leave_btn.setEnabled(False)
        self.zt_copy_btn.setVisible(False)
        self.status_badge.set_status("warning", "未连接")
        self._append_log("已离开网络")

    def _start_ip_polling(self):
        if self.zt_poll_timer:
            self.zt_poll_timer.stop()
        self.zt_poll_timer = QTimer()
        self.zt_poll_timer.setInterval(2000)
        self.zt_poll_timer.timeout.connect(self._poll_ip)
        self.zt_poll_timer.start()
        self._poll_ip()

    def _stop_ip_polling(self):
        if self.zt_poll_timer:
            self.zt_poll_timer.stop()
            self.zt_poll_timer = None

    def _poll_ip(self):
        ip = self._get_zerotier_ip()
        if ip:
            self.zt_virtual_ip = ip
            self.zt_ip_label.setText(ip)
            self.zt_status_label.setText("已连接")
            self.zt_copy_btn.setVisible(True)
            self.zt_join_btn.setEnabled(False)
            self.zt_leave_btn.setEnabled(True)
            self.status_badge.set_status("normal", "已连接")
            self._append_log(f"获取到虚拟IP: {ip}")
            self._stop_ip_polling()

    def _get_zerotier_ip(self):
        try:
            result = subprocess.run(
                ["zerotier-cli", "listnetworks"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
            )
            if result.returncode != 0:
                return None
            for line in result.stdout.splitlines():
                if self.zt_network_id and self.zt_network_id not in line:
                    continue
                if "OK" not in line:
                    continue
                parts = line.split()
                if len(parts) < 8:
                    continue
                last = parts[-1]
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', last)
                if match:
                    ip = match.group(1)
                    if ip.startswith("192.168.") or ip.startswith("10."):
                        return ip
        except Exception:
            pass
        return None

    def _copy_address(self):
        ip = self.zt_virtual_ip
        if ip:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(ip)
            self.zt_status_label.setText("地址已复制")
            self._append_log(f"已复制地址: {ip}")

    def _append_log(self, text):
        self.log_text.append(text)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())