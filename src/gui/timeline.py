import os
from datetime import datetime, timedelta

from PyQt6.QtCore import QRect, Qt, QMimeData
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen, QDrag
from PyQt6.QtWidgets import QMenu, QWidget

from core.database_protocol import DatabaseProtocol
from utils.config import should_ignore_activity
from utils.icon_cache import IconCache


class TimelineWidget(QWidget):
    """Widget to display activity timeline"""

    def __init__(self, database: DatabaseProtocol):
        super().__init__()
        self.database = database
        self.activities = []
        self.current_date = datetime.now().date()

        # Icon cache
        self.icon_cache = IconCache()

        # Merge settings from environment
        self.merge_gap = int(os.getenv('MERGE_GAP', 60))
        self.min_activity_duration = int(os.getenv('MIN_ACTIVITY_DURATION', 10))
        self.project_merge_gap = int(os.getenv('PROJECT_MERGE_GAP', 180))

        # Visual settings
        self.hour_height = 60  # pixels per hour (adjustable via zoom)
        self.left_margin = 60
        self.right_margin = 20
        self.top_margin = 20

        # Colors
        self.colors = {
            'active': QColor(52, 152, 219),  # Blue
            'idle': QColor(149, 165, 166),   # Gray
            'background': QColor(255, 255, 255),
            'grid': QColor(236, 240, 241),
            'text': QColor(44, 62, 80)
        }

        # Color palette for different apps
        self.app_colors = {}

        # Predefined color palette for better distinction (30 colors)
        self.color_palette = [
            QColor(52, 152, 219),   # Blue
            QColor(46, 204, 113),   # Green
            QColor(155, 89, 182),   # Purple
            QColor(241, 196, 15),   # Yellow
            QColor(230, 126, 34),   # Orange
            QColor(231, 76, 60),    # Red
            QColor(26, 188, 156),   # Turquoise
            QColor(52, 73, 94),     # Dark Blue
            QColor(22, 160, 133),   # Sea Green
            QColor(243, 156, 18),   # Bright Orange
            QColor(211, 84, 0),     # Dark Orange
            QColor(192, 57, 43),    # Dark Red
            QColor(142, 68, 173),   # Dark Purple
            QColor(41, 128, 185),   # Ocean Blue
            QColor(39, 174, 96),    # Emerald
            QColor(127, 140, 141),  # Gray
            QColor(44, 62, 80),     # Midnight Blue
            QColor(149, 165, 166),  # Silver
            QColor(236, 240, 241),  # Clouds (darker for visibility)
            QColor(189, 195, 199),  # Concrete
            QColor(255, 118, 117),  # Light Red
            QColor(253, 203, 110),  # Light Orange
            QColor(162, 155, 254),  # Light Purple
            QColor(116, 185, 255),  # Light Blue
            QColor(9, 132, 227),    # Dodger Blue
            QColor(108, 92, 231),   # Blue Violet
            QColor(255, 159, 243),  # Pink
            QColor(85, 239, 196),   # Aqua
            QColor(0, 184, 148),    # Green Sea
            QColor(255, 234, 167),  # Light Yellow
        ]

        # Track activity rectangles for click detection
        self.activity_rects = []

        # Track selected activities for multi-selection
        self.selected_activities = []
        self.last_clicked_activity = None  # Track last clicked for shift-selection

        self.setMinimumHeight(24 * self.hour_height + 2 * self.top_margin)
        self.setMouseTracking(True)
        self.setToolTip("")  # Enable tooltips

        # Drag and drop support
        self.drag_start_position = None

    def set_activities(self, activities, date):
        """Set activities to display"""
        # Filter out ignored processes
        filtered = [
            act for act in activities
            if not should_ignore_activity(act['app_name'], act.get('window_title', ''))
        ]

        # Merge consecutive activities from the same app
        self.activities = self._merge_activities(filtered)
        self.current_date = date
        self.update()

    def _merge_activities(self, activities):
        """
        Merge consecutive activities with intelligent filtering:
        1. Filter out activities shorter than MIN_ACTIVITY_DURATION
        2. Merge same app activities within MERGE_GAP
        3. Merge same project activities within PROJECT_MERGE_GAP (more aggressive)
        """
        if not activities:
            return []

        # Step 1: Filter out too-short activities (noise reduction)
        filtered = [
            act for act in activities
            if act['duration'] >= self.min_activity_duration
        ]

        if not filtered:
            return []

        # Sort by timestamp (oldest first for merging)
        sorted_activities = sorted(filtered, key=lambda x: x['timestamp'])

        merged = []
        current = None

        for activity in sorted_activities:
            if current is None:
                # First activity
                current = activity.copy()
                current['end_time'] = current['timestamp'] + timedelta(seconds=current['duration'])
            else:
                activity_end = activity['timestamp'] + timedelta(seconds=activity['duration'])
                gap = (activity['timestamp'] - current['end_time']).total_seconds()

                # Determine if we should merge
                should_merge = False

                # Skip merging for idle activities
                if current.get('is_idle', False) or activity.get('is_idle', False):
                    should_merge = False
                # Smart merge: Same project with larger gap allowance
                elif (current.get('project_id') and
                      activity.get('project_id') and
                      current['project_id'] == activity['project_id'] and
                      current['app_name'] == activity['app_name']):
                    should_merge = gap <= self.project_merge_gap
                # Normal merge: Same app within standard gap
                elif current['app_name'] == activity['app_name']:
                    should_merge = gap <= self.merge_gap

                if should_merge:
                    # Extend current activity
                    current['end_time'] = activity_end
                    current['duration'] = int((current['end_time'] - current['timestamp']).total_seconds())
                    # Keep the most recent window title
                    if activity['window_title']:
                        current['window_title'] = activity['window_title']
                else:
                    # Save current and start new
                    merged.append(current)
                    current = activity.copy()
                    current['end_time'] = activity_end

        # Don't forget the last one
        if current:
            merged.append(current)

        return merged

    def set_zoom(self, hour_height):
        """Set zoom level (pixels per hour)"""
        self.hour_height = hour_height
        self.setMinimumHeight(24 * self.hour_height + 2 * self.top_margin)

    def paintEvent(self, event):
        """Paint the timeline"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), self.colors['background'])

        # Draw time grid
        self.draw_time_grid(painter)

        # Draw activities
        self.draw_activities(painter)

    def draw_time_grid(self, painter):
        """Draw time grid (hours)"""
        painter.setPen(QPen(self.colors['grid'], 1))
        font = QFont('Arial', 10)
        painter.setFont(font)

        width = self.width()

        for hour in range(25):  # 0-24
            y = self.top_margin + hour * self.hour_height

            # Draw horizontal line
            painter.drawLine(self.left_margin, y, width - self.right_margin, y)

            # Draw hour label
            time_str = f"{hour:02d}:00"
            painter.setPen(QPen(self.colors['text'], 1))
            painter.drawText(10, y - 5, self.left_margin - 15, 20,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           time_str)
            painter.setPen(QPen(self.colors['grid'], 1))

    def draw_activities(self, painter):
        """Draw activity blocks"""
        if not self.activities:
            return

        width = self.width()
        timeline_width = width - self.left_margin - self.right_margin

        # Clear previous rects
        self.activity_rects = []

        for idx, activity in enumerate(self.activities):
            # Calculate position
            timestamp = activity['timestamp']
            duration = activity['duration']

            # Convert to hours from midnight
            hours_from_midnight = (
                timestamp.hour +
                timestamp.minute / 60 +
                timestamp.second / 3600
            )

            duration_hours = duration / 3600

            # Calculate rectangle
            y = self.top_margin + hours_from_midnight * self.hour_height
            height = duration_hours * self.hour_height

            # Make minimum height visible (at least 3 pixels)
            if height < 3:
                height = 3

            rect = QRect(
                self.left_margin,
                int(y),
                timeline_width,
                int(height)
            )

            # Choose color based on app (give each app a unique color)
            app_name = activity['app_name']
            if app_name not in self.app_colors:
                # Use hash to get consistent color from palette
                import hashlib
                hash_val = int(hashlib.md5(app_name.encode()).hexdigest()[:8], 16)
                color_idx = hash_val % len(self.color_palette)
                base_color = self.color_palette[color_idx]

                # If color already used, slightly adjust hue for distinction
                if base_color in self.app_colors.values():
                    # Shift hue slightly
                    h, s, v, a = base_color.getHsv()
                    h = (h + 20) % 360  # Shift hue by 20 degrees
                    adjusted_color = QColor.fromHsv(h, s, v, a)
                    self.app_colors[app_name] = adjusted_color
                else:
                    self.app_colors[app_name] = base_color

            is_idle = activity.get('is_idle', False)

            # Check if activity has project assignment
            if activity.get('project_id'):
                # Get project color from database
                projects = self.database.get_projects()
                project = next((p for p in projects if p['id'] == activity['project_id']), None)
                if project and project.get('color'):
                    color = QColor(project['color'])
                else:
                    color = self.app_colors[app_name]
            else:
                color = self.colors['idle'] if is_idle else self.app_colors[app_name]

            # Draw activity block
            painter.fillRect(rect, color)

            # Draw border (thicker if selected)
            if activity in self.selected_activities:
                painter.setPen(QPen(QColor(255, 215, 0), 3))  # Gold border for selected
            else:
                painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawRect(rect)

            # Store rect for click detection
            self.activity_rects.append((rect, activity))

            # Draw icon and text if block is large enough
            if height > 15:
                # Try to get icon
                icon_pixmap = None
                text_offset = 5

                if activity.get('process_path'):
                    icon_pixmap = self.icon_cache.get_icon_pixmap(activity['process_path'], size=16)

                if icon_pixmap and not icon_pixmap.isNull():
                    # Scale icon to fit properly
                    scaled_icon = icon_pixmap.scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    # Draw icon
                    icon_y = rect.y() + 2
                    painter.drawPixmap(rect.x() + 3, icon_y, scaled_icon)
                    text_offset = 20  # Make room for icon

                painter.setPen(QPen(QColor(255, 255, 255), 1))
                font = QFont('Arial', 8, QFont.Weight.Bold)
                painter.setFont(font)

                app_name = activity['app_name']
                window_title = activity['window_title'] or ''

                # Get project name if assigned
                project_name = ''
                if activity.get('project_id'):
                    projects = self.database.get_projects()
                    project = next((p for p in projects if p['id'] == activity['project_id']), None)
                    if project:
                        project_name = project['name']

                # Build text based on available space
                if height > 40:
                    # Enough space for multiple lines
                    text = f"{app_name}"
                    if project_name:
                        text += f"\n[{project_name}]"
                    if window_title and len(window_title) > 0:
                        text += f"\n{window_title[:40]}"
                elif height > 25:
                    # Medium space - show app and project
                    text = f"{app_name}"
                    if project_name:
                        text += f" [{project_name}]"
                else:
                    # Minimal space - just app name
                    text = app_name[:20]

                painter.drawText(
                    rect.adjusted(text_offset, 2, -5, -2),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    text
                )

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        # Check if Ctrl is pressed
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom with mouse wheel (prevent scrolling)
            delta = event.angleDelta().y()

            if delta > 0:
                # Zoom in
                new_height = min(self.hour_height + 5, 200)
            else:
                # Zoom out
                new_height = max(self.hour_height - 5, 30)

            self.hour_height = new_height
            self.setMinimumHeight(24 * self.hour_height + 2 * self.top_margin)

            # Update parent slider if exists
            widget = self.parent()
            while widget is not None:
                if hasattr(widget, 'zoom_slider'):
                    widget.zoom_slider.setValue(new_height)
                    break
                widget = widget.parent()

            self.update()
            event.accept()  # Accept the event to prevent scrolling
            return  # Don't propagate to parent
        else:
            # Normal scrolling
            super().wheelEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse movement for tooltips and drag"""
        # Check for drag initiation
        if (event.buttons() & Qt.MouseButton.LeftButton and
            self.drag_start_position is not None and
            self.selected_activities):
            # Calculate distance moved
            distance = (event.pos() - self.drag_start_position).manhattanLength()
            if distance >= 10:  # Minimum drag distance
                self.start_drag()
                return

        # Check if mouse is over an activity
        for rect, activity in self.activity_rects:
            if rect.contains(event.pos()):
                # Show tooltip for this activity
                tooltip = self._create_tooltip(activity)
                self.setToolTip(tooltip)
                return

        # No activity under mouse
        self.setToolTip("")

    def start_drag(self):
        """Start drag operation with selected activities"""
        if not self.selected_activities:
            return

        drag = QDrag(self)
        mime_data = QMimeData()

        # Store activity IDs in mime data (we'll use the timestamp as identifier)
        activity_data = []
        for activity in self.selected_activities:
            activity_data.append({
                'timestamp': activity['timestamp'].isoformat(),
                'app_name': activity['app_name'],
                'duration': activity['duration']
            })

        import json
        mime_data.setText(json.dumps(activity_data))
        drag.setMimeData(mime_data)

        # Execute drag
        drag.exec(Qt.DropAction.CopyAction)

    def mousePressEvent(self, event):
        """Handle mouse clicks"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Store drag start position
            self.drag_start_position = event.pos()

            # Find clicked activity
            for rect, activity in self.activity_rects:
                if rect.contains(event.pos()):
                    # Range selection with Shift
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        if self.last_clicked_activity and self.last_clicked_activity in [a for _, a in self.activity_rects]:
                            # Find indices of last and current activities
                            activities_list = [a for _, a in self.activity_rects]
                            try:
                                last_idx = activities_list.index(self.last_clicked_activity)
                                current_idx = activities_list.index(activity)

                                # Select all activities in range
                                start_idx = min(last_idx, current_idx)
                                end_idx = max(last_idx, current_idx)

                                # Add all activities in range to selection
                                for idx in range(start_idx, end_idx + 1):
                                    if activities_list[idx] not in self.selected_activities:
                                        self.selected_activities.append(activities_list[idx])
                            except ValueError:
                                pass  # Activity not found in list
                        else:
                            # No last activity - just select current
                            if activity not in self.selected_activities:
                                self.selected_activities.append(activity)

                        self.last_clicked_activity = activity
                        self.update()
                    # Toggle selection with Ctrl
                    elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        if activity in self.selected_activities:
                            self.selected_activities.remove(activity)
                        else:
                            self.selected_activities.append(activity)
                        self.last_clicked_activity = activity
                        self.update()
                    else:
                        # Single click without modifiers - select only this one
                        self.selected_activities = [activity]
                        self.last_clicked_activity = activity
                        self.update()
                    return

            # Clicked on empty space - clear selection
            if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.selected_activities = []
                self.last_clicked_activity = None
                self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            # Find clicked activity
            for rect, activity in self.activity_rects:
                if rect.contains(event.pos()):
                    self.show_context_menu(event.pos(), activity)
                    return

    def show_context_menu(self, pos, activity):
        """Show context menu for activity"""
        menu = QMenu(self)

        # Get all projects
        projects = self.database.get_projects()

        # Determine if we're working with multiple activities
        activities_to_assign = self.selected_activities if self.selected_activities else [activity]
        is_multi = len(activities_to_assign) > 1

        if projects:
            if is_multi:
                menu.addSection(f"{len(activities_to_assign)} Aktivitäten zuordnen zu:")

            for project in projects:
                label = f"→ {project['name']}"
                if is_multi:
                    label = f"   {project['name']}"
                action = QAction(label, self)
                action.triggered.connect(
                    lambda checked, acts=activities_to_assign, pid=project['id']:
                    self.assign_multiple_to_project(acts, pid)
                )
                menu.addAction(action)

            menu.addSeparator()

        # Clear project assignment
        if any(act.get('project_id') for act in activities_to_assign):
            clear_label = "Projektzuordnungen entfernen" if is_multi else "Projektzuordnung entfernen"
            clear_action = QAction(clear_label, self)
            clear_action.triggered.connect(
                lambda: self.assign_multiple_to_project(activities_to_assign, None)
            )
            menu.addAction(clear_action)

        menu.exec(self.mapToGlobal(pos))

    def assign_to_project(self, activity, project_id):
        """Assign activity to project (including all merged activities in the timerange)"""
        # Use the merged activity's time range to assign ALL activities in that range
        start_time = activity['timestamp']
        end_time = activity.get('end_time', start_time + timedelta(seconds=activity['duration']))
        app_name = activity['app_name']

        # Assign all activities in this time range for this app
        count = self.database.assign_activities_by_timerange(
            start_time, end_time, app_name, project_id
        )

        print(f"Assigned {count} activities to project")

        # Clear selection
        self.selected_activities = []

        # Find main window and refresh
        widget = self
        while widget is not None:
            if hasattr(widget, 'load_timeline'):
                widget.load_timeline()
                break
            widget = widget.parent()

    def assign_multiple_to_project(self, activities, project_id):
        """Assign multiple activities to a project"""
        total_count = 0

        for activity in activities:
            # Use the merged activity's time range to assign ALL activities in that range
            start_time = activity['timestamp']
            end_time = activity.get('end_time', start_time + timedelta(seconds=activity['duration']))
            app_name = activity['app_name']

            # Assign all activities in this time range for this app
            count = self.database.assign_activities_by_timerange(
                start_time, end_time, app_name, project_id
            )
            total_count += count

        print(f"Assigned {total_count} activities to project")

        # Clear selection
        self.selected_activities = []

        # Find main window and refresh
        widget = self
        while widget is not None:
            if hasattr(widget, 'load_timeline'):
                widget.load_timeline()
                break
            widget = widget.parent()

    def select_all_activities(self, activities):
        """Select all given activities in the timeline"""
        # Find matching activities from the merged activities
        self.selected_activities = []

        for target_activity in activities:
            # Find the merged activity that contains this activity
            for merged_activity in self.activities:
                # Check if this merged activity overlaps with the target activity
                target_start = target_activity['timestamp']
                target_end = target_activity['timestamp'] + timedelta(seconds=target_activity['duration'])
                merged_start = merged_activity['timestamp']
                merged_end = merged_activity.get('end_time', merged_start + timedelta(seconds=merged_activity['duration']))

                # Check for overlap and same app
                if (merged_activity['app_name'] == target_activity['app_name'] and
                    merged_start <= target_end and merged_end >= target_start):
                    if merged_activity not in self.selected_activities:
                        self.selected_activities.append(merged_activity)
                    break

        self.update()

    def _create_tooltip(self, activity):
        """Create tooltip text for activity"""
        from datetime import timedelta

        # Basic info
        timestamp = activity['timestamp']
        duration = activity['duration']
        app_name = activity['app_name']
        window_title = activity.get('window_title', '')

        # Calculate end time
        end_time = timestamp + timedelta(seconds=duration)

        # Format duration
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60

        if hours > 0:
            duration_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = f"{seconds}s"

        # Build tooltip
        tooltip = f"<b>{app_name}</b><br>"

        if window_title:
            tooltip += f"{window_title}<br>"

        tooltip += f"<br><b>Zeit:</b> {timestamp.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}<br>"
        tooltip += f"<b>Dauer:</b> {duration_str}<br>"

        # Add project if assigned
        if activity.get('project_id'):
            projects = self.database.get_projects()
            project = next((p for p in projects if p['id'] == activity['project_id']), None)
            if project:
                tooltip += f"<b>Projekt:</b> {project['name']}<br>"

        # Add idle status
        if activity.get('is_idle'):
            tooltip += "<i>(Idle)</i>"

        return tooltip
