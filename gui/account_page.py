"""账号管理页面 - 离线登录 + 默认账号切换"""

import json
import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox,
)
from PyQt5.QtGui import QFont

from core.launcher import AccountManager
from gui.widgets import Card, SectionTitle, SubTitle, StatusBadge
from gui.i18n import tr


ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "accounts.json")


def get_default_account():
    """获取默认账号，如果没有则返回 None"""
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        accounts = data.get("accounts", [])
        default_idx = data.get("default_idx", 0)
        if accounts and 0 <= default_idx < len(accounts):
            return accounts[default_idx]
        if accounts:
            return accounts[0]
    return None


class AccountPage(QWidget):
    accounts_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.account_manager = AccountManager()
        self.accounts = []
        self.default_idx = 0
        self._load_accounts()
        self._build_ui()
        self._refresh_account_list()

    def _get_accounts_path(self):
        return ACCOUNTS_FILE

    def _load_accounts(self):
        path = self._get_accounts_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.accounts = data.get("accounts", [])
                self.default_idx = data.get("default_idx", 0)
        else:
            self.accounts = []
            self.default_idx = 0

    def _save_accounts(self):
        path = self._get_accounts_path()
        data = {
            "accounts": self.accounts,
            "default_idx": self.default_idx,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_current_account(self):
        if self.accounts and 0 <= self.default_idx < len(self.accounts):
            return self.accounts[self.default_idx]
        return None

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title = SectionTitle(tr("acc_title"))
        header.addWidget(title)
        header.addStretch()
        self.status_badge = StatusBadge("", "normal")
        header.addWidget(self.status_badge)
        main_layout.addLayout(header)

        sub = SubTitle(tr("acc_subtitle"))
        main_layout.addWidget(sub)

        card1 = Card()
        card1_layout = QVBoxLayout(card1)
        card1_layout.setSpacing(12)

        card1_title = QLabel(tr("acc_saved"))
        card1_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        card1_layout.addWidget(card1_title)

        self.account_list = QListWidget()
        self.account_list.setMinimumHeight(150)
        self.account_list.setAlternatingRowColors(True)
        self.account_list.itemClicked.connect(self._on_account_selected)
        card1_layout.addWidget(self.account_list)

        acc_btn_row = QHBoxLayout()
        self.set_default_btn = QPushButton(tr("acc_set_default"))
        self.set_default_btn.setObjectName("btnSecondary")
        self.set_default_btn.setEnabled(False)
        self.set_default_btn.clicked.connect(self._set_default_account)
        acc_btn_row.addWidget(self.set_default_btn)

        self.delete_btn = QPushButton(tr("acc_delete_btn"))
        self.delete_btn.setObjectName("btnDanger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_account)
        acc_btn_row.addWidget(self.delete_btn)
        acc_btn_row.addStretch()
        card1_layout.addLayout(acc_btn_row)

        main_layout.addWidget(card1)

        card2 = Card()
        card2_layout = QVBoxLayout(card2)
        card2_layout.setSpacing(12)

        card2_title = QLabel(tr("acc_add"))
        card2_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        card2_layout.addWidget(card2_title)

        form_row = QHBoxLayout()
        self.offline_name_edit = QLineEdit()
        self.offline_name_edit.setPlaceholderText(tr("acc_name_placeholder"))
        form_row.addWidget(self.offline_name_edit)
        self.add_offline_btn = QPushButton(tr("acc_add_btn"))
        self.add_offline_btn.setMinimumHeight(36)
        self.add_offline_btn.clicked.connect(self._add_offline_account)
        form_row.addWidget(self.add_offline_btn)
        card2_layout.addLayout(form_row)

        main_layout.addWidget(card2)
        main_layout.addStretch()

    def _add_offline_account(self):
        name = self.offline_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, tr("tip"), tr("acc_name_required"))
            return
        for acc in self.accounts:
            if acc.get("name") == name and acc.get("authType") == "offline":
                QMessageBox.warning(self, tr("tip"), tr("acc_exists"))
                return
        account = self.account_manager.create_offline(name)
        self.accounts.append(account)
        if len(self.accounts) == 1:
            self.default_idx = 0
        self._save_accounts()
        self._refresh_account_list()
        self.offline_name_edit.clear()
        self.status_badge.set_status("normal", f"{tr('acc_added')} {name}")
        self.accounts_changed.emit()

    def _delete_account(self):
        current = self.account_list.currentItem()
        if not current:
            return
        idx = self.account_list.currentRow()
        acc = self.accounts[idx]
        reply = QMessageBox.question(
            self, tr("acc_delete_btn"),
            f"{tr('acc_confirm_delete')} {acc.get('name', '')}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.accounts[idx]
            if self.default_idx >= len(self.accounts):
                self.default_idx = max(0, len(self.accounts) - 1)
            elif idx < self.default_idx:
                self.default_idx -= 1
            self._save_accounts()
            self._refresh_account_list()
            self.status_badge.set_status("normal", tr("acc_deleted"))
            self.accounts_changed.emit()

    def _set_default_account(self):
        current = self.account_list.currentItem()
        if not current:
            return
        idx = self.account_list.currentRow()
        self.default_idx = idx
        self._save_accounts()
        self._refresh_account_list()
        acc = self.accounts[idx]
        self.status_badge.set_status("normal", f"{tr('acc_default_set')}: {acc['name']}")
        self.accounts_changed.emit()

    def _refresh_account_list(self):
        self.account_list.clear()
        for i, acc in enumerate(self.accounts):
            display = tr("acc_offline")
            marker = " ★" if i == self.default_idx else ""
            item = QListWidgetItem()
            item.setText(f"{acc['name']}  [{display}]{marker}")
            item.setData(Qt.UserRole, acc)
            item.setSizeHint(item.sizeHint().grownBy(0, 6))
            self.account_list.addItem(item)
        if self.accounts:
            self.status_badge.set_status("normal", f"{len(self.accounts)} {tr('acc_offline')}")
        else:
            self.status_badge.set_status("warning", tr("acc_no_accounts"))

    def _on_account_selected(self, item):
        self.delete_btn.setEnabled(True)
        self.set_default_btn.setEnabled(True)