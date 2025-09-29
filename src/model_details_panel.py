from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
)
from PySide6.QtCore import Qt


class ModelDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Select a model to see details")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.download_button = QPushButton("Download Model")
        self.download_button.setVisible(False)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.download_button)

        # Model Card Display
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

        self.layout.addLayout(header_layout)
        self.layout.addWidget(self.details_text)

    def set_model_details(self, model_info, model_readme):
        """
        Populates the panel with model details.
        """
        self.current_model_id = model_info.id
        self.title_label.setText(model_info.id)
        self.details_text.setMarkdown(model_readme)
        self.download_button.setVisible(True)

    def clear_details(self):
        """
        Clears the panel.
        """
        self.current_model_id = None
        self.title_label.setText("Select a model to see details")
        self.details_text.clear()
        self.download_button.setVisible(False)