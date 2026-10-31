# TrustRoute — API Monitoring & Reliability Analysis System

TrustRoute checks your APIs on a schedule, measures response time, records every result in MySQL,
detects outages as incidents, raises alerts, and shows reliability analytics on a dashboard.

**Stack:** Django · Django REST Framework · Requests · APScheduler · MySQL · React (Vite) · React Router · Axios · Recharts · Lucide

> **Status note:** this code was generated in an environment with no package-registry access, so it has been
> syntax-checked but **not yet run end to end**. Follow the setup below, run `python manage.py test` and `npm test`,
> and open an issue / ask for fixes if anything fails. See "What to verify first" at the bottom.

## Project structure

```
trustroute/
├── backend/
│   ├── manage.py, requirements.txt, .env.example
│   ├── trustroute/            # Django project (settings, urls, wsgi)
│   └── monitor/
│       ├── models.py          # MonitoredAPI, CheckResult, Incident, Alert
│       ├── serializers.py, views.py, urls.py, filters.py, pagination.py
│       ├── scheduler.py       # APScheduler + atomic "claim" to avoid duplicate checks
│       ├── services/
│       │   ├── ssrf.py        # URL / DNS / redirect safety
│       │   ├── checker.py     # HTTP health check + persistence
│       │   ├── incidents.py   # open / close incidents
│       │   ├── analytics.py   # uptime + time series + dashboard summary
│       │   └── notifications.py  # in-app alerts + optional email
│       ├── management/commands/   # run_scheduler, run_checks_once, prune_checks
│       └── tests/             # mocked-HTTP tests (no internet needed)
├── frontend/                  # React + Vite app (src/pages, src/components, Vitest tests)
├── postman/TrustRoute.postman_collection.json
└── docs/                      # SAMPLE_SCENARIOS.md, TROUBLESHOOTING.md
```

## Prerequisites

- Python 3.10+ · Node 18+ · MySQL 8 (or MariaDB 10.6+) · VS Code (recommended)

## 1. MySQL setup

In a MySQL shell (`mysql -u root -p`):

```sql
CREATE DATABASE trustroute CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trustroute'@'localhost' IDENTIFIED BY 'choose-a-strong-password';
GRANT ALL PRIVILEGES ON trustroute.* TO 'trustroute'@'localhost';
GRANT ALL PRIVILEGES ON `test\_%`.* TO 'trustroute'@'localhost';  -- lets Django create its test database
FLUSH PRIVILEGES;
```

*No MySQL yet?* Set `DB_ENGINE=sqlite` in `.env` to try the app locally with a SQLite file.

## 2. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# edit .env: set DJANGO_SECRET_KEY and DB_PASSWORD

python manage.py makemigrations monitor   # generates the initial migration for your Django version
python manage.py migrate
python manage.py createsuperuser          # optional, for /admin/
python manage.py runserver
```

API: <http://127.0.0.1:8000/api/> · Swagger docs: <http://127.0.0.1:8000/api/docs/> · Schema: `/api/schema/`

`runserver` also starts the monitoring scheduler (when `SCHEDULER_ENABLED=True`).
Commit the generated `monitor/migrations/` folder to git.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, **register** an account, and add your first API. The Vite dev server proxies `/api`
to Django, so no CORS setup or backend URLs live in the frontend bundle. Production build: `npm run build`.

## 4. Tests

```bash
cd backend && python manage.py test        # uses mocked HTTP + mocked DNS; no internet required
cd frontend && npm test                    # Vitest: loading / empty / error / data states
```

Backend tests cover: healthy, slow, HTTP 500, connection failure, timeout, DNS failure, redirect-to-private blocked,
incident open → no duplicates → recovery, uptime formula, SSRF/URL validation, user isolation, endpoints, filters,
dashboard metrics and schema generation. Use `DB_ENGINE=sqlite python manage.py test` if you skip MySQL.

## 5. Postman

Import `postman/TrustRoute.postman_collection.json`. Run **Auth → Register** (stores the token), then
**Create API (healthy example)** (stores `apiId`), then any other request. Scenarios: `docs/SAMPLE_SCENARIOS.md`.

## How it works

**Checks.** Each check sends the configured HTTP method with Requests (`allow_redirects=False`, body not downloaded),
measures time-to-response in ms, and classifies it:

| Result | When |
|---|---|
| `healthy` | status == expected and time ≤ threshold |
| `slow` | status == expected and time > threshold |
| `failed` | timeout, DNS/connection/SSL error, blocked destination, or unexpected status |

Every result is saved as a `CheckResult` row.

**Incidents.** On the first failed check (from healthy, slow or not-yet-checked) an `Incident` opens with start time,
reason and status code. Further failures during the same outage add nothing. The first non-failed check closes it
(recovery time + duration). A row lock on the API serialises concurrent checks, so duplicates cannot occur.

**Alerts.** In-app alerts for failure, recovery, and *entering* slow state (not on every slow check). Email is optional:
set `ALERT_EMAIL_ENABLED=True` plus the `EMAIL_*` variables in `.env` (credentials never live in code).

**Uptime calculation (documented formula).**

```
uptime % = successful checks ÷ total completed checks × 100
```

A check is *successful* when the endpoint returned the expected status (healthy **or** slow); anything else is failed.
This is check-based, not wall-clock availability. With no checks the value is `null` (shown as “—”), not 100%.

## Request headers and body (e.g. Google AI Studio / Gemini)

Each API can have optional **request headers** and, for POST, a **request body**.

- Header values (API keys, tokens) are **encrypted in the database** (key derived from `DJANGO_SECRET_KEY`) and are
  **never returned by the API or shown in the UI** — only the header names are. Editing an API keeps saved headers unless you
  enter new ones or tick "Remove saved headers". If you change `DJANGO_SECRET_KEY`, re-enter headers.
- Headers and body are **not forwarded when a redirect goes to a different host**.
- Blocked headers: `Host`, `Content-Length`, `Transfer-Encoding`, `Connection`, `Upgrade`, `TE`, `Trailer`. Max 10 headers, body max 5000 chars.
- Put keys in headers, not in the URL, so they are not displayed or logged.

Gemini example (a real prompt, POST):

| Field | Value |
|---|---|
| URL | `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent` |
| Method / expected status | `POST` / `200` |
| Headers | `x-goog-api-key: YOUR_KEY` |
| Body | `{"contents":[{"parts":[{"text":"Reply with OK"}]}]}` |

Note: each check sends a real prompt and counts against your quota. Use a long interval (e.g. 600 s) and a small prompt.
Cheaper health check: `GET https://generativelanguage.googleapis.com/v1beta/models` with the same header.
Model names change over time; confirm a current one at the models endpoint.

## Security

- **SSRF:** URLs must be http/https, no embedded credentials; the hostname is resolved and *every* resolved IP must be
  public (blocks loopback, private, link-local incl. `169.254.169.254`, CGNAT, ULA, IPv4-mapped IPv6, `.local`/`.internal`).
  Validation runs on save **and before every request and every redirect hop** (max 5).
  *Limitation:* a DNS-rebinding race between our lookup and the actual connect is theoretically possible; for hostile multi-tenant
  use, run the worker in an egress-restricted network or pin resolved IPs.
- Only methods GET/HEAD/POST/OPTIONS; timeouts 1–30 s and shorter than the interval; minimum interval 30 s; max 50 APIs/user.
- Token auth; every query is scoped to `request.user`. Rate limits via DRF throttling (`THROTTLE_*`).
- Secrets only in `backend/.env` (git-ignored). Errors returned to clients never include stack traces; details go to logs.
- The frontend stores its API token in `localStorage` (simple for a SPA demo). For stricter deployments, move to
  httpOnly-cookie sessions.

## Scheduler: design and limitations

APScheduler runs one lightweight tick every `SCHEDULER_TICK_SECONDS`. For each due API it performs an atomic
`UPDATE … WHERE next_check_at <= now` to *claim* the check, then runs it in a thread pool. Only the process whose UPDATE
matched a row runs the check, so **multiple processes never duplicate or overlap checks**, and shutdown is clean
(`atexit` + SIGTERM for the worker).

**Limitations of the in-process mode** (`runserver`): the scheduler dies with the web process, is not started by
gunicorn/uwsgi, and shares CPU with web requests.

**Recommended production setup:** set `SCHEDULER_ENABLED=False` for web workers and run a dedicated worker:

```bash
python manage.py run_scheduler        # blocking scheduler, one per deployment (more are safe but unnecessary)
```

Alternatives: system cron / Windows Task Scheduler calling `python manage.py run_checks_once`, or move to Celery beat
+ Celery workers (call `monitor.services.checker.check_api` from a task). Old history is deleted daily
(`CHECK_RETENTION_DAYS`, or `python manage.py prune_checks`).

## Deployment preparation

1. `DJANGO_DEBUG=False`, strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=your.domain`, HTTPS in front.
2. `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic`.
3. Web: `gunicorn trustroute.wsgi:application --workers 3`. Worker: `python manage.py run_scheduler`.
4. Frontend: `npm run build`, serve `frontend/dist` from nginx and proxy `/api` to gunicorn (same origin, no CORS needed).
5. Keep `ALLOW_PRIVATE_URLS=False` and `ALLOW_REGISTRATION=False` if the instance is not public.

## What to verify first (not yet run)

1. `pip install -r requirements.txt`, `makemigrations monitor`, `migrate` succeed (re-run both after pulling model changes).
2. `python manage.py test` — all backend tests pass.
3. `npm install && npm test` — frontend tests pass.
4. Register, add `https://httpbin.org/status/200`, watch it turn green; add `/status/500` and confirm one incident + alert.

Troubleshooting: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
