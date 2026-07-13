<script lang="ts">
  import { onMount } from 'svelte';
  import gsap from 'gsap';
  import { ScrollTrigger } from 'gsap/ScrollTrigger';
  gsap.registerPlugin(ScrollTrigger);

  let sectionRef: HTMLElement;

  const guarantees = [
    {
      icon: 'shield',
      title: 'Read-only queries',
      desc: 'BoloDB never modifies your data. Every query runs as read-only — no INSERT, UPDATE, DELETE, or DDL allowed.',
    },
    {
      icon: 'eye',
      title: 'Schema only',
      desc: 'Only your database structure and question are sent to the AI. Row data never leaves your database.',
    },
    {
      icon: 'code',
      title: 'Fully open source',
      desc: 'Every line of code is on GitHub. Audit, self-host, or contribute — your data, your control.',
    },
  ];

  onMount(() => {
    const ctx = gsap.context(() => {
      const cards = sectionRef.querySelectorAll('.trust-card');
      ScrollTrigger.create({
        trigger: sectionRef,
        start: 'top 80%',
        onEnter: () => {
          gsap.fromTo(cards, { y: 30, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.15, duration: 0.6, ease: 'power3.out' });
        },
        once: true,
      });
    }, sectionRef);
    return () => ctx.revert();
  });
</script>

<section bind:this={sectionRef} style="position:relative;z-index:1;padding:80px 24px 100px">
  <div class="max-w-5xl mx-auto">
    <h2 style="font-size:clamp(1.6rem, 3.5vw, 2.5rem);font-weight:800;text-align:center;margin-bottom:12px;color:var(--ink);letter-spacing:-0.02em">
      Your data stays yours
    </h2>
    <p style="text-align:center;color:var(--muted);font-size:1.05rem;font-weight:500;margin-bottom:48px;max-width:480px;margin-left:auto;margin-right:auto">
      Security and privacy built into every layer.
    </p>

    <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:24px">
      {#each guarantees as g}
        <div class="trust-card" style="padding:32px 28px;border-radius:16px;border:1px solid var(--border);background:var(--surface);text-align:center">
          <div style="width:48px;height:48px;border-radius:12px;background:var(--brand-tint);color:var(--brand);display:flex;align-items:center;justify-content:center;margin:0 auto 16px">
            {#if g.icon === 'shield'}
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            {:else if g.icon === 'eye'}
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            {:else}
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            {/if}
          </div>
          <h3 style="font-size:1.1rem;font-weight:700;color:var(--ink);margin-bottom:8px">{g.title}</h3>
          <p style="color:var(--muted);font-size:0.92rem;line-height:1.6;font-weight:500;margin:0">{g.desc}</p>
        </div>
      {/each}
    </div>

    <div style="text-align:center;margin-top:40px">
      <a href="https://github.com/HAAHIT/bolodb" target="_blank" rel="noopener noreferrer"
        style="display:inline-flex;align-items:center;gap:8px;padding:10px 24px;border-radius:99px;border:1px solid var(--border);color:var(--muted);font-size:14px;font-weight:600;text-decoration:none;transition:all .15s;background:var(--surface)">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
        View on GitHub
      </a>
    </div>
  </div>
</section>
