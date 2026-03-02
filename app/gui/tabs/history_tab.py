from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QSplitter, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.db import database


class HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("История анализов")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("Обновить")
        self.btn_delete  = QPushButton("Удалить выбранный")
        self.btn_delete.setEnabled(False)
        header_layout.addWidget(self.btn_refresh)
        header_layout.addWidget(self.btn_delete)
        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Таблица истории
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Дата/Время", "Снимок", "% воды", "Площадь (кв.км)", "Объектов"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        # Детали выбранного анализа
        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setFont(QFont("Courier", 11))
        self.detail_box.setMaximumHeight(180)
        self.detail_box.setPlaceholderText("Выберите строку для просмотра деталей...")
        splitter.addWidget(self.detail_box)

        layout.addWidget(splitter)

        self.btn_refresh.clicked.connect(self.load_history)
        self.btn_delete.clicked.connect(self._delete_selected)

        self.load_history()

    def load_history(self):
        rows = database.get_all_analyses()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(row['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(row['timestamp']))
            self.table.setItem(i, 2, QTableWidgetItem(row['scene_name'] or '—'))
            self.table.setItem(i, 3, QTableWidgetItem(f"{row['water_percentage']:.2f}%"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{row['total_water_area_km2']:.4f}"))
            self.table.setItem(i, 5, QTableWidgetItem(str(row['object_count'])))
            for col in range(6):
                item = self.table.item(i, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        if not selected:
            self.btn_delete.setEnabled(False)
            self.detail_box.clear()
            return
        self.btn_delete.setEnabled(True)
        analysis_id = int(self.table.item(self.table.currentRow(), 0).text())
        self._show_detail(analysis_id)

    def _show_detail(self, analysis_id: int):
        analysis, objects = database.get_analysis_detail(analysis_id)
        if not analysis:
            return
        lines = [
            f"Анализ #{analysis['id']}  |  {analysis['timestamp']}",
            f"Снимок: {analysis['scene_name'] or '—'}",
            f"",
            f"Площадь воды:   {analysis['total_water_area_km2']:.4f} кв.км   ({analysis['water_percentage']:.2f}%)",
            f"Периметр:       {analysis['total_perimeter_km']:.4f} км",
            f"Объектов:       {analysis['object_count']}",
            f"Крупнейший:     {analysis['largest_object_area']:.4f} кв.км",
            f"",
            f"Параметры: NDWI={analysis['ndwi_threshold']}  MNDWI={analysis['mndwi_threshold']}  "
            f"AWEI={analysis['awei_threshold']}  LSWI={analysis['lswi_threshold']}",
            f"Мин. объект: {analysis['min_object_size']} пикс.  "
            f"Морфология: {'да' if analysis['apply_morphology'] else 'нет'}",
        ]
        if analysis['export_path']:
            lines.append(f"Экспорт: {analysis['export_path']}")
        self.detail_box.setPlainText("\n".join(lines))

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        analysis_id = int(self.table.item(row, 0).text())
        reply = QMessageBox.question(
            self, "Удалить запись",
            f"Удалить анализ #{analysis_id} из истории?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            database.delete_analysis(analysis_id)
            self.load_history()
            self.detail_box.clear()
