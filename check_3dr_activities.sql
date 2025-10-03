-- Alle 3DR.exe Aktivitäten am 03.10.2025 (auch ohne Projektzuordnung)

-- 1. Alle 3DR.exe Aktivitäten (mit und ohne Projekt)
SELECT
    a.id,
    a.timestamp,
    a.app_name,
    a.window_title,
    a.duration,
    ROUND(a.duration::numeric / 3600, 3) as stunden,
    a.is_idle,
    COALESCE(p.name, 'KEIN PROJEKT') as projekt,
    a.project_id
FROM activities a
LEFT JOIN projects p ON a.project_id = p.id
WHERE a.app_name = '3DR.exe'
  AND a.timestamp >= '2025-10-03 00:00:00'
  AND a.timestamp < '2025-10-04 00:00:00'
ORDER BY a.timestamp;

-- 2. Zusammenfassung 3DR.exe nach Projekt
SELECT
    COALESCE(p.name, 'OHNE PROJEKT') as projekt,
    COUNT(*) as anzahl,
    SUM(a.duration) as sekunden,
    ROUND(SUM(a.duration)::numeric / 3600, 2) as stunden
FROM activities a
LEFT JOIN projects p ON a.project_id = p.id
WHERE a.app_name = '3DR.exe'
  AND a.timestamp >= '2025-10-03 00:00:00'
  AND a.timestamp < '2025-10-04 00:00:00'
  AND a.is_idle = FALSE
GROUP BY p.name
ORDER BY sekunden DESC;
