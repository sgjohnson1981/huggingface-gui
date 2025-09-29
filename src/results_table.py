from PySide6.QtCore import QAbstractTableModel, Qt, QSortFilterProxyModel
from PySide6.QtWidgets import QTableView, QHeaderView, QMenu


class ResultsTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = [
            "Model ID",
            "Author",
            "Task",
            "Downloads",
            "Likes",
            "Last Updated",
        ]
        self._column_visibility = [True] * len(self._headers)

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return sum(self._column_visibility)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            row_data = self._data[index.row()]
            visible_col_index = self._get_visible_column_index(index.column())

            if visible_col_index == 0:
                return row_data.id
            elif visible_col_index == 1:
                return row_data.author
            elif visible_col_index == 2:
                return getattr(row_data, 'pipeline_tag', 'N/A')
            elif visible_col_index == 3:
                return row_data.downloads
            elif visible_col_index == 4:
                return row_data.likes
            elif visible_col_index == 5:
                return row_data.lastModified.strftime("%Y-%m-%d")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._get_visible_header(section)
        return None

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_column_visibility(self):
        return self._column_visibility

    def set_column_visibility(self, visibility):
        self.beginResetModel()
        self._column_visibility = visibility
        self.endResetModel()

    def _get_visible_column_index(self, visible_index):
        count = -1
        for i, visible in enumerate(self._column_visibility):
            if visible:
                count += 1
            if count == visible_index:
                return i
        return -1

    def _get_visible_header(self, visible_index):
        count = -1
        for i, header in enumerate(self._headers):
            if self._column_visibility[i]:
                count += 1
            if count == visible_index:
                return header
        return None

    def get_headers(self):
        return self._headers


class ResultsTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setEditTriggers(QTableView.NoEditTriggers)

        self.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self.header_context_menu)

    def set_model(self, model):
        proxy_model = QSortFilterProxyModel()
        proxy_model.setSourceModel(model)
        self.setModel(proxy_model)
        self.base_model = model

    def header_context_menu(self, pos):
        menu = QMenu()
        all_headers = self.base_model.get_headers()
        visibility = self.base_model.get_column_visibility()

        for i, header in enumerate(all_headers):
            action = menu.addAction(header)
            action.setCheckable(True)
            action.setChecked(visibility[i])
            action.triggered.connect(lambda checked, index=i: self.toggle_column(index))

        menu.exec_(self.horizontalHeader().mapToGlobal(pos))

    def toggle_column(self, index):
        visibility = self.base_model.get_column_visibility()
        visibility[index] = not visibility[index]
        self.base_model.set_column_visibility(visibility)