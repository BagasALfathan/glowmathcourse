# Deployment Guide — GlowMath Course

> **Status:** 🟡 **NOT YET DEPLOYED.** This is a forward-looking blueprint for **Phase 4**. The Hostinger VPS is provisioned but no app code runs there yet.
>
> **Target:** Hostinger VPS KVM 1 at `76.13.219.144` (Ubuntu 24.04), domain `glowmathclass.com`.
>
> **Last updated:** 2026-05-28.

---

## Stack migration: Dev → Prod

| Component | Dev | Prod |
|---|---|---|
| Python | 3.12+ | 3.12 (system or via deadsnakes) |
| Django settings | `config.settings.dev` | `config.settings.production` |
| Database | SQLite (`db.sqlite3`) | PostgreSQL 16 |
| Server | `runserver` on port 8765 | Gunicorn (UDS) behind Nginx (80/443) |
| Static files | Django dev autoserve | Nginx serving `/staticfiles/` (collectstatic output) |
| Media files | Django dev autoserve | Nginx serving `/media/` |
| Cache | `LocMemCache` (default) | LocMem fine for single-process; consider Redis for multi-worker |
| Email | console backend | SMTP (Hostinger mail or Mailgun) |
| Domain | `localhost:8765` | `glowmathclass.com` (+ www) |
| TLS | none | Let's Encrypt via certbot |
| Logs | stdout | systemd journal + Nginx access/error logs |

---

## Pre-deployment checklist

- [ ] `DEBUG=False` in `config/settings/production.py`
- [ ] `ALLOWED_HOSTS = ['glowmathclass.com', 'www.glowmathclass.com', '76.13.219.144']`
- [ ] `SECRET_KEY` rotated (NOT the dev key — generate a new one)
- [ ] `DATABASE_URL` configured in `.env` (parsed via `dj-database-url`)
- [ ] `STATIC_ROOT` set; `python manage.py collectstatic --noinput` succeeds locally
- [ ] `MEDIA_ROOT` directory will exist on the server with `www-data` write access
- [ ] `CSRF_TRUSTED_ORIGINS = ['https://glowmathclass.com', 'https://www.glowmathclass.com']`
- [ ] `SECURE_SSL_REDIRECT = True`
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] `SECURE_HSTS_SECONDS = 31536000` (after SSL verified)
- [ ] `python manage.py migrate --check` returns 0 unapplied migrations
- [ ] `python manage.py check --deploy` reviewed (warnings addressed)
- [ ] Local `db.sqlite3` backed up via `python manage.py backup_database`
- [ ] `ENABLE_PAYMENT_FEATURE` confirmed `False` (no payment UI in prod yet)
- [ ] Domain DNS A-records pointing to `76.13.219.144`

---

## Step-by-step deployment

### 1. SSH into the VPS

```bash
ssh root@76.13.219.144
```

### 2. System setup (one-time)

```bash
apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip \
               nginx postgresql postgresql-contrib \
               certbot python3-certbot-nginx git ufw

# Firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

### 3. PostgreSQL setup

```bash
sudo -u postgres psql <<EOF
CREATE DATABASE glowmath_prod;
CREATE USER glowmath_user WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE glowmath_prod TO glowmath_user;
ALTER DATABASE glowmath_prod OWNER TO glowmath_user;
\q
EOF
```

### 4. App user + clone

```bash
adduser --system --group --home /var/www/glowmathcourse glowmath
mkdir -p /var/www/glowmathcourse
cd /var/www/glowmathcourse
git clone <repo-url> .
chown -R glowmath:www-data /var/www/glowmathcourse
```

### 5. Virtualenv + dependencies

```bash
sudo -u glowmath python3.12 -m venv venv
sudo -u glowmath venv/bin/pip install -r requirements.txt
# psycopg2-binary + gunicorn are already in requirements.txt — no separate install
```

### 6. Environment variables

Create `/var/www/glowmathcourse/.env` (mode 600):

```env
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<generate-with-django-secret-key-generator>
DEBUG=False
DATABASE_URL=postgres://glowmath_user:STRONG_PASSWORD@localhost:5432/glowmath_prod
ALLOWED_HOSTS=glowmathclass.com,www.glowmathclass.com,76.13.219.144
EMAIL_HOST=smtp.hostinger.com
EMAIL_HOST_USER=noreply@glowmathclass.com
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_PORT=587
EMAIL_USE_TLS=True
```

```bash
chmod 600 /var/www/glowmathcourse/.env
chown glowmath:glowmath /var/www/glowmathcourse/.env
```

### 7. Django setup

```bash
cd /var/www/glowmathcourse
sudo -u glowmath venv/bin/python manage.py migrate
sudo -u glowmath venv/bin/python manage.py collectstatic --noinput
sudo -u glowmath venv/bin/python manage.py createsuperuser
sudo -u glowmath venv/bin/python manage.py create_test_users   # optional for initial demo
```

### 8. Gunicorn systemd unit

Create `/etc/systemd/system/glowmath.service`:

```ini
[Unit]
Description=Gunicorn for GlowMath Course
After=network.target postgresql.service

[Service]
User=glowmath
Group=www-data
WorkingDirectory=/var/www/glowmathcourse
EnvironmentFile=/var/www/glowmathcourse/.env
ExecStart=/var/www/glowmathcourse/venv/bin/gunicorn \
          --workers 3 \
          --timeout 60 \
          --access-logfile - \
          --error-logfile - \
          --bind unix:/var/www/glowmathcourse/gunicorn.sock \
          config.wsgi:application
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable glowmath
systemctl start glowmath
systemctl status glowmath    # verify "active (running)"
```

> The repo's `Procfile` (used by Heroku-style platforms) already wires `gunicorn config.wsgi`. The systemd unit above does the same for direct VPS install.

### 9. Nginx config

Create `/etc/nginx/sites-available/glowmathclass.com`:

```nginx
upstream glowmath_app {
    server unix:/var/www/glowmathcourse/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    server_name glowmathclass.com www.glowmathclass.com;

    client_max_body_size 25M;         # Course-material uploads cap at 20 MB (Prompt 11); 25 covers multipart overhead
    keepalive_timeout 60s;

    location /static/ {
        alias /var/www/glowmathcourse/staticfiles/;
        expires 30d;
        access_log off;
    }

    location /media/ {
        alias /var/www/glowmathcourse/media/;
        expires 7d;
    }

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_pass http://glowmath_app;
    }

    location = /favicon.ico { access_log off; log_not_found off; }
}
```

```bash
ln -s /etc/nginx/sites-available/glowmathclass.com /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

### 10. SSL via Let's Encrypt

```bash
certbot --nginx -d glowmathclass.com -d www.glowmathclass.com \
        --non-interactive --agree-tos -m admin@glowmathclass.com
# Auto-renew is installed via systemd timer (`certbot.timer`)
systemctl status certbot.timer
```

After certbot finishes, the Nginx config is automatically updated with the SSL block + HTTP→HTTPS redirect.

### 11. DNS (at domain registrar)

| Record | Type | Value | TTL |
|---|---|---|---|
| `glowmathclass.com` | A | `76.13.219.144` | 300 |
| `www.glowmathclass.com` | A | `76.13.219.144` | 300 |

Propagation typically takes 5–30 min. Verify with `dig glowmathclass.com +short`.

---

## Post-deployment verification

- [ ] `https://glowmathclass.com` loads the student login page
- [ ] SSL certificate is valid (lock icon, no browser warning)
- [ ] All 3 portal logins work (`/`, `/guru/login/`, `/admin/login/`)
- [ ] Static files load (CSS, Tabler icons, images)
- [ ] No 500 errors in `/var/log/nginx/error.log` after 10 min of activity
- [ ] `journalctl -u glowmath -n 200` shows no Python tracebacks
- [ ] `python manage.py smoke_test` returns all 200s (run on the server via venv)
- [ ] Forgot password sends an email (test the SMTP path)
- [ ] Teacher photo upload works (`/media/` writable)
- [ ] HTTP redirects to HTTPS
- [ ] `https://www.glowmathclass.com` redirects/serves correctly

---

## Rollback plan

If a deploy goes bad:

```bash
ssh root@76.13.219.144
cd /var/www/glowmathcourse
git log --oneline -10         # find last known-good commit
sudo -u glowmath git reset --hard <commit-sha>
sudo -u glowmath venv/bin/python manage.py migrate    # if migrations were rolled back
systemctl restart glowmath
```

For a more catastrophic rollback (DB schema drift), restore the latest backup:

```bash
sudo -u glowmath venv/bin/python manage.py backup_database --restore <backup-file>
```

(The `backup_database` command lives at `activity_logs/management/commands/backup_database.py`.)

---

## Monitoring (future hardening)

| Tool | Purpose | Priority |
|---|---|---|
| Sentry | Error tracking + tracebacks | high — wire after first user reports |
| UptimeRobot or Better Uptime | Downtime alerts (free tier) | high |
| Postgres `pg_stat_statements` | Slow query identification | medium |
| Nginx access log analysis (GoAccess) | Traffic patterns | low |

Sentry stub for `production.py`:

```python
# Uncomment after creating Sentry project
# import sentry_sdk
# from sentry_sdk.integrations.django import DjangoIntegration
# sentry_sdk.init(
#     dsn=os.environ['SENTRY_DSN'],
#     integrations=[DjangoIntegration()],
#     traces_sample_rate=0.1,
# )
```

---

## Caveats / open questions for Phase 4

- **Email provider** — Hostinger includes SMTP but rate limits may bite. Consider Mailgun free tier (5k/mo) as a backup.
- **Backup strategy** — `backup_database` dumps to local disk. For prod we'd want either pg_dump cron + offsite S3, or Hostinger's built-in snapshots.
- **Worker count** — 3 workers is a starting point for a 1-vCPU VPS; benchmark after launch and tune.
- **Redis** — not needed for current cache load (single-worker LocMem suffices), but enable if we move to multi-worker async (channels) for notifications.
- **CDN** — static asset CDN (Cloudflare free tier) is optional for the initial launch but trivial to add later — just point CNAME via Cloudflare.
- **DEBUG=True risk** — `config/settings/production.py` must explicitly set `DEBUG=False`. Don't rely on `.env` for this critical flag.
