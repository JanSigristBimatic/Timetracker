from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.database_protocol import DatabaseProtocol

DEFAULT_COLOR = QColor(52, 152, 219)


class ProjectManagerDialog(QDialog):
    """Dialog for managing projects"""

    def __init__(self, database: DatabaseProtocol, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.database = database
        self.setup_ui()
        self.load_projects()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Projekte verwalten")
        self.setGeometry(200, 200, 500, 420)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Projekte (Doppelklick zum Umbenennen):"))

        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(lambda _item: self.rename_project())
        layout.addWidget(self.project_list)

        # Actions on the selected project
        edit_layout = QHBoxLayout()

        rename_btn = QPushButton("Umbenennen")
        rename_btn.clicked.connect(self.rename_project)
        edit_layout.addWidget(rename_btn)

        recolor_btn = QPushButton("Farbe ändern")
        recolor_btn.clicked.connect(self.recolor_project)
        edit_layout.addWidget(recolor_btn)

        delete_btn = QPushButton("Löschen")
        delete_btn.clicked.connect(self.delete_project)
        edit_layout.addWidget(delete_btn)

        edit_layout.addStretch()
        layout.addLayout(edit_layout)

        # Add project section
        add_layout = QHBoxLayout()

        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Neuer Projektname...")
        self.project_name_input.returnPressed.connect(self.add_project)
        add_layout.addWidget(self.project_name_input)

        self.color_btn = QPushButton("Farbe wählen")
        self.color_btn.clicked.connect(self.choose_color)
        add_layout.addWidget(self.color_btn)

        self.selected_color = QColor(DEFAULT_COLOR)
        self.update_color_button()

        add_btn = QPushButton("Hinzufügen")
        add_btn.clicked.connect(self.add_project)
        add_layout.addWidget(add_btn)

        layout.addLayout(add_layout)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def load_projects(self):
        """Load projects from database"""
        self.project_list.clear()

        for project in self.database.get_projects():
            item = QListWidgetItem(project['name'])
            item.setData(Qt.ItemDataRole.UserRole, project)
            color = QColor(project['color']) if project['color'] else DEFAULT_COLOR
            item.setForeground(QBrush(color))
            self.project_list.addItem(item)

    def _selected_project(self) -> Optional[dict]:
        item = self.project_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Fehler", "Bitte ein Projekt auswählen.")
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def choose_color(self):
        """Open color picker for a new project"""
        color = QColorDialog.getColor(self.selected_color, self, "Projektfarbe wählen")
        if color.isValid():
            self.selected_color = color
            self.update_color_button()

    def update_color_button(self):
        """Update color button appearance"""
        self.color_btn.setStyleSheet(
            f"background-color: {self.selected_color.name()}; "
            f"color: {'white' if self.selected_color.lightness() < 128 else 'black'};"
        )

    def add_project(self):
        """Add a new project"""
        name = self.project_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Bitte einen Projektnamen eingeben.")
            return

        try:
            self.database.create_project(name, self.selected_color.name())
            self.project_name_input.clear()
            self.selected_color = QColor(DEFAULT_COLOR)
            self.update_color_button()
            self.load_projects()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Projekt konnte nicht erstellt werden: {e}")

    def rename_project(self):
        """Rename the selected project"""
        project = self._selected_project()
        if not project:
            return

        name, ok = QInputDialog.getText(
            self, "Projekt umbenennen", "Neuer Name:", text=project['name']
        )
        name = name.strip()
        if not ok or not name or name == project['name']:
            return

        self._update_project(project, name=name)

    def recolor_project(self):
        """Change the color of the selected project"""
        project = self._selected_project()
        if not project:
            return

        current = QColor(project['color']) if project['color'] else DEFAULT_COLOR
        color = QColorDialog.getColor(current, self, "Projektfarbe ändern")
        if color.isValid():
            self._update_project(project, color=color.name())

    def _update_project(
        self, project: dict, name: Optional[str] = None, color: Optional[str] = None
    ):
        try:
            self.database.update_project(
                project['id'], name or project['name'], color or project['color']
            )
            self.load_projects()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Projekt konnte nicht geändert werden: {e}")

    def delete_project(self):
        """Delete the selected project after showing what it affects"""
        project = self._selected_project()
        if not project:
            return

        activities = self.database.get_activities(project_id=project['id'])
        hours = sum(
            a['duration'] for a in activities if not a.get('is_idle', False)
        ) / 3600

        reply = QMessageBox.question(
            self, "Projekt löschen",
            f"Projekt '{project['name']}' wirklich löschen?\n\n"
            f"{len(activities)} Aktivitäten mit {hours:.1f} h verlieren ihre "
            f"Zuordnung, die Regeln dieses Projekts werden gelöscht. "
            f"Das kann nicht rückgängig gemacht werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.database.delete_project(project['id'])
                self.load_projects()
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Projekt konnte nicht gelöscht werden: {e}")
