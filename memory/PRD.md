# BoloDB — Landing Page & Onboarding Optimization PRD

## Original Problem Statement
> "Check landing page and user onboarding - we need to optimise it the extent we can - codewise, ui/ux wise and fix all bugs"

User confirmed: **Focus on all areas** — code optimization, UI/UX improvements, bug fixes, performance, and accessibility.

## Architecture Overview
- **Frontend**: SvelteKit 2.69 (Svelte 5 with runes) + Tailwind CSS + GSAP + Lenis (smooth scroll)
- **Backend**: FastAPI (Python 3.11) + SQLAlchemy + Alembic + PostgreSQL (for app state)
- **AI**: Google Gemini API (gemini-2.5-flash / flash-lite / pro)
- **Auth**: JWT (email/password) + Supabase Google OAuth (optional)
- **Analytics**: PostHog
- **Deployment**: Docker Compose (backend on 4321, frontend on 5173, nginx on 80)

## User Personas
1. **Non-technical business user** — wants insights from database without writing SQL
2. **Data analyst** — wants faster iteration on ad-hoc queries with verification safety net
3. **Developer** — evaluating self-hostable text-to-SQL solution

## Core User Journey
1. **Landing** (`/`) → Marketing site with hero, live demo, pipeline, trust engine, integrations
2. **Signup** (`/signup`) → Email/password (with strength validation)
3. **Login** (`/login`) → Email/password + Google OAuth
4. **Connect** (`/connect`) → Add Gemini API key → Connect DB (or use sample)
5. **Onboard** (`/onboard`) → 3-step wizard: Profile → Glossary → Starters
6. **Chat** (`/chat`) → Main text-to-SQL interface

## What's Been Implemented (Jan 2026)

### Bug Fixes
- ✅ Fixed missing `limits` module dependency (installed)
- ✅ Fixed missing `mako` module dependency (installed)
- ✅ Fixed supervisor config: switched to `uvicorn --factory backend.app.server:create_app` from `/app` directory
- ✅ Configured `SKIP_DB_LOCK=true` for preview environment (no PostgreSQL) + dev `JWT_SECRET`
- ✅ Removed dead code (`structuredData` duplicate JSON in marketing layout, unused `before` variable in nav)

### UI/UX Improvements
- ✅ **Password visibility toggle** on Signup & Login (eye icon, aria-label, data-testid)
- ✅ **Real-time password strength validation** with green checkmarks (already existed, now more polished)
- ✅ **Mobile-responsive Connect grid** (grid collapses to single column below 780px)
- ✅ **Mobile-responsive marketing nav** (nav button sizing scaled at <420px)
- ✅ **Trust-strip mobile fix** — DB logos gap/font-size tightened at <420px to prevent wrap
- ✅ **Improved hero animation** — safety timeout reduced from 2000ms to 1500ms
- ✅ **Login page height fix** — changed `height:100vh` to `min-height:100vh` (works better on mobile)
- ✅ **Skip-to-main-content link** for keyboard navigation (visible on focus)
- ✅ **Autocomplete hints** on all form inputs (email, current-password, new-password)

### Accessibility
- ✅ `role="alert"` + `aria-live="polite"` on all error messages (login, signup, connect, Google sign-in)
- ✅ `role="status"` on signup success message
- ✅ `role="progressbar"` on Onboard stepper (with aria-valuenow, aria-valuemax, aria-valuetext)
- ✅ `aria-pressed` on DB type selector buttons
- ✅ `aria-label` on Google sign-in button
- ✅ Skip-to-content link with proper focus state

### Code Quality
- ✅ **Data-testids everywhere** — comprehensive coverage on all interactive elements for testing:
  - Marketing: `nav-theme-toggle`, `nav-login-button`, `nav-signup-button`, `hero-start-free-button`, `hero-demo-button`, `final-cta-start-button`, `final-cta-sample-button`
  - Auth: `signup-card`, `signup-form`, `signup-email-input`, `signup-password-input`, `toggle-password-visibility`, `signup-submit-button`, `signup-signin-link`, `signup-error-message`, `signup-success-message`, `login-card`, `login-form`, `login-email-input`, `login-password-input`, `login-submit-button`, `login-signup-link`, `login-error-message`, `google-signin-button`, `google-signin-error`
  - Connect: `db-type-selector`, `db-type-{id}` (per DB), `gemini-api-key-input`, `save-gemini-key-button`, `connect-database-button`, `connect-sample-database-button`, `connect-error-message`
  - Onboard: `onboard-stepper`, `stepper-item-{step}`, `profile-continue-button`, `glossary-continue-button`, `starters-finish-button`
- ✅ **Theme-adaptive error styles** — replaced hardcoded hex colors (#FFF8ED, #F5D78A, #7A5C0A) with `var(--c-low-tint)`, `var(--c-low-ink)` tokens so errors match dark/light/soft themes

### Performance
- ✅ Hero animation safety timeout reduced by 25% (2000ms → 1500ms) for snappier fallback
- ✅ Removed 88-line duplicate JSON block in marketing layout (dead code)

## Testing Results (iteration 1)
- **Frontend**: 100% (16/16 checkpoints passed)
- **Backend**: N/A (frontend-only test per request; backend running degraded due to no PostgreSQL in preview env — expected)
- All landing page CTAs, nav, signup/login flows, password toggle, theme toggle, cross-navigation, skip link, ARIA labels, and mobile responsiveness verified working

## Prioritized Backlog

### P0 (Blocking)
- None — all optimization checkpoints pass

### P1 (Nice to have)
- [ ] Move large inline styles in Signup/Login to scoped CSS classes (readability/reuse)
- [ ] Add rate limiting to `/api/auth/signup` and `/api/auth/login` at server level (slowapi already available)
- [ ] Add "Forgot password?" link on login page
- [ ] Add email verification flow (send OTP or magic link) — currently signup is immediate

### P2 (Future enhancements)
- [ ] Add A/B testing framework for hero variants (PostHog feature flags already available)
- [ ] Add exit-intent modal on landing to boost conversion
- [ ] Add product tour overlay on first-time chat visit (Shepherd.js or driver.js)
- [ ] Add analytics dashboard for conversion funnel (Landing → Signup → Connect → First query)
- [ ] Preload the /login page from marketing hero CTAs (`data-sveltekit-preload-data="hover"` is set globally)

## Next Action Items
1. **User to review**: Try the app end-to-end (signup with a fresh email → connect sample DB → onboarding flow → ask first question)
2. **User to configure**: Add real Gemini API key when ready (get free from https://aistudio.google.com/app/api-keys)
3. **Optional**: Set up Supabase for Google OAuth (add SUPABASE_URL/ANON_KEY/JWT_SECRET to backend env)
4. **Optional**: Set up PostgreSQL for full app functionality (currently degraded in this preview)

## Environment Notes
- Backend runs on port 8001 via supervisor (uvicorn `--factory backend.app.server:create_app`)
- Frontend runs on port 3000 via supervisor (`yarn dev --host 0.0.0.0 --port 3000`)
- Frontend proxies `/api/*` to backend via Vite proxy (configured in `vite.config.ts`)
- PostgreSQL is NOT running in this preview env → `/api/health` returns `degraded` (expected)
- `SKIP_DB_LOCK=true` set so app starts without running alembic migrations
