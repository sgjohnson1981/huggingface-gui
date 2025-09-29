import sys
from PySide6.QtCore import QThreadPool, QTimer
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
from .huggingface_service import hf_service, run_download_in_process
from .results_table import ResultsTableView, ResultsTableModel
from .model_details_panel import ModelDetailsPanel
from .config_manager import config_manager
from .cache_manager import cache_manager
from .logging_config import logger
from .worker import Worker
from .download_worker import DownloadWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Hugging Face Model Hub Explorer")
        self.setGeometry(100, 100, 1200, 800)
        self.threadpool = QThreadPool()
        logger.info(f"Multithreading with maximum {self.threadpool.maxThreadCount()} threads")
        self.current_download_worker = None
        self.current_download_model_id = None
        self.cached_tags = []

        # Timer to check the download queue
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(100)  # Check every 100ms
        self.queue_timer.timeout.connect(self.process_download_queue)


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

        self.status_bar_layout = QHBoxLayout()
        self.status_bar_widget = QWidget()
        self.status_bar_widget.setLayout(self.status_bar_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.setFixedWidth(80)
        self.cancel_button.clicked.connect(self.cancel_download)

        self.status_bar_layout.addStretch()
        self.status_bar_layout.addWidget(self.progress_bar)
        self.status_bar_layout.addWidget(self.cancel_button)
        self.status_bar_layout.setContentsMargins(0,0,0,0)

        self.status_bar.addPermanentWidget(self.status_bar_widget)

    def process_download_queue(self):
        """
        Processes messages from the download worker's queue.
        This is called by a QTimer.
        """
        if not self.current_download_worker:
            return

        try:
            # Read all available messages from the queue
            while not self.current_download_worker.queue.empty():
                message_type, data = self.current_download_worker.queue.get_nowait()

                if message_type == 'progress':
                    self.on_download_progress(*data)
                elif message_type == 'result':
                    self.on_download_finished(data)
                    self.queue_timer.stop() # Stop polling when finished
                elif message_type == 'error':
                    self.on_download_error(data)
                    self.queue_timer.stop() # Stop polling when finished

        except Exception as e:
            logger.error(f"Error processing download queue: {e}", exc_info=True)
            self.queue_timer.stop()


    def load_initial_filters(self):
        """
        Loads filters from cache for a quick startup, then fetches fresh
        filters in the background to update the cache and UI if needed.
        """
        # 1. Load from cache and populate UI immediately
        self.cached_tags = cache_manager.load_filters() or []
        self.search_panel.populate_filters(self.cached_tags)
        logger.info(f"Loaded {len(self.cached_tags)} filters from cache.")

        # 2. Start background worker to fetch fresh tags
        self.statusBar().showMessage("Checking for new filters...", 2000)
        filter_worker = Worker(hf_service.get_model_tags)
        filter_worker.signals.result.connect(self.on_filter_refresh_finished)
        filter_worker.signals.error.connect(self.on_filter_refresh_error)
        self.threadpool.start(filter_worker)

    def on_filter_refresh_finished(self, fresh_tags):
        """
        Handles the result of the background filter refresh. Updates the UI and
        cache if the new tags are different from the cached ones.
        """
        if fresh_tags and set(fresh_tags) != set(self.cached_tags):
            logger.info("New filters found. Updating UI and cache.")
            self.statusBar().showMessage("Filters updated.", 5000)
            self.search_panel.populate_filters(fresh_tags)
            cache_manager.save_filters(fresh_tags)
            self.cached_tags = fresh_tags
        elif not fresh_tags and self.cached_tags:
            logger.warning("Filter refresh returned no tags. Sticking with cached version.")
            self.statusBar().showMessage("Failed to update filters. Using cached version.", 5000)
        elif not fresh_tags and not self.cached_tags:
            logger.error("Failed to fetch initial filters and no cache was available.")
        else:
            logger.info("Filters are up-to-date.")
            self.statusBar().showMessage("Filters are up-to-date.", 3000)

    def on_filter_refresh_error(self, err):
        """
        Handles errors from the background filter refresh.
        """
        exctype, value, tb = err
        logger.error(f"Failed to refresh filters in background: {value}", exc_info=err)
        self.statusBar().showMessage("Failed to update filters.", 5000)

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


    # --- Download Handling ---

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
        self.cancel_button.setVisible(True)
        self.details_panel.download_button.setEnabled(False)

        self.current_download_model_id = model_id
        self.current_download_worker = DownloadWorker(
            target=run_download_in_process,
            args=(model_id, download_dir)
        )
        self.current_download_worker.start()
        self.queue_timer.start()

    def on_download_progress(self, current, total):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.status_bar.showMessage(f"Downloading file {current} of {total}...")

    def cancel_download(self):
        if self.current_download_worker and self.current_download_worker.is_running():
            logger.info(f"Attempting to cancel download for model: {self.current_download_model_id}")
            self.current_download_worker.stop()
            self.queue_timer.stop()
            hf_service.delete_model_cache(self.current_download_model_id)
            self.status_bar.showMessage("Download cancelled.", 5000)
            self.progress_bar.setVisible(False)
            self.cancel_button.setVisible(False)
            self.details_panel.download_button.setEnabled(True)
            self.current_download_worker = None
            self.current_download_model_id = None

    def on_download_finished(self, result):
        success, message = result
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.details_panel.download_button.setEnabled(True)
        self.current_download_worker = None
        self.current_download_model_id = None
        self.status_bar.showMessage(message, 5000)
        if success:
            QMessageBox.information(self, "Download Complete", message)
        else:
            QMessageBox.warning(self, "Download Failed", message)

    def on_download_error(self, err):
        if self.current_download_worker is None:
            return # Already cancelled
        exctype, value, tb = err
        logger.critical(f"An unexpected error occurred during download: {value}", exc_info=(exctype, value, tb))
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self.details_panel.download_button.setEnabled(True)
        self.current_download_worker = None
        self.current_download_model_id = None
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