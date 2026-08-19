-- schema.sql
-- ============================================================
-- BingeFinder database schema.
--
-- Table: series
-- Stores web/TV series metadata fetched from TMDb. `id` is the
-- canonical TMDb series ID and is used as the primary key so that
-- repeated syncs perform idempotent upserts rather than creating
-- duplicate rows.
--
-- Related lookup/junction tables (added to support the future
-- recommendation system) capture genres, cast, keywords, and
-- watch providers for each series. All foreign-key IDs are TMDb
-- IDs where TMDb provides one, so this data can be safely re-synced
-- from the API without creating duplicates.
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS series (
    id                  INTEGER PRIMARY KEY,      -- TMDb series ID
    name                TEXT NOT NULL,            -- Series title
    original_name       TEXT,                     -- Original (untranslated) title
    overview            TEXT,                     -- Synopsis / description
    tagline             TEXT,                     -- Marketing tagline
    status              TEXT,                     -- e.g. "Returning Series", "Ended", "Canceled"
    first_air_date      TEXT,                     -- ISO date string (YYYY-MM-DD)
    last_air_date       TEXT,                     -- ISO date string (YYYY-MM-DD)
    number_of_seasons   INTEGER,                  -- Total season count
    number_of_episodes  INTEGER,                  -- Total episode count
    vote_average        REAL,                     -- Average user rating (0-10)
    vote_count          INTEGER,                  -- Number of user votes
    popularity           REAL,                     -- TMDb popularity score
    original_language   TEXT,                     -- ISO 639-1 language code
    origin_country       TEXT,                     -- JSON-encoded list of ISO 3166-1 country codes
    genre_ids           TEXT,                     -- JSON-encoded list of genre IDs (kept for backward compatibility;
                                                    -- normalized genre data now also lives in genres/series_genres)
    poster_path         TEXT,                     -- Relative poster image path
    backdrop_path       TEXT,                     -- Relative backdrop image path
    homepage             TEXT,                     -- Official series homepage URL
    adult               INTEGER DEFAULT 0,        -- 0 = false, 1 = true
    last_updated        TEXT NOT NULL             -- ISO timestamp of last sync
);

-- Helpful indexes for common lookups/sorting used by later phases
-- (recommendation logic, search, filtering by rating/popularity, etc.)
CREATE INDEX IF NOT EXISTS idx_series_popularity ON series (popularity);
CREATE INDEX IF NOT EXISTS idx_series_vote_average ON series (vote_average);
CREATE INDEX IF NOT EXISTS idx_series_first_air_date ON series (first_air_date);
CREATE INDEX IF NOT EXISTS idx_series_status ON series (status);

-- ============================================================
-- Genres
-- ============================================================

CREATE TABLE IF NOT EXISTS genres (
    id      INTEGER PRIMARY KEY,   -- TMDb genre ID
    name    TEXT NOT NULL UNIQUE   -- Genre name, e.g. "Drama"
);

CREATE TABLE IF NOT EXISTS series_genres (
    series_id   INTEGER NOT NULL,
    genre_id    INTEGER NOT NULL,
    PRIMARY KEY (series_id, genre_id),
    FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id)  REFERENCES genres (id)  ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_series_genres_genre_id ON series_genres (genre_id);

-- ============================================================
-- Cast
-- NOTE: "cast" is a reserved SQL keyword, so it is quoted in every
-- statement that references it.
-- ============================================================

CREATE TABLE IF NOT EXISTS "cast" (
    id              INTEGER PRIMARY KEY,   -- TMDb person ID
    name            TEXT NOT NULL,         -- Actor's name
    profile_path    TEXT                   -- Relative headshot image path
);

CREATE INDEX IF NOT EXISTS idx_cast_name ON "cast" (name);

CREATE TABLE IF NOT EXISTS series_cast (
    series_id       INTEGER NOT NULL,
    cast_id         INTEGER NOT NULL,
    character_name  TEXT,                  -- Character played, if known
    cast_order      INTEGER,                -- TMDb billing order (lower = more prominent)
    PRIMARY KEY (series_id, cast_id),
    FOREIGN KEY (series_id) REFERENCES series (id)  ON DELETE CASCADE,
    FOREIGN KEY (cast_id)   REFERENCES "cast" (id)  ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_series_cast_cast_id ON series_cast (cast_id);

-- ============================================================
-- Keywords
-- ============================================================

CREATE TABLE IF NOT EXISTS keywords (
    id      INTEGER PRIMARY KEY,   -- TMDb keyword ID
    name    TEXT NOT NULL UNIQUE   -- Keyword/tag text
);

CREATE TABLE IF NOT EXISTS series_keywords (
    series_id   INTEGER NOT NULL,
    keyword_id  INTEGER NOT NULL,
    PRIMARY KEY (series_id, keyword_id),
    FOREIGN KEY (series_id)  REFERENCES series (id)   ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_series_keywords_keyword_id ON series_keywords (keyword_id);

-- ============================================================
-- Watch providers
-- A series can be available via different providers in different
-- countries and under different offer types (flatrate/rent/buy/etc.),
-- so series_providers is keyed on all four to avoid duplicates while
-- still allowing multiple rows per series.
-- ============================================================

CREATE TABLE IF NOT EXISTS providers (
    id          INTEGER PRIMARY KEY,   -- TMDb watch-provider ID
    name        TEXT NOT NULL,         -- Provider name, e.g. "Netflix"
    logo_path   TEXT                   -- Relative provider logo image path
);

CREATE TABLE IF NOT EXISTS series_providers (
    series_id       INTEGER NOT NULL,
    provider_id     INTEGER NOT NULL,
    country_code    TEXT NOT NULL,         -- ISO 3166-1 country code, e.g. "US"
    provider_type   TEXT NOT NULL,         -- "flatrate", "free", "ads", "rent", or "buy"
    PRIMARY KEY (series_id, provider_id, country_code, provider_type),
    FOREIGN KEY (series_id)    REFERENCES series (id)    ON DELETE CASCADE,
    FOREIGN KEY (provider_id)  REFERENCES providers (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_series_providers_provider_id ON series_providers (provider_id);
CREATE INDEX IF NOT EXISTS idx_series_providers_country ON series_providers (country_code);
