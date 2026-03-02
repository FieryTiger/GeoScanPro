from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QSizePolicy
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont


class DetectionTab(QWidget):
    analysis_requested = Signal(dict)  # эмитит параметры

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Параметры детектирования водных объектов")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # --- Пороги индексов ---
        indices_group = QGroupBox("Пороговые значения водных индексов")
        indices_layout = QVBoxLayout(indices_group)

        self.threshold_spins = {}
        indices = [
            ("NDWI",     "Normalized Difference Water Index",            0.3,  -1.0, 1.0),
            ("MNDWI",    "Modified NDWI",                                0.2,  -1.0, 1.0),
            ("AWEI_nsh", "Automated Water Extraction Index (no shadows)", 0.0, -10.0, 10.0),
            ("LSWI",     "Land Surface Water Index",                     0.3,  -1.0, 1.0),
        ]

        for name, desc, default, min_val, max_val in indices:
            row = QHBoxLayout()
            name_label = QLabel(f"<b>{name}</b>")
            name_label.setFixedWidth(80)
            desc_label = QLabel(desc)
            desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setSingleStep(0.05)
            spin.setDecimals(2)
            spin.setValue(default)
            spin.setFixedWidth(90)
            self.threshold_spins[name] = spin
            row.addWidget(name_label)
            row.addWidget(desc_label)
            row.addWidget(spin)
            indices_layout.addLayout(row)

        layout.addWidget(indices_group)

        # --- Постобработка ---
        post_group = QGroupBox("Постобработка")
        post_layout = QVBoxLayout(post_group)

        self.chk_morphology = QCheckBox("Применить морфологические операции (closing/opening)")
        self.chk_morphology.setChecked(True)
        post_layout.addWidget(self.chk_morphology)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Минимальный размер объекта (пикселей):"))
        self.spin_min_size = QSpinBox()
        self.spin_min_size.setRange(1, 10000)
        self.spin_min_size.setValue(100)
        self.spin_min_size.setFixedWidth(100)
        size_row.addWidget(self.spin_min_size)
        size_row.addStretch()
        post_layout.addLayout(size_row)

        layout.addWidget(post_group)

        layout.addStretch()

        self.btn_analyze = QPushButton("Запустить анализ")
        self.btn_analyze.setMinimumHeight(44)
        self.btn_analyze.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self._emit_params)
        layout.addWidget(self.btn_analyze)

    def set_ready(self, ready: bool):
        self.btn_analyze.setEnabled(ready)

    def get_params(self) -> dict:
        return {
            'thresholds': {name: spin.value() for name, spin in self.threshold_spins.items()},
            'min_object_size': self.spin_min_size.value(),
            'apply_morphology': self.chk_morphology.isChecked(),
        }

    def _emit_params(self):
        self.analysis_requested.emit(self.get_params())
