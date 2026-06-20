import os
import re
import urllib.request
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import clean_mountpoint_name

class PlaylistFetcher(QThread):
    playlistsLoaded = pyqtSignal(dict)
    
    def run(self):
        new_stations = {}
        
        # Завантажуємо спочатку з https://radio.ukr.radio/
        try:
            req = urllib.request.Request('https://radio.ukr.radio/status.xsl', headers={'User-Agent':'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            content = response.read().decode('utf-8', errors='ignore')
            
            blocks = content.split('<div class="newscontent">')
            for block in blocks[1:]:
                mp_match = re.search(r'<h3>Mount Point\s+([^<]+)</h3>', block)
                if not mp_match:
                    continue
                mountpoint = mp_match.group(1).strip()
                
                if mountpoint.endswith('.xspf') or mountpoint.endswith('.m3u'):
                    continue
                    
                stream_url = f"https://radio.ukr.radio{mountpoint}"
                station_name, quality = clean_mountpoint_name(mountpoint)
                
                if station_name not in new_stations:
                    new_stations[station_name] = []
                
                new_stations[station_name].append({"name": f"[Суспільне] {quality}", "url": stream_url})
        except Exception:
            pass

        try:
            req = urllib.request.Request('https://iptv.org.ua/iptv/radio.m3u', headers={'User-Agent':'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=10)
            content = response.read().decode('utf-8', errors='ignore').splitlines()
            current_name = None
            for line in content:
                line = line.strip()
                if line.startswith("#EXTINF"):
                    parts = line.split(',')
                    if len(parts) > 1:
                        current_name = parts[-1].strip()
                elif line.startswith("http") and current_name:
                    if current_name not in new_stations:
                        new_stations[current_name] = []
                    new_stations[current_name].append({"name": f"[IPTV] Джерело {len(new_stations[current_name]) + 1}", "url": line})
                    current_name = None
        except Exception:
            pass
            
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
                    parts = link.split('/')
                    name = parts[-2] if len(parts) > 2 else f"Джерело {idx+1}"
                    new_stations["Opencartbot Збірка"].append({"name": f"[OCB] {name}", "url": link})
        except Exception:
            pass
            
        self.playlistsLoaded.emit(new_stations)


class RecordThread(QThread):
    def __init__(self, url, filepath):
        super().__init__()
        self.url = url
        self.filepath = filepath
        self.running = True

    def run(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                with open(self.filepath, 'wb') as f:
                    while self.running:
                        chunk = response.read(4096)
                        if not chunk:
                            break
                        f.write(chunk)
        except Exception as e:
            print(f"Recording error: {e}")

    def stop(self):
        self.running = False

class MetadataFetcher(QThread):
    metadataFetched = pyqtSignal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.running = True
        
    def run(self):
        while self.running:
            req = urllib.request.Request(self.url, headers={'Icy-MetaData': '1', 'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    metaint = int(response.headers.get('icy-metaint', 0))
                    if metaint == 0:
                        self.msleep(5000)
                        continue
                    
                    while self.running:
                        # Read and discard audio data
                        discarded = 0
                        while discarded < metaint and self.running:
                            chunk_size = min(4096, metaint - discarded)
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            discarded += len(chunk)
                            
                        if discarded < metaint or not self.running:
                            break
                            
                        # Read metadata length
                        length_byte = response.read(1)
                        if not length_byte:
                            break
                            
                        length = ord(length_byte) * 16
                        if length > 0:
                            meta_chunk = response.read(length)
                            data = meta_chunk.decode('utf-8', errors='ignore')
                            match = re.search(r"StreamTitle='([^']*)';", data)
                            if match:
                                title = match.group(1).strip()
                                self.metadataFetched.emit(title)
            except Exception:
                pass
                
            if self.running:
                # If connection dropped or failed, wait before reconnecting
                for _ in range(50):
                    if not self.running: break
                    self.msleep(100)

    def stop(self):
        self.running = False
