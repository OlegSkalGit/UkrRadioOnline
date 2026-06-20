import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QLineEdit, QDialogButtonBox, QMessageBox)
from PyQt6.QtCore import Qt

class ScheduleDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування розкладу")
        self.config = config
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Дні:"))
        self.day_chks = []
        days_lbl = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        saved_days = self.config.get('schedule_days', [0,1,2,3,4,5,6])
        for i, d in enumerate(days_lbl):
            chk = QCheckBox(d)
            chk.setChecked(i in saved_days)
            self.day_chks.append(chk)
            days_layout.addWidget(chk)
        layout.addLayout(days_layout)
        
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Час (З - По):"))
        self.start_edit = QLineEdit(self.config.get('schedule_start', '08:00'))
        self.start_edit.setFixedWidth(60)
        self.start_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.end_edit = QLineEdit(self.config.get('schedule_end', '18:00'))
        self.end_edit.setFixedWidth(60)
        self.end_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_layout.addWidget(self.start_edit)
        time_layout.addWidget(QLabel("-"))
        time_layout.addWidget(self.end_edit)
        time_layout.addStretch()
        layout.addLayout(time_layout)
        
        note_lbl = QLabel("Формат: ГГ:ХХ (наприклад, 08:00 - 18:00)")
        layout.addWidget(note_lbl)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self):
        days = [i for i, chk in enumerate(self.day_chks) if chk.isChecked()]
        return days, self.start_edit.text(), self.end_edit.text()

    def accept(self):
        days, start_t, end_t = self.get_data()
        try:
            t_start = datetime.datetime.strptime(start_t, "%H:%M").time()
            t_end = datetime.datetime.strptime(end_t, "%H:%M").time()
            if t_start == t_end:
                QMessageBox.warning(self, "Помилка розкладу", "Час початку та закінчення не можуть співпадати!")
                return
        except ValueError:
            QMessageBox.warning(self, "Помилка розкладу", "Некоректний формат часу! Використовуйте формат ГГ:ХХ (наприклад, 08:00).")
            return
        super().accept()
