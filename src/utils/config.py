"""Configuration and constants"""
import os
from pathlib import Path

# Default processes to ignore (system processes, not relevant for tracking)
DEFAULT_IGNORED_PROCESSES = {
    'explorer.exe',
    'SearchHost.exe',
    'ShellExperienceHost.exe',
    'ApplicationFrameHost.exe',
    'SystemSettings.exe',
    'Taskmgr.exe',
    'dwm.exe',
    'SearchUI.exe',
    'StartMenuExperienceHost.exe',
    'LockApp.exe',
    'TextInputHost.exe',
    'SecurityHealthSystray.exe',
    'RuntimeBroker.exe',
    'sihost.exe',
    'ctfmon.exe',
    'python.exe',  # Don't track the TimeTracker app itself
    'pythonw.exe',
}

# Default windows with these titles should be ignored
DEFAULT_IGNORED_WINDOW_TITLES = {
    '',  # Empty titles
    'Program Manager',  # Desktop
    'Task Switching',
    'Windows Shell Experience Host',
}

def get_ignored_processes():
    """Get ignored processes from environment or defaults"""
    env_value = os.getenv('IGNORED_PROCESSES', '')
    if env_value.strip():
        # Parse comma-separated list from env
        return {p.strip() for p in env_value.split(',') if p.strip()}
    return DEFAULT_IGNORED_PROCESSES.copy()

def get_ignored_window_titles():
    """Get ignored window titles from environment or defaults"""
    env_value = os.getenv('IGNORED_WINDOW_TITLES', '')
    if env_value.strip():
        # Parse comma-separated list from env
        return {t.strip() for t in env_value.split(',') if t.strip()}
    return DEFAULT_IGNORED_WINDOW_TITLES.copy()

def should_ignore_activity(app_name, window_title=''):
    """Check if an activity should be ignored"""
    # Get latest values from environment
    ignored_procs = get_ignored_processes()
    ignored_titles = get_ignored_window_titles()

    # Ignore based on process name
    if app_name.lower() in {p.lower() for p in ignored_procs}:
        return True

    # Ignore based on window title
    if window_title in ignored_titles:
        return True

    return False

def get_database_path():
    """Get database path from environment or return default"""
    env_path = os.getenv('DATABASE_PATH', '').strip()
    if env_path:
        return env_path
    return str(Path.home() / '.timetracker' / 'timetracker.db')

def get_env_int(key: str, default: int) -> int:
    """Read an integer environment variable, falling back on bad values."""
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default

def get_user_env_path() -> Path:
    """Path to the user-writable settings file.

    Settings are stored in the user profile so they work for installed
    versions too (no write access to the program directory needed).
    """
    config_dir = Path.home() / '.timetracker'
    config_dir.mkdir(exist_ok=True)
    return config_dir / '.env'
