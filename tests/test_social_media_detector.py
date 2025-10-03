"""Tests for Social Media Detector"""

import pytest

from src.utils.social_media_detector import SocialMediaDetector


class TestSocialMediaDetector:
    """Test suite for Social Media Detector"""

    def test_detect_facebook(self):
        """Test Facebook detection"""
        assert SocialMediaDetector.is_social_media(
            "Chrome", "Facebook - Google Chrome"
        )
        assert SocialMediaDetector.is_social_media(
            "Firefox", "https://www.facebook.com/feed"
        )

    def test_detect_twitter(self):
        """Test Twitter/X detection"""
        assert SocialMediaDetector.is_social_media(
            "Chrome", "Twitter - Home"
        )
        assert SocialMediaDetector.is_social_media(
            "Edge", "X.com - Timeline"
        )

    def test_detect_instagram(self):
        """Test Instagram detection"""
        assert SocialMediaDetector.is_social_media(
            "Chrome", "Instagram - Photos"
        )
        assert SocialMediaDetector.is_social_media(
            "Safari", "instagram.com/explore"
        )

    def test_detect_linkedin(self):
        """Test LinkedIn detection"""
        assert SocialMediaDetector.is_social_media(
            "Chrome", "LinkedIn - Feed"
        )
        assert SocialMediaDetector.is_social_media(
            "Firefox", "www.linkedin.com/in/profile"
        )
        assert SocialMediaDetector.is_social_media(
            "Chrome", "LinkedIn | Feed"
        )
        assert SocialMediaDetector.is_social_media(
            "Edge", "(2) LinkedIn"
        )

    def test_detect_youtube(self):
        """Test YouTube detection"""
        assert SocialMediaDetector.is_social_media(
            "Chrome", "YouTube - Trending"
        )
        assert SocialMediaDetector.is_social_media(
            "Firefox", "youtube.com/watch?v=123"
        )

    def test_detect_reddit(self):
        """Test Reddit detection"""
        assert SocialMediaDetector.is_social_media(
            "Chrome", "reddit.com - frontpage"
        )

    def test_detect_discord(self):
        """Test Discord detection"""
        assert SocialMediaDetector.is_social_media(
            "Discord", "Discord - General Chat"
        )
        assert SocialMediaDetector.is_social_media(
            "Chrome", "discord.com/channels/123"
        )

    def test_not_social_media(self):
        """Test non-social media activities"""
        assert not SocialMediaDetector.is_social_media(
            "VSCode", "main.py - Visual Studio Code"
        )
        assert not SocialMediaDetector.is_social_media(
            "Chrome", "Google Search Results"
        )
        assert not SocialMediaDetector.is_social_media(
            "Excel", "Budget.xlsx"
        )
        assert not SocialMediaDetector.is_social_media(
            "PyCharm", "tracker.py"
        )

    def test_get_platform_name_facebook(self):
        """Test getting platform name for Facebook"""
        name = SocialMediaDetector.get_platform_name(
            "Chrome", "facebook.com - News Feed"
        )
        assert name == "Facebook"

    def test_get_platform_name_youtube(self):
        """Test getting platform name for YouTube"""
        name = SocialMediaDetector.get_platform_name(
            "Firefox", "youtube.com - Home"
        )
        assert name == "YouTube"

    def test_get_platform_name_none(self):
        """Test getting platform name for non-social media"""
        name = SocialMediaDetector.get_platform_name(
            "VSCode", "main.py"
        )
        assert name is None

    def test_case_insensitive_detection(self):
        """Test that detection is case insensitive"""
        assert SocialMediaDetector.is_social_media(
            "CHROME", "FACEBOOK.COM - HOME"
        )
        assert SocialMediaDetector.is_social_media(
            "chrome", "facebook.com - home"
        )

    def test_multiple_platforms(self):
        """Test detection of various platforms"""
        platforms = [
            ("Chrome", "tiktok.com - For You"),
            ("Firefox", "pinterest.com - Ideas"),
            ("Chrome", "whatsapp.com - Chats"),
            ("Telegram", "Telegram Desktop"),
            ("Chrome", "twitch.tv - Live Streams"),
        ]

        for app_name, window_title in platforms:
            assert SocialMediaDetector.is_social_media(app_name, window_title)
