from enum import Enum


class Platform(str, Enum):
    REDDIT = "reddit"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"

    @property
    def display_name(self) -> str:
        return {
            "reddit":   "Reddit",
            "twitter":  "Twitter/X",
            "facebook": "Facebook",
            "instagram": "Instagram",
            "youtube":  "YouTube",
            "tiktok":   "TikTok",
            "whatsapp": "WhatsApp",
            "telegram": "Telegram",
        }[self.value]

    @property
    def base_url(self) -> str:
        return {
            "reddit":   "https://www.reddit.com",
            "twitter":  "https://x.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "youtube":  "https://www.youtube.com",
            "tiktok":   "https://www.tiktok.com",
            "whatsapp": "https://www.whatsapp.com",
            "telegram": "https://telegram.org",
        }[self.value]


class ContentType(str, Enum):
    POST    = "post"
    TWEET   = "tweet"
    VIDEO   = "video"
    COMMENT = "comment"
    REPLY   = "reply"
    REEL    = "reel"
    MESSAGE = "message"


PLATFORM_CONTENT_TYPES: dict[Platform, list[ContentType]] = {
    Platform.REDDIT:   [ContentType.POST,  ContentType.COMMENT],
    Platform.TWITTER:  [ContentType.TWEET, ContentType.REPLY],
    Platform.FACEBOOK: [ContentType.POST,  ContentType.REEL, ContentType.COMMENT],
    Platform.INSTAGRAM:[ContentType.POST,  ContentType.REEL, ContentType.COMMENT],
    Platform.YOUTUBE:  [ContentType.VIDEO, ContentType.COMMENT],
    Platform.TIKTOK:   [ContentType.VIDEO, ContentType.COMMENT],
    Platform.WHATSAPP: [ContentType.MESSAGE],
    Platform.TELEGRAM: [ContentType.MESSAGE],
}
