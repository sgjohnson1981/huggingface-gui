from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

class ClickableLabel(QLabel):
    clicked = Signal(str)

    def __init__(self, text, data=None, parent=None):
        super().__init__(text, parent)
        self.data = data
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet("color: #3b82f6; text-decoration: underline;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.data)
        super().mousePressEvent(event)

class ModelTreeWidget(QWidget):
    # Signals for navigation and searching
    modelClicked = Signal(str)  # Navigates to a specific model ID
    filterClicked = Signal(str)  # Triggers a search with a filter (e.g. "base_model:finetune:...")

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)
        
        self.setVisible(False)
        self.setStyleSheet("""
            #tree_container {
                background-color: #1a1a1a;
                border-radius: 8px;
                border: 1px solid #333333;
                color: #e5e7eb;
            }
            QLabel {
                background: transparent;
            }
            QLabel#header {
                font-weight: bold;
                font-size: 13px;
                color: #ffffff;
                margin-bottom: 5px;
            }
            QLabel#label {
                color: #9ca3af;
                font-size: 12px;
            }
            QLabel#badge {
                background-color: #1e3a8a;
                color: #bfdbfe;
                padding: 1px 6px;
                border-radius: 8px;
                font-size: 10px;
            }
        """)
        
        self.container = QFrame()
        self.container.setObjectName("tree_container")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        self.container_layout.setSpacing(2)
        
        self.layout.addWidget(self.container)

    def _clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                elif item.layout() is not None:
                    self._clear_layout(item.layout())
                    item.layout().deleteLater()

    def set_relationships(self, model_id, relationships):
        """
        Populates the widget with relationship data.
        """
        # Clear existing layout inside container
        self._clear_layout(self.container_layout)

        if not relationships:
            self.setVisible(False)
            return

        self.setVisible(True)

        # Header
        header = QLabel(f"Model tree for {model_id}")
        header.setObjectName("header")
        self.container_layout.addWidget(header)

        # Base Model
        if relationships.get("base_model"):
            base_layout = QHBoxLayout()
            base_label = QLabel("Base model")
            base_label.setObjectName("label")
            
            base_link = ClickableLabel(relationships["base_model"], relationships["base_model"])
            base_link.clicked.connect(self.modelClicked.emit)
            
            base_layout.addWidget(base_label)
            base_layout.addSpacing(10)
            base_layout.addWidget(base_link)
            base_layout.addStretch()
            self.container_layout.addLayout(base_layout)

            # Branch icon for current model
            branch_layout = QHBoxLayout()
            branch_layout.setContentsMargins(10, 0, 0, 0)
            
            branch_label = QLabel("└──")
            branch_label.setObjectName("label")
            
            model_type = "Finetuned" if relationships.get("this_model_is_finetune") else "Model"
            type_label = QLabel(model_type)
            type_label.setObjectName("label")
            
            badge = QLabel("this model")
            badge.setObjectName("badge")
            
            branch_layout.addWidget(branch_label)
            branch_layout.addWidget(type_label)
            branch_layout.addSpacing(10)
            branch_layout.addWidget(badge)
            branch_layout.addStretch()
            self.container_layout.addLayout(branch_layout)

            # Children of this model
            child_indent = 30
            
            for key, label in [("adapters", "Adapters"), ("finetunes", "Finetunes"), ("quantizations", "Quantizations")]:
                count = relationships.get(key, 0)
                if count > 0:
                    child_layout = QHBoxLayout()
                    child_layout.setContentsMargins(child_indent, 0, 0, 0)
                    
                    child_branch = QLabel("├──" if key != "quantizations" else "└──")
                    child_branch.setObjectName("label")
                    
                    child_name = QLabel(label)
                    child_name.setObjectName("label")
                    
                    link_text = f"{count} models"
                    filter_str = f"base_model:{key[:-1]}:{model_id}" if key != "quantizations" else f"base_model:quantized:{model_id}"
                    if key == "finetunes":
                        filter_str = f"base_model:finetune:{model_id}"
                    elif key == "adapters":
                        filter_str = f"base_model:adapter:{model_id}"
                    
                    link = ClickableLabel(link_text, filter_str)
                    link.clicked.connect(self.filterClicked.emit)
                    
                    child_layout.addWidget(child_branch)
                    child_layout.addWidget(child_name)
                    child_layout.addSpacing(10)
                    child_layout.addWidget(link)
                    child_layout.addStretch()
                    self.container_layout.addLayout(child_layout)
        else:
            # If no base model, this might be a base model itself.
            # We can still show its children.
            model_label = QLabel(model_id)
            model_label.setObjectName("label")
            self.container_layout.addWidget(model_label)
            
            for key, label in [("adapters", "Adapters"), ("finetunes", "Finetunes"), ("quantizations", "Quantizations")]:
                count = relationships.get(key, 0)
                if count > 0:
                    child_layout = QHBoxLayout()
                    child_layout.setContentsMargins(20, 0, 0, 0)
                    
                    child_branch = QLabel("├──" if key != "quantizations" else "└──")
                    child_branch.setObjectName("label")
                    
                    child_name = QLabel(label)
                    child_name.setObjectName("label")
                    
                    filter_str = f"base_model:{key[:-1]}:{model_id}" if key != "quantizations" else f"base_model:quantized:{model_id}"
                    if key == "finetunes":
                        filter_str = f"base_model:finetune:{model_id}"
                    elif key == "adapters":
                        filter_str = f"base_model:adapter:{model_id}"
                        
                    link = ClickableLabel(f"{count} models", filter_str)
                    link.clicked.connect(self.filterClicked.emit)
                    
                    child_layout.addWidget(child_branch)
                    child_layout.addWidget(child_name)
                    child_layout.addSpacing(10)
                    child_layout.addWidget(link)
                    child_layout.addStretch()
                    self.container_layout.addLayout(child_layout)
