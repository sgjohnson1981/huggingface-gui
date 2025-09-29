from PySide6.QtWidgets import QMessageBox


class AboutDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Hugging Face GUI Explorer")
        self.setText(
            """
            <b>Hugging Face GUI Explorer</b>
            <p>Version 1.0</p>
            <p>A desktop application to search, explore, and download models from the Hugging Face Hub.</p>
            <p>Created with PySide6 and the Hugging Face Hub library.</p>
            """
        )
        self.setIcon(QMessageBox.Icon.Information)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)