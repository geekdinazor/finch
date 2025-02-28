from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget


class QProgressIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.setInterval(50)
        
        self.displayedWhenStopped = False
        self.color = QColor(Qt.white)
        
        # Smaller size
        self.setFixedSize(16, 16)  # Changed from 32 to 24
        self.hide()

    def setColor(self, color: QColor):
        """Set the color of the spinner"""
        self.color = color
        self.update()

    def rotate(self):
        self.angle = (self.angle + 10) % 360  # Changed minus to plus for clockwise
        self.update()

    def start(self):
        self.angle = 0
        self.timer.start()
        self.show()

    def stop(self):
        self.timer.stop()
        # self.hide()

    def paintEvent(self, event):
        if not self.timer.isActive() and not self.displayedWhenStopped:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width(), self.height())
        pen_width = int(size / 8)
        
        # Setup pen for the rings
        pen = QPen(self.color)
        pen.setWidth(pen_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        
        # Calculate ring size
        ring_radius = int((size - pen_width) / 2)
        
        # Draw the rings
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        
        # Draw first arc (0 to 120 degrees)
        painter.drawArc(
            int(-ring_radius),
            int(-ring_radius),
            int(ring_radius * 2),
            int(ring_radius * 2),
            0 * 16,
            120 * 16
        )
        
        # Draw second arc (180 to 300 degrees)
        painter.drawArc(
            int(-ring_radius),
            int(-ring_radius),
            int(ring_radius * 2),
            int(ring_radius * 2),
            180 * 16,
            120 * 16
        ) 