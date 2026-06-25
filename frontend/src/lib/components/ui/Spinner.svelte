<script lang="ts">
  let { light = false }: { light?: boolean } = $props();
</script>

<span
  class="spin"
  style="width:16px;height:16px;border-radius:99px;border:2.2px solid {light ? 'rgba(255,255,255,.4)' : 'var(--border-2)'};border-top-color:{light ? '#fff' : 'var(--brand)'};display:inline-block"
></span>
