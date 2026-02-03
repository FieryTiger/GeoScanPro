"""
GeoScanPro - Детектирование водных объектов на снимках Landsat 9
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app.db import database


def check_dependencies():
    missing = []
    for pkg in ['numpy', 'cv2', 'rasterio', 'matplotlib', 'pandas', 'PIL', 'scipy', 'skimage']:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GeoScanPro")
    app.setOrganizationName("GeoScanPro")

    missing = check_dependencies()
    if missing:
        QMessageBox.critical(
            None, "Ошибка зависимостей",
            f"Не удалось импортировать библиотеки:\n{', '.join(missing)}\n\n"
            "pip install numpy opencv-python rasterio matplotlib pandas pillow scipy scikit-image"
        )
        sys.exit(1)

    # Создание необходимых директорий
    for d in ["resources", "exports", "temp_extracted"]:
        Path(d).mkdir(exist_ok=True)

    # Инициализация БД
    database.init_db()

    # Запуск главного окна
    from app.gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
