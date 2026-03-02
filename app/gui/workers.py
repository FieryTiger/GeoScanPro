from PySide6.QtCore import QThread, Signal


class AnalysisWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, water_detector, loaded_data, params):
        super().__init__()
        self.water_detector = water_detector
        self.loaded_data = loaded_data
        self.params = params

    def run(self):
        try:
            self.progress.emit("Применение параметров...")
            self.water_detector.set_parameters(
                thresholds=self.params.get('thresholds'),
                min_object_size=self.params.get('min_object_size', 100),
                apply_morphology=self.params.get('apply_morphology', True),
                merge_gap_px=self.params.get('merge_gap_px', 0),
                spatial_fill=self.params.get('spatial_fill', False),
                mask_shadows=self.params.get('mask_shadows', True),
            )

            self.progress.emit("Вычисление водных индексов...")
            results = self.water_detector.detect_water(self.loaded_data)

            if results:
                self.finished.emit(results)
            else:
                self.error.emit("Не удалось выполнить анализ")

        except Exception as e:
            self.error.emit(str(e))
