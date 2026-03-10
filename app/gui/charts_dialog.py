from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from app.gui.charts import build_charts_figure


class ChartsDialog(QDialog):
    def __init__(self, results: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Статистика — графики')
        self.setMinimumSize(860, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        canvas = FigureCanvasQTAgg(build_charts_figure(results))
        layout.addWidget(canvas, 1)

        btn = QPushButton('Закрыть')
        btn.setFixedHeight(28)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
