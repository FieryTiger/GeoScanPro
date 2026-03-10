import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.gui.image_viewer import ImageViewer, _to_uint8


class ViewButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setFixedHeight(28)
        self.setFont(QFont('Arial', 10))
        self.mark_active(False)

    def mark_active(self, active: bool):
        if active:
            self.setStyleSheet("""
                QPushButton {
                    background: #2563eb;
                    color: white;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    padding: 0 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: #f1f5f9;
                    color: #333;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 0 10px;
                }
                QPushButton:hover { background: #e2e8f0; }
            """)


class LabeledSlider(QWidget):
    valueChanged = Signal(int)

    def __init__(self, label: str, lo: int, hi: int, default: int, step: int = 1):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl = QLabel(label)
        lbl.setFont(QFont('Arial', 9))
        lbl.setFixedWidth(58)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(default)
        self.slider.setSingleStep(step)
        self.slider.setFixedWidth(100)

        self.val_lbl = QLabel(str(default))
        self.val_lbl.setFont(QFont('Arial', 9))
        self.val_lbl.setFixedWidth(32)
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.slider.valueChanged.connect(self._on_change)

        layout.addWidget(lbl)
        layout.addWidget(self.slider)
        layout.addWidget(self.val_lbl)

    def _on_change(self, v: int):
        self.val_lbl.setText(str(v))
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self.slider.value()


class CenterPanel(QWidget):
    export_requested = Signal()

    def __init__(self):
        super().__init__()
        self.results = None
        self._orig_shape: tuple[int, int] | None = None
        self._cache: dict[int, np.ndarray] = {}      # float32 массивы по индексу вида
        self._cache_u8: dict[int, np.ndarray] = {}   # uint8 ресайзнутые — для быстрого показа
        self._current_view = 0
        self._max_px = 1600  # максимальный размер стороны при отображении
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ---- Toolbar ----
        toolbar = QWidget()
        toolbar.setFixedHeight(52)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 10, 10, 6)
        tb_layout.setSpacing(6)
        tb_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # View buttons
        view_labels = ['RGB', 'Маска', 'Overlay', 'Контуры', 'Облака']
        self._view_btns: list[ViewButton] = []
        for i, lbl in enumerate(view_labels):
            btn = ViewButton(lbl)
            btn.clicked.connect(lambda _, idx=i: self._switch_view(idx))
            tb_layout.addWidget(btn)
            self._view_btns.append(btn)
        self._view_btns[0].mark_active(True)

        tb_layout.addSpacing(12)

        # Enhancement sliders
        self.sl_brightness = LabeledSlider('Яркость',   -100, 100, 0)
        self.sl_contrast   = LabeledSlider('Контраст',   -50, 150, 0)
        self.sl_sharpness  = LabeledSlider('Резкость',     0, 100, 0)
        for sl in (self.sl_brightness, self.sl_contrast, self.sl_sharpness):
            tb_layout.addWidget(sl)

        tb_layout.addSpacing(8)

        # Качество отображения (макс. размер стороны в пикселях)
        self.sl_quality = LabeledSlider('Разр.', 600, 2400, self._max_px, 200)
        self.sl_quality.slider.setFixedWidth(80)
        tb_layout.addWidget(self.sl_quality)

        tb_layout.addStretch()

        self.btn_fit = QPushButton('Вписать')
        self.btn_fit.setFixedHeight(28)
        self.btn_fit.setFixedWidth(70)
        self.btn_fit.clicked.connect(lambda: self.viewer.reset_zoom())

        self.btn_export = QPushButton('💾 Экспорт')
        self.btn_export.setFixedHeight(28)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_requested)

        tb_layout.addWidget(self.btn_fit)
        tb_layout.addSpacing(6)
        tb_layout.addWidget(self.btn_export)

        layout.addWidget(toolbar)

        # ---- Image viewer ----
        self.viewer = ImageViewer()
        layout.addWidget(self.viewer, 1)

        # Placeholder
        self.placeholder = QLabel('Загрузите данные Landsat 9\nи запустите анализ')
        self.placeholder.setFont(QFont('Arial', 14))
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet('color: #aaaaaa;')
        layout.addWidget(self.placeholder)

        # Hint
        hint = QLabel('Колёсико - масштаб  |  ЛКМ + перетащить - перемещение')
        hint.setStyleSheet('color: #aaaaaa; font-size: 10px;')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Connections
        self.sl_brightness.valueChanged.connect(self._apply_enhancement)
        self.sl_contrast.valueChanged.connect(self._apply_enhancement)
        self.sl_sharpness.valueChanged.connect(self._apply_enhancement)
        self.sl_quality.valueChanged.connect(self._on_quality_change)

    # Public API
    def show_results(self, results: dict, orig_shape: tuple[int, int]):
        self.results = results
        self._orig_shape = orig_shape
        self._cache.clear()
        self._cache_u8.clear()
        self.placeholder.hide()
        self.btn_export.setEnabled(True)
        self._switch_view(0)
        self.viewer.reset_zoom()  # сброс зума только при новых результатах

    def highlight_object(self, obj_index: int):
        if not self.results or self._orig_shape is None:
            return
        objects = self.results.get('objects_data', [])
        if 0 <= obj_index < len(objects):
            contour = objects[obj_index].get('contour')
            self.viewer.highlight_object(contour, self._orig_shape)

    # Internal
    def _switch_view(self, index: int):
        self._current_view = index
        for i, btn in enumerate(self._view_btns):
            btn.mark_active(i == index)
        arr_u8 = self._get_u8(index)
        if arr_u8 is not None:
            # set_image_u8: без ресайза и float-конвертации, зум не сбрасывается
            self.viewer.set_image_u8(arr_u8)

    def _get_u8(self, index: int) -> np.ndarray | None:
        """Возвращает кешированный uint8 массив для текущего _max_px."""
        if index in self._cache_u8:
            return self._cache_u8[index]
        arr = self._get_array(index)
        if arr is None:
            return None
        arr_u8 = _to_uint8(arr, self._max_px)
        self._cache_u8[index] = arr_u8
        return arr_u8

    def _apply_enhancement(self, _=None):
        brightness = self.sl_brightness.value()
        contrast   = 1.0 + self.sl_contrast.value() / 100.0
        sharpness  = self.sl_sharpness.value() / 100.0 * 3.0
        self.viewer.set_enhancement(brightness, contrast, sharpness)

    def _on_quality_change(self, v: int):
        self._max_px = v
        self._cache_u8.clear()  # сбрасываем кеш — нужен ресайз под новый размер
        arr_u8 = self._get_u8(self._current_view)
        if arr_u8 is not None:
            self.viewer.set_image_u8(arr_u8)

    def _get_array(self, index: int) -> np.ndarray | None:
        if index in self._cache:
            return self._cache[index]
        if self.results is None:
            return None

        r = self.results
        arr = None

        if index == 0:
            arr = r.get('rgb_image')
        elif index == 1 and 'water_mask' in r:
            mask = r['water_mask']
            arr = np.where(mask[:, :, np.newaxis], [0.2, 0.5, 1.0], [0.88, 0.88, 0.88])
            arr = arr.astype(np.float32)
        elif index == 2:
            arr = r.get('overlay_image')
        elif index == 3:
            arr = r.get('contour_image')
        elif index == 4:
            arr = r.get('cloud_mask_image')

        if arr is not None:
            self._cache[index] = arr
        return arr
