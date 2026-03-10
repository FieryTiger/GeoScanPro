from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QFileDialog,
    QMessageBox, QToolBar, QDialog, QTabWidget
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt

from app.core.data_processor import DataProcessor
from app.core.water_detector import WaterDetector
from app.utils.exporter import ImageExporter
from app.db import database

from app.gui.workers import AnalysisWorker, LoadWorker, ExportWorker
from app.gui.panels.left_panel import LeftPanel
from app.gui.panels.center_panel import CenterPanel
from app.gui.panels.stats_panel import StatsPanel
from app.gui.tabs.history_tab import HistoryTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_processor = DataProcessor()
        self.water_detector  = WaterDetector()
        self.image_exporter  = ImageExporter()

        self.loaded_data       = None
        self.detection_results = None
        self.current_scene     = ''
        self._worker           = None
        self._export_worker    = None

        self._build_ui()
        self._build_menu()

    # Layout

    def _build_ui(self):
        self.setWindowTitle('GeoScanPro — Детектирование водных объектов')
        self.setMinimumSize(1100, 700)
        self.resize(1440, 900)

        icon_path = Path('resources/GeoScanPro.png')
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.left_panel = LeftPanel(self.data_processor)
        h_splitter.addWidget(self.left_panel)

        v_splitter = QSplitter(Qt.Orientation.Vertical)

        self.center_panel = CenterPanel()
        v_splitter.addWidget(self.center_panel)

        self.stats_panel = StatsPanel()
        v_splitter.addWidget(self.stats_panel)

        v_splitter.setStretchFactor(0, 3)  # viewer gets 75%
        v_splitter.setStretchFactor(1, 1)  # stats gets 25%
        v_splitter.setSizes([600, 220])

        h_splitter.addWidget(v_splitter)
        h_splitter.setStretchFactor(0, 0)  # left panel fixed
        h_splitter.setStretchFactor(1, 1)  # right area expands

        main_layout.addWidget(h_splitter)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage('Готов к работе. Загрузите данные Landsat 9.')

        # Connections
        self.left_panel.files_loaded.connect(self._on_files_loaded)
        self.left_panel.analysis_requested.connect(self._start_analysis)
        self.left_panel.load_progress.connect(self.status.showMessage)
        self.center_panel.export_requested.connect(self._export_results)
        self.stats_panel.object_selected.connect(self._on_object_selected)

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu('Файл')
        act_files   = QAction('Открыть файлы .tif', self)
        act_archive = QAction('Открыть архив', self)
        self.act_export = QAction('Экспорт результатов', self)
        self.act_export.setEnabled(False)
        act_quit = QAction('Выход', self)

        act_files.triggered.connect(self.left_panel.load_files)
        act_archive.triggered.connect(self.left_panel.load_archive)
        self.act_export.triggered.connect(self._export_results)
        act_quit.triggered.connect(self.close)

        file_menu.addAction(act_files)
        file_menu.addAction(act_archive)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        view_menu = mb.addMenu('Вид')
        act_history = QAction('История анализов', self)
        act_history.triggered.connect(self._show_history)
        view_menu.addAction(act_history)

        help_menu = mb.addMenu('Справка')
        act_about = QAction('О программе', self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # Handlers

    def _on_files_loaded(self, file_paths: list):
        self.loaded_data = self.data_processor.data_cache
        self.current_scene = Path(file_paths[0]).parent.name if file_paths else ''
        self.status.showMessage(f'Данные загружены: {self.current_scene}')
        self._try_load_metadata(file_paths)

    def _try_load_metadata(self, file_paths: list):
        """Читаем MTL.txt если он есть рядом с .tif файлами."""
        try:
            folder = Path(file_paths[0]).parent
            mtl_files = list(folder.glob('*_MTL.txt'))
            if not mtl_files:
                return
            text = mtl_files[0].read_text(encoding='utf-8', errors='ignore')

            def extract(key):
                for line in text.splitlines():
                    if key in line:
                        return line.split('=')[-1].strip().strip('"')
                return '—'

            meta = {
                'date':          extract('DATE_ACQUIRED'),
                'time':          extract('SCENE_CENTER_TIME')[:8] + ' UTC',
                'cloud_cover':   extract('CLOUD_COVER'),
                'sun_elevation': extract('SUN_ELEVATION')[:5],
                'wrs_path':      extract('WRS_PATH'),
                'wrs_row':       extract('WRS_ROW'),
            }
            self.left_panel.show_metadata(meta)
        except Exception as e:
            print(f'Метаданные не загружены: {e}')

    def _start_analysis(self, params: dict):
        if not self.loaded_data:
            QMessageBox.warning(self, 'Нет данных', 'Сначала загрузите данные Landsat 9')
            return
        self.left_panel.set_running(True)
        self.status.showMessage('Выполняется анализ...')

        self._worker = AnalysisWorker(self.water_detector, self.loaded_data, params)
        self._worker.finished.connect(lambda r: self._on_done(r, params))
        self._worker.error.connect(self._on_error)
        self._worker.progress.connect(self.status.showMessage)
        self._worker.start()

    def _on_done(self, results: dict, params: dict):
        self.detection_results = results
        self.left_panel.set_running(False)
        self.act_export.setEnabled(True)
        self.status.showMessage(
            f"Готово — площадь воды: {results.get('total_water_area_km2', 0):.2f} км²  "
            f"| объектов: {results.get('object_count', 0)}"
        )

        orig_shape = results['water_mask'].shape
        self.center_panel.show_results(results, orig_shape)
        self.stats_panel.update_statistics(results)

        try:
            database.save_analysis(results, params, self.current_scene)
        except Exception as e:
            print(f'Ошибка сохранения в БД: {e}')

    def _on_error(self, msg: str):
        self.left_panel.set_running(False)
        self.status.showMessage('Ошибка анализа')
        QMessageBox.critical(self, 'Ошибка анализа', msg)

    def _on_object_selected(self, index: int):
        self.center_panel.highlight_object(index)

    def _export_results(self):
        if not self.detection_results:
            QMessageBox.warning(self, 'Нет результатов', 'Сначала выполните анализ')
            return
        if self._export_worker and self._export_worker.isRunning():
            QMessageBox.information(self, 'Экспорт', 'Экспорт уже выполняется...')
            return
        export_dir = QFileDialog.getExistingDirectory(self, 'Выберите папку для экспорта')
        if not export_dir:
            return

        self.center_panel.btn_export.setEnabled(False)
        self.act_export.setEnabled(False)
        self.status.showMessage('Экспорт...')

        self._export_worker = ExportWorker(
            self.image_exporter, self.detection_results, self.loaded_data, export_dir
        )
        self._export_worker.progress.connect(self.status.showMessage)
        self._export_worker.finished.connect(self._on_export_done)
        self._export_worker.start()

    def _on_export_done(self, success: bool, path: str):
        self.center_panel.btn_export.setEnabled(True)
        self.act_export.setEnabled(True)
        if success:
            self.status.showMessage(f'Экспорт завершён — {path}')
            QMessageBox.information(self, 'Экспорт завершён',
                                    f'Результаты сохранены:\n{path}')
        else:
            self.status.showMessage('Ошибка экспорта')
            QMessageBox.critical(self, 'Ошибка экспорта', path)

    def _show_history(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('История анализов')
        dlg.resize(900, 500)
        layout = QVBoxLayout(dlg)
        layout.addWidget(HistoryTab())
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(self, 'О программе', (
            'GeoScanPro v2.0\n\n'
            'Детектирование водных объектов на снимках Landsat 9.\n\n'
            'Индексы: NDWI, MNDWI, AWEI_nsh, LSWI\n'
            'Алгоритм: ансамбль с голосованием\n\n'
            'Разработано для ихтиологов, экологов и специалистов по ДЗЗ.'
        ))
