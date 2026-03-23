from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QHBoxLayout,
    QFileDialog,
)
from .config_manager import config_manager


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 350)

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # Hugging Face Token
        self.hf_token_input = QLineEdit()
        self.hf_token_input.setEchoMode(QLineEdit.Password)
        self.hf_token_input.setText(config_manager.get("hf_token"))
        self.form_layout.addRow("Hugging Face Token:", self.hf_token_input)

        # Download Directory
        self.download_dir_input = QLineEdit()
        self.download_dir_input.setText(config_manager.get("download_dir"))
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_download_dir)

        download_dir_layout = QHBoxLayout()
        download_dir_layout.addWidget(self.download_dir_input)
        download_dir_layout.addWidget(browse_button)
        self.form_layout.addRow("Default Download Directory:", download_dir_layout)

        # Other settings
        self.prompt_download_checkbox = QCheckBox("Always ask for download location")
        self.prompt_download_checkbox.setChecked(config_manager.get("prompt_for_download"))
        self.form_layout.addRow(self.prompt_download_checkbox)

        self.view_details_window_checkbox = QCheckBox("Open model details in a new window")
        self.view_details_window_checkbox.setChecked(config_manager.get("view_details_in_new_window"))
        self.form_layout.addRow(self.view_details_window_checkbox)

        self.layout.addLayout(self.form_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def browse_download_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", self.download_dir_input.text()
        )
        if directory:
            self.download_dir_input.setText(directory)

    def accept(self):
        # Save settings
        config_manager.set("hf_token", self.hf_token_input.text())
        config_manager.set("download_dir", self.download_dir_input.text())
        config_manager.set("prompt_for_download", self.prompt_download_checkbox.isChecked())
        config_manager.set("view_details_in_new_window", self.view_details_window_checkbox.isChecked())
        config_manager.save_config()
        config_manager.ensure_download_dir_exists()
        super().accept()