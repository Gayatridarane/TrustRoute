# Troubleshooting

## Setup

**`pip install` fails building `mysqlclient`**
The project uses **PyMySQL** (pure Python), so `mysqlclient` is not needed. Make sure you installed from `backend/requirements.txt`.

**`django.db.utils.OperationalError: (1045, Access denied for user ...)`**
`DB_USER` / `DB_PASSWORD` in `backend/.env` don't match the MySQL user you created. Re-run the SQL in the README.

**`(2003, Can't connect to MySQL server on '127.0.0.1')`**
MySQL isn't running or `DB_HOST`/`DB_PORT` are wrong. Start the MySQL service (Windows: *Services → MySQL80 → Start*).

**`RuntimeError: 'cryptography' package is required for sha256_password or caching_sha2_password`**
Run `pip install cryptography` (it is in requirements.txt). MySQL 8 uses `caching_sha2_password` by default.

**`ImproperlyConfigured: DJANGO_SECRET_KEY must be set`**
Copy `backend/.env.example` to `backend/.env`. For local work keep `DJANGO_DEBUG=True`.

**`No changes detected` / tables missing**
Run `python manage.py makemigrations monitor` then `python manage.py migrate`. (The initial migration is generated on your machine so it matches your Django version.)

**Tests fail with "Access denied ... to database 'test_trustroute'"**
Django creates a throwaway `test_trustroute` database. Grant the user rights on it:
`GRANT ALL ON \`test\_%\`.* TO 'trustroute'@'localhost';`
Or run tests on SQLite: `DB_ENGINE=sqlite python manage.py test` (PowerShell: `$env:DB_ENGINE="sqlite"; python manage.py test`).

**Want to try without MySQL?** Set `DB_ENGINE=sqlite` in `.env`.

## Running

**Frontend shows "Cannot reach the TrustRoute server"**
Backend isn't running on port 8000. Start it with `python manage.py runserver`. If it runs elsewhere, start Vite with `VITE_BACKEND_URL=http://host:port npm run dev`.

**Everything redirects to /login**
Your token expired or was deleted (e.g. after Sign out). Sign in again.

**APIs stay "Pending" and no checks happen**
- The scheduler only starts with `python manage.py runserver` and `SCHEDULER_ENABLED=True`.
- Under gunicorn/uwsgi it does **not** auto-start; run `python manage.py run_scheduler` in a second terminal.
- You can force checks with the **Run check now** button or `python manage.py run_checks_once`.

**Scheduler log appears twice / checks run twice**
`runserver` starts a reloader process; TrustRoute only starts the scheduler in the serving child. Even if two schedulers ran, an atomic database claim makes each check run once per interval.

**My URL is rejected: "resolves to a private … address"**
That's the SSRF protection working. Use a public endpoint, or for local demos only set `ALLOW_PRIVATE_URLS=True`.

**Every check says "DNS resolution failed" / "Connection failed"**
The machine running the backend has no internet access, or a corporate proxy blocks it. `requests` honours `HTTP_PROXY`/`HTTPS_PROXY` environment variables.

**HTTP 429 "Too many requests"**
You hit a rate limit. Adjust `THROTTLE_*` in `.env`.

## Frontend

**`npm install` errors on old Node**
Use Node 18 or newer.

**Blank page after login**
Open the browser console. A failing `/api/...` call usually means the backend is down or migrations weren't applied.
