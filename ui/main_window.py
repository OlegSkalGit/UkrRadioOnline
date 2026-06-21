import os
import sys
import datetime
import re
import winreg
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QSlider, QCheckBox, QLineEdit, 
                             QSystemTrayIcon, QMenu, QGroupBox, QFrame,
                             QMessageBox, QDialog, QTextBrowser, QFileDialog, QCompleter,
                             QToolButton, QWidgetAction, QSizePolicy, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent, pyqtSignal
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QMediaMetaData
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QActionGroup

from core.config import load_config, save_config, RADIO_STATIONS, THEMES, APP_DIR
from core.threads import PlaylistFetcher, RecordThread, MetadataFetcher
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

class StationButton(QPushButton):
    stationSelected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "station_btn")
        self.clicked.connect(self.show_popup)
        
        self.popup = QWidget(self, Qt.WindowType.Popup)
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Пошук станції...")
        self.search_input.textChanged.connect(self.filter_list)
        layout.addWidget(self.search_input)
        
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)
        
        self.items_data = []

    def populate(self, nat_list, fav_list, other_list, selected_station=None):
        self.list_widget.clear()
        self.items_data.clear()
        
        def add_item(text, data):
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.list_widget.addItem(item)
            self.items_data.append((item, text))
            
        for s in nat_list:
            add_item(s, s)
        for s in fav_list:
            add_item(f"⭐ {s}", s)
        for s in other_list:
            add_item(s, s)
            
    def filter_list(self, text):
        search_text = text.strip().lower()
        for item, name in self.items_data:
            item.setHidden(search_text not in name.lower())

    def on_item_clicked(self, item):
        station = item.data(Qt.ItemDataRole.UserRole)
        self.popup.hide()
        self.stationSelected.emit(station)
        
    def show_popup(self):
        window = self.window()
        if window:
            self.popup.setStyleSheet(window.styleSheet())
            
        pos = self.mapToGlobal(self.rect().bottomLeft())
        h = min(350, self.list_widget.count() * 25 + 40)
        if h < 100: h = 300
        self.popup.setGeometry(pos.x(), pos.y(), self.width(), h)
        self.search_input.clear()
        self.popup.show()
        self.search_input.setFocus()

class UkrRadioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Українське радіо (online)")
        self.config = load_config()
        
        self.setWindowIcon(create_icon())
        
        self.current_theme = self.config.get('theme', 'dark')
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(self.config.get('volume', 70) / 100.0)
        
        saved_device = self.config.get('audio_device', '')
        if saved_device:
            for device in QMediaDevices.audioOutputs():
                if bytearray(device.id()).decode('utf-8', 'ignore') == saved_device:
                    self.audio_output.setDevice(device)
                    break
        self.is_playing = False
        self.ignore_station_change = False
        self.record_thread = None
        self.meta_thread = None
        
        self.player.errorOccurred.connect(self.on_player_error)
        
        # Завантажуємо користувацькі станції перед ініціалізацією UI
        custom_stations = self.config.setdefault('custom_m3u_stations', {})
        for name, sources in custom_stations.items():
            if name in RADIO_STATIONS:
                for src in sources:
                    if src['url'] not in [s['url'] for s in RADIO_STATIONS[name]]:
                        RADIO_STATIONS[name].append(src)
            else:
                RADIO_STATIONS[name] = sources
                
        # Також завантажуємо улюблені станції з конфігу (якщо вони збережені зі шляхами)
        favs = self.config.get('favorites', {})
        if isinstance(favs, dict):
            for name, sources in favs.items():
                if name in RADIO_STATIONS:
                    for src in sources:
                        if src['url'] not in [s['url'] for s in RADIO_STATIONS[name]]:
                            RADIO_STATIONS[name].append(src)
                else:
                    RADIO_STATIONS[name] = sources
                    
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
        if self.config.get('auto_record', False):
            self.show_notification("startup_autorecord", "Увага! Автозапис", "Функція автоматичного запису ефіру активна.", QSystemTrayIcon.MessageIcon.Warning, 3000)
            
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
        main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        
        # Header
        header_layout = QHBoxLayout()
        self.title_lbl = QLabel("Українське радіо (online) 📻")
        self.title_lbl.setProperty("class", "header_title")
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        
        self.vol_container = QFrame()
        self.vol_container.setProperty("class", "vol_container")
        vol_layout = QHBoxLayout(self.vol_container)
        vol_layout.setContentsMargins(10, 4, 10, 4)
        vol_layout.setSpacing(8)
        
        self.mute_btn = QPushButton("🔈")
        self.mute_btn.setProperty("class", "mute_btn")
        self.mute_btn.clicked.connect(self.toggle_mute)
        self.mute_btn.setToolTip("Вимкнути/увімкнути звук")
        self.mute_btn.setFixedSize(24, 24)
        vol_layout.addWidget(self.mute_btn)
        
        self.is_muted = False
        self.saved_volume = self.config.get('volume', 70)
        
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.config.get('volume', 70))
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.valueChanged.connect(self.on_volume_change)
        vol_layout.addWidget(self.vol_slider)
        vol_layout.addWidget(QLabel("🔊"))
        
        header_layout.addWidget(self.vol_container)
        main_layout.addLayout(header_layout)
        
        # Player Card
        self.player_card = QGroupBox()
        self.player_card.setProperty("class", "card")
        player_layout = QVBoxLayout(self.player_card)
        player_layout.setSpacing(10)
        
        # Station Layout
        station_layout = QHBoxLayout()
        
        self.fav_btn = QPushButton("☆")
        self.fav_btn.setProperty("class", "icon_btn")
        self.fav_btn.clicked.connect(self.toggle_favorite)
        station_layout.addWidget(self.fav_btn)
        
        self.station_btn = StationButton()
        self.station_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.station_btn.stationSelected.connect(self.select_station)
        station_layout.addWidget(self.station_btn, 2)
        
        self.source_cb = QComboBox()
        self.source_cb.currentIndexChanged.connect(self.on_source_change)
        station_layout.addWidget(self.source_cb, 1)
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("play_btn")
        self.play_btn.setProperty("class", "primary_btn")
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setFixedSize(32, 32)
        station_layout.addWidget(self.play_btn)
        
        self.record_main_btn = QPushButton("●")
        self.record_main_btn.setProperty("class", "record_btn_circle")
        self.record_main_btn.clicked.connect(self.toggle_record_from_main)
        self.record_main_btn.setFixedSize(32, 32)
        self.record_main_btn.setToolTip("Почати запис")
        station_layout.addWidget(self.record_main_btn)
        
        player_layout.addLayout(station_layout)
        
        self.metadata_lbl = QLabel("Дані відсутні.")
        self.metadata_lbl.setProperty("class", "metadata_label")
        self.metadata_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metadata_lbl.setWordWrap(True)
        player_layout.addWidget(self.metadata_lbl)
        
        saved_station = self.config.get('station', 'Радіо Промінь')
        self._current_station = saved_station
        self.populate_stations(saved_station)
        
        self.populate_sources()
        
        saved_idx = self.config.get('source_index', 0)
        if saved_idx < self.source_cb.count():
            self.source_cb.setCurrentIndex(saved_idx)
            
        # Volume controls were moved to header
        
        main_layout.addWidget(self.player_card)

    def create_menu(self):
        menubar = self.menuBar()
        
        # Налаштування
        settings_action = QAction("Налаштування", self)
        settings_action.triggered.connect(self.open_settings_dialog)
        menubar.addAction(settings_action)
        
        # Довідка
        help_action = QAction("Довідка", self)
        help_action.triggered.connect(self.show_help)
        menubar.addAction(help_action)
        
        # Вихід
        exit_action = QAction("Вихід", self)
        exit_action.triggered.connect(self.quit_app)
        menubar.addAction(exit_action)
        
        # Keep a hidden action to maintain compatibility with existing methods
        self.record_action = QAction("Запис", self, checkable=True)
        self.record_action.setChecked(False)
        self.record_action.toggled.connect(self.on_record_toggled)

    def open_settings_dialog(self):
        from ui.settings_window import SettingsDialog
        dialog = SettingsDialog(self, self.config)
        dialog.setStyleSheet(self.styleSheet())
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config, autostart = dialog.get_updated_config()
            self.config.update(new_config)
            
            # Autostart
            set_autostart(autostart)
            
            # Theme
            if self.config['theme'] != self.current_theme:
                self.current_theme = self.config['theme']
                self.apply_theme()
            
            # Audio device
            device_id = self.config.get('audio_device', '')
            if not device_id:
                self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
            else:
                for device in QMediaDevices.audioOutputs():
                    if bytearray(device.id()).decode('utf-8', 'ignore') == device_id:
                        self.audio_output.setDevice(device)
                        break
            
            self.save_current_config()
            self.check_schedule()

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

    def load_m3u_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Оберіть m3u файли", "", "M3U Playlists (*.m3u *.m3u8)")
        if not files:
            return
            
        added_count = 0
        custom_stations = self.config.setdefault('custom_m3u_stations', {})
        
        for file in files:
            try:
                # Protection: check file size (<5MB)
                if os.path.getsize(file) > 5 * 1024 * 1024:
                    continue
                    
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().splitlines()
                    
                current_name = None
                for line in content:
                    line = line.strip()
                    if line.startswith("#EXTINF"):
                        parts = line.split(',')
                        if len(parts) > 1:
                            current_name = parts[-1].strip()
                    elif line.startswith("http"):
                        # Ensure we have a valid station name
                        if not current_name:
                            current_name = os.path.basename(file).split('.')[0]
                            
                        # Add to config custom_stations
                        if current_name not in custom_stations:
                            custom_stations[current_name] = []
                            
                        # Avoid duplicates
                        if line not in [s['url'] for s in custom_stations[current_name]]:
                            custom_stations[current_name].append({"name": f"[Користувацька] Джерело {len(custom_stations[current_name]) + 1}", "url": line})
                            
                        # Also add to RADIO_STATIONS live
                        if current_name not in RADIO_STATIONS:
                            RADIO_STATIONS[current_name] = []
                            added_count += 1
                        
                        if line not in [s['url'] for s in RADIO_STATIONS[current_name]]:
                            RADIO_STATIONS[current_name].append({"name": f"[Користувацька] Джерело {len(RADIO_STATIONS[current_name]) + 1}", "url": line})
                            
                        current_name = None
            except Exception as e:
                print(f"Помилка читання {file}: {e}")
                
        if added_count > 0 or files:
            self.save_current_config()
            current_station = self.get_current_station()
            self.populate_stations(current_station)
            
            # Також оновлюємо source_cb якщо змінилась поточна станція
            current_source_idx = self.source_cb.currentIndex()
            self.populate_sources()
            if current_source_idx < self.source_cb.count():
                self.source_cb.setCurrentIndex(current_source_idx)
                
            self.show_notification("playlists", "Плейлисти завантажено", f"Успішно оброблено {len(files)} файлів.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def show_help(self):
        try:
            readme_path = os.path.join(APP_DIR, 'README.md')
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            content = "Файл README.md не знайдено."
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Довідка")
        saved_width = self.config.get('help_dialog_width', 600)
        saved_height = self.config.get('help_dialog_height', 450)
        dialog.resize(saved_width, saved_height)
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
        
        self.config['help_dialog_width'] = dialog.width()
        self.config['help_dialog_height'] = dialog.height()
        self.save_current_config()

    def apply_theme(self):
        theme_file = f"dark_theme.qss" if self.current_theme == 'dark' else "light_theme.qss"
        theme_path = os.path.join(APP_DIR, "assets", theme_file)
        
        try:
            with open(theme_path, 'r', encoding='utf-8') as f:
                qss = f.read()
            self.setStyleSheet(qss)
        except Exception as e:
            print(f"Помилка завантаження теми: {e}")
        
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
        if hasattr(self, '_current_station'):
            return self._current_station
        return self.config.get('station', 'Радіо Промінь')

    def populate_stations(self, station_to_select=None):
        national = ["Радіо Промінь", "Українське Радіо", "Радіо Культура", "Радіо Україна (Всесвітня служба)", "Радіоточка"]
        favorites = self.config.get('favorites', {})
        all_stations = list(RADIO_STATIONS.keys())
        
        nat_list = [s for s in national if s in all_stations]
        fav_list = sorted([s for s in favorites.keys() if s in all_stations and s not in nat_list])
        other_list = sorted([s for s in all_stations if s not in nat_list and s not in fav_list])
        
        self.station_btn.populate(nat_list, fav_list, other_list, station_to_select)
        if station_to_select:
            self._current_station = station_to_select
            favorites = self.config.get('favorites', {})
            prefix = "⭐ " if station_to_select in favorites else ""
            self.station_btn.setText(f"{prefix}{station_to_select}")
        self.update_favorite_btn()

    def select_station(self, station):
        self._current_station = station
        favorites = self.config.get('favorites', {})
        prefix = "⭐ " if station in favorites else ""
        self.station_btn.setText(f"{prefix}{station}")
        self.on_station_change()

    def update_favorite_btn(self):
        station = self.get_current_station()
        favorites = self.config.get('favorites', {})
        if isinstance(favorites, list):
            is_fav = station in favorites
        else:
            is_fav = station in favorites
            
        national = ["Радіо Промінь", "Українське Радіо", "Радіо Культура", "Радіо Україна (Всесвітня служба)", "Радіоточка"]
        
        if is_fav or station in national:
            self.fav_btn.setText("★")
            self.fav_btn.setStyleSheet("color: #f9e2af;") # Жовтий колір для зірочки
        else:
            self.fav_btn.setText("☆")
            self.fav_btn.setStyleSheet("")

    def toggle_favorite(self):
        station = self.get_current_station()
        national = ["Радіо Промінь", "Українське Радіо", "Радіо Культура", "Радіо Україна (Всесвітня служба)", "Радіоточка"]
        if station in national:
            return # Національні станції завжди в улюблених
            
        if 'favorites' not in self.config:
            self.config['favorites'] = {}
        elif isinstance(self.config['favorites'], list):
            new_favs = {}
            for s in self.config['favorites']:
                if s in RADIO_STATIONS:
                    new_favs[s] = RADIO_STATIONS[s]
            self.config['favorites'] = new_favs
            
        favorites = self.config['favorites']
        
        if station in favorites:
            del favorites[station]
        else:
            if station in RADIO_STATIONS:
                favorites[station] = RADIO_STATIONS[station]
            
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

    def toggle_mute(self):
        if self.is_muted:
            self.is_muted = False
            self.vol_slider.setValue(self.saved_volume)
            self.mute_btn.setText("🔈")
            if hasattr(self, 'tray_mute_action'):
                self.tray_mute_action.setText("Вимкнути звук")
        else:
            self.saved_volume = self.vol_slider.value()
            self.is_muted = True
            self.vol_slider.setValue(0)
            self.mute_btn.setText("🔇")
            if hasattr(self, 'tray_mute_action'):
                self.tray_mute_action.setText("Увімкнути звук")

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
        
        if self.meta_thread:
            self.meta_thread.stop()
            self.meta_thread.wait()
            self.meta_thread = None
            
        self.meta_thread = MetadataFetcher(url)
        self.meta_thread.metadataFetched.connect(self.on_icy_metadata)
        self.meta_thread.start()
        
        self.play_btn.setText("■")
        self.play_btn.setProperty("class", "error_btn")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)
        
        if hasattr(self, 'tray_play_action'):
            self.tray_play_action.setText("Зупинити")
            self.tray_play_action.setIcon(QIcon("icons/stop.png"))
        
        if self.config.get('auto_record', False) and not self.record_action.isChecked():
            self.record_action.setChecked(True)
        elif self.record_action.isChecked():
            self.start_recording()

    def stop_radio(self, user_initiated=False):
        if self.record_thread:
            self.stop_recording(show_folder=user_initiated)
            
        if self.meta_thread:
            self.meta_thread.stop()
            self.meta_thread.wait()
            self.meta_thread = None
            
        self.player.stop()
        self.is_playing = False
        
        self.metadata_lbl.setText("Дані відсутні.")
        
        self.play_btn.setText("▶")
        self.play_btn.setProperty("class", "primary_btn")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)
        
        if hasattr(self, 'tray_play_action'):
            self.tray_play_action.setText("Грати")
            self.tray_play_action.setIcon(QIcon())

    def on_icy_metadata(self, title):
        if not self.is_playing:
            return
            
        old_title = getattr(self, 'current_metadata_title', None)
        self.current_metadata_title = title if title else ""
            
        if title:
            self.metadata_lbl.setText(f"🎵 {title}")
        else:
            self.metadata_lbl.setText("Дані відсутні.")
            
        if self.record_thread and self.record_thread.isRunning():
            if old_title != self.current_metadata_title:
                old_filepath = self.record_thread.filepath
                self.record_thread.stop()
                self.record_thread.wait()
                self.record_thread = None
                
                # Delete the old file if it's very small (e.g. < 50KB) to avoid clutter
                try:
                    if os.path.exists(old_filepath) and os.path.getsize(old_filepath) < 50000:
                        os.remove(old_filepath)
                except Exception:
                    pass
                    
                self.start_recording()



    def on_player_error(self, error, error_string):
        if not self.is_playing:
            return
            
        print(f"Player Error: {error} - {error_string}")
        
        station = self.get_current_station()
        sources = RADIO_STATIONS.get(station, [])
        current_idx = self.source_cb.currentIndex()
        if self.config.get('auto_switch', True) and len(sources) > 1:
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
        # This was an action toggle callback, but we apply autostart in dialog
        pass
        self.save_current_config()

    def on_schedule_toggled(self, checked):
        self.save_current_config()
        if checked:
            self.open_schedule_dialog()

    def save_current_config(self):
        cfg = self.config.copy()
        cfg.update({
            'theme': self.current_theme,
            'station': self.get_current_station(),
            'source_index': self.source_cb.currentIndex(),
            'volume': self.vol_slider.value(),
            'favorites': self.config.get('favorites', [])
        })
        save_config(cfg)
        self.config = cfg

    def toggle_record_from_main(self):
        is_rec = self.record_thread and self.record_thread.isRunning()
        self.on_record_toggled(not is_rec)

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
        safe_station_name = re.sub(r'[\\/*?:"<>|]', "", station).strip()
        
        meta_title = getattr(self, 'current_metadata_title', "")
        if meta_title:
            safe_meta = re.sub(r'[\\/*?:"<>|]', "", meta_title).strip()
            # Обмежуємо довжину метаданих у назві, щоб уникнути помилок файлової системи (макс 255 символів для всього шляху)
            if len(safe_meta) > 100:
                safe_meta = safe_meta[:100] + "..."
            filename = f"{time_str}_{safe_station_name} - {safe_meta}.mp3"
        else:
            filename = f"{time_str}_{safe_station_name}.mp3"
            
        filepath = os.path.join(date_dir, filename)
        
        self.record_thread = RecordThread(url, filepath)
        self.record_thread.start()
        
        self.record_main_btn.setText("●")
        self.record_main_btn.setProperty("class", "record_btn_circle active")
        self.record_main_btn.style().unpolish(self.record_main_btn)
        self.record_main_btn.style().polish(self.record_main_btn)
        self.record_main_btn.setToolTip("Зупинити запис")
        
        self.show_notification("record", "Запис розпочато", f"Записуємо станцію '{station}' у файл:\n{filename}", QSystemTrayIcon.MessageIcon.Information, 1500)

    def stop_recording(self, show_folder=False):
        if self.record_thread:
            self.record_thread.stop()
            self.record_thread.wait()
            self.record_thread = None
            
            self.record_main_btn.setText("●")
            self.record_main_btn.setProperty("class", "record_btn_circle")
            self.record_main_btn.style().unpolish(self.record_main_btn)
            self.record_main_btn.style().polish(self.record_main_btn)
            self.record_main_btn.setToolTip("Почати запис")
            
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
        
        self.tray_play_action = QAction("Зупинити" if self.is_playing else "Грати", self)
        if self.is_playing:
            self.tray_play_action.setIcon(QIcon("icons/stop.png"))
        self.tray_play_action.triggered.connect(self.toggle_play)
        tray_menu.addAction(self.tray_play_action)
        
        self.tray_mute_action = QAction("Увімкнути звук" if getattr(self, 'is_muted', False) else "Вимкнути звук", self)
        self.tray_mute_action.triggered.connect(self.toggle_mute)
        tray_menu.addAction(self.tray_mute_action)
        
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
        save_config(self.config)
        
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
