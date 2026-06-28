<script lang="ts">
  let { level = 'medium', reason = '', compact = false }:
    { level?: 'high' | 'medium' | 'low'; reason?: string; compact?: boolean } = $props();

  const map: Record<string, [string, string]> = {
    high: ['conf-high', 'High confidence'],
    medium: ['conf-med', 'Medium confidence'],
    low: ['conf-low', 'Low confidence']
  };

  const cls = $derived(map[level]?.[0] ?? map.medium[0]);
  const label = $derived(map[level]?.[1] ?? map.medium[1]);
</script>

<span class="conf {cls}" title={reason}>
  <span class="dot"></span>
  {compact ? label.split(' ')[0] : label}
</span>
