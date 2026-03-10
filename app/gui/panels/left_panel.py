import zipfile, tarfile
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QDoubleSpinBox,
    QSpinBox, QCheckBox, QScrollArea, QSizePolicy, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPixmap

from app.core.data_processor import DataProcessor
from app.gui.workers import LoadWorker


BAND_INFO = {
    'SR_B2':    ('B2',  'Blue',   '#4488FF'),
    'SR_B3':    ('B3',  'Green',  '#44BB44'),
    'SR_B4':    ('B4',  'Red',    '#FF4444'),
    'SR_B5':    ('B5',  'NIR',    '#AA44FF'),
    'SR_B6':    ('B6',  'SWIR1',  '#FF8800'),
    'SR_B7':    ('B7',  'SWIR2',  '#FF4400'),
    'QA_PIXEL': ('QA',  'Quality','#888888'),
}

# Опциональные каналы
OPTIONAL_BAND_INFO = {
    'st_celsius': ('ST',  'Thermal (B10)', '#E8A020'),
    'cdist_km':   ('CD',  'Cloud Dist',    '#E8A020'),
}


class BandRow(QWidget):
    def __init__(self, band_key: str):
        super().__init__()
        self.band_key = band_key
        short, name, color = BAND_INFO[band_key]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        dot = QLabel('●')
        dot.setStyleSheet(f'color: {color}; font-size: 14px;')
        dot.setFixedWidth(16)

        label = QLabel(f'{short}  {name}')
        label.setFont(QFont('Arial', 12))

        self.status = QLabel('—')
        self.status.setFont(QFont('Arial', 12))
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(dot)
        layout.addWidget(label, 1)
        layout.addWidget(self.status)

    def set_found(self, found: bool):
        if found:
            self.status.setText('✓')
            self.status.setStyleSheet('color: #44BB44; font-weight: bold;')
        else:
            self.status.setText('✗')
            self.status.setStyleSheet('color: #FF4444; font-weight: bold;')

    def set_optional(self, found: bool):
        """Для опциональных каналов: жёлтый круг если отсутствует, зелёная галка если есть."""
        if found:
            self.status.setText('✓')
            self.status.setStyleSheet('color: #44BB44; font-weight: bold;')
        else:
            self.status.setText('●')
            self.status.setStyleSheet('color: #E8A020; font-weight: bold;')

    def reset(self):
        self.status.setText('—')
        self.status.setStyleSheet('color: #888888;')


class OptionalBandRow(QWidget):
    """Строка для опционального канала: жёлтый круг если отсутствует, зелёная галка если есть."""
    def __init__(self, short: str, name: str, color: str, tooltip: str = ''):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        dot = QLabel('●')
        dot.setStyleSheet(f'color: {color}; font-size: 14px;')
        dot.setFixedWidth(16)

        label = QLabel(f'{short}  {name}')
        label.setFont(QFont('Arial', 12))

        self.status = QLabel('—')
        self.status.setFont(QFont('Arial', 12))
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(dot)
        layout.addWidget(label, 1)
        layout.addWidget(self.status)

        if tooltip:
            self.setToolTip(tooltip)

    def set_status(self, found: bool):
        if found:
            self.status.setText('✓')
            self.status.setStyleSheet('color: #44BB44; font-weight: bold;')
        else:
            self.status.setText('●')
            self.status.setStyleSheet('color: #E8A020; font-weight: bold;')

    def reset(self):
        self.status.setText('—')
        self.status.setStyleSheet('color: #888888;')


class LeftPanel(QScrollArea):
    files_loaded      = Signal(list)   # пути к .tif файлам
    analysis_requested = Signal(dict)  # параметры детектирования
    load_progress     = Signal(str)

    def __init__(self, data_processor: DataProcessor):
        super().__init__()
        self.data_processor = data_processor
        self._load_worker = None
        self._loading_files: list = []

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedWidth(270)
        self.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(10)
        self.setWidget(content)

        self._build_load_section()
        self._build_bands_section()
        self._build_meta_section()
        self._build_detection_section()
        self._layout.addStretch()
        self._build_branding()
        self._build_run_button()

        self.setAcceptDrops(True)

    # Build sections

    def _build_load_section(self):
        self.drop_frame = QFrame()
        self.drop_frame.setFixedHeight(80)
        self.drop_frame.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaaaaa;
                border-radius: 6px;
                background: #f5f5f5;
            }
        """)
        drop_layout = QVBoxLayout(self.drop_frame)
        lbl = QLabel('Перетащите архив\nили файлы .tif сюда')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet('color: #888; font-size: 13px; border: none;')
        drop_layout.addWidget(lbl)
        self._layout.addWidget(self.drop_frame)

        btn_row = QHBoxLayout()
        self.btn_files   = QPushButton('Файлы .tif')
        self.btn_archive = QPushButton('Архив')
        self.btn_files.setFixedHeight(28)
        self.btn_archive.setFixedHeight(28)
        self.btn_files.clicked.connect(self.load_files)
        self.btn_archive.clicked.connect(self.load_archive)
        btn_row.addWidget(self.btn_files)
        btn_row.addWidget(self.btn_archive)
        self._layout.addLayout(btn_row)

    def _build_bands_section(self):
        grp = QGroupBox('Каналы')
        grp.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        layout = QVBoxLayout(grp)
        layout.setSpacing(1)
        layout.setContentsMargins(6, 8, 6, 8)

        self.band_rows: dict[str, BandRow] = {}
        for key in BAND_INFO:
            row = BandRow(key)
            self.band_rows[key] = row
            layout.addWidget(row)

        # Разделитель перед опциональными каналами
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color: #cccccc;')
        layout.addWidget(sep)

        self.optional_rows: dict[str, 'OptionalBandRow'] = {}
        tooltips = {
            'st_celsius': 'ST_B10 — температура поверхности.\nНужен для температурной маски облаков.',
            'cdist_km':   'ST_CDIST — расстояние до ближайшего облака.\nНужен для буферной маски краёв облаков.',
        }
        for key, (short, name, color) in OPTIONAL_BAND_INFO.items():
            row = OptionalBandRow(short, name, color, tooltips.get(key, ''))
            self.optional_rows[key] = row
            layout.addWidget(row)

        self._layout.addWidget(grp)

    def _build_meta_section(self):
        self.meta_group = QGroupBox('Метаданные сцены')
        self.meta_group.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        self.meta_group.setVisible(False)
        layout = QVBoxLayout(self.meta_group)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(3)

        self.lbl_date  = QLabel()
        self.lbl_cloud = QLabel()
        self.lbl_sun   = QLabel()
        self.lbl_path  = QLabel()
        for lbl in (self.lbl_date, self.lbl_cloud, self.lbl_sun, self.lbl_path):
            lbl.setFont(QFont('Arial', 12))
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

        self._layout.addWidget(self.meta_group)

    def _build_detection_section(self):
        grp = QGroupBox('Пороги детектирования')
        grp.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        self.threshold_spins: dict[str, QDoubleSpinBox] = {}
        indices = [
            ('NDWI',     'NDWI',     0.30, -1.0, 1.0),
            ('MNDWI',    'MNDWI',    0.20, -1.0, 1.0),
            ('AWEI_nsh', 'AWEI',     0.00, -10., 10.),
            ('LSWI',     'LSWI',     0.30, -1.0, 1.0),
        ]
        for key, label, default, lo, hi in indices:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(52)
            lbl.setFont(QFont('Arial', 12))
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            spin.setValue(default)
            self.threshold_spins[key] = spin
            row.addWidget(lbl)
            row.addWidget(spin)
            layout.addLayout(row)

        self.chk_shadows = QCheckBox('Маскировать тени облаков')
        self.chk_shadows.setChecked(True)
        self.chk_shadows.setFont(QFont('Arial', 12))
        self.chk_shadows.setToolTip(
            'Исключать тени облаков из детектирования.\n'
            'Снимите, если тени падают на водоёмы и создают дыры в маске.\n'
            'В этом случае рекомендуется включить «Заполнить под облаками».'
        )
        layout.addWidget(self.chk_shadows)

        self.chk_morph = QCheckBox('Морфологическая обработка')
        self.chk_morph.setChecked(True)
        self.chk_morph.setFont(QFont('Arial', 12))
        layout.addWidget(self.chk_morph)

        size_row = QHBoxLayout()
        size_lbl = QLabel('Мин. объект, пикс.:')
        size_lbl.setFont(QFont('Arial', 12))
        self.spin_min_size = QSpinBox()
        self.spin_min_size.setRange(1, 50000)
        self.spin_min_size.setValue(100)
        size_row.addWidget(size_lbl)
        size_row.addWidget(self.spin_min_size)
        layout.addLayout(size_row)

        gap_row = QHBoxLayout()
        gap_lbl = QLabel('Слияние разрывов, пикс.:')
        gap_lbl.setFont(QFont('Arial', 12))
        self.spin_merge_gap = QSpinBox()
        self.spin_merge_gap.setRange(0, 50)
        self.spin_merge_gap.setValue(0)
        self.spin_merge_gap.setToolTip(
            'Радиус closing для объединения близких объектов.\n0 = выключено.'
        )
        gap_row.addWidget(gap_lbl)
        gap_row.addWidget(self.spin_merge_gap)
        layout.addLayout(gap_row)

        self.chk_spatial_fill = QCheckBox('Заполнить под облаками')
        self.chk_spatial_fill.setChecked(True)
        self.chk_spatial_fill.setFont(QFont('Arial', 12))
        self.chk_spatial_fill.setToolTip(
            'Тени и облака внутри водоёма заполняются как вода.\n'
            'Тени от облаков мешают детектированию воды — эта опция восстанавливает пропущенные участки.\n'
            'Компонент заполняется если ≥70% его границы окружено водой.'
        )
        layout.addWidget(self.chk_spatial_fill)

        fill_row = QHBoxLayout()
        fill_row.setContentsMargins(16, 0, 0, 0)
        fill_lbl = QLabel('Мин. площадь, пикс.:')
        fill_lbl.setFont(QFont('Arial', 12))
        self.spin_min_fill_area = QSpinBox()
        self.spin_min_fill_area.setRange(1, 100000)
        self.spin_min_fill_area.setValue(20)
        self.spin_min_fill_area.setToolTip('Минимальная площадь тени/облака для заполнения.')
        fill_row.addWidget(fill_lbl)
        fill_row.addWidget(self.spin_min_fill_area)
        layout.addLayout(fill_row)

        frac_row = QHBoxLayout()
        frac_row.setContentsMargins(16, 0, 0, 0)
        frac_lbl = QLabel('Мин. окружение водой:')
        frac_lbl.setFont(QFont('Arial', 12))
        self.spin_fill_frac = QDoubleSpinBox()
        self.spin_fill_frac.setRange(0.1, 1.0)
        self.spin_fill_frac.setSingleStep(0.05)
        self.spin_fill_frac.setDecimals(2)
        self.spin_fill_frac.setValue(0.50)
        self.spin_fill_frac.setToolTip('Доля границы тени/облака окружённой водой (0.5 = 50%).\nМеньше = заполняет агрессивнее, больше = строже.')
        frac_row.addWidget(frac_lbl)
        frac_row.addWidget(self.spin_fill_frac)
        layout.addLayout(frac_row)

        # Разделитель
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet('color: #cccccc;')
        layout.addWidget(sep2)

        # Температурная маска
        self.chk_thermal = QCheckBox('Темп. маска (ST_B10)')
        self.chk_thermal.setChecked(False)
        self.chk_thermal.setFont(QFont('Arial', 12))
        self.chk_thermal.setEnabled(False)
        self.chk_thermal.setToolTip('Требуется файл ST_B10.\nХолодный + яркий пиксель = незамаскированное облако.')
        layout.addWidget(self.chk_thermal)

        thermal_row = QHBoxLayout()
        thermal_row.setContentsMargins(16, 0, 0, 0)
        t_lbl = QLabel('Порог °C:')
        t_lbl.setFont(QFont('Arial', 12))
        self.spin_thermal_temp = QDoubleSpinBox()
        self.spin_thermal_temp.setRange(-20.0, 20.0)
        self.spin_thermal_temp.setSingleStep(0.5)
        self.spin_thermal_temp.setDecimals(1)
        self.spin_thermal_temp.setValue(5.0)
        self.spin_thermal_temp.setEnabled(False)
        thermal_row.addWidget(t_lbl)
        thermal_row.addWidget(self.spin_thermal_temp)
        thermal_row.addStretch()
        layout.addLayout(thermal_row)

        self.chk_thermal.toggled.connect(self.spin_thermal_temp.setEnabled)

        # CDIST буфер
        self.chk_cdist = QCheckBox('Буфер облаков (ST_CDIST)')
        self.chk_cdist.setChecked(False)
        self.chk_cdist.setFont(QFont('Arial', 12))
        self.chk_cdist.setEnabled(False)
        self.chk_cdist.setToolTip('Требуется файл ST_CDIST.\nУбирает ложные объекты на краях облаков.')
        layout.addWidget(self.chk_cdist)

        cdist_row = QHBoxLayout()
        cdist_row.setContentsMargins(16, 0, 0, 0)
        c_lbl = QLabel('Буфер км:')
        c_lbl.setFont(QFont('Arial', 12))
        self.spin_cdist_km = QDoubleSpinBox()
        self.spin_cdist_km.setRange(0.1, 5.0)
        self.spin_cdist_km.setSingleStep(0.1)
        self.spin_cdist_km.setDecimals(1)
        self.spin_cdist_km.setValue(0.3)
        self.spin_cdist_km.setEnabled(False)
        cdist_row.addWidget(c_lbl)
        cdist_row.addWidget(self.spin_cdist_km)
        cdist_row.addStretch()
        layout.addLayout(cdist_row)

        self.chk_cdist.toggled.connect(self.spin_cdist_km.setEnabled)

        # Разделитель
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet('color: #cccccc;')
        layout.addWidget(sep3)

        # Буфер QA-маски
        buf_row = QHBoxLayout()
        buf_lbl = QLabel('Буфер QA, пикс.:')
        buf_lbl.setFont(QFont('Arial', 12))
        self.spin_cloud_buffer = QSpinBox()
        self.spin_cloud_buffer.setRange(0, 15)
        self.spin_cloud_buffer.setValue(0)
        self.spin_cloud_buffer.setToolTip(
            'Расширяет QA-маску облаков на N пикселей.\n'
            'Захватывает "чёрную мешанину" по краям облаков (cloud adjacency effect).\n'
            'Расширенные пиксели восстанавливаются spatial fill если окружены водой.\n'
            '2–4 пикс. обычно достаточно.'
        )
        buf_row.addWidget(buf_lbl)
        buf_row.addWidget(self.spin_cloud_buffer)
        layout.addLayout(buf_row)

        # HOT-маска
        self.chk_hot = QCheckBox('HOT-маска (дымка/хейз)')
        self.chk_hot.setChecked(False)
        self.chk_hot.setFont(QFont('Arial', 12))
        self.chk_hot.setToolTip(
            'Haze Optimized Transform: HOT = Blue − 0.5 × Red.\n'
            'Высокий HOT → полупрозрачное облако или дымка.\n'
            'Маскирует пиксели с HOT выше порога, затем spatial fill восстанавливает их.\n'
            'Не требует дополнительных файлов.'
        )
        layout.addWidget(self.chk_hot)

        hot_row = QHBoxLayout()
        hot_row.setContentsMargins(16, 0, 0, 0)
        hot_lbl = QLabel('Порог HOT:')
        hot_lbl.setFont(QFont('Arial', 12))
        self.spin_hot_threshold = QDoubleSpinBox()
        self.spin_hot_threshold.setRange(0.01, 0.80)
        self.spin_hot_threshold.setSingleStep(0.01)
        self.spin_hot_threshold.setDecimals(2)
        self.spin_hot_threshold.setValue(0.05)
        self.spin_hot_threshold.setEnabled(False)
        self.spin_hot_threshold.setToolTip(
            'Пиксели с HOT > порога маскируются как облако.\n'
            '0.05 — мягко, 0.03 — агрессивнее.'
        )
        hot_row.addWidget(hot_lbl)
        hot_row.addWidget(self.spin_hot_threshold)
        hot_row.addStretch()
        layout.addLayout(hot_row)

        self.chk_hot.toggled.connect(self.spin_hot_threshold.setEnabled)

        self._layout.addWidget(grp)

    def _build_branding(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = Path('resources/GeoScanPro.png')
        if logo_path.exists():
            pix = QPixmap(str(logo_path)).scaledToWidth(
                160, Qt.TransformationMode.SmoothTransformation
            )
            logo_lbl.setPixmap(pix)
        layout.addWidget(logo_lbl)

        ver_lbl = QLabel('v2.0  •  Landsat 9 Water Detection')
        ver_lbl.setFont(QFont('Arial', 12))
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_lbl.setStyleSheet('color: #94a3b8;')

        layout.addWidget(ver_lbl)
        self._layout.addWidget(container)

    def _build_run_button(self):
        self.btn_run = QPushButton('▶  Запустить анализ')
        self.btn_run.setMinimumHeight(40)
        self.btn_run.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._emit_analysis)
        self._layout.addWidget(self.btn_run)

    # Public API

    def set_bands_status(self, loaded_data: dict):
        for key, row in self.band_rows.items():
            row.set_found(key in loaded_data)

        has_thermal = 'st_celsius' in loaded_data
        has_cdist   = 'cdist_km'   in loaded_data

        self.optional_rows['st_celsius'].set_status(has_thermal)
        self.optional_rows['cdist_km'].set_status(has_cdist)

        self.chk_thermal.setEnabled(has_thermal)
        self.spin_thermal_temp.setEnabled(has_thermal and self.chk_thermal.isChecked())
        if not has_thermal:
            self.chk_thermal.setChecked(False)
            self.chk_thermal.setToolTip('ST_B10 не загружен. Добавьте файл ST_B10.TIF в набор данных.')

        self.chk_cdist.setEnabled(has_cdist)
        self.spin_cdist_km.setEnabled(has_cdist and self.chk_cdist.isChecked())
        if not has_cdist:
            self.chk_cdist.setChecked(False)
            self.chk_cdist.setToolTip('ST_CDIST не загружен. Добавьте файл ST_CDIST.TIF в набор данных.')

    def show_metadata(self, meta: dict):
        self.lbl_date.setText(f"{meta.get('date', '—')}  {meta.get('time', '')}")
        self.lbl_cloud.setText(f"Облачность: {meta.get('cloud_cover', '—')}%")
        self.lbl_sun.setText(f"Угол Солнца: {meta.get('sun_elevation', '—')}°")
        self.lbl_path.setText(f"Path/Row: {meta.get('wrs_path', '—')}/{meta.get('wrs_row', '—')}")
        self.meta_group.setVisible(True)

    def set_running(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_run.setText('Анализ...' if running else 'Запустить анализ')

    # Drag & Drop

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.zip', '.tar', '.gz')):
                self._process_archive(path)
                return
            elif path.lower().endswith(('.tif', '.tiff')):
                self.load_files()
                return

    # Loading

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Выберите файлы Landsat 9', '', 'TIFF (*.tif *.TIF *.tiff)'
        )
        if files:
            self._start_load(files)

    def load_archive(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите архив', '', 'Архивы (*.zip *.tar *.gz)'
        )
        if path:
            self._process_archive(path)

    def _process_archive(self, archive_path: str):
        temp_dir = Path('temp_extracted')
        temp_dir.mkdir(exist_ok=True)
        try:
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as z:
                    z.extractall(temp_dir)
            else:
                with tarfile.open(archive_path, 'r') as t:
                    t.extractall(temp_dir)
            tif_files = [str(f) for f in temp_dir.rglob('*.tif')] + \
                        [str(f) for f in temp_dir.rglob('*.TIF')]
            if tif_files:
                self._start_load(tif_files)
            else:
                QMessageBox.warning(self, 'Файлы не найдены', 'В архиве нет .tif файлов')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось извлечь архив:\n{e}')

    def _start_load(self, file_paths: list):
        self._loading_files = file_paths
        self.btn_files.setEnabled(False)
        self.btn_archive.setEnabled(False)
        self.btn_run.setEnabled(False)
        # Reset all band rows to loading state
        for row in self.band_rows.values():
            row.reset()
        for row in self.optional_rows.values():
            row.reset()

        self._load_worker = LoadWorker(self.data_processor, file_paths)
        self._load_worker.band_loaded.connect(self._on_band_loaded)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.progress.connect(self.load_progress)
        self._load_worker.start()

    def _on_band_loaded(self, band_key: str):
        """Вызывается из LoadWorker по мере загрузки каждого канала."""
        if band_key in self.band_rows:
            self.band_rows[band_key].set_found(True)
        elif band_key in self.optional_rows:
            self.optional_rows[band_key].set_status(True)

    def _on_load_finished(self, loaded_data: object):
        self.btn_files.setEnabled(True)
        self.btn_archive.setEnabled(True)
        self.set_bands_status(loaded_data)
        self.btn_run.setEnabled(True)
        self.files_loaded.emit(self._loading_files)

    def _on_load_error(self, msg: str):
        self.btn_files.setEnabled(True)
        self.btn_archive.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, 'Ошибка загрузки', msg)

    def _emit_analysis(self):
        self.analysis_requested.emit({
            'thresholds': {k: s.value() for k, s in self.threshold_spins.items()},
            'min_object_size': self.spin_min_size.value(),
            'apply_morphology': self.chk_morph.isChecked(),
            'merge_gap_px': self.spin_merge_gap.value(),
            'spatial_fill': self.chk_spatial_fill.isChecked(),
            'min_fill_area': self.spin_min_fill_area.value(),
            'fill_water_frac': self.spin_fill_frac.value(),
            'mask_shadows': self.chk_shadows.isChecked(),
            'use_thermal_mask': self.chk_thermal.isChecked(),
            'thermal_temp_c': self.spin_thermal_temp.value(),
            'thermal_bright_threshold': 0.12,
            'use_cdist_buffer': self.chk_cdist.isChecked(),
            'cdist_buffer_km': self.spin_cdist_km.value(),
            'cloud_buffer_px': self.spin_cloud_buffer.value(),
            'use_hot_mask': self.chk_hot.isChecked(),
            'hot_threshold': self.spin_hot_threshold.value(),
        })
