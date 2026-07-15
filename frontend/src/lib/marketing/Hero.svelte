<script lang="ts">
  import { browser } from "$app/environment";
  import LL from "$lib/i18n/i18n-svelte";
  import { goto } from "$app/navigation";
  import { magnetic } from "$lib/actions/magnetic";
  import { motionPrefs } from "$lib/motion/motionPrefs";
  import { scrollTo } from "$lib/motion/lenis";
  import { trackCtaClick } from "$lib/marketing/analytics";

  let heroEl: HTMLElement;
  let h1Line1: HTMLElement;
  let h1Line2: HTMLElement;
  let subEl: HTMLElement;
  let ctaRow: HTMLElement;
  let trustEl: HTMLElement;

  function revealInstant() {
    if (h1Line1) h1Line1.style.clipPath = "none";
    if (h1Line2) h1Line2.style.clipPath = "none";
    if (subEl) subEl.style.opacity = "1";
    if (ctaRow) ctaRow.style.opacity = "1";
    if (trustEl) trustEl.style.opacity = "0.7";
  }

  $effect(() => {
    if (!browser) return;
    if (motionPrefs.reduced) {
      revealInstant();
      return;
    }

    let cleanup = () => {};
    let cancelled = false;
    let revealed = false;

    // Safety net: if the GSAP chunk fails to load or the timeline never
    // finishes (slow network, blocked script, etc.), force the hero back
    // to visible so copy/CTAs are never stuck at their hidden "from" state.
    const safetyTimer = window.setTimeout(() => {
      if (!cancelled) {
        revealed = true;
        revealInstant();
      }
    }, 1500);

    (async () => {
      try {
        const { loadGsap } = await import("$lib/motion/gsap");
        const { gsap } = await loadGsap();

        if (cancelled || revealed) return;

        const tl = gsap.timeline({
          defaults: { ease: "power3.out", duration: 0.6 },
          onComplete: () => window.clearTimeout(safetyTimer),
        });

        tl.fromTo(
          h1Line1,
          { clipPath: "inset(0 0 100% 0)" },
          { clipPath: "inset(0 0 0% 0)", duration: 0.7 }
        )
          .fromTo(
            h1Line2,
            { clipPath: "inset(0 0 100% 0)" },
            { clipPath: "inset(0 0 0% 0)", duration: 0.7 },
            "-=0.4"
          )
          .fromTo(
            subEl,
            { y: 16, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.5 },
            "-=0.25"
          )
          .fromTo(
            ctaRow,
            { y: 16, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.5 },
            "-=0.2"
          )
          .fromTo(
            trustEl,
            { y: 12, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.5 },
            "-=0.15"
          );

        cleanup = () => tl.kill();
      } catch (err) {
        console.error("Hero animation failed to load, showing content instantly", err);
        if (!cancelled) revealInstant();
      }
    })();

    return () => {
      cancelled = true;
      window.clearTimeout(safetyTimer);
      cleanup();
    };
  });
</script>

<section bind:this={heroEl} class="hero">
  <div class="hero-content">
    <span class="eyebrow">AI data analyst you can trust</span>

    <h1 class="hero-h1">
      <span class="h1-mask" bind:this={h1Line1}><span class="h1-line">{$LL.landing.talkToYourDatabase()}</span></span>
      <span class="h1-mask" bind:this={h1Line2}><span class="h1-line h1-accent">{$LL.landing.likeAHuman()}</span></span>
    </h1>

    <p class="hero-sub" bind:this={subEl}>{$LL.landing.noSqlRequired()}</p>

    <div class="hero-ctas" bind:this={ctaRow}>
      <button
        class="btn btn-primary btn-lg"
        use:magnetic
        data-testid="hero-start-free-button"
        onclick={() => { trackCtaClick("hero", "Start for free", "/signup"); goto("/signup"); }}
      >
        {$LL.landing.startForFree()}
      </button>
      <button
        class="btn btn-ghost btn-lg"
        data-testid="hero-demo-button"
        onclick={() => { trackCtaClick("hero", "Watch it work", "#demo"); scrollTo("demo"); }}
      >
        {$LL.landing.viewDemo()}
      </button>
    </div>

    <div class="trust-strip" bind:this={trustEl}>
      <div class="db-logos">
        <span class="db-logo">PostgreSQL</span>
        <span class="db-dot">•</span>
        <span class="db-logo">MySQL</span>
        <span class="db-dot">•</span>
        <span class="db-logo">SQL Server</span>
        <span class="db-dot">•</span>
        <span class="db-logo">SQLite</span>
      </div>
      <span class="trust-line">read-only • your data stays yours</span>
    </div>
  </div>
</section>

<style>
  .hero {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 90vh;
    padding: 160px 24px 80px;
  }

  .hero-content {
    max-width: 800px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
  }

  .eyebrow {
    display: inline-flex;
    padding: 6px 14px;
    border-radius: 99px;
    font-size: 13px;
    font-weight: 600;
    color: var(--brand);
    background: var(--brand-tint);
    border: 1px solid var(--brand-tint-2);
    letter-spacing: -0.01em;
  }

  .hero-h1 {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .h1-mask {
    overflow: hidden;
    display: block;
  }

  .h1-line {
    display: block;
    font-size: clamp(2.5rem, 6vw, 4.75rem);
    font-weight: 800;
    line-height: 1.05;
    letter-spacing: -0.02em;
    color: var(--ink);
  }

  .h1-accent {
    color: var(--brand);
  }

  .hero-sub {
    font-size: clamp(1rem, 2vw, 1.25rem);
    line-height: 1.6;
    color: var(--muted);
    max-width: 600px;
    text-wrap: balance;
  }

  .hero-ctas {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: center;
    margin-top: 8px;
  }

  .trust-strip {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    margin-top: 32px;
    opacity: 0.7;
  }

  .db-logos {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
    font-weight: 600;
    color: var(--faint);
    font-family: var(--font-mono);
  }

  .db-dot {
    opacity: 0.3;
  }

  .trust-line {
    font-size: 12.5px;
    color: var(--faint);
    letter-spacing: 0.02em;
  }
</style>
