import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont

from app.gui.image_viewer import ImageViewer, _to_uint8

_PREVIEW_PX = 380  # быстрое превью пока идёт фоновый рендер


def _get_view_array(index: int, results: dict) -> np.ndarray | None:
    r = results
    if index == 0:
        return r.get('rgb_image')
    elif index == 1 and 'water_mask' in r:
        mask = r['water_mask'].astype(bool)
        arr = np.empty((*mask.shape, 3), dtype=np.float32)
        arr[:] = [0.88, 0.88, 0.88]
        arr[mask] = [0.2, 0.5, 1.0]
        return arr
    elif index == 2:
        return r.get('overlay_image')
    elif index == 3:
        return r.get('contour_image')
    elif index == 4:
        return r.get('cloud_mask_image')
    return None


class RenderWorker(QThread):
    preview_ready = Signal(int, object)  # (view_index, arr_u8 preview)
    full_ready    = Signal(int, object)  # (view_index, arr_u8 full)

    def __init__(self, index: int, results: dict, max_px: int):
        super().__init__()
        self._index   = index
        self._results = results
        self._max_px  = max_px

    def run(self):
        arr = _get_view_array(self._index, self._results)
        if arr is None:
            return

        # Этап 1: маленькое превью
        preview = _to_uint8(arr, _PREVIEW_PX)
        if not self.isInterruptionRequested():
            self.preview_ready.emit(self._index, preview)

        # Этап 2: полное качество
        if not self.isInterruptionRequested():
            full = _to_uint8(arr, self._max_px)
            if not self.isInterruptionRequested():
                self.full_ready.emit(self._index, full)


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
        self._cache_u8: dict[int, np.ndarray] = {}       # uint8 кеш полного качества
        self._cache_preview: dict[int, np.ndarray] = {}  # uint8 кеш 380px превью
        self._current_view = 0
        self._max_px = 1600
        self._render_worker: RenderWorker | None = None
        # Retiring-воркеры: держим Python-ссылку пока поток не завершится,
        # иначе GC удаляет обёртку раньше C++ потока, получаем краш
        self._retiring: list[RenderWorker] = []
        # Debounce для слайдера качества
        self._quality_timer = QTimer()
        self._quality_timer.setSingleShot(True)
        self._quality_timer.setInterval(250)
        self._quality_timer.timeout.connect(self._apply_quality_change)
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

        view_labels = ['RGB', 'Маска', 'Overlay', 'Контуры', 'Облака']
        self._view_btns: list[ViewButton] = []
        for i, lbl in enumerate(view_labels):
            btn = ViewButton(lbl)
            btn.clicked.connect(lambda _, idx=i: self._switch_view(idx))
            tb_layout.addWidget(btn)
            self._view_btns.append(btn)
        self._view_btns[0].mark_active(True)

        tb_layout.addSpacing(12)

        self.sl_brightness = LabeledSlider('Яркость',  -100, 100, 0)
        self.sl_contrast   = LabeledSlider('Контраст',  -50, 150, 0)
        self.sl_sharpness  = LabeledSlider('Резкость',    0, 100, 0)
        for sl in (self.sl_brightness, self.sl_contrast, self.sl_sharpness):
            tb_layout.addWidget(sl)

        tb_layout.addSpacing(8)

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

        self.viewer = ImageViewer()
        layout.addWidget(self.viewer, 1)

        self.placeholder = QLabel('Загрузите данные Landsat 9\nи запустите анализ')
        self.placeholder.setFont(QFont('Arial', 14))
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet('color: #aaaaaa;')
        layout.addWidget(self.placeholder)

        hint = QLabel('Колёсико - масштаб  |  ЛКМ + перетащить - перемещение')
        hint.setStyleSheet('color: #aaaaaa; font-size: 10px;')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.sl_brightness.valueChanged.connect(self._apply_enhancement)
        self.sl_contrast.valueChanged.connect(self._apply_enhancement)
        self.sl_sharpness.valueChanged.connect(self._apply_enhancement)
        self.sl_quality.valueChanged.connect(self._on_quality_change)

    # Public API

    def show_results(self, results: dict, orig_shape: tuple[int, int]):
        self.results = results
        self._orig_shape = orig_shape
        self._cache_u8.clear()
        self._cache_preview.clear()
        self._retire_current_worker()
        self.placeholder.hide()
        self.btn_export.setEnabled(True)
        self._switch_view(0)

    def highlight_object(self, obj_index: int):
        if not self.results or self._orig_shape is None:
            return
        objects = self.results.get('objects_data', [])
        if 0 <= obj_index < len(objects):
            contour = objects[obj_index].get('contour')
            self.viewer.highlight_object(contour, self._orig_shape)

    # Internal

    def _switch_view(self, index: int):
        prev_view = self._current_view
        self._current_view = index
        for i, btn in enumerate(self._view_btns):
            btn.mark_active(i == index)

        if self.results is None:
            return

        if index in self._cache_u8:
            self.viewer.set_image_u8(self._cache_u8[index])
            return

        if index in self._cache_preview:
            self.viewer.set_image_u8(self._cache_preview[index])
        elif prev_view in self._cache_preview:
            self.viewer.set_image_u8(self._cache_preview[prev_view])

        self._start_render(index)

    def _start_render(self, index: int):
        self._retire_current_worker()
        self._render_worker = RenderWorker(index, self.results, self._max_px)
        self._render_worker.preview_ready.connect(self._on_preview_ready)
        self._render_worker.full_ready.connect(self._on_full_ready)
        self._render_worker.start()

    def _retire_current_worker(self):
        """Отправляет текущий воркер на пенсию: прерывает, отключает сигналы,
        но НЕ ждёт - Python-ссылка живёт в _retiring пока поток не завершится."""
        w = self._render_worker
        if w is None:
            return
        w.requestInterruption()
        try:
            w.preview_ready.disconnect()
            w.full_ready.disconnect()
        except RuntimeError:
            pass
        self._retiring.append(w)
        w.finished.connect(lambda: self._retiring.remove(w) if w in self._retiring else None)
        self._render_worker = None

    def _on_preview_ready(self, index: int, arr_u8: np.ndarray):
        self._cache_preview[index] = arr_u8  # кешируем для быстрого показа при следующем свопе
        if index == self._current_view:
            self.viewer.set_image_u8(arr_u8)

    def _on_full_ready(self, index: int, arr_u8: np.ndarray):
        self._cache_u8[index] = arr_u8
        if index == self._current_view:
            self.viewer.set_image_u8(arr_u8)

    def _apply_enhancement(self, _=None):
        brightness = self.sl_brightness.value()
        contrast   = 1.0 + self.sl_contrast.value() / 100.0
        sharpness  = self.sl_sharpness.value() / 100.0 * 3.0
        self.viewer.set_enhancement(brightness, contrast, sharpness)

    def _on_quality_change(self, v: int):
        self._max_px = v
        self._quality_timer.start()

    def _apply_quality_change(self):
        self._cache_u8.clear()
        if self.results is not None:
            self._start_render(self._current_view)
