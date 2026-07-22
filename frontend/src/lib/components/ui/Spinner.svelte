<script lang="ts">
  let {
    light = false,
    size = 16,
  }: { light?: boolean; size?: number } = $props();
</script>

<span
  class="spin"
  role="status"
  aria-label="Loading"
  style="
    width:{size}px;
    height:{size}px;
    border-radius:99px;
    border:{Math.max(2, size * 0.14)}px solid {light ? 'rgba(255,255,255,.25)' : 'var(--border-2)'};
    border-top-color:{light ? '#fff' : 'var(--brand)'};
    border-right-color:{light ? 'rgba(255,255,255,.6)' : 'rgba(var(--glow-rgb),.5)'};
    display:inline-block;
    flex-shrink:0;
  "
></span>
