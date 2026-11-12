import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core.database_protocol import DatabaseProtocol
from utils.config import (
    DEFAULT_IGNORED_PROCESSES,
    DEFAULT_IGNORED_WINDOW_TITLES,
    get_env_int,
    get_user_env_path,
)

from .theme import ThemeMode, get_theme

DAILY_GOAL_SETTING_KEY = 'daily_goal_hours'


class SettingsDialog(QDialog):
    """Dialog for application settings"""

    def __init__(self, database: Optional[DatabaseProtocol] = None, parent=None):
        super().__init__(parent)
        self.database = database
        self.theme_manager = get_theme()
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Einstellungen")
        self.setGeometry(200, 200, 550, 620)

        layout = QVBoxLayout(self)

        # Appearance Settings (Theme)
        appearance_group = QGroupBox("Erscheinungsbild")
        appearance_layout = QVBoxLayout()

        theme_label = QLabel("Design-Modus:")
        appearance_layout.addWidget(theme_label)

        theme_row = QHBoxLayout()

        self.theme_group = QButtonGroup(self)

        self.system_radio = QRadioButton("Automatisch (System)")
        self.system_radio.setToolTip("Folgt der Windows-Einstellung")
        self.theme_group.addButton(self.system_radio, 0)
        theme_row.addWidget(self.system_radio)

        self.light_radio = QRadioButton("Hell")
        self.light_radio.setToolTip("Helles Design")
        self.theme_group.addButton(self.light_radio, 1)
        theme_row.addWidget(self.light_radio)

        self.dark_radio = QRadioButton("Dunkel")
        self.dark_radio.setToolTip("Dunkles Design")
        self.theme_group.addButton(self.dark_radio, 2)
        theme_row.addWidget(self.dark_radio)

        theme_row.addStretch()

        current_mode = self.theme_manager.current_theme
        if current_mode == ThemeMode.SYSTEM:
            self.system_radio.setChecked(True)
        elif current_mode == ThemeMode.DARK:
            self.dark_radio.setChecked(True)
        else:
            self.light_radio.setChecked(True)

        self.theme_group.buttonClicked.connect(self.on_theme_changed)

        appearance_layout.addLayout(theme_row)
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)

        # Goals
        goal_group = QGroupBox("Tagesziel")
        goal_layout = QFormLayout()

        self.daily_goal_spin = QDoubleSpinBox()
        self.daily_goal_spin.setRange(0.0, 24.0)
        self.daily_goal_spin.setSingleStep(0.5)
        self.daily_goal_spin.setSuffix(" Stunden")
        self.daily_goal_spin.setSpecialValueText("Deaktiviert")
        self.daily_goal_spin.setToolTip(
            "Sollarbeitszeit pro Tag. Wird im Tray-Tooltip angezeigt; "
            "bei Erreichen erscheint eine Benachrichtigung. 0 = aus."
        )
        goal_layout.addRow("Aktive Zeit pro Tag:", self.daily_goal_spin)

        goal_group.setLayout(goal_layout)
        layout.addWidget(goal_group)

        # Database Settings
        db_group = QGroupBox("Datenbank")
        db_layout = QHBoxLayout()

        self.db_path_edit = QLineEdit()
        self.db_path_edit.setPlaceholderText("Standard: %USERPROFILE%\\.timetracker\\timetracker.db")
        self.db_path_edit.setReadOnly(True)
        db_layout.addWidget(self.db_path_edit)

        browse_btn = QPushButton("Durchsuchen...")
        browse_btn.clicked.connect(self.browse_database_path)
        db_layout.addWidget(browse_btn)

        reset_db_btn = QPushButton("Standard")
        reset_db_btn.clicked.connect(self.reset_database_path)
        reset_db_btn.setToolTip("Zurück zum Standard-Datenbankpfad")
        db_layout.addWidget(reset_db_btn)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # Tracking Settings
        tracking_group = QGroupBox("Tracking Einstellungen")
        tracking_layout = QFormLayout()

        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 10)
        self.poll_interval_spin.setSuffix(" Sekunden")
        self.poll_interval_spin.setToolTip("Wie oft wird das aktive Fenster überprüft")
        tracking_layout.addRow("Polling-Intervall:", self.poll_interval_spin)

        self.idle_threshold_spin = QSpinBox()
        self.idle_threshold_spin.setRange(60, 3600)
        self.idle_threshold_spin.setSuffix(" Sekunden")
        self.idle_threshold_spin.setToolTip("Zeit ohne Aktivität bis Idle-Status")
        tracking_layout.addRow("Idle-Schwellwert:", self.idle_threshold_spin)

        tracking_group.setLayout(tracking_layout)
        layout.addWidget(tracking_group)

        # Timeline Merge Settings
        merge_group = QGroupBox("Timeline Zusammenführung")
        merge_layout = QFormLayout()

        self.min_duration_spin = QSpinBox()
        self.min_duration_spin.setRange(1, 60)
        self.min_duration_spin.setSuffix(" Sekunden")
        self.min_duration_spin.setToolTip("Aktivitäten kürzer als diese Zeit werden ignoriert")
        merge_layout.addRow("Minimum Aktivitätsdauer:", self.min_duration_spin)

        self.merge_gap_spin = QSpinBox()
        self.merge_gap_spin.setRange(5, 600)
        self.merge_gap_spin.setSuffix(" Sekunden")
        self.merge_gap_spin.setToolTip("Zeitlücke für Zusammenführung gleicher Apps")
        merge_layout.addRow("Merge-Gap (App):", self.merge_gap_spin)

        self.project_merge_gap_spin = QSpinBox()
        self.project_merge_gap_spin.setRange(30, 1800)
        self.project_merge_gap_spin.setSuffix(" Sekunden")
        self.project_merge_gap_spin.setToolTip("Zeitlücke für Zusammenführung bei gleichem Projekt")
        merge_layout.addRow("Merge-Gap (Projekt):", self.project_merge_gap_spin)

        merge_group.setLayout(merge_layout)
        layout.addWidget(merge_group)

        # Blacklist Settings
        blacklist_group = QGroupBox("Blacklist (Ignorierte Prozesse & Fenster)")
        blacklist_layout = QVBoxLayout()

        processes_label = QLabel("Ignorierte Prozesse (einer pro Zeile):")
        blacklist_layout.addWidget(processes_label)

        self.ignored_processes_text = QTextEdit()
        self.ignored_processes_text.setPlaceholderText("z.B.:\nexplorer.exe\nTaskmgr.exe")
        self.ignored_processes_text.setMaximumHeight(100)
        blacklist_layout.addWidget(self.ignored_processes_text)

        titles_label = QLabel("Ignorierte Fenstertitel (einer pro Zeile):")
        blacklist_layout.addWidget(titles_label)

        self.ignored_titles_text = QTextEdit()
        self.ignored_titles_text.setPlaceholderText("z.B.:\nProgram Manager\nTask Switching")
        self.ignored_titles_text.setMaximumHeight(100)
        blacklist_layout.addWidget(self.ignored_titles_text)

        blacklist_group.setLayout(blacklist_layout)
        layout.addWidget(blacklist_group)

        # Info section
        info_label = QLabel(
            "<b>Hinweise:</b><br>"
            "• Einstellungen werden sofort wirksam und in "
            f"{get_user_env_path()} gespeichert<br>"
            "• Nur Änderungen am Datenbankpfad erfordern einen Neustart"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("Speichern")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        reset_btn = QPushButton("Zurücksetzen")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)

        layout.addLayout(button_layout)

    def on_theme_changed(self, button):
        """Handle theme change"""
        if button == self.system_radio:
            self.theme_manager.set_theme(ThemeMode.SYSTEM)
        elif button == self.dark_radio:
            self.theme_manager.set_theme(ThemeMode.DARK)
        else:
            self.theme_manager.set_theme(ThemeMode.LIGHT)

    def browse_database_path(self):
        """Open file dialog to select database path"""
        default_path = str(Path.home() / '.timetracker' / 'timetracker.db')
        current_path = self.db_path_edit.text() or default_path

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Datenbank-Pfad wählen",
            current_path,
            "SQLite Datenbank (*.db);;Alle Dateien (*.*)"
        )

        if file_path:
            self.db_path_edit.setText(file_path)

    def reset_database_path(self):
        """Reset database path to default"""
        self.db_path_edit.clear()

    def load_settings(self):
        """Load current settings from environment"""
        db_path = os.getenv('DATABASE_PATH', '')
        if db_path:
            self.db_path_edit.setText(db_path)
        else:
            self.db_path_edit.clear()

        self.poll_interval_spin.setValue(get_env_int('POLL_INTERVAL', 2))
        self.idle_threshold_spin.setValue(get_env_int('IDLE_THRESHOLD', 300))
        self.min_duration_spin.setValue(get_env_int('MIN_ACTIVITY_DURATION', 10))
        self.merge_gap_spin.setValue(get_env_int('MERGE_GAP', 60))
        self.project_merge_gap_spin.setValue(get_env_int('PROJECT_MERGE_GAP', 180))

        if self.database:
            goal = self.database.get_setting(DAILY_GOAL_SETTING_KEY) or '0'
            try:
                self.daily_goal_spin.setValue(float(goal))
            except (TypeError, ValueError):
                self.daily_goal_spin.setValue(0.0)

        ignored_procs = os.getenv('IGNORED_PROCESSES', '')
        if ignored_procs.strip():
            self.ignored_processes_text.setPlainText('\n'.join(p.strip() for p in ignored_procs.split(',') if p.strip()))
        else:
            self.ignored_processes_text.setPlainText('\n'.join(sorted(DEFAULT_IGNORED_PROCESSES)))

        ignored_titles = os.getenv('IGNORED_WINDOW_TITLES', '')
        if ignored_titles.strip():
            self.ignored_titles_text.setPlainText('\n'.join(t.strip() for t in ignored_titles.split(',') if t.strip()))
        else:
            self.ignored_titles_text.setPlainText('\n'.join(sorted(DEFAULT_IGNORED_WINDOW_TITLES)))

    def reset_to_defaults(self):
        """Reset to default values"""
        self.poll_interval_spin.setValue(2)
        self.idle_threshold_spin.setValue(300)
        self.min_duration_spin.setValue(10)
        self.merge_gap_spin.setValue(60)
        self.project_merge_gap_spin.setValue(180)
        self.daily_goal_spin.setValue(0.0)
        self.ignored_processes_text.setPlainText('\n'.join(sorted(DEFAULT_IGNORED_PROCESSES)))
        self.ignored_titles_text.setPlainText('\n'.join(sorted(DEFAULT_IGNORED_WINDOW_TITLES)))

    def save_settings(self):
        """Save settings to the user env file and the running process."""
        try:
            env_path = get_user_env_path()
            env_lines = []

            if env_path.exists():
                env_lines = env_path.read_text(encoding='utf-8').splitlines(keepends=True)

            ignored_processes = [p.strip() for p in self.ignored_processes_text.toPlainText().split('\n') if p.strip()]
            ignored_titles = [t.strip() for t in self.ignored_titles_text.toPlainText().split('\n') if t.strip()]

            settings = {
                'DATABASE_PATH': self.db_path_edit.text().strip(),
                'POLL_INTERVAL': str(self.poll_interval_spin.value()),
                'IDLE_THRESHOLD': str(self.idle_threshold_spin.value()),
                'MIN_ACTIVITY_DURATION': str(self.min_duration_spin.value()),
                'MERGE_GAP': str(self.merge_gap_spin.value()),
                'PROJECT_MERGE_GAP': str(self.project_merge_gap_spin.value()),
                'IGNORED_PROCESSES': ','.join(ignored_processes),
                'IGNORED_WINDOW_TITLES': ','.join(ignored_titles),
            }

            # Update existing lines or collect them
            updated_keys = set()
            new_lines = []

            for line in env_lines:
                stripped = line.strip()
                if '=' in stripped and not stripped.startswith('#'):
                    key = stripped.split('=')[0].strip()
                    if key in settings:
                        new_lines.append(f"{key}={settings[key]}\n")
                        updated_keys.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            for key, value in settings.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={value}\n")

            env_path.write_text(''.join(new_lines), encoding='utf-8')

            # Update the running process so changes apply without restart
            # and the dialog shows current values when reopened
            for key, value in settings.items():
                os.environ[key] = value

            if self.database:
                self.database.set_setting(
                    DAILY_GOAL_SETTING_KEY, str(self.daily_goal_spin.value())
                )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler beim Speichern",
                f"Fehler beim Speichern der Einstellungen: {e}"
            )
