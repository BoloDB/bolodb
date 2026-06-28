<script lang="ts">
  import type { TrustLevel } from '$lib/types';

  let { level, count }: { level: TrustLevel; count: number } = $props();

  const tints: Record<string, [string, string, string]> = {
    supervised: ['var(--c-med-tint)', 'var(--c-med-ink)', 'var(--c-med)'],
    assisted: ['var(--brand-tint)', 'var(--brand-ink)', 'var(--brand)'],
    trusted: ['var(--brand-tint)', 'var(--brand-ink)', 'var(--brand)']
  };

  const colors = $derived(tints[level.key] ?? tints.supervised);
</script>

<span
  style="display:inline-flex;align-items:center;gap:7px;padding:6px 13px;border-radius:99px;white-space:nowrap;background:{colors[0]};color:{colors[1]};font-size:12.5px;font-weight:700;border:1px solid color-mix(in srgb, {colors[2]} 25%, transparent)"
>
  <span style="width:7px;height:7px;border-radius:99px;background:{colors[2]}"></span>
  {level.label}
  <span class="tnum" style="opacity:.6">· {count}</span>
</span>
