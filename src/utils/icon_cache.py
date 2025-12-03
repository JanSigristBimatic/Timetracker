"""Icon extraction and caching for Windows apps.

This module provides functionality to extract and cache application icons
from Windows executables for display in the GUI.
"""

import logging
import os
import sys
from typing import Optional

from PyQt6.QtGui import QImage, QPixmap

logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    import io

    import win32gui
    import win32ui
    from PIL import Image


class IconCache:
    """Cache for application icons.

    This class extracts icons from Windows executables and caches them
    for efficient retrieval. Icons are stored as QPixmap objects.

    Attributes:
        cache: Dictionary mapping cache keys to QPixmap objects
    """

    def __init__(self):
        """Initialize empty icon cache."""
        self.cache: dict[str, QPixmap] = {}

    def get_icon_pixmap(self, exe_path: Optional[str], size: int = 16) -> Optional[QPixmap]:
        """Get icon pixmap for executable path.

        Args:
            exe_path: Path to the executable file
            size: Desired icon size in pixels (default: 16)

        Returns:
            QPixmap of the icon, or None if extraction fails
        """
        if not exe_path or not os.path.exists(exe_path):
            return None

        cache_key = f"{exe_path}_{size}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        if sys.platform == 'win32':
            pixmap = self._extract_windows_icon(exe_path, size)
            if pixmap and not pixmap.isNull():
                self.cache[cache_key] = pixmap
                return pixmap

        return None

    def _extract_windows_icon(self, exe_path: str, size: int) -> Optional[QPixmap]:
        """Extract icon from Windows executable.

        Args:
            exe_path: Path to the executable file
            size: Desired icon size in pixels

        Returns:
            QPixmap of the extracted icon, or None if extraction fails

        Note:
            This method properly cleans up all Win32 handles even on error.
        """
        large_icons: list = []
        small_icons: list = []
        hicon = None
        hdc = None
        hdc_mem = None
        hbmp = None

        try:
            # Extract icons from exe
            large_icons, small_icons = win32gui.ExtractIconEx(exe_path, 0)

            if not small_icons and not large_icons:
                return None

            # Use small icon if available
            hicon = small_icons[0] if small_icons else (large_icons[0] if large_icons else None)

            if not hicon:
                return None

            # Create device context
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, size, size)
            hdc_mem = hdc.CreateCompatibleDC()

            hdc_mem.SelectObject(hbmp)
            hdc_mem.DrawIcon((0, 0), hicon)

            # Convert to PIL Image
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer('RGB', (size, size), bmpstr, 'raw', 'BGRX', 0, 1)

            # Convert PIL Image to QPixmap
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            qimage = QImage()
            qimage.loadFromData(img_byte_arr.read())
            pixmap = QPixmap.fromImage(qimage)

            return pixmap

        except (OSError, AttributeError, ValueError) as e:
            logger.warning(f"Icon extraction failed for {exe_path}: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error extracting icon for {exe_path}: {e}")
            return None

        finally:
            # Cleanup Win32 handles in reverse order of creation
            if hbmp:
                try:
                    win32gui.DeleteObject(hbmp.GetHandle())
                except (OSError, AttributeError):
                    pass

            if hdc_mem:
                try:
                    hdc_mem.DeleteDC()
                except (OSError, AttributeError):
                    pass

            if hdc:
                try:
                    hdc.DeleteDC()
                except (OSError, AttributeError):
                    pass

            # Cleanup all extracted icons
            for icon in (large_icons or []) + (small_icons or []):
                try:
                    win32gui.DestroyIcon(icon)
                except (OSError, TypeError):
                    pass

    def clear(self) -> None:
        """Clear the icon cache."""
        self.cache.clear()

    def __len__(self) -> int:
        """Return number of cached icons."""
        return len(self.cache)
