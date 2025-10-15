"""
Smart Project Assigner - Intelligente Projektzuordnung

Lernt aus bisherigen Zuordnungen und schlägt automatisch Projekte vor.
Verwendet Pattern-Matching und statistische Analyse.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Any
import re

from core.database_protocol import DatabaseProtocol


class SmartProjectAssigner:
    """Intelligente Projektzuordnung basierend auf Lernmustern"""

    def __init__(self, database: DatabaseProtocol):
        self.database = database
        self.patterns = {}  # Gelernte Muster
        self.app_project_map = {}  # App -> Projekt Mapping
        self.keyword_project_map = {}  # Keywords -> Projekt Mapping

    def learn_from_history(self, days_back: int = 90) -> None:
        """
        Lernt aus historischen Zuordnungen

        Args:
            days_back: Anzahl Tage zurück zum Lernen
        """
        print(f"[LEARN] Analysiere Aktivitäten der letzten {days_back} Tage...")

        # Hole alle Aktivitäten mit Projektzuordnung
        start_date = datetime.now() - timedelta(days=days_back)
        activities = self.database.get_activities(start_date=start_date)

        # Filtere nur zugeordnete Aktivitäten
        assigned = [a for a in activities if a.get("project_id")]

        print(f"[LEARN] {len(assigned)} zugeordnete Aktivitäten gefunden")

        # Lerne App -> Projekt Muster
        app_projects = defaultdict(lambda: defaultdict(int))

        for activity in assigned:
            app_name = activity["app_name"]
            project_id = activity["project_id"]
            duration = activity["duration"]

            # Zähle gewichtete Zeit pro App-Projekt Kombination
            app_projects[app_name][project_id] += duration

        # Erstelle App -> Projekt Mapping (häufigstes Projekt pro App)
        for app_name, project_durations in app_projects.items():
            # Nimm Projekt mit meister Zeit
            best_project = max(project_durations.items(), key=lambda x: x[1])
            self.app_project_map[app_name] = best_project[0]

        print(f"[LEARN] {len(self.app_project_map)} App-Muster gelernt")

        # Lerne Keyword -> Projekt Muster aus Fenstertiteln
        keyword_projects = defaultdict(lambda: defaultdict(int))

        for activity in assigned:
            window_title = activity.get("window_title", "").lower()
            project_id = activity["project_id"]
            duration = activity["duration"]

            # Extrahiere wichtige Keywords (Wörter länger als 3 Zeichen)
            keywords = re.findall(r"\b\w{4,}\b", window_title)

            for keyword in keywords:
                keyword_projects[keyword][project_id] += duration

        # Erstelle Keyword -> Projekt Mapping
        for keyword, project_durations in keyword_projects.items():
            if len(project_durations) >= 1:  # Mindestens 1 Projekt
                best_project = max(project_durations.items(), key=lambda x: x[1])
                # Nur wenn deutliche Präferenz (>60% der Zeit)
                total_time = sum(project_durations.values())
                if best_project[1] / total_time > 0.6:
                    self.keyword_project_map[keyword] = best_project[0]

        print(f"[LEARN] {len(self.keyword_project_map)} Keyword-Muster gelernt")

    def suggest_project(self, activity: dict[str, Any]) -> Optional[int]:
        """
        Schlägt ein Projekt für eine Aktivität vor

        Args:
            activity: Aktivitätsdaten

        Returns:
            Projekt-ID oder None
        """
        app_name = activity["app_name"]
        window_title = activity.get("window_title", "").lower()

        # Strategie 1: Exakte App-Übereinstimmung
        if app_name in self.app_project_map:
            return self.app_project_map[app_name]

        # Strategie 2: Keyword-Matching im Fenstertitel
        keywords = re.findall(r"\b\w{4,}\b", window_title)

        # Zähle Matches pro Projekt
        project_scores = defaultdict(int)

        for keyword in keywords:
            if keyword in self.keyword_project_map:
                project_id = self.keyword_project_map[keyword]
                project_scores[project_id] += 1

        # Nimm Projekt mit meisten Keyword-Matches
        if project_scores:
            best_project = max(project_scores.items(), key=lambda x: x[1])
            return best_project[0]

        return None

    def get_confidence(self, activity: dict[str, Any], project_id: int) -> float:
        """
        Berechnet Konfidenz-Score für eine Projektzuordnung

        Args:
            activity: Aktivitätsdaten
            project_id: Vorgeschlagene Projekt-ID

        Returns:
            Konfidenz zwischen 0.0 und 1.0
        """
        app_name = activity["app_name"]
        window_title = activity.get("window_title", "").lower()

        confidence = 0.0

        # App-Match = hohe Konfidenz
        if app_name in self.app_project_map:
            if self.app_project_map[app_name] == project_id:
                confidence += 0.6

        # Keyword-Matches
        keywords = re.findall(r"\b\w{4,}\b", window_title)
        matching_keywords = 0

        for keyword in keywords:
            if keyword in self.keyword_project_map:
                if self.keyword_project_map[keyword] == project_id:
                    matching_keywords += 1

        if keywords:
            keyword_confidence = matching_keywords / len(keywords)
            confidence += 0.4 * keyword_confidence

        return min(confidence, 1.0)

    def auto_assign_unassigned(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_confidence: float = 0.5,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        Ordnet automatisch nicht zugeordnete Aktivitäten zu

        Args:
            start_date: Start-Datum
            end_date: End-Datum
            min_confidence: Minimale Konfidenz für Auto-Zuordnung
            dry_run: Wenn True, nur simulieren

        Returns:
            Statistiken über Zuordnungen
        """
        # Lerne zuerst aus Historie
        self.learn_from_history()

        # Hole nicht zugeordnete Aktivitäten
        activities = self.database.get_activities(start_date=start_date, end_date=end_date)

        unassigned = [a for a in activities if not a.get("project_id")]

        print(f"[AUTO-ASSIGN] {len(unassigned)} nicht zugeordnete Aktivitäten gefunden")

        stats = {
            "total_unassigned": len(unassigned),
            "assigned": 0,
            "skipped_low_confidence": 0,
            "assignments": [],
        }

        # Hole Projekt-Namen für Ausgabe
        projects = {p["id"]: p["name"] for p in self.database.get_projects()}

        for activity in unassigned:
            # Vorschlag holen
            suggested_project = self.suggest_project(activity)

            if suggested_project:
                confidence = self.get_confidence(activity, suggested_project)

                if confidence >= min_confidence:
                    assignment_info = {
                        "activity_id": activity["id"],
                        "app_name": activity["app_name"],
                        "window_title": activity.get("window_title", "")[:50],
                        "project": projects.get(suggested_project, "Unknown"),
                        "confidence": f"{confidence:.0%}",
                    }

                    if not dry_run:
                        # Tatsächlich zuordnen
                        self.database.assign_activity_to_project(activity["id"], suggested_project)

                    stats["assigned"] += 1
                    stats["assignments"].append(assignment_info)
                else:
                    stats["skipped_low_confidence"] += 1

        return stats

    def get_suggestions_for_review(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        min_duration: int = 60,  # Mindestdauer in Sekunden (Standard: 1 Minute)
    ) -> list[dict[str, Any]]:
        """
        Holt Vorschläge zur manuellen Review

        Args:
            start_date: Start-Datum
            end_date: End-Datum
            limit: Maximale Anzahl Vorschläge
            min_duration: Mindestdauer in Sekunden (filtert sehr kurze Aktivitäten)

        Returns:
            Liste von Vorschlägen mit Aktivität und Projekt
        """
        self.learn_from_history()

        # Hole nicht zugeordnete Aktivitäten
        activities = self.database.get_activities(start_date=start_date, end_date=end_date)

        # Filtere nach nicht zugeordnet UND Mindestdauer (ignoriere sehr kurze Aktivitäten)
        unassigned = [
            a for a in activities
            if not a.get("project_id") and a.get("duration", 0) >= min_duration
        ]

        # Hole Projekt-Namen
        projects = {p["id"]: p for p in self.database.get_projects()}

        suggestions = []

        for activity in unassigned[:limit]:
            suggested_project_id = self.suggest_project(activity)

            if suggested_project_id:
                confidence = self.get_confidence(activity, suggested_project_id)
                project = projects.get(suggested_project_id)

                suggestions.append(
                    {
                        "activity": activity,
                        "suggested_project_id": suggested_project_id,
                        "suggested_project_name": project["name"] if project else "Unknown",
                        "suggested_project_color": project["color"] if project else "#999",
                        "confidence": confidence,
                        "confidence_percent": f"{confidence:.0%}",
                    }
                )

        # Sortiere nach Konfidenz (höchste zuerst)
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)

        return suggestions
