# Backend Status and Operational Notes

This document replaces an earlier audit whose findings no longer matched the backend implementation.

## Remediated issues

- SingleFlight resolves followers when a leader raises or is cancelled.
- Redis reconnects after transient failures. Cache data also has a PostgreSQL fallback and a bounded process-local fallback.
- Cache expiration is enforced across stores, and clearing the LeetCode cache leaves scheduler locks and rate-limit keys intact.
- User, problem, submission, and user-problem writes handle concurrent inserts with database upserts or conflict handling.
- Problem catalog ingestion uses LeetCode question metadata instead of treating submission IDs as question numbers.
- Activity and problem requests return 404 for nonexistent LeetCode users. Background persistence does not create placeholder users.
- Comparison rejects self-comparison, and streak scoring counts accepted solves only.
- Snapshot synchronization uses bounded, keyset-paginated batches with short-lived database sessions.
- Health checks return HTTP 503 when PostgreSQL is unavailable. Trusted proxy headers are only used for configured proxy addresses.
- Rate limiting falls back to process-local counters if Redis becomes unavailable.
- Schema changes run through Alembic; startup no longer stamps a schema version after creating tables directly.

## Operational notes

- The container applies Alembic migrations before starting Uvicorn. For local development, run `alembic upgrade head` from `backend/` before starting the server.
- The persistent cache fallback requires the `0002_persistent_database_cache` migration. When PostgreSQL is unavailable, the backend continues with bounded process memory; Redis-backed scheduler locking is skipped so multiple workers cannot run the same sync without coordination.
- Rate-limit counters are per process during Redis outages, so limits can temporarily differ between replicas.
- LeetCode activity responses are capped at 50 recent submissions. Historical analytics therefore depend on snapshots and submissions previously captured by this backend.
- Cache and database fallback data are disposable. PostgreSQL remains the source of truth for user records, submissions, problem associations, and statistics.

## Verification

The repository contains regression tests under `tests/`. They were not run as part of the current code review.
