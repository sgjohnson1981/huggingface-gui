import os
import requests
import tempfile
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QApplication
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

class ImageDownloadThread(QThread):
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            # We want to cache to a workspace directory as requested by the user rules
            # We will use huggingface-gui/.cache/popup_image.dat
            cache_dir = os.path.join(os.getcwd(), '.cache')
            os.makedirs(cache_dir, exist_ok=True)
            self.file_path = os.path.join(cache_dir, 'popup_image.dat')
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(self.url, headers=headers, stream=True, timeout=15)
            response.raise_for_status()
            
            with open(self.file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            self.finished_signal.emit(self.file_path)
        except Exception as e:
            self.error_signal.emit(str(e))

class ImagePopupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.setWindowFlags(self.windowFlags() | Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border: 1px solid #555555;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border: 1px solid #ef4444;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header with Close button
        header_layout = QHBoxLayout()
        header_layout.addStretch()
        self.close_button = QPushButton("X")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.on_close_clicked)
        header_layout.addWidget(self.close_button)
        layout.addLayout(header_layout)

        # Image view
        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(Qt.transparent)
        
        # Start immediately with loading UI directly in web view to avoid UI jumping and two separate widgets
        loading_html = '''
        <body style="margin: 0; display: flex; justify-content: center; align-items: center; background-color: #1a1a1a; color: white; height: 100vh; overflow: hidden; font-family: sans-serif;">
            <h3>Loading image...</h3>
        </body>
        '''
        self.web_view.setHtml(loading_html)
        
        # Scale dialog size 
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            max_w = int(geom.width() * 0.85)
            max_h = int(geom.height() * 0.85)
        else:
            max_w, max_h = 1000, 800
            
        self.resize(max_w, max_h)
        layout.addWidget(self.web_view)

    def load_image(self, url):
        self.download_thread = ImageDownloadThread(url)
        self.download_thread.finished_signal.connect(self.on_image_loaded)
        self.download_thread.error_signal.connect(self.on_image_error)
        self.download_thread.start()

    def on_image_loaded(self, file_path):
        # We tell the Chromium viewer to natively load the local generic file!
        # This completely bypasses Data URI size limits for huge benchmark images 
        # and completely avoids HTTP SSL NSS errors!
        self.web_view.load(QUrl.fromLocalFile(file_path))

    def on_image_error(self, error_msg):
        error_html = f'''
        <body style="margin: 0; display: flex; justify-content: center; align-items: center; background-color: #1a1a1a; color: #ef4444; height: 100vh; overflow: hidden; font-family: sans-serif; padding: 20px; text-align: center;">
            <h3>Error loading image: <br><br>{error_msg}</h3>
        </body>
        '''
        self.web_view.setHtml(error_html)

    def on_close_clicked(self):
        self.web_view.deleteLater()
        self.close()
