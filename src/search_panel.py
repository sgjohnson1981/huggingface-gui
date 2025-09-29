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
from PySide6.QtCore import Signal


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
        self.filters_layout = QVBoxLayout()
        self.task_filters = {}

        # Initially, show a loading message
        self.loading_label = QLabel("Loading filters...")
        self.filters_layout.addWidget(self.loading_label)

        self.filters_group.setLayout(self.filters_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.filters_group)


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
        self.layout.addWidget(scroll)
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
        """
        # Clear the "Loading..." label
        if self.loading_label:
            self.filters_layout.removeWidget(self.loading_label)
            self.loading_label.deleteLater()
            self.loading_label = None

        if not tags:
            # If no tags are returned, show an error message
            self.filters_layout.addWidget(QLabel("Could not load filters."))
            return

        # Create and add a checkbox for each tag
        for tag in tags:
            checkbox = QCheckBox(self._format_tag_name(tag))
            self.task_filters[tag] = checkbox
            self.filters_layout.addWidget(checkbox)

        # Add a stretch to push checkboxes to the top
        self.filters_layout.addStretch()