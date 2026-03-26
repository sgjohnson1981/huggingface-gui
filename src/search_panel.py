from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QScrollArea,
    QCheckBox,
    QGroupBox,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal, QTimer, Qt


class FilterChip(QFrame):
    removed = Signal(str)

    def __init__(self, text, tag, parent=None):
        super().__init__(parent)
        self.tag = tag
        self.setObjectName("filter_chip")
        
        # Styling to look like a chip
        self.setStyleSheet("""
            QFrame#filter_chip {
                background-color: #2a82da;
                border-radius: 12px;
                padding: 2px 6px;
            }
            QLabel {
                color: white;
                font-weight: bold;
                background: transparent;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 0;
                margin: 0;
            }
            QPushButton:hover {
                color: #ffcccc;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        self.label = QLabel(text)
        layout.addWidget(self.label)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setFixedSize(16, 16)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        layout.addWidget(self.remove_btn)
        
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def _on_remove_clicked(self):
        self.removed.emit(self.tag)


class SearchPanel(QWidget):
    search_triggered = Signal(dict)
    cancel_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Active Chips Layout
        self.active_chips = {}  # tag -> FilterChip
        self.active_chips_layout = QHBoxLayout()
        self.active_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.active_chips_layout.setSpacing(5)
        self.active_chips_layout.setAlignment(Qt.AlignLeft)

        # Search Query with Help Icon
        search_query_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for models (supports AND, OR, NOT)...")
        search_help_text = (
            "Enter keywords or complex queries using boolean operators:\n"
            "- AND / &: Both terms must match\n"
            "- OR / |: Either term can match\n"
            "- NOT / !: Exclude terms\n"
            "- ( ): Use parentheses to group conditions\n"
            "- \" \": Use quotes for exact phrases\n\n"
            "Use 'Strict keyword matching' below to disable fuzzy results like 'evaluation' for 'evolution'."
        )
        # Remove tooltip from text box as requested
        self.search_input.textChanged.connect(self.update_clear_button_visibility)
        
        self.help_icon = QLabel("❓")
        self.help_icon.setToolTip(search_help_text)
        self.help_icon.setCursor(Qt.PointingHandCursor)
        self.help_icon.setStyleSheet("font-size: 16px; margin-left: 5px; color: #2a82da;")
        
        search_query_layout.addWidget(self.search_input)
        search_query_layout.addWidget(self.help_icon)

        # Full Text Search Checkbox
        self.full_text_checkbox = QCheckBox("Full-text search (READMEs)")
        self.full_text_checkbox.setToolTip("Search within model cards/READMEs instead of just by title/ID.")
        self.full_text_checkbox.stateChanged.connect(self.update_clear_button_visibility)

        # Strict Search Checkbox (only for Full Text)
        self.strict_search_checkbox = QCheckBox("Strict keyword matching")
        self.strict_search_checkbox.setToolTip("Disable fuzzy matching (e.g. searching 'evolution' won't return 'evaluation').")
        self.strict_search_checkbox.setEnabled(False) # Only enabled if full_text is checked
        self.full_text_checkbox.stateChanged.connect(lambda state: self.strict_search_checkbox.setEnabled(state == 2))
        self.strict_search_checkbox.stateChanged.connect(self.update_clear_button_visibility)

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
        self.filter_search_input.textChanged.connect(
            self.update_clear_button_visibility
        )
        self.filter_search_input.textChanged.connect(self.update_select_buttons_text)

        self.filter_search_timer = QTimer(self)
        self.filter_search_timer.setSingleShot(True)
        self.filter_search_timer.setInterval(300) # 300ms debounce delay
        self.filter_search_timer.timeout.connect(self.perform_filter_search)

        filters_group_layout.addWidget(self.filter_search_input)

        # Select All / Deselect All buttons
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.select_all_filters)
        self.deselect_all_button = QPushButton("Deselect All")
        self.deselect_all_button.clicked.connect(self.deselect_all_filters)

        select_buttons_layout = QHBoxLayout()
        select_buttons_layout.addWidget(self.select_all_button)
        select_buttons_layout.addWidget(self.deselect_all_button)
        filters_group_layout.addLayout(select_buttons_layout)

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

        # Search, Clear and Cancel Buttons
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search_clicked)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_search_inputs)
        self.clear_button.setVisible(False)  # Initially hidden
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_triggered.emit)
        self.cancel_button.setVisible(False)  # Initially hidden

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.search_button)
        button_layout.addWidget(self.clear_button)

        search_vlayout = QVBoxLayout()
        search_vlayout.addLayout(self.active_chips_layout)
        search_vlayout.addLayout(search_query_layout)

        # Layout
        form_layout = QFormLayout()
        form_layout.addRow(search_vlayout)
        form_layout.addRow(self.full_text_checkbox)
        form_layout.addRow(self.strict_search_checkbox)
        form_layout.addRow(QLabel("Sort by:"))
        form_layout.addRow(self.sort_combo)

        self.layout.addLayout(form_layout)
        self.layout.addWidget(self.filters_group, 1)  # Allow filter list to expand
        self.layout.addLayout(button_layout)
        self.layout.addWidget(self.cancel_button)

    def add_filter_chip(self, tag):
        """Adds a visual filter chip above the search bar."""
        if tag in self.active_chips:
            return

        formatted_text = self._format_tag_name(tag)
        # Custom formatting for base_model relationships
        if tag.startswith("base_model:"):
            parts = tag.split(":")
            if len(parts) >= 3:
                rel_type = parts[1].capitalize()
                base_name = ":".join(parts[2:])
                formatted_text = f"{rel_type} of {base_name}"
            else:
                formatted_text = tag

        chip = FilterChip(formatted_text, tag)
        chip.removed.connect(self.remove_filter_chip)
        
        self.active_chips[tag] = chip
        self.active_chips_layout.addWidget(chip)
        self.update_clear_button_visibility()

    def remove_filter_chip(self, tag):
        """Removes a filter chip and triggers a new search."""
        if tag in self.active_chips:
            chip = self.active_chips.pop(tag)
            self.active_chips_layout.removeWidget(chip)
            chip.deleteLater()
            self.update_clear_button_visibility()
            # Automatically trigger search when a chip is removed
            self.on_search_clicked()

    def get_active_chips(self):
        """Returns a list of tags currently active as chips."""
        return list(self.active_chips.keys())

    def clear_search_inputs(self):
        """Clears all search and filter inputs."""
        self.search_input.clear()
        self.full_text_checkbox.setChecked(False)
        self.strict_search_checkbox.setChecked(False)
        self.filter_search_input.clear()
        for checkbox in self.task_filters.values():
            checkbox.setChecked(False)
        
        # Clear chips
        for tag in list(self.active_chips.keys()):
            chip = self.active_chips.pop(tag)
            self.active_chips_layout.removeWidget(chip)
            chip.deleteLater()
            
        self.update_clear_button_visibility()

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
        
        # Include active chips
        selected_filters.extend(self.get_active_chips())

        return {
            "search_query": self.search_input.text(),
            "full_text": self.full_text_checkbox.isChecked(),
            "strict": self.strict_search_checkbox.isChecked(),
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
        self.update_select_buttons_text()

    def update_select_buttons_text(self):
        """Updates the text of the 'Select All'/'Deselect All' buttons."""
        if self.filter_search_input.text():
            self.select_all_button.setText("Select All Visible")
            self.deselect_all_button.setText("Deselect All Visible")
        else:
            self.select_all_button.setText("Select All")
            self.deselect_all_button.setText("Deselect All")

    def select_all_filters(self, select=True):
        """Selects or deselects all filters."""
        search_text = self.filter_search_input.text()
        for checkbox in self.task_filters.values():
            if not search_text or checkbox.isVisible():
                checkbox.setChecked(select)
        self.update_clear_button_visibility()

    def deselect_all_filters(self):
        """Deselects all filters."""
        self.select_all_filters(select=False)

    def set_enabled(self, enabled):
        """Enable or disable the search panel widgets."""
        self.search_input.setEnabled(enabled)
        self.sort_combo.setEnabled(enabled)
        self.filters_group.setEnabled(enabled)
        self.search_button.setEnabled(enabled)

    def set_searching_state(self, searching):
        """Toggles the UI between searching and idle states."""
        self.set_enabled(not searching)
        self.search_button.setVisible(not searching)
        self.cancel_button.setVisible(searching)

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
            checkbox.stateChanged.connect(self.update_clear_button_visibility)
            self.task_filters[tag] = checkbox
            self.filters_layout.addWidget(checkbox)

        # Add a stretch to push checkboxes to the top
        self.filters_layout.addStretch()

    def update_clear_button_visibility(self):
        """Shows or hides the clear button based on input fields and checkboxes."""
        has_search_text = bool(self.search_input.text())
        has_filter_text = bool(self.filter_search_input.text())
        has_checked_filter = any(
            cb.isChecked() for cb in self.task_filters.values()
        )
        has_chips = len(self.active_chips) > 0
        has_full_text = self.full_text_checkbox.isChecked()
        self.clear_button.setVisible(
            has_search_text or has_filter_text or has_checked_filter or has_chips or has_full_text
        )