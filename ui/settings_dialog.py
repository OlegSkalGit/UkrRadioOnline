from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QCheckBox, QPushButton, QComboBox, QRadioButton, QButtonGroup,
    QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QMediaDevices

class SettingsDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Налаштування")
        self.setMinimumSize(400, 300)
        self.config = current_config
        
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- 1. Програвання (Playback) ---
        playback_tab = QWidget()
        playback_layout = QVBoxLayout(playback_tab)
        
        self.autoplay_cb = QCheckBox("Автопрогравання")
        self.autoplay_cb.setChecked(self.config.get('autoplay', True))
        playback_layout.addWidget(self.autoplay_cb)
        
        self.autoswitch_cb = QCheckBox("Автоперемикання джерела при обриві")
        self.autoswitch_cb.setChecked(self.config.get('auto_switch', True))
        playback_layout.addWidget(self.autoswitch_cb)
        
        playback_layout.addStretch()
        self.tabs.addTab(playback_tab, "Програвання")
        
        # --- 2. Запуск (Launch) ---
        launch_tab = QWidget()
        launch_layout = QVBoxLayout(launch_tab)
        
        self.autostart_cb = QCheckBox("Автозапуск з Windows")
        self.autostart_cb.setChecked(self.config.get('autostart', False))
        launch_layout.addWidget(self.autostart_cb)
        
        self.autominimize_cb = QCheckBox("Автозгортання при запуску")
        self.autominimize_cb.setChecked(self.config.get('autominimize', False))
        launch_layout.addWidget(self.autominimize_cb)
        
        self.minimize_to_tray_cb = QCheckBox("Згортати в трей при закритті/згортанні")
        self.minimize_to_tray_cb.setChecked(self.config.get('minimize_to_tray', True))
        launch_layout.addWidget(self.minimize_to_tray_cb)
        
        launch_layout.addStretch()
        self.tabs.addTab(launch_tab, "Запуск")
        
        # --- 3. Сповіщення (Notifications) ---
        notif_tab = QWidget()
        notif_layout = QVBoxLayout(notif_tab)
        
        notifs = self.config.get('notifications', {})
        self.notif_cbs = {}
        for key, text in [
            ('background', "Згортання / фоновий режим"),
            ('playlists', "Оновлення плейлистів"),
            ('playback', "Статус відтворення"),
            ('network', "Обрив зв'язку"),
            ('record', "Статус запису"),
            ('open_folder', "Відкривати папку з записами після зупинки"),
            ('startup_autorecord', "Повідомлення про автозапис при старті")
        ]:
            cb = QCheckBox(text)
            cb.setChecked(notifs.get(key, True))
            notif_layout.addWidget(cb)
            self.notif_cbs[key] = cb
            
        notif_layout.addStretch()
        self.tabs.addTab(notif_tab, "Сповіщення")
        
        # --- 4. Запис (Recording) ---
        record_tab = QWidget()
        record_layout = QVBoxLayout(record_tab)
        
        self.autorecord_cb = QCheckBox("Автоматичний запис при старті нового мовлення")
        self.autorecord_cb.setChecked(self.config.get('auto_record', False))
        record_layout.addWidget(self.autorecord_cb)
        
        record_layout.addStretch()
        self.tabs.addTab(record_tab, "Запис")
        
        # --- 5. Звук (Audio) ---
        audio_tab = QWidget()
        audio_layout = QVBoxLayout(audio_tab)
        
        audio_layout.addWidget(QLabel("Вибір звукової карти:"))
        self.audio_cb = QComboBox()
        self.audio_cb.addItem("Системний за замовчуванням", "")
        
        saved_device = self.config.get('audio_device', '')
        for device in QMediaDevices.audioOutputs():
            desc = device.description()
            device_id = bytearray(device.id()).decode('utf-8', 'ignore')
            self.audio_cb.addItem(desc, device_id)
            if saved_device == device_id:
                self.audio_cb.setCurrentIndex(self.audio_cb.count() - 1)
                
        audio_layout.addWidget(self.audio_cb)
        audio_layout.addStretch()
        self.tabs.addTab(audio_tab, "Звук")
        
        # --- 6. Інтерфейс (Theme) ---
        theme_tab = QWidget()
        theme_layout = QVBoxLayout(theme_tab)
        
        self.theme_group = QButtonGroup(self)
        self.theme_light = QRadioButton("Світла тема")
        self.theme_dark = QRadioButton("Темна тема")
        
        self.theme_group.addButton(self.theme_light)
        self.theme_group.addButton(self.theme_dark)
        
        current_theme = self.config.get('theme', 'dark')
        if current_theme == 'light':
            self.theme_light.setChecked(True)
        else:
            self.theme_dark.setChecked(True)
            
        theme_layout.addWidget(self.theme_light)
        theme_layout.addWidget(self.theme_dark)
        theme_layout.addStretch()
        self.tabs.addTab(theme_tab, "Інтерфейс")
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Відміна")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_ok = QPushButton("Ок")
        self.btn_ok.setProperty("class", "primary_btn")
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_ok)
        
        main_layout.addLayout(btn_layout)
        
    def get_settings(self):
        new_config = {
            'autoplay': self.autoplay_cb.isChecked(),
            'auto_switch': self.autoswitch_cb.isChecked(),
            'autostart': self.autostart_cb.isChecked(),
            'autominimize': self.autominimize_cb.isChecked(),
            'minimize_to_tray': self.minimize_to_tray_cb.isChecked(),
            'auto_record': self.autorecord_cb.isChecked(),
            'audio_device': self.audio_cb.currentData(),
            'theme': 'light' if self.theme_light.isChecked() else 'dark',
            'notifications': {k: cb.isChecked() for k, cb in self.notif_cbs.items()}
        }
        return new_config
