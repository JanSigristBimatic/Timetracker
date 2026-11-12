"""
Dialog for reviewing project suggestions learned from past assignments
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.database_protocol import DatabaseProtocol
from utils.smart_project_assigner import SmartProjectAssigner

from .theme import get_theme

logger = logging.getLogger(__name__)


class AssignmentSuggestionsDialog(QDialog):
    """Review and apply project suggestions derived from assignment history"""

    def __init__(self, database: DatabaseProtocol, parent=None):
        super().__init__(parent)
        self.database = database
        self.assigner = SmartProjectAssigner(database)
        self.suggestions = []
        self.selected_suggestions = set()
        self.projects = []  # Alle verfügbaren Projekte
        self.widget_map = {}  # Map: index -> widget für Style-Updates
        self.last_clicked_index = None  # Für Shift-Klick Bereichsauswahl
        self.applied_changes: list[tuple[int, Optional[int]]] = []  # For undo
        self.theme = get_theme()

        self.setup_ui()
        self.load_suggestions()

    def setup_ui(self):
        """Setup Dialog UI"""
        self.setWindowTitle("Zuordnungsvorschläge")
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Zuordnungsvorschläge")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Info Text
        info = QLabel(
            "Vorschläge basieren auf deinen bisherigen Zuordnungen (welches Programm "
            "und welche Begriffe im Fenstertitel zu welchem Projekt gehörten). "
            "Übernommene Vorschläge lassen sich mit Strg+Z rückgängig machen.\n"
            "Tipp: Shift gedrückt halten und zwei Karten anklicken wählt einen Bereich."
        )
        info.setWordWrap(True)
        info.setProperty("class", "muted")
        layout.addWidget(info)

        # Zeitraum-Auswahl
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Zeitraum:"))

        self.period_combo = QComboBox()
        self.period_combo.addItem("Heute", 1)
        self.period_combo.addItem("Letzte 7 Tage", 7)
        self.period_combo.addItem("Letzte 30 Tage", 30)
        self.period_combo.setCurrentIndex(1)
        self.period_combo.currentIndexChanged.connect(self.load_suggestions)
        period_row.addWidget(self.period_combo)
        period_row.addStretch()

        layout.addLayout(period_row)

        # Scroll Area für Vorschläge
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.suggestions_widget = QWidget()
        self.suggestions_layout = QVBoxLayout(self.suggestions_widget)
        self.suggestions_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.suggestions_widget)
        layout.addWidget(scroll)

        # Button Bar
        button_layout = QHBoxLayout()

        select_all_btn = QPushButton("Alle auswählen")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Keine auswählen")
        select_none_btn.clicked.connect(self.select_none)
        button_layout.addWidget(select_none_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.apply_btn = QPushButton("Ausgewählte übernehmen")
        self.apply_btn.clicked.connect(self.apply_selected)
        self.apply_btn.setProperty("class", "success")
        button_layout.addWidget(self.apply_btn)

        layout.addLayout(button_layout)

    def load_suggestions(self):
        """Load suggestions for the selected period"""
        # Bestehende Einträge entfernen (bei Zeitraum-Wechsel)
        while self.suggestions_layout.count():
            child = self.suggestions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.selected_suggestions.clear()
        self.widget_map.clear()
        self.last_clicked_index = None

        # Lade alle Projekte
        self.projects = self.database.get_projects()

        days_back = self.period_combo.currentData() or 7
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        self.suggestions = self.assigner.get_suggestions_for_review(
            start_date=start_date, end_date=end_date, limit=100
        )

        self.apply_btn.setEnabled(bool(self.suggestions))

        # Zeige Anzahl
        if not self.suggestions:
            no_suggestions = QLabel("Keine Vorschläge verfügbar")
            no_suggestions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_suggestions.setProperty("class", "muted")
            self.suggestions_layout.addWidget(no_suggestions)
            self.apply_btn.setEnabled(False)
            return

        # Erstelle Widget für jeden Vorschlag
        for i, suggestion in enumerate(self.suggestions):
            suggestion_widget = self.create_suggestion_widget(i, suggestion)
            self.suggestions_layout.addWidget(suggestion_widget)
            self.widget_map[i] = suggestion_widget

        # Alle standardmäßig auswählen (außer sehr niedrige Konfidenz)
        for i, suggestion in enumerate(self.suggestions):
            if suggestion["confidence"] >= 0.5:
                self.selected_suggestions.add(i)

        self.update_checkboxes()
        self.update_all_widget_styles()
        self.update_button_text()

    def create_suggestion_widget(self, index: int, suggestion: dict) -> QWidget:
        """Erstellt Widget für einen einzelnen Vorschlag"""
        c = self.theme.colors
        widget = QWidget()
        widget.setObjectName(f"suggestion_card_{index}")  # Unique identifier
        widget.setStyleSheet(
            f"QWidget#suggestion_card_{index} {{ background-color: {c.card_background}; border: 1px solid {c.border}; "
            f"border-radius: 8px; padding: 10px; margin: 2px; }} "
            f"QWidget#suggestion_card_{index}:hover {{ background-color: {c.background_tertiary}; border-color: {c.accent}; }}"
        )
        widget.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Top Row: Checkbox + Confidence
        top_row = QHBoxLayout()

        checkbox = QCheckBox()
        checkbox.stateChanged.connect(
            lambda state, idx=index: self.toggle_suggestion(idx, state)
        )
        checkbox.setObjectName(f"checkbox_{index}")
        top_row.addWidget(checkbox)

        # Confidence Badge
        confidence = suggestion["confidence"]
        confidence_color = self.get_confidence_color(confidence)
        confidence_badge = QLabel(f"Konfidenz: {suggestion['confidence_percent']}")
        confidence_badge.setStyleSheet(
            f"background-color: {confidence_color}; color: white; "
            f"padding: 3px 8px; border-radius: 3px; font-weight: bold;"
        )
        top_row.addWidget(confidence_badge)

        top_row.addStretch()

        # Timestamp
        activity = suggestion["activity"]
        timestamp = activity["timestamp"]
        # Ensure timestamp is datetime object (it should already be from database)
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        time_label = QLabel(timestamp.strftime("%d.%m.%Y %H:%M"))
        time_label.setProperty("class", "muted")
        top_row.addWidget(time_label)

        layout.addLayout(top_row)

        # Activity Info
        activity_info = QHBoxLayout()

        app_label = QLabel(f"📱 {activity['app_name']}")
        app_font = QFont()
        app_font.setBold(True)
        app_label.setFont(app_font)
        activity_info.addWidget(app_label)

        window_title = activity.get("window_title", "")
        if window_title:
            window_label = QLabel(f" - {window_title[:60]}")
            activity_info.addWidget(window_label)

        activity_info.addStretch()

        # Duration
        duration_minutes = activity["duration"] / 60
        duration_label = QLabel(f"{duration_minutes:.0f} min")
        duration_label.setProperty("class", "muted")
        activity_info.addWidget(duration_label)

        layout.addLayout(activity_info)

        # Project Suggestion mit ComboBox
        project_row = QHBoxLayout()
        project_label = QLabel("→ Projekt:")
        project_row.addWidget(project_label)

        # Projekt-ComboBox (uses global theme styles)
        project_combo = QComboBox()
        project_combo.setMinimumWidth(200)

        # Fülle ComboBox mit allen Projekten
        for project in self.projects:
            project_combo.addItem(f"  {project['name']}", project['id'])

        # Setze vorgeschlagenes Projekt als Standard (BEVOR Signal verbunden wird!)
        suggested_project_id = suggestion["suggested_project_id"]
        for i in range(project_combo.count()):
            if project_combo.itemData(i) == suggested_project_id:
                project_combo.setCurrentIndex(i)
                break

        # Verhindere Click-Propagation zum Widget (stoppt Checkbox-Toggle beim ComboBox-Klick)
        def combo_mouse_press(event):
            event.accept()  # Stoppt Event-Propagation
            QComboBox.mousePressEvent(project_combo, event)  # Führe normale ComboBox-Funktion aus

        project_combo.mousePressEvent = combo_mouse_press  # pyright: ignore[reportAttributeAccessIssue]

        # Signal-Handler NACH dem Setzen des Standard-Index verbinden!
        # Dadurch wird der Handler nicht beim initialen Setzen aufgerufen
        project_combo.currentIndexChanged.connect(
            lambda idx, index=index: self.on_project_changed(index, project_combo.itemData(idx))
        )

        project_row.addWidget(project_combo)
        project_row.addStretch()

        layout.addLayout(project_row)

        # Speichere Checkbox-Referenz im Widget für Click-Handler
        widget.checkbox = checkbox  # pyright: ignore[reportAttributeAccessIssue]
        widget.suggestion_index = index  # pyright: ignore[reportAttributeAccessIssue]

        # Mache das gesamte Widget klickbar
        widget.mousePressEvent = lambda event: self.on_widget_clicked(widget, event)  # pyright: ignore[reportAttributeAccessIssue]

        return widget

    def on_widget_clicked(self, widget: QWidget, event):
        """Handler für Widget-Klicks - togglet die Checkbox oder wählt Bereich bei Shift"""
        index = widget.suggestion_index  # pyright: ignore[reportAttributeAccessIssue]

        # Prüfe auf Shift-Klick für Bereichsauswahl
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and self.last_clicked_index is not None:
            # Bereichsauswahl: Wähle alle Items zwischen last_clicked_index und index
            start = min(self.last_clicked_index, index)
            end = max(self.last_clicked_index, index)

            # Wähle alle Items im Bereich aus
            for i in range(start, end + 1):
                self.selected_suggestions.add(i)

            # Aktualisiere UI
            self.update_checkboxes()
            self.update_all_widget_styles()
            self.update_button_text()
        else:
            # Normaler Klick: Toggle Checkbox
            checkbox = widget.checkbox  # pyright: ignore[reportAttributeAccessIssue]
            checkbox.setChecked(not checkbox.isChecked())
            self.last_clicked_index = index

    def on_project_changed(self, index: int, new_project_id: int):
        """Handler für Projekt-Änderungen"""
        # Aktualisiere die Suggestion mit dem neuen Projekt
        self.suggestions[index]["suggested_project_id"] = new_project_id

        # Finde das neue Projekt
        new_project = next((p for p in self.projects if p["id"] == new_project_id), None)
        if new_project:
            self.suggestions[index]["suggested_project_name"] = new_project["name"]
            self.suggestions[index]["suggested_project_color"] = new_project["color"]

    def get_confidence_color(self, confidence: float) -> str:
        """Bestimmt Farbe basierend auf Konfidenz"""
        if confidence >= 0.8:
            return "#27ae60"  # Grün
        elif confidence >= 0.6:
            return "#f39c12"  # Orange
        else:
            return "#e74c3c"  # Rot

    def toggle_suggestion(self, index: int, state: int):
        """Toggle Auswahl eines Vorschlags"""
        if state == Qt.CheckState.Checked.value:
            self.selected_suggestions.add(index)
        else:
            self.selected_suggestions.discard(index)

        self.update_widget_style(index)
        self.update_button_text()

    def update_widget_style(self, index: int):
        """Aktualisiere Widget-Style basierend auf Auswahl-Status"""
        widget = self.widget_map.get(index)
        if not widget:
            return

        c = self.theme.colors
        object_name = f"suggestion_card_{index}"

        if index in self.selected_suggestions:
            # Ausgewählt: Grüne Umrandung (nur auf Haupt-Widget)
            widget.setStyleSheet(
                f"QWidget#{object_name} {{ background-color: {c.card_background}; border: 3px solid {c.success}; "
                f"border-radius: 8px; padding: 10px; margin: 2px; }} "
                f"QWidget#{object_name}:hover {{ background-color: {c.background_tertiary}; border-color: {c.success_hover}; }}"
            )
        else:
            # Nicht ausgewählt: Standard-Style
            widget.setStyleSheet(
                f"QWidget#{object_name} {{ background-color: {c.card_background}; border: 1px solid {c.border}; "
                f"border-radius: 8px; padding: 10px; margin: 2px; }} "
                f"QWidget#{object_name}:hover {{ background-color: {c.background_tertiary}; border-color: {c.accent}; }}"
            )

    def select_all(self):
        """Wähle alle Vorschläge aus"""
        self.selected_suggestions = set(range(len(self.suggestions)))
        self.update_checkboxes()
        self.update_all_widget_styles()
        self.update_button_text()

    def select_none(self):
        """Wähle keine Vorschläge aus"""
        self.selected_suggestions.clear()
        self.update_checkboxes()
        self.update_all_widget_styles()
        self.update_button_text()

    def update_all_widget_styles(self):
        """Aktualisiere alle Widget-Styles"""
        for i in range(len(self.suggestions)):
            self.update_widget_style(i)

    def update_checkboxes(self):
        """Aktualisiere Checkbox-States"""
        for i in range(len(self.suggestions)):
            checkbox = self.suggestions_widget.findChild(QCheckBox, f"checkbox_{i}")
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(i in self.selected_suggestions)
                checkbox.blockSignals(False)

    def update_button_text(self):
        """Aktualisiere Button-Text mit Anzahl"""
        count = len(self.selected_suggestions)
        self.apply_btn.setText(f"Ausgewählte übernehmen ({count})")

    def apply_selected(self):
        """Übernimm ausgewählte Vorschläge"""
        if not self.selected_suggestions:
            return

        for index in self.selected_suggestions:
            suggestion = self.suggestions[index]
            activity = suggestion["activity"]
            self.applied_changes.append((activity["id"], activity.get("project_id")))
            self.database.assign_activity_to_project(
                activity["id"], suggestion["suggested_project_id"]
            )

        logger.info(f"{len(self.selected_suggestions)} Aktivitäten zugeordnet")

        self.accept()
