import sys
import json
import os
import datetime
import winreg
import urllib.request
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QRadioButton, 
                             QPushButton, QSlider, QCheckBox, QLineEdit, 
                             QSystemTrayIcon, QMenu, QGroupBox, QButtonGroup)
from PyQt6.QtCore import Qt, QTimer, QUrl, QTime, QThread, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction

THEMES = {
    'dark': {
        'bg': '#1e1e2e',
        'card_bg': '#252538',
        'text': '#cdd6f4',
        'subtext': '#a6adc8',
        'entry_bg': '#313244',
        'accent': '#89b4fa',
        'accent_hover': '#b4befe',
        'accent_text': '#11111b',
        'error': '#f38ba8'
    },
    'light': {
        'bg': '#f4f4f7',
        'card_bg': '#ffffff',
        'text': '#1e1e2e',
        'subtext': '#585b70',
        'entry_bg': '#e6e6ea',
        'accent': '#3f51b5',
        'accent_hover': '#5c6bc0',
        'accent_text': '#ffffff',
        'error': '#d32f2f'
    }
}

CONFIG_FILE = "radio_config.json"

# Basic list of stations
RADIO_STATIONS = {
    "Радіо Промінь": [
        {"name": "Основне (Висока якість)", "url": "https://radio.nrcu.gov.ua:8443/ur2-mp3"},
        {"name": "Резервне (Низька якість)", "url": "https://radio.nrcu.gov.ua:8443/ur2-mp3-l"}
    ],
    "Українське Радіо": [
        {"name": "Основне (Висока якість)", "url": "https://radio.nrcu.gov.ua:8443/ur1-mp3"},
        {"name": "Резервне (Низька якість)", "url": "https://radio.nrcu.gov.ua:8443/ur1-mp3-l"}
    ],
    "Радіо Культура": [
        {"name": "Основне (Висока якість)", "url": "https://radio.nrcu.gov.ua:8443/ur3-mp3"},
        {"name": "Резервне (Низька якість)", "url": "https://radio.nrcu.gov.ua:8443/ur3-mp3-l"}
    ],
    "Радіо Україна (Всесвітня служба)": [
        {"name": "Основне", "url": "https://radio.ukr.radio/ur4-mp3"}
    ],
    "Радіоточка": [
        {"name": "Основне", "url": "https://radio.ukr.radio/ur5-mp3"}
    ],
    "Хіт FM": [
        {"name": "Основне", "url": "https://online.hitfm.ua/HitFM"}
    ],
    "Радіо ROKS": [
        {"name": "Основне", "url": "https://online.radioroks.ua/RadioROKS"}
    ],
    "KISS FM": [
        {"name": "Основне", "url": "https://online.kissfm.ua/KissFM"}
    ],
    "Радіо Релакс": [
        {"name": "Основне", "url": "https://online.radiorelax.ua/RadioRelax"}
    ],
    "Мелодія FM": [
        {"name": "Основне", "url": "https://online.melodiafm.ua/MelodiaFM"}
    ],
    "Радіо Байрактар": [
        {"name": "Основне", "url": "https://online.radiobayraktar.ua/RadioBayraktar"}
    ],
    "Люкс ФМ": [
        {"name": "Основне", "url": "https://icecast.luxnet.ua/lux-fm"}
    ],
    "Максимум ФМ": [
        {"name": "Основне", "url": "https://icecast.luxnet.ua/maximum"}
    ],
    "Ностальжі": [
        {"name": "Основне", "url": "https://icecast.luxnet.ua/nostalgie"}
    ],
    "Шлягер FM": [
        {"name": "Основне", "url": "https://stream.radiocorp.com.ua/shlager"}
    ],
    "Радіо Шансон": [
        {"name": "Основне", "url": "https://stream.radiocorp.com.ua/shanson"}
    ],
    "DJ FM": [
        {"name": "Основне", "url": "https://stream.radiocorp.com.ua/djfm"}
    ],
    "Power FM": [
        {"name": "Основне", "url": "https://stream.radiocorp.com.ua/powerfm"}
    ]
}

def load_config():
    defaults = {
        'theme': 'dark',
        'station': 'Радіо Промінь',
        'source_index': 0,
        'volume': 70,
        'schedule_enabled': False,
        'schedule_days': [0, 1, 2, 3, 4, 5, 6],
        'schedule_start': '08:00',
        'schedule_end': '18:00',
        'autostart': False,
        'auto_switch': True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                defaults.update(config)
        except Exception:
            pass
    return defaults

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

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
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "UkrRadioOnline"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            exe_path = sys.executable
            script_path = os.path.abspath(__file__)
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
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "UkrRadioOnline"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, app_name)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False

class PlaylistFetcher(QThread):
    playlistsLoaded = pyqtSignal(dict)
    
    def run(self):
        new_stations = {}
        
        # 1. iptv.org.ua/iptv/radio.m3u
        try:
            req = urllib.request.Request('https://iptv.org.ua/iptv/radio.m3u', headers={'User-Agent':'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            content = response.read().decode('utf-8', errors='ignore').splitlines()
            
            current_name = None
            for line in content:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    # Extract name after last comma
                    parts = line.split(',')
                    if len(parts) > 1:
                        current_name = parts[-1].strip()
                elif line.startswith("http") and current_name:
                    if current_name not in new_stations:
                        new_stations[current_name] = []
                    new_stations[current_name].append({"name": f"[IPTV] Джерело {len(new_stations[current_name]) + 1}", "url": line})
                    current_name = None
        except Exception as e:
            print("Error loading iptv.org.ua playlist:", e)
            
        # 2. opencartbot page m3u8 links
        try:
            req = urllib.request.Request('https://tech.opencartbot.com/instructions/ua-online-radio-playlist', headers={'User-Agent':'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            content = response.read().decode('utf-8', errors='ignore')
            links = re.findall(r'href=\"([^\"]+)\"', content)
            m3u_links = [l for l in links if '.m3u' in l]
            
            if m3u_links:
                if "Opencartbot Збірка" not in new_stations:
                    new_stations["Opencartbot Збірка"] = []
                for idx, link in enumerate(set(m3u_links)):
                    # try to extract a name from URL
                    parts = link.split('/')
                    name = parts[-2] if len(parts) > 2 else f"Джерело {idx+1}"
                    new_stations["Opencartbot Збірка"].append({"name": f"[OCB] {name}", "url": link})
        except Exception as e:
            print("Error loading opencartbot playlist:", e)
            
        self.playlistsLoaded.emit(new_stations)


class UkrRadioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Українське радіо (online)")
        self.setFixedSize(500, 560)
        self.setWindowIcon(create_icon())
        
        self.config = load_config()
        self.current_theme = self.config.get('theme', 'dark')
        
        # Audio Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(self.config.get('volume', 70) / 100.0)
        self.is_playing = False
        self.ignore_station_change = False
        
        self.player.errorOccurred.connect(self.on_player_error)
        
        self.init_ui()
        self.apply_theme()
        self.setup_tray()
        
        # Start fetching dynamic playlists
        self.fetcher = PlaylistFetcher()
        self.fetcher.playlistsLoaded.connect(self.on_playlists_loaded)
        self.fetcher.start()
        
        # Scheduler Timer
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_schedule)
        self.scheduler_timer.start(30000) # Check every 30 seconds
        
    def init_ui(self):
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
        self.theme_btn = QPushButton("Тема")
        self.theme_btn.setProperty("class", "theme_btn")
        self.theme_btn.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.theme_btn)
        main_layout.addLayout(header_layout)
        
        # Player Card
        self.player_card = QGroupBox()
        self.player_card.setProperty("class", "card")
        player_layout = QVBoxLayout(self.player_card)
        player_layout.setSpacing(10)
        
        lbl_station = QLabel("Радіостанція:")
        lbl_station.setProperty("class", "bold_label")
        player_layout.addWidget(lbl_station)
        
        # Station ComboBox
        self.station_cb = QComboBox()
        self.station_cb.addItems(list(RADIO_STATIONS.keys()))
        
        saved_station = self.config.get('station', 'Радіо Промінь')
        if saved_station in RADIO_STATIONS:
            self.station_cb.setCurrentText(saved_station)
            
        self.station_cb.currentTextChanged.connect(self.on_station_change)
        player_layout.addWidget(self.station_cb)
        
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
        
        self.auto_switch_chk = QCheckBox("Автоперемикання джерела при обриві")
        self.auto_switch_chk.setProperty("class", "bold_label")
        self.auto_switch_chk.setChecked(self.config.get('auto_switch', True))
        self.auto_switch_chk.stateChanged.connect(self.save_current_config)
        player_layout.addWidget(self.auto_switch_chk)
        
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
        
        # Schedule Card
        self.schedule_card = QGroupBox()
        self.schedule_card.setProperty("class", "card")
        schedule_layout = QVBoxLayout(self.schedule_card)
        schedule_layout.setSpacing(10)
        
        self.sched_chk = QCheckBox("Увімкнути розклад (авто-запуск/зупинка)")
        self.sched_chk.setProperty("class", "bold_label")
        self.sched_chk.setChecked(self.config.get('schedule_enabled', False))
        self.sched_chk.stateChanged.connect(self.save_current_config)
        schedule_layout.addWidget(self.sched_chk)
        
        self.autostart_chk = QCheckBox("Автозапуск програми разом із Windows")
        self.autostart_chk.setProperty("class", "bold_label")
        self.autostart_chk.setChecked(check_autostart())
        self.autostart_chk.stateChanged.connect(self.on_autostart_change)
        schedule_layout.addWidget(self.autostart_chk)
        
        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Дні:"))
        self.day_chks = []
        days_lbl = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
        saved_days = self.config.get('schedule_days', [0,1,2,3,4,5,6])
        for i, d in enumerate(days_lbl):
            chk = QCheckBox(d)
            chk.setChecked(i in saved_days)
            chk.stateChanged.connect(self.save_current_config)
            self.day_chks.append(chk)
            days_layout.addWidget(chk)
        days_layout.addStretch()
        schedule_layout.addLayout(days_layout)
        
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Час (З - По):"))
        self.start_edit = QLineEdit(self.config.get('schedule_start', '08:00'))
        self.start_edit.setFixedWidth(60)
        self.start_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.end_edit = QLineEdit(self.config.get('schedule_end', '18:00'))
        self.end_edit.setFixedWidth(60)
        self.end_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.start_edit.textChanged.connect(self.save_current_config)
        self.end_edit.textChanged.connect(self.save_current_config)
        time_layout.addWidget(self.start_edit)
        time_layout.addWidget(QLabel("-"))
        time_layout.addWidget(self.end_edit)
        time_layout.addStretch()
        schedule_layout.addLayout(time_layout)
        
        note_lbl = QLabel("Формат: ГГ:ХХ (наприклад, 08:00 - 18:00)")
        note_lbl.setProperty("class", "subtext")
        schedule_layout.addWidget(note_lbl)
        
        main_layout.addWidget(self.schedule_card)
        main_layout.addStretch()

    def apply_theme(self):
        c = THEMES[self.current_theme]
        qss = f"""
        QWidget {{
            background-color: {c['bg']};
            color: {c['text']};
            font-family: 'Segoe UI';
            font-size: 14px;
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
        QLabel.subtext {{
            font-size: 12px;
            color: {c['subtext']};
            background-color: {c['card_bg']};
        }}
        QLabel {{
            background-color: {c['card_bg']};
        }}
        QCheckBox {{
            background-color: {c['card_bg']};
        }}
        QPushButton {{
            background-color: {c['entry_bg']};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
        }}
        QPushButton:hover {{
            background-color: {c['bg']};
        }}
        QPushButton.theme_btn {{
            background-color: {c['bg']};
            padding: 6px 12px;
        }}
        QPushButton.theme_btn:hover {{
            background-color: {c['card_bg']};
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
        QComboBox {{
            background-color: {c['entry_bg']};
            border: 1px solid {c['bg']};
            border-radius: 4px;
            padding: 6px;
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
        
        if self.is_playing:
            self.play_btn.setProperty("class", "error_btn")
            self.play_btn.style().unpolish(self.play_btn)
            self.play_btn.style().polish(self.play_btn)

    def populate_sources(self):
        self.ignore_station_change = True
        self.source_cb.clear()
        station = self.station_cb.currentText()
        sources = RADIO_STATIONS.get(station, [])
        for src in sources:
            self.source_cb.addItem(src["name"])
        self.ignore_station_change = False

    def on_playlists_loaded(self, new_stations):
        # Merge new stations into the global dictionary
        added_count = 0
        for name, sources in new_stations.items():
            if name in RADIO_STATIONS:
                # Append new sources to existing station
                for src in sources:
                    if src['url'] not in [s['url'] for s in RADIO_STATIONS[name]]:
                        RADIO_STATIONS[name].append(src)
            else:
                # Add entirely new station
                RADIO_STATIONS[name] = sources
                added_count += 1
                
        # Update the station combo box with new items (without replacing current selection)
        if added_count > 0:
            current_station = self.station_cb.currentText()
            self.station_cb.blockSignals(True)
            self.station_cb.clear()
            self.station_cb.addItems(list(RADIO_STATIONS.keys()))
            self.station_cb.setCurrentText(current_station)
            self.station_cb.blockSignals(False)
            
        # Repopulate current sources just in case the current station received new sources
        current_source_idx = self.source_cb.currentIndex()
        self.populate_sources()
        if current_source_idx < self.source_cb.count():
            self.source_cb.setCurrentIndex(current_source_idx)
            
        if added_count > 0:
            self.tray_icon.showMessage("Плейлисти оновлено", f"Успішно завантажено {added_count} нових інтернет-радіостанцій.", QSystemTrayIcon.MessageIcon.Information, 3000)

    def toggle_theme(self):
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_theme()
        self.save_current_config()

    def on_station_change(self):
        self.populate_sources()
        self.save_current_config()
        if self.is_playing:
            self.play_radio()

    def on_source_change(self):
        if self.ignore_station_change:
            return
        self.save_current_config()
        if self.is_playing:
            self.play_radio()

    def on_volume_change(self, val):
        self.audio_output.setVolume(val / 100.0)
        self.save_current_config()

    def toggle_play(self):
        if self.is_playing:
            self.stop_radio()
        else:
            self.play_radio()

    def play_radio(self):
        station = self.station_cb.currentText()
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

    def stop_radio(self):
        self.player.stop()
        self.is_playing = False
        
        self.play_btn.setText("▶ Грати")
        self.play_btn.setProperty("class", "primary_btn")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)

    def on_player_error(self, error, error_string):
        if not self.is_playing:
            return
            
        print(f"Player Error: {error} - {error_string}")
        
        station = self.station_cb.currentText()
        sources = RADIO_STATIONS.get(station, [])
        current_idx = self.source_cb.currentIndex()
        
        if self.auto_switch_chk.isChecked() and len(sources) > 1:
            next_idx = (current_idx + 1) % len(sources)
            self.tray_icon.showMessage("Обрив зв'язку", f"Перемикаємось на '{sources[next_idx]['name']}' (через 5 сек)...", QSystemTrayIcon.MessageIcon.Warning, 2000)
            self.ignore_station_change = True
            self.source_cb.setCurrentIndex(next_idx)
            self.save_current_config()
            self.ignore_station_change = False
        else:
            self.tray_icon.showMessage("Обрив зв'язку", "Очікуємо на відновлення з'єднання (повтор через 5 сек)...", QSystemTrayIcon.MessageIcon.Warning, 2000)
            
        # Try to reconnect after 5 seconds to prevent infinite instant-fail loops
        QTimer.singleShot(5000, self.retry_play)

    def retry_play(self):
        if self.is_playing:
            self.play_radio()

    def on_autostart_change(self, state):
        set_autostart(self.autostart_chk.isChecked())
        self.save_current_config()

    def save_current_config(self):
        days = [i for i, chk in enumerate(self.day_chks) if chk.isChecked()]
        cfg = {
            'theme': self.current_theme,
            'station': self.station_cb.currentText(),
            'source_index': self.source_cb.currentIndex(),
            'volume': self.vol_slider.value(),
            'schedule_enabled': self.sched_chk.isChecked(),
            'schedule_days': days,
            'schedule_start': self.start_edit.text(),
            'schedule_end': self.end_edit.text(),
            'autostart': self.autostart_chk.isChecked(),
            'auto_switch': self.auto_switch_chk.isChecked()
        }
        save_config(cfg)

    def check_schedule(self):
        if not self.sched_chk.isChecked():
            return
            
        now = datetime.datetime.now()
        current_day = now.weekday()
        days = [i for i, chk in enumerate(self.day_chks) if chk.isChecked()]
        
        if current_day in days:
            start_str = self.start_edit.text().strip()
            end_str = self.end_edit.text().strip()
            
            try:
                t_start = datetime.datetime.strptime(start_str, "%H:%M").time()
                t_end = datetime.datetime.strptime(end_str, "%H:%M").time()
                current_time = now.time()
                
                is_in_schedule = False
                if t_start < t_end:
                    is_in_schedule = t_start <= current_time <= t_end
                else:
                    is_in_schedule = current_time >= t_start or current_time <= t_end
                    
                if is_in_schedule and not self.is_playing:
                    self.play_radio()
                elif not is_in_schedule and self.is_playing:
                    self.stop_radio()
            except ValueError:
                pass

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(create_icon())
        
        tray_menu = QMenu()
        
        show_action = QAction("Показати", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        play_action = QAction("Грати", self)
        play_action.triggered.connect(self.play_radio)
        tray_menu.addAction(play_action)
        
        stop_action = QAction("Зупинити", self)
        stop_action.triggered.connect(self.stop_radio)
        tray_menu.addAction(stop_action)
        
        quit_action = QAction("Вихід", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("Українське радіо (online)", "Програма згорнута у трей. Радіо продовжує працювати.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def quit_app(self):
        self.stop_radio()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = UkrRadioApp()
    window.show()
    sys.exit(app.exec())
