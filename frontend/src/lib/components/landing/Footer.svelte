<script lang="ts">
  import { onMount } from 'svelte';
  import gsap from 'gsap';
  import { ScrollTrigger } from 'gsap/ScrollTrigger';
  gsap.registerPlugin(ScrollTrigger);

  let sectionRef: HTMLElement;

  onMount(() => {
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: sectionRef,
        start: 'top 95%',
        onEnter: () => {
          gsap.fromTo(sectionRef.querySelectorAll('.fade-item'), { y: 12, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.1, duration: 0.5, ease: 'power2.out' });
        },
        once: true,
      });
    }, sectionRef);
    return () => ctx.revert();
  });
</script>

<footer bind:this={sectionRef} style="position:relative;z-index:1;padding:40px 24px;border-top:1px solid var(--border)">
  <div class="max-w-5xl mx-auto" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px">
    <div class="fade-item" style="font-size:13px;font-weight:600;color:var(--faint)">
      &copy; 2026 BoloDB. All rights reserved.
    </div>
    <div style="display:flex;gap:20px">
      {#each [{label:'GitHub', href:'https://github.com/HAAHIT/bolodb'}, {label:'Privacy', href:'#'}, {label:'Terms', href:'#'}] as link}
        <a class="fade-item" {href} target="_blank" rel="noopener noreferrer"
          style="font-size:13px;font-weight:600;color:var(--faint);text-decoration:none;transition:color .15s"
          onmouseenter={(e) => (e.currentTarget as HTMLElement).style.color = 'var(--muted)'}
          onmouseleave={(e) => (e.currentTarget as HTMLElement).style.color = 'var(--faint)'}
        >{link.label}</a>
      {/each}
    </div>
  </div>
</footer>
