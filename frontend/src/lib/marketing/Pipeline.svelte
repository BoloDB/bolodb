<script lang="ts">
  import { browser } from "$app/environment";
  import { motionPrefs } from "$lib/motion/motionPrefs";
  import { reveal } from "$lib/actions/reveal";

  const steps = [
    {
      icon: "plug",
      title: "Connect",
      desc: "Connect your database with a connection string — or try sample data in seconds.",
    },
    {
      icon: "message",
      title: "Ask",
      desc: "Type questions in plain English. No SQL needed.",
    },
    {
      icon: "shield",
      title: "Trust",
      desc: "See the exact SQL, inspect results, and confirm every answer. BoloDB gets smarter with each verification.",
    },
  ];

  let pipelineEl: HTMLElement;
  let spineEl: SVGPathElement;

  $effect(() => {
    if (!browser) return;
    if (!pipelineEl) return;
    if (motionPrefs.reduced) return;

    let sts: any[] = [];
    let mm: any;

    (async () => {
      const { loadGsap } = await import("$lib/motion/gsap");
      const { gsap, ScrollTrigger } = await loadGsap();

      mm = gsap.matchMedia();

      mm.add("(min-width: 768px)", () => {
        const cards = pipelineEl.querySelectorAll<HTMLElement>(".pipeline-step");
        const spine = spineEl;
        if (!cards.length || !spine) return;

        const spineLen = spine.getTotalLength();
        gsap.set(spine, { strokeDasharray: spineLen, strokeDashoffset: spineLen });

        const st = ScrollTrigger.create({
          trigger: pipelineEl,
          start: "top center",
          end: "bottom center",
          pin: false,
          scrub: 1.2,
          onUpdate: (self: any) => {
            const p = self.progress;
            const drawLen = spineLen * p;
            gsap.set(spine, { strokeDashoffset: spineLen - drawLen });
            cards.forEach((card, i) => {
              const stepProgress = Math.min(1, Math.max(0, (p - i * 0.28) * 3));
              gsap.set(card, {
                opacity: 0.3 + stepProgress * 0.7,
                y: 20 - stepProgress * 20,
                scale: 0.95 + stepProgress * 0.05,
                boxShadow: stepProgress > 0.5 ? "var(--shadow-lg)" : "none",
              });
              const number = card.querySelector(".step-number") as HTMLElement;
              if (number) {
                gsap.set(number, {
                  background: stepProgress > 0.5 ? "var(--brand)" : "var(--brand-tint)",
                  color: stepProgress > 0.5 ? "#fff" : "var(--brand)",
                });
              }
            });
          },
        });
        sts.push(st);

        return () => sts.forEach((t: any) => t.kill());
      });

      ScrollTrigger.refresh();
    })();

    return () => {
      sts.forEach((t: any) => t.kill());
      mm?.revert();
    };
  });
</script>

<section id="pipeline" bind:this={pipelineEl} class="pipeline-section">
  <h2 class="section-label">How it works</h2>
  <h3 class="section-title">From question to trusted answer in three steps</h3>

  <div class="pipeline-desktop">
    <svg class="pipeline-spine" viewBox="0 0 300 12" preserveAspectRatio="none" aria-hidden="true">
      <path d="M 10 6 L 290 6" stroke="var(--border-2)" stroke-width="3" stroke-linecap="round" fill="none" />
      <path bind:this={spineEl} d="M 10 6 L 290 6" stroke="var(--brand)" stroke-width="3" stroke-linecap="round" fill="none" />
      <circle cx="50" cy="6" r="4" fill="var(--surface-2)" stroke="var(--border-2)" stroke-width="1.5" />
      <circle cx="150" cy="6" r="4" fill="var(--surface-2)" stroke="var(--border-2)" stroke-width="1.5" />
      <circle cx="250" cy="6" r="4" fill="var(--surface-2)" stroke="var(--border-2)" stroke-width="1.5" />
    </svg>

    <div class="pipeline-grid">
      {#each steps as step, i}
        <div class="pipeline-step" style="opacity:0;transform:translateY(20px) scale(0.95)">
          <div class="step-number">{i + 1}</div>
          <div class="step-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              {#if step.icon === "plug"}
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
              {:else if step.icon === "message"}
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              {:else if step.icon === "shield"}
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              {/if}
            </svg>
          </div>
          <h4 class="step-title">{step.title}</h4>
          <p class="step-desc">{step.desc}</p>
        </div>
      {/each}
    </div>
  </div>

  <div class="pipeline-mobile">
    {#each steps as step, i}
      <div class="mobile-step" use:reveal>
        <div class="mobile-step-left">
          <div class="step-dot"></div>
          {#if i < steps.length - 1}
            <div class="step-line"></div>
          {/if}
        </div>
        <div class="mobile-step-content">
          <div class="step-number">{i + 1}</div>
          <div class="step-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              {#if step.icon === "plug"}
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
              {:else if step.icon === "message"}
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              {:else if step.icon === "shield"}
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              {/if}
            </svg>
          </div>
          <h4 class="step-title">{step.title}</h4>
          <p class="step-desc">{step.desc}</p>
        </div>
      </div>
    {/each}
  </div>
</section>

<style>
  .pipeline-section {
    position: relative;
    z-index: 2;
    max-width: 1100px;
    margin: 0 auto;
    padding: 100px 24px;
    text-align: center;
  }

  .section-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--faint);
    font-family: var(--font-mono);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 0 0 8px;
  }

  .section-title {
    font-size: clamp(1.5rem, 3.5vw, 2.25rem);
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 60px;
    line-height: 1.2;
    text-wrap: balance;
  }

  .pipeline-desktop {
    position: relative;
  }

  @media (max-width: 767px) {
    .pipeline-desktop { display: none; }
  }

  .pipeline-spine {
    position: absolute;
    top: 108px;
    left: 5%;
    right: 5%;
    width: 90%;
    height: 8px;
    z-index: 0;
  }

  .pipeline-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    position: relative;
    z-index: 1;
  }

  .pipeline-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 32px 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease);
    will-change: transform, opacity;
  }

  .pipeline-step:hover {
    transform: translateY(-4px) !important;
    box-shadow: var(--shadow-lg);
  }

  .step-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    color: var(--brand);
    background: var(--brand-tint);
    font-family: var(--font-mono);
  }

  .step-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 14px;
    color: var(--brand);
    background: var(--brand-tint-2);
  }

  .step-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    margin: 0;
  }

  .step-desc {
    font-size: 14px;
    line-height: 1.6;
    color: var(--muted);
    margin: 0;
    text-wrap: balance;
  }

  /* Mobile stepper */
  .pipeline-mobile {
    display: none;
  }

  @media (max-width: 767px) {
    .pipeline-mobile {
      display: flex;
      flex-direction: column;
      gap: 0;
      max-width: 400px;
      margin: 0 auto;
    }
  }

  .mobile-step {
    display: flex;
    gap: 16px;
    text-align: left;
  }

  .mobile-step-left {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 20px;
    flex-shrink: 0;
  }

  .step-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--brand);
    border: 2px solid var(--brand-tint-2);
    flex-shrink: 0;
    margin-top: 16px;
  }

  .step-line {
    width: 2px;
    flex: 1;
    background: var(--border-2);
    min-height: 30px;
  }

  .mobile-step-content {
    flex: 1;
    padding: 12px 0 32px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .mobile-step-content .step-number {
    width: 24px;
    height: 24px;
    font-size: 10px;
  }

  .mobile-step-content .step-icon {
    width: 40px;
    height: 40px;
  }
</style>
