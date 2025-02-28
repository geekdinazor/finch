import os
import sys
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from finch.views.main_window import MainWindow
from finch.utils.config import create_config_files_if_not_exist
from finch.utils.ui import apply_theme



def main():
    create_config_files_if_not_exist()
    app = QApplication(sys.argv)
    app.setApplicationName('Finch S3 Client')
    app.setWindowIcon(QIcon(":/icons/icon.png"))
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()