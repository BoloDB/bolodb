<script lang="ts">
  import { ArcChart } from 'layerchart';
  import { trustFor } from '$lib/data';

  let {
    verifiedCount,
  }: {
    verifiedCount: number;
  } = $props();

  const level = $derived(trustFor(verifiedCount));
  const progress = $derived(Math.min(verifiedCount / 7, 1));
  const nextMilestone = $derived(level.next);
  const barColor = $derived(
    level.key === 'trusted' ? 'var(--c-high)' :
    level.key === 'assisted' ? 'var(--c-med)' :
    'var(--brand)'
  );
</script>

<div style="display:flex;flex-direction:column;align-items:center;padding:8px 0;">
  <div style="width:180px;height:180px;">
    <ArcChart
      data={[{ key: 'progress', label: 'Progress', value: progress * 100 }]}
      key="key"
      label="label"
      value="value"
      maxValue={100}
      range={[0, 360]}
      innerRadius={0.65}
      outerRadius={0.9}
      cornerRadius={8}
      padAngle={0}
      tooltipContext={false}
      series={[{ key: 'progress', color: barColor }]}
      props={{ arc: { track: { fill: 'var(--surface-3)', fillOpacity: 1 } } }}
    />
  </div>

  <div style="text-align:center;margin-top:0;">
    <div style="display:inline-flex;align-items:center;gap:6px;padding:5px 14px;border-radius:99px;font-size:13px;font-weight:700;background:{level.key === 'trusted' ? 'var(--c-high-tint)' : level.key === 'assisted' ? 'var(--c-med-tint)' : 'var(--brand-tint)'};color:{level.key === 'trusted' ? 'var(--c-high-ink)' : level.key === 'assisted' ? 'var(--c-med-ink)' : 'var(--brand-ink)'};">
      <span class="dot" style="width:7px;height:7px;border-radius:50%;background:{barColor};"></span>
      {level.label}
    </div>
    {#if nextMilestone !== null}
      <div style="font-size:12px;color:var(--muted);margin-top:8px;font-weight:500;">
        {nextMilestone - verifiedCount} more verification{nextMilestone - verifiedCount === 1 ? '' : 's'} to reach {level.key === 'supervised' ? 'Assisted' : 'Trusted'}
      </div>
    {:else}
      <div style="font-size:12px;color:var(--c-high-ink);margin-top:8px;font-weight:600;">
        Maximum trust level reached
      </div>
    {/if}
  </div>
</div>
