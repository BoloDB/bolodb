<script lang="ts">
  import type { Provider } from '$lib/types';
  let { provider, active, onclick, delay = 0 }:
    { provider: Provider; active: boolean; onclick: () => void; delay?: number } = $props();
</script>

<button {onclick} class="focusable rise"
  style="text-align:left;padding:16px 15px;border-radius:var(--radius);cursor:pointer;
    background:{active?'var(--surface)':'var(--surface-2)'};
    border:{active?'1.5px solid var(--brand)':'1.5px solid var(--border)'};
    box-shadow:{active?'0 0 0 4px var(--ring), var(--shadow)':'var(--shadow-sm)'};
    transition:all .18s var(--ease);position:relative;animation-delay:{delay}ms">
  {#if provider.badge}
    <span style="position:absolute;top:-8px;right:10px;font-size:10.5px;font-weight:800;letter-spacing:.02em;padding:3px 8px;border-radius:99px;background:{provider.tone==='brand'?'var(--brand)':'var(--ink)'};color:var(--surface)">{provider.badge}</span>
  {/if}
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
    <span style="width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:{active?'var(--brand-tint)':'var(--surface-3)'};color:{active?'var(--brand)':'var(--muted)'}">
      {#if provider.id==='ollama'}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor"/></svg>
      {/if}
    </span>
    <div>
      <div style="font-weight:700;font-size:15px;line-height:1.1">{provider.name}</div>
      <div style="font-size:11.5px;color:var(--faint);font-weight:600">{provider.sub}</div>
    </div>
  </div>
  {#each [
    ['Privacy', provider.id==='ollama'?'Fully private':'No row data sent', provider.id==='ollama'],
    ['Cost', provider.cost==='Pay per use'?'Metered':provider.cost, provider.cost==='Free'],
    ['Accuracy', provider.accuracy.split('—')[0].split(',')[0].trim(), false]
  ] as [label, value, good]}
    <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;font-size:12px;padding:3px 0">
      <span style="color:var(--faint);font-weight:600;flex-shrink:0">{label}</span>
      <span style="color:{good?'var(--brand-ink)':'var(--ink-2)'};font-weight:650;font-size:11.8px;white-space:nowrap">{value}</span>
    </div>
  {/each}
</button>
