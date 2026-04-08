import os
import sys
from pathlib import Path

import PySide6.QtAsyncio as QtAsyncio
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from finch.config import CONFIG_PATH, app_settings
from finch.utils.ui import apply_theme, resource_path
from finch.browser.window import MainWindow


def main():
    os.makedirs(CONFIG_PATH, exist_ok=True)
    Path(os.path.join(CONFIG_PATH, 'credentials.json')).touch()
    app_settings.load()
    app_settings.apply_logging()
    app = QApplication(sys.argv)
    app.setApplicationName('Finch S3 Client')
    app.setWindowIcon(QIcon(resource_path("img/icon.png")))
    apply_theme(app)

    window = MainWindow()
    window.show()
    QtAsyncio.run(handle_sigint=True)


if __name__ == '__main__':
    main()
