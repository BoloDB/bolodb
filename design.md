# BoloDB — Hallmark Design Audit

**Date:** 2026-07-16
**Branch:** hallmark-redesign

## Anti-Pattern Findings

| ID | Severity | Pattern | Status |
|---|---|---|---|
| C1 | Critical | AI-default nav (wordmark-left, links-centred, CTA-right) | Fixed — N5 floating pill |
| C2 | Critical | Centred hero layout | Fixed — asymmetric 2-column |
| C3 | Critical | Centred everything (eyebrows + centred text) | Fixed — eyebrows removed, FinalCta left-aligned |
| C4 | Critical | 3-column equal feature grid | Fixed — 2-col + hero card |
| C5 | Critical | AI-default footer (social icons, multi-column) | Fixed — Ft6 letter close |
| C6 | Critical | Fake browser chrome in demo | Fixed — minimal demo-top with badge |
| C7 | Critical | Token improvisation (raw hex in components) | Fixed — lifted to tokens |
| C8 | Critical | Invented metrics (128940) | Fixed — replaced with — placeholder |
| M3 | Major | Centred text in sections | Fixed — left-aligned where needed |
| M4 | Major | GSAP scroll animations (performance) | Fixed — removed from Pipeline, FinalCta, TrustEngine |
| M5 | Major | Eyebrow labels on every section | Fixed — removed all eyebrows |

## Changes Applied

### Commit 1: `fix(routing)`
- `connect/+page.svelte`: Shows "currently connected" banner with switch/disconnect options
- `chat/+page.svelte`: Shows "No database connected" empty state instead of blank flash
- `dashboard/+page.svelte`: Shows empty state with "Connect a database" CTA
- `onboard/+page.svelte`: Added loading state while checking connection
- `Navbar.svelte`: Conditionally shows "Switch DB" vs "Connect" based on `appState.dbInfo`

### Commit 2: `fix(nav)`
- `MarketingNav.svelte`: Full rewrite from full-width sticky nav to floating pill at bottom of viewport
- Pill appears after scrolling past hero (200px threshold)
- Frosted glass backdrop-filter, logo · divider · links · divider · actions
- Mobile: links hidden, full-width pill at bottom

### Commit 3: `fix(hero)`
- `Hero.svelte`: Replaced centred single-column with asymmetric 2-column grid (1.2fr + 0.8fr)
- Removed eyebrow label, removed `min-height: 90vh`, content-based height
- Mobile: collapses to centred single column at 768px

### Commit 4: `fix(components)`
- `TrustEngine.svelte`: Break 3-col equal grid → 2-col bottom + full-width hero card
- `LiveDemo.svelte`: Remove fake browser chrome, replace raw hex with tokens, remove eyebrow
- `Flywheel.svelte`: Replace invented metric 128940 with — placeholder, remove eyebrow

### Commit 5: `fix(footer)`
- `Footer.svelte`: Rewrite as Ft6 — brand left, links below, reassurance right
- `Pipeline.svelte`: Remove eyebrow, remove GSAP spine scroll animation
- `Integrations.svelte`: Remove eyebrow, remove use:reveal
- `FinalCta.svelte`: Left-align panel, remove GSAP scroll animation, remove magnetic action

### Commit 6: `fix(alembic)`
- Rename duplicate revision 0003 → 0004 for password_reset_tokens migration

### Commit 7: `fix: reduce card padding, add missing sampleSQL`
- Pipeline cards: 32px → 24px padding
- TrustEngine cards: 36px → 28px padding
- TrustEngine flip card: define sampleSQL (was undefined)

### Commit 8: `feat: add privacy and terms pages`
- Create `/privacy` and `/terms` routes with legal content
- Footer: add Privacy and Terms links
- Layout: add legal routes to hidden navbar paths

## Design Tokens

| Token | Value | Usage |
|---|---|---|
| `--brand` | `#1b9e6b` | Primary accent |
| `--bg` | `#eef1f0` | Page background |
| `--surface` | `#f6f8f7` | Card background |
| `--ink` | `#1a1d1c` | Primary text |
| `--muted` | `#5c6360` | Secondary text |
| `--faint` | `#8c918e` | Tertiary text |
| `--border` | `#d4dbd8` | Borders |
| `--radius-sm` | `8px` | Small radius |
| `--radius-md` | `12px` | Medium radius |
| `--radius-lg` | `16px` | Large radius |
| `--font-display` | `Hanken Grotesk` | Headings |
| `--font-mono` | `JetBrains Mono` | Code/labels |

## Marketing Page Architecture

```
MarketingLayout
├── MarketingNav (floating pill, bottom)
├── Hero (left-biased 2-col)
├── LiveDemo (minimal panel)
├── Pipeline (3-step cards)
├── TrustEngine (2-col + hero card)
├── Flywheel (diagram + stats)
├── Integrations (DB grid + connection strings)
├── FinalCta (left-aligned panel)
└── Footer (Ft6 letter close)
```

## Files Modified

- `frontend/src/lib/marketing/MarketingNav.svelte`
- `frontend/src/lib/marketing/Hero.svelte`
- `frontend/src/lib/marketing/LiveDemo.svelte`
- `frontend/src/lib/marketing/Pipeline.svelte`
- `frontend/src/lib/marketing/TrustEngine.svelte`
- `frontend/src/lib/marketing/Flywheel.svelte`
- `frontend/src/lib/marketing/Integrations.svelte`
- `frontend/src/lib/marketing/FinalCta.svelte`
- `frontend/src/lib/marketing/Footer.svelte`
- `frontend/src/routes/privacy/+page.svelte`
- `frontend/src/routes/terms/+page.svelte`
- `frontend/src/routes/connect/+page.svelte`
- `frontend/src/routes/chat/+page.svelte`
- `frontend/src/routes/dashboard/+page.svelte`
- `frontend/src/routes/onboard/+page.svelte`
- `frontend/src/lib/components/ui/Navbar.svelte`
- `backend/alembic/versions/0004_add_password_reset_tokens.py`
