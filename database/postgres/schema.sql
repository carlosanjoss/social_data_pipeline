-- ============================================================
-- Radar Ódio — PostgreSQL Schema (IS-A)
-- ============================================================

-- ------------------------------------------------------------
-- Base table: posts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    id              SERIAL PRIMARY KEY,
    platform        VARCHAR(20)  NOT NULL,
    external_id     VARCHAR(255) NOT NULL,
    content_type    VARCHAR(20)  NOT NULL,
    title           TEXT,
    text            TEXT,
    url             TEXT,
    author          VARCHAR(512),
    author_id       VARCHAR(255),
    language        VARCHAR(10)  NOT NULL,
    published_at    TIMESTAMPTZ,
    like_count      INTEGER,
    share_count     INTEGER,
    comment_count   INTEGER,
    retweet_count   INTEGER,
    reply_count     INTEGER,
    quote_count     INTEGER,
    view_count      INTEGER,
    quality_score   REAL,
    quality_flags   TEXT[],
    is_usable       BOOLEAN,
    source_system   VARCHAR(50),
    mongo_id        VARCHAR(30),
    collected_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_posts_platform_ext UNIQUE (platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_platform        ON posts (platform);
CREATE INDEX IF NOT EXISTS idx_posts_published_at    ON posts (published_at);
CREATE INDEX IF NOT EXISTS idx_posts_is_usable       ON posts (is_usable);
CREATE INDEX IF NOT EXISTS idx_posts_language        ON posts (language);

-- ------------------------------------------------------------
-- Extension: reddit_posts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reddit_posts (
    post_id      INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    score        INTEGER,
    num_comments INTEGER,
    subreddit    VARCHAR(100)
);

-- ------------------------------------------------------------
-- Extension: twitter_tweets
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS twitter_tweets (
    post_id         INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    conversation_id VARCHAR(100),
    group_name      VARCHAR(50),
    hashtags        TEXT[]
);

-- ------------------------------------------------------------
-- Extension: youtube_videos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS youtube_videos (
    post_id       INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    channel_id    VARCHAR(100),
    channel_title VARCHAR(255),
    description   TEXT,
    duration      VARCHAR(20),
    thumbnail_url TEXT,
    tags          TEXT[]
);

-- ------------------------------------------------------------
-- Extension: facebook_posts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facebook_posts (
    post_id     INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    page_id     VARCHAR(255),
    page_slug   VARCHAR(255),
    reactions   JSONB,
    media_types TEXT[]
);

-- ------------------------------------------------------------
-- Base table: comments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
    id                  SERIAL PRIMARY KEY,
    platform            VARCHAR(20)  NOT NULL,
    external_id         VARCHAR(255) NOT NULL,
    content_type        VARCHAR(20)  NOT NULL,
    text                TEXT,
    author              VARCHAR(512),
    author_id           VARCHAR(255),
    language            VARCHAR(10) NOT NULL,
    post_external_id    VARCHAR(255),
    parent_external_id  VARCHAR(255),
    post_pk             INTEGER REFERENCES posts(id),
    is_reply            BOOLEAN DEFAULT FALSE,
    depth               INTEGER,
    published_at        TIMESTAMPTZ,
    like_count          INTEGER,
    reply_count         INTEGER,
    quality_score       REAL,
    quality_flags       TEXT[],
    is_usable           BOOLEAN,
    source_system       VARCHAR(50),
    mongo_id            VARCHAR(30),
    collected_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_comments_platform_ext UNIQUE (platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_comments_platform         ON comments (platform);
CREATE INDEX IF NOT EXISTS idx_comments_post_external_id ON comments (platform, post_external_id);
CREATE INDEX IF NOT EXISTS idx_comments_published_at     ON comments (published_at);
CREATE INDEX IF NOT EXISTS idx_comments_is_usable        ON comments (is_usable);

-- ------------------------------------------------------------
-- Extension: reddit_comments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reddit_comments (
    comment_id          INTEGER PRIMARY KEY REFERENCES comments(id) ON DELETE CASCADE,
    score               INTEGER,
    subreddit           VARCHAR(100),
    is_reply_to_comment BOOLEAN DEFAULT FALSE
);

-- ------------------------------------------------------------
-- Extension: youtube_comments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS youtube_comments (
    comment_id INTEGER PRIMARY KEY REFERENCES comments(id) ON DELETE CASCADE,
    video_id   VARCHAR(50)
);

-- ------------------------------------------------------------
-- Extension: facebook_comments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facebook_comments (
    comment_id INTEGER PRIMARY KEY REFERENCES comments(id) ON DELETE CASCADE,
    page_slug  VARCHAR(255)
);

-- ------------------------------------------------------------
-- Extension: tiktok_videos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tiktok_videos (
    post_id   INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    video_url TEXT
);

-- ------------------------------------------------------------
-- Extension: tiktok_comments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tiktok_comments (
    comment_id INTEGER PRIMARY KEY REFERENCES comments(id) ON DELETE CASCADE,
    video_id   VARCHAR(50)
);

-- ------------------------------------------------------------
-- Extensions: mensagens privadas/canais do Farol Digital
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    post_id               INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    group_id              VARCHAR(512),
    member_id             VARCHAR(512),
    score_sentiment       REAL,
    score_misinformation  REAL,
    matched_terms         TEXT[] NOT NULL DEFAULT '{}',
    collection_periods    TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS telegram_messages (
    post_id               INTEGER PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
    group_id              VARCHAR(512),
    member_id             VARCHAR(512),
    score_sentiment       REAL,
    score_misinformation  REAL,
    matched_terms         TEXT[] NOT NULL DEFAULT '{}',
    collection_periods    TEXT[] NOT NULL DEFAULT '{}'
);

-- Migração aditiva para bancos criados por versões anteriores do schema.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS source_system VARCHAR(50);
ALTER TABLE comments ADD COLUMN IF NOT EXISTS source_system VARCHAR(50);
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS matched_terms TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE whatsapp_messages ADD COLUMN IF NOT EXISTS collection_periods TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE telegram_messages ADD COLUMN IF NOT EXISTS matched_terms TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE telegram_messages ADD COLUMN IF NOT EXISTS collection_periods TEXT[] NOT NULL DEFAULT '{}';
