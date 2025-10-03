# Überlappungs-Fix für TimeTracker

## Problem
Die Gesamtzeit wurde zu hoch berechnet, weil sich Aktivitäten in der Datenbank überlappten. Dies führte zu:
- Doppelzählung von Zeit
- Unrealistisch hohen Tageswerten
- Inkonsistenten Statistiken

## Ursachen
1. **Mehrfach laufende Tracker**: Beim Entwickeln/Testen liefen mehrere Tracker-Instanzen parallel
2. **Fehlende Überlappungsprüfung**: Die Datenbank prüfte nicht auf zeitliche Konflikte
3. **Keine automatische Bereinigung**: Alte Überlappungen blieben in der Datenbank

## Lösung

### 1. Überlappungs-Prävention (database.py)
Die `save_activity()` Methode wurde erweitert:

```python
# Vor dem Speichern wird geprüft, ob sich die neue Aktivität
# mit bestehenden Aktivitäten überschneidet

# Wenn ja:
- Bestehende Aktivität wird gekürzt (endet wenn neue beginnt)
- Aktivitäten mit 0 Sekunden werden gelöscht
- Neue Aktivität wird normal gespeichert
```

**Vorteile:**
- Keine Überlappungen mehr in Zukunft
- Automatische Lösung bei Konflikten
- Thread-sicher durch bestehenden `_write_lock`

### 2. Cleanup-Script (cleanup_overlaps.py)
Bereinigt bestehende Überlappungen in der Datenbank:

```bash
py cleanup_overlaps.py
```

**Features:**
- Findet alle Überlappungen
- Zeigt Dry-Run Preview
- Fragt vor Änderungen nach Bestätigung
- Bereinigt iterativ (re-fetcht nach jeder Änderung)

**Strategien:**
1. Idle-Aktivitäten werden gelöscht
2. Vollständig enthaltene Aktivitäten werden gelöscht
3. Gleiche Apps werden gemerged
4. Verschiedene Apps: Erste wird gekürzt

### 3. Tests (test_overlap_prevention.py)
Umfassende Test-Suite mit 7 Tests:

```bash
py -m pytest tests/test_overlap_prevention.py -v
```

**Getestet werden:**
- Sequentielle Aktivitäten (kein Overlap)
- Teilweise Überlappungen
- Vollständige Überlappungen
- Multiple Überlappungen
- Minimale (1s) Überlappungen
- Idle-Aktivitäten
- Lücken zwischen Aktivitäten

## Verwendung

### Für bestehende Datenbank:
```bash
# 1. Backup erstellen
copy "%USERPROFILE%\.timetracker\timetracker.db" "%USERPROFILE%\.timetracker\timetracker.db.backup"

# 2. Cleanup ausführen
py cleanup_overlaps.py

# 3. Anwendung neu starten
```

### Für neue Aktivitäten:
Automatisch aktiv! Der Tracker verhindert nun Überlappungen beim Speichern.

## Analyse-Tool
Das Script `analyze_db.py` hilft bei der Diagnose:

```bash
py analyze_db.py
```

**Zeigt:**
- Gesamtstatistik (Aktivitäten, Zeit, Idle)
- Überlappungen
- Top 10 Apps
- Sehr lange Aktivitäten (>1h)
- Stunden-Verteilung
- Duplikate

## Statistik-Korrektur (main_window.py)
Die `update_stats()` Methode wurde korrigiert:
- Verwendet jetzt **alle** Aktivitäten des Tages für Gesamtzeit
- Nicht nur gefilterte Aktivitäten
- Zeigt Filter-Info wenn aktiv

## Ergebnis
Nach der Bereinigung:
- ✓ Keine Überlappungen mehr
- ✓ Korrekte Gesamtzeit
- ✓ Zukünftige Überlappungen werden verhindert
- ✓ Statistiken sind konsistent

## Migration von alter Version
1. Backup der Datenbank erstellen
2. `cleanup_overlaps.py` ausführen
3. Anwendung aktualisieren (neue database.py)
4. Tracker neu starten
5. Mit `analyze_db.py` verifizieren

## Tests ausführen
```bash
# Nur Overlap-Tests
py -m pytest tests/test_overlap_prevention.py -v

# Alle Tests
py -m pytest

# Mit Coverage
py -m pytest --cov=src tests/test_overlap_prevention.py
```

## Bekannte Einschränkungen
- Das Cleanup-Script muss manuell ausgeführt werden (einmalig)
- Sehr viele Überlappungen (>1000) können lange dauern
- Backup ist Pflicht vor Cleanup!

## Zukünftige Verbesserungen
- [ ] Automatischer Cleanup beim Start
- [ ] GUI-Integration für Overlap-Erkennung
- [ ] Warnung bei verdächtigen Zeitwerten
- [ ] Export ohne Überlappungen
