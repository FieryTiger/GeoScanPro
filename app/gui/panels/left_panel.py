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


BAND_INFO = {
    'SR_B2':    ('B2',  'Blue',   '#4488FF'),
    'SR_B3':    ('B3',  'Green',  '#44BB44'),
    'SR_B4':    ('B4',  'Red',    '#FF4444'),
    'SR_B5':    ('B5',  'NIR',    '#AA44FF'),
    'SR_B6':    ('B6',  'SWIR1',  '#FF8800'),
    'SR_B7':    ('B7',  'SWIR2',  '#FF4400'),
    'QA_PIXEL': ('QA',  'Quality','#888888'),
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

    def reset(self):
        self.status.setText('—')
        self.status.setStyleSheet('color: #888888;')


class LeftPanel(QScrollArea):
    files_loaded      = Signal(list)   # пути к .tif файлам
    analysis_requested = Signal(dict)  # параметры детектирования

    def __init__(self, data_processor: DataProcessor):
        super().__init__()
        self.data_processor = data_processor

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
            'В этом случае рекомендуется включить "Заполнить под облаками".'
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
        self.chk_spatial_fill.setChecked(False)
        self.chk_spatial_fill.setFont(QFont('Arial', 12))
        self.chk_spatial_fill.setToolTip(
            'Пиксели облаков, полностью окружённые водой,\nклассифицируются как вода.'
        )
        layout.addWidget(self.chk_spatial_fill)

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

    def show_metadata(self, meta: dict):
        self.lbl_date.setText(f"{meta.get('date', '—')}  {meta.get('time', '')}")
        self.lbl_cloud.setText(f"блачность: {meta.get('cloud_cover', '—')}%")
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
            self._load_and_emit(files)

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
                self._load_and_emit(tif_files)
            else:
                QMessageBox.warning(self, 'Файлы не найдены', 'В архиве нет .tif файлов')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось извлечь архив:\n{e}')

    def _load_and_emit(self, file_paths: list):
        loaded = self.data_processor.load_landsat_data(file_paths)
        if loaded:
            self.set_bands_status(loaded)
            self.btn_run.setEnabled(True)
            self.files_loaded.emit(file_paths)
        else:
            QMessageBox.critical(self, 'Ошибка загрузки',
                                 'Не удалось загрузить необходимые каналы Landsat 9.\n'
                                 'Убедитесь что все SR_B2–B7 и QA_PIXEL файлы присутствуют.')

    def _emit_analysis(self):
        self.analysis_requested.emit({
            'thresholds': {k: s.value() for k, s in self.threshold_spins.items()},
            'min_object_size': self.spin_min_size.value(),
            'apply_morphology': self.chk_morph.isChecked(),
            'merge_gap_px': self.spin_merge_gap.value(),
            'spatial_fill': self.chk_spatial_fill.isChecked(),
            'mask_shadows': self.chk_shadows.isChecked(),
        })
