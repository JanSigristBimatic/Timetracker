from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QLabel,
    QColorDialog, QMessageBox
)
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt


class ProjectManagerDialog(QDialog):
    """Dialog for managing projects"""

    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.setup_ui()
        self.load_projects()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Projekte verwalten")
        self.setGeometry(200, 200, 500, 400)

        layout = QVBoxLayout(self)

        # Project list
        list_label = QLabel("Projekte:")
        layout.addWidget(list_label)

        self.project_list = QListWidget()
        layout.addWidget(self.project_list)

        # Add project section
        add_layout = QHBoxLayout()

        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Neuer Projektname...")
        add_layout.addWidget(self.project_name_input)

        self.color_btn = QPushButton("Farbe wählen")
        self.color_btn.clicked.connect(self.choose_color)
        add_layout.addWidget(self.color_btn)

        self.selected_color = QColor(52, 152, 219)  # Default blue
        self.update_color_button()

        add_btn = QPushButton("Hinzufügen")
        add_btn.clicked.connect(self.add_project)
        add_layout.addWidget(add_btn)

        layout.addLayout(add_layout)

        # Delete button
        delete_btn = QPushButton("Ausgewähltes Projekt löschen")
        delete_btn.clicked.connect(self.delete_project)
        layout.addWidget(delete_btn)

        # Close button
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def load_projects(self):
        """Load projects from database"""
        self.project_list.clear()
        projects = self.database.get_projects()

        for project in projects:
            item = QListWidgetItem(project['name'])
            item.setData(Qt.ItemDataRole.UserRole, project['id'])

            # Set color
            color = QColor(project['color']) if project['color'] else QColor(52, 152, 219)
            item.setForeground(QBrush(color))

            self.project_list.addItem(item)

    def choose_color(self):
        """Open color picker"""
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
            QMessageBox.warning(self, "Fehler", "Bitte geben Sie einen Projektnamen ein.")
            return

        try:
            self.database.create_project(name, self.selected_color.name())
            self.project_name_input.clear()
            self.selected_color = QColor(52, 152, 219)
            self.update_color_button()
            self.load_projects()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Projekt konnte nicht erstellt werden: {e}")

    def delete_project(self):
        """Delete selected project"""
        current_item = self.project_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Fehler", "Bitte wählen Sie ein Projekt aus.")
            return

        project_id = current_item.data(Qt.ItemDataRole.UserRole)
        project_name = current_item.text()

        reply = QMessageBox.question(
            self, "Projekt löschen",
            f"Möchten Sie das Projekt '{project_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                cursor = self.database.conn.cursor()
                cursor.execute('DELETE FROM projects WHERE id = %s', (project_id,))
                self.database.conn.commit()
                cursor.close()
                self.load_projects()
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Projekt konnte nicht gelöscht werden: {e}")
