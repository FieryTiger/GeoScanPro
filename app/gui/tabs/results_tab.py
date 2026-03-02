import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from app.gui.image_viewer import ImageViewer


class ResultsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.results = None
        self._cache: dict[int, np.ndarray] = {}  # кэш уже подготовленных массивов
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()

        self.combo_view = QComboBox()
        self.combo_view.addItems([
            "Исходный снимок (RGB)",
            "Бинарная маска воды",
            "Наложение маски",
            "Контуры объектов",
        ])
        self.combo_view.currentIndexChanged.connect(self._update_view)

        btn_fit = QPushButton("Вписать")
        btn_fit.setFixedWidth(80)
        btn_fit.clicked.connect(lambda: self.viewer.fit())

        self.btn_export = QPushButton("Экспорт результатов")
        self.btn_export.setEnabled(False)

        toolbar.addWidget(QLabel("Вид:"))
        toolbar.addWidget(self.combo_view)
        toolbar.addWidget(btn_fit)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_export)
        layout.addLayout(toolbar)

        self.viewer = ImageViewer()
        layout.addWidget(self.viewer)

        hint = QLabel("Колёсико — масштаб  |  ЛКМ + перетащить — перемещение")
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.placeholder = QLabel("Результаты анализа появятся здесь после обработки данных")
        self.placeholder.setFont(QFont("Arial", 13))
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder)

    def show_results(self, results: dict, loaded_data: dict):
        self.results = results
        self._cache.clear()
        self.placeholder.hide()
        self.btn_export.setEnabled(True)
        self._update_view(self.combo_view.currentIndex())

    def _update_view(self, index: int):
        if self.results is None:
            return

        arr = self._get_array(index)
        if arr is not None:
            self.viewer.set_image(arr)

    def _get_array(self, index: int) -> np.ndarray | None:
        """Возвращает массив для отображения, кэширует результат."""
        if index in self._cache:
            return self._cache[index]

        arr = None
        r = self.results

        if index == 0:
            arr = r.get('rgb_image')

        elif index == 1 and 'water_mask' in r:
            # Вода - синий [0.2, 0.5, 1.0], суша - светло-серый [0.88, 0.88, 0.88]
            mask = r['water_mask']
            rgb = np.where(mask[:, :, np.newaxis], [0.2, 0.5, 1.0], [0.88, 0.88, 0.88])
            arr = rgb.astype(np.float32)

        elif index == 2:
            arr = r.get('overlay_image')

        elif index == 3:
            arr = r.get('contour_image')

        if arr is not None:
            self._cache[index] = arr

        return arr
