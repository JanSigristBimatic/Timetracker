"""Icon extraction and caching for Windows apps"""
import os
import sys

from PyQt6.QtGui import QImage, QPixmap

if sys.platform == 'win32':
    import io

    import win32gui
    import win32ui
    from PIL import Image


class IconCache:
    """Cache for app icons"""

    def __init__(self):
        self.cache = {}

    def get_icon_pixmap(self, exe_path, size=16):
        """Get icon pixmap for executable path"""
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

    def _extract_windows_icon(self, exe_path, size):
        """Extract icon from Windows executable"""
        try:
            # Extract icons from exe
            large, small = win32gui.ExtractIconEx(exe_path, 0)

            if not small and not large:
                return None

            # Use small icon if available
            hicon = small[0] if small else (large[0] if large else None)

            if not hicon:
                return None

            # Get icon info
            info = win32gui.GetIconInfo(hicon)

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

            # Cleanup
            win32gui.DeleteObject(hbmp.GetHandle())
            hdc_mem.DeleteDC()
            hdc.DeleteDC()
            win32gui.DestroyIcon(hicon)

            # Cleanup all icons
            for icon in (large or []) + (small or []):
                try:
                    win32gui.DestroyIcon(icon)
                except:
                    pass

            return pixmap

        except Exception as e:
            print(f"Icon extraction error for {exe_path}: {e}")
            return None
