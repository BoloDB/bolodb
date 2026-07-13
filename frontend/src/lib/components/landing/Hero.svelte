<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import gsap from 'gsap';
  import MagneticButton from '$lib/components/ui/MagneticButton.svelte';

  let heroRef: HTMLElement;
  let glowRef: HTMLElement;
  let headlineWords = ['Talk', 'to', 'your', 'database', 'like', 'a', 'human.'];
  let highlightIdx = new Set([3, 6]);
  let quickToX: ((v: number) => void) | null = null;
  let quickToY: ((v: number) => void) | null = null;

  function onMouseMove(e: MouseEvent) {
    if (!glowRef || !quickToX || !quickToY) return;
    quickToX(e.clientX - 150);
    quickToY(e.clientY - 150);
  }

  onMount(() => {
    quickToX = gsap.quickTo(glowRef, 'x', { duration: 1.2, ease: 'power2.out' });
    quickToY = gsap.quickTo(glowRef, 'y', { duration: 1.2, ease: 'power2.out' });

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
      tl.fromTo('.hero-word',
        { y: 80, opacity: 0, rotateX: -20 },
        { y: 0, opacity: 1, rotateX: 0, stagger: 0.04, duration: 0.7 }
      ).fromTo('.hero-sub',
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.8 },
        '-=0.2'
      ).fromTo('.hero-ctas > *',
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, stagger: 0.15, duration: 0.6 },
        '-=0.4'
      );
    }, heroRef);

    window.addEventListener('mousemove', onMouseMove);
    return () => {
      ctx.revert();
      window.removeEventListener('mousemove', onMouseMove);
    };
  });
</script>

<section
  bind:this={heroRef}
  class="hero"
  style="position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:120px 24px 80px"
>
  <div class="cursor-glow" bind:this={glowRef}></div>

  <div class="max-w-5xl mx-auto" style="position:relative;z-index:2">
    <h1 class="hero-headline" style="font-size:clamp(2.5rem, 6vw, 5rem);font-weight:800;letter-spacing:-0.03em;line-height:1.08;margin-bottom:24px;color:var(--ink)">
      {#each headlineWords as word, i}
        <span class="hero-word" style="display:inline-block;white-space:nowrap;{highlightIdx.has(i) ? `color:var(--brand);` : ''}">
          {word}{#if i < headlineWords.length - 1}&nbsp;{/if}
        </span>
      {/each}
    </h1>

    <p class="hero-sub" style="font-size:clamp(1rem, 2vw, 1.35rem);font-weight:500;color:var(--muted);max-width:660px;margin:0 auto 40px;line-height:1.6;letter-spacing:-0.01em">
      Ask questions in plain English. Get instant SQL-powered answers.<br class="hidden sm:block" />
      No query language required.
    </p>

    <div class="hero-ctas" style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;align-items:center">
      <MagneticButton onclick={() => goto('/signup')}>
        Try it free&nbsp;→
      </MagneticButton>
      <MagneticButton kind="ghost" onclick={() => {
        const demo = document.getElementById('demo-section');
        demo?.scrollIntoView({ behavior: 'smooth' });
      }}>
        Watch the demo&nbsp;↓
      </MagneticButton>
    </div>
  </div>
</section>

<style>
  .cursor-glow {
    position: fixed;
    top: 0;
    left: 0;
    width: 300px;
    height: 300px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--brand) 0%, transparent 70%);
    opacity: 0.06;
    pointer-events: none;
    z-index: 0;
    will-change: transform;
  }
</style>
