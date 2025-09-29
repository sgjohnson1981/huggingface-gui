import sys
from PySide6.QtCore import QThreadPool
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
    QProgressBar,
)
from .settings_dialog import SettingsDialog
from .search_panel import SearchPanel
from .huggingface_service import hf_service
from .results_table import ResultsTableView, ResultsTableModel
from .model_details_panel import ModelDetailsPanel
from .config_manager import config_manager
from .logging_config import logger
from .worker import Worker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Hugging Face Model Hub Explorer")
        self.setGeometry(100, 100, 1200, 800)
        self.threadpool = QThreadPool()
        logger.info(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")


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
        self.setup_status_bar()

        # Load dynamic filters on startup
        self.load_initial_filters()

    def setup_status_bar(self):
        """
        Initializes the status bar, including the download progress bar.
        """
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar(self.status_bar)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def load_initial_filters(self):
        """
        Starts a background worker to fetch model tags and populate the search filters.
        """
        filter_worker = Worker(hf_service.get_model_tags)
        filter_worker.signals.result.connect(self.search_panel.populate_filters)
        filter_worker.signals.error.connect(self.on_filter_load_error)
        self.threadpool.start(filter_worker)

    def on_filter_load_error(self, err):
        exctype, value, tb = err
        logger.error(f"Failed to load filters: {value}", exc_info=err)
        # The search panel will show an error message, but we can also log it.
        self.search_panel.populate_filters([]) # Pass empty list to show error message

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
        self.search_panel.set_enabled(False)

        worker = Worker(hf_service.search_models, **search_params)
        worker.signals.result.connect(self.on_search_finished)
        worker.signals.error.connect(self.on_search_error)
        worker.signals.finished.connect(lambda: self.search_panel.set_enabled(True))
        self.threadpool.start(worker)

    def on_search_finished(self, results):
        self.statusBar().showMessage(f"Found {len(results)} models.")
        self.results_model.set_data(results)
        self.details_panel.clear_details()

    def on_search_error(self, err):
        exctype, value, tb = err
        logger.error(f"Search failed: {value}", exc_info=err)
        QMessageBox.critical(self, "Search Error", f"An unexpected error occurred during search: {value}")
        self.statusBar().showMessage("Search failed.", 5000)

    def on_model_selected(self, selected, deselected):
        if not selected.indexes():
            return

        source_index = self.results_table.model().mapToSource(selected.indexes()[0])
        model_info = self.results_model._data[source_index.row()]
        model_id = model_info.id

        self.statusBar().showMessage(f"Fetching details for {model_id}...")

        worker = Worker(hf_service.get_model_readme, model_id)
        # Pass model_info to the result handler using a lambda
        worker.signals.result.connect(lambda readme: self.on_details_finished(model_info, readme))
        worker.signals.error.connect(self.on_details_error)
        self.threadpool.start(worker)

    def on_details_finished(self, model_info, readme):
        self.details_panel.set_model_details(model_info, readme)
        self.statusBar().showMessage(f"Details loaded for {model_info.id}.", 3000)

    def on_details_error(self, err):
        exctype, value, tb = err
        logger.error(f"Failed to fetch model details: {value}", exc_info=err)
        QMessageBox.warning(self, "Error", f"Could not fetch model details: {value}")
        self.statusBar().showMessage("Failed to load details.", 5000)


    def on_download_clicked(self):
        model_id = self.details_panel.current_model_id
        if not model_id:
            return

        download_dir = None
        if config_manager.get('prompt_for_download'):
            download_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory")
            if not download_dir:
                logger.info("User cancelled download dialog.")
                return
        else:
            download_dir = config_manager.get('download_dir')

        if not download_dir:
            QMessageBox.warning(self, "Download Directory Not Set", "Please set a download directory in Settings.")
            return

        self.status_bar.showMessage(f"Starting download for {model_id}...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.details_panel.download_button.setEnabled(False)

        worker = Worker(hf_service.download_model, model_id, download_dir)
        worker.signals.progress.connect(self.on_download_progress)
        worker.signals.result.connect(self.on_download_finished)
        worker.signals.error.connect(self.on_download_error)
        # Re-enable the button once the worker is completely finished
        worker.signals.finished.connect(lambda: self.details_panel.download_button.setEnabled(True))
        self.threadpool.start(worker)

    def on_download_progress(self, current, total):
        """
        Updates the download progress bar.
        """
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.status_bar.showMessage(f"Downloading file {current} of {total}...")

    def on_download_finished(self, result):
        success, message = result
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage(message, 5000)
        if success:
            logger.info(f"Successfully downloaded. Message: {message}")
            QMessageBox.information(self, "Download Complete", message)
        else:
            logger.error(f"Download failed. Reason: {message}")
            QMessageBox.warning(self, "Download Failed", message)

    def on_download_error(self, err):
        exctype, value, tb = err
        logger.critical(f"An unexpected error occurred during download: {value}", exc_info=err)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Download Error", f"An unexpected error occurred: {value}")
        self.status_bar.showMessage("Download failed.", 5000)


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