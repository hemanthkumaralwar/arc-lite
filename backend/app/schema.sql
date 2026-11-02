-- Arc Lite schema (PostgreSQL). Safe to run more than once.

CREATE TABLE IF NOT EXISTS faq_entries (
    id               BIGSERIAL PRIMARY KEY,
    category         TEXT NOT NULL
                     CHECK (category IN ('courses', 'certificates', 'jobs', 'account')),
    keywords         TEXT[] NOT NULL
                     CHECK (cardinality(keywords) >= 1),
    canonical_answer TEXT NOT NULL
                     CHECK (length(btrim(canonical_answer)) > 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS faq_entries_category_idx ON faq_entries (category);

CREATE TABLE IF NOT EXISTS conversations (
    id              BIGSERIAL PRIMARY KEY,
    question        TEXT NOT NULL
                    CHECK (length(question) BETWEEN 1 AND 500),
    answer          TEXT,
    category        TEXT
                    CHECK (category IN ('courses', 'certificates', 'jobs', 'account')),
    matched_faq_id  BIGINT REFERENCES faq_entries (id) ON DELETE SET NULL,
    verdict         TEXT NOT NULL
                    CHECK (verdict IN ('Answered', 'Refused', 'Unclear')),
    score           DOUBLE PRECISION,
    response_ms     INTEGER NOT NULL
                    CHECK (response_ms >= 0),
    rating          TEXT
                    CHECK (rating IN ('up', 'down')),
    llm_used        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_created_at_idx ON conversations (created_at);
CREATE INDEX IF NOT EXISTS conversations_category_verdict_idx ON conversations (category, verdict);
CREATE INDEX IF NOT EXISTS conversations_verdict_rating_idx ON conversations (verdict, rating);

CREATE TABLE IF NOT EXISTS staff (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE
                  CHECK (email = lower(email) AND position('@' IN email) > 1),
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
