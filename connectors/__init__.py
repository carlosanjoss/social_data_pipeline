from .base import BaseConnector
from .reddit_connector import RedditConnector
from .twitter_connector import TwitterConnector
from .youtube_connector import YouTubeConnector
from .facebook_connector import FacebookConnector
from .tiktok_connector import TikTokConnector
from .farol_messaging_connector import TelegramConnector, WhatsAppConnector

CONNECTORS = {
    "reddit":   RedditConnector,
    "twitter":  TwitterConnector,
    "youtube":  YouTubeConnector,
    "facebook": FacebookConnector,
    "tiktok":   TikTokConnector,
    "whatsapp": WhatsAppConnector,
    "telegram": TelegramConnector,
}

__all__ = [
    "BaseConnector",
    "RedditConnector",
    "TwitterConnector",
    "YouTubeConnector",
    "FacebookConnector",
    "TikTokConnector",
    "WhatsAppConnector",
    "TelegramConnector",
    "CONNECTORS",
]
