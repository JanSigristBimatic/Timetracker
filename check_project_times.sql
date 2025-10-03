-- Zeitstatistiken für den 3. Oktober 2025
-- Zeigt die Gesamtzeit pro Projekt

-- 1. Zeit pro Projekt (in Sekunden und Stunden)
SELECT
    COALESCE(p.name, 'Ohne Projekt') as projekt_name,
    p.color as farbe,
    SUM(a.duration) as sekunden,
    ROUND(SUM(a.duration)::numeric / 3600, 2) as stunden,
    ROUND((SUM(a.duration)::numeric / (SELECT SUM(duration) FROM activities WHERE timestamp >= '2025-10-03 00:00:00' AND timestamp < '2025-10-04 00:00:00' AND is_idle = FALSE) * 100), 1) as prozent,
    COUNT(*) as anzahl_aktivitaeten
FROM activities a
LEFT JOIN projects p ON a.project_id = p.id
WHERE a.timestamp >= '2025-10-03 00:00:00'
  AND a.timestamp < '2025-10-04 00:00:00'
  AND a.is_idle = FALSE
GROUP BY p.id, p.name, p.color
ORDER BY sekunden DESC;

-- 2. Zeit pro App (Top 15)
SELECT
    a.app_name,
    SUM(a.duration) as sekunden,
    ROUND(SUM(a.duration)::numeric / 3600, 2) as stunden,
    ROUND((SUM(a.duration)::numeric / (SELECT SUM(duration) FROM activities WHERE timestamp >= '2025-10-03 00:00:00' AND timestamp < '2025-10-04 00:00:00' AND is_idle = FALSE) * 100), 1) as prozent,
    COUNT(*) as anzahl_aktivitaeten
FROM activities a
WHERE a.timestamp >= '2025-10-03 00:00:00'
  AND a.timestamp < '2025-10-04 00:00:00'
  AND a.is_idle = FALSE
GROUP BY a.app_name
ORDER BY sekunden DESC
LIMIT 15;

-- 3. Gesamtstatistik für den Tag
SELECT
    DATE(timestamp) as datum,
    COUNT(*) as gesamt_aktivitaeten,
    SUM(CASE WHEN is_idle = FALSE THEN duration ELSE 0 END) as aktive_sekunden,
    ROUND(SUM(CASE WHEN is_idle = FALSE THEN duration ELSE 0 END)::numeric / 3600, 2) as aktive_stunden,
    SUM(CASE WHEN is_idle = TRUE THEN duration ELSE 0 END) as idle_sekunden,
    ROUND(SUM(CASE WHEN is_idle = TRUE THEN duration ELSE 0 END)::numeric / 3600, 2) as idle_stunden
FROM activities
WHERE timestamp >= '2025-10-03 00:00:00'
  AND timestamp < '2025-10-04 00:00:00'
GROUP BY DATE(timestamp);

-- 4. Zeit pro Datei (extrahiert aus window_title)
SELECT
    -- Extrahiere Dateinamen aus verschiedenen Formaten
    CASE
        WHEN window_title LIKE '%.%' THEN
            REGEXP_REPLACE(
                SUBSTRING(window_title FROM '([^\\/:*?"<>|]+\.[a-zA-Z0-9]+)'),
                ' - .*$', ''
            )
        ELSE 'Keine Datei erkannt'
    END as dateiname,
    SUM(duration) as sekunden,
    ROUND(SUM(duration)::numeric / 3600, 2) as stunden,
    ROUND((SUM(duration)::numeric / (SELECT SUM(duration) FROM activities WHERE timestamp >= '2025-10-03 00:00:00' AND timestamp < '2025-10-04 00:00:00' AND is_idle = FALSE) * 100), 1) as prozent,
    COUNT(*) as anzahl_aktivitaeten,
    MAX(window_title) as beispiel_titel
FROM activities
WHERE timestamp >= '2025-10-03 00:00:00'
  AND timestamp < '2025-10-04 00:00:00'
  AND is_idle = FALSE
  AND window_title IS NOT NULL
  AND window_title != ''
GROUP BY dateiname
HAVING SUM(duration) > 60  -- Nur Dateien mit mehr als 1 Minute
ORDER BY sekunden DESC
LIMIT 30;

-- 5. Details für BG-TG Projekt
SELECT
    a.timestamp,
    a.app_name,
    a.window_title,
    a.duration,
    ROUND(a.duration::numeric / 3600, 3) as stunden
FROM activities a
JOIN projects p ON a.project_id = p.id
WHERE p.name = 'BG-TG'
  AND a.timestamp >= '2025-10-03 00:00:00'
  AND a.timestamp < '2025-10-04 00:00:00'
  AND a.is_idle = FALSE
ORDER BY a.timestamp;
