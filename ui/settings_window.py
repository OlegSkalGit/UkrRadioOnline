from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                             QWidget, QCheckBox, QPushButton, QLabel, 
                             QComboBox, QDialogButtonBox)
from PyQt6.QtMultimedia import QMediaDevices
from PyQt6.QtCore import Qt
import copy
from ui.main_window import check_autostart

class SettingsDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle("Налаштування")
        self.setMinimumWidth(450)
        self.config = copy.deepcopy(config)
        self.parent_window = parent
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # 1. Програвання
        play_tab = QWidget()
        play_layout = QVBoxLayout(play_tab)
        
        self.autoplay_chk = QCheckBox("Автопрогравання")
        self.autoplay_chk.setChecked(self.config.get('autoplay', True))
        play_layout.addWidget(self.autoplay_chk)
        
        self.autoswitch_chk = QCheckBox("Автоперемикання джерела при обриві")
        self.autoswitch_chk.setChecked(self.config.get('auto_switch', True))
        play_layout.addWidget(self.autoswitch_chk)
        
        # Звукова карта
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("Звукова карта:"))
        self.audio_cb = QComboBox()
        self.audio_cb.addItem("Системна за замовчуванням", "")
        saved_device = self.config.get('audio_device', '')
        
        for device in QMediaDevices.audioOutputs():
            desc = device.description()
            dev_id = bytearray(device.id()).decode('utf-8', 'ignore')
            self.audio_cb.addItem(desc, dev_id)
            if saved_device == dev_id:
                self.audio_cb.setCurrentIndex(self.audio_cb.count() - 1)
        
        audio_layout.addWidget(self.audio_cb)
        play_layout.addLayout(audio_layout)
        
        # Розклад
        sched_layout = QHBoxLayout()
        self.sched_chk = QCheckBox("Увімкнути розклад (автозапуск/зупинка)")
        self.sched_chk.setChecked(self.config.get('schedule_enabled', False))
        sched_layout.addWidget(self.sched_chk)
        
        self.sched_btn = QPushButton("Налаштувати розклад")
        self.sched_btn.clicked.connect(self.open_schedule_dialog)
        sched_layout.addWidget(self.sched_btn)
        play_layout.addLayout(sched_layout)
        
        play_layout.addStretch()
        self.tabs.addTab(play_tab, "Програвання")
        
        # 2. Запуск та Вікно
        launch_tab = QWidget()
        launch_layout = QVBoxLayout(launch_tab)
        
        self.autostart_chk = QCheckBox("Автозапуск з Windows")
        self.autostart_chk.setChecked(check_autostart())
        launch_layout.addWidget(self.autostart_chk)
        
        self.autominimize_chk = QCheckBox("Автозгортання при запуску")
        self.autominimize_chk.setChecked(self.config.get('autominimize', False))
        launch_layout.addWidget(self.autominimize_chk)
        
        self.mintotray_chk = QCheckBox("Згортати в трей при закритті/згортанні")
        self.mintotray_chk.setChecked(self.config.get('minimize_to_tray', True))
        launch_layout.addWidget(self.mintotray_chk)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Тема:"))
        self.theme_cb = QComboBox()
        self.theme_cb.addItem("Темна", "dark")
        self.theme_cb.addItem("Світла", "light")
        if self.config.get('theme', 'dark') == 'light':
            self.theme_cb.setCurrentIndex(1)
        theme_layout.addWidget(self.theme_cb)
        launch_layout.addLayout(theme_layout)
        
        launch_layout.addStretch()
        self.tabs.addTab(launch_tab, "Запуск та Вікно")
        
        # 3. Запис та Плейлисти
        record_tab = QWidget()
        record_layout = QVBoxLayout(record_tab)
        
        self.autorecord_chk = QCheckBox("Автоматичний запис при старті нового мовлення")
        self.autorecord_chk.setChecked(self.config.get('auto_record', False))
        record_layout.addWidget(self.autorecord_chk)
        
        self.record_btn = QPushButton()
        self.update_record_btn()
        self.record_btn.clicked.connect(self.toggle_record)
        record_layout.addWidget(self.record_btn)
        
        self.open_rec_btn = QPushButton("Відкрити папку з записами")
        self.open_rec_btn.clicked.connect(self.parent_window.open_records_folder)
        record_layout.addWidget(self.open_rec_btn)
        
        record_layout.addWidget(QLabel("Користувацькі плейлисти:"))
        self.load_m3u_btn = QPushButton("Завантажити плейлист (.m3u)")
        self.load_m3u_btn.clicked.connect(self.parent_window.load_m3u_dialog)
        record_layout.addWidget(self.load_m3u_btn)
        
        record_layout.addStretch()
        self.tabs.addTab(record_tab, "Запис та Плейлисти")
        
        # 4. Сповіщення
        notif_tab = QWidget()
        notif_layout = QVBoxLayout(notif_tab)
        
        notifs = self.config.get('notifications', {})
        self.notif_chks = {}
        for key, text in [
            ('background', "Згортання / фоновий режим"),
            ('playlists', "Оновлення плейлистів"),
            ('playback', "Статус відтворення"),
            ('network', "Обрив зв'язку"),
            ('record', "Статус запису"),
            ('open_folder', "Відкривати папку з записами після зупинки"),
            ('startup_autorecord', "Повідомлення про автозапис при старті")
        ]:
            chk = QCheckBox(text)
            chk.setChecked(notifs.get(key, True))
            notif_layout.addWidget(chk)
            self.notif_chks[key] = chk
            
        notif_layout.addStretch()
        self.tabs.addTab(notif_tab, "Сповіщення")
        
        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def open_schedule_dialog(self):
        from ui.schedule_dialog import ScheduleDialog
        dialog = ScheduleDialog(self, self.config)
        dialog.setStyleSheet(self.styleSheet())
        
        if dialog.exec():
            days, start_t, end_t = dialog.get_data()
            self.config['schedule_days'] = days
            self.config['schedule_start'] = start_t
            self.config['schedule_end'] = end_t
        else:
            self.sched_chk.setChecked(False)

    def update_record_btn(self):
        is_rec = self.parent_window.record_thread and self.parent_window.record_thread.isRunning()
        self.record_btn.setText("Зупинити запис" if is_rec else "Почати запис поточної станції")
        self.record_btn.setProperty("class", "error_btn" if is_rec else "")
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)

    def toggle_record(self):
        is_rec = self.parent_window.record_thread and self.parent_window.record_thread.isRunning()
        self.parent_window.on_record_toggled(not is_rec)
        self.update_record_btn()

    def get_updated_config(self):
        self.config['autoplay'] = self.autoplay_chk.isChecked()
        self.config['auto_switch'] = self.autoswitch_chk.isChecked()
        self.config['audio_device'] = self.audio_cb.currentData()
        self.config['schedule_enabled'] = self.sched_chk.isChecked()
        
        self.config['autominimize'] = self.autominimize_chk.isChecked()
        self.config['minimize_to_tray'] = self.mintotray_chk.isChecked()
        self.config['theme'] = self.theme_cb.currentData()
        
        self.config['auto_record'] = self.autorecord_chk.isChecked()
        
        if 'notifications' not in self.config:
            self.config['notifications'] = {}
        for key, chk in self.notif_chks.items():
            self.config['notifications'][key] = chk.isChecked()
            
        return self.config, self.autostart_chk.isChecked()
