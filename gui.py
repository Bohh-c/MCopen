"""MCOpen 启动器 GUI 入口"""

import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow
from core.base import init_launcher_watermark


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MCOpen")

    init_launcher_watermark(PROJECT_ROOT)

    window = MainWindow()
    window.apply_theme(app)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()