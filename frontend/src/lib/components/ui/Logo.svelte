<script lang="ts">
  let { size = 28, withText = true, sub = false }: { size?: number; withText?: boolean; sub?: boolean } = $props();
</script>

<div style="display:flex;align-items:center;gap:10px">
  <svg width={size} height={size} viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M 52 44 Q 52 30 66 30 L 190 30 Q 204 30 204 44 L 204 138 Q 204 152 190 152 L 116 152 L 88 176 L 92 152 L 66 152 Q 52 152 52 138 Z" stroke="var(--brand)" stroke-width="6" fill="none"/>
    <g stroke="var(--brand)" stroke-width="6" stroke-linecap="round" fill="none">
      <ellipse cx="128" cy="66" rx="34" ry="11"/>
      <path d="M 94 66 L 94 108 Q 94 119 128 119 Q 162 119 162 108 L 162 66"/>
      <path d="M 94 87 Q 94 98 128 98 Q 162 98 162 87"/>
    </g>
    <circle cx="182" cy="46" r="3.5" fill="var(--brand)"/>
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
