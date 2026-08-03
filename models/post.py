from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, field_validator


class QualityReport(BaseModel):
    score: float = Field(ge=0, le=100)
    flags: list[str] = Field(default_factory=list)
    is_usable: bool  # True when score >= 60 (has text + date)


class NormalizedPost(BaseModel):
    """Validated normalized fields for a post/tweet/video/message."""

    # --- identity ---
    platform: str
    external_id: str
    content_type: str  # post | tweet | reply | video | reel | message

    # --- content ---
    title: str | None = None
    text: str | None = None
    url: str | None = None
    language: str | None = None

    # --- author ---
    author: str | None = None
    author_id: str | None = None

    # --- time ---
    published_at: str | None = None

    # --- engagement (all optional, all int) ---
    like_count: int | None = None
    share_count: int | None = None
    comment_count: int | None = None
    retweet_count: int | None = None
    reply_count: int | None = None
    quote_count: int | None = None
    view_count: int | None = None
    score: int | None = None           # Reddit upvote score

    # --- platform-specific ---
    subreddit: str | None = None       # reddit
    conversation_id: str | None = None # twitter
    group_name: str | None = None      # twitter
    channel_id: str | None = None      # youtube
    channel_title: str | None = None   # youtube
    page_id: str | None = None         # facebook
    page_slug: str | None = None       # facebook
    group_id: str | None = None        # whatsapp / telegram
    member_id: str | None = None       # whatsapp / telegram
    score_sentiment: float | None = None
    score_misinformation: float | None = None
    matched_terms: list[str] = Field(default_factory=list)
    collection_periods: list[str] = Field(default_factory=list)

    # --- meta ---
    hashtags: list[str] = Field(default_factory=list)
    media_types: list[str] = Field(default_factory=list)
    reactions: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    # --- quality (added after validation) ---
    quality: QualityReport | None = None

    @field_validator("like_count", "share_count", "comment_count",
                     "retweet_count", "reply_count", "quote_count",
                     "view_count", "score", mode="before")
    @classmethod
    def coerce_int(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    model_config = {"extra": "ignore"}
