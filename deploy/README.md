# deploy/ — VPS deployment artifacts

> **Authoritative runbook lives in [../DEPLOYMENT.md](../DEPLOYMENT.md).**
> This directory ships the committable templates referenced from there:
>
> - [glowmath.service](glowmath.service) — Gunicorn systemd unit
> - [nginx-glowmathclass.com.conf](nginx-glowmathclass.com.conf) — Nginx site config
> - [../.env.example](../.env.example) — environment variables template (NEVER commit a populated `.env`)
>
> No secrets live in this directory or in `.env.example`. Verify with:
> `git check-ignore -v .env` → must report `.gitignore:2:.env  .env`

## Canonical paths used by these templates

| Concern | Path |
|---|---|
| App root | `/var/www/glowmathcourse` |
| Virtualenv | `/var/www/glowmathcourse/venv` |
| Env file | `/var/www/glowmathcourse/.env` (chmod 600, owner `glowmath:glowmath`) |
| Gunicorn socket | `/var/www/glowmathcourse/gunicorn.sock` |
| Static collected | `/var/www/glowmathcourse/staticfiles/` |
| Uploaded media | `/var/www/glowmathcourse/media/` |
| Logs | `/var/www/glowmathcourse/logs/django.log` + `journalctl -u glowmath` |
| Domain | `glowmathclass.com`, `www.glowmathclass.com` |
| Server IP | `76.13.219.144` (Hostinger KVM 1, Ubuntu 24.04) |
| App user | `glowmath` (system, member of `www-data` group) |

If you change any path above, search both files in this directory + `DEPLOYMENT.md` and update consistently — the templates assume these.

## Why the 25 MB nginx body limit

Course materials (`course_materials/models.py`) accept up to 20 MB per upload at the Django layer. `client_max_body_size 25M` gives nginx a small margin for multipart envelope overhead.  Lowering this below 25 MB will reject legitimate uploads with a 413 *before* they reach Django.

## Why a separate `/media/` location block

WhiteNoise (in `MIDDLEWARE`) serves `/static/` from Gunicorn but does **not** serve user-uploaded `/media/`. Without the explicit `location /media/` alias, every uploaded course material 404s in production.

## First-deploy sequence (cliff notes — full version in DEPLOYMENT.md)

1. DNS A-records for `glowmathclass.com` + `www` → `76.13.219.144` (confirm with `dig +short glowmathclass.com`)
2. System packages + firewall
3. PostgreSQL — create db + user + grant
4. Clone repo, venv, `pip install -r requirements.txt`
5. Write `/var/www/glowmathcourse/.env` (mode 600) — generate fresh `SECRET_KEY`, real DB password
6. `python manage.py migrate` (PostgreSQL — fresh schema) — **confirm before running, this is irreversible on a populated DB**
7. `python manage.py collectstatic --noinput`
8. `python manage.py createsuperuser`  (then optionally `create_test_users` for the named demo accounts)
9. Install systemd unit, `daemon-reload`, `enable --now glowmath`
10. Install nginx site, `nginx -t`, reload — **DO THIS BEFORE CERTBOT** (certbot needs port 80 working to solve the ACME challenge)
11. `certbot --nginx -d glowmathclass.com -d www.glowmathclass.com` — adds HTTPS block + HTTP→HTTPS redirect automatically
12. Smoke test — see DEPLOYMENT.md "Post-deployment verification" checklist
