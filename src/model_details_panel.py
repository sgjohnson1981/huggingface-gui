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

        self.details_text = QTextBrowser()
        self.details_text.setOpenExternalLinks(True)
        self.details_text.setStyleSheet("background-color: #1e1e1e; color: #ffffff; border: none; padding: 10px;")
        
        self.layout.addWidget(self.details_text)

    def copy_model_id(self):
        if self.current_model_id:
            QApplication.clipboard().setText(self.current_model_id)

    def open_on_hub(self):
        if self.current_model_id:
            url = f"https://huggingface.co/{self.current_model_id}"
            webbrowser.open(url)

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
            
            # Add some basic CSS so HTML elements inherit the dark mode style properly
            # and format images/tables so they don't break the layout
            styled_html = f"""
            <style>
                body {{ color: #ffffff; font-family: sans-serif; }}
                a {{ color: #3b82f6; }}
                code, pre {{ background-color: #2d2d2d; padding: 2px 4px; border-radius: 4px; }}
                pre {{ padding: 10px; }}
                table {{ border-collapse: collapse; margin-top: 10px; margin-bottom: 10px; }}
                th, td {{ border: 1px solid #555555; padding: 6px 12px; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
            {html_content}
            """
            
            self.details_text.setHtml(styled_html)
        else:
            self.details_text.clear()
        
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
        """Highlights all occurrences of the query terms in the text document."""
        if not query:
            return

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("yellow"))
        fmt.setForeground(QColor("black"))

        document = self.details_text.document()
        cursor = QTextCursor(document)
        cursor.beginEditBlock()
        
        # Split search terms to highlight each matching word
        terms = [t.strip() for t in query.split() if len(t.strip()) > 1]
        if not terms:
             cursor.endEditBlock()
             return

        for term in terms:
            search_cursor = QTextCursor(document)
            while True:
                # Default document.find is case-insensitive
                search_cursor = document.find(term, search_cursor)
                if search_cursor.isNull():
                    break
                search_cursor.mergeCharFormat(fmt)
            
        cursor.endEditBlock()
        
        # Ensure scroll position is at the top
        self.details_text.moveCursor(QTextCursor.Start)

    def clear_details(self):
        """
        Clears the panel.
        """
        self.current_model_id = None
        self.title_label.setText("Select a model to see details")
        self.details_text.clear()
        self.download_button.setVisible(False)
        self.copy_button.setVisible(False)
        self.open_hub_button.setVisible(False)