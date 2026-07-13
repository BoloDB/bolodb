<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import gsap from 'gsap';
  import { ScrollTrigger } from 'gsap/ScrollTrigger';
  import MagneticButton from '$lib/components/ui/MagneticButton.svelte';
  gsap.registerPlugin(ScrollTrigger);

  let sectionRef: HTMLElement;
  let words = ['Ready', 'to', 'talk', 'to', 'your', 'database?'];

  onMount(() => {
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: sectionRef,
        start: 'top 85%',
        onEnter: () => {
          const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
          tl.fromTo('.cta-word', { y: 40, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.04, duration: 0.6 })
            .fromTo('.cta-sub', { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6 }, '-=0.3')
            .fromTo('.cta-btn', { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5 }, '-=0.2')
            .fromTo('.cta-dbs', { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4 }, '-=0.1');
        },
        once: true,
      });
    }, sectionRef);
    return () => ctx.revert();
  });
</script>

<section bind:this={sectionRef} style="position:relative;z-index:1;padding:100px 24px 80px;text-align:center">
  <div class="max-w-3xl mx-auto">
    <h2 style="font-size:clamp(2rem, 4vw, 3rem);font-weight:800;letter-spacing:-0.03em;line-height:1.15;color:var(--ink);margin-bottom:16px">
      {#each words as word, i}
        <span class="cta-word" style="display:inline-block;white-space:nowrap;{i === 5 ? `color:var(--brand);` : ''}">
          {word}{#if i < words.length - 1}&nbsp;{/if}
        </span>
      {/each}
    </h2>

    <p class="cta-sub" style="font-size:1.1rem;font-weight:500;color:var(--muted);max-width:480px;margin:0 auto 32px;line-height:1.6">
      Ask questions. Get answers. Trust the logic.
    </p>

    <div class="cta-btn">
      <MagneticButton onclick={() => goto('/signup')}>
        Start asking&nbsp;→
      </MagneticButton>
    </div>

    <p class="cta-dbs" style="font-size:0.85rem;font-weight:600;color:var(--faint);margin-top:16px">
      No credit card required &middot; Postgres &middot; SQLite &middot; MySQL (coming soon)
    </p>
  </div>
</section>
