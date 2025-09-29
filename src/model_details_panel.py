import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QApplication,
)


class ModelDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_model_id = None

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

        # Model Card Display
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.details_text)

    def copy_model_id(self):
        if self.current_model_id:
            QApplication.clipboard().setText(self.current_model_id)

    def open_on_hub(self):
        if self.current_model_id:
            url = f"https://huggingface.co/{self.current_model_id}"
            webbrowser.open(url)

    def set_model_details(self, model_info, model_readme):
        """
        Populates the panel with model details.
        """
        self.current_model_id = model_info.id
        self.title_label.setText(model_info.id)
        self.details_text.setMarkdown(model_readme)
        self.download_button.setVisible(True)
        self.copy_button.setVisible(True)
        self.open_hub_button.setVisible(True)

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