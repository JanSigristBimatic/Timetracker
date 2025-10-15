"""
KI-Zuordnungs-Dialog für intelligente Projektzuordnung
"""

from datetime import datetime, timedelta

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


class AssignmentSuggestionsDialog(QDialog):
    """Dialog zur Anzeige und Bestätigung von KI-Projektzuordnungen"""

    def __init__(self, database: DatabaseProtocol, parent=None):
        super().__init__(parent)
        self.database = database
        self.assigner = SmartProjectAssigner(database)
        self.suggestions = []
        self.selected_suggestions = set()
        self.projects = []  # Alle verfügbaren Projekte
        self.widget_map = {}  # Map: index -> widget für Style-Updates
        self.last_clicked_index = None  # Für Shift-Klick Bereichsauswahl

        self.setup_ui()
        self.load_suggestions()

    def setup_ui(self):
        """Setup Dialog UI"""
        self.setWindowTitle("🤖 KI-Projektzuordnung")
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Intelligente Projektzuordnung")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Info Text
        info = QLabel(
            "Die KI hat aus Ihren bisherigen Zuordnungen gelernt und schlägt "
            "automatisch Projekte für nicht zugeordnete Aktivitäten vor. "
            "Wählen Sie die Vorschläge aus, die Sie übernehmen möchten.\n"
            "💡 Tipp: Halten Sie Shift gedrückt und klicken Sie auf zwei Karten, "
            "um einen Bereich auszuwählen."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #7f8c8d; margin: 10px 0;")
        layout.addWidget(info)

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
        self.apply_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 5px 15px;"
        )
        button_layout.addWidget(self.apply_btn)

        layout.addLayout(button_layout)

    def load_suggestions(self):
        """Lade KI-Vorschläge"""
        # Lade alle Projekte
        self.projects = self.database.get_projects()

        # Hole Vorschläge für die letzten 7 Tage
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        self.suggestions = self.assigner.get_suggestions_for_review(
            start_date=start_date, end_date=end_date, limit=100
        )

        # Zeige Anzahl
        if not self.suggestions:
            no_suggestions = QLabel("Keine Vorschläge verfügbar")
            no_suggestions.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_suggestions.setStyleSheet(
                "color: #7f8c8d; padding: 20px; font-size: 14px;"
            )
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
        widget = QWidget()
        widget.setObjectName(f"suggestion_card_{index}")  # Unique identifier
        widget.setStyleSheet(
            f"QWidget#suggestion_card_{index} {{ background-color: #f8f9fa; border: 1px solid #dee2e6; "
            f"border-radius: 5px; padding: 10px; margin: 2px; }} "
            f"QWidget#suggestion_card_{index}:hover {{ background-color: #e9ecef; border-color: #adb5bd; }}"
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
        time_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        top_row.addWidget(time_label)

        layout.addLayout(top_row)

        # Activity Info
        activity_info = QHBoxLayout()

        app_label = QLabel(f"📱 {activity['app_name']}")
        app_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        activity_info.addWidget(app_label)

        window_title = activity.get("window_title", "")
        if window_title:
            window_label = QLabel(f" - {window_title[:60]}")
            window_label.setStyleSheet("color: #495057;")
            activity_info.addWidget(window_label)

        activity_info.addStretch()

        # Duration
        duration_minutes = activity["duration"] / 60
        duration_label = QLabel(f"{duration_minutes:.0f} min")
        duration_label.setStyleSheet("color: #7f8c8d;")
        activity_info.addWidget(duration_label)

        layout.addLayout(activity_info)

        # Project Suggestion mit ComboBox
        project_row = QHBoxLayout()
        project_label = QLabel("→ Projekt:")
        project_label.setStyleSheet("color: #2c3e50;")
        project_row.addWidget(project_label)

        # Projekt-ComboBox
        project_combo = QComboBox()
        project_combo.setStyleSheet(
            "QComboBox { padding: 5px; background-color: white; color: #2c3e50; border: 1px solid #ced4da; "
            "border-radius: 3px; min-width: 200px; }"
            "QComboBox:hover { border-color: #80bdff; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background-color: white; color: #2c3e50; "
            "selection-background-color: #3498db; selection-color: white; }"
        )

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

        project_combo.mousePressEvent = combo_mouse_press

        # Signal-Handler NACH dem Setzen des Standard-Index verbinden!
        # Dadurch wird der Handler nicht beim initialen Setzen aufgerufen
        project_combo.currentIndexChanged.connect(
            lambda idx, index=index: self.on_project_changed(index, project_combo.itemData(idx))
        )

        project_row.addWidget(project_combo)
        project_row.addStretch()

        layout.addLayout(project_row)

        # Speichere Checkbox-Referenz im Widget für Click-Handler
        widget.checkbox = checkbox
        widget.suggestion_index = index

        # Mache das gesamte Widget klickbar
        widget.mousePressEvent = lambda event: self.on_widget_clicked(widget, event)

        return widget

    def on_widget_clicked(self, widget: QWidget, event):
        """Handler für Widget-Klicks - togglet die Checkbox oder wählt Bereich bei Shift"""
        index = widget.suggestion_index

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
            checkbox = widget.checkbox
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

        object_name = f"suggestion_card_{index}"

        if index in self.selected_suggestions:
            # Ausgewählt: Grüne Umrandung (nur auf Haupt-Widget)
            widget.setStyleSheet(
                f"QWidget#{ object_name} {{ background-color: #f8f9fa; border: 3px solid #27ae60; "
                f"border-radius: 5px; padding: 10px; margin: 2px; }} "
                f"QWidget#{object_name}:hover {{ background-color: #e9ecef; border-color: #1e8449; }}"
            )
        else:
            # Nicht ausgewählt: Standard-Style
            widget.setStyleSheet(
                f"QWidget#{object_name} {{ background-color: #f8f9fa; border: 1px solid #dee2e6; "
                f"border-radius: 5px; padding: 10px; margin: 2px; }} "
                f"QWidget#{object_name}:hover {{ background-color: #e9ecef; border-color: #adb5bd; }}"
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

        # Wende Zuordnungen an
        for index in self.selected_suggestions:
            suggestion = self.suggestions[index]
            activity_id = suggestion["activity"]["id"]
            project_id = suggestion["suggested_project_id"]

            self.database.assign_activity_to_project(activity_id, project_id)

        print(f"✓ {len(self.selected_suggestions)} Aktivitäten zugeordnet")

        self.accept()
