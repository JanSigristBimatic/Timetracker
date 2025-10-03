"""Configuration and constants"""

# Processes to ignore (system processes, not relevant for tracking)
IGNORED_PROCESSES = {
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

# Windows with these titles should be ignored
IGNORED_WINDOW_TITLES = {
    '',  # Empty titles
    'Program Manager',  # Desktop
    'Task Switching',
    'Windows Shell Experience Host',
}

def should_ignore_activity(app_name, window_title=''):
    """Check if an activity should be ignored"""
    # Ignore based on process name
    if app_name.lower() in {p.lower() for p in IGNORED_PROCESSES}:
        return True

    # Ignore based on window title
    if window_title in IGNORED_WINDOW_TITLES:
        return True

    return False
