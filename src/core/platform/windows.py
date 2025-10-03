import re
from datetime import datetime

import psutil
import win32gui
import win32process


class WindowsActivityTracker:
    """Windows-specific activity tracking using Win32 API"""

    @staticmethod
    def get_active_window():
        """Get currently active window information"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)

            window_title = win32gui.GetWindowText(hwnd)
            app_name = process.name()

            # Enhanced browser tracking
            browser_info = WindowsActivityTracker._get_browser_info(app_name, window_title)
            if browser_info:
                window_title = browser_info

            return {
                'app_name': app_name,
                'window_title': window_title,
                'timestamp': datetime.now(),
                'process_path': process.exe()
            }
        except Exception:
            return None

    @staticmethod
    def _get_browser_info(app_name, window_title):
        """Extract browser tab information from window title"""
        app_lower = app_name.lower()

        # Chrome, Edge, Brave
        if any(browser in app_lower for browser in ['chrome.exe', 'msedge.exe', 'brave.exe']):
            # Window title format: "Page Title - Google Chrome"
            match = re.match(r'^(.+?) - (?:Google Chrome|Microsoft Edge|Brave)$', window_title)
            if match:
                return match.group(1)

        # Firefox
        elif 'firefox.exe' in app_lower:
            # Window title format: "Page Title - Mozilla Firefox"
            match = re.match(r'^(.+?) - Mozilla Firefox(?: Private Browsing)?$', window_title)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def get_idle_time():
        """Get system idle time in seconds"""
        try:
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [
                    ('cbSize', ctypes.c_uint),
                    ('dwTime', ctypes.c_uint),
                ]

            lastInputInfo = LASTINPUTINFO()
            lastInputInfo.cbSize = ctypes.sizeof(lastInputInfo)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lastInputInfo))

            millis = ctypes.windll.kernel32.GetTickCount() - lastInputInfo.dwTime
            return millis / 1000.0
        except:
            return 0
