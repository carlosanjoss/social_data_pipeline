from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from .post import QualityReport


class NormalizedComment(BaseModel):
    """Validated normalized fields for a comment/reply."""

    # --- identity ---
    platform: str
    external_id: str
    content_type: str  # comment | reply

    # --- content ---
    text: str | None = None
    language: str | None = None

    # --- author ---
    author: str | None = None
    author_id: str | None = None

    # --- hierarchy ---
    post_id: str | None = None         # parent post/video/tweet
    parent_id: str | None = None       # parent comment (for replies)
    is_reply: bool = False
    is_reply_to_comment: bool = False  # reddit-specific
    depth: int | None = None

    # --- time ---
    published_at: str | None = None

    # --- engagement ---
    like_count: int | None = None
    reply_count: int | None = None
    score: int | None = None           # reddit

    # --- platform-specific ---
    subreddit: str | None = None       # reddit
    page_slug: str | None = None       # facebook
    conversation_id: str | None = None # twitter (if ever used)

    # --- quality ---
    quality: QualityReport | None = None

    @field_validator("like_count", "reply_count", "score", "depth", mode="before")
    @classmethod
    def coerce_int(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    model_config = {"extra": "ignore"}
