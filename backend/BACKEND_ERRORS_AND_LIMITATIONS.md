# Backend Technical Audit: Errors, Vulnerabilities, and Architectural Limitations

**Repository:** `Compete`  
**Backend Subsystem:** `CompeteFastAPI`  
**Audit Scope:** Codebase architecture, data models, persistence services, concurrency primitives, caching layer, upstream integrations, worker scheduling, Docker deployment, and frontend contract alignment.  
**Test Verification Status:** 63/63 passing tests (55 legacy + 8 newly introduced failure-mode verification tests in `tests/test_workflow_and_edge_cases.py`).

---

## 1. Executive Summary

The `Compete` platform is designed to provide head-to-head developer comparisons and progress analytics using LeetCode data. While the FastAPI backend incorporates modern patterns (async SQLAlchemy 2.0, Alembic migrations, SingleFlight request coalescing, Redis caching with in-memory fallback, and APScheduler background tasks), deep structural analysis and automated edge-case testing revealed **critical concurrency deadlocks, database corruption, memory leaks, inconsistent error handling, deployment failure modes, and broken frontend integrations**.

---

## 2. Broken Links, Missing Files, and Defective Assets

### 2.1 Frontend Broken Dependencies and Assets
| File / Resource | Issue Type | Root Cause & Impact |
| :--- | :--- | :--- |
| `CompeteFrontend/vite.config.js` | **Fatal Build Error / Missing Package** | Imports `@tailwindcss/vite` on line 4, but `@tailwindcss/vite` is not declared in `package.json` or installed in `node_modules`. Running `npm run build` or `npm run dev` crashes immediately with `ERR_MODULE_NOT_FOUND`. |
| `CompeteFrontend/src/App.css` | **Build Dependency Error** | Contains `@import 'tailwindcss';` without the corresponding Tailwind v4 Vite plugin configured, breaking CSS bundling. |
| `CompeteFrontend/index.html` | **Broken HTML Link (404)** | Line 5 links to `/favicon.svg` (`<link rel="icon" type="image/svg+xml" href="/favicon.svg" />`), but `CompeteFrontend/public/` is completely empty. Causes HTTP 404 in browsers. |
| `CompeteFrontend/src/App.jsx` | **Linter Error / Unimplemented Shell** | Unused `useState` import fails `npm run lint` (`no-unused-vars`). Component returns empty fragment `<></>` with no integration to backend comparison APIs. |
| `CompeteFrontend/src/assets/` | **Empty Directory** | Directory exists with no assets or icons. |
| `CompeteFrontend/src/index.css` | **Empty File** | 0-byte file referenced in `main.jsx`. |

### 2.2 Backend Configuration & Documentation Gaps
| File / Resource | Issue Type | Root Cause & Impact |
| :--- | :--- | :--- |
| `CompeteFastAPI/pytest.ini` | **Missing Configuration** | Lacks `pythonpath = .`. Running standard `.venv/bin/pytest` directly from `CompeteFastAPI/` fails with `ModuleNotFoundError: No module named 'app'`. (Only `python -m pytest` works). |
| `CompeteFastAPI/.env.example` | **Missing File** | No example template exists. Developers must infer environment variables from code. |
| `CompeteFastAPI/.env` | **Hardcoded Local Secret Exposure** | Contains personal credentials `DATABASE_URL="postgresql://aarav:aarav123@localhost:5432/compete_database"`, inconsistent with `docker-compose.yml` (`compete_user:compete_password`) and `config.py` (`postgres:postgres`). |
| Root `README.md` | **Incomplete File** | Contains only `# compete`, lacking setup instructions, architecture diagrams, and run commands. |
| `CompeteFastAPI/alembic/README` | **Placeholder File** | Contains default one-line template string: `Generic single-database configuration.`. |
| `CompeteFastAPI/app/api/v1/*` | **Divergent API Pathing** | Workspace metadata refers to `app/api/v1/endpoints/`, but actual codebase structure is flattened directly under `app/api/endpoints/` with no `/v1` namespace. |

---

## 3. Critical Backend Bugs & Concurrency Deadlocks

### 3.1 SingleFlight Request Coalescing Hang on Task Cancellation
* **Location:** `CompeteFastAPI/app/services/single_flight.py:42-58`
* **Severity:** **CRITICAL** (Deadlock & Memory Leak)
* **Mechanics:**
  In `SingleFlight.execute()`, the leader task executes inside:
  ```python
  try:
      result = await fn()
      if not future.done():
          future.set_result(result)
      return result
  except Exception as exc:
      if not future.done():
          future.set_exception(exc)
      raise
  finally:
      async with self._lock:
          self._calls.pop(key, None)
  ```
  In Python 3.8+, `asyncio.CancelledError` inherits from `BaseException`, **not** `Exception`. When a client disconnects or an upstream timeout cancels the leader task, `except Exception` is skipped!
* **Consequence:**
  The `future` is never marked as done (`future.set_result` / `future.set_exception` are never called). In the `finally` block, the key is removed from `_calls`. However, all follower coroutines that were waiting on `await asyncio.shield(future)` **hang indefinitely**, consuming memory and event loop slots.
* **Verification:** Verified by `test_single_flight_leader_cancellation_hangs_followers`.

---

### 3.2 Permanent Redis Disconnection on Transient Failure
* **Location:** `CompeteFastAPI/app/services/cache_service.py:34-77`
* **Severity:** **HIGH** (Degraded Performance / No Auto-Recovery)
* **Mechanics:**
  When connecting to Redis in `_get_redis()`, or if a transient socket timeout occurs in `get()` or `set()`, the service executes:
  ```python
  except Exception as e:
      self._is_redis_available = False
  ```
  Subsequent requests evaluate:
  ```python
  if self._redis is None and self._is_redis_available:
      ...
  return self._redis
  ```
* **Consequence:**
  Once a single connection error occurs (e.g., Redis restarting, network blip, or temporary overload), `_is_redis_available` is flipped to `False` and **is never reset to `True`**. The entire application remains locked into the in-memory fallback cache permanently until the FastAPI process is restarted.
* **Verification:** Verified by `test_cache_service_cannot_recover_after_transient_failure`.

---

### 3.3 Unbounded In-Memory Fallback Cache (Memory Leak)
* **Location:** `CompeteFastAPI/app/services/cache_service.py:31, 80-101`
* **Severity:** **HIGH** (Out-Of-Memory Risk)
* **Mechanics:**
  `CacheService._fallback_store` is an unconstrained Python dictionary:
  ```python
  self._fallback_store: Dict[str, Tuple[str, float]] = {}
  ```
  Expired entries are only removed during explicit `get(key)` calls:
  ```python
  if key in self._fallback_store:
      val, expire_at = self._fallback_store[key]
      if time.time() < expire_at:
          return val
      self._fallback_store.pop(key, None)
  ```
* **Consequence:**
  Keys that are written once (e.g. user activity snapshots, temporary comparisons) and never queried again remain stored in RAM indefinitely. There is no max size, no LRU eviction, and no periodic expiration scrubber. Under prolonged Redis downtime or high request volume, this leads to an unbounded memory leak.
* **Verification:** Verified by `test_cache_fallback_store_unbounded_growth`.

---

## 4. Data Layer & Persistence Deficiencies

### 4.1 Problem Catalog Corruption: Submission ID vs. Question ID
* **Location:** `CompeteFastAPI/app/services/problem_service.py:57-73`
* **Severity:** **HIGH** (Data Integrity Corruption)
* **Mechanics:**
  In `record_user_problems()`:
  ```python
  question_id: Optional[int] = None
  if item.id and item.id.isdigit():
      question_id = int(item.id)
  if problem is None:
      problem = Problem(frontend_question_id=question_id, ...)
  ```
  `ProblemStatusItem.id` is populated in `leetcode_client.py:320` from LeetCode's `recentAcSubmissionList` query:
  ```graphql
  recentAcSubmissionList(username: $username, limit: $limit) {
    id
    title
    titleSlug
    timestamp
  }
  ```
* **Consequence:**
  In LeetCode's GraphQL API, the `id` field of `recentAcSubmissionList` is the **Submission ID** (e.g. `1423891024`), **not** the LeetCode Question Number (e.g. Problem 1 for "Two Sum"). The database table `problems.frontend_question_id` gets populated with random multi-digit submission identifiers, destroying problem ordering and catalog accuracy.
* **Verification:** Verified by `test_problem_service_confuses_submission_id_with_question_id`.

---

### 4.2 Nonexistent User 404 Discrepancy & Database Ghost User Pollution
* **Location:** `CompeteFastAPI/app/services/leetcode_client.py:274-332` & `CompeteFastAPI/app/api/endpoints/users.py:43-81`
* **Severity:** **HIGH** (Data Pollution & API Contract Inconsistency)
* **Mechanics:**
  1. `get_user_profile` checks `matchedUser` and properly raises `UserNotFoundError` (HTTP 404).
  2. In contrast, `get_user_activity` and `get_user_problems` do **not** check if the user exists. When querying LeetCode for a nonexistent user, LeetCode returns null lists, which default to `[]`. Both endpoints return HTTP 200 OK with empty arrays:
     - `/api/users/fake_user/activity` -> `{"username": "fake_user", "total": 0, "submissions": []}` (HTTP 200)
     - `/api/users/fake_user/problems` -> `{"username": "fake_user", "total": 0, "problems": []}` (HTTP 200)
  3. When these endpoints are queried, background tasks `_persist_submissions` and `_persist_user_problems` execute:
     ```python
     user = result.scalar_one_or_none()
     if user is None:
         user = User(username=username)
         session.add(user)
         await session.flush()
     ```
* **Consequence:**
  Any arbitrary typo or malicious script querying `/api/users/{junk_string}/activity` inserts a permanent ghost `User` record into PostgreSQL with `real_name=None`, `contest_rating=None`, etc.
* **Verification:** Verified by `test_nonexistent_user_returns_200_for_activity_and_problems` and `test_background_task_pollutes_db_with_ghost_users`.

---

### 4.3 Concurrent Insertion Race Conditions & Constraint Violations
* **Location:** `CompeteFastAPI/app/services/problem_service.py:61-70` & `CompeteFastAPI/app/services/submission_service.py:35-68`
* **Severity:** **MEDIUM-HIGH** (Transient Database Crashes)
* **Mechanics:**
  1. **Problem Insertion:** If two users simultaneously submit activity containing a newly introduced LeetCode problem, both concurrently select `Problem` by slug, find None, and attempt `session.add(problem)`. Since `problems.title_slug` has a `UNIQUE` constraint, one will fail with `UniqueViolationError`.
  2. **Submission Insertion:** `upsert_submissions` fetches `existing_ids` prior to the loop. If duplicate items exist in the incoming payload, or if two requests process identical submissions concurrently, duplicate `Submission(submission_id=...)` rows are staged. Because `session.add_all()` does not use PostgreSQL's `ON CONFLICT DO NOTHING`, an `IntegrityError` is thrown, aborting the transaction.
* **Verification:** Verified by `test_upsert_submissions_batch_duplicates`.

---

### 4.4 Solving Velocity Calculation Skew & Timezone Truncation
* **Location:** `CompeteFastAPI/app/services/stats_service.py:91-95`
* **Severity:** **MEDIUM** (Metrics Distortion)
* **Mechanics:**
  In `compute_solving_velocity`:
  ```python
  delta_solved = max(0, current_total - reference_snapshot.total_solved)
  elapsed_days = max(
      1,
      (datetime.now(timezone.utc) - reference_snapshot.snapshot_at).days,
  )
  return round(delta_solved / elapsed_days, 2)
  ```
  `timedelta.days` returns the integer number of full 24-hour periods. A snapshot taken 23 hours ago has `.days == 0`. A snapshot taken 47 hours ago has `.days == 1`.
* **Consequence:**
  Any snapshot taken between 1 hour and 47.9 hours ago is treated as `elapsed_days = 1`. A user who solved 20 problems over 2 days will register a 7-day velocity of `20 / 1 = 20.0 problems/day` instead of `20 / 2 = 10.0 problems/day`, distorting competition match scoring.

---

## 5. Scoring & Business Logic Flaws

### 5.1 Streak Calculation Accrues on Failed Submissions
* **Location:** `CompeteFastAPI/app/services/competition_service.py:65-88`
* **Severity:** **MEDIUM** (Scoring Inaccuracy)
* **Mechanics:**
  In `calculate_streak`:
  ```python
  active_dates = set()
  for s in submissions:
      if s.timestamp:
          sub_date = datetime.fromtimestamp(s.timestamp, tz=timezone.utc).date()
          active_dates.add(sub_date)
  ```
  In contrast to `calculate_window_solves()` (which explicitly checks `s.status.lower() in ("accepted", "solved")`), `calculate_streak()` includes **any** submission status.
* **Consequence:**
  A user submitting broken code that results in "Wrong Answer", "Runtime Error", or "Compile Error" maintains and increases their active competition streak, gaining up to 100 streak points undeservedly.
* **Verification:** Verified by `test_streak_counts_wrong_answer_submissions`.

---

### 5.2 Self-Comparison Endpoint Duplication Bug
* **Location:** `CompeteFastAPI/app/api/endpoints/compare.py:55-92` & `CompeteFastAPI/app/services/competition_service.py:272-279`
* **Severity:** **MEDIUM** (Response Schema Inconsistency)
* **Mechanics:**
  The endpoint allows comparing a user against themselves (e.g. `/api/compare/alice/alice`). In `CompareResponse`:
  ```python
  score = {
      first_profile.username: first_score,
      second_profile.username: second_score,
  }
  ```
* **Consequence:**
  Because dictionary keys must be unique, the second entry overwrites the first. The returned `score` and `scoreBreakdown` contain only a single user key instead of two, breaking UI expectations on the frontend. The API should reject self-comparison with HTTP 400 Bad Request.

---

## 6. Infrastructure, Docker & Deployment Deficiencies

### 6.1 Docker Healthcheck False Positive
* **Location:** `CompeteFastAPI/Dockerfile:32-33` & `CompeteFastAPI/app/main.py:136-177`
* **Severity:** **HIGH** (Container Orchestration Blindness)
* **Mechanics:**
  In `Dockerfile`:
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
      CMD curl -f http://localhost:8000/health || exit 1
  ```
  In `app/main.py`, `/health` probes database, cache, and scheduler. If PostgreSQL and Redis are both offline, the endpoint returns:
  ```json
  {"status": "unhealthy", "database": {"status": "unhealthy"}, "cache": {"status": "degraded"}}
  ```
  However, the HTTP response status code is **always `200 OK`**.
* **Consequence:**
  `curl -f` treats HTTP 200 as successful. Docker and Kubernetes will flag the container as "HEALTHY" even when the database is unreachable, cache is down, and all user data queries fail with 500 errors.

---

### 6.2 Missing Database Migrations on Startup / Compose
* **Location:** `CompeteFastAPI/Dockerfile:36` & `CompeteFastAPI/docker-compose.yml:4-30`
* **Severity:** **HIGH** (Initial Deployment Crash)
* **Mechanics:**
  The `Dockerfile` CMD starts `uvicorn app.main:app` directly. `app/db/init_db.py` contains `init_db()`, but it is **never called** in `app/main.py` lifespan.
* **Consequence:**
  When executing `docker compose up`, PostgreSQL starts with zero tables. CompeteFastAPI starts up, but fails with `UndefinedTable: relation "users" does not exist` on the first API request or scheduled background sync. Alembic migrations must be executed either via an entrypoint script (`alembic upgrade head`) or within `lifespan`.

---

### 6.3 Background Scheduler Unbounded Query & Single-Transaction Bottleneck
* **Location:** `CompeteFastAPI/app/workers/scheduler.py:24-64`
* **Severity:** **HIGH** (Production Scalability Bottleneck)
* **Mechanics:**
  In `sync_tracked_users_snapshots()`:
  ```python
  async with async_session_factory() as session:
      result = await session.execute(select(User))
      users = result.scalars().all()
      for user in users:
          profile = await client.get_user_profile(user.username)
          await record_snapshot(session, user, profile)
      await session.commit()
  ```
* **Consequence:**
  1. **Memory Spike:** Fetches all users across the entire platform in a single unpaginated query.
  2. **Long-Lived Transaction:** Loops sequentially through all users while keeping a single database transaction open. If there are 500 users and each profile fetch takes 0.5s, the transaction remains open for over 4 minutes, holding locks and pool connections.
  3. **Upstream Rate Limiting:** Serial requests without delays or token buckets will trigger LeetCode HTTP 429 rate limits.
  4. **All-or-Nothing Failure:** If a single database commit constraint fails at the end, all snapshot records for the entire batch roll back.

---

### 6.4 SlowAPI Rate Limiting Behind Reverse Proxies
* **Location:** `CompeteFastAPI/app/core/limiter.py:7`
* **Severity:** **MEDIUM** (Denial of Service for All Clients)
* **Mechanics:**
  `limiter = Limiter(key_func=get_remote_address)`.
* **Consequence:**
  When deployed behind Docker bridge networking, Nginx, or cloud load balancers (AWS ALB, Cloudflare), `request.client.host` represents the reverse proxy's IP. All inbound users share a single rate-limit bucket (60 req/min for general routes, 30 req/min for compare), leading to false rate-limit rejections for legitimate users.

---

## 7. Test Suite Audit & Workflow Verification Results

### 7.1 Existing Test Suite Analysis
The pre-existing tests in `CompeteFastAPI/tests/` consisted of 55 tests covering:
- Happy paths for LeetCode adapter and mock response parsing (`test_leetcode_adapter.py`)
- Basic API routes with mocked GraphQL client (`test_api_endpoints.py`)
- SQLite in-memory persistence and velocity formulas (`test_persistence.py`)
- In-memory cache operations (`test_cache_service.py`)
- Basic SingleFlight deduplication (`test_single_flight.py`)

**What Existing Tests Missed:**
- Leader coroutine cancellation in `SingleFlight`.
- Reconnection failure in `CacheService`.
- In-memory cache eviction and memory leakage.
- Nonexistent user error handling across activity and problem endpoints.
- Database ghost record pollution from background tasks.
- Problem catalog question ID vs. submission ID mixup.
- In-batch duplicate submission constraints.
- Failed submission streak inflation.

### 7.2 Verification Suite: `tests/test_workflow_and_edge_cases.py`
To verify the identified limitations, 8 targeted workflow tests were introduced and executed against the codebase:

```bash
CompeteFastAPI/.venv/bin/python -m pytest tests/test_workflow_and_edge_cases.py
```
**Results:**
```text
============================= test session starts ==============================
platform linux -- Python 3.14.8, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/unknownentity/Projects/Compete/CompeteFastAPI
configfile: pytest.ini
plugins: anyio-4.15.1, asyncio-1.4.0
collected 8 items

tests/test_workflow_and_edge_cases.py::test_single_flight_leader_cancellation_hangs_followers PASSED
tests/test_workflow_and_edge_cases.py::test_cache_service_cannot_recover_after_transient_failure PASSED
tests/test_workflow_and_edge_cases.py::test_cache_fallback_store_unbounded_growth PASSED
tests/test_workflow_and_edge_cases.py::test_nonexistent_user_returns_200_for_activity_and_problems PASSED
tests/test_workflow_and_edge_cases.py::test_background_task_pollutes_db_with_ghost_users PASSED
tests/test_workflow_and_edge_cases.py::test_problem_service_confuses_submission_id_with_question_id PASSED
tests/test_workflow_and_edge_cases.py::test_upsert_submissions_batch_duplicates PASSED
tests/test_workflow_and_edge_cases.py::test_streak_counts_wrong_answer_submissions PASSED

======================== 8 passed, 5 warnings in 0.49s =========================
```

**Total Combined Test Status:** **63 passed, 0 failed** in 2.47s.

---

## 8. Prioritized Remediation Roadmap

### Priority 1: Critical Fixes (Data Integrity & Process Stability)
1. **Fix SingleFlight Cancellation:**
   Catch `BaseException` in `SingleFlight.execute()`. If the leader is cancelled, set the exception or cancel the future before re-raising, unblocking all waiting followers.
2. **Prevent Ghost User Insertion:**
   Validate user existence via `get_user_profile()` before dispatching background persistence tasks for `/activity` and `/problems`. Return HTTP 404 if the user is not found.
3. **Correct Problem Catalog Ingestion:**
   Do not store `item.id` as `frontend_question_id`. Either query LeetCode's problem details GraphQL query for `questionFrontendId` or allow `frontend_question_id` to remain `None` until resolved.
4. **Fix Frontend Build & Assets:**
   Install `@tailwindcss/vite` in `CompeteFrontend/package.json`, provide a valid `favicon.svg` in `public/`, and remove the unused `useState` in `App.jsx`.

### Priority 2: Reliability & Error Handling
1. **Cache Service Auto-Recovery & Eviction:**
   Implement backoff-based reconnection attempts in `_get_redis()` instead of permanently locking `_is_redis_available = False`. Add an LRU cache or max-size limit (e.g. `collections.OrderedDict` with 10,000 key ceiling) to the in-memory fallback store.
2. **PostgreSQL Upsert Safety:**
   Refactor `upsert_submissions` and `record_user_problems` to use SQLAlchemy PostgreSQL dialect `insert().on_conflict_do_nothing()` or `on_conflict_do_update()` to prevent unique key constraint crashes under concurrency.
3. **Enforce Accepted Submissions in Streak Calculation:**
   Filter `submissions` in `CompetitionService.calculate_streak` using `s.status.lower() in ("accepted", "solved")`.
4. **Reject Self-Comparison:**
   Add validation in `compare_users`: if `first_user.lower() == second_user.lower()`, return HTTP 400 Bad Request.

### Priority 3: Infrastructure & Production Readiness
1. **Docker Healthcheck HTTP Status Code:**
   Update `/health` to return HTTP 503 Service Unavailable when the database is unhealthy so container orchestrators can detect failures.
2. **Automate Migrations on Startup:**
   Add an entrypoint script to `Dockerfile`:
   ```bash
   alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. **Refactor APScheduler Job:**
   Paginate user loading using `yield_per(100)` or batch chunks. Use an async worker queue with concurrency limits and rate-limiting delays between LeetCode queries, committing each user in its own transaction.
4. **Add `pythonpath = .` to `pytest.ini`:**
   Enables direct invocation of `pytest` without needing `python -m pytest`.

