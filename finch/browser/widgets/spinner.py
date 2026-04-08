from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget


class QProgressIndicator(QWidget):
    """macOS-style animated spinner (rotating segments)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._color = QColor(100, 100, 100)
        self.setFixedSize(20, 20)
        self.hide()

    def start(self):
        self._timer.start(80)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)

        segments = 12
        for i in range(segments):
            angle = self._angle + i * (360 / segments)
            opacity = (i + 1) / segments
            color = QColor(self._color)
            color.setAlphaF(opacity)
            painter.save()
            painter.rotate(angle)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            r = min(self.width(), self.height()) / 2
            painter.drawRoundedRect(
                QRect(int(r * 0.4), -int(r * 0.08),
                      int(r * 0.5), int(r * 0.16)),
                2, 2,
            )
            painter.restore()
