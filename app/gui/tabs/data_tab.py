import zipfile
import tarfile
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class DataTab(QWidget):
    files_loaded = Signal(list)  # список путей к .tif файлам

    def __init__(self, data_processor):
        super().__init__()
        self.data_processor = data_processor
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Загрузка спутниковых данных Landsat 9")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Drag & drop зона
        self.drop_frame = QFrame()
        self.drop_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.drop_frame.setMinimumHeight(160)
        self.drop_frame.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaaaaa;
                border-radius: 8px;
                background-color: #f9f9f9;
            }
        """)
        drop_layout = QVBoxLayout(self.drop_frame)
        drop_label = QLabel("Перетащите архив (.zip, .tar) с данными Landsat 9\nили воспользуйтесь кнопками ниже")
        drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_label.setFont(QFont("Arial", 12))
        drop_label.setStyleSheet("color: #666666; border: none;")
        drop_layout.addWidget(drop_label)
        layout.addWidget(self.drop_frame)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_files = QPushButton("Выбрать файлы .tif")
        self.btn_archive = QPushButton("Загрузить архив")
        for btn in (self.btn_files, self.btn_archive):
            btn.setMinimumHeight(36)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        self.btn_files.clicked.connect(self.load_files)
        self.btn_archive.clicked.connect(self.load_archive)

        # Информационная область
        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setPlaceholderText("Здесь появится информация о загруженных файлах...")
        self.info_box.setFont(QFont("Courier", 11))
        layout.addWidget(self.info_box)

    # --- Drag & Drop ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.zip', '.tar', '.gz')):
                self._process_archive(path)
                return
        QMessageBox.warning(self, "Неподдерживаемый файл", "Перетащите архив (.zip, .tar, .gz)")

    # --- Загрузка ---

    def load_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите файлы Landsat 9", "", "TIFF файлы (*.tif *.TIF)"
        )
        if files:
            self._load_and_emit(files)

    def load_archive(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите архив", "", "Архивы (*.zip *.tar *.gz)"
        )
        if path:
            self._process_archive(path)

    def _process_archive(self, archive_path):
        temp_dir = Path("temp_extracted")
        temp_dir.mkdir(exist_ok=True)
        try:
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as z:
                    z.extractall(temp_dir)
            else:
                with tarfile.open(archive_path, 'r') as t:
                    t.extractall(temp_dir)

            tif_files = [str(f) for f in temp_dir.rglob("*.tif")] + \
                        [str(f) for f in temp_dir.rglob("*.TIF")]
            if tif_files:
                self._load_and_emit(tif_files)
            else:
                QMessageBox.warning(self, "Файлы не найдены", "В архиве нет .tif файлов")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось извлечь архив:\n{e}")

    def _load_and_emit(self, file_paths):
        loaded = self.data_processor.load_landsat_data(file_paths)
        if loaded:
            self._show_info(loaded)
            self.files_loaded.emit(file_paths)
        else:
            QMessageBox.critical(self, "Ошибка загрузки", "Не удалось загрузить необходимые каналы Landsat 9")

    def _show_info(self, loaded_data):
        bands_info = {
            'SR_B2': 'Синий   (0.45–0.51 мкм)',
            'SR_B3': 'Зеленый (0.53–0.59 мкм)',
            'SR_B4': 'Красный (0.64–0.67 мкм)',
            'SR_B5': 'NIR     (0.85–0.88 мкм)',
            'SR_B6': 'SWIR1   (1.57–1.65 мкм)',
            'SR_B7': 'SWIR2   (2.11–2.29 мкм)',
            'QA_PIXEL': 'Качество пикселей',
        }
        lines = ["Загруженные каналы Landsat 9:\n"]
        for band, arr in loaded_data.items():
            if band in bands_info and hasattr(arr, 'shape'):
                lines.append(f"  {band:<12} {bands_info[band]:<28} {arr.shape[1]}x{arr.shape[0]} px")
        if 'meta' in loaded_data:
            meta = loaded_data['meta']
            lines.append(f"\nПроекция: {meta.get('crs', 'N/A')}")
        lines.append("\nГотов к анализу.")
        self.info_box.setPlainText("\n".join(lines))
