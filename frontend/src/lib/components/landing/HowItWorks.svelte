<script lang="ts">
  import { onMount } from 'svelte';
  import gsap from 'gsap';
  import { ScrollTrigger } from 'gsap/ScrollTrigger';
  gsap.registerPlugin(ScrollTrigger);

  let sectionRef: HTMLElement;

  const steps = [
    {
      icon: 'connect',
      title: 'Connect',
      desc: 'Paste your database URL. BoloDB auto-detects your schema and is ready to answer questions instantly.',
    },
    {
      icon: 'ask',
      title: 'Ask',
      desc: 'Type questions in plain English. The AI generates the right SQL for your schema behind the scenes.',
    },
    {
      icon: 'trust',
      title: 'Trust',
      desc: 'Review every generated query. Verify answers to train the AI — it gets smarter with each correction.',
    },
  ];

  onMount(() => {
    const ctx = gsap.context(() => {
      const cards = sectionRef.querySelectorAll('.hiw-card');
      const lines = sectionRef.querySelectorAll('.hiw-line');
      ScrollTrigger.create({
        trigger: sectionRef,
        start: 'top 80%',
        onEnter: () => {
          gsap.fromTo(lines, { scaleX: 0 }, { scaleX: 1, duration: 0.6, stagger: 0.3, ease: 'power2.out', transformOrigin: 'left center' });
          gsap.fromTo(cards, { y: 40, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.2, duration: 0.6, ease: 'power3.out' });
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
      How it works
    </h2>
    <p style="text-align:center;color:var(--muted);font-size:1.05rem;font-weight:500;margin-bottom:56px;max-width:480px;margin-left:auto;margin-right:auto">
      Three simple steps from connection to trusted answers.
    </p>

    <div style="display:grid;grid-template-columns:repeat(3, 1fr);gap:0;position:relative">
      {#each steps as step, i}
        <div class="hiw-card" style="text-align:center;padding:0 24px">
          <div style="width:56px;height:56px;border-radius:16px;background:var(--brand-tint);color:var(--brand);display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:24px;font-weight:800">
            {#if i === 0}
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/></svg>
            {:else if i === 1}
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            {:else}
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg>
            {/if}
          </div>
          <div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:10px">
            <span style="width:28px;height:28px;border-radius:50%;background:var(--brand);color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800">{i + 1}</span>
            <h3 style="font-size:1.2rem;font-weight:700;color:var(--ink);margin:0">{step.title}</h3>
          </div>
          <p style="color:var(--muted);font-size:0.95rem;line-height:1.65;font-weight:500;max-width:320px;margin:0 auto">{step.desc}</p>
        </div>

        {#if i < steps.length - 1}
          <div class="hiw-line" style="position:absolute;top:28px;left:calc((100% / 3) * (1 + {i}) - 10%);width:20%;height:2px;background:var(--border-2);transform-origin:left center;scaleX:0">
          </div>
        {/if}
      {/each}
    </div>
  </div>
</section>
