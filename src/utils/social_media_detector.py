"""Social Media Detector for TimeTracker

Detects and categorizes social media activities automatically.
"""

from typing import Optional


class SocialMediaDetector:
    """Detects social media usage based on window titles and app names"""

    # Common social media platforms and their identifiers
    # Multiple patterns per platform for better detection
    SOCIAL_MEDIA_PATTERNS = {
        'facebook': 'Facebook',
        'twitter': 'Twitter',
        'x.com': 'X (Twitter)',
        'instagram': 'Instagram',
        'linkedin': 'LinkedIn',
        'reddit': 'Reddit',
        'tiktok': 'TikTok',
        'youtube': 'YouTube',
        'snapchat': 'Snapchat',
        'pinterest': 'Pinterest',
        'whatsapp': 'WhatsApp',
        'telegram': 'Telegram',
        'discord': 'Discord',
        'twitch': 'Twitch',
    }

    @classmethod
    def is_social_media(cls, app_name: str, window_title: str) -> bool:
        """
        Check if the activity is social media related

        Args:
            app_name: Name of the application
            window_title: Title of the window

        Returns:
            True if activity is social media related, False otherwise
        """
        combined_text = f"{app_name.lower()} {window_title.lower()}"

        return any(
            pattern in combined_text
            for pattern in cls.SOCIAL_MEDIA_PATTERNS.keys()
        )

    @classmethod
    def get_platform_name(cls, app_name: str, window_title: str) -> Optional[str]:
        """
        Get the name of the social media platform

        Args:
            app_name: Name of the application
            window_title: Title of the window

        Returns:
            Name of the platform or None if not social media
        """
        combined_text = f"{app_name.lower()} {window_title.lower()}"

        for pattern, name in cls.SOCIAL_MEDIA_PATTERNS.items():
            if pattern in combined_text:
                return name

        return None
