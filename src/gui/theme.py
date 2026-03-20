"""
Design System und Theme Management für TimeTracker
Unterstützt Light und Dark Mode mit modernen UI-Verbesserungen
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


class ThemeMode(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"  # Folgt System-Einstellung


@dataclass
class ThemeColors:
    """Farbdefinitionen für ein Theme"""
    # Hintergrundfarben
    background: str
    background_secondary: str
    background_tertiary: str

    # Vordergrundfarben (Text)
    text_primary: str
    text_secondary: str
    text_muted: str

    # Akzentfarben
    accent: str
    accent_hover: str
    accent_pressed: str

    # Semantische Farben
    success: str
    success_hover: str
    warning: str
    warning_hover: str
    error: str
    error_hover: str
    info: str

    # UI-Elemente
    border: str
    border_light: str
    shadow: str

    # Spezielle Elemente
    card_background: str
    input_background: str
    button_background: str
    button_text: str

    # Timeline-spezifisch
    timeline_background: str
    timeline_grid: str
    timeline_idle: str
    timeline_active: str
    timeline_selected_border: str

    # Scrollbar
    scrollbar_track: str
    scrollbar_handle: str
    scrollbar_handle_hover: str


# Light Theme Farben
LIGHT_THEME = ThemeColors(
    # Hintergrund
    background="#ffffff",
    background_secondary="#f8f9fa",
    background_tertiary="#e9ecef",

    # Text
    text_primary="#212529",
    text_secondary="#495057",
    text_muted="#6c757d",

    # Akzent (Blau)
    accent="#3498db",
    accent_hover="#2980b9",
    accent_pressed="#1f6dad",

    # Semantisch
    success="#27ae60",
    success_hover="#219a52",
    warning="#f39c12",
    warning_hover="#d68910",
    error="#e74c3c",
    error_hover="#c0392b",
    info="#17a2b8",

    # UI
    border="#dee2e6",
    border_light="#e9ecef",
    shadow="rgba(0, 0, 0, 0.1)",

    # Spezielle Elemente
    card_background="#ffffff",
    input_background="#ffffff",
    button_background="#e9ecef",
    button_text="#212529",

    # Timeline
    timeline_background="#ffffff",
    timeline_grid="#ecf0f1",
    timeline_idle="#95a5a6",
    timeline_active="#3498db",
    timeline_selected_border="#ffd700",

    # Scrollbar
    scrollbar_track="#f1f1f1",
    scrollbar_handle="#c1c1c1",
    scrollbar_handle_hover="#a8a8a8",
)


# Dark Theme Farben
DARK_THEME = ThemeColors(
    # Hintergrund
    background="#1a1a2e",
    background_secondary="#16213e",
    background_tertiary="#0f3460",

    # Text
    text_primary="#e8e8e8",
    text_secondary="#b8b8b8",
    text_muted="#808080",

    # Akzent (Blau)
    accent="#4fc3f7",
    accent_hover="#29b6f6",
    accent_pressed="#0288d1",

    # Semantisch
    success="#66bb6a",
    success_hover="#4caf50",
    warning="#ffb74d",
    warning_hover="#ffa726",
    error="#ef5350",
    error_hover="#e53935",
    info="#4dd0e1",

    # UI
    border="#2d3748",
    border_light="#3d4a5c",
    shadow="rgba(0, 0, 0, 0.3)",

    # Spezielle Elemente
    card_background="#16213e",
    input_background="#1a1a2e",
    button_background="#0f3460",
    button_text="#e8e8e8",

    # Timeline
    timeline_background="#1a1a2e",
    timeline_grid="#2d3748",
    timeline_idle="#4a5568",
    timeline_active="#4fc3f7",
    timeline_selected_border="#ffd700",

    # Scrollbar
    scrollbar_track="#1a1a2e",
    scrollbar_handle="#4a5568",
    scrollbar_handle_hover="#718096",
)


class ThemeManager:
    """Verwaltet das aktuelle Theme der Anwendung"""

    _instance = None
    _current_theme: ThemeMode = ThemeMode.LIGHT
    _colors: ThemeColors = LIGHT_THEME
    _settings: QSettings = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialisiere den ThemeManager"""
        self._settings = QSettings("TimeTracker", "TimeTracker")
        saved_theme = self._settings.value("theme", "light")

        if saved_theme == "dark":
            self._current_theme = ThemeMode.DARK
            self._colors = DARK_THEME
        else:
            self._current_theme = ThemeMode.LIGHT
            self._colors = LIGHT_THEME

    @property
    def current_theme(self) -> ThemeMode:
        return self._current_theme

    @property
    def colors(self) -> ThemeColors:
        return self._colors

    @property
    def is_dark(self) -> bool:
        return self._current_theme == ThemeMode.DARK

    def set_theme(self, theme: ThemeMode):
        """Setze das aktuelle Theme"""
        self._current_theme = theme

        if theme == ThemeMode.DARK:
            self._colors = DARK_THEME
        else:
            self._colors = LIGHT_THEME

        # Speichere Einstellung
        self._settings.setValue("theme", theme.value)

        # Wende Theme auf alle Fenster an
        self.apply_theme()

    def toggle_theme(self):
        """Wechsle zwischen Light und Dark Mode"""
        if self._current_theme == ThemeMode.LIGHT:
            self.set_theme(ThemeMode.DARK)
        else:
            self.set_theme(ThemeMode.LIGHT)

    def apply_theme(self):
        """Wende das aktuelle Theme auf die Anwendung an"""
        app = QApplication.instance()
        if app:
            app.setStyleSheet(self.get_stylesheet())

    def get_stylesheet(self) -> str:
        """Generiere das komplette Stylesheet für das aktuelle Theme"""
        c = self._colors

        return f"""
        /* ========== GLOBALE STYLES ========== */

        QWidget {{
            background-color: {c.background};
            color: {c.text_primary};
            font-family: "Segoe UI", "SF Pro Display", -apple-system, sans-serif;
            font-size: 13px;
        }}

        QMainWindow {{
            background-color: {c.background};
        }}

        /* ========== LABELS ========== */

        QLabel {{
            background-color: transparent;
            color: {c.text_primary};
            padding: 2px;
        }}

        QLabel[class="title"] {{
            font-size: 18px;
            font-weight: bold;
            color: {c.text_primary};
        }}

        QLabel[class="subtitle"] {{
            font-size: 14px;
            font-weight: 600;
            color: {c.text_secondary};
        }}

        QLabel[class="muted"] {{
            color: {c.text_muted};
            font-style: italic;
        }}

        /* ========== BUTTONS ========== */

        QPushButton {{
            background-color: {c.button_background};
            color: {c.button_text};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 500;
            min-height: 20px;
        }}

        QPushButton:hover {{
            background-color: {c.background_tertiary};
            border-color: {c.accent};
        }}

        QPushButton:pressed {{
            background-color: {c.accent};
            color: white;
        }}

        QPushButton:disabled {{
            background-color: {c.background_secondary};
            color: {c.text_muted};
            border-color: {c.border_light};
        }}

        /* Primary Button */
        QPushButton[class="primary"] {{
            background-color: {c.accent};
            color: white;
            border: none;
            font-weight: 600;
        }}

        QPushButton[class="primary"]:hover {{
            background-color: {c.accent_hover};
        }}

        QPushButton[class="primary"]:pressed {{
            background-color: {c.accent_pressed};
        }}

        /* Success Button */
        QPushButton[class="success"] {{
            background-color: {c.success};
            color: white;
            border: none;
            font-weight: 600;
        }}

        QPushButton[class="success"]:hover {{
            background-color: {c.success_hover};
        }}

        /* Danger Button */
        QPushButton[class="danger"] {{
            background-color: {c.error};
            color: white;
            border: none;
        }}

        QPushButton[class="danger"]:hover {{
            background-color: {c.error_hover};
        }}

        /* Icon Button (klein, quadratisch) */
        QPushButton[class="icon"] {{
            padding: 6px;
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
        }}

        /* ========== INPUTS ========== */

        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: {c.input_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 12px;
            selection-background-color: {c.accent};
            selection-color: white;
        }}

        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {c.accent};
            border-width: 2px;
        }}

        QLineEdit:disabled, QTextEdit:disabled {{
            background-color: {c.background_secondary};
            color: {c.text_muted};
        }}

        /* ========== COMBOBOX ========== */

        QComboBox {{
            background-color: {c.input_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 12px;
            min-height: 20px;
        }}

        QComboBox:hover {{
            border-color: {c.accent};
        }}

        QComboBox:focus {{
            border-color: {c.accent};
            border-width: 2px;
        }}

        QComboBox::drop-down {{
            border: none;
            width: 24px;
            padding-right: 8px;
        }}

        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {c.text_secondary};
            margin-right: 8px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {c.card_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 4px;
            selection-background-color: {c.accent};
            selection-color: white;
        }}

        /* ========== SPINBOX ========== */

        QSpinBox, QDoubleSpinBox {{
            background-color: {c.input_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 12px;
        }}

        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {c.accent};
        }}

        QSpinBox::up-button, QSpinBox::down-button,
        QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
            background-color: {c.button_background};
            border: none;
            width: 20px;
        }}

        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {c.background_tertiary};
        }}

        /* ========== DATEEDIT ========== */

        QDateEdit {{
            background-color: {c.input_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 12px;
        }}

        QDateEdit:focus {{
            border-color: {c.accent};
        }}

        QDateEdit::drop-down {{
            border: none;
            width: 24px;
        }}

        QCalendarWidget {{
            background-color: {c.card_background};
        }}

        QCalendarWidget QToolButton {{
            color: {c.text_primary};
            background-color: {c.button_background};
            border-radius: 4px;
            padding: 4px;
        }}

        QCalendarWidget QToolButton:hover {{
            background-color: {c.accent};
            color: white;
        }}

        /* ========== CHECKBOX & RADIOBUTTON ========== */

        QCheckBox, QRadioButton {{
            color: {c.text_primary};
            spacing: 8px;
        }}

        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {c.border};
            background-color: {c.input_background};
        }}

        QCheckBox::indicator {{
            border-radius: 4px;
        }}

        QRadioButton::indicator {{
            border-radius: 9px;
        }}

        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {c.accent};
            border-color: {c.accent};
        }}

        QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
            border-color: {c.accent};
        }}

        /* ========== SLIDER ========== */

        QSlider::groove:horizontal {{
            height: 6px;
            background-color: {c.background_tertiary};
            border-radius: 3px;
        }}

        QSlider::handle:horizontal {{
            background-color: {c.accent};
            width: 18px;
            height: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }}

        QSlider::handle:horizontal:hover {{
            background-color: {c.accent_hover};
        }}

        QSlider::sub-page:horizontal {{
            background-color: {c.accent};
            border-radius: 3px;
        }}

        /* ========== SCROLLBAR ========== */

        QScrollBar:vertical {{
            background-color: {c.scrollbar_track};
            width: 12px;
            border-radius: 6px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background-color: {c.scrollbar_handle};
            border-radius: 6px;
            min-height: 30px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {c.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        QScrollBar:horizontal {{
            background-color: {c.scrollbar_track};
            height: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {c.scrollbar_handle};
            border-radius: 6px;
            min-width: 30px;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {c.scrollbar_handle_hover};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}

        /* ========== SCROLLAREA ========== */

        QScrollArea {{
            background-color: {c.background};
            border: none;
        }}

        QScrollArea > QWidget > QWidget {{
            background-color: {c.background};
        }}

        /* ========== FRAME ========== */

        QFrame {{
            background-color: {c.background};
            border: none;
        }}

        QFrame[class="card"] {{
            background-color: {c.card_background};
            border: 1px solid {c.border};
            border-radius: 8px;
            padding: 12px;
        }}

        QFrame[frameShape="4"], QFrame[frameShape="5"] {{
            background-color: {c.border};
            max-height: 1px;
        }}

        /* ========== GROUPBOX ========== */

        QGroupBox {{
            background-color: {c.card_background};
            border: 1px solid {c.border};
            border-radius: 8px;
            margin-top: 12px;
            padding: 16px;
            padding-top: 24px;
            font-weight: 600;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px;
            color: {c.text_primary};
            background-color: {c.card_background};
        }}

        /* ========== LISTWIDGET ========== */

        QListWidget {{
            background-color: {c.input_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 8px;
            padding: 4px;
        }}

        QListWidget::item {{
            padding: 8px 12px;
            border-radius: 4px;
        }}

        QListWidget::item:hover {{
            background-color: {c.background_secondary};
        }}

        QListWidget::item:selected {{
            background-color: {c.accent};
            color: white;
        }}

        /* ========== TABLEWIDGET ========== */

        QTableWidget, QTableView {{
            background-color: {c.input_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 8px;
            gridline-color: {c.border_light};
        }}

        QTableWidget::item, QTableView::item {{
            padding: 8px;
        }}

        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {c.accent};
            color: white;
        }}

        QHeaderView::section {{
            background-color: {c.background_secondary};
            color: {c.text_primary};
            padding: 8px;
            border: none;
            border-bottom: 1px solid {c.border};
            font-weight: 600;
        }}

        /* ========== TABWIDGET ========== */

        QTabWidget::pane {{
            background-color: {c.card_background};
            border: 1px solid {c.border};
            border-radius: 8px;
            margin-top: -1px;
        }}

        QTabBar::tab {{
            background-color: {c.background_secondary};
            color: {c.text_secondary};
            padding: 10px 20px;
            border: 1px solid {c.border};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}

        QTabBar::tab:selected {{
            background-color: {c.card_background};
            color: {c.text_primary};
            font-weight: 600;
        }}

        QTabBar::tab:hover:!selected {{
            background-color: {c.background_tertiary};
        }}

        /* ========== DIALOG ========== */

        QDialog {{
            background-color: {c.background};
        }}

        /* ========== MENU ========== */

        QMenu {{
            background-color: {c.card_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 8px;
            padding: 8px 0;
        }}

        QMenu::item {{
            padding: 8px 32px;
        }}

        QMenu::item:selected {{
            background-color: {c.accent};
            color: white;
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {c.border};
            margin: 4px 8px;
        }}

        /* ========== MENUBAR ========== */

        QMenuBar {{
            background-color: {c.background};
            color: {c.text_primary};
            border-bottom: 1px solid {c.border};
            padding: 4px;
        }}

        QMenuBar::item {{
            padding: 6px 12px;
            border-radius: 4px;
        }}

        QMenuBar::item:selected {{
            background-color: {c.accent};
            color: white;
        }}

        /* ========== TOOLBAR ========== */

        QToolBar {{
            background-color: {c.background_secondary};
            border: none;
            padding: 4px;
            spacing: 4px;
        }}

        QToolButton {{
            background-color: transparent;
            color: {c.text_primary};
            border: none;
            border-radius: 6px;
            padding: 8px;
        }}

        QToolButton:hover {{
            background-color: {c.background_tertiary};
        }}

        QToolButton:pressed {{
            background-color: {c.accent};
            color: white;
        }}

        /* ========== STATUSBAR ========== */

        QStatusBar {{
            background-color: {c.background_secondary};
            color: {c.text_secondary};
            border-top: 1px solid {c.border};
        }}

        /* ========== TOOLTIP ========== */

        QToolTip {{
            background-color: {c.card_background};
            color: {c.text_primary};
            border: 1px solid {c.border};
            border-radius: 6px;
            padding: 8px 12px;
        }}

        /* ========== PROGRESSBAR ========== */

        QProgressBar {{
            background-color: {c.background_tertiary};
            border: none;
            border-radius: 4px;
            height: 8px;
            text-align: center;
        }}

        QProgressBar::chunk {{
            background-color: {c.accent};
            border-radius: 4px;
        }}

        /* ========== MESSAGEBOX ========== */

        QMessageBox {{
            background-color: {c.background};
        }}

        QMessageBox QLabel {{
            color: {c.text_primary};
        }}
        """

    def get_timeline_colors(self) -> Dict[str, QColor]:
        """Gibt die Timeline-Farben als QColor-Dict zurück"""
        c = self._colors
        return {
            'active': QColor(c.timeline_active),
            'idle': QColor(c.timeline_idle),
            'background': QColor(c.timeline_background),
            'grid': QColor(c.timeline_grid),
            'text': QColor(c.text_primary),
            'selected_border': QColor(c.timeline_selected_border),
        }

    def get_color(self, name: str) -> str:
        """Gibt eine Farbe nach Namen zurück"""
        return getattr(self._colors, name, self._colors.text_primary)

    def get_qcolor(self, name: str) -> QColor:
        """Gibt eine Farbe als QColor zurück"""
        return QColor(self.get_color(name))


# Globale Instanz
theme_manager = ThemeManager()


def get_theme() -> ThemeManager:
    """Gibt den ThemeManager zurück"""
    return theme_manager
