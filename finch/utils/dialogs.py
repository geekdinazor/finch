from enum import Enum

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox,
    QHBoxLayout, QComboBox, QWidget, QDoubleSpinBox,
)

from finch.utils.error import show_error_dialog


class TimeIntervalDialog(QDialog):
    """Modal dialog for entering a time duration with unit selection."""

    class Unit(Enum):
        SECONDS = 1
        MINUTES = 60
        HOURS   = 60 * 60
        DAYS    = 24 * 60 * 60

    def __init__(self, parent=None, title: str = "Enter Time Interval",
                 max_seconds: int = None,
                 default_unit: "TimeIntervalDialog.Unit" = Unit.SECONDS,
                 default_value: int = None, allow_zero: bool = False):
        super().__init__(parent)
        self.value = None
        self.unit = default_unit
        self.value_as_seconds = None
        self.max_seconds = max_seconds
        self.allow_zero = allow_zero
        self.setWindowTitle(title)

        self._spin = QDoubleSpinBox()
        self._spin.setMaximum(2147483647)
        self._spin.setDecimals(3)
        if default_value is not None:
            self._spin.setValue(default_value)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems([u.name.lower() for u in self.Unit])
        self._unit_combo.setCurrentText(default_unit.name.lower())
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.addWidget(self._spin)
        row_layout.addWidget(self._unit_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(row)
        layout.addWidget(buttons)

    def _on_accept(self):
        value = self._spin.value()
        seconds = value * self.unit.value
        if not self.allow_zero and seconds == 0:
            show_error_dialog("Time interval cannot be zero seconds")
            return
        if self.max_seconds is not None and seconds > self.max_seconds:
            show_error_dialog(f"Maximum allowed time interval is {self.max_seconds} seconds")
            return
        self.value = value
        self.value_as_seconds = seconds
        self.accept()

    def _on_unit_changed(self, index: int):
        current_seconds = self._spin.value() * self.unit.value
        self.unit = self.Unit[self._unit_combo.currentText().upper()]
        self._spin.setValue(current_seconds / self.unit.value)