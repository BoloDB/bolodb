<script lang="ts">
  let { num, title, hint, children }: { num: string; title: string; hint?: string; children: any } = $props();
</script>

<div class="rise" style="margin-bottom:30px;animation-delay:.05s">
  <div style="display:flex;align-items:baseline;gap:11px;margin-bottom:14px">
    <span style="width:24px;height:24px;border-radius:8px;background:var(--ink);color:var(--surface);display:grid;place-items:center;font-size:12.5px;font-weight:800;flex-shrink:0;transform:translateY(3px)">{num}</span>
    <div>
      <h2 style="margin:0;font-size:19px;font-weight:700;letter-spacing:-.02em">{title}</h2>
      {#if hint}
        <p style="margin:3px 0 0;font-size:13.5px;color:var(--faint)">{hint}</p>
      {/if}
    </div>
  </div>
  {@render children()}
</div>
