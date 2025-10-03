from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QDateEdit, QComboBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QDate
from datetime import datetime, timedelta
from utils.export import Exporter


class ExportDialog(QDialog):
    """Dialog for exporting data"""

    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.exporter = Exporter(database)
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Daten exportieren")
        self.setGeometry(200, 200, 500, 300)

        layout = QVBoxLayout(self)

        # Date range selection
        date_label = QLabel("Zeitraum:")
        layout.addWidget(date_label)

        # Preset buttons
        preset_layout = QHBoxLayout()

        today_btn = QPushButton("Heute")
        today_btn.clicked.connect(self.set_today)
        preset_layout.addWidget(today_btn)

        week_btn = QPushButton("Diese Woche")
        week_btn.clicked.connect(self.set_this_week)
        preset_layout.addWidget(week_btn)

        month_btn = QPushButton("Dieser Monat")
        month_btn.clicked.connect(self.set_this_month)
        preset_layout.addWidget(month_btn)

        layout.addLayout(preset_layout)

        # Date range inputs
        date_range_layout = QHBoxLayout()

        date_range_layout.addWidget(QLabel("Von:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        date_range_layout.addWidget(self.start_date_edit)

        date_range_layout.addWidget(QLabel("Bis:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        date_range_layout.addWidget(self.end_date_edit)

        layout.addLayout(date_range_layout)

        # Export type selection
        layout.addWidget(QLabel("Export-Typ:"))

        self.export_type = QComboBox()
        self.export_type.addItems([
            "Detaillierte Aktivitäten (CSV)",
            "Projekt-Zusammenfassung (CSV)",
            "Excel mit allen Details (XLSX)"
        ])
        layout.addWidget(self.export_type)

        layout.addStretch()

        # Export button
        export_btn = QPushButton("Exportieren")
        export_btn.clicked.connect(self.export_data)
        layout.addWidget(export_btn)

        # Cancel button
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def set_today(self):
        """Set date range to today"""
        today = QDate.currentDate()
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)

    def set_this_week(self):
        """Set date range to this week"""
        today = QDate.currentDate()
        # Monday of this week
        monday = today.addDays(-(today.dayOfWeek() - 1))
        self.start_date_edit.setDate(monday)
        self.end_date_edit.setDate(today)

    def set_this_month(self):
        """Set date range to this month"""
        today = QDate.currentDate()
        first_day = QDate(today.year(), today.month(), 1)
        self.start_date_edit.setDate(first_day)
        self.end_date_edit.setDate(today)

    def export_data(self):
        """Export data based on selection"""
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()

        # Convert to datetime
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Get filename from user
        export_type_idx = self.export_type.currentIndex()

        if export_type_idx == 0:
            default_name = f"aktivitaeten_{start_date}_{end_date}.csv"
            file_filter = "CSV Dateien (*.csv)"
            dialog_title = "CSV Datei speichern"
        elif export_type_idx == 1:
            default_name = f"projekt_zusammenfassung_{start_date}_{end_date}.csv"
            file_filter = "CSV Dateien (*.csv)"
            dialog_title = "CSV Datei speichern"
        else:
            default_name = f"timetracker_export_{start_date}_{end_date}.xlsx"
            file_filter = "Excel Dateien (*.xlsx)"
            dialog_title = "Excel Datei speichern"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            default_name,
            file_filter
        )

        if not filepath:
            return

        try:
            if export_type_idx == 0:
                count = self.exporter.export_csv(start_datetime, end_datetime, filepath)
                QMessageBox.information(
                    self,
                    "Export erfolgreich",
                    f"{count} Aktivitäten wurden exportiert nach:\n{filepath}"
                )
            elif export_type_idx == 1:
                count = self.exporter.export_project_summary_csv(start_datetime, end_datetime, filepath)
                QMessageBox.information(
                    self,
                    "Export erfolgreich",
                    f"{count} Projekte wurden exportiert nach:\n{filepath}"
                )
            else:
                count = self.exporter.export_excel(start_datetime, end_datetime, filepath)
                QMessageBox.information(
                    self,
                    "Export erfolgreich",
                    f"{count} Aktivitäten wurden in Excel-Format exportiert nach:\n{filepath}\n\nDas Excel enthält 3 Sheets:\n- Detailliert\n- Projekt-Zusammenfassung\n- Tages-Zusammenfassung"
                )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Export fehlgeschlagen",
                f"Fehler beim Exportieren: {e}"
            )
