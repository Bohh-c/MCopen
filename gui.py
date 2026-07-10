import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer

from gui.main_window import MainWindow
from core.base import init_launcher_watermark

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MCOpen")

    splash_pixmap = QPixmap(os.path.join(PROJECT_ROOT, "1.png"))
    if not splash_pixmap.isNull():
        splash = QSplashScreen(splash_pixmap, Qt.WindowStaysOnTopHint)
    else:
        splash = QSplashScreen()
        splash.setStyleSheet("background-color: #2b2b2b; color: white; font-size: 20px;")
        splash.showMessage("MCOpen 启动中...", Qt.AlignCenter, Qt.white)

    splash.show()
    app.processEvents()

    def delayed_init():
        init_launcher_watermark(PROJECT_ROOT)
        window = MainWindow()
        window.apply_theme(app)
        window.show()
        app.processEvents()
        splash.finish(window)

    QTimer.singleShot(0, delayed_init)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()