from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QSpinBox, QGroupBox, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt
import os
from utils.config import DEFAULT_IGNORED_PROCESSES, DEFAULT_IGNORED_WINDOW_TITLES


class SettingsDialog(QDialog):
    """Dialog for application settings"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Einstellungen")
        self.setGeometry(200, 200, 500, 400)

        layout = QVBoxLayout(self)

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

        # Ignored Processes
        processes_label = QLabel("Ignorierte Prozesse (einer pro Zeile):")
        blacklist_layout.addWidget(processes_label)

        self.ignored_processes_text = QTextEdit()
        self.ignored_processes_text.setPlaceholderText("z.B.:\nexplorer.exe\nTaskmgr.exe")
        self.ignored_processes_text.setMaximumHeight(100)
        blacklist_layout.addWidget(self.ignored_processes_text)

        # Ignored Window Titles
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
            "• Minimum Aktivitätsdauer: Kürzere Aktivitäten werden als Rauschen gefiltert<br>"
            "• Merge-Gap (App): Wechsel zur gleichen App werden zusammengefasst<br>"
            "• Merge-Gap (Projekt): Noch aggressiveres Merging für Projekt-Aktivitäten<br>"
            "• Blacklist: Prozesse und Fenstertitel, die nicht getrackt werden sollen<br>"
            "• Änderungen werden beim Speichern in .env geschrieben"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        reset_btn = QPushButton("Zurücksetzen")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)

        layout.addLayout(button_layout)

    def load_settings(self):
        """Load current settings from environment"""
        self.poll_interval_spin.setValue(int(os.getenv('POLL_INTERVAL', 2)))
        self.idle_threshold_spin.setValue(int(os.getenv('IDLE_THRESHOLD', 300)))
        self.min_duration_spin.setValue(int(os.getenv('MIN_ACTIVITY_DURATION', 10)))
        self.merge_gap_spin.setValue(int(os.getenv('MERGE_GAP', 60)))
        self.project_merge_gap_spin.setValue(int(os.getenv('PROJECT_MERGE_GAP', 180)))

        # Load blacklist settings
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
        self.ignored_processes_text.setPlainText('\n'.join(sorted(DEFAULT_IGNORED_PROCESSES)))
        self.ignored_titles_text.setPlainText('\n'.join(sorted(DEFAULT_IGNORED_WINDOW_TITLES)))

    def save_settings(self):
        """Save settings to .env file"""
        try:
            # Read current .env file
            env_path = '.env'
            env_lines = []

            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    env_lines = f.readlines()

            # Parse blacklist entries
            ignored_processes = [p.strip() for p in self.ignored_processes_text.toPlainText().split('\n') if p.strip()]
            ignored_titles = [t.strip() for t in self.ignored_titles_text.toPlainText().split('\n') if t.strip()]

            # Update or add settings
            settings = {
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

            # Add new settings that weren't in the file
            for key, value in settings.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={value}\n")

            # Write back to file
            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            QMessageBox.information(
                self,
                "Einstellungen gespeichert",
                "Die Einstellungen wurden erfolgreich gespeichert.\n\n"
                "Bitte starten Sie die Anwendung neu, damit alle Änderungen wirksam werden."
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Fehler beim Speichern",
                f"Fehler beim Speichern der Einstellungen: {e}"
            )
