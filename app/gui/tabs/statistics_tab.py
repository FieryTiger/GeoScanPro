from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class StatisticsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setFont(QFont("Courier", 11))
        self.stats_text.setMaximumHeight(200)
        self.stats_text.setPlaceholderText("Общая статистика появится после анализа...")
        splitter.addWidget(self.stats_text)

        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 8, 0, 0)

        table_label = QLabel("Детализация по водным объектам")
        table_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        table_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Площадь (кв.км)", "Площадь (пикс.)", "Периметр (км)", "Коэф. формы"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        table_layout.addWidget(self.table)

        splitter.addWidget(table_widget)
        layout.addWidget(splitter)

    def update_statistics(self, results):
        text = (
            f"Общая площадь воды:          {results.get('total_water_area_km2', 0):.4f} кв.км\n"
            f"Общая площадь воды:          {results.get('total_water_area_pixels', 0):,} пикселей\n"
            f"Общий периметр:              {results.get('total_perimeter_km', 0):.4f} км\n"
            f"Процент водной поверхности:  {results.get('water_percentage', 0):.2f}%\n"
            f"\n"
            f"Количество объектов:         {results.get('object_count', 0)}\n"
            f"Крупнейший объект:           {results.get('largest_object_area', 0):.4f} кв.км\n"
            f"Средний размер объекта:      {results.get('average_object_size', 0):.4f} кв.км\n"
        )
        self.stats_text.setPlainText(text)

        objects = results.get('objects_data', [])
        self.table.setRowCount(len(objects))
        for row, obj in enumerate(objects):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{obj['area_km2']:.4f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{obj['area_pixels']:,}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{obj['perimeter_km']:.4f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{obj['shape_factor']:.4f}"))

            for col in range(5):
                item = self.table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
