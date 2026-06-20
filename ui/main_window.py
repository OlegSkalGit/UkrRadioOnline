import os
import sys
import datetime
import re
import winreg
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QSlider, QCheckBox, QLineEdit, 
                             QSystemTrayIcon, QMenu, QGroupBox,
                             QMessageBox, QDialog, QTextBrowser)
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QMediaMetaData
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QActionGroup

from core.config import load_config, save_config, RADIO_STATIONS, THEMES, APP_DIR
from core.threads import PlaylistFetcher, RecordThread
from ui.schedule_dialog import ScheduleDialog

def create_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(137, 180, 250))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(10, 10, 44, 44)
    painter.setBrush(QColor(30, 30, 46))
    painter.drawEllipse(20, 20, 24, 24)
    painter.setBrush(QColor(137, 180, 250))
    painter.drawEllipse(28, 28, 8, 8)
    painter.end()
    return QIcon(pixmap)

def set_autostart(enable=True):
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    app_name = 'UkrRadioOnline'
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            if getattr(sys, 'frozen', False):
                cmd = f'"{sys.executable}"'
            else:
                exe_path = sys.executable
                script_path = os.path.abspath(os.path.join(APP_DIR, "main.py"))
                cmd = f'"{exe_path}" "{script_path}"'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception:
        pass

def check_autostart():
    key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
    app_name = 'UkrRadioOnline'
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, app_name)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
class UkrRadioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Українське радіо (online)")
        self.setMinimumSize(500, 320)
        self.resize(500, 320)
        self.setWindowIcon(create_icon())
        
        self.config = load_config()
        self.current_theme = self.config.get('theme', 'dark')
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(self.config.get('volume', 70) / 100.0)
        self.is_playing = False
        self.ignore_station_change = False
        self.record_thread = None
        
        self.player.errorOccurred.connect(self.on_player_error)
        self.player.metaDataChanged.connect(self.on_metadata_changed)
        
        self.init_ui()
        self.apply_theme()
        self.setup_tray()
        
        self.fetcher = PlaylistFetcher()
        self.fetcher.playlistsLoaded.connect(self.on_playlists_loaded)
        self.fetcher.start()
        
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_schedule)
        self.scheduler_timer.start(30000)
        
        self.server = QLocalServer(self)
        QLocalServer.removeServer("UkrRadioOnline_IPC")
        self.server.listen("UkrRadioOnline_IPC")
        self.server.newConnection.connect(self.on_new_instance_connection)
        
        self.midnight_timer = QTimer(self)
        self.midnight_timer.timeout.connect(self.check_midnight_split)
        self.midnight_timer.start(10000) # Кожні 10 секунд
        
        QTimer.singleShot(500, self.startup_autoplay)
        
    def startup_autoplay(self):
        if not self.config.get('autoplay', True):
            return
            
        if self.config.get('schedule_enabled', False):
            self.check_schedule()
        else:
            self.play_radio()
            
    def on_new_instance_connection(self):
        socket = self.server.nextPendingConnection()
        if socket:
            socket.deleteLater()
        self.show_and_activate_window()
        self.show_notification("background", "Українське радіо", "Програма вже працює у фоновому режимі!", QSystemTrayIcon.MessageIcon.Information, 1500)
        
    def init_ui(self):
        self.create_menu()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        self.title_lbl = QLabel("Українське радіо (online) 📻")
        self.title_lbl.setProperty("class", "header_title")
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        self.metadata_lbl = QLabel("")
        self.metadata_lbl.setProperty("class", "metadata_label")
        self.metadata_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metadata_lbl.setWordWrap(True)
        self.metadata_lbl.hide() # Приховуємо, поки немає метаданих
        main_layout.addWidget(self.metadata_lbl)
        
        # Player Card
        self.player_card = QGroupBox()
        self.player_card.setProperty("class", "card")
        player_layout = QVBoxLayout(self.player_card)
        player_layout.setSpacing(10)
        
        lbl_station = QLabel("Радіостанція:")
        lbl_station.setProperty("class", "bold_label")
        player_layout.addWidget(lbl_station)
        
        station_layout = QHBoxLayout()
        self.station_cb = QComboBox()
        self.station_cb.currentIndexChanged.connect(self.on_station_change)
        station_layout.addWidget(self.station_cb, 1)
        
        self.fav_btn = QPushButton("☆")
        self.fav_btn.setFixedWidth(35)
        self.fav_btn.setProperty("class", "icon_btn")
        self.fav_btn.clicked.connect(self.toggle_favorite)
        station_layout.addWidget(self.fav_btn)
        
        player_layout.addLayout(station_layout)
        
        saved_station = self.config.get('station', 'Радіо Промінь')
        self.populate_stations(saved_station)
        
        lbl_source = QLabel("Джерело потоку:")
        lbl_source.setProperty("class", "bold_label")
        player_layout.addWidget(lbl_source)
        
        self.source_cb = QComboBox()
        self.populate_sources()
        saved_idx = self.config.get('source_index', 0)
        if saved_idx < self.source_cb.count():
            self.source_cb.setCurrentIndex(saved_idx)
        self.source_cb.currentIndexChanged.connect(self.on_source_change)
        player_layout.addWidget(self.source_cb)
        
        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton("▶ Грати")
        self.play_btn.setProperty("class", "primary_btn")
        self.play_btn.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_btn)
        
        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("🔈"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.config.get('volume', 70))
        self.vol_slider.setFixedWidth(150)
        self.vol_slider.valueChanged.connect(self.on_volume_change)
        controls_layout.addWidget(self.vol_slider)
        controls_layout.addWidget(QLabel("🔊"))
        
        player_layout.addLayout(controls_layout)
        main_layout.addWidget(self.player_card)
        main_layout.addStretch()

    def create_menu(self):
        menubar = self.menuBar()
        
        # Перемикання тем
        self.theme_action = QAction("Темна тема" if self.current_theme == 'light' else "Світла тема", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        menubar.addAction(self.theme_action)
        
        # Налаштування
        settings_menu = menubar.addMenu("Налаштування")
        
        self.autoplay_action = QAction("Автопрогравання", self, checkable=True)
        self.autoplay_action.setChecked(self.config.get('autoplay', True))
        self.autoplay_action.triggered.connect(self.save_current_config)
        settings_menu.addAction(self.autoplay_action)
        
        self.autoswitch_action = QAction("Автоперемикання джерела при обриві", self, checkable=True)
        self.autoswitch_action.setChecked(self.config.get('auto_switch', True))
        self.autoswitch_action.triggered.connect(self.save_current_config)
        settings_menu.addAction(self.autoswitch_action)
        
        launch_menu = settings_menu.addMenu("Запуск програми")
        
        self.autostart_action = QAction("Автозапуск з Windows", self, checkable=True)
        self.autostart_action.setChecked(check_autostart())
        self.autostart_action.triggered.connect(self.on_autostart_change)
        launch_menu.addAction(self.autostart_action)
        
        self.autominimize_action = QAction("Автозгортання при запуску", self, checkable=True)
        self.autominimize_action.setChecked(self.config.get('autominimize', False))
        self.autominimize_action.triggered.connect(self.save_current_config)
        launch_menu.addAction(self.autominimize_action)
        
        self.minimize_to_tray_action = QAction("Згортати в трей при закритті/згортанні", self, checkable=True)
        self.minimize_to_tray_action.setChecked(self.config.get('minimize_to_tray', True))
        self.minimize_to_tray_action.triggered.connect(self.save_current_config)
        launch_menu.addAction(self.minimize_to_tray_action)
        
        record_menu = settings_menu.addMenu("Запис")
        
        self.record_action = QAction("Увімкнути запис поточної станції", self, checkable=True)
        self.record_action.setChecked(False)
        self.record_action.toggled.connect(self.on_record_toggled)
        record_menu.addAction(self.record_action)
        
        self.auto_record_action = QAction("Автоматичний запис при старті нового мовлення", self, checkable=True)
        self.auto_record_action.setChecked(self.config.get('auto_record', False))
        self.auto_record_action.triggered.connect(self.save_current_config)
        record_menu.addAction(self.auto_record_action)
        
        record_menu.addSeparator()
        self.open_records_action = QAction("Відкрити папку з записами", self)
        self.open_records_action.triggered.connect(self.open_records_folder)
        record_menu.addAction(self.open_records_action)
        
        self.audio_devices_menu = settings_menu.addMenu("Вибір звукової карти")
        self.audio_device_group = QActionGroup(self)
        self.populate_audio_devices()
        
        settings_menu.addSeparator()
        
        # Сповіщення
        notif_menu = settings_menu.addMenu("Сповіщення")
        
        notifs = self.config.get('notifications', {
            'background': True, 'playlists': True, 'playback': True, 'network': True, 'record': True, 'open_folder': True
        })
        
        self.notif_actions = {}
        for key, text in [
            ('background', "Згортання / фоновий режим"),
            ('playlists', "Оновлення плейлистів"),
            ('playback', "Статус відтворення"),
            ('network', "Обрив зв'язку"),
            ('record', "Статус запису"),
            ('open_folder', "Відкривати папку з записами після зупинки")
        ]:
            act = QAction(text, self, checkable=True)
            act.setChecked(notifs.get(key, True))
            act.triggered.connect(self.save_current_config)
            notif_menu.addAction(act)
            self.notif_actions[key] = act
        
        self.sched_enable_action = QAction("Увімкнути розклад (автозапуск/зупинка)", self, checkable=True)
        self.sched_enable_action.setChecked(self.config.get('schedule_enabled', False))
        self.sched_enable_action.toggled.connect(self.on_schedule_toggled)
        settings_menu.addAction(self.sched_enable_action)
        
        # Довідка
        help_action = QAction("Довідка", self)
        help_action.triggered.connect(self.show_help)
        menubar.addAction(help_action)
        
        # Вихід
        exit_action = QAction("Вихід", self)
        exit_action.triggered.connect(self.quit_app)
        menubar.addAction(exit_action)

    def populate_audio_devices(self):
        self.audio_devices_menu.clear()
        
        default_action = QAction("Системний за замовчуванням", self, checkable=True)
        default_action.setData("")
        self.audio_device_group.addAction(default_action)
        self.audio_devices_menu.addAction(default_action)
        
        saved_device = self.config.get('audio_device', '')
        has_matched = False
        
        for device in QMediaDevices.audioOutputs():
            desc = device.description()
            action = QAction(desc, self, checkable=True)
            action.setData(device.id())
            self.audio_device_group.addAction(action)
            self.audio_devices_menu.addAction(action)
            
            if saved_device and saved_device == bytearray(device.id()).decode('utf-8', 'ignore'):
                action.setChecked(True)
                self.audio_output.setDevice(device)
                has_matched = True
                
        if not has_matched:
            default_action.setChecked(True)
            self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
            
        self.audio_device_group.triggered.connect(self.on_audio_device_changed)

    def on_audio_device_changed(self, action):
        device_id = action.data()
        self.config['audio_device'] = bytearray(device_id).decode('utf-8', 'ignore') if device_id else ""
        
        if not device_id:
            self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
        else:
            for device in QMediaDevices.audioOutputs():
                if device.id() == device_id:
                    self.audio_output.setDevice(device)
                    break
        self.save_current_config()

    def open_schedule_dialog(self):
        dialog = ScheduleDialog(self, self.config)
        # Apply current theme to dialog
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec():
            days, start_t, end_t = dialog.get_data()
            self.config['schedule_days'] = days
            self.config['schedule_start'] = start_t
            self.config['schedule_end'] = end_t
            self.save_current_config()
            self.check_schedule()
        else:
            # Якщо користувач натиснув Cancel, знімаємо прапорець
            self.sched_enable_action.setChecked(False)
            self.save_current_config()
            self.check_schedule()

    def show_help(self):
        try:
            readme_path = os.path.join(APP_DIR, 'README.md')
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            content = "Файл README.md не знайдено."
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Довідка")
        dialog.resize(600, 450)
        dialog.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout(dialog)
        
        browser = QTextBrowser()
        browser.setMarkdown(content)
        layout.addWidget(browser)
        
        btn = QPushButton("Закрити")
        btn.setProperty("class", "primary_btn")
        btn.clicked.connect(dialog.accept)
        layout.addWidget(btn)
        
        dialog.exec()

    def apply_theme(self):
        c = THEMES[self.current_theme]
        qss = f"""
        QWidget {{
            background-color: {c['bg']};
            color: {c['text']};
            font-family: 'Segoe UI';
            font-size: 14px;
        }}
        QMenuBar {{
            background-color: {c['menu_bg']};
            color: {c['menu_fg']};
        }}
        QMenuBar::item:selected {{
            background-color: {c['menu_sel']};
        }}
        QMenu {{
            background-color: {c['menu_bg']};
            color: {c['menu_fg']};
            border: 1px solid {c['menu_sel']};
        }}
        QMenu::item:selected {{
            background-color: {c['menu_sel']};
        }}
        QGroupBox.card {{
            background-color: {c['card_bg']};
            border: none;
            border-radius: 8px;
            margin-top: 0px;
        }}
        QLabel.header_title {{
            font-size: 22px;
            font-weight: bold;
            color: {c['accent']};
            background-color: {c['bg']};
        }}
        QLabel.bold_label {{
            font-weight: bold;
            background-color: {c['card_bg']};
        }}
        QLabel {{
            background-color: transparent;
        }}
        QCheckBox {{
            background-color: transparent;
        }}
        QPushButton {{
            background-color: {c['entry_bg']};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            min-height: 30px;
        }}
        QPushButton:hover {{
            background-color: {c['bg']};
        }}
        QPushButton.primary_btn {{
            background-color: {c['accent']};
            color: {c['accent_text']};
            font-weight: bold;
            font-size: 16px;
        }}
        QPushButton.primary_btn:hover {{
            background-color: {c['accent_hover']};
        }}
        QPushButton.error_btn {{
            background-color: {c['error']};
            color: {c['accent_text']};
            font-weight: bold;
            font-size: 16px;
        }}
        QLabel.metadata_label {{
            font-size: 14px;
            font-style: italic;
            color: {c['subtext']};
            background-color: {c['bg']};
            margin-bottom: 5px;
        }}
        QComboBox {{
            background-color: {c['entry_bg']};
            border: 1px solid {c['bg']};
            border-radius: 4px;
            padding: 6px;
            min-height: 25px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c['card_bg']};
            selection-background-color: {c['accent']};
        }}
        QLineEdit {{
            background-color: {c['entry_bg']};
            border: none;
            border-radius: 4px;
            padding: 4px;
        }}
        QSlider::groove:horizontal {{
            background: {c['entry_bg']};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {c['accent']};
            width: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }}
        """
        self.setStyleSheet(qss)
        
        self.theme_action.setText("Темна тема" if self.current_theme == 'light' else "Світла тема")
        
        if self.is_playing:
            self.play_btn.setProperty("class", "error_btn")
            self.play_btn.style().unpolish(self.play_btn)
            self.play_btn.style().polish(self.play_btn)

    def populate_sources(self):
        self.ignore_station_change = True
        self.source_cb.clear()
        station = self.get_current_station()
        sources = RADIO_STATIONS.get(station, [])
        for src in sources:
            self.source_cb.addItem(src["name"])
        self.ignore_station_change = False

    def get_current_station(self):
        data = self.station_cb.currentData()
        return data if data else self.station_cb.currentText()

    def populate_stations(self, station_to_select=None):
        self.station_cb.blockSignals(True)
        self.station_cb.clear()
        
        national = ["Українське Радіо", "Радіо Промінь", "Радіо Культура", "Радіо Україна (Всесвітня служба)", "Радіоточка"]
        favorites = self.config.get('favorites', [])
        all_stations = list(RADIO_STATIONS.keys())
        
        nat_list = [s for s in national if s in all_stations]
        fav_list = sorted([s for s in favorites if s in all_stations and s not in nat_list])
        other_list = sorted([s for s in all_stations if s not in nat_list and s not in fav_list])
        
        idx = 0
        target_idx = 0
        
        for s in nat_list:
            self.station_cb.addItem(s, userData=s)
            if s == station_to_select: target_idx = idx
            idx += 1
            
        for s in fav_list:
            self.station_cb.addItem(f"⭐ {s}", userData=s)
            if s == station_to_select: target_idx = idx
            idx += 1
            
        for s in other_list:
            self.station_cb.addItem(s, userData=s)
            if s == station_to_select: target_idx = idx
            idx += 1
            
        self.station_cb.setCurrentIndex(target_idx)
        self.station_cb.blockSignals(False)
        self.update_favorite_btn()

    def update_favorite_btn(self):
        station = self.get_current_station()
        favorites = self.config.get('favorites', [])
        if station in favorites:
            self.fav_btn.setText("★")
            self.fav_btn.setStyleSheet("color: #f9e2af;") # Жовтий колір для зірочки
        else:
            self.fav_btn.setText("☆")
            self.fav_btn.setStyleSheet("")

    def toggle_favorite(self):
        station = self.get_current_station()
        if 'favorites' not in self.config:
            self.config['favorites'] = []
            
        if station in self.config['favorites']:
            self.config['favorites'].remove(station)
        else:
            self.config['favorites'].append(station)
            
        self.save_current_config()
        self.populate_stations(station_to_select=station)

    def on_playlists_loaded(self, new_stations):
        added_count = 0
        for name, sources in new_stations.items():
            if name in RADIO_STATIONS:
                for src in sources:
                    if src['url'] not in [s['url'] for s in RADIO_STATIONS[name]]:
                        RADIO_STATIONS[name].append(src)
            else:
                RADIO_STATIONS[name] = sources
                added_count += 1
                
        if added_count > 0:
            current_station = self.get_current_station()
            self.station_cb.blockSignals(True)
            self.populate_stations(current_station)
            
        current_source_idx = self.source_cb.currentIndex()
        self.populate_sources()
        if current_source_idx < self.source_cb.count():
            self.source_cb.setCurrentIndex(current_source_idx)
            
        if added_count > 0:
            self.show_notification("playlists", "Плейлисти оновлено", f"Успішно завантажено {added_count} нових інтернет-радіостанцій.", QSystemTrayIcon.MessageIcon.Information, 1500)

    def toggle_theme(self):
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_theme()
        self.save_current_config()

    def on_station_change(self):
        self.update_favorite_btn()
        self.populate_sources()
        self.save_current_config()
        if self.is_playing or self.config.get('autoplay', True):
            self.play_radio()

    def on_source_change(self):
        if self.ignore_station_change:
            return
        self.save_current_config()
        if self.is_playing or self.config.get('autoplay', True):
            self.play_radio()

    def on_volume_change(self, val):
        self.audio_output.setVolume(val / 100.0)
        self.save_current_config()

    def toggle_play(self):
        if self.is_playing:
            self.stop_radio(user_initiated=True)
        else:
            self.play_radio(show_warning=True)

    def play_radio(self, show_warning=False):
        if not self.is_in_schedule_range():
            if show_warning:
                QMessageBox.information(
                    self, 
                    "Обмеження розкладу", 
                    "Не вдалося запустити відтворення:\nЗараз час поза межами активного розкладу."
                )
            self.stop_radio()
            return
            
        if self.record_thread:
            self.stop_recording(show_folder=False)
            
        station = self.get_current_station()
        idx = self.source_cb.currentIndex()
        if idx < 0: return
        
        sources = RADIO_STATIONS.get(station, [])
        if idx >= len(sources): return
        
        url = sources[idx]["url"]
        self.player.setSource(QUrl(url))
        self.player.play()
        self.is_playing = True
        
        self.play_btn.setText("⏹ Зупинити")
        self.play_btn.setProperty("class", "error_btn")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)
        
        if self.auto_record_action.isChecked() and not self.record_action.isChecked():
            self.record_action.setChecked(True)
        elif self.record_action.isChecked():
            self.start_recording()

    def stop_radio(self, user_initiated=False):
        if self.record_thread:
            self.stop_recording(show_folder=user_initiated)
            
        self.player.stop()
        self.is_playing = False
        
        self.metadata_lbl.hide()
        self.metadata_lbl.setText("")
        
        self.play_btn.setText("▶ Грати")
        self.play_btn.setProperty("class", "primary_btn")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)

    def on_metadata_changed(self):
        if not self.is_playing:
            return
            
        metadata = self.player.metaData()
        if not metadata:
            self.metadata_lbl.hide()
            return
            
        title = metadata.value(QMediaMetaData.Key.Title)
        author = metadata.value(QMediaMetaData.Key.Author)
        contributing_artist = metadata.value(QMediaMetaData.Key.ContributingArtist)
        
        artist = author if author else contributing_artist
        
        text = ""
        if artist and title:
            text = f"🎵 {artist} - {title}"
        elif title:
            text = f"🎵 {title}"
        elif artist:
            text = f"🎵 {artist}"
            
        if text:
            self.metadata_lbl.setText(text)
            self.metadata_lbl.show()
        else:
            self.metadata_lbl.hide()

    def on_player_error(self, error, error_string):
        if not self.is_playing:
            return
            
        print(f"Player Error: {error} - {error_string}")
        
        station = self.get_current_station()
        sources = RADIO_STATIONS.get(station, [])
        current_idx = self.source_cb.currentIndex()
        
        if self.autoswitch_action.isChecked() and len(sources) > 1:
            next_idx = (current_idx + 1) % len(sources)
            self.show_notification("network", "Обрив зв'язку", f"Перемикаємось на '{sources[next_idx]['name']}' (через 5 сек)...", QSystemTrayIcon.MessageIcon.Warning, 1500)
            self.ignore_station_change = True
            self.source_cb.setCurrentIndex(next_idx)
            self.save_current_config()
            self.ignore_station_change = False
        else:
            self.show_notification("network", "Обрив зв'язку", "Очікуємо на відновлення з'єднання (повтор через 5 сек)...", QSystemTrayIcon.MessageIcon.Warning, 1500)
            
        QTimer.singleShot(5000, self.retry_play)

    def retry_play(self):
        if self.is_playing:
            self.play_radio()

    def on_autostart_change(self):
        set_autostart(self.autostart_action.isChecked())
        self.save_current_config()

    def on_schedule_toggled(self, checked):
        self.save_current_config()
        if checked:
            self.open_schedule_dialog()

    def save_current_config(self):
        cfg = {
            'theme': self.current_theme,
            'station': self.get_current_station(),
            'source_index': self.source_cb.currentIndex(),
            'volume': self.vol_slider.value(),
            'schedule_enabled': self.sched_enable_action.isChecked(),
            'schedule_days': self.config.get('schedule_days', [0,1,2,3,4,5,6]),
            'schedule_start': self.config.get('schedule_start', '08:00'),
            'schedule_end': self.config.get('schedule_end', '18:00'),
            'autostart': self.autostart_action.isChecked(),
            'autominimize': self.autominimize_action.isChecked(),
            'minimize_to_tray': self.minimize_to_tray_action.isChecked(),
            'auto_switch': self.autoswitch_action.isChecked(),
            'autoplay': self.autoplay_action.isChecked(),
            'auto_record': self.auto_record_action.isChecked(),
            'notifications': {k: a.isChecked() for k, a in self.notif_actions.items()},
            'audio_device': self.config.get('audio_device', '')
        }
        save_config(cfg)
        self.config = cfg

    def on_record_toggled(self, checked):
        if checked:
            if not self.is_playing:
                QMessageBox.warning(self, "Запис", "Для початку запису спочатку запустіть відтворення радіостанції!")
                self.record_action.blockSignals(True)
                self.record_action.setChecked(False)
                self.record_action.blockSignals(False)
                return
            self.start_recording()
        else:
            self.stop_recording(show_folder=True)

    def get_base_records_dir(self):
        base_record_dir = os.path.join(APP_DIR, "records")
        has_write_access = False
        try:
            os.makedirs(base_record_dir, exist_ok=True)
            test_file = os.path.join(base_record_dir, "test.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            has_write_access = True
        except Exception:
            has_write_access = False

        if not has_write_access:
            base_record_dir = os.path.join(os.path.expanduser("~"), "Music", "UkrRadioOnline_records")
        return base_record_dir

    def open_records_folder(self):
        base_dir = self.get_base_records_dir()
        os.makedirs(base_dir, exist_ok=True)
        os.startfile(base_dir)

    def start_recording(self):
        if self.record_thread and self.record_thread.isRunning():
            return
            
        station = self.get_current_station()
        idx = self.source_cb.currentIndex()
        if idx < 0:
            self.record_action.blockSignals(True)
            self.record_action.setChecked(False)
            self.record_action.blockSignals(False)
            return
            
        sources = RADIO_STATIONS.get(station, [])
        if idx >= len(sources):
            self.record_action.blockSignals(True)
            self.record_action.setChecked(False)
            self.record_action.blockSignals(False)
            return
            
        url = sources[idx]["url"]
        
        # Build file path
        now = datetime.datetime.now()
        date_str = now.strftime("%Y.%m.%d")
        
        base_record_dir = self.get_base_records_dir()
            
        self.current_recording_date = now.date()
        
        date_dir = os.path.join(base_record_dir, date_str)
        self.current_record_dir = date_dir
        
        time_str = now.strftime("%H.%M.%S")
        safe_station_name = re.sub(r'[\\/*?:"<>|]', "", station)
        filename = f"{time_str}_{safe_station_name}.mp3"
        filepath = os.path.join(date_dir, filename)
        
        self.record_thread = RecordThread(url, filepath)
        self.record_thread.start()
        
        self.show_notification("record", "Запис розпочато", f"Записуємо станцію '{station}' у файл:\n{filename}", QSystemTrayIcon.MessageIcon.Information, 1500)

    def stop_recording(self, show_folder=False):
        if self.record_thread:
            self.record_thread.stop()
            self.record_thread.wait()
            self.record_thread = None
            self.show_notification("record", "Запис зупинено", "Аудіофайл успішно збережено.", QSystemTrayIcon.MessageIcon.Information, 1500)
            
            if show_folder and self.config.get('notifications', {}).get('open_folder', True) and not self.isMinimized() and self.isVisible():
                if hasattr(self, 'current_record_dir') and os.path.exists(self.current_record_dir):
                    os.startfile(self.current_record_dir)
            
        self.record_action.blockSignals(True)
        self.record_action.setChecked(False)
        self.record_action.blockSignals(False)

    def check_midnight_split(self):
        if self.record_thread and self.record_thread.isRunning():
            now_date = datetime.datetime.now().date()
            if hasattr(self, 'current_recording_date') and self.current_recording_date < now_date:
                self.record_thread.stop()
                self.record_thread.wait()
                self.record_thread = None
                self.start_recording()

    def is_in_schedule_range(self):
        if not self.config.get('schedule_enabled', False):
            return True
            
        now = datetime.datetime.now()
        current_day = now.weekday()
        days = self.config.get('schedule_days', [])
        
        start_str = self.config.get('schedule_start', '08:00')
        end_str = self.config.get('schedule_end', '18:00')
        
        try:
            t_start = datetime.datetime.strptime(start_str, "%H:%M").time()
            t_end = datetime.datetime.strptime(end_str, "%H:%M").time()
            current_time = now.time()
            
            # 1. Check if we match today's schedule
            if current_day in days:
                if t_start < t_end:
                    if t_start <= current_time <= t_end:
                        return True
                elif t_start > t_end:
                    if current_time >= t_start:
                        return True
            
            # 2. Check if we match yesterday's overnight schedule
            yesterday = (current_day - 1) % 7
            if yesterday in days:
                if t_start > t_end:
                    if current_time <= t_end:
                        return True
        except ValueError:
            pass
            
        return False

    def check_schedule(self):
        if not self.config.get('schedule_enabled', False):
            return
            
        is_in_schedule = self.is_in_schedule_range()
                
        if is_in_schedule and not self.is_playing:
            self.play_radio()
        elif not is_in_schedule and self.is_playing:
            self.stop_radio()

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(create_icon())
        
        tray_menu = QMenu()
        
        show_action = QAction("Показати", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        play_action = QAction("Грати", self)
        play_action.triggered.connect(lambda: self.play_radio(show_warning=True))
        tray_menu.addAction(play_action)
        
        stop_action = QAction(QIcon("icons/stop.png"), "Зупинити", self)
        stop_action.triggered.connect(lambda: self.stop_radio(user_initiated=True))
        tray_menu.addAction(stop_action)
        
        quit_action = QAction("Вихід", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.messageClicked.connect(self.show_and_activate_window)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
                self.hide()
            else:
                self.show_and_activate_window()

    def show_and_activate_window(self):
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self.config.get('minimize_to_tray', True):
                self.hide()
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.config.get('minimize_to_tray', True):
            event.ignore()
            self.hide()
            if self.tray_icon.isVisible():
                self.show_notification("background", "Українське радіо", "Програма працює у фоновому режимі.", QSystemTrayIcon.MessageIcon.Information, 1500)
        else:
            self.quit_app()

    def show_notification(self, type_key, title, msg, icon, time=1500):
        notifs = self.config.get('notifications', {})
        if notifs.get(type_key, True):
            if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                self.tray_icon.showMessage(title, msg, icon, time)

    def quit_app(self):
        self.stop_radio(user_initiated=True)
        QApplication.quit()
