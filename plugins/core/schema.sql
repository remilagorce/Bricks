-- Bricks workspace schema — v0 (fixed columns).
-- FROZEN CONTRACT: changing this file requires a PR approved by the whole team.
-- v0 simplification: enrichment columns are hardcoded. The dynamic column
-- registry (columns/cells tables) comes in a later version without breaking bricks.

CREATE TABLE IF NOT EXISTS companies (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT NOT NULL,
  domain         TEXT UNIQUE,
  source         TEXT,
  segment        TEXT NOT NULL DEFAULT 'prospect', -- prospect | seed (won customer)
  status         TEXT NOT NULL DEFAULT 'new',      -- new | disqualified
  pitch          TEXT,
  language       TEXT,                             -- ISO code, e.g. fr, en
  size_hint      TEXT,                             -- solo | small | mid | large
  website_status TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | not_found | failed
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS people (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id      INTEGER REFERENCES companies(id),
  first_name      TEXT,
  last_name       TEXT,
  title           TEXT,
  linkedin_url    TEXT,
  email           TEXT,
  email_status    TEXT NOT NULL DEFAULT 'pending', -- pending | running | done | not_found | failed
  sequence_status TEXT NOT NULL DEFAULT 'pending', -- pending | running | done | failed
  source          TEXT,
  status          TEXT NOT NULL DEFAULT 'new',     -- new | disqualified
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  person_id  INTEGER NOT NULL REFERENCES people(id),
  step       INTEGER NOT NULL,                     -- 1, 2, 3
  send_day   INTEGER,                              -- day offset: 0, 3, 7
  subject    TEXT,
  body       TEXT,
  status     TEXT NOT NULL DEFAULT 'draft',        -- draft | approved | sent
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT,
  UNIQUE(person_id, step)
);

CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_id);
CREATE INDEX IF NOT EXISTS idx_messages_person ON messages(person_id);
