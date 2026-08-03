"""
Quality score (0–100) based on field completeness for NLP / hate-speech analysis.

Scoring weights (posts and comments share the same logic):
  +40  text present and non-empty          ← critical for NLP
  +20  published_at present                ← critical for time-series
  +15  author present                      ← important for author analysis
  +10  any engagement metric present       ← useful context
  +10  platform-specific required field    ← platform completeness
   +5  language field present

is_usable = score >= 60  (text + date = 60 pts minimum)
"""

from __future__ import annotations

_PLATFORM_REQUIRED: dict[str, list[str]] = {
    "reddit":   ["subreddit"],
    "twitter":  ["conversation_id"],
    "youtube":  ["post_id"],      # for comments; channel_id for posts
    "facebook": ["page_slug"],
    "whatsapp": ["group_id"],
    "telegram": ["group_id"],
}

_ENGAGEMENT_FIELDS = {
    "like_count", "share_count", "comment_count",
    "retweet_count", "reply_count", "quote_count",
    "view_count", "score",
}


def compute_quality(normalized: dict, platform: str, is_comment: bool = False) -> dict:
    """
    Returns a quality dict: {'score': float, 'flags': list[str], 'is_usable': bool}
    """
    flags: list[str] = []
    score = 0.0

    # 1. Text (40 pts)
    text = normalized.get("text")
    if text and str(text).strip():
        score += 40
    else:
        flags.append("missing_text")

    # 2. Date (20 pts)
    if normalized.get("published_at"):
        score += 20
    else:
        flags.append("missing_date")

    # 3. Author (15 pts)
    if normalized.get("author"):
        score += 15
    else:
        flags.append("missing_author")

    # 4. Any engagement metric (10 pts)
    if any(normalized.get(f) is not None for f in _ENGAGEMENT_FIELDS):
        score += 10
    else:
        flags.append("no_engagement_data")

    # 5. Platform-specific required field (10 pts)
    platform_fields = _PLATFORM_REQUIRED.get(platform, [])
    # for posts: youtube needs channel_id, comments need post_id
    if platform == "youtube" and not is_comment:
        platform_fields = ["channel_id"]
    missing_platform = [f for f in platform_fields if not normalized.get(f)]
    if not missing_platform:
        score += 10
    else:
        flags.extend(f"missing_{f}" for f in missing_platform)

    # 6. Language (5 pts)
    if normalized.get("language"):
        score += 5
    else:
        flags.append("missing_language")

    return {
        "score":     round(score, 1),
        "flags":     flags,
        "is_usable": score >= 60,
    }
