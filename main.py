import sys
import json
import os
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QRadioButton, 
                             QPushButton, QSlider, QCheckBox, QLineEdit, 
                             QSystemTrayIcon, QMenu, QGroupBox, QButtonGroup)
from PyQt6.QtCore import Qt, QTimer, QUrl, QTime
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

RADIO_STATIONS = {
    "Українське Радіо": {"high": "https://radio.nrcu.gov.ua:8443/ur1-mp3", "low": "https://radio.nrcu.gov.ua:8443/ur1-mp3-l"},
    "Радіо Промінь": {"high": "https://radio.nrcu.gov.ua:8443/ur2-mp3", "low": "https://radio.nrcu.gov.ua:8443/ur2-mp3-l"},
    "Радіо Культура": {"high": "https://radio.nrcu.gov.ua:8443/ur3-mp3", "low": "https://radio.nrcu.gov.ua:8443/ur3-mp3-l"},
    "Хіт FM": {"high": "https://online.hitfm.ua/HitFM"},
    "Люкс ФМ": {"high": "https://icecast.luxnet.ua/lux-fm"},
    "Радіо Максимум": {"high": "https://icecast.luxnet.ua/maximum"}
}

def load_config():
    defaults = {
        'theme': 'dark',
        'station': 'Українське Радіо',
        'quality': 'high',
        'volume': 70,
        'schedule_enabled': False,
        'schedule_days': [0, 1, 2, 3, 4, 5, 6],
        'schedule_start': '08:00',
        'schedule_end': '18:00'
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

class UkrRadioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Українське Радіо Онлайн")
        self.setFixedSize(500, 520)
        self.setWindowIcon(create_icon())
        
        self.config = load_config()
        self.current_theme = self.config.get('theme', 'dark')
        
        # Audio Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(self.config.get('volume', 70) / 100.0)
        self.is_playing = False
        
        self.init_ui()
        self.apply_theme()
        self.setup_tray()
        
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
        self.title_lbl = QLabel("УкрРадіо Онлайн 📻")
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
        
        self.station_cb = QComboBox()
        self.station_cb.addItems(list(RADIO_STATIONS.keys()))
        self.station_cb.setCurrentText(self.config.get('station', 'Українське Радіо'))
        self.station_cb.currentTextChanged.connect(self.on_station_change)
        player_layout.addWidget(self.station_cb)
        
        lbl_quality = QLabel("Якість:")
        lbl_quality.setProperty("class", "bold_label")
        player_layout.addWidget(lbl_quality)
        
        quality_layout = QHBoxLayout()
        self.quality_group = QButtonGroup(self)
        self.rb_high = QRadioButton("Висока")
        self.rb_low = QRadioButton("Низька")
        self.quality_group.addButton(self.rb_high)
        self.quality_group.addButton(self.rb_low)
        quality_layout.addWidget(self.rb_high)
        quality_layout.addWidget(self.rb_low)
        quality_layout.addStretch()
        
        if self.config.get('quality', 'high') == 'low':
            self.rb_low.setChecked(True)
        else:
            self.rb_high.setChecked(True)
            
        self.quality_group.buttonClicked.connect(self.on_station_change)
        player_layout.addLayout(quality_layout)
        
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
        QRadioButton {{
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

    def toggle_theme(self):
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_theme()
        self.save_current_config()

    def on_station_change(self):
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
        quality = 'low' if self.rb_low.isChecked() else 'high'
        urls = RADIO_STATIONS.get(station)
        if not urls: return
        url = urls.get(quality) or urls.get('high')
        
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

    def save_current_config(self):
        days = [i for i, chk in enumerate(self.day_chks) if chk.isChecked()]
        quality = 'low' if self.rb_low.isChecked() else 'high'
        cfg = {
            'theme': self.current_theme,
            'station': self.station_cb.currentText(),
            'quality': quality,
            'volume': self.vol_slider.value(),
            'schedule_enabled': self.sched_chk.isChecked(),
            'schedule_days': days,
            'schedule_start': self.start_edit.text(),
            'schedule_end': self.end_edit.text()
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
        self.tray_icon.showMessage("УкрРадіо", "Програма згорнута у трей. Радіо продовжує працювати.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def quit_app(self):
        self.stop_radio()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = UkrRadioApp()
    window.show()
    sys.exit(app.exec())
