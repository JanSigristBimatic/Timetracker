"""Dialog for managing automatic assignment rules."""

from datetime import datetime, timedelta
from typing import Optional

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

APPLY_PERIODS = [
    ("Letzte 7 Tage", 7),
    ("Letzter Monat", 30),
    ("Letzte 3 Monate", 90),
    ("Gesamter Zeitraum", None),
]


class RulesDialog(QDialog):
    """Manage deterministic project assignment rules."""

    def __init__(self, database: DatabaseProtocol, parent=None):
        super().__init__(parent)
        self.database = database
        self.editing_rule_id: Optional[int] = None
        self._rules: list[dict] = []
        self.setup_ui()
        self.load_rules()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Zuordnungsregeln")
        self.setMinimumSize(760, 520)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Regeln ordnen neue Aktivitäten automatisch einem Projekt zu. "
            "Die erste zutreffende Regel gewinnt. Regeln haben Vorrang vor "
            "der KI-Zuordnung. Doppelklick auf eine Regel öffnet sie zum "
            "Bearbeiten."
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
        self.table.itemDoubleClicked.connect(
            lambda item: self.start_editing(item.row())
        )
        layout.addWidget(self.table)

        # Table actions
        table_actions = QHBoxLayout()

        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setToolTip("Ausgewählte Regel in die Eingabezeile laden")
        edit_btn.clicked.connect(self.edit_selected_rule)
        table_actions.addWidget(edit_btn)

        delete_btn = QPushButton("Löschen")
        delete_btn.clicked.connect(self.delete_rule)
        table_actions.addWidget(delete_btn)

        table_actions.addStretch()
        layout.addLayout(table_actions)

        # Add/edit rule row
        self.edit_hint = QLabel("Regel bearbeiten:")
        self.edit_hint.setProperty("class", "subtitle")
        self.edit_hint.setVisible(False)
        layout.addWidget(self.edit_hint)

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
        self.pattern_input.returnPressed.connect(self.save_rule)
        add_layout.addWidget(self.pattern_input, stretch=1)

        self.project_combo = QComboBox()
        add_layout.addWidget(self.project_combo)

        self.save_btn = QPushButton("Hinzufügen")
        self.save_btn.setProperty("class", "primary")
        self.save_btn.clicked.connect(self.save_rule)
        add_layout.addWidget(self.save_btn)

        self.cancel_edit_btn = QPushButton("Abbrechen")
        self.cancel_edit_btn.setToolTip("Bearbeitung verwerfen")
        self.cancel_edit_btn.clicked.connect(self.cancel_editing)
        self.cancel_edit_btn.setVisible(False)
        add_layout.addWidget(self.cancel_edit_btn)

        layout.addLayout(add_layout)

        # Apply row
        apply_layout = QHBoxLayout()

        apply_layout.addWidget(QLabel("Regeln anwenden auf:"))

        self.apply_period_combo = QComboBox()
        for label, days in APPLY_PERIODS:
            self.apply_period_combo.addItem(label, days)
        self.apply_period_combo.setToolTip(
            "Zeitraum, in dem nicht zugeordnete Aktivitäten "
            "per Regel zugeordnet werden"
        )
        apply_layout.addWidget(self.apply_period_combo)

        apply_btn = QPushButton("Jetzt anwenden")
        apply_btn.setToolTip(
            "Wendet alle aktiven Regeln auf nicht zugeordnete "
            "Aktivitäten im gewählten Zeitraum an"
        )
        apply_btn.clicked.connect(self.apply_rules)
        apply_layout.addWidget(apply_btn)

        apply_layout.addStretch()

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        apply_layout.addWidget(close_btn)

        layout.addLayout(apply_layout)

    def load_rules(self):
        """Load rules and projects from the database"""
        self.projects = self.database.get_projects()
        project_map = {p['id']: p['name'] for p in self.projects}

        current_project = self.project_combo.currentData()
        self.project_combo.clear()
        for project in self.projects:
            self.project_combo.addItem(project['name'], project['id'])
        if current_project is not None:
            index = self.project_combo.findData(current_project)
            if index >= 0:
                self.project_combo.setCurrentIndex(index)

        self._rules = self.database.get_project_rules()
        self.table.setRowCount(0)

        for rule in self._rules:
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

    # ------------------------------------------------------------------
    # Create / edit
    # ------------------------------------------------------------------

    def save_rule(self):
        """Create a new rule or save the rule being edited"""
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

        field = self.field_combo.currentData()
        match_type = self.match_combo.currentData()

        if self.editing_rule_id is not None:
            self.database.update_project_rule(
                self.editing_rule_id, project_id, field, pattern, match_type
            )
            self.cancel_editing()
        else:
            self.database.create_project_rule(
                project_id=project_id,
                field=field,
                pattern=pattern,
                match_type=match_type,
            )
            self.pattern_input.clear()

        self.load_rules()

    def edit_selected_rule(self):
        """Load the selected rule into the edit row"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Fehler", "Bitte eine Regel auswählen.")
            return
        self.start_editing(row)

    def start_editing(self, row: int):
        """Enter edit mode for the rule at the given table row"""
        if row < 0 or row >= len(self._rules):
            return

        rule = self._rules[row]
        self.editing_rule_id = rule['id']

        field_index = self.field_combo.findData(rule['field'])
        if field_index >= 0:
            self.field_combo.setCurrentIndex(field_index)

        match_index = self.match_combo.findData(rule['match_type'])
        if match_index >= 0:
            self.match_combo.setCurrentIndex(match_index)

        self.pattern_input.setText(rule['pattern'])

        project_index = self.project_combo.findData(rule['project_id'])
        if project_index >= 0:
            self.project_combo.setCurrentIndex(project_index)

        self.edit_hint.setVisible(True)
        self.save_btn.setText("Speichern")
        self.cancel_edit_btn.setVisible(True)
        self.pattern_input.setFocus()

    def cancel_editing(self):
        """Leave edit mode without saving"""
        self.editing_rule_id = None
        self.pattern_input.clear()
        self.edit_hint.setVisible(False)
        self.save_btn.setText("Hinzufügen")
        self.cancel_edit_btn.setVisible(False)

    def delete_rule(self):
        """Delete the selected rule"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Fehler", "Bitte eine Regel auswählen.")
            return

        rule_id = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        if rule_id == self.editing_rule_id:
            self.cancel_editing()

        self.database.delete_project_rule(rule_id)
        self.load_rules()

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply_rules(self):
        """Apply all enabled rules to unassigned activities in the
        selected period ('Gesamter Zeitraum' means all data)."""
        days_back = self.apply_period_combo.currentData()

        start_date = None
        if days_back is not None:
            start_date = datetime.now() - timedelta(days=days_back)

        activities = self.database.get_activities(
            start_date=start_date, end_date=datetime.now()
        )
        assigned = apply_rules_to_activities(self.database, activities)

        period_label = self.apply_period_combo.currentText()
        QMessageBox.information(
            self,
            "Regeln angewendet",
            f"{assigned} Aktivitäten wurden zugeordnet "
            f"({period_label}, {len(activities)} Aktivitäten geprüft)."
        )
