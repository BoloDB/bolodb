# Landing Page Redesign — Design & Build Plan

> **Status:** Plan only. This document is the brief for the engineers who will
> build the redesign. It specifies *what* to build, *how* it should move, and
> *how we'll know it's done*. It does not change any product code.
>
> **Target quality bar:** Awwwards / CSSDA "Site of the Day" level polish —
> restrained, fast, and tactile. Motion serves comprehension of the product
> (plain-English → trusted answer), never decoration for its own sake.

---

## 1. Goals & non-goals

### What "next level" means here
1. **Tells the story in one scroll.** A non-technical visitor understands
   *what BoloDB does* and *why they can trust it* before they reach the footer.
2. **Feels alive and precise.** Scroll-choreographed reveals, magnetic/tactile
   micro-interactions, and one or two genuine "wow" moments — all at 60fps.
3. **Production-ready.** Ships prerendered, accessible (WCAG 2.2 AA), respects
   `prefers-reduced-motion`, hits our performance budgets, and works in all
   three themes (`dark` default, `crisp`, `soft`).

### Success criteria (measurable)
| Metric | Target |
|---|---|
| Lighthouse Performance (mobile, throttled) | ≥ 90 |
| Largest Contentful Paint (LCP) | < 2.5s |
| Cumulative Layout Shift (CLS) | < 0.05 |
| Interaction to Next Paint (INP) | < 200ms |
| Total blocking from animation JS (parsed, gzipped) | < 45 KB |
| Sustained frame rate during scroll/hover | 60fps (no long tasks > 50ms) |
| `prefers-reduced-motion: reduce` | Fully usable, zero non-essential motion |
| Signup CTA click-through (PostHog, vs. current) | Instrument & compare |

### Non-goals
- No redesign of the authenticated app (chat / dashboard / onboard). Reuse the
  existing design tokens so the marketing page and app feel like one product.
- No new brand identity. We keep the BoloDB logo, palette, and voice.
- No heavy 3D/WebGL. If a "wow" moment needs it, it must be optional and
  lazy-loaded (see §6). Default experience is DOM + SVG + CSS + GSAP.

---

## 2. Message architecture (drives the whole layout)

The page is a narrative. Each section answers the visitor's next question.

| # | Visitor's question | Section | One-line payload |
|---|---|---|---|
| 1 | "What is this?" | **Hero** | Talk to your database like a human. |
| 2 | "Show me." | **Live demo** | Question → SQL → answer, with confidence. |
| 3 | "How does it work?" | **The pipeline** | Connect → Ask → Verify → Trust. |
| 4 | "Why should I trust an AI with my data?" | **Trust engine** | See every query, data stays yours, read-only. |
| 5 | "Does it actually get smarter?" | **The flywheel** | Every verified answer teaches your database. |
| 6 | "What can it connect to?" | **Integrations** | Postgres, MySQL, SQL Server, SQLite. |
| 7 | "Convince me / who's it for." | **Social proof / outcomes** | Roles + before/after. |
| 8 | "How do I start?" | **Final CTA** | Start free with a OpenRouter key in ~1 min. |

Copy is owned by product; engineers should use the placeholder copy in §4 and
leave `<!-- COPY -->` markers so it's swappable without touching layout.

---

## 3. Art direction & reference (the bar, not to copy)

**Direction: "Living light, calm confidence."** Dark-first (BoloDB's default
theme), premium, and *alive* — a generative gradient/aurora atmosphere breathing
behind crisp typography and glass surfaces, with cinematic but restrained motion.
This is richer than a flat Linear look: the background itself is a signature.

**Reference board** (stakeholder-loved; borrow the intent, not the layout):

| Reference | What we take |
|---|---|
| **Reflect** — reflect.app | The living, iridescent **gradient/aurora** hero atmosphere; dark, premium, typographic calm. |
| **Zajno** — motion.zajno.com | **Motion-as-narrative**: animation guides the eye and *unpacks* information; seamless section transitions; micro-interaction craft (WebGL/GSAP/GLSL). |
| **Hydra Design Labs** — hydradesignlabs.com | Cinematic, **design-first precision**; one or two bold hero moments; intentionality. |
| **Stryds** — stryds.com | **Vibrant gradients pulsing on dark**, rounded forms, energetic-yet-approachable; each section moves with purpose. |
| **Antigravity** — antigravity.google | A **generative, physics-inspired ambient background** effect as signature atmosphere. |
| **Stripe** | The gold standard for scroll-scrubbed diagrams that *explain a technical product to humans* (our pipeline, §4.3). |

**Palette move:** layer an **aurora accent gradient** — brand blue `#4da6ff` →
emerald `#62e0b0` → a restrained violet — over the existing dark tokens; in
`crisp`/`soft` the aurora cools to brand green (`#1b9e6b`). Confidence semantics
unchanged.

We borrow the *vocabulary*, not the layouts. BoloDB's differentiator is
**trust**, so the atmosphere sets the mood while our signature *content* moment
stays the trust/verification loop (§6) — never a generic gradient-hero template.

---

## 4. Section-by-section spec

> Layout uses the existing tokens in `frontend/src/routes/layout.css`
> (`--bg`, `--surface`, `--ink`, `--muted`, `--brand`, `--radius-*`,
> `--shadow-*`, `--ease`, `--spring`). **Do not hardcode colors.** The current
> feature icons use `bg-emerald-100` etc. — these break in dark mode and must be
> replaced with token-based tints (`var(--brand-tint)` + `var(--brand)`).

### 4.0 Global shell
- **Marketing navbar** (new, separate from the app `Navbar.svelte`): logo left;
  anchor links (Demo, How it works, Trust, Connect) center; theme toggle + "Log
  in" + primary "Start free" right. Sticky, `backdrop-filter: blur(12px)`,
  translucent `--surface`, 1px `--border-2` bottom. On scroll past hero, it
  condenses (height 72→60px, stronger shadow) via a single ScrollTrigger.
- **Backdrop — the living aurora atmosphere (signature).** This is the
  Reflect/Antigravity move. Build it in **two tiers** so quality scales with the
  device:
  - **Tier 1 (default, always ships):** a layered CSS/Canvas **aurora** — 2–3
    large iridescent gradient fields (blue→emerald→violet) that drift *very
    slowly* (30–40s, transform-only), parallax gently with scroll, over a subtle
    SVG grain/noise at ~3% (kills banding on dark). Cheap, universal.
  - **Tier 2 (progressive enhancement, behind decision D-3):** an optional
    **WebGL flow-field / gradient-shader** layer (e.g. OGL, a few KB) for the
    truly "alive" Antigravity feel. **Lazy-loaded, client-only,** and gated: only
    on capable, non-`save-data`, non-reduced-motion, sufficient-`deviceMemory`
    sessions; otherwise Tier 1 shows. Must pause off-screen and cap DPR.
  - All decorative: `aria-hidden`, `pointer-events: none`, never the LCP element,
    fully replaced by a static gradient under reduced-motion.
- **Smooth scroll:** Lenis (see §5). Anchor links use Lenis `scrollTo`.

### 4.1 Hero
- **Layout:** centered, max-width ~1120px. Eyebrow chip ("AI data analyst you
  can trust") → H1 → subhead → CTA row → trust strip (logos of supported DBs +
  "read-only • your data stays yours").
- **H1:** `Talk to your database` / `like a human.` — the second line in
  `--brand`. Fluid type: `clamp(2.5rem, 6vw, 4.75rem)`, `line-height: 1.05`,
  `letter-spacing: -0.02em`.
- **Primary CTA:** "Start for free" → `/signup`. **Secondary:** "Watch it work"
  → smooth-scrolls to the live demo (§4.2).
- **Motion:** masked line-by-line reveal of the H1 (SplitText), staggered rise
  of subhead/CTAs, trust strip fades last. **LCP guard:** the H1 is the LCP
  element — do **not** animate it from `opacity: 0`. Use a `clip-path`/mask
  wipe that keeps pixels painted, or render it visible and animate a `translateY`
  of ≤ 12px only. Measure LCP before/after.
- **Signature micro-interaction:** the primary CTA is **magnetic** (§6.2).

### 4.2 Live demo — "Ask your data" (the centerpiece)
Reimagine the current `setTimeout` demo (`+page.svelte:14-35`) into a robust,
looping, scroll-aware sequence. This is the single most important asset on the
page: it shows the product working.

- **Frame:** a browser/app chrome card (reuse the traffic-light header already
  there) sitting on a soft pedestal shadow, slight 3D tilt that responds to
  cursor (`rotateX/rotateY` ≤ 6°, springy, disabled on touch + reduced-motion).
- **Sequence (looping, GSAP timeline, not `setTimeout`):**
  1. A question **types in** (rotate through 3 real questions, e.g. "Top 3
     customers this month by revenue", "Which products are low on stock?",
     "Refunds vs last quarter").
  2. **"Thinking"** shimmer (reuse `.skel` / spinner tokens).
  3. **SQL writes itself** — monospace, with a caret; subtle line-by-line
     stagger. Keep the existing SQL styling.
  4. **Results table** rows **stagger up**; the **confidence pill** pops
     (`--spring`) to "High".
  5. Hold ~2.5s, cross-fade to the next question.
- **Scroll behavior:** the timeline **plays only while in view**
  (ScrollTrigger `onEnter`/`onLeave` pause), and the whole card does a
  scroll-scrub tilt/parallax as it enters. Pausing off-screen is a battery/CPU
  requirement, not a nicety.
- **Accessibility:** the demo is decorative narration of a real capability —
  wrap in `aria-hidden` and provide a concise text equivalent nearby, or expose
  a "Skip animation / see a static example" affordance.

### 4.3 The pipeline — "How it works" (scroll-scrubbed)
Four steps: **Connect → Ask → Verify → Trust** (mirrors README §"How it works").
- **Desktop:** a horizontal, scroll-scrubbed sequence. A progress "spine" (SVG
  path) draws itself (`strokeDashoffset`) as you scroll; each step card pins
  briefly, its icon/illustration animates, then releases. Think Stripe's
  scroll-diagrams.
- **Mobile:** degrade to a vertical stepper — each step reveals on enter, the
  connecting line draws between them. No pinning on mobile (pinning + touch is
  fragile; avoid).
- Reuse existing iconography language; each step gets a small purpose-built
  SVG micro-animation (e.g., "Connect" = plug snaps in, "Verify" = check draws).

### 4.4 Trust engine
The emotional core — this is why a non-technical buyer picks BoloDB.
- Three pillars (replace the current 3 feature cards, upgraded):
  1. **See every query.** Toggle reveals the exact SQL. Micro-interaction: a
     real toggle that flips a card face from answer → SQL (3D `rotateY` flip).
  2. **Your data stays yours.** Only schema + question leave; rows never do;
     queries run **read-only**. Micro-interaction: an animated diagram showing
     "schema out, rows stay home."
  3. **Confidence you can read.** High/Medium/Low from real signals. Reuse the
     `.conf` pill components; animate a gauge count-up.
- Cards use **cursor-aware spotlight** (radial highlight follows pointer) and a
  1px gradient border on hover (§6.3).

### 4.5 The flywheel — "It learns your database"
There's already a `Flywheel.svelte` — audit it for reuse.
- Concept: verified answers → higher confidence → trust level climbs
  (Supervised → Assisted → Trusted). A circular, looping motion diagram with a
  **count-up** on a "verified answers" number and a trust meter that fills.
- Motion: a continuous, slow rotation (respecting reduced-motion → static), with
  the trust meter animating on scroll-in.

### 4.6 Integrations / connect
- A quiet, confident row: Postgres, MySQL, SQL Server, SQLite logos (+ "any SQL
  database"). Optional slow marquee on mobile; static grid on desktop.
- Connection-string formats in a tabbed code block (reuse `SqlBlock` styling).

### 4.7 Final CTA
- Full-bleed gradient panel. Big headline ("Ask your first question in a
  minute."), the ~1-minute OpenRouter-key value prop, primary CTA → `/signup`,
  secondary "Try with sample data". Magnetic button again.
- Background: the mesh/orb system reprised, slightly more saturated.

### 4.8 Footer
- Upgrade the current one-line footer: product links, docs (`docs/`), GitHub,
  license, small logo, "No telemetry. No cloud sync." reassurance line.

---

## 5. Motion & interaction system

This is the section engineers should internalize before writing any animation.

### 5.1 Libraries (all free, MIT-friendly for our use)
| Lib | Purpose | Notes |
|---|---|---|
| **GSAP** (core) | Timelines, tweens, `quickTo` | As of 2025 **all** GSAP plugins are free (Webflow). No club license needed. |
| **ScrollTrigger** | Scroll-linked reveals, pin, scrub | GSAP plugin. |
| **SplitText** | Line/char masked text reveals | GSAP plugin (now free). Has built-in `revert()` — call it on cleanup. |
| **Lenis** | Smooth scroll | Pair with ScrollTrigger via `lenis.on('scroll', ScrollTrigger.update)` and drive Lenis from `gsap.ticker`. |
| **OGL** *(optional, D-3)* | Tier-2 WebGL aurora / flow-field background | ~5 KB gz, minimal WebGL. **Only** for the Tier-2 atmosphere (§4.0); lazy, gated, with a static fallback. Not required for launch. |

Do **not** add Framer Motion / Motion One / AOS as well — one motion stack.
Everything ships lazy-loaded and code-split (§7). Budget: < 45 KB gz for the
core motion stack; the optional WebGL layer is separately lazy-loaded and gated,
never on the critical path.

### 5.2 Motion principles (the house style)
1. **Transform & opacity only.** Never animate `width`, `top`, `box-shadow`,
   `filter` on scroll. Layout/paint kills the frame budget.
2. **One easing family.** Reuse the tokens already in `layout.css`:
   `--ease: cubic-bezier(0.22,0.61,0.36,1)` for entrances/UI,
   `--spring: cubic-bezier(0.34,1.56,0.64,1)` for playful pops (pills, magnetic
   snap-back). Mirror them in GSAP config (define a matching `CustomEase` or use
   `power3.out` / `back.out(1.4)`).
3. **Duration scale:** micro 120–180ms · small reveal 300–500ms · hero/section
   500–800ms · ambient loops 20–40s. Nothing on the critical path waits on a
   loop.
4. **Stagger, don't dump.** Reveal groups with 40–80ms stagger; cap total
   sequence at ~600ms so nothing feels slow.
5. **Enter once.** Content reveals fire once (`toggleActions: 'play none none
   none'`), don't re-trigger on scroll-up. Only ambient/looping elements repeat.
6. **In-view only.** Anything looping pauses when off-screen.

### 5.3 Reduced motion (non-negotiable)
- Read `window.matchMedia('(prefers-reduced-motion: reduce)')` once.
- When reduced: **no** SplitText reveals, tilt, magnetism, scrubbing, marquees,
  or ambient loops. Replace reveals with an instant (or ≤ 120ms opacity) state.
  Set all "final" states as the default in CSS so the page is fully correct with
  zero JS. Also honor it live (`addEventListener('change', …)`).
- ScrollTrigger + reduced motion: use `gsap.matchMedia()` to register the two
  worlds cleanly (`(prefers-reduced-motion: no-preference)` vs `reduce`).

### 5.4 Micro-interaction catalog (build these as reusable Svelte actions)
| Interaction | Where | Spec |
|---|---|---|
| **Magnetic button** | Primary CTAs | Pointer within ~80px pulls the label/bg toward cursor via `gsap.quickTo` (max ~10–14px), springs back on leave. Touch/reduced-motion → off. |
| **Cursor spotlight card** | Trust cards, feature cards | CSS var `--mx/--my` updated on `pointermove`; radial-gradient highlight + gradient border. Throttle with `quickTo`. |
| **3D tilt** | Demo card, flip cards | `rotateX/Y` ≤ 6°, `transform-style: preserve-3d`, spring return. |
| **Number count-up** | Flywheel, trust gauge | GSAP tween on a number, `Intl.NumberFormat`, fires on ScrollTrigger enter. `tabular-nums` already tokenized (`.tnum`). |
| **Masked text reveal** | H1, section headings | SplitText lines, `yPercent 100 → 0` behind `overflow:hidden` mask. |
| **Link underline wipe** | Nav + inline links | `scaleX 0→1` from left on hover, `--brand`. |
| **Scroll-draw path** | Pipeline spine, flywheel | `strokeDashoffset` scrubbed. |
| **Sticky navbar condense** | Global | Single ScrollTrigger toggling a class. |

Each is a `use:` action in `src/lib/actions/` so juniors compose, not copy.

---

## 6. Signature "wow" moments (pick 2–3 to ship; the rest are stretch)

Awwwards juries reward **one or two** memorable, on-brand moments — not ten.
Commit to 2–3 (decision D-2). Ranked by payoff-to-effort:

1. **The live demo (§4.2).** Highest priority. It *is* the product. Nail the
   choreography and it carries the page.
2. **The living aurora atmosphere (§4.0).** The reference-defining mood
   (Reflect/Antigravity). Tier 1 is cheap and universal; it makes the whole page
   feel premium and alive before any content animates.
3. **Magnetic CTA + tactile buttons.** Cheap, high perceived quality, everywhere.
4. **Scroll-scrubbed pipeline (§4.3).** The "explain it to humans" moment
   (Stripe/Zajno — motion that *unpacks* information). Medium effort; big
   comprehension payoff.
5. **Trust flip cards (§4.4.1).** Answer→SQL flip literally demonstrates the
   trust pitch. On-brand and delightful.
6. **(Stretch) WebGL flow-field atmosphere (Tier 2, §4.0)** and/or a **schema
   constellation** — a lightweight graph of tables/keys that links on scroll
   ("it knows your schema"). Both lazy-loaded, gated, off under reduced-motion.
   Do not block launch on either.

---

## 7. SvelteKit 5 implementation notes (read before coding)

### 7.1 Where the page lives & rendering
- The marketing page is `src/routes/+page.svelte`. **Prerender it.** Add
  `export const prerender = true;` in a `+page.ts` for `/` (and give it its own
  `+layout` group so it doesn't pull the app shell/PostHog init the way the
  current page calls `appState.init(false)`). Marketing route should be static,
  cache-friendly HTML — critical for LCP and SEO.
- Confirm the deploy adapter. `svelte.config.js` currently specifies **no**
  adapter (falls back to `adapter-auto`); `adapter-static` is installed. Decide
  and pin one; prerendering the marketing route works with either.

### 7.2 GSAP + Svelte 5 (runes) integration pattern
- Load GSAP **only on the client, only for this route**, dynamically so it never
  enters the SSR/prerender bundle:
  ```ts
  // src/lib/motion/gsap.ts  (client-only helper)
  export async function loadGsap() {
    const { gsap } = await import('gsap');
    const { ScrollTrigger } = await import('gsap/ScrollTrigger');
    gsap.registerPlugin(ScrollTrigger);
    return { gsap, ScrollTrigger };
  }
  ```
- Drive animations from `$effect` (runs client-side, gives a cleanup return):
  ```svelte
  <script lang="ts">
    let root: HTMLElement;
    $effect(() => {
      let ctx: any, cleanup = () => {};
      (async () => {
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        const { gsap } = await loadGsap();
        ctx = gsap.context(() => { /* timelines scoped to root */ }, root);
        cleanup = () => ctx?.revert();
      })();
      return () => cleanup();            // runs on unmount / re-run
    });
  </script>
  <section bind:this={root}> … </section>
  ```
  Use `gsap.context()`/`ctx.revert()` (or `gsap.matchMedia()`) for automatic
  cleanup — essential in SvelteKit's client-side nav so triggers don't leak
  between pages. Also call `ScrollTrigger.refresh()` after fonts load and after
  the demo card mounts (layout-affecting).
- Prefer reusable `use:` **actions** for the micro-interactions (§5.4); prefer
  `$effect` for section-level timelines.

### 7.3 Lenis
- Init once in the marketing `+layout`, destroy on unmount. Wire to GSAP ticker
  and `ScrollTrigger.update`. Provide a `data-lenis-prevent` escape hatch for any
  internally-scrolling element (e.g., the SQL block, code tabs).

### 7.4 Fonts & CLS
- Fonts are pulled from Google CDN in `app.html`. For LCP/CLS, **self-host**
  Hanken Grotesk + JetBrains Mono (subset, `woff2`, `font-display: swap`,
  `<link rel="preload">` the H1 weight). Removes a render-blocking third-party
  round-trip. `ScrollTrigger.refresh()` on `document.fonts.ready`.

### 7.5 Theme correctness
- Everything must look right in **dark** (default), **crisp**, **soft**. Replace
  all hardcoded Tailwind color utilities on the current page
  (`bg-emerald-100`, `text-emerald-600`, `bg-red-400`, `#fff` SQL text, etc.)
  with token equivalents. Test the theme toggle mid-scroll — no reflows, no
  broken contrast.

---

## 8. Accessibility & performance budgets

**Accessibility (WCAG 2.2 AA):**
- Full keyboard path through nav → CTAs → footer; visible focus (reuse
  `.focusable` ring token).
- All decorative motion/orbs/demos `aria-hidden`; provide text equivalents for
  the demo's meaning.
- Contrast ≥ 4.5:1 (text) / 3:1 (UI) in **all three themes** — verify, don't
  assume.
- `prefers-reduced-motion` fully handled (§5.3). Page must be 100% usable and
  correct with JavaScript disabled (prerendered HTML + CSS final states).
- Respect focus order; don't trap focus in the demo; pinned sections must not
  strand keyboard users.

**Performance budgets:**
- LCP < 2.5s, CLS < 0.05, INP < 200ms (§1 table).
- Animation JS < 45 KB gz, lazy-loaded, not blocking first paint.
- No layout thrash: transform/opacity only; `will-change` used sparingly and
  removed after.
- Images/illustrations: SVG where possible; any raster is `loading="lazy"`,
  correctly sized, AVIF/WebP.
- Test on a mid-tier Android (throttled 4×CPU) — the demo timeline must hold
  60fps and pause off-screen.

---

## 9. Component & file structure (suggested)

```
src/routes/
  (marketing)/                 # route group so marketing ≠ app shell
    +layout.svelte             # Lenis init, marketing nav, footer
    +layout.ts                 # export const prerender = true
    +page.svelte               # composes the sections below
src/lib/marketing/
  Hero.svelte
  LiveDemo.svelte              # refactor of the current inline demo
  Pipeline.svelte
  TrustEngine.svelte
  Flywheel.svelte              # audit existing src/lib/components/Flywheel.svelte for reuse
  Integrations.svelte
  FinalCta.svelte
  MarketingNav.svelte
  Footer.svelte
  Backdrop.svelte              # mesh gradient + orbs + grain
src/lib/actions/
  magnetic.ts                  # use:magnetic
  tilt.ts                      # use:tilt
  spotlight.ts                 # use:spotlight
  reveal.ts                    # use:reveal (ScrollTrigger entrance)
  countUp.ts                   # use:countUp
src/lib/motion/
  gsap.ts                      # lazy loader + plugin registration
  lenis.ts                     # smooth-scroll singleton
  motionPrefs.ts               # reduced-motion helper (matchMedia + store)
```
Reuse existing UI primitives (`Button`, `ConfidenceBadge`/`.conf`, `TrustMeter`,
`SqlBlock`, `Logo`, `.card`, `.chip`, `.skel`) instead of re-inventing them.

---

## 10. Phased delivery roadmap (for the build team)

Each phase is independently shippable and reviewable. Definition of Done (DoD)
includes: works in all 3 themes, reduced-motion correct, keyboard-accessible,
no console errors, meets the relevant perf budget.

- **Phase 0 — Foundations (0.5–1 day).**
  Marketing route group + prerender; self-host fonts; add motion helpers
  (`gsap.ts`, `lenis.ts`, `motionPrefs.ts`); Lenis wired to GSAP ticker.
  *DoD:* page prerenders, smooth scroll works, reduced-motion disables it.
- **Phase 1 — Structure & tokens (1–2 days).**
  Build all sections with **final CSS states, no motion yet**. Replace every
  hardcoded color with tokens. Responsive at 360 / 768 / 1024 / 1440.
  *DoD:* static page is beautiful and correct with JS off, in all themes.
- **Phase 2 — Micro-interactions (1–2 days).**
  Implement the `use:` actions (§5.4): magnetic, tilt, spotlight, reveal,
  countUp, underline wipe, navbar condense. *DoD:* every action degrades under
  reduced-motion/touch; 60fps.
- **Phase 3 — The live demo (2 days).**
  Refactor the demo into a GSAP timeline; question rotation; in-view pause;
  cursor tilt; text equivalent. *DoD:* loops cleanly, pauses off-screen, holds
  60fps on mid-tier mobile.
- **Phase 4 — Scroll choreography (2 days).**
  Hero masked reveal (with LCP guard), section reveals, scroll-scrubbed
  pipeline (desktop) + vertical stepper (mobile), flywheel count-up.
  *DoD:* no CLS from reveals; scrub is smooth; mobile degrades correctly.
- **Phase 5 — Polish, a11y & perf (1–2 days).**
  Lighthouse + axe pass, contrast audit ×3 themes, keyboard walk-through,
  `ScrollTrigger.refresh()` on fonts/resize, PostHog events on CTAs.
  *DoD:* all §1 budgets met; QA checklist (§11) green.
- **(Stretch) Phase 6 — Schema constellation** (§6.5), only if budget allows.

**Rough total:** ~8–11 focused engineering days for one strong front-end dev,
plus copy + any custom illustration/SVG from design.

---

## 11. QA checklist (gate for launch)

- [ ] LCP < 2.5s, CLS < 0.05, INP < 200ms on throttled mobile (field-realistic).
- [ ] Lighthouse Perf/A11y/Best-Practices/SEO ≥ 90 each.
- [ ] `prefers-reduced-motion: reduce` → no non-essential motion, page correct.
- [ ] JS disabled → prerendered page fully readable, all copy/CTAs present.
- [ ] All three themes: contrast, no broken colors, toggle works mid-scroll.
- [ ] Full keyboard traversal; visible focus everywhere; no focus traps.
- [ ] Screen-reader pass: decorative motion hidden, demo has text equivalent.
- [ ] No ScrollTrigger/Lenis leaks on client-side nav to app and back.
- [ ] 60fps during scroll + hover on a mid-tier Android and a 4-yr-old laptop.
- [ ] Breakpoints 360 / 390 / 768 / 1024 / 1440 / 1920 all clean.
- [ ] CTAs fire PostHog events; links go to `/signup`, sample-data, `/login`.
- [ ] Cross-browser: latest Chrome, Safari (incl. iOS), Firefox.

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Motion tanks performance on mobile | Transform/opacity only; in-view pause; hard 45 KB JS budget; test on real mid-tier device each phase. |
| Animations feel gratuitous → hurts conversion | Motion must aid comprehension; A/B the demo & CTA via PostHog; keep reduced-motion as a first-class, tested path. |
| ScrollTrigger/Lenis leaks across SvelteKit nav | `gsap.context()`/`matchMedia()` cleanup in `$effect` returns; destroy Lenis on unmount; QA the app↔marketing round-trip. |
| Hero reveal delays LCP | Never fade the LCP text from 0; mask/clip reveal or ≤12px translate; measure. |
| Third-party font round-trip | Self-host, subset, preload; `ScrollTrigger.refresh()` on `fonts.ready`. |
| Scope creep from "wow" moments | Ship 2–3 signature moments (§6); constellation is explicitly stretch. |
| Dark-mode-only design breaks crisp/soft | Token-only styling; theme audit is a DoD item every phase. |

---

## 13. Open questions for product/design (before Phase 1)

1. **Copy & claims:** final H1/subhead, and any social proof / customer logos we
   can legitimately show? (Placeholder copy is in §4.)
2. **Illustration budget:** do we get custom SVG for the pipeline steps &
   flywheel, or build from icon primitives?
3. **Sample data / "Try it" flow:** does "Watch it work" scroll to the demo, or
   deep-link into a live sandbox? Affects §4.1/§4.7.
4. **Analytics goals:** which CTA conversions are we optimizing? Confirms the
   PostHog events to instrument.
5. **Scope of signature moments:** confirm the 2–3 from §6 to commit to.

---

*Companion visual reference:* [`docs/landing-page-motion-spec.html`](./landing-page-motion-spec.html)
is a self-contained, dependency-free page — **open it in a browser** to *feel*
the target quality (living aurora background, magnetic buttons, spotlight cards,
easing tokens, masked reveals, and the looping query→answer demo), or **read its
source** for reference implementations of each interaction. The build specifies
the GSAP + Lenis equivalents to use in the real SvelteKit code.
