# Testing Guide — GlowMath Course

> **Last updated:** 2026-05-28. Manual QA strategy + the small set of automated commands that exist. Reference [TEST_USERS.md](TEST_USERS.md) for accounts.

---

## Quick commands

```bash
# Django system check (model/template/URL validation) — should always pass
python manage.py check

# Run any defined unit tests (most apps have empty tests.py at the moment)
python manage.py test

# Smoke test — hits every named URL as each role and checks status codes
python manage.py smoke_test

# Concurrent enrollment stress test (race-safety regression)
python manage.py stress_test_enroll --threads 20 --capacity 3 --level SD
```

### What `smoke_test` actually does

`accounts/management/commands/smoke_test.py` iterates over ~30 URL names per role (student / teacher / admin), reverses each, logs in as the matching test user, hits the URL, and asserts the expected status. **No CLI flags.** Run after any URLconf or auth change to catch regressions.

### What `stress_test_enroll` does

`enrollments/management/commands/stress_test_enroll.py` spawns N threads that all try to enroll in the same Kelas with capacity C. Verifies `select_for_update` + capacity guard hold: exactly `C` enrollments succeed, the rest fail cleanly with no over-enrollment.

| Flag | Default | Notes |
|---|---|---|
| `--threads N` | 20 | parallel enrollment attempts |
| `--capacity N` | 3 | target Kelas capacity to test against |
| `--level LEVEL` | SD | jenjang to test (TK/SD/SMP/SMA/UMUM) |

Expected output: `Enrolled: 3 / Refused: 17 / Capacity overflow: 0` (with default args).

### What `python manage.py test` does

Runs Django's test runner against any `TestCase` subclasses in `<app>/tests.py`. **Most apps currently have a stub `tests.py` with no tests defined** — `test` will return "Ran 0 tests" until we add coverage. This is a Phase 4+ priority.

---

## Manual QA strategy

### Per-phase QA pass

After each phase completion, run a structured full pass:

1. **Login round-trip** — log in as each test user (Rafael / Trista / GlowMath), confirm role-appropriate redirect to `/dashboard/<role>/`
2. **Sidebar click-through** — click every sidebar item, confirm no 404
3. **Page-by-page** — for each NEW page redesigned in this phase, verify visually against the approved mockup
4. **Form submission** — submit valid AND invalid data on every form; confirm error states render
5. **Responsive check** — iPhone SE (375 px), iPad (768 px), desktop ≥ 1024 px
6. **Regression sweep** — open one page from each prior phase to confirm no styling regression

### Test matrix per page (template)

| Page | Viewport | Role | What to check |
|---|---|---|---|
| Dashboard | Desktop + Mobile | Student / Teacher / Admin | All sections render; widgets non-empty |
| Browse Classes | Desktop | Student | Filter chips work, pagination, card hover lift |
| Class Detail | Mobile | Student | Sticky bottom CTA visible; no clipped content |
| Rate Teacher | Desktop | Student | Star interactivity, validation, atomic submission |
| My Class Detail | Both | Student | KPI cards, amber rate banner if COMPLETED+unrated |
| Pengumuman | Both | Student | Hero + filter chips + pinned section + card grid |
| Profile | Both | Student | Cyan hero + edit form; POST persists |
| Logout modal | Desktop | Student | Modal opens, Escape closes, backdrop closes, "Ya, Logout" POSTs to `/logout/` |

---

## Browser testing targets

| Browser | Priority | Notes |
|---|---|---|
| Chrome | **primary** | dev baseline |
| Firefox | secondary | check Tailwind `:has()` support (FF 121+) |
| Safari (Mac + iPhone) | required | most likely real student device on iPhone |
| Edge | nice-to-have | older Indonesian school office machines |

---

## Mobile testing

| Device | Viewport | Status |
|---|---|---|
| iPhone SE (2nd gen) | 375 × 667 | Required pass — smallest realistic target |
| iPhone 14 | 390 × 844 | Required pass |
| iPad | 768 × 1024 | Should pass |
| Galaxy S20 | 360 × 800 | Should pass |
| Desktop 1024 | 1024 × 768 | Required pass |
| Desktop 1440 | 1440 × 900 | Required pass |

Use Chrome DevTools Device Mode for quick checks. For real-device testing, use a phone on the same Wi-Fi as the dev machine and hit `http://<dev-machine-LAN-IP>:8765/` after adding the LAN IP to `ALLOWED_HOSTS`.

---

## Stress test scenarios

### Concurrent enrollment race

```bash
python manage.py stress_test_enroll --threads 20 --capacity 3
```

Expected output:
```
Enrolled: 3
Refused: 17
Capacity overflow: 0
Elapsed: ~80–150 ms
```

If "Capacity overflow > 0" the `select_for_update()` + recount-inside-transaction guard has regressed. See [PITFALLS.md](PITFALLS.md#-race-condition-on-enrollment-capacity).

### Database load

Manual scenario:
1. Run `populate_full_demo --reset` (~30s)
2. Optionally seed extra: in `manage.py shell`, loop-create 1000+ Enrollment rows
3. Visit `/my-classes/` as Rafael → should load in < 200 ms
4. Use Django Debug Toolbar (dev only) to count queries — target ≤ 5 queries on the list view (rest should be select_related / prefetch_related batched)

---

## Common test flows

### Login flow

1. Open `http://localhost:8765/`
2. Enter `rafaeladhikabagasalfathan` / `ikanbuvivid`
3. Submit → redirect to `/dashboard/student/`
4. Sidebar shows 11 student items (Khan Playful teal)

### Rate Teacher flow

1. Login as Rafael
2. Navigate to `/my-classes/`
3. Find COMPLETED unrated card (has pulsing orange `⭐ Beri Rating` badge)
4. Click → `/my-classes/<id>/`
5. See amber gradient banner at top
6. Click banner → `/rate/<enrollment_id>/`
7. Select 4 stars for teacher + 5 for class
8. Add optional comments (≥20 chars or empty)
9. Submit
10. Verify: redirect to `/my-classes/<id>/`; banner gone; "Sudah Beri Rating" shown in Aksi Cepat panel
11. Verify: sidebar count widget (if any) decrements

### Enrollment race flow (manual variant)

1. In Django admin, set a Kelas to `capacity=3` and `status=OPEN`
2. Open 4 incognito browser windows, log into each as a different `student00X` user (same `level` as the Kelas)
3. Navigate all 4 to the class detail page
4. Click "DAFTAR" within a 1-second window across all 4 tabs
5. Verify: 3 succeed (see "Enrollment berhasil" success); 4th sees "Kelas penuh" error
6. Check the DB: `Enrollment.objects.filter(kelas=k, status='ACTIVE').count() == 3`

### Logout modal flow

1. Login as student
2. Click `🚪 Logout` in sidebar bottom
3. Modal appears with red gradient circle + 🚪 emoji + "Yakin mau keluar?"
4. Test **Batal** → modal closes, still logged in
5. Test backdrop click → modal closes
6. Test Escape key → modal closes
7. Test **Ya, Logout** → POST `/logout/` → redirect to `/` (login page)

---

## Pre-commit checklist

- [ ] `python manage.py check` — 0 errors, 0 silenced
- [ ] `python manage.py runserver 8765` — starts cleanly, no import errors
- [ ] Manual QA on every page changed in this commit
- [ ] Browser console (F12) — no JS errors, no failed network requests
- [ ] Mobile (iPhone SE 375 px) — no horizontal scroll, no clipped CTAs
- [ ] If changed a Khan Playful page → compare against approved mockup
- [ ] If changed a URLconf → run `smoke_test`
- [ ] If changed enrollment logic → run `stress_test_enroll`

---

## Bug report format

When opening an issue or logging a bug to fix later:

```
PAGE: /classes/<id>/
ROLE: Student (rafaeladhikabagasalfathan)
VIEWPORT: iPhone SE (375 × 667)
BROWSER: Chrome 131.0.6778
STEP TO REPRODUCE:
1. Login as Rafael
2. Navigate to /classes/40/
3. Scroll to "Daftar Pertemuan" section
4. Click "Lihat selengkapnya"
EXPECTED: Modal opens with full session list
ACTUAL: Page reloads from top, no modal
SCREENSHOT: <paste>
CONSOLE: TypeError: Alpine is not defined
```

The CLAUDE.md format guidance applies: lead with WHAT broke and HOW to reproduce, not WHY you think it broke.

---

## What's NOT tested today (gaps)

- **Unit tests** — `<app>/tests.py` files are stubs. Adding pytest + factory-boy + ≥80% coverage is a Phase 4+ target.
- **Integration tests** — `smoke_test` is the only integration coverage; no Selenium / Playwright.
- **Visual regression** — no automated screenshot diffing. Mockup comparison is manual.
- **Performance** — no Lighthouse runs in CI. Manual DevTools profiling only.
- **Accessibility (a11y)** — no automated WAVE/axe scans. Manual keyboard nav + reduced-motion checks done.
- **Security** — no SAST tooling (Bandit / Semgrep). `django-axes` brute-force protection not yet wired.
