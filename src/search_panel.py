from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QScrollArea,
    QCheckBox,
    QGroupBox,
)
from PySide6.QtCore import Signal, QTimer


class SearchPanel(QWidget):
    search_triggered = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Search Query
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for models...")

        # Sorting
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Most Downloads", "Most Likes", "Recently Updated"]
        )

        # Filters
        self.filters_group = QGroupBox("Filters")
        filters_group_layout = QVBoxLayout(self.filters_group)

        # Filter Search Box
        self.filter_search_input = QLineEdit()
        self.filter_search_input.setPlaceholderText("Search filters...")
        self.filter_search_input.textChanged.connect(self.on_filter_search_changed)

        self.filter_search_timer = QTimer(self)
        self.filter_search_timer.setSingleShot(True)
        self.filter_search_timer.setInterval(300) # 300ms debounce delay
        self.filter_search_timer.timeout.connect(self.perform_filter_search)

        filters_group_layout.addWidget(self.filter_search_input)

        # Scroll Area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.filters_widget = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_widget)
        self.task_filters = {}

        # Initially, show a loading message
        self.loading_label = QLabel("Loading filters...")
        self.filters_layout.addWidget(self.loading_label)

        # Label for "No filters found"
        self.no_filters_found_label = QLabel("No filters found.")
        self.no_filters_found_label.setVisible(False)
        self.filters_layout.addWidget(self.no_filters_found_label)

        scroll.setWidget(self.filters_widget)
        filters_group_layout.addWidget(scroll)

        # Search Button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search_clicked)

        # Layout
        form_layout = QFormLayout()
        form_layout.addRow(QLabel("Search:"))
        form_layout.addRow(self.search_input)
        form_layout.addRow(QLabel("Sort by:"))
        form_layout.addRow(self.sort_combo)

        self.layout.addLayout(form_layout)
        self.layout.addWidget(self.filters_group)
        self.layout.addStretch()
        self.layout.addWidget(self.search_button)

    def on_search_clicked(self):
        search_params = self.get_search_parameters()
        self.search_triggered.emit(search_params)

    def get_search_parameters(self):
        # Map combo box text to API sort values
        sort_map = {
            "Most Downloads": "downloads",
            "Most Likes": "likes",
            "Recently Updated": "lastModified",
        }
        sort_val = sort_map.get(self.sort_combo.currentText())

        # Get selected filters
        selected_filters = [
            task for task, checkbox in self.task_filters.items() if checkbox.isChecked()
        ]

        return {
            "search_query": self.search_input.text(),
            "sort": sort_val,
            "direction": -1,  # Always descending for these sort options
            "filters": selected_filters,
        }

    def on_filter_search_changed(self):
        """
        Restarts the debounce timer every time the user types in the
        filter search box.
        """
        self.filter_search_timer.start()

    def perform_filter_search(self):
        """
        Filters the list of checkboxes based on the search text.
        This is connected to the debounce timer's timeout signal.
        """
        search_text = self.filter_search_input.text().lower()
        found_match = False

        for checkbox in self.task_filters.values():
            if search_text in checkbox.text().lower():
                checkbox.setVisible(True)
                found_match = True
            else:
                checkbox.setVisible(False)

        # Show/hide the "No filters found" label
        self.no_filters_found_label.setVisible(not found_match)


    def set_enabled(self, enabled):
        """Enable or disable the search panel widgets."""
        self.search_input.setEnabled(enabled)
        self.sort_combo.setEnabled(enabled)
        self.filters_group.setEnabled(enabled)
        self.search_button.setEnabled(enabled)

    def _format_tag_name(self, tag):
        """Formats a tag ID into a human-readable label."""
        return tag.replace("-", " ").title()

    def populate_filters(self, tags):
        """
        Populates the filter group box with checkboxes for each tag.
        This method clears any existing filters before adding new ones.
        """
        # Reset search and hide 'not found' label
        self.filter_search_input.clear()
        self.no_filters_found_label.setVisible(False)

        # Clear any existing widgets from the layout
        while self.filters_layout.count():
            item = self.filters_layout.takeAt(0)
            widget = item.widget()
            if widget and widget not in [self.no_filters_found_label, self.loading_label]:
                 widget.deleteLater()

        self.task_filters.clear()

        # Remove loading label if it exists
        if self.loading_label:
            self.loading_label.deleteLater()
            self.loading_label = None

        if not tags:
            # If no tags are returned, show an error message.
            # This can happen on first load with no network, or if API fails.
            self.filters_layout.addWidget(QLabel("Could not load filters."))
            return

        # Create and add a checkbox for each tag
        for tag in sorted(tags): # Sort for consistent UI
            checkbox = QCheckBox(self._format_tag_name(tag))
            self.task_filters[tag] = checkbox
            self.filters_layout.addWidget(checkbox)

        # Add a stretch to push checkboxes to the top
        self.filters_layout.addStretch()