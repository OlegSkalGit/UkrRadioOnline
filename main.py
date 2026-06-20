import sys
import os

# Force native Windows Media Foundation backend for Qt6 Multimedia to save size (eliminates FFmpeg DLLs)
os.environ['QT_MEDIA_BACKEND'] = 'windows'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalSocket

from ui.main_window import UkrRadioApp

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Перевірка на Single Instance
    socket = QLocalSocket()
    socket.connectToServer("UkrRadioOnline_IPC")
    if socket.waitForConnected(500):
        # Якщо вже запущено, відправляємо сигнал і виходимо
        sys.exit(0)
        
    window = UkrRadioApp()
    if not window.config.get('autominimize', False):
        window.show()
        
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
