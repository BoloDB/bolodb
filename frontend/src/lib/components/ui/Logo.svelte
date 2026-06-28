<script lang="ts">
  let { size = 28, withText = true, sub = false }: { size?: number; withText?: boolean; sub?: boolean } = $props();
</script>

<div style="display:flex;align-items:center;gap:10px">
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
    <rect x="2.2" y="2.2" width="27.6" height="27.6" rx="9" fill="var(--brand)" />
    <path d="M9 20.5c2.3 1.7 4.6 2.5 7 2.5 2.4 0 4.7-.8 7-2.5" stroke="#fff" stroke-width="2.1" stroke-linecap="round" />
    <circle cx="12" cy="13" r="1.9" fill="#fff" />
    <circle cx="20" cy="13" r="1.9" fill="#fff" />
  </svg>
  {#if withText}
    <div style="line-height:1">
      <div style="font-weight:800;font-size:{size * 0.66}px;letter-spacing:-.02em;color:var(--ink)">
        Bolo<span style="color:var(--brand)">DB</span>
      </div>
      {#if sub}
        <div style="font-size:11.5px;color:var(--faint);font-weight:600;margin-top:3px">Ask your data. Trust the answer.</div>
      {/if}
    </div>
  {/if}
</div>
