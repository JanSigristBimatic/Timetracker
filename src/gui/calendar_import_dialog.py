"""Dialog for importing calendar events from an ICS file."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.database_protocol import DatabaseProtocol
from utils.ics_import import parse_ics_events

logger = logging.getLogger(__name__)

CALENDAR_APP_NAME = 'Kalender'


class CalendarImportDialog(QDialog):
    """Import ICS calendar events as activities."""

    def __init__(self, database: DatabaseProtocol, parent=None):
        super().__init__(parent)
        self.database = database
        self.events = []
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Kalender importieren (ICS)")
        self.setMinimumSize(560, 520)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Termine aus einer ICS-Datei (Outlook/Google Kalender Export) "
            "als Aktivitäten übernehmen. Serientermine und ganztägige "
            "Termine werden übersprungen. Ein Termin ersetzt die während "
            "seiner Dauer erfasste PC-Zeit, damit nichts doppelt zählt."
        )
        info.setWordWrap(True)
        info.setProperty("class", "muted")
        layout.addWidget(info)

        # File selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("Keine Datei gewählt")
        self.file_label.setProperty("class", "muted")
        file_layout.addWidget(self.file_label, stretch=1)

        browse_btn = QPushButton("ICS-Datei wählen...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Date range filter
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Von:"))

        today = QDate.currentDate()
        monday = today.addDays(-(today.dayOfWeek() - 1))

        self.start_date_edit = QDateEdit(monday)
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.dateChanged.connect(self.refresh_event_list)
        range_layout.addWidget(self.start_date_edit)

        range_layout.addWidget(QLabel("Bis:"))
        self.end_date_edit = QDateEdit(monday.addDays(6))
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.dateChanged.connect(self.refresh_event_list)
        range_layout.addWidget(self.end_date_edit)

        range_layout.addStretch()

        range_layout.addWidget(QLabel("Projekt:"))
        self.project_combo = QComboBox()
        self.project_combo.addItem("Kein Projekt", None)
        for project in self.database.get_projects():
            self.project_combo.addItem(project['name'], project['id'])
        range_layout.addWidget(self.project_combo)

        layout.addLayout(range_layout)

        # Event list with checkboxes
        self.event_list = QListWidget()
        layout.addWidget(self.event_list)

        # Buttons
        button_layout = QHBoxLayout()

        select_all_btn = QPushButton("Alle auswählen")
        select_all_btn.clicked.connect(lambda: self.set_all_checked(True))
        button_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Keine auswählen")
        select_none_btn.clicked.connect(lambda: self.set_all_checked(False))
        button_layout.addWidget(select_none_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.import_btn = QPushButton("Importieren")
        self.import_btn.setProperty("class", "primary")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.import_selected)
        button_layout.addWidget(self.import_btn)

        layout.addLayout(button_layout)

    def browse_file(self):
        """Choose and parse an ICS file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "ICS-Datei wählen",
            str(Path.home()),
            "iCalendar Dateien (*.ics);;Alle Dateien (*.*)"
        )

        if not filepath:
            return

        try:
            content = Path(filepath).read_text(encoding='utf-8', errors='replace')
            self.events = parse_ics_events(content)
            self.file_label.setText(
                f"{Path(filepath).name} ({len(self.events)} Termine)"
            )
            self.refresh_event_list()
        except OSError as e:
            QMessageBox.critical(
                self, "Fehler", f"Datei konnte nicht gelesen werden: {e}"
            )

    def refresh_event_list(self):
        """Show events within the selected date range"""
        self.event_list.clear()

        start = datetime.combine(
            self.start_date_edit.date().toPyDate(), datetime.min.time()
        )
        end = datetime.combine(
            self.end_date_edit.date().toPyDate(), datetime.max.time()
        )

        for event in self.events:
            if not (start <= event['start'] <= end):
                continue

            duration_min = int(
                (event['end'] - event['start']).total_seconds() / 60
            )
            label = (
                f"{event['start'].strftime('%a %d.%m. %H:%M')} - "
                f"{event['end'].strftime('%H:%M')}  ({duration_min} min)  "
                f"{event['summary']}"
            )

            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.event_list.addItem(item)

        self.import_btn.setEnabled(self.event_list.count() > 0)

    def set_all_checked(self, checked: bool):
        """Check or uncheck all listed events"""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.event_list.count()):
            self.event_list.item(i).setCheckState(state)

    def import_selected(self):
        """Import all checked events as activities"""
        project_id = self.project_combo.currentData()
        imported = 0

        for i in range(self.event_list.count()):
            item = self.event_list.item(i)
            if item.checkState() != Qt.CheckState.Checked:
                continue

            event = item.data(Qt.ItemDataRole.UserRole)

            # A meeting replaces the PC time tracked during it, so the
            # time is counted once and belongs to the meeting's project
            activity_id = self.database.save_activity(
                app_name=CALENDAR_APP_NAME,
                window_title=event['summary'],
                start_time=event['start'],
                end_time=event['end'],
            )

            if activity_id:
                imported += 1
                if project_id is not None:
                    self.database.assign_activity_to_project(
                        activity_id, project_id
                    )

        logger.info(f"Imported {imported} calendar events")
        QMessageBox.information(
            self, "Import abgeschlossen",
            f"{imported} Termine wurden importiert."
        )
        self.accept()
