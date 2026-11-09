from .base import BaseConnector
from .reddit_connector import RedditConnector
from .twitter_connector import TwitterConnector
from .youtube_connector import YouTubeConnector
from .facebook_connector import FacebookConnector
from .instagram_connector import InstagramConnector
from .tiktok_connector import TikTokConnector
from .farol_messaging_connector import TelegramConnector, WhatsAppConnector

CONNECTORS = {
    "reddit":   RedditConnector,
    "twitter":  TwitterConnector,
    "youtube":  YouTubeConnector,
    "facebook": FacebookConnector,
    "instagram": InstagramConnector,
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
    "InstagramConnector",
    "TikTokConnector",
    "WhatsAppConnector",
    "TelegramConnector",
    "CONNECTORS",
]
