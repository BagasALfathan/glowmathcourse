# Design System — GlowMath Course

> **Last reviewed:** 2026-05-29.
> Source of truth for colours, spacing, typography, components, and per-role visual style.

## Color Palette

### Primary (Teal, anchored on `#7fcacd`) — rebrand 2026-05-29

Single brand palette, applied uniformly across all roles (student / teacher / admin).
The previous emerald primary + per-page accents (cyan Profile, orange Pengumuman,
purple/pink KPI cards) have all been merged into this one teal family.

| Slot | Hex | Tailwind alias | Use |
|---|---|---|---|
| 50 | `#f0f9fa` | `bg-primary-50` | page bg, soft hover |
| 100 | `#e0f1f2` | `bg-primary-100` | badge bg, soft button, section bg |
| 200 | `#c2e4e6` | `border-primary-200` | border, divider, hover state |
| 300 | `#7fcacd` | `bg-primary-300` | BASE — hero accents, chips, decorations |
| 400 | `#5fb3b7` | `text-primary-400` | accent, icons, hover-fill |
| 500 | `#4a9499` | `bg-primary-500` | **primary button** (white text contrast ok) |
| 600 | `#4a9499` | `bg-primary-600` | alias of 500 — keeps existing `bg-primary-600` button styling working without per-template edits |
| 700 | `#3d7c80` | `hover:bg-primary-700` | button hover, text emphasis |
| 800 | `#326568` | `text-primary-800` | heading text, sidebar active |
| 900 | `#1f3d3f` | `text-primary-900` | darkest body text |

Rules:
- For primary buttons that need white text, use **500/600/700** — never 300 (contrast fails).
- Hero gradient: `from-[#a5dadc] via-[#7fcacd] to-[#4a9499]`
- Badge / chip bg → 100, text → 600/700
- Border → 200, hover border → 300

CSS variables are mirrored in `templates/base.html` `<style>` block:
`--primary-50` … `--primary-900` — usable in inline `style="..."` attributes.

### Semantic (orthogonal to brand — do not merge into teal)
- **Success:** `#16a34a` (green-600) — PRESENT, ACTIVE, COMPLETED, PAID. Kept distinct from
  brand teal so a teacher can tell "success status" apart from "brand accent".
- **Warning:** `#f59e0b` (amber-500) — IZIN, PENDING, UNPAID
- **Danger:** `#ef4444` (red-500) — ALPHA, REJECTED, OVERDUE, logout, delete
- **Info:** `#3b82f6` (blue-500) — notifications, hints

> **Migration note (2026-05-29 rebrand):** during the bulk emerald → primary swap,
> success status badges that used `bg-emerald-100 text-emerald-700` (e.g. "Aktif",
> "Hadir", "Selesai") were converted to `bg-primary-100 text-primary-700` and now
> render teal. A follow-up pass will restore these to `bg-green-100 text-green-700`
> per the semantic rule above. Flag any UX-confusing overlap encountered.

### Neutral
- Text Primary: `#111827` (gray-900)
- Text Body: `#374151` (gray-700)
- Text Muted: `#6b7280` (gray-500)
- Text Hint: `#9ca3af` (gray-400)
- Border: `#e5e7eb` (gray-200)
- BG Page (teacher / admin): `#f9fafb` (gray-50)
- BG Card: `#ffffff`

### Dark Theme (Admin login portal)
- BG: `#111827` (gray-900)
- Card: `#1f2937` (gray-800)
- Border: `#374151` (gray-700)
- Text: `#f9fafb` (gray-50)

## Levels (5 jenjang)

The project supports **5 education levels** in `StudentProfile.level`, `TeacherJenjang.level`, and `Kelas.level`:

| Code | UI label | Typical content |
|------|----------|-----------------|
| `TK` | TK | Pre-school / kindergarten |
| `SD` | SD | Sekolah Dasar (1–6) |
| `SMP` | SMP | Sekolah Menengah Pertama (7–9) |
| `SMA` | SMA | Sekolah Menengah Atas (10–12) |
| `UMUM` | Umum | University / professional / UTBK / TOEFL / IELTS / business English |

Pills in register wizards render all 5 in a 5-column grid (mobile) or row (desktop). A teacher's jenjang is stored as a `TeacherJenjang` row per level — not three booleans.

## Typography

- **Font:** Inter (or system default)
- **Case:** Sentence case always (never Title Case, never ALL CAPS for content)
- **Weights:** 400 (regular) + 500/600 (semibold for emphasis)
- **Sizes:** 10px, 11px, 12px, 13px, 14px, 16px, 18px, 20px, 22px, 24px

## Spacing & Layout

- **Border radius:** 8px (default), 10px (cards), 12px (large cards), 16px / 2xl (hero)
- **Border width:** 0.5px (subtle), 1px (visible), 2px (featured)
- **Padding card:** 16px (compact), 20px (default), 28–32px (spacious)
- **Card shadow:** subtle `0 4px 20px rgba(0,0,0,0.04)`; hover lift `0 6px 16px rgba(0,0,0,0.06)`

## Per-Role Visual Style

Since the 2026-05-29 rebrand all three roles share the **same** teal primary
palette. Role-specific differences are in **layout density and interaction
patterns**, not color.

### Student — Khan Academy playful
- Background: teal soft gradients (`#f0f9fa → #e0f1f2 → #c2e4e6`), decorative bubbles
- Cards: rounded-2xl, soft shadows
- Emoji-friendly headings ("Hai!", "Yuk", "📚 Kelas saya")
- Gradient buttons (teal primary gradient — see Hero pattern above)
- Hover: `card-hover-lift` (translateY(-2px) + shadow)
- Friendly Indonesian tone

### Teacher — Notion clean
- Background: `#f9fafb` (gray-50)
- Cards: white, 0.5px border, rounded-xl
- Whitespace heavy
- Role pill: "🎓 Portal Guru" in `bg-primary-100`
- Solid teal primary buttons (no gradients)
- Hover: `card-hover-border` (primary border on hover, no lift)
- Professional Indonesian tone

### Admin — Data Pro (planned)
- Background: white or subtle gray
- Dense metric cards in grids
- Tables with sortable columns
- Activity feed sidebar
- Tab navigation for sections
- Dark theme on admin login portal (security feel)

## Sidebar (collapse + mobile drawer)

- **Desktop (≥ 768px):**
  - `position: sticky; top: 0; height: 100vh`
  - Two widths: expanded 240px ↔ collapsed 64px
  - Toggle button in sidebar header (`ti-layout-sidebar-left-collapse` / `ti-layout-sidebar-left-expand`)
  - **localStorage-persisted** across page navigation (`localStorage.sidebar_collapsed`)
  - Collapsed state: icons only, `font-size:0` hides text, tooltip via CSS `::after attr(data-label)` on hover
- **Mobile (< 768px):**
  - `position: fixed; left: 0; transform: translateX(-100%)` — drawer pulled fully off-screen
  - Always full width (280px) when open — collapsed/icon-only mode is desktop-only
  - Hamburger `ti-menu-2` in navbar opens it; backdrop click or `ti-x` button closes
  - Tap a nav link → full page navigation → drawer naturally resets to closed on next page

## Animation patterns ([static/css/animations.css](static/css/animations.css))

| Use | Class / keyframe | Duration |
|-----|------------------|----------|
| Page load | `.animate-fade-in` / `glowFadeIn` | 0.2s ease-out |
| Card mount | `.animate-fade-up` / `glowFadeUp` | 0.3s ease-out |
| Wizard step (student playful) | `.animate-slide-right` / `glowSlideInRight` | 0.3s ease-out |
| Wizard step (teacher minimal) | `.animate-fade-in` (no slide) | 0.2s ease-out |
| Error feedback | `.animate-shake` / `glowShake` | 0.4s ease-in-out |
| Active step circle (student only) | `.step-circle-active` / `glowPulseGlow` | 1.5s loop |
| Inline button loading | `.spinner` (white) / `.spinner-dark` (primary teal `#4a9499`) | 0.6s linear loop |
| Submit success | `.animate-success-pop` / `glowSuccessPop` | 0.4s ease-out |
| Card hover (student) | `.card-hover-lift` — translateY(-2px) + shadow | 0.2s ease |
| Card hover (teacher / admin) | `.card-hover-border` — border-color → primary teal `#7fcacd` | 0.2s ease |
| Pill press | `.pill-press` — scale(0.96) on `:active` | 0.1s ease |
| Progress bar fill | `.progress-bar-anim` — width transition | 0.4s cubic-bezier |
| Pulse-ring (waiting) | inline `@keyframes pulse-ring` | 1.6s loop |

All animations honour `@media (prefers-reduced-motion: reduce)`.

## Components

### Buttons
- **Primary:** teal solid `#4a9499` (primary-500/600) → hover `#3d7c80` (primary-700). White text always — 300 fails contrast, never use it for buttons.
- **Primary gradient:** `linear-gradient(135deg, #4a9499 0%, #3d7c80 100%)` for student CTAs (register submit, "Daftar Sekarang"). Hero-tier gradient `from-[#a5dadc] via-[#7fcacd] to-[#4a9499]`.
- **Secondary:** white + 0.5px border (`#e5e7eb`)
- **Ghost:** transparent + hover bg
- **Danger:** red `#ef4444` (semantic — do NOT use teal for delete / logout / reject)
- **WhatsApp:** `#25d366` solid (gradient variant on student forgot-password)
- **Loading state:** `.btn-loading` (opacity 0.7, pointer-events: none, cursor: not-allowed)

### Cards
- **Standard:** white bg, 0.5px border, rounded-xl, padding 16-20px
- **Hover:** `.card-hover-lift` (student) OR `.card-hover-border` (teacher / admin → border-color `#7fcacd`)
- **Featured:** 2px border `#4a9499`, optional "Recommended" badge
- **Stat card:** number large (22px+), label 11–12px gray
- **Admin (.dp-card):** white bg, 1px border `#e2e8f0`, rounded-12px (Data Pro)

### Inputs
- Border 0.5px gray-200, rounded-lg
- Focus: primary border (`#7fcacd`) + 3px ring `rgba(127,202,205,0.18)`
- Padding 10-11px
- Optional leading icon (gray-400)
- **Error state** (`.input-error`): border `#ef4444`, bg `#fef2f2`, focus ring `rgba(239,68,68,0.15)`. Error message uses `.error-message` (slides in via `glowFadeUp`)

### Badges
- Pill shape rounded-full
- Light bg + dark text from same color family
- **Semantic status (do NOT recolor to teal):**
  - Aktif / Hadir / Selesai / Paid: `bg-green-100 text-green-700` (`#dcfce7` / `#15803d`)
  - Izin / Pending / Unpaid: `bg-amber-50 text-amber-700` (`#fffbeb` / `#b45309`)
  - Alpha / Rejected / Overdue: `bg-red-100 text-red-700` (`#fee2e2` / `#b91c1c`)
- **Brand pills (info / level / role):**
  - Level (TK / SD / SMP / SMA / UMUM): `bg-primary-100 text-primary-700` (`#e0f1f2` / `#326568`)
  - Generic info pill: same primary-100 / primary-700 family
- **Admin role pills:** Siswa = blue, Guru = teal (`#ccfbf1 / #115e59`), Admin = violet — distinct identities

### Icons
- **Tabler Icons** (loaded as webfont CDN — `@tabler/icons-webfont@3.5.0`)
- Outline only (never `-filled`)
- Sizes: 12px (badge), 14–16px (inline / button), 20px (sidebar), 24–32px (decorative)
- Color: inherit from parent

## Layout Patterns

### Login pages (standalone, no extends from base.html)
- Centered card, max-width 360–380px
- Full viewport bg
- Inline Tailwind config so they don't depend on the dashboard `base.html`

### Dashboard pages (extends base.html)
- Flex layout: `<aside class="sidebar"> + <main class="flex-1 min-w-0">`
- Sticky navbar with role-aware nav partial
- Stat grid at top, then sections
- Cards / lists / tables for content

### List pages (paginated)
- Filter bar (search + selects + date range)
- Card grid OR table view
- Pagination at bottom (preserves query string via `qs_preserve`)

## Mobile Responsive

- **Breakpoints:** sm 640px · md 768px · lg 1024px · xl 1280px
- **Sidebar:** drawer below 768px, sticky from 768px up
- **Stats:** stack on mobile (`flex-col`), row from 640px / 768px
- **Tables:** card view on mobile, table on desktop (e.g. Teacher Dashboard's "Kelas Saya")
- **Long labels:** `truncate` + `min-w-0` on flex children for proper ellipsis
