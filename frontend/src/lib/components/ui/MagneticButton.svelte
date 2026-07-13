<script lang="ts">
  import gsap from 'gsap';

  let {
    href,
    kind = 'primary',
    size = 'lg',
    onclick,
    children,
  }: {
    href?: string;
    kind?: 'primary' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    onclick?: () => void;
    children?: import('svelte').Snippet;
  } = $props();

  let el = $state<HTMLElement>();

  const maxDist = 12;

  function onMove(e: PointerEvent) {
    if (!el || e.pointerType !== 'mouse') return;
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = ((e.clientX - cx) / (rect.width / 2)) * maxDist;
    const dy = ((e.clientY - cy) / (rect.height / 2)) * maxDist;
    gsap.to(el, { x: dx, y: dy, duration: 0.4, ease: 'power2.out', overwrite: 'auto' });
  }

  function onLeave() {
    if (!el) return;
    gsap.to(el, { x: 0, y: 0, duration: 0.4, ease: 'power2.out' });
  }

  const sizeClasses: Record<string, string> = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3 text-base',
    lg: 'px-8 py-4 text-lg',
  };

  const kindClasses: Record<string, string> = {
    primary: 'btn-primary shadow-xl hover:shadow-2xl',
    ghost: 'btn-ghost',
  };
</script>

{#if href}
  <a
    bind:this={el as HTMLAnchorElement}
    {href}
    onpointermove={onMove}
    onpointerleave={onLeave}
    class="magnetic-btn {kindClasses[kind]} {sizeClasses[size]}">
    <div class="magnetic-inner">
      {@render children?.()}
    </div>
  </a>
{:else}
  <button
    bind:this={el as HTMLButtonElement}
    {onclick}
    onpointermove={onMove}
    onpointerleave={onLeave}
    class="magnetic-btn {kindClasses[kind]} {sizeClasses[size]}"
  >
    <div class="magnetic-inner">
      {@render children?.()}
    </div>
  </button>
{/if}

<style>
  .magnetic-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-radius: 999px;
    font-weight: 700;
    cursor: pointer;
    transition: box-shadow .2s, background .2s;
    position: relative;
    overflow: hidden;
    text-decoration: none;
    will-change: transform;
  }
  .magnetic-inner {
    pointer-events: none;
  }
</style>
