import win32gui
import win32process
import psutil
from datetime import datetime


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

            return {
                'app_name': process.name(),
                'window_title': window_title,
                'timestamp': datetime.now(),
                'process_path': process.exe()
            }
        except Exception as e:
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
