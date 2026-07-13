"""Dialog for managing automatic assignment rules."""

from datetime import datetime, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.database_protocol import DatabaseProtocol
from utils.assignment_rules import (
    FIELD_APP,
    FIELD_LABELS,
    FIELD_TITLE,
    MATCH_CONTAINS,
    MATCH_LABELS,
    MATCH_REGEX,
    apply_rules_to_activities,
)


class RulesDialog(QDialog):
    """Manage deterministic project assignment rules."""

    def __init__(self, database: DatabaseProtocol, parent=None):
        super().__init__(parent)
        self.database = database
        self.setup_ui()
        self.load_rules()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Zuordnungsregeln")
        self.setMinimumSize(720, 480)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Regeln ordnen neue Aktivitäten automatisch einem Projekt zu. "
            "Die erste zutreffende Regel gewinnt. Regeln haben Vorrang vor "
            "der KI-Zuordnung."
        )
        info.setWordWrap(True)
        info.setProperty("class", "muted")
        layout.addWidget(info)

        # Rules table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Aktiv", "Feld", "Bedingung", "Muster", "Projekt"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # New rule row
        add_layout = QHBoxLayout()

        self.field_combo = QComboBox()
        self.field_combo.addItem(FIELD_LABELS[FIELD_TITLE], FIELD_TITLE)
        self.field_combo.addItem(FIELD_LABELS[FIELD_APP], FIELD_APP)
        add_layout.addWidget(self.field_combo)

        self.match_combo = QComboBox()
        self.match_combo.addItem(MATCH_LABELS[MATCH_CONTAINS], MATCH_CONTAINS)
        self.match_combo.addItem(MATCH_LABELS[MATCH_REGEX], MATCH_REGEX)
        add_layout.addWidget(self.match_combo)

        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("Muster, z.B. 'Bahnhof' oder 'chrome.exe'")
        self.pattern_input.returnPressed.connect(self.add_rule)
        add_layout.addWidget(self.pattern_input, stretch=1)

        self.project_combo = QComboBox()
        add_layout.addWidget(self.project_combo)

        add_btn = QPushButton("Hinzufügen")
        add_btn.setProperty("class", "primary")
        add_btn.clicked.connect(self.add_rule)
        add_layout.addWidget(add_btn)

        layout.addLayout(add_layout)

        # Action buttons
        button_layout = QHBoxLayout()

        delete_btn = QPushButton("Ausgewählte Regel löschen")
        delete_btn.clicked.connect(self.delete_rule)
        button_layout.addWidget(delete_btn)

        apply_btn = QPushButton("Auf letzte 7 Tage anwenden")
        apply_btn.setToolTip(
            "Wendet alle aktiven Regeln auf nicht zugeordnete "
            "Aktivitäten der letzten 7 Tage an"
        )
        apply_btn.clicked.connect(self.apply_to_recent)
        button_layout.addWidget(apply_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_rules(self):
        """Load rules and projects from the database"""
        self.projects = self.database.get_projects()
        project_map = {p['id']: p['name'] for p in self.projects}

        self.project_combo.clear()
        for project in self.projects:
            self.project_combo.addItem(project['name'], project['id'])

        rules = self.database.get_project_rules()
        self.table.setRowCount(0)

        for rule in rules:
            row = self.table.rowCount()
            self.table.insertRow(row)

            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(bool(rule['enabled']))
            enabled_checkbox.toggled.connect(
                lambda checked, rule_id=rule['id']:
                self.database.set_project_rule_enabled(rule_id, checked)
            )
            self.table.setCellWidget(row, 0, enabled_checkbox)

            field_item = QTableWidgetItem(
                FIELD_LABELS.get(rule['field'], rule['field'])
            )
            field_item.setData(Qt.ItemDataRole.UserRole, rule['id'])
            self.table.setItem(row, 1, field_item)

            self.table.setItem(row, 2, QTableWidgetItem(
                MATCH_LABELS.get(rule['match_type'], rule['match_type'])
            ))
            self.table.setItem(row, 3, QTableWidgetItem(rule['pattern']))
            self.table.setItem(row, 4, QTableWidgetItem(
                project_map.get(rule['project_id'], f"? (ID {rule['project_id']})")
            ))

    def add_rule(self):
        """Create a new rule from the input row"""
        pattern = self.pattern_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Fehler", "Bitte ein Muster eingeben.")
            return

        project_id = self.project_combo.currentData()
        if project_id is None:
            QMessageBox.warning(
                self, "Fehler",
                "Kein Projekt vorhanden. Bitte zuerst ein Projekt anlegen."
            )
            return

        self.database.create_project_rule(
            project_id=project_id,
            field=self.field_combo.currentData(),
            pattern=pattern,
            match_type=self.match_combo.currentData(),
        )

        self.pattern_input.clear()
        self.load_rules()

    def delete_rule(self):
        """Delete the selected rule"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Fehler", "Bitte eine Regel auswählen.")
            return

        rule_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        self.database.delete_project_rule(rule_id)
        self.load_rules()

    def apply_to_recent(self):
        """Apply all enabled rules to unassigned activities (last 7 days)"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        activities = self.database.get_activities(
            start_date=start_date, end_date=end_date
        )
        assigned = apply_rules_to_activities(self.database, activities)

        QMessageBox.information(
            self,
            "Regeln angewendet",
            f"{assigned} Aktivitäten wurden zugeordnet."
        )
