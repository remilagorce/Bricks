# Brick contract: signal-person

| Field | Value |
|---|---|
| family | signal (person level — twin of signal-sillage, account level) |
| target | reads contacts, writes signals (+ freshness columns on contacts) |
| method | four announced passes, cheap first: job change via FullEnrich re-search (free) → recent posts via `web_data_linkedin_posts` (per-record) → hiring via `web_data_linkedin_job_listings` (per-record) → company news via SERP |
| cost | pass 1 free · passes 2-3 per-record (caps: 25 post lookups, 25 hiring lookups) · pass 4 ~1 credit per company query |

## IN

- `contacts` with `linkedin_url` (passes 1-2; from enrich-person-profile
  or enrich-buying-committee) and a resolvable company (pass 3).
- Scope: `tier` A/B when the score brick has run; otherwise
  user-confirmed. Disqualified companies' contacts never scanned;
  kill-rule flags in `memory/` exclude the same way until score ships.
- Freshness: `signal_status='pending'` OR `signal_checked_at` > 7 days.
- Optional: FullEnrich MCP (pass 1), Bright Data MCP + pro tools
  (passes 2-3). Missing → the pass is skipped and the receipt says so.

## OUT

- `signals` rows: `contact_id` + `contact_name` (person-level kinds;
  empty for company-level ones), `company_id`, `company_name`, `kind` =
  `job_change` | `new_post` | `hiring` | `company_news`, `date`,
  `freshness` = `fresh` (≤ 60 days) | `context`, `summary`
  (evidence-anchored), `evidence_url`, `source` = `fullenrich-search` |
  `linkedin-posts` | `linkedin-jobs` | `news-serp`, `sig_key` (dedup
  key), `status='new'`, `detected_at`.
- On contacts: `last_signal` (short human line), `signal_status` →
  `done` | `not_found` | `failed`, `signal_checked_at`.
- Promotion (same company) resets the contact's
  `profile_status='pending'` — bus relay so enrich-person-profile
  refreshes role/seniority. A company CHANGE never relays: it sets
  `left_company=1`, the row's identity columns stay frozen (they
  describe who the person was at THIS company), and person-profile +
  write-sequence exclude the row; following the person to the new
  company is the user's call.
- Only `fresh` (≤ 60 days) signals are icebreaker material downstream;
  `context` ones are background, never presented as news.

## Errors

- Person absent from FullEnrich → no job-change verdict (absence of
  data ≠ no change); other passes still run.
- `web_data_linkedin_posts` / `web_data_linkedin_job_listings` absent →
  passes 2-3 unavailable (need plugin ≥ 0.4.0 + Bright Data connected);
  never emulated by scraping profile pages (login wall).
- Signal without a source record/URL → not written. Ever.

## Guardrails

- Paid passes announced with exact volume BEFORE spending (money gate
  §8); hard caps without explicit override: 25 post lookups, 25 hiring
  lookups per run.
- Append-only signals, deduped on `sig_key` — re-scans never duplicate.
- Every scanned contact gets `signal_checked_at` stamped, found or not;
  7-day freshness window keeps re-runs cheap.
- Never logs into LinkedIn; public records and indexed content only.
