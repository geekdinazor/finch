import os
import pathlib
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


def apply_theme(app):
    if sys.platform != "win32":
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, QColor(25, 25, 25))
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        palette.setColor(QPalette.Active, QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
        app.setPalette(palette)

    qss_path = resource_path("img/theme.qss")
    try:
        with open(qss_path) as f:
            qss = f.read()
        qss = qss.replace("{arrow_right}", resource_path("img/arrow-right.svg").replace("\\", "/"))
        qss = qss.replace("{arrow_down}", resource_path("img/arrow-down.svg").replace("\\", "/"))
        qss = qss.replace("{arrow_right_selected}", resource_path("img/arrow-right-selected.svg").replace("\\", "/"))
        qss = qss.replace("{arrow_down_selected}", resource_path("img/arrow-down-selected.svg").replace("\\", "/"))
        app.setStyleSheet(qss)
    except OSError:
        pass


def center_window(window):
    geometry = window.frameGeometry()
    center_point = QApplication.primaryScreen().availableGeometry().center()
    geometry.moveCenter(center_point)
    window.move(geometry.topLeft())


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        # Move up two levels: finch/utils/ -> finch/
        base_path = pathlib.Path(__file__).parent.parent.resolve()
    return os.path.join(base_path, relative_path)