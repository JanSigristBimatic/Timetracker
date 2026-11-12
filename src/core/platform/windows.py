"""Windows-specific activity tracking using Win32 API.

This module provides Windows-specific functionality for tracking user activity,
including active window detection, idle time measurement, and audio playback status.
"""

import ctypes
import logging
import re
from datetime import datetime
from typing import Optional

import psutil
import win32gui
import win32process

logger = logging.getLogger(__name__)


class LASTINPUTINFO(ctypes.Structure):
    """Windows LASTINPUTINFO structure for idle time detection."""

    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint),
    ]


class WindowsActivityTracker:
    """Windows-specific activity tracking using Win32 API.

    This class provides methods to track user activity on Windows systems,
    including active window detection, browser tab tracking, idle time
    measurement, and audio playback detection.
    """

    @staticmethod
    def get_active_window() -> Optional[dict]:
        """Get currently active window information.

        Returns:
            Dictionary with window information containing:
                - app_name: Name of the application executable
                - window_title: Title of the active window
                - timestamp: Current datetime
                - process_path: Full path to the executable
            Returns None if no window is active or on error.
        """
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

        except psutil.NoSuchProcess:
            # Process terminated before we could get info
            return None
        except psutil.AccessDenied:
            # No permission to access process
            return None
        except OSError as e:
            # Win32 API error (e.g., window closed)
            logger.debug(f"Win32 error getting active window: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting active window: {e}")
            return None

    @staticmethod
    def _get_browser_info(app_name: str, window_title: str) -> Optional[str]:
        """Extract browser tab information from window title.

        Args:
            app_name: Name of the application executable
            window_title: Original window title

        Returns:
            Extracted page title for browsers, or None if not a browser
            or title extraction fails.
        """
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
    def is_audio_playing(app_name: Optional[str]) -> bool:
        """Check if the given foreground application is playing audio.

        Only audio from the foreground app counts as presence. Background
        apps often keep an audio session active for hours (chat clients,
        browser tabs), which would otherwise block idle detection.

        Args:
            app_name: Executable name of the foreground app, or None

        Returns:
            True if that app has an active, audible session.
        """
        if not app_name:
            return False

        try:
            from pycaw.pycaw import AudioUtilities

            target = app_name.lower()
            for session in AudioUtilities.GetAllSessions():
                if not session.Process or session.Process.name().lower() != target:
                    continue
                # AudioSessionStateActive = 1
                if session.State == 1 and session.SimpleAudioVolume.GetMasterVolume() > 0:
                    return True
            return False

        except ImportError:
            logger.warning("pycaw not available for audio detection")
            return False
        except OSError as e:
            # COM error or audio service unavailable
            logger.debug(f"Audio detection error: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error in audio detection: {e}")
            return False

    @staticmethod
    def get_idle_time() -> float:
        """Get system idle time in seconds.

        Uses Windows GetLastInputInfo API to determine how long since
        the last user input (keyboard/mouse).

        Returns:
            Idle time in seconds, or 0.0 on error.
        """
        try:
            last_input_info = LASTINPUTINFO()
            last_input_info.cbSize = ctypes.sizeof(last_input_info)

            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info)):
                logger.debug("GetLastInputInfo failed")
                return 0.0

            # Both values are 32-bit tick counts that wrap after ~49.7 days
            millis = (
                ctypes.windll.kernel32.GetTickCount() - last_input_info.dwTime
            ) & 0xFFFFFFFF
            return millis / 1000.0

        except OSError as e:
            logger.debug(f"Error getting idle time: {e}")
            return 0.0
        except Exception as e:
            logger.warning(f"Unexpected error getting idle time: {e}")
            return 0.0
