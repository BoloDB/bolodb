<script lang="ts">
  import { browser } from "$app/environment";
  import { goto } from "$app/navigation";
  import { motionPrefs } from "$lib/motion/motionPrefs";
  import { magnetic } from "$lib/actions/magnetic";
  import { trackCtaClick } from "$lib/marketing/analytics";

  let panelEl: HTMLElement;

  $effect(() => {
    if (!browser || !panelEl) return;
    if (motionPrefs.reduced) return;
    let st: any;
    (async () => {
      const { loadGsap } = await import("$lib/motion/gsap");
      const { gsap, ScrollTrigger } = await loadGsap();
      gsap.set(panelEl, { y: 32, opacity: 0, scale: 0.97 });
      st = ScrollTrigger.create({
        trigger: panelEl,
        start: "top 85%",
        onEnter: () => {
          gsap.to(panelEl, { y: 0, opacity: 1, scale: 1, duration: 0.7, ease: "power3.out" });
        },
        once: true,
      });
    })();
    return () => { st?.kill(); };
  });
</script>

<section class="cta-section">
  <div bind:this={panelEl} class="cta-panel">
    <h2 class="cta-title">Ask your first question in a minute.</h2>
    <p class="cta-desc">
      Get a free Gemini API key, connect your database, and start asking
      questions. No credit card required.
    </p>
    <div class="cta-buttons">
      <button
        class="btn btn-primary btn-lg"
        use:magnetic
        data-testid="final-cta-start-button"
        onclick={() => { trackCtaClick("final", "Start for free", "/signup"); goto("/signup"); }}
      >
        Start for free
      </button>
      <button 
        class="btn btn-ghost btn-lg" 
        data-testid="final-cta-sample-button"
        onclick={() => { trackCtaClick("final", "Try with sample data", "/signup"); goto("/signup"); }}
      >
        Try with sample data
      </button>
    </div>
  </div>
</section>

<style>
  .cta-section {
    position: relative;
    z-index: 2;
    padding: 100px 24px;
    display: flex;
    justify-content: center;
  }

  .cta-panel {
    max-width: 640px;
    width: 100%;
    text-align: center;
    padding: 64px 40px;
    border-radius: var(--radius-xl);
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
  }

  .cta-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
      radial-gradient(700px 250px at 50% 0%, var(--brand-tint) 0%, transparent 60%),
      radial-gradient(500px 300px at 80% 80%, var(--brand-tint-2) 0%, transparent 50%);
    pointer-events: none;
  }

  .cta-title {
    position: relative;
    font-size: clamp(1.6rem, 3.5vw, 2.25rem);
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 12px;
    line-height: 1.15;
    text-wrap: balance;
  }

  .cta-desc {
    position: relative;
    font-size: 15px;
    line-height: 1.6;
    color: var(--muted);
    margin: 0 0 32px;
    text-wrap: balance;
  }

  .cta-buttons {
    position: relative;
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
  }
</style>
