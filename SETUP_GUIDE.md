# Setup Guide — GlowMath Course

> **Last updated:** 2026-05-28. Fresh-install steps for a new developer. ETA: 10–15 minutes.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | project tested on 3.12.x |
| Git | any | |
| Editor | VS Code or PyCharm | Django + Tailwind extensions recommended |
| PostgreSQL | 15+ | **optional** — only needed for prod-parity testing. Dev uses SQLite. |

---

## Quick Start (5 commands to a working dashboard)

### 1. Clone + create virtualenv

```bash
git clone <repo-url> glowmathcourse
cd glowmathcourse

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create `.env` at project root (gitignored):

```env
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=django-insecure-replace-this-with-anything-for-local-dev
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

(For prod you'd also set `DATABASE_URL=postgres://...` but that's not needed for dev.)

### 4. Migrate + seed data

```bash
python manage.py migrate
python manage.py create_test_users      # named users: Rafael, Trista, GlowMath admin
python manage.py populate_full_demo     # idempotent — full demo dataset (~30s)
```

### 5. Run dev server

```bash
python manage.py runserver 8765
```

Open http://localhost:8765/ — student login page renders.

---

## Login & verify (3 portals)

| Role | Username | Password | URL |
|---|---|---|---|
| Student | `rafaeladhikabagasalfathan` | `ikanbuvivid` | http://localhost:8765/ |
| Teacher | `candrarinitristaharidewati` | `ikanbuvivid` | http://localhost:8765/guru/login/ |
| Admin | `glowmathcourse` | `ikanbuvivid` | http://localhost:8765/admin/login/ |

After Rafael logs in:
- `/dashboard/student/` renders Khan V3 dashboard
- `/my-classes/` shows ~6 UMUM enrollments with a rate-prompt badge on the unrated COMPLETED card
- `/announcements/` lists pengumuman with orange Khan Playful styling
- `/help/` shows the Bantuan FAQ

If those render, setup is complete. ✅

---

## Common setup issues

### ❌ `runserver` port 8000 occupied

The project standard is port **8765** (not 8000 — see [CLAUDE.md](CLAUDE.md)). If 8765 is also busy:

```bash
python manage.py runserver 9999
```

Just remember the absolute URLs in test-helper scripts assume 8765.

### ❌ `psycopg2-binary` build error on `pip install`

This is the Postgres driver and is **only needed for prod**. For dev (SQLite) you can skip it:

```bash
pip install -r requirements.txt --no-binary psycopg2-binary
# or simply ignore the error — dev runs without it
```

### ❌ Migrations error / "no such table"

If models are out of sync after a pull:

```bash
python manage.py makemigrations
python manage.py migrate
```

If you see `OperationalError: no such table: ...` at runtime, run `migrate` first.

### ❌ Static files not loading (CSS, icons missing)

Tailwind/HTMX/Alpine come from CDN — they should "just work". For local-only CSS in `static/css/`:

```bash
python manage.py collectstatic --noinput
```

Then ensure `STATIC_URL = '/static/'` in `config/settings/dev.py`.

### ❌ Empty test data after migrate

Re-run the populate command:

```bash
python manage.py populate_full_demo
```

It's idempotent — safe to run multiple times. Use `--reset` to wipe and start fresh.

### ❌ `ALLOWED_HOSTS` error in `testserver` flow

When running ad-hoc Python tests with `Client()`, add `'testserver'` to `ALLOWED_HOSTS` first:

```python
settings.ALLOWED_HOSTS = list(set(list(settings.ALLOWED_HOSTS) + ['testserver']))
```

### ❌ `Faker` not installed (dummy names look generic)

```bash
pip install Faker
python manage.py populate_full_demo --reset    # regenerate with realistic id_ID names
```

`Faker` is optional — without it, the populate command falls back to a fixed name pool.

---

## VS Code recommended extensions

- **Python** (Microsoft)
- **Django** (`batisteo.vscode-django`) — template syntax highlighting
- **Tailwind CSS IntelliSense** — class autocomplete
- **HTMX support** (if available in marketplace)
- **Alpine.js IntelliSense** (`adrianwilczynski.alpine-js-intellisense`)
- **Black Formatter** + **isort** — Python style

Optional settings for `.vscode/settings.json`:

```json
{
  "files.associations": { "*.html": "django-html" },
  "emmet.includeLanguages": { "django-html": "html" },
  "python.analysis.typeCheckingMode": "basic"
}
```

---

## Development workflow

1. **Always work on a feature branch** — never push directly to `main`.
2. **Run `python manage.py check`** before committing. Should end "0 silenced".
3. **Manual QA per test users** in [TEST_USERS.md](TEST_USERS.md) — login as Rafael for student-side changes, Trista for teacher-side, GlowMath for admin.
4. **Reference [PITFALLS.md](PITFALLS.md) before debugging** — chances are someone hit it already.
5. **Update [CHANGELOG.md](CHANGELOG.md)** for significant features or behavior changes.
6. **Check [URL_ROUTES.md](URL_ROUTES.md) before writing `{% url %}`** — wrong namespace is the #1 cause of `NoReverseMatch`.

---

## Next steps after setup

1. [`CLAUDE.md`](CLAUDE.md) — project conventions + what NOT to build
2. [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) — Khan Playful, Notion Clean, Data Pro visual variants
3. [`ERD_REFERENCE.md`](ERD_REFERENCE.md) — 26-table schema
4. [`URL_ROUTES.md`](URL_ROUTES.md) — every namespaced URL with view
5. [`PHASE_ROADMAP.md`](PHASE_ROADMAP.md) — what's done + what's next

---

## Production deployment (preview)

Phase 4 will document Hostinger VPS setup in detail. Quick preview:

- Ubuntu 24.04 + Nginx reverse proxy + Gunicorn (systemd unit)
- PostgreSQL via `DATABASE_URL` env var
- whitenoise for static; let's encrypt for SSL
- `Procfile` at repo root already wires `gunicorn config.wsgi:application`
- Set `DJANGO_SETTINGS_MODULE=config.settings.production`, `DEBUG=False`, real `SECRET_KEY`, real `ALLOWED_HOSTS`
