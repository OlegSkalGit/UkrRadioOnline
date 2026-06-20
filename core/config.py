import os
import sys
import json
import re

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_DIR = get_app_dir()

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
        'error': '#f38ba8',
        'menu_bg': '#1e1e2e',
        'menu_fg': '#cdd6f4',
        'menu_sel': '#313244'
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
        'error': '#d32f2f',
        'menu_bg': '#ffffff',
        'menu_fg': '#1e1e2e',
        'menu_sel': '#e6e6ea'
    }
}

CONFIG_FILE = os.path.join(APP_DIR, "radio_config.json")

RADIO_STATIONS = {
    "Радіо Промінь": [
        {"name": "Основне (Висока якість)", "url": "https://radio.ukr.radio/ur2-mp3"},
        {"name": "Резервне (Низька якість)", "url": "https://radio.ukr.radio/ur2-mp3-m"}
    ],
    "Українське Радіо": [
        {"name": "Основне (Висока якість)", "url": "https://radio.ukr.radio/ur1-mp3"},
        {"name": "Резервне (Низька якість)", "url": "https://radio.ukr.radio/ur1-mp3-m"}
    ],
    "Радіо Культура": [
        {"name": "Основне (Висока якість)", "url": "https://radio.ukr.radio/ur3-mp3"},
        {"name": "Резервне (Низька якість)", "url": "https://radio.ukr.radio/ur3-mp3-m"}
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
        'auto_switch': True,
        'autoplay': True,
        'autominimize': False,
        'minimize_to_tray': True,
        'auto_record': False,
        'notifications': {
            'background': True,
            'playlists': True,
            'playback': True,
            'network': True,
            'record': True,
            'open_folder': True
        },
        'audio_device': '',
        'favorites': {}
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

def clean_mountpoint_name(mp):
    mp = mp.strip('/')
    
    regions = {
        "ck": "Черкаси",
        "cn": "Чернігів",
        "cr": "Кропивницький",
        "cv": "Чернівці",
        "dp": "Дніпро",
        "if": "Івано-Франківськ",
        "kh": "Харків",
        "km": "Хмельницький",
        "kr": "Краматорськ",
        "krr": "Кривий Ріг",
        "lv": "Львів",
        "mk": "Миколаїв",
        "od": "Одеса",
        "pl": "Полтава",
        "rv": "Рівне",
        "sm": "Суми",
        "te": "Тернопіль",
        "uz": "Ужгород",
        "vn": "Вінниця",
        "vo": "Волинь",
        "zt": "Житомир",
        "kyiv": "Київ",
    }
    
    bases = {
        "ur1": "Українське Радіо",
        "ur2": "Радіо Промінь",
        "ur3": "Радіо Культура",
        "ur4": "Радіо Україна (Всесвітня служба)",
        "ur5": "Радіоточка",
        "urkazka": "Радіо Казка",
        "urclassic": "Радіо Класик",
        "golosdonbasu": "Голос Донбасу",
        "tysafm": "Тиса FM",
        "rui": "Radio Ukraine International",
    }
    
    parts = mp.split('-')
    base_code = parts[0]
    
    base_name = bases.get(base_code, base_code.upper())
    
    region_name = ""
    quality = "Основне"
    
    for part in parts[1:]:
        if part in regions:
            region_name = f" ({regions[part]})"
        elif part == "mp3":
            pass
        elif part == "m":
            quality = "Резерв"
        elif part == "l" or part == "aacplus" or part == "aacp":
            quality = "Низька якість"
        elif part == "ulow":
            quality = "Наднизька якість"
            
    final_name = f"{base_name}{region_name}"
    return final_name, quality
