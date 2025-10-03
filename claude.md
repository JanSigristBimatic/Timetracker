# TimeTracker - Entwicklungsrichtlinien für Claude

## Projektübersicht
TimeTracker ist eine plattformübergreifende Desktop-Anwendung zur automatischen Zeiterfassung. Die Anwendung nutzt PyQt6 für die GUI und SQLite für die Datenspeicherung.

## Technologie-Stack
- **Python**: 3.9+
- **GUI Framework**: PyQt6
- **Datenbank**: SQLite3 (lokale Speicherung)
- **Plattform**: Windows (primär), macOS/Linux (geplant)
- **Testing**: pytest

## Code-Prinzipien

### Clean Code nach Uncle Bob
Das Projekt folgt den Clean Code Prinzipien von Robert C. Martin:
- **Aussagekräftige Namen**: Verwende klare, selbsterklärende Variablen- und Funktionsnamen
- **Kleine Funktionen**: Funktionen sollten eine Aufgabe erfüllen und kurz sein
- **Single Responsibility Principle**: Jede Klasse/Funktion hat nur eine Verantwortung
- **DRY (Don't Repeat Yourself)**: Vermeide Code-Duplikation
- **Kommentare**: Nur wenn nötig - der Code sollte selbsterklärend sein
- **Docstrings**: Dokumentiere öffentliche Funktionen und Klassen

### PEP 8 Standards
- Folge den Python PEP 8 Konventionen
- Einrückung: 4 Leerzeichen
- Maximale Zeilenlänge: 88 Zeichen (Black-kompatibel)
- Import-Reihenfolge: Standard-Bibliothek, Drittanbieter, lokale Imports

## Projektstruktur

```
src/
├── main.py                      # Einstiegspunkt
├── core/                        # Kernlogik
│   ├── database.py              # SQLite-Datenbankmanagement
│   ├── database_protocol.py     # Type Protocols für Dependency Injection
│   ├── tracker.py               # Activity Tracking Logik
│   └── platform/
│       └── windows.py           # Plattformspezifisches Tracking
├── gui/                         # PyQt6 GUI Komponenten
│   ├── main_window.py
│   ├── timeline.py
│   ├── projects.py
│   ├── export_dialog.py
│   └── settings_dialog.py
├── utils/                       # Hilfsfunktionen
│   ├── config.py
│   ├── export.py
│   └── icon_cache.py
└── models/                      # Datenmodelle
```

## Datenbankrichtlinien

### SQLite Besonderheiten
- Datenbank liegt in `%USERPROFILE%\.timetracker\timetracker.db`
- `check_same_thread=False` für Thread-Safety mit Lock
- `row_factory = sqlite3.Row` für Dictionary-ähnlichen Zugriff
- Alle Schreiboperationen müssen Thread-sicher sein (`_write_lock`)

### Wichtige Tabellen
- `activities`: Zeiterfassungseinträge
- `projects`: Projektdefinitionen
- `project_rules`: Automatische Zuordnungsregeln
- `settings`: Anwendungseinstellungen

### Datenbankänderungen
- Verwende Database-Protokoll für Type Safety (`database_protocol.py`)
- Verwende Dependency Injection für Testbarkeit
- Nutze Context Manager wo möglich
- Schreibe Tests für neue Datenbankfunktionen

## GUI-Entwicklung mit PyQt6

### Wichtige Punkte
- Alle GUI-Updates müssen im Main Thread erfolgen
- Verwende Signals/Slots für Thread-Kommunikation
- System Tray Integration beachten
- Icon-Caching nutzen für Performance

### Fenster und Dialoge
- Verwende QMainWindow als Basis für Hauptfenster
- Dialoge erben von QDialog
- Layouts: Bevorzuge QVBoxLayout/QHBoxLayout/QGridLayout

## Testing

### Test-Anforderungen
- **Pflicht**: Schreibe Tests für neue Features
- **Framework**: pytest
- **Struktur**: Tests in `tests/` Verzeichnis
- **Fixtures**: Nutze `conftest.py` für gemeinsame Fixtures
- **Mocking**: Mock externe Abhängigkeiten (DB, File System, etc.)

### Test-Typen
- Unit Tests für einzelne Funktionen
- Integration Tests für Datenbankoperationen
- Mock-basierte Tests für GUI-Komponenten

### Beispiel Test-Setup
```python
@pytest.fixture
def temp_db(self):
    """Temporäre Datenbank für Tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path.home = lambda: Path(tmpdir)
        db = Database()
        yield db
        db.close()
```

## Dependency Injection

Das Projekt verwendet Dependency Injection für bessere Testbarkeit:
- Database wird als Parameter übergeben, nicht im Konstruktor erstellt
- Verwende Type Protocols (`database_protocol.py`) statt konkreter Klassen
- Ermöglicht einfaches Mocking in Tests

## Fehlerbehandlung

- Verwende spezifische Exceptions
- Logge Fehler angemessen
- Zeige benutzerfreundliche Fehlermeldungen in der GUI
- Fail-safe: Anwendung sollte auch bei Fehlern weiterlaufen können

## Performance-Überlegungen

- **Icon-Caching**: Icons werden gecacht, nicht bei jedem Request neu geladen
- **Thread-Safety**: Datenbankzugriffe sind Thread-sicher
- **Poll-Intervall**: Konfigurierbar (Standard: 2 Sekunden)
- **Idle-Erkennung**: Verhindert unnötige Aktivitätseinträge

## Plattform-Spezifika

### Windows (aktuell unterstützt)
- `pywin32` für native Windows API-Zugriffe
- Icon-Extraktion nur unter Windows verfügbar

### macOS/Linux (geplant)
- Noch nicht implementiert
- Plattform-spezifischer Code in `core/platform/` organisieren

## Konfiguration

- Konfigurationsdatei: `%USERPROFILE%\.timetracker\config.json`
- Verwende `utils/config.py` für Konfigurationszugriff
- Standard-Werte sind in Code hinterlegt

## Export-Funktionalität

- Formate: Excel, PDF, CSV
- Verwende `utils/export.py`
- pandas für Datenverarbeitung
- reportlab für PDF, openpyxl für Excel

## Wichtige Verhaltensweisen beim Bearbeiten

### DO's ✓
- **Immer Tests schreiben** für neue Features
- **Type Hints verwenden** für bessere Code-Qualität
- **Dependency Injection** für Testbarkeit nutzen
- **Thread-Safety** bei GUI und Datenbankoperationen beachten
- **Clean Code Prinzipien** befolgen
- **Docstrings** für öffentliche Funktionen schreiben
- **Existierende Patterns** im Codebase folgen

### DON'Ts ✗
- **Keine globalen Variablen** ohne guten Grund
- **Keine direkten Datenbankverbindungen** in GUI-Code
- **Keine blockierenden Operationen** im Main Thread
- **Keine Hard-coded Pfade** - verwende Path.home()
- **Keine ungetesteten Datenbankänderungen**
- **Keine Breaking Changes** ohne Migration

## Git Workflow

- Branch: `main` (Hauptbranch)
- Commit-Messages: Aussagekräftig und auf Deutsch
- Vor Commit: Tests ausführen
- Aktuelle Änderungen werden in requirements.txt, database.py, GUI-Komponenten vorgenommen

## Bekannte Issues

- macOS/Linux Support fehlt noch
- Icon-Extraktion nur Windows
- Cloud-Synchronisation noch nicht implementiert

## Zukünftige Entwicklung (Roadmap)

- Cloud-Synchronisation
- Erweiterte Statistiken und Analysen
- API für Drittanbieter-Integrationen
- macOS/Linux Support

## Hilfreiche Befehle

```bash
# Tests ausführen
pytest

# Mit Coverage
pytest --cov=src

# Anwendung starten
python src/main.py

# Virtuelle Umgebung aktivieren
venv\Scripts\activate  # Windows
```

## Kontakt & Support

Autor: Jan Sigrist
Lizenz: MIT
