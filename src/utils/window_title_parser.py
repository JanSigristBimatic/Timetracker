"""Extraction of file names and content descriptions from window titles.

Pure function, extracted from the main window so the pattern
matching can be unit tested without a GUI.
"""

import re
from typing import Optional


def extract_filename_from_title(window_title: Optional[str]) -> Optional[str]:
    """Extract a file name or relevant content from a window title.

    Args:
        window_title: Raw window title as reported by the OS

    Returns:
        Extracted file/content name, or None if nothing meaningful found
    """
    if not window_title:
        return None

    # Pattern 1: Autodesk/CAD style - "Program - [filename.ext]"
    autodesk_match = re.search(r"\[([^\]]+\.[a-zA-Z0-9]+)\]", window_title)
    if autodesk_match:
        return autodesk_match.group(1)

    # Pattern 1b: Cyclone 3DR - "project_name - Cyclone 3DR version"
    cyclone_match = re.match(r"^(.+?)\s*-\s*Cyclone 3DR", window_title)
    if cyclone_match:
        return cyclone_match.group(1).strip()

    # Pattern 1c: Revit - "project_name - Autodesk Revit" or similar
    revit_match = re.match(r"^(.+?)\s*-\s*(Autodesk\s+)?Revit", window_title)
    if revit_match:
        return revit_match.group(1).strip()

    # Pattern 1d: Blender - "filename.blend - Blender" or "Blender - filename.blend"
    blender_match = re.search(r"(.+?\.blend)", window_title)
    if blender_match and "Blender" in window_title:
        return blender_match.group(1).strip()

    # Pattern 2: Teams chat - "Chat | Person Name | ..."
    teams_match = re.search(r"Chat\s*\|\s*([^|]+?)\s*\|", window_title)
    if teams_match:
        return teams_match.group(1).strip()

    # Pattern 3: Slack - "#channel-name | Workspace - Slack"
    slack_match = re.search(r"^(#[^\|]+)\s*\|", window_title)
    if slack_match:
        return slack_match.group(1).strip()

    # Pattern 4: Zoom - "Zoom Meeting - Meeting Name"
    zoom_match = re.match(r"^Zoom Meeting\s*-\s*(.+)", window_title)
    if zoom_match:
        return zoom_match.group(1).strip()

    # Pattern 5: JetBrains IDEs - "filename.ext - Project [Path] - IDE"
    jetbrains_match = re.match(
        r"^([^\-]+\.[a-zA-Z0-9]+)\s*-\s*([^\[]+)", window_title
    )
    if jetbrains_match and (
        "PyCharm" in window_title
        or "IntelliJ" in window_title
        or "WebStorm" in window_title
        or "PhpStorm" in window_title
    ):
        filename = jetbrains_match.group(1).strip()
        project = jetbrains_match.group(2).strip()
        return f"{filename} - {project}"

    # Pattern 6: VS Code style - "content... - Project - Visual Studio Code"
    vscode_match = re.match(
        r"^(.+?)\s*-\s*([^-]+)\s*-\s*Visual Studio Code", window_title
    )
    if vscode_match:
        content = vscode_match.group(1).strip()
        project = vscode_match.group(2).strip()
        return f"{content} - {project}"

    # Pattern 7: Microsoft Office - "filename.ext - Word/Excel/PowerPoint"
    office_match = re.match(
        r"^(.+?\.(docx?|xlsx?|pptx?|pdf))\s*-\s*(Microsoft\s+)?(Word|Excel|PowerPoint|Outlook)",
        window_title,
        re.IGNORECASE,
    )
    if office_match:
        return office_match.group(1)

    # Pattern 8: Adobe Reader/Acrobat - "filename.pdf - Adobe..."
    adobe_match = re.match(r"^(.+?\.pdf)\s*-\s*Adobe", window_title, re.IGNORECASE)
    if adobe_match:
        return adobe_match.group(1)

    # Pattern 9: Notepad++ - "filename.ext - Notepad++"
    notepad_match = re.match(
        r"^(.+?\.[a-zA-Z0-9]+)\s*-\s*Notepad\+\+", window_title
    )
    if notepad_match:
        return notepad_match.group(1)

    # Pattern 10: Browsers - "Page Title - Browser Name"
    browser_match = re.match(
        r"^(.+?)\s*-\s*(Google Chrome|Mozilla Firefox|Microsoft Edge|Opera|Safari|Brave)$",
        window_title,
    )
    if browser_match:
        page_title = browser_match.group(1).strip()
        return page_title[:80] if len(page_title) > 80 else page_title

    # Pattern 11: Outlook - various formats
    if "Outlook" in window_title:
        outlook_cleaned = re.sub(
            r"\s*-\s*(Microsoft\s+)?Outlook.*$", "", window_title
        )
        if outlook_cleaned:
            parts = outlook_cleaned.split(" - ")
            return parts[0].strip()[:60]

    # Pattern 12: Figma - "Design Name - Figma"
    figma_match = re.match(r"^(.+?)\s*-\s*Figma$", window_title)
    if figma_match:
        return figma_match.group(1).strip()

    # Pattern 13: General file with extension
    file_match = re.search(r'([^\\/:\*\?"<>\|]+\.[a-zA-Z0-9]+)', window_title)
    if file_match:
        filename = file_match.group(1)
        filename = re.sub(
            r"\s*-\s*(Visual Studio Code|Notepad|Word|Excel|PowerPoint|Adobe|Reader).*$",
            "",
            filename,
        )
        return filename.strip()

    # Pattern 14: For other apps, strip known app names at the end
    cleaned = re.sub(
        r"\s*-\s*(Microsoft Teams|Google Chrome|Firefox|Edge|Outlook|Discord|Spotify)$",
        "",
        window_title,
    )

    if cleaned != window_title and cleaned.strip():
        parts = cleaned.split(" - ")
        if len(parts) > 0:
            result = parts[0].strip()
            return result[:60] if len(result) > 60 else result

    return None
