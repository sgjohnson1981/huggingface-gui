import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QApplication,
    QTextBrowser,
)
from PySide6.QtGui import QTextCharFormat, QColor, QTextDocument, QTextCursor


from .model_tree_widget import ModelTreeWidget
from .worker import Worker
from .huggingface_service import hf_service
import sys
import traceback
import requests
import re
from PySide6.QtCore import QUrl

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

class ModelWebEnginePage(QWebEnginePage):
    def __init__(self, parent=None, popup_callback=None):
        super().__init__(parent)
        self.popup_callback = popup_callback

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        url_str = url.toString() if hasattr(url, 'toString') else str(url)
        if _type == QWebEnginePage.NavigationTypeLinkClicked:
            if url_str.startswith("image-popup:"):
                if self.popup_callback:
                    self.popup_callback(url_str)
                return False
            else:
                import webbrowser
                webbrowser.open(url_str)
                return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)

class ModelDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_model_id = None
        self.relationship_worker = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # --- Header ---
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Select a model to see details")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.copy_button = QPushButton("Copy Model ID")
        self.copy_button.setVisible(False)
        self.copy_button.clicked.connect(self.copy_model_id)

        self.open_hub_button = QPushButton("Open on Hub")
        self.open_hub_button.setVisible(False)
        self.open_hub_button.clicked.connect(self.open_on_hub)

        self.download_button = QPushButton("Download Model")
        self.download_button.setVisible(False)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.copy_button)
        header_layout.addWidget(self.open_hub_button)
        header_layout.addWidget(self.download_button)
        # --- End Header ---

        self.layout.addLayout(header_layout)
        
        # Model Tree (initially hidden)
        self.tree_widget = ModelTreeWidget()
        self.tree_widget.setVisible(False)
        self.layout.addWidget(self.tree_widget)

        self.details_text = QWebEngineView()
        self.details_page = ModelWebEnginePage(self, popup_callback=self.handle_link_clicked)
        self.details_text.setPage(self.details_page)
        self.details_text.setStyleSheet("background-color: #1e1e1e;")
        
        self.layout.addWidget(self.details_text)

    def copy_model_id(self):
        if self.current_model_id:
            QApplication.clipboard().setText(self.current_model_id)

    def open_on_hub(self):
        if self.current_model_id:
            import webbrowser
            url = f"https://huggingface.co/{self.current_model_id}"
            webbrowser.open(url)

    def handle_link_clicked(self, url_str):
        if url_str.startswith("image-popup:"):
            img_url = url_str.split("image-popup:", 1)[1]
            from .image_popup_dialog import ImagePopupDialog
            from PySide6.QtCore import Qt
            self.image_popup = ImagePopupDialog(self)
            self.image_popup.setWindowModality(Qt.ApplicationModal)
            self.image_popup.load_image(img_url)
            self.image_popup.show()
        else:
            import webbrowser
            webbrowser.open(url_str)

    def set_model_details(self, model_info, model_readme, highlight_query=None):
        """
        Populates the panel with model details.
        """
        self.current_model_id = model_info.id
        self.title_label.setText(model_info.id)

        import re
        import markdown
        
        if model_readme:
            # Strip YAML frontmatter
            if model_readme.startswith("---"):
                model_readme = re.sub(r'^---\n.*?\n---\n?', '', model_readme, flags=re.DOTALL)
            
            # Convert python markdown to HTML, as QTextBrowser setMarkdown is buggy
            html_content = markdown.markdown(
                model_readme, 
                extensions=['fenced_code', 'tables', 'sane_lists']
            )
            
            image_urls = []
            # Rewrite img tags to use absolute URLs and wrap in anchor for the popup
            def rewrite_img(match):
                full_tag = match.group(0)
                src = match.group(1)
                new_src = src
                if not src.startswith(('http://', 'https://', 'data:')):
                    clean_src = src.lstrip('./').lstrip('/')
                    new_src = f"https://huggingface.co/{self.current_model_id}/resolve/main/{clean_src}"
                    full_tag = full_tag.replace(f'src="{src}"', f'src="{new_src}"').replace(f"src='{src}'", f"src='{new_src}'")
                
                image_urls.append(new_src)
                return f'<a href="image-popup:{new_src}">{full_tag}</a>'

            html_content = re.sub(r'<img\s+[^>]*?src=["\']([^"\']+)["\'][^>]*>', rewrite_img, html_content)
            
            # Add some basic CSS so HTML elements inherit the dark mode style properly
            # and format images/tables so they don't break the layout
            styled_html = f"""
            <style>
                body {{ background-color: #1e1e1e; color: #ffffff; font-family: sans-serif; padding: 10px; margin: 0; }}
                a {{ color: #3b82f6; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                code, pre {{ background-color: #2d2d2d; padding: 2px 4px; border-radius: 4px; }}
                pre {{ padding: 10px; overflow-x: auto; }}
                table {{ border-collapse: collapse; margin-top: 10px; margin-bottom: 10px; width: 100%; }}
                th, td {{ border: 1px solid #555555; padding: 6px 12px; }}
                img {{ max-width: 100%; max-height: 600px; height: auto; object-fit: contain; margin: 10px 0; }}
            </style>
            {html_content}
            """
            
            self.details_text.setHtml(styled_html)
                
        else:
            self.details_text.setHtml("")
        
        if highlight_query:
            self.highlight_search_term(highlight_query)
            
        self.download_button.setVisible(True)
        self.copy_button.setVisible(True)
        self.open_hub_button.setVisible(True)

        # Fetch relationships in background
        self.fetch_relationships(self.current_model_id)

    def fetch_relationships(self, model_id):
        if self.relationship_worker:
            # We don't have a direct cancel for QRunnable but we can ignore results
            self.relationship_worker.signals.result.disconnect()

        self.tree_widget.setVisible(False)
        
        from PySide6.QtCore import QThreadPool
        threadpool = QThreadPool.globalInstance()
        
        self.relationship_worker = Worker(hf_service.get_model_relationships, model_id)
        self.relationship_worker.signals.result.connect(self.on_relationships_loaded)
        threadpool.start(self.relationship_worker)

    def on_relationships_loaded(self, relationships):
        if relationships:
            self.tree_widget.set_relationships(self.current_model_id, relationships)
        else:
            self.tree_widget.setVisible(False)

    def highlight_search_term(self, query):
        """Highlights occurrences of the query terms using JavaScript."""
        if not query:
            return

        terms = [t.strip() for t in query.split() if len(t.strip()) > 1]
        if not terms:
             return

        # Simple JS script to highlight text, wait for ready
        js = f"""
        function highlightText() {{
            let words = {terms};
            words.forEach(word => {{
                let body = document.body.innerHTML;
                let regex = new RegExp(`(${{word}})`, 'gi');
                document.body.innerHTML = body.replace(regex, '<span style="background-color: yellow; color: black;">$1</span>');
            }});
            window.scrollTo(0,0);
        }}
        highlightText();
        """
        self.details_text.page().runJavaScript(js)

    def clear_details(self):
        """
        Clears the panel.
        """
        self.current_model_id = None
        self.title_label.setText("Select a model to see details")
        self.details_text.setHtml("")
        self.download_button.setVisible(False)
        self.copy_button.setVisible(False)
        self.open_hub_button.setVisible(False)