"""
Automatisierungsscript für tägliche Rapporte und Projektzuordnung.

Kann manuell ausgeführt oder über den Task Scheduler automatisiert werden.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path so the script also works when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import Database
from utils.smart_project_assigner import SmartProjectAssigner


class DailyReportGenerator:
    """Minimal Report-Generator, der eine einfache TXT-Zusammenfassung erstellt."""

    def __init__(self, database: Database):
        self.database = database
        self.output_dir = Path.home() / ".timetracker" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_report(self, date: Optional[datetime] = None, auto_open: bool = False):
        """Erzeuge einen einfachen Tagesrapport als Textdatei."""
        if date is None:
            date = datetime.now()

        start = datetime.combine(date.date(), datetime.min.time())
        end = datetime.combine(date.date(), datetime.max.time())

        activities = self.database.get_activities(start_date=start, end_date=end)
        if not activities:
            return None

        total_seconds = sum(a["duration"] for a in activities)
        active_seconds = sum(a["duration"] for a in activities if not a.get("is_idle"))
        idle_seconds = total_seconds - active_seconds

        by_app = Counter()
        counts = Counter()
        for act in activities:
            by_app[act["app_name"]] += act["duration"]
            counts[act["app_name"]] += 1

        lines = [
            f"TimeTracker Tagesrapport {date.date()}",
            "-" * 40,
            f"Anzahl Aktivitäten: {len(activities)}",
            f"Gesamt: {total_seconds / 3600:.2f} h",
            f"Aktiv: {active_seconds / 3600:.2f} h",
            f"Idle: {idle_seconds / 3600:.2f} h",
            "",
            "Top 5 Programme (nach Dauer):",
        ]

        for app, _ in by_app.most_common(5):
            lines.append(
                f"- {app}: {by_app[app] / 3600:.2f} h ({counts[app]} Aktivitäten)"
            )

        report_path = self.output_dir / f"rapport_{date.date()}.txt"
        report_path.write_text("\n".join(lines), encoding="utf-8")

        if auto_open:
            try:
                os.startfile(report_path)  # type: ignore[attr-defined]
            except Exception:
                # Öffnen ist optional; Fehler hier dürfen den Report nicht verhindern
                pass

        return report_path


def auto_assign_projects(
    database: Database, days_back: int = 1, min_confidence: float = 0.7, dry_run: bool = False
):
    """
    Automatische Projektzuordnung.
    """
    print("=" * 80)
    print("AUTOMATISCHE PROJEKTZUORDNUNG")
    print("=" * 80)

    assigner = SmartProjectAssigner(database)

    # Berechne Zeitraum
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    print(f"\nZeitraum: {start_date.date()} bis {end_date.date()}")
    print(f"Minimale Konfidenz: {min_confidence:.0%}")
    print(f"Modus: {'DRY RUN (keine Änderungen)' if dry_run else 'PRODUKTIV'}")
    print()

    # Führe Auto-Zuordnung aus
    stats = assigner.auto_assign_unassigned(
        start_date=start_date, end_date=end_date, min_confidence=min_confidence, dry_run=dry_run
    )

    print("\n" + "=" * 80)
    print("ERGEBNISSE")
    print("=" * 80)
    print(f"Gesamt nicht zugeordnet: {stats['total_unassigned']}")
    print(f"Zugeordnet: {stats['assigned']}")
    print(f"Übersprungen (niedrige Konfidenz): {stats['skipped_low_confidence']}")
    print()

    if stats["assignments"]:
        print("ZUGEORDNETE AKTIVITÄTEN:")
        print("-" * 80)
        for assignment in stats["assignments"][:10]:  # Zeige erste 10
            print(
                f"  {assignment['app_name']:<20} -> {assignment['project']:<20} ({assignment['confidence']})"
            )
            if assignment["window_title"]:
                print(f"    ↳ {assignment['window_title']}")

        if len(stats["assignments"]) > 10:
            print(f"  ... und {len(stats['assignments']) - 10} weitere")

    print("\n" + "=" * 80)
    return stats


def generate_daily_report(database: Database, date: Optional[datetime] = None, auto_open: bool = True):
    """
    Generiert täglichen Rapport.
    """
    print("=" * 80)
    print("TAGESRAPPORT GENERIERUNG")
    print("=" * 80)

    generator = DailyReportGenerator(database)

    if date is None:
        date = datetime.now()

    print(f"\nGeneriere Rapport für: {date.date()}")
    print(f"Ausgabeverzeichnis: {generator.output_dir}")
    print()

    filepath = generator.generate_daily_report(date=date, auto_open=auto_open)

    if filepath:
        print(f"\n✓ Rapport erfolgreich erstellt: {filepath}")
        print(f"  Dateigröße: {filepath.stat().st_size / 1024:.1f} KB")
    else:
        print("\nℹ Keine Aktivitäten für diesen Tag gefunden")

    print("\n" + "=" * 80)
    return filepath


def main():
    """Hauptfunktion"""
    parser = argparse.ArgumentParser(
        description="TimeTracker Automatisierung - Projektzuordnung und Rapporte"
    )

    parser.add_argument(
        "--mode",
        choices=["assign", "report", "both"],
        default="both",
        help="Modus: assign (nur Zuordnung), report (nur Rapport), both (beides)",
    )

    parser.add_argument(
        "--days-back", type=int, default=1, help="Tage zurück für Zuordnung (default: 1)"
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.7,
        help="Minimale Konfidenz für Auto-Zuordnung (0.0-1.0, default: 0.7)",
    )

    parser.add_argument(
        "--date", type=str, help="Datum für Rapport im Format YYYY-MM-DD (default: heute)"
    )

    parser.add_argument("--dry-run", action="store_true", help="Dry-Run Modus (keine Änderungen)")

    parser.add_argument("--no-open", action="store_true", help="Rapport nicht automatisch öffnen")

    args = parser.parse_args()

    # Initialisiere Datenbank
    print("\nInitialisiere Datenbank...")
    database = Database()

    try:
        # Projektzuordnung
        if args.mode in ["assign", "both"]:
            auto_assign_projects(
                database=database,
                days_back=args.days_back,
                min_confidence=args.confidence,
                dry_run=args.dry_run,
            )

        # Rapport-Generierung
        if args.mode in ["report", "both"]:
            # Parse Datum
            report_date = None
            if args.date:
                try:
                    report_date = datetime.strptime(args.date, "%Y-%m-%d")
                except ValueError:
                    print(
                        f"Fehler: Ungültiges Datumsformat '{args.date}'. Verwende Format YYYY-MM-DD"
                    )
                    sys.exit(1)

            generate_daily_report(database=database, date=report_date, auto_open=not args.no_open)

    finally:
        database.close()

    print("\n✓ Fertig!")


if __name__ == "__main__":
    main()
