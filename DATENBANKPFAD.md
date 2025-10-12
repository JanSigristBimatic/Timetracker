# Datenbankpfad-Konfiguration

## Übersicht

Ab sofort kannst du den Speicherort der TimeTracker-Datenbank über die Einstellungen konfigurieren. Dies ist nützlich für:

- **Cloud-Synchronisation**: Speichere die Datenbank in einem Cloud-Ordner (Dropbox, OneDrive, etc.)
- **Backup-Strategie**: Nutze einen Pfad, der automatisch gesichert wird
- **Netzwerkspeicher**: Speichere die Datenbank auf einem Netzwerklaufwerk
- **Mehrere Profile**: Verwende unterschiedliche Datenbanken für verschiedene Zwecke

## Standard-Verhalten

Ohne Konfiguration wird die Datenbank am Standard-Ort gespeichert:
```
%USERPROFILE%\.timetracker\timetracker.db
```

Beispiel: `C:\Users\JanSigrist\.timetracker\timetracker.db`

## Konfiguration über die GUI

1. Öffne die Anwendung
2. Klicke auf **Einstellungen** (im Menü oder System Tray)
3. Im Bereich **Datenbank** siehst du das aktuelle Pfad-Feld
4. Klicke auf **Durchsuchen...** um einen neuen Pfad zu wählen
5. Wähle einen Ordner und Dateinamen (z.B. `D:\Backup\timetracker.db`)
6. Klicke auf **Speichern**
7. **Starte die Anwendung neu**, damit die Änderung wirksam wird

### Zurücksetzen auf Standard

- Klicke auf den Button **Standard** neben dem Pfad-Feld
- Die Einstellung wird geleert und der Standard-Pfad wird verwendet
- Speichere und starte die Anwendung neu

## Konfiguration über .env Datei

Du kannst den Datenbankpfad auch manuell in der `.env` Datei setzen:

```bash
DATABASE_PATH=D:\Cloud\Dropbox\TimeTracker\timetracker.db
```

**Wichtig**:
- Verwende absolute Pfade
- Unter Windows kannst du Backslashes (`\`) oder Forward-Slashes (`/`) verwenden
- Das Verzeichnis wird automatisch erstellt, falls es nicht existiert

## Programmierung & API

### Database-Klasse

Die `Database`-Klasse unterstützt drei Wege zur Pfad-Konfiguration (in dieser Priorität):

```python
from core.database import Database

# 1. Expliziter Pfad (höchste Priorität)
db = Database(db_path="/pfad/zur/datenbank.db")

# 2. Environment Variable
import os
os.environ['DATABASE_PATH'] = "/pfad/zur/datenbank.db"
db = Database()

# 3. Standard-Pfad (wenn nichts anderes gesetzt)
db = Database()  # Verwendet ~/.timetracker/timetracker.db
```

### Config-Funktion

```python
from utils.config import get_database_path

# Gibt den konfigurierten oder Standard-Pfad zurück
db_path = get_database_path()
print(f"Datenbank-Pfad: {db_path}")
```

## Besondere Hinweise

### Cloud-Synchronisation

**Warnung**: Bei Cloud-Synchronisation können Konflikte entstehen, wenn die Anwendung auf mehreren Geräten gleichzeitig läuft!

**Empfehlung**:
- Schließe TimeTracker auf allen Geräten außer einem
- Warte, bis die Cloud-Sync abgeschlossen ist
- Starte TimeTracker auf dem anderen Gerät

### Netzwerklaufwerke

Bei Netzwerklaufwerken können Leistungsprobleme auftreten. Die Datenbank sollte idealerweise lokal gespeichert werden.

### Migration existierender Daten

Um eine bestehende Datenbank an einen neuen Ort zu verschieben:

1. Schließe TimeTracker vollständig
2. Kopiere die Datei `timetracker.db` an den neuen Ort
3. Konfiguriere den neuen Pfad in den Einstellungen oder `.env`
4. Starte TimeTracker neu
5. Überprüfe, dass deine Daten vorhanden sind
6. Lösche die alte Datenbank-Datei (optional)

## Technische Details

### Datenbankpfad-Auflösung

Die Anwendung löst den Datenbankpfad in folgender Reihenfolge auf:

1. **Konstruktor-Parameter** (nur für programmatische Nutzung)
2. **Umgebungsvariable** `DATABASE_PATH` (aus `.env` geladen)
3. **Standard-Pfad** `%USERPROFILE%\.timetracker\timetracker.db`

### Verzeichnis-Erstellung

- Parent-Verzeichnisse werden automatisch erstellt
- Fehlt das Verzeichnis, wird es angelegt
- Bei fehlenden Berechtigungen schlägt die Initialisierung fehl

### Thread-Safety

Die Datenbank ist thread-safe und kann von mehreren Threads gleichzeitig verwendet werden. Allerdings ist sie **nicht** für den gleichzeitigen Zugriff von mehreren Prozessen/Geräten ausgelegt.

## Troubleshooting

### Fehler: "Permission denied"

- Überprüfe die Schreibrechte für das Zielverzeichnis
- Verwende einen Pfad, für den du Schreibrechte hast

### Fehler: "Database is locked"

- Eine andere Instanz von TimeTracker verwendet die Datenbank
- Schließe alle TimeTracker-Instanzen
- Bei Netzwerklaufwerken: Warte auf Sync-Abschluss

### Daten sind nach Pfadänderung weg

- Die alte Datenbank ist noch vorhanden, aber nicht geladen
- Kopiere die Datei vom alten zum neuen Pfad
- Oder setze den Pfad zurück auf den alten Ort

### Änderungen werden nicht übernommen

- Hast du die Anwendung nach der Änderung neu gestartet?
- Überprüfe die `.env` Datei auf Schreibfehler
- Schaue im Log nach Fehlermeldungen

## Tests

Die Funktionalität ist vollständig getestet. Du kannst die Tests ausführen mit:

```bash
pytest tests/test_database_path.py -v
```

## Siehe auch

- [CLAUDE.md](CLAUDE.md) - Entwicklungsrichtlinien
- [README.md](README.md) - Allgemeine Dokumentation
