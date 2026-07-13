<script lang="ts">
  import { onMount } from 'svelte';
  import gsap from 'gsap';
  import { ScrollTrigger } from 'gsap/ScrollTrigger';
  gsap.registerPlugin(ScrollTrigger);

  let sectionRef: HTMLElement;

  const stats = [
    { value: 4600, suffix: '+', label: 'GitHub stars' },
    { value: 12000, suffix: '+', label: 'Queries answered' },
    { value: 3, suffix: '', label: 'Databases supported' },
    { value: 99, suffix: '%', label: 'Uptime' },
  ];

  onMount(() => {
    const ctx = gsap.context(() => {
      const counters = sectionRef.querySelectorAll('.stat-counter');
      const labels = sectionRef.querySelectorAll('.stat-label');
      ScrollTrigger.create({
        trigger: sectionRef,
        start: 'top 85%',
        onEnter: () => {
          gsap.fromTo(labels, { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, stagger: 0.1, ease: 'power2.out' });
          counters.forEach((el, i) => {
            const target = stats[i].value;
            gsap.fromTo(el, { textContent: '0' }, {
              textContent: target,
              duration: 2,
              ease: 'power2.out',
              snap: { textContent: 1 },
              delay: 0.2,
            });
          });
        },
        once: true,
      });
    }, sectionRef);
    return () => ctx.revert();
  });
</script>

<section bind:this={sectionRef} style="position:relative;z-index:1;padding:60px 24px 80px">
  <div class="max-w-5xl mx-auto">
    <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:0;border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:40px 0">
      {#each stats as s, i}
        <div style="text-align:center;border-right:{i < stats.length - 1 ? '1px solid var(--border)' : 'none'};padding:0 16px">
          <div class="stat-value" style="font-size:clamp(1.8rem, 3vw, 2.5rem);font-weight:800;color:var(--brand);letter-spacing:-0.02em;font-variant-numeric:tabular-nums">
            <span class="stat-counter">0</span>{s.suffix}
          </div>
          <div class="stat-label" style="font-size:0.88rem;font-weight:600;color:var(--faint);margin-top:4px">{s.label}</div>
        </div>
      {/each}
    </div>
  </div>
</section>
