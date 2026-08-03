-- ============================================================
-- Radar Ódio — DuckDB Star Schema
-- ============================================================

-- ------------------------------------------------------------
-- dim_date  (date spine, gerada via Python)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_date (
    date_key     INTEGER PRIMARY KEY,   -- YYYYMMDD
    date         DATE        NOT NULL,
    year         SMALLINT,
    quarter      SMALLINT,
    month        SMALLINT,
    month_name   VARCHAR(12),
    week         SMALLINT,
    day          SMALLINT,
    weekday      SMALLINT,              -- 0=Mon … 6=Sun
    weekday_name VARCHAR(12),
    is_weekend   BOOLEAN
);

-- ------------------------------------------------------------
-- dim_platform
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_platform (
    platform_key SMALLINT PRIMARY KEY,
    platform     VARCHAR(20) UNIQUE NOT NULL,
    display_name VARCHAR(50)
);

-- ------------------------------------------------------------
-- dim_content_type
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_content_type (
    content_type_key SMALLINT PRIMARY KEY,
    content_type     VARCHAR(20) UNIQUE NOT NULL,
    is_post          BOOLEAN,
    is_comment       BOOLEAN
);

-- ------------------------------------------------------------
-- dim_location  (subreddit / canal / página)
-- ------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS seq_dim_location START 1;
CREATE TABLE IF NOT EXISTS dim_location (
    location_key INTEGER PRIMARY KEY DEFAULT nextval('seq_dim_location'),
    platform     VARCHAR(20),
    location     VARCHAR(512),
    UNIQUE (platform, location)
);

-- ------------------------------------------------------------
-- dim_author  (SCD Type 2 — rastreia mudanças ao longo do tempo)
-- ------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS seq_dim_author START 1;
CREATE TABLE IF NOT EXISTS dim_author (
    author_key     INTEGER PRIMARY KEY DEFAULT nextval('seq_dim_author'),
    platform       VARCHAR(20),
    author         VARCHAR(512),
    author_id      VARCHAR(255),
    effective_from DATE NOT NULL,
    effective_to   DATE,               -- NULL = versão atual
    is_current     BOOLEAN DEFAULT TRUE,
    UNIQUE (platform, author, effective_from)
);

-- ------------------------------------------------------------
-- fact_posts  (granularidade: 1 linha por post/vídeo/tweet)
-- FKs para dimensões de baixa cardinalidade mantidas; date_key e author_key
-- sem FK por dados sujos (datas futuras, autores anônimos).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_posts (
    post_key         INTEGER PRIMARY KEY,
    date_key         INTEGER,
    platform_key     SMALLINT REFERENCES dim_platform(platform_key),
    content_type_key SMALLINT REFERENCES dim_content_type(content_type_key),
    author_key       INTEGER,
    location_key     INTEGER,
    -- dimensões degeneradas
    external_id      VARCHAR(255),
    postgres_id      INTEGER,
    -- medidas de engajamento
    like_count       INTEGER,
    share_count      INTEGER,
    comment_count    INTEGER,
    retweet_count    INTEGER,
    reply_count      INTEGER,
    quote_count      INTEGER,
    view_count       INTEGER,
    -- medidas de qualidade
    quality_score    REAL,
    is_usable        BOOLEAN,
    has_text         BOOLEAN,
    text_length      INTEGER
);

-- ------------------------------------------------------------
-- fact_comments  (granularidade: 1 linha por comentário/reply)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_comments (
    comment_key      INTEGER PRIMARY KEY,
    date_key         INTEGER,
    platform_key     SMALLINT REFERENCES dim_platform(platform_key),
    content_type_key SMALLINT REFERENCES dim_content_type(content_type_key),
    author_key       INTEGER,
    post_key         INTEGER,
    -- dimensões degeneradas
    external_id      VARCHAR(255),
    postgres_id      INTEGER,
    post_external_id VARCHAR(255),
    -- medidas
    like_count       INTEGER,
    reply_count      INTEGER,
    depth            INTEGER,
    quality_score    REAL,
    is_usable        BOOLEAN,
    has_text         BOOLEAN,
    text_length      INTEGER,
    is_reply         BOOLEAN
);
