import sys
from PySide6.QtCore import QThreadPool, QTimer, Qt
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
    QPushButton,
    QSplitter,
)
from .settings_dialog import SettingsDialog
from .search_panel import SearchPanel
from .huggingface_service import hf_service, run_download_in_process, run_search_in_process
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
        self.current_search_worker = None
        self.cached_tags = []
        self.active_details_workers = set() # Keep references to detail workers

        # Timer to check the download queue
        self.download_queue_timer = QTimer(self)
        self.download_queue_timer.setInterval(100)
        self.download_queue_timer.timeout.connect(self.process_download_queue)

        # Timer to check the search queue
        self.search_queue_timer = QTimer(self)
        self.search_queue_timer.setInterval(100)
        self.search_queue_timer.timeout.connect(self.process_search_queue)


        # Create main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main Splitter: Left (Search) vs Right (Table & Details)
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Left Panel: Search and Filter
        self.search_panel = SearchPanel()
        self.search_panel.setMinimumWidth(250)
        self.main_splitter.addWidget(self.search_panel)
        self.search_panel.search_triggered.connect(self.perform_search)
        self.search_panel.cancel_triggered.connect(self.cancel_search)

        # Right Panel: Results and Details (Vertical Splitter)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.right_splitter)

        # Top Right: Search Results
        self.results_table = ResultsTableView()
        self.results_model = ResultsTableModel()
        self.results_table.set_model(self.results_model)
        self.results_table.selectionModel().selectionChanged.connect(self.on_model_selected)
        self.right_splitter.addWidget(self.results_table)

        # Bottom Right: Model Details
        self.details_panel = ModelDetailsPanel()
        self.details_panel.download_button.clicked.connect(self.on_download_clicked)
        self.details_panel.tree_widget.modelClicked.connect(self.navigate_to_model)
        self.details_panel.tree_widget.filterClicked.connect(self.perform_filtered_search)
        self.right_splitter.addWidget(self.details_panel)

        # Set stretch factors:
        # 0: Search panel (doesn't grow horizontally by default)
        # 1: Right panel (grows to fill horizontal space)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        # Results table and details panel should both grow
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 1)

        # Set initial proportions
        self.right_splitter.setSizes([480, 320])
        self.main_splitter.setSizes([300, 900])

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

    def process_search_queue(self):
        """
        Processes messages from the search worker's queue.
        """
        if not self.current_search_worker:
            return

        try:
            while not self.current_search_worker.queue.empty():
                message_type, data = self.current_search_worker.queue.get_nowait()

                if message_type == 'result':
                    self.on_search_finished(data)
                elif message_type == 'error':
                    self.on_search_error(data)

        except Exception as e:
            logger.error(f"Error processing search queue: {e}", exc_info=True)
        finally:
            # Ensure the timer is stopped and state is reset if the worker is no longer running
            if not self.current_search_worker or not self.current_search_worker.is_running():
                self.search_queue_timer.stop()
                self.search_panel.set_searching_state(False)
                if self.current_search_worker: # If it finished or crashed
                    self.current_search_worker = None


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
                    self.download_queue_timer.stop() # Stop polling when finished
                elif message_type == 'error':
                    self.on_download_error(data)
                    self.download_queue_timer.stop() # Stop polling when finished

        except Exception as e:
            logger.error(f"Error processing download queue: {e}", exc_info=True)
            self.download_queue_timer.stop()


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
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(lambda: self.on_edit_action("undo"))
        
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(lambda: self.on_edit_action("redo"))
        
        edit_menu.addSeparator()
        
        cut_action = edit_menu.addAction("Cut")
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(lambda: self.on_edit_action("cut"))
        
        copy_action = edit_menu.addAction("Copy")
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(lambda: self.on_edit_action("copy"))
        
        paste_action = edit_menu.addAction("Paste")
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self.on_edit_action("paste"))
        
        edit_menu.addSeparator()
        
        select_all_action = edit_menu.addAction("Select All")
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(lambda: self.on_edit_action("select_all"))

        # View Menu
        view_menu = menu_bar.addMenu("View")
        self.toggle_search_action = view_menu.addAction("Show Search Panel")
        self.toggle_search_action.setCheckable(True)
        self.toggle_search_action.setChecked(True)
        self.toggle_search_action.triggered.connect(self.toggle_search_panel)
        
        refresh_action = view_menu.addAction("Refresh Filters")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.load_initial_filters)

        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.open_about_dialog)

    def on_edit_action(self, action_name):
        """
        Dispatches standard Edit actions to the focused widget if it supports them.
        """
        widget = QApplication.focusWidget()
        if not widget:
            return
            
        if action_name == "undo" and hasattr(widget, 'undo'):
            widget.undo()
        elif action_name == "redo" and hasattr(widget, 'redo'):
            widget.redo()
        elif action_name == "cut" and hasattr(widget, 'cut'):
            widget.cut()
        elif action_name == "copy" and hasattr(widget, 'copy'):
            widget.copy()
        elif action_name == "paste" and hasattr(widget, 'paste'):
            widget.paste()
        elif action_name == "select_all" and hasattr(widget, 'selectAll'):
            widget.selectAll()

    def toggle_search_panel(self, checked):
        self.search_panel.setVisible(checked)
        self.toggle_search_action.setText("Show Search Panel" if not checked else "Hide Search Panel")

    def open_about_dialog(self):
        from .about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()

    def open_settings_dialog(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Reconnect service if token changed
            hf_service.connect()

    def perform_search(self, search_params):
        if self.current_search_worker and self.current_search_worker.is_running():
            QMessageBox.warning(self, "Search in Progress", "A search is already in progress. Please cancel it before starting a new one.")
            return

        self.statusBar().showMessage("Searching for models...")
        self.search_panel.set_searching_state(True)
        self.results_model.set_data([]) # Clear previous results
        self.details_panel.clear_details()

        self.current_search_worker = DownloadWorker(
            target=run_search_in_process,
            args=(search_params,)
        )
        self.current_search_worker.start()
        self.search_queue_timer.start()


    def cancel_search(self):
        """Cancels the currently running search."""
        if self.current_search_worker and self.current_search_worker.is_running():
            logger.info("User cancelled search.")
            self.current_search_worker.stop()
            self.search_queue_timer.stop()
            self.current_search_worker = None
            self.search_panel.set_searching_state(False)
            self.statusBar().showMessage("Search cancelled.", 3000)

    def on_search_finished(self, results):
        models, total_hits = results
        self.results_model.set_data(models)
        self.details_panel.clear_details()

        # Update status bar with meaningful result summary
        model_count = len(models)
        if total_hits and model_count < total_hits:
            self.statusBar().showMessage(f"Showing first {model_count} models out of {total_hits:,} estimated total hits.")
        else:
            self.statusBar().showMessage(f"Found {model_count} models.")

    def on_search_error(self, err):
        exctype, value, tb = err
        logger.error(f"Search failed: {value}", exc_info=err)
        QMessageBox.critical(self, "Search Error", f"An unexpected error occurred during search: {value}")
        self.statusBar().showMessage("Search failed.", 5000)
        # The worker/timer will be stopped in the process_search_queue method.

    def navigate_to_model(self, model_id):
        """Navigates to a specific model by ID."""
        self.search_panel.search_input.setText(model_id)
        self.perform_search({"search_query": model_id, "strict": True})

    def perform_filtered_search(self, filter_str):
        """Adds a relationship filter chip and performs a search."""
        self.statusBar().showMessage(f"Adding filter for related models: {filter_str}")
        self.search_panel.add_filter_chip(filter_str)
        self.perform_search(self.search_panel.get_search_parameters())

    def on_model_selected(self, selected, deselected):
        if not selected.indexes():
            return

        source_index = self.results_table.model().mapToSource(selected.indexes()[0])
        if not source_index.isValid():
            return

        # Double check row range to prevent IndexError
        if source_index.row() >= len(self.results_model._data) or source_index.row() < 0:
            logger.warning(f"Selected row {source_index.row()} is out of range.")
            return

        model_info = self.results_model._data[source_index.row()]
        model_id = getattr(model_info, 'id', None)
        if not model_id:
            logger.error("Selected model info has no ID.")
            return

        self.statusBar().showMessage(f"Fetching details for {model_id}...")

        worker = Worker(hf_service.get_model_readme, model_id)
        # Pass model_info to the result handler using a lambda
        worker.signals.result.connect(lambda readme, m=model_info, w=worker: self.on_details_finished(m, readme, w))
        worker.signals.error.connect(lambda err, w=worker: self.on_details_error(err, w))
        worker.signals.finished.connect(lambda w=worker: self.active_details_workers.discard(w))
        
        # Keep a reference to prevent GC
        self.active_details_workers.add(worker)
        self.threadpool.start(worker)

    def on_details_finished(self, model_info, readme, worker=None):
        search_query = self.search_panel.search_input.text()
        self.details_panel.set_model_details(model_info, readme, highlight_query=search_query)
        self.statusBar().showMessage(f"Details loaded for {model_info.id}.", 3000)

    def on_details_error(self, err, worker=None):
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
        self.download_queue_timer.start()

    def on_download_progress(self, current, total):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.status_bar.showMessage(f"Downloading file {current} of {total}...")

    def cancel_download(self):
        if self.current_download_worker and self.current_download_worker.is_running():
            logger.info(f"Attempting to cancel download for model: {self.current_download_model_id}")
            self.current_download_worker.stop()
            self.download_queue_timer.stop()
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
    from PySide6.QtGui import QPalette, QColor
    
    # Set Palette for specific items like PlaceholderText
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(43, 43, 43))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(60, 60, 60))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.PlaceholderText, QColor(120, 120, 120))
    app.setPalette(palette)

    dark_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            border: none;
        }
        QSplitter::handle {
            background-color: #323232;
        }
        QSplitter::handle:horizontal {
            width: 3px;
        }
        QSplitter::handle:vertical {
            height: 3px;
        }
        QMainWindow, QDialog {
            background-color: #2b2b2b;
        }
        QMenuBar {
            background-color: #3c3c3c;
            border-bottom: 1px solid #1e1e1e;
        }
        QMenuBar::item {
            background-color: #3c3c3c;
            color: #ffffff;
            padding: 4px 10px;
        }
        QMenuBar::item::selected {
            background-color: #555555;
        }
        QMenu {
            background-color: #3c3c3c;
            border: 1px solid #454545;
        }
        QMenu::item {
            padding: 4px 20px;
        }
        QMenu::item::selected {
            background-color: #555555;
        }
        QLineEdit, QComboBox, QAbstractSpinBox {
            background-color: #1e1e1e;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 5px;
            color: #ffffff;
        }
        QLineEdit:focus, QComboBox:focus {
            border: 1px solid #2a82da;
        }
        QGroupBox {
            border: 1px solid #555555;
            border-radius: 6px;
            margin-top: 1.1em;
            padding-top: 0.5em;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 3px;
        }
        QPushButton {
            background-color: #454545;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 12px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QPushButton:pressed {
            background-color: #353535;
        }
        QPushButton:disabled {
            background-color: #323232;
            color: #777777;
        }
        QHeaderView::section {
            background-color: #3c3c3c;
            color: #ffffff;
            padding: 4px;
            border: 1px solid #1e1e1e;
        }
        QTableView {
            background-color: #1e1e1e;
            alternate-background-color: #252525;
            gridline-color: #323232;
            selection-background-color: #2a82da;
            border: 1px solid #555555;
        }
        QScrollBar:vertical {
            border: none;
            background: #2b2b2b;
            width: 14px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #454545;
            min-height: 20px;
            border-radius: 7px;
            margin: 2px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QStatusBar {
            background-color: #3c3c3c;
            border-top: 1px solid #1e1e1e;
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