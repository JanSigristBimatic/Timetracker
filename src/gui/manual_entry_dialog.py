"""Dialog for adding manual activity entries (meetings, offline work)."""

from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from core.database_protocol import DatabaseProtocol

MANUAL_APP_NAME = 'Manueller Eintrag'


class ManualEntryDialog(QDialog):
    """Add a manual activity (e.g. a meeting or on-site work)."""

    def __init__(
        self,
        database: DatabaseProtocol,
        start: Optional[datetime] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.database = database

        if start is None:
            start = datetime.now().replace(minute=0, second=0, microsecond=0)

        self.setup_ui(start)

    def setup_ui(self, start: datetime):
        """Setup the user interface"""
        self.setWindowTitle("Manueller Eintrag")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Zeit nachtragen, die nicht am PC erfasst wurde "
            "(Meeting, Telefonat, Aussentermin)."
        )
        info.setWordWrap(True)
        info.setProperty("class", "muted")
        layout.addWidget(info)

        form = QFormLayout()

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("z.B. Baustellenbesprechung")
        form.addRow("Beschreibung:", self.description_input)

        self.start_edit = QDateTimeEdit(QDateTime(start))
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        form.addRow("Start:", self.start_edit)

        self.end_edit = QDateTimeEdit(QDateTime(start + timedelta(hours=1)))
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        form.addRow("Ende:", self.end_edit)

        self.project_combo = QComboBox()
        self.project_combo.addItem("Kein Projekt", None)
        for project in self.database.get_projects():
            self.project_combo.addItem(project['name'], project['id'])
        form.addRow("Projekt:", self.project_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_entry)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_entry(self):
        """Validate and store the manual activity"""
        start = self.start_edit.dateTime().toPyDateTime()
        end = self.end_edit.dateTime().toPyDateTime()

        if end <= start:
            QMessageBox.warning(
                self, "Ungültiger Zeitraum",
                "Das Ende muss nach dem Start liegen."
            )
            return

        description = self.description_input.text().strip() or "Manuell erfasst"

        activity_id = self.database.save_activity(
            app_name=MANUAL_APP_NAME,
            window_title=description,
            start_time=start,
            end_time=end,
        )

        project_id = self.project_combo.currentData()
        if activity_id and project_id is not None:
            self.database.assign_activity_to_project(activity_id, project_id)

        self.accept()
