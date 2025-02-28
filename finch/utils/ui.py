import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QDesktopWidget


def center_window(self):
    """ Center windows to screen """
    geometry = self.frameGeometry()
    center_point = QDesktopWidget().availableGeometry().center()
    geometry.moveCenter(center_point)
    self.move(geometry.topLeft())

def apply_theme(app):
    """ Apply Dark Theme """
    # Use light theme by default in Windows due color incompatibilities.
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
        palette.setColor(QPalette.HighlightedText, QColor(35, 35, 35))
        palette.setColor(QPalette.Active, QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.WindowText, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.Text, Qt.darkGray)
        palette.setColor(QPalette.Disabled, QPalette.Light, QColor(53, 53, 53))
        app.setPalette(palette)