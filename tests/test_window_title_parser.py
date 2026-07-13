"""Tests for window title parsing"""
from utils.window_title_parser import extract_filename_from_title


class TestExtractFilename:
    def test_none_and_empty(self):
        assert extract_filename_from_title(None) is None
        assert extract_filename_from_title("") is None

    def test_cad_bracket_style(self):
        assert extract_filename_from_title(
            "Autodesk Civil 3D - [Bahnhof_Nord.dwg]"
        ) == "Bahnhof_Nord.dwg"

    def test_revit(self):
        assert extract_filename_from_title(
            "Projekt_X - Autodesk Revit 2024"
        ) == "Projekt_X"

    def test_office_word(self):
        assert extract_filename_from_title(
            "Bericht.docx - Word"
        ) == "Bericht.docx"

    def test_browser_page_title(self):
        assert extract_filename_from_title(
            "GitHub Dashboard - Google Chrome"
        ) == "GitHub Dashboard"

    def test_vscode(self):
        assert extract_filename_from_title(
            "main.py - Timetracker - Visual Studio Code"
        ) == "main.py - Timetracker"

    def test_teams_chat(self):
        assert extract_filename_from_title(
            "Chat | Max Muster | Microsoft Teams"
        ) == "Max Muster"

    def test_generic_file_extension(self):
        assert extract_filename_from_title(
            "readme.md"
        ) == "readme.md"

    def test_unknown_title_returns_none(self):
        assert extract_filename_from_title("Rechner") is None
