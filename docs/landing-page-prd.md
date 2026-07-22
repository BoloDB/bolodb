# PRD — BoloDB Landing Page Redesign

| | |
|---|---|
| **Product** | BoloDB — "Ask your data. Trust the answer." |
| **Surface** | Public marketing landing page (`/`) |
| **Status** | Draft for review |
| **Author** | Design/Eng (this document) |
| **Version** | 0.1 |
| **Companion docs** | Build plan: [`docs/landing-page-redesign-plan.md`](./landing-page-redesign-plan.md) · Live motion spec: [`docs/landing-page-motion-spec.html`](./landing-page-motion-spec.html) (open in a browser) |
| **Related product docs** | [`docs/README.md`](./README.md), [`docs/01-what-is-bolodb.md`](./01-what-is-bolodb.md), [`docs/06-learning-trust-and-confidence.md`](./06-learning-trust-and-confidence.md) |

> This PRD defines **what** we're building and **why**, **who** it's for, how we
> prioritize, and how we'll measure success. The companion build plan defines
> **how** (architecture, motion system, component breakdown). Requirements here
> are labeled with IDs and MoSCoW priority so scope decisions are explicit.

---

## 1. Summary

Rebuild the BoloDB marketing landing page into a **premium, motion-forward
experience** that makes a non-technical visitor *feel* the product's core
promise — ask a question in plain English, watch trustworthy SQL and an answer
appear — within the first screen, and converts them to "Start for free."

The bar is Awwwards / CSSDA "Site of the Day": a **living, dark-first
atmosphere** (generative gradient/WebGL ambient background), **motion that
narrates** the product rather than decorates it, and tactile micro-interactions
— all while hitting strict performance and accessibility budgets and staying
correct across BoloDB's three existing themes.

---

## 2. Background & problem statement

**Today.** The current landing page (`frontend/src/routes/+page.svelte`) has the
right ingredients — a hero, a mock chat demo, three feature cards — but:

- The demo is a brittle `setTimeout` sequence that plays once and never loops,
  runs even when off-screen, and doesn't communicate the *trust* story.
- Feature icons use hardcoded light Tailwind colors (`bg-emerald-100`,
  `text-emerald-600`, …) that **break in the default dark theme**.
- There is **no motion system** — no scroll choreography, no micro-interactions,
  no ambient atmosphere. It reads as a competent template, not a product people
  screenshot and share.
- It doesn't visually differentiate BoloDB's actual moat: **verifiable trust**
  (see the SQL, confidence levels, read-only, data-stays-yours, learns from
  verified answers).

**Why now.** BoloDB's differentiator is emotional — *can I trust an AI with my
company's data?* A generic page can't carry that. Competitors in text-to-SQL are
proliferating; a distinctive, high-craft landing page is a cheap, durable edge
and directly feeds top-of-funnel conversion.

---

## 3. Goals, non-goals & success metrics

### 3.1 Business goals
- **G1 — Convert.** Increase landing→signup start rate and signup completion.
- **G2 — Communicate trust.** Visitors can articulate *why BoloDB is safe/trustworthy* (see SQL, read-only, data stays yours) after one visit.
- **G3 — Signal quality.** The page's craft makes BoloDB feel like a premium, modern product (brand halo; shareable; Awwwards-worthy).

### 3.2 User goals
- **U1** Understand what BoloDB does in < 10 seconds.
- **U2** See it actually work without signing up.
- **U3** Feel confident their data is safe before starting.
- **U4** Start in one obvious click; know setup takes ~1 minute.

### 3.3 Success metrics (KPIs)

> Baselines to be captured from the **existing** page via PostHog (already in the
> stack, `posthog-js`) before launch. Targets are relative to baseline.

| # | Metric | Instrumented via | Target |
|---|---|---|---|
| M1 | Landing → clicked a primary CTA ("Start for free") | PostHog event `lp_cta_click` | +25% vs. baseline |
| M2 | Landing → signup completed | Funnel `lp_view → signup_completed` | +15% vs. baseline |
| M3 | Demo engagement (viewed ≥1 full demo loop or interacted) | `lp_demo_viewed` / `lp_demo_interact` | ≥ 60% of sessions |
| M4 | Scroll depth to Trust section | `lp_section_view{trust}` | ≥ 55% of sessions |
| M5 | Median time-to-first-CTA-click | PostHog | ↓ vs. baseline |
| M6 | Bounce rate | PostHog | ↓ vs. baseline |
| M7 | Lighthouse Performance (mobile, throttled) | CI/Lighthouse | ≥ 90 |
| M8 | Core Web Vitals (LCP/CLS/INP) | Field + lab | LCP < 2.5s · CLS < 0.05 · INP < 200ms |

### 3.4 Non-goals
- No redesign of the authenticated app (chat / dashboard / onboard / connect).
- No new brand identity, logo, or product naming. We build on the existing
  token system in `frontend/src/routes/layout.css`.
- No pricing page, blog, or docs-site redesign (separate efforts). The landing
  page may *link* to docs and GitHub.
- No account/auth changes; CTAs route to existing `/signup`, `/login`, sample-data.
- No mandatory heavy 3D/WebGL. Generative ambient is an **enhancement with a
  static fallback** (see NFRs).

---

## 4. Target users & personas

BoloDB is text-to-SQL for **non-technical people**, self-hostable (Docker,
open-source, MIT) and available as a hosted signup. The page must speak to the
buyer *and* the technical evaluator.

| Persona | Who | What they need from the page | Primary? |
|---|---|---|---|
| **P1 — Priya, Ops/Founder (non-technical)** | Runs a business, lives in spreadsheets, waits on others for data pulls. | "Can *I* actually use this? Is my data safe? Show me." Plain-English proof, trust reassurance, 1-click start. | **Yes (primary)** |
| **P2 — Devin, technical evaluator** | Eng/analyst vetting tools for the team. | Read-only enforcement, schema-only-to-AI privacy, supported DBs, self-host/OSS, "how it works." | Secondary |
| **P3 — Maya, data-curious operator** | Marketing/finance/support power-user. | Speed, example questions, "does it learn my domain?" | Secondary |

**Accessibility persona (cross-cutting):** users with reduced-motion
preferences, keyboard-only navigation, and screen readers must get a fully
equivalent, comfortable experience (see NFRs).

---

## 5. Jobs-to-be-done / user stories

- **JTBD-1:** *When* I land on BoloDB, *I want to* instantly grasp what it does,
  *so I can* decide if it's worth my time. → Hero (§7.1)
- **JTBD-2:** *When* I'm skeptical an AI can query my DB correctly, *I want to*
  watch it turn a real question into SQL and a correct answer, *so I can* believe
  it. → Live demo (§7.2)
- **JTBD-3:** *When* I worry about data safety, *I want to* see exactly what
  leaves my database and that queries are read-only, *so I can* trust it. →
  Trust engine (§7.4)
- **JTBD-4:** *When* I wonder if it stays accurate, *I want to* understand it
  learns from answers I verify, *so I can* invest in it. → Flywheel (§7.5)
- **JTBD-5:** *When* I'm sold, *I want to* start immediately and know it's quick,
  *so I* don't stall. → CTAs everywhere + Final CTA (§7.7)
- **JTBD-6 (P2):** *When* evaluating for my team, *I want* the specifics
  (read-only, schema-only, DBs, OSS/self-host), *so I can* approve it. → Trust +
  Integrations + footer.

---

## 6. Experience principles & art direction

### 6.1 Experience principles
1. **Show, don't tell.** The product demoing itself beats any headline.
2. **Motion narrates.** Every animation earns its place by guiding attention or
   revealing meaning (per Zajno's motion philosophy) — never decoration.
3. **Trust is the feeling.** Calm, precise, transparent. Craft *is* the trust
   signal.
4. **Fast and inclusive by construction.** Premium never means heavy or
   exclusionary; reduced-motion and no-JS are first-class paths.

### 6.2 Art direction — "Living light, calm confidence"

Dark-first (BoloDB's default theme), premium, and **alive**: a generative
gradient/aurora atmosphere breathing behind crisp typography and glass surfaces,
with cinematic but restrained motion.

**Reference board** (what we take from each — the bar, not to copy):

| Reference | What we borrow |
|---|---|
| **Reflect** (reflect.app) | The living, iridescent **gradient/aurora** hero atmosphere; dark, premium, typographic calm. |
| **Zajno** (motion.zajno.com) | **Motion-as-narrative**: animation guides the eye and *unpacks* information; seamless section transitions; micro-interaction craft (WebGL/GSAP/GLSL). |
| **Hydra Design Labs** | Cinematic, **design-first precision**; one or two bold hero moments; intentionality. |
| **Stryds** | **Vibrant gradients pulsing on dark**, rounded forms, energetic-yet-approachable; each section moving with purpose. |
| **Antigravity** (Google) | A **generative, physics-inspired ambient background** effect as signature atmosphere. |

**What we deliberately avoid:** full-page WebGL everywhere that tanks
performance; motion that fights comprehension; abandoning light themes
(`crisp`/`soft` must stay first-class); anything that reads as a generic
gradient-hero template.

**Palette direction:** layer an **aurora accent gradient** — brand blue
`#4da6ff` → emerald `#62e0b0` → a restrained violet — over BoloDB's existing
dark tokens (`--bg #0a0a0a`, `--surface #141518`, `--ink #f0f0f0`). In light
themes the aurora cools to brand green (`#1b9e6b`) tints. Semantic confidence
colors (High/Med/Low) are reused unchanged from `layout.css`.

**Typography:** existing pairing — **Hanken Grotesk** (UI/display) + **JetBrains
Mono** (data/SQL/labels). Fluid display scale, tight tracking, `text-wrap:
balance` on headings.

---

## 7. Functional requirements

Priority: **M**ust / **S**hould / **C**ould / **W**on't (this release). Each
requirement has testable acceptance criteria (AC). Section order encodes the
narrative (§5). Motion behaviors are specified at requirement level here and in
implementation detail in the build plan.

### 7.0 Global shell
- **LP-F-00.1 (M) Marketing chrome.** A marketing-specific nav (separate from the
  app `Navbar.svelte`): logo, anchor links (Demo, How it works, Trust, Connect),
  theme toggle, "Log in", primary "Start free". Sticky, translucent blur;
  condenses on scroll past hero.
  *AC:* sticky; anchors smooth-scroll to sections; condense transition fires
  once; works in all 3 themes; keyboard-navigable.
- **LP-F-00.2 (M) Ambient background system.** A living gradient/aurora
  atmosphere behind content that slowly drifts and subtly parallaxes on scroll.
  *AC:* transform/opacity or GPU-shader only; `aria-hidden`; `pointer-events:
  none`; **static gradient fallback** when WebGL unavailable or reduced-motion;
  no impact on LCP element; ≤ agreed GPU/CPU budget (NFR-P).
- **LP-F-00.3 (M) Smooth scroll** with anchor integration; escape hatch for
  internally-scrolling elements (SQL/code blocks). *AC:* disabled under
  reduced-motion; no scroll-hijack that traps keyboard users.
- **LP-F-00.4 (M) Theme correctness.** Replace all hardcoded Tailwind colors on
  the current page with tokens. *AC:* no broken colors/contrast in dark/crisp/soft;
  toggling mid-scroll causes no layout shift.

### 7.1 Hero
- **LP-F-01.1 (M) Value proposition.** H1 "Talk to your database like a human.",
  subhead (plain-English, trust, instant), against the ambient atmosphere.
- **LP-F-01.2 (M) Primary + secondary CTA.** "Start for free" → `/signup`;
  "Watch it work" → smooth-scroll to demo.
- **LP-F-01.3 (S) Trust strip.** Supported-DB marks + "read-only • your data
  stays yours" reassurance below the fold-line.
- **LP-F-01.4 (S) Signature entrance.** Masked line-by-line headline reveal +
  staggered subhead/CTA rise on load.
  *AC (hero):* LCP element (H1) is **not** faded from opacity 0 (mask/clip or
  ≤12px translate only); measured LCP < 2.5s; primary CTA is magnetic on
  pointer devices, inert on touch/reduced-motion.

### 7.2 Live demo — "Ask your data" (centerpiece)
- **LP-F-02.1 (M) Looping question→answer sequence.** Rewritten as a robust
  timeline (not `setTimeout`): a real question types in → "thinking" → SQL writes
  itself → results table staggers in → **confidence pill pops to "High"** →
  holds → cross-fades to the next of ~3 rotating questions.
- **LP-F-02.2 (M) In-view only.** Timeline plays only while visible; pauses fully
  off-screen. *AC:* CPU/GPU idle when scrolled away (verify in devtools).
- **LP-F-02.3 (S) Cursor-reactive frame.** Subtle 3D tilt/parallax on the demo
  card (≤6°), off on touch/reduced-motion.
- **LP-F-02.4 (M) Accessible equivalent.** Animation `aria-hidden` with an
  always-present text equivalent, plus a visible "skip animation / see static
  example" control. *AC:* screen-reader users get the meaning; skip control works
  and is keyboard-operable.

### 7.3 The pipeline — "How it works"
- **LP-F-03.1 (M) Four steps:** Connect → Ask → Verify → Trust (mirrors README).
- **LP-F-03.2 (S) Desktop scroll choreography.** A progress "spine" draws itself;
  each step reveals its micro-illustration as it enters.
- **LP-F-03.3 (M) Mobile degrade.** Vertical stepper with reveal-on-enter and a
  drawn connector; **no pinning** on touch. *AC:* fully legible and non-janky on
  a mid-tier Android.

### 7.4 Trust engine
- **LP-F-04.1 (M) See every query.** A real toggle/flip revealing the exact SQL
  behind an answer (answer ⇄ SQL). Demonstrates transparency literally.
- **LP-F-04.2 (M) Your data stays yours.** Communicate that only schema + question
  reach the AI (never rows), queries run **read-only**. Supported by a small
  animated diagram. *AC:* claims match `docs/03` and README exactly; reviewed by
  product for accuracy.
- **LP-F-04.3 (M) Confidence you can read.** High/Medium/Low from real signals;
  reuse existing `.conf` pill components; optional gauge count-up.
- **LP-F-04.4 (S) Cursor-aware cards.** Spotlight highlight + gradient border on
  hover; degrade cleanly.

### 7.5 The flywheel — "It learns your database"
- **LP-F-05.1 (S) Learning loop.** Verified answers → higher confidence → trust
  level climbs (Supervised → Assisted → Trusted). Audit existing
  `Flywheel.svelte` for reuse.
- **LP-F-05.2 (C) Count-up + meter.** A "verified answers" count-up and a trust
  meter that fills on scroll-in; static under reduced-motion.

### 7.6 Integrations / connect
- **LP-F-06.1 (M) Supported databases.** Postgres, MySQL, SQL Server, SQLite (+
  "any SQL database"), presented confidently.
- **LP-F-06.2 (S) Connection formats.** Tabbed code block of connection-string
  formats (reuse `SqlBlock` styling), with a read-only-account safety tip.

### 7.7 Final CTA & footer
- **LP-F-07.1 (M) Closing CTA.** Full-bleed aurora panel: "Ask your first
  question in a minute.", the ~1-minute OpenRouter-key value prop, "Start for free" →
  `/signup`, secondary "Try with sample data".
- **LP-F-07.2 (M) Footer.** Product links, docs, GitHub (OSS), license,
  "No telemetry. No cloud sync." reassurance.

### 7.8 SEO & sharing
- **LP-F-08.1 (M)** Prerendered HTML, semantic headings, meta description,
  canonical, Open Graph/Twitter card image, favicon (existing).
  *AC:* valid OG preview; Lighthouse SEO ≥ 90; page readable with JS disabled.

---

## 8. Content requirements

- **CR-1 (M)** Final copy deck owned by product for: H1/subhead, section
  headings + body, 3 rotating demo questions (with realistic SQL + results),
  pipeline step copy, trust pillar copy, final CTA. Engineers scaffold with the
  placeholder copy in the build plan and leave swap markers.
- **CR-2 (M)** **Claims accuracy review.** Every privacy/security claim
  ("read-only", "only schema + question sent", "data stays yours", "no
  telemetry") must be verified against `docs/03-the-ai-layer-openrouter.md`,
  `docs/05-safety-validation-and-self-repair.md`, and README before launch.
- **CR-3 (S)** Any social proof (logos, quotes, numbers) must be real and
  approved, or omitted. No fabricated testimonials or metrics.
- **CR-4 (C)** Illustration/asset budget decision: custom SVG for pipeline &
  flywheel vs. built from existing icon primitives.

---

## 9. Non-functional requirements

### Performance (NFR-P)
- **NFR-P1 (M)** LCP < 2.5s, CLS < 0.05, INP < 200ms (throttled mobile).
- **NFR-P2 (M)** Lighthouse Perf/A11y/Best-Practices/SEO ≥ 90 each.
- **NFR-P3 (M)** Marketing route **prerendered**; animation/WebGL code
  **lazy-loaded**, client-only, code-split; total motion JS < 45 KB gz (excl. an
  optional WebGL layer, which must itself be lazy + gated + fallback).
- **NFR-P4 (M)** Animate transform/opacity (or shader uniforms) only; no layout
  thrash; sustained 60fps on a mid-tier Android and a ~4-year-old laptop.
- **NFR-P5 (M)** Ambient/looping effects **pause off-screen** and respect the
  device (disable heavy WebGL on low-power/`deviceMemory`/save-data signals).

### Accessibility (NFR-A) — target WCAG 2.2 AA
- **NFR-A1 (M)** Full keyboard path; visible focus (reuse `.focusable` ring);
  no focus traps; pinned sections never strand keyboard users.
- **NFR-A2 (M)** `prefers-reduced-motion: reduce` disables all non-essential
  motion (ambient, tilt, magnetism, scrub, marquees, reveals) and lands on
  correct final states; honored live on change.
- **NFR-A3 (M)** Contrast ≥ 4.5:1 text / 3:1 UI in **all three themes**.
- **NFR-A4 (M)** Decorative motion/canvas `aria-hidden`; the demo has a text
  equivalent; images have alt text.
- **NFR-A5 (M)** Page is fully usable/readable with **JavaScript disabled**
  (prerendered HTML + CSS final states).

### Compatibility (NFR-C)
- **NFR-C1 (M)** Latest Chrome, Safari (incl. iOS), Firefox; Edge.
- **NFR-C2 (M)** Responsive & clean at 360 / 390 / 768 / 1024 / 1440 / 1920.
- **NFR-C3 (S)** Graceful degradation where `backdrop-filter`/WebGL unsupported.

### Privacy & analytics (NFR-D)
- **NFR-D1 (M)** PostHog events per §10; no PII in event payloads; respect the
  product's privacy posture ("no telemetry" refers to the *app's* data handling —
  marketing-site analytics are standard but must be disclosed if a cookie/consent
  banner is required by jurisdiction — **decision D-6**).
- **NFR-D2 (M)** No third-party render-blocking calls on the critical path;
  self-host fonts (currently Google CDN) for LCP/CLS and privacy.

### Maintainability (NFR-M)
- **NFR-M1 (S)** Micro-interactions as reusable Svelte `use:` actions; sections
  as discrete components; a marketing route group separate from the app shell.
- **NFR-M2 (S)** Content swappable without touching layout/motion code.

---

## 10. Analytics & experimentation plan

**Events (PostHog `posthog-js`, already installed):**

| Event | Trigger | Key props |
|---|---|---|
| `lp_view` | Landing mount | theme, referrer, device |
| `lp_section_view` | Section enters viewport | `section` (hero/demo/pipeline/trust/flywheel/integrations/cta) |
| `lp_demo_viewed` | ≥1 full demo loop seen | `question_index` |
| `lp_demo_interact` | User tilts/skips/interacts with demo | `action` |
| `lp_cta_click` | Any CTA click | `location` (hero/nav/final), `label`, `destination` |
| `lp_theme_toggle` | Theme changed | `to_theme` |
| `lp_scroll_depth` | 25/50/75/100% thresholds | `depth` |

**Funnel:** `lp_view → lp_section_view{demo} → lp_cta_click → signup_completed`.

**Experiment ideas (post-launch, PostHog experiments):**
- **E1** Hero CTA copy ("Start for free" vs. "Ask your data — free").
- **E2** Demo autoplay vs. click-to-play on first view.
- **E3** Ambient WebGL atmosphere vs. static gradient (perf/conversion trade-off).

*(Baseline capture on the current page is a Phase-0 prerequisite so targets in
§3.3 are measurable.)*

---

## 11. Dependencies & assumptions

**Dependencies**
- Final copy deck & claims review (product) — blocks Phase 1 content.
- Any custom illustration/OG image (design) — CR-4.
- Confirmation of the deploy adapter/prerender path (`svelte.config.js` currently
  specifies no adapter → `adapter-auto`; `adapter-static` is installed).
- Motion libraries: GSAP (+ ScrollTrigger, SplitText — all free as of 2025) and
  Lenis; optional WebGL via a lightweight lib (e.g. OGL) **only if** the WebGL
  atmosphere is greenlit (D-3).

**Assumptions**
- Primary conversion is **hosted signup** (`/signup` exists), with self-host/OSS
  as a secondary path for P2 — **confirm (D-1)**.
- BoloDB brand/tokens are fixed; we style through `layout.css` variables.
- Existing components (`Button`, `ConfidenceBadge`/`.conf`, `TrustMeter`,
  `SqlBlock`, `Flywheel`, `Logo`) are reusable.

---

## 12. Release plan & milestones

Maps to the build plan's phases; each milestone is independently shippable and
carries the full DoD (all 3 themes · reduced-motion · keyboard · budgets).

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 — Foundations** | Marketing route group + prerender; self-host fonts; motion helpers; Lenis; **PostHog baseline capture** | Prerenders; smooth scroll; reduced-motion kill-switch; baseline KPIs recorded |
| **M1 — Structure & tokens** | All sections, final CSS states, token-only colors, responsive | Beautiful & correct with JS off, all themes |
| **M2 — Micro-interactions** | Magnetic, tilt, spotlight, reveal, count-up, underline, nav condense (as `use:` actions) | 60fps; degrade on touch/reduced-motion |
| **M3 — Live demo** | Timeline rewrite, rotation, in-view pause, text equivalent, skip | Loops cleanly; pauses off-screen; 60fps mobile |
| **M4 — Scroll choreography + ambient** | Hero reveal (LCP-safe), section reveals, pipeline scrub/stepper, flywheel, **ambient atmosphere + fallback** | No CLS from reveals; ambient within budget; fallback verified |
| **M5 — Polish, a11y, perf, analytics** | Lighthouse/axe, contrast ×3, keyboard, events wired, OG/SEO | All §3.3 & §9 budgets met; QA gate (§14) green |
| **M6 (stretch)** | Schema constellation "wow" moment | Only if budget allows; lazy + fallback |

**Estimate:** ~8–12 focused front-end days + copy + optional illustration.

---

## 13. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ambient WebGL hurts perf/battery on mobile | Med | High | Lazy + gated + static fallback; pause off-screen; disable on low-power/save-data; A/B (E3) |
| Motion feels gratuitous → hurts conversion | Med | High | Motion must aid comprehension; A/B demo & CTA; reduced-motion first-class |
| Hero reveal delays LCP | Med | Med | Never fade LCP text from 0; mask/clip; measure each build |
| Dark-first direction breaks light themes | Med | Med | Token-only styling; theme audit is a DoD item every milestone |
| Claims drift from product reality | Low | High | CR-2 claims review against `docs/` before launch |
| Scope creep from "wow" moments | Med | Med | Commit to 2–3 signature moments; constellation is explicit stretch |
| Motion/scroll libs leak across SvelteKit nav | Med | Med | `gsap.context()`/`matchMedia` cleanup; destroy Lenis on unmount; QA app↔marketing round-trip |

---

## 14. Acceptance criteria — launch gate (Definition of Done)

- [ ] All **Must** requirements (§7–§9) implemented and verified.
- [ ] KPIs instrumented (§10); baseline captured; dashboards live.
- [ ] LCP < 2.5s, CLS < 0.05, INP < 200ms on throttled mobile.
- [ ] Lighthouse Perf/A11y/Best-Practices/SEO ≥ 90 each.
- [ ] `prefers-reduced-motion` and **JS-disabled** paths fully correct.
- [ ] All three themes: contrast, colors, toggle mid-scroll — clean.
- [ ] Full keyboard traversal; visible focus; no traps; demo text equivalent.
- [ ] Ambient effect within budget, pauses off-screen, has a verified fallback.
- [ ] Breakpoints 360/390/768/1024/1440/1920 clean; cross-browser (incl. iOS Safari).
- [ ] Claims review (CR-2) signed off by product.
- [ ] CTAs route correctly and fire analytics.

---

## 15. Open decisions (need sign-off before/within M0–M1)

| # | Decision | Owner | Default if undecided |
|---|---|---|---|
| **D-1** | Primary conversion goal: hosted signup vs. self-host/GitHub star? | Product | Hosted signup (primary), self-host secondary |
| **D-2** | Which **2–3 signature moments** to commit to? | Design+Eng | Live demo · magnetic CTAs · pipeline scrub |
| **D-3** | Greenlight the **WebGL ambient** atmosphere, or ship CSS-gradient aurora only? | Design+Eng | CSS/canvas aurora now; WebGL as fast-follow behind E3 |
| **D-4** | Illustration budget: custom SVG vs. icon primitives (CR-4)? | Design | Icon primitives |
| **D-5** | Final H1/subhead + demo questions + any social proof (CR-1/CR-3)? | Product | Build-plan placeholders |
| **D-6** | Cookie/consent banner needed for marketing analytics (jurisdiction)? | Legal/Product | Follow existing site policy |
| **D-7** | Deploy adapter/prerender path confirmation | Eng | Prerender `/` via adapter-static |

---

## Appendix A — Glossary
- **Trust levels:** Supervised → Assisted → Trusted (see `docs/06`).
- **Confidence:** High/Medium/Low signal on each answer.
- **Flywheel:** verified answers → higher accuracy/confidence over time.
- **Aurora atmosphere:** the living gradient/WebGL ambient background (art direction §6.2).

## Appendix B — References
- Reflect — https://reflect.app/
- Zajno motion — https://motion.zajno.com/
- Hydra Design Labs — https://hydradesignlabs.com/
- Stryds — https://www.stryds.com/
- Antigravity (background effect) — https://antigravity.google/

## Appendix C — Changelog
- **0.1** — Initial PRD; incorporates reference-driven art direction ("living
  light") and the companion build plan.
