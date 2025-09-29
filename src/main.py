import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStatusBar,
    QMenuBar,
    QLabel,
    QFileDialog,
    QMessageBox,
)
from .settings_dialog import SettingsDialog
from .search_panel import SearchPanel
from .huggingface_service import hf_service
from .results_table import ResultsTableView, ResultsTableModel
from .model_details_panel import ModelDetailsPanel
from .config_manager import config_manager
from .logging_config import logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Hugging Face Model Hub Explorer")
        self.setGeometry(100, 100, 1200, 800)

        # Create main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left Panel: Search and Filter
        self.search_panel = SearchPanel()
        self.search_panel.setFixedWidth(300)
        main_layout.addWidget(self.search_panel)
        self.search_panel.search_triggered.connect(self.perform_search)

        # Right Panel: Results and Details
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel)

        # Top Right: Search Results
        self.results_table = ResultsTableView()
        self.results_model = ResultsTableModel()
        self.results_table.set_model(self.results_model)
        self.results_table.selectionModel().selectionChanged.connect(self.on_model_selected)
        right_panel_layout.addWidget(self.results_table)

        # Bottom Right: Model Details
        self.details_panel = ModelDetailsPanel()
        self.details_panel.download_button.clicked.connect(self.on_download_clicked)
        right_panel_layout.addWidget(self.details_panel)

        # Set up Menu Bar and Status Bar
        self.create_menu_bar()
        self.setStatusBar(QStatusBar(self))

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        # File Menu
        file_menu = menu_bar.addMenu("File")
        settings_action = file_menu.addAction("Settings...")
        settings_action.triggered.connect(self.open_settings_dialog)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        # Edit Menu
        edit_menu = menu_bar.addMenu("Edit")

        # View Menu
        view_menu = menu_bar.addMenu("View")

        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("About")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Reconnect service if token changed
            hf_service.connect()

    def perform_search(self, search_params):
        self.statusBar().showMessage("Searching for models...")
        # This should be run in a separate thread in a real app to avoid freezing the GUI
        # For now, we'll run it directly
        try:
            logger.info(f"Performing search with params: {search_params}")
            results = hf_service.search_models(**search_params)
            self.statusBar().showMessage(f"Found {len(results)} models.")
            self.results_model.set_data(results)
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Search Error", f"An unexpected error occurred during search: {e}")
            self.statusBar().showMessage("Search failed.", 5000)
        finally:
            self.details_panel.clear_details()

    def on_model_selected(self, selected, deselected):
        if not selected.indexes():
            return

        source_index = self.results_table.model().mapToSource(selected.indexes()[0])
        model_info = self.results_model._data[source_index.row()]

        self.statusBar().showMessage(f"Fetching details for {model_info.id}...")
        # In a real app, this should be in a thread
        try:
            logger.info(f"Fetching details for model: {model_info.id}")
            readme = hf_service.get_model_readme(model_info.id)
            self.details_panel.set_model_details(model_info, readme)
            self.statusBar().showMessage(f"Details loaded for {model_info.id}.", 3000)
        except Exception as e:
            logger.error(f"Failed to fetch model details for {model_info.id}: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Could not fetch model details: {e}")
            self.statusBar().showMessage("Failed to load details.", 5000)

    def on_download_clicked(self):
        model_id = self.details_panel.current_model_id
        if not model_id:
            return

        try:
            if config_manager.get('prompt_for_download'):
                download_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory")
                if not download_dir:
                    logger.info("User cancelled download dialog.")
                    return  # User cancelled
            else:
                download_dir = config_manager.get('download_dir')

            self.statusBar().showMessage(f"Downloading {model_id}...")
            logger.info(f"Starting download for model {model_id} to directory {download_dir}")

            # This should also be in a thread
            success, message = hf_service.download_model(model_id, download_dir)
            self.statusBar().showMessage(message, 5000)

            if success:
                logger.info(f"Successfully downloaded model {model_id}.")
                QMessageBox.information(self, "Download Complete", message)
            else:
                logger.error(f"Download failed for model {model_id}. Reason: {message}")
                QMessageBox.warning(self, "Download Failed", message)
        except Exception as e:
            logger.critical(f"An unexpected error occurred during download for {model_id}: {e}", exc_info=True)
            QMessageBox.critical(self, "Download Error", f"An unexpected error occurred: {e}")
            self.statusBar().showMessage("Download failed.", 5000)


def set_dark_mode(app):
    dark_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            border: 1px solid #323232;
        }
        QMainWindow {
            background-color: #2b2b2b;
        }
        QMenuBar {
            background-color: #3c3c3c;
        }
        QMenuBar::item {
            background-color: #3c3c3c;
            color: #ffffff;
        }
        QMenuBar::item::selected {
            background-color: #555555;
        }
        QMenu {
            background-color: #3c3c3c;
            border: 1px solid #454545;
        }
        QMenu::item::selected {
            background-color: #555555;
        }
        QLabel {
            border: none;
        }
        QStatusBar {
            background-color: #3c3c3c;
        }
    """
    app.setStyleSheet(dark_stylesheet)


def global_exception_hook(exctype, value, traceback):
    """
    Global exception handler to catch unhandled exceptions.
    """
    logger.critical("Global unhandled exception caught!", exc_info=(exctype, value, traceback))
    sys.__excepthook__(exctype, value, traceback)
    # Optionally, show a critical message to the user
    QMessageBox.critical(
        None,
        "Unhandled Exception",
        "A critical error occurred. Please check the logs for details.",
    )

if __name__ == "__main__":
    sys.excepthook = global_exception_hook

    app = QApplication(sys.argv)
    set_dark_mode(app)
    main_window = MainWindow()
    main_window.show()
    logger.info("Application started successfully.")
    sys.exit(app.exec())