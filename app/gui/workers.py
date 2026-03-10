import os
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QThread, Signal


class LoadWorker(QThread):
    """Загрузка данных Landsat в фоновом потоке."""
    band_loaded = Signal(str)   # band key (SR_B2, QA_PIXEL, st_celsius, cdist_km)
    finished    = Signal(object)  # loaded_data dict
    error       = Signal(str)
    progress    = Signal(str)

    def __init__(self, data_processor, file_paths):
        super().__init__()
        self.data_processor = data_processor
        self.file_paths = file_paths

    def run(self):
        def on_band(band_key, file_path):
            fname = Path(file_path).name
            self.progress.emit(f'Загружен {band_key} — {fname}')
            self.band_loaded.emit(band_key)

        result = self.data_processor.load_landsat_data(
            self.file_paths, progress_callback=on_band
        )
        if result is not None:
            self.finished.emit(result)
        else:
            self.error.emit(
                'Не удалось загрузить необходимые каналы Landsat 9.\n'
                'Убедитесь что все SR_B2–B7 и QA_PIXEL файлы присутствуют.'
            )


class AnalysisWorker(QThread):
    finished = Signal(dict)
    error    = Signal(str)
    progress = Signal(str)

    def __init__(self, water_detector, loaded_data, params):
        super().__init__()
        self.water_detector = water_detector
        self.loaded_data = loaded_data
        self.params = params

    def run(self):
        try:
            self.progress.emit('Применение параметров...')
            self.water_detector.set_parameters(
                thresholds=self.params.get('thresholds'),
                min_object_size=self.params.get('min_object_size', 100),
                apply_morphology=self.params.get('apply_morphology', True),
                merge_gap_px=self.params.get('merge_gap_px', 0),
                spatial_fill=self.params.get('spatial_fill', False),
                min_fill_area=self.params.get('min_fill_area', 20),
                fill_water_frac=self.params.get('fill_water_frac', 0.50),
                mask_shadows=self.params.get('mask_shadows', True),
                use_thermal_mask=self.params.get('use_thermal_mask', False),
                thermal_temp_c=self.params.get('thermal_temp_c', 5.0),
                thermal_bright_threshold=self.params.get('thermal_bright_threshold', 0.12),
                use_cdist_buffer=self.params.get('use_cdist_buffer', False),
                cdist_buffer_km=self.params.get('cdist_buffer_km', 0.3),
                cloud_buffer_px=self.params.get('cloud_buffer_px', 0),
                use_hot_mask=self.params.get('use_hot_mask', False),
                hot_threshold=self.params.get('hot_threshold', 0.05),
            )

            results = self.water_detector.detect_water(
                self.loaded_data, progress_callback=self.progress.emit
            )

            if results:
                self.finished.emit(results)
            else:
                self.error.emit('Не удалось выполнить анализ')

        except Exception as e:
            self.error.emit(str(e))


class ExportWorker(QThread):
    finished = Signal(bool, str)  # success, export_dir или сообщение об ошибке
    progress = Signal(str)

    def __init__(self, exporter, results, loaded_data, export_dir):
        super().__init__()
        self._exporter   = exporter
        self._results    = results
        self._loaded_data = loaded_data
        self._export_dir = export_dir

    def run(self):
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')

            self.progress.emit('Экспорт изображений...')
            self._exporter.export_results(self._results, self._loaded_data, self._export_dir)

            self.progress.emit('Экспорт Excel...')
            self._exporter.export_to_excel(
                self._results,
                os.path.join(self._export_dir, f'Статистика_{ts}.xlsx'),
            )

            self.progress.emit('Формирование PDF-отчёта...')
            self._exporter.export_to_pdf(
                self._results,
                os.path.join(self._export_dir, f'Отчёт_{ts}.pdf'),
            )

            self.finished.emit(True, self._export_dir)
        except Exception as e:
            self.finished.emit(False, str(e))
