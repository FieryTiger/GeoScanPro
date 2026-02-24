from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class StatCard(QFrame):
    def __init__(self, title: str, unit: str = ''):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Не задаём background — берём из системной палитры (работает и в тёмной теме)
        self.setStyleSheet('QFrame { border: 1px solid palette(mid); border-radius: 6px; }')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        self._value_lbl = QLabel('—')
        self._value_lbl.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_text = f'{title}' + (f', {unit}' if unit else '')
        self._title_lbl = QLabel(title_text)
        self._title_lbl.setFont(QFont('Arial', 11))
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._value_lbl)
        layout.addWidget(self._title_lbl)

    def set_value(self, value: str):
        self._value_lbl.setText(value)


class StatsPanel(QWidget):
    object_selected = Signal(int)  # index объекта в objects_data

    def __init__(self):
        super().__init__()
        self._objects_data = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Карточки
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        self.card_area    = StatCard('Площадь воды',   'км²')
        self.card_pct     = StatCard('% воды',         '')
        self.card_count   = StatCard('Объектов',       '')
        self.card_largest = StatCard('Крупнейший',     'км²')
        for card in (self.card_area, self.card_pct, self.card_count, self.card_largest):
            cards_row.addWidget(card)
        layout.addLayout(cards_row)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            'ID', 'Площадь, км²', 'Площадь, пикс.', 'Периметр, км', 'Коэф. формы'
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMaximumHeight(180)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.table)

    def update_statistics(self, results: dict):
        self.card_area.set_value(f"{results.get('total_water_area_km2', 0):.2f}")
        self.card_pct.set_value(f"{results.get('water_percentage', 0):.1f}%")
        self.card_count.set_value(str(results.get('object_count', 0)))
        self.card_largest.set_value(f"{results.get('largest_object_area', 0):.2f}")

        self._objects_data = results.get('objects_data', [])
        self.table.setRowCount(len(self._objects_data))
        for i, obj in enumerate(self._objects_data):
            vals = [
                str(i + 1),
                f"{obj['area_km2']:.4f}",
                f"{obj['area_pixels']:,}",
                f"{obj['perimeter_km']:.4f}",
                f"{obj['shape_factor']:.4f}",
            ]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, col, item)

    def _on_row_selected(self):
        selected = self.table.selectedItems()
        if selected:
            row = self.table.currentRow()
            self.object_selected.emit(row)
