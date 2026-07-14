<script lang="ts">
  import LL from "$lib/i18n/i18n-svelte";
</script>

<footer class="marketing-footer">
  <div class="footer-inner">
    <div class="footer-col">
      <span class="footer-brand">{$LL.common.appName()}</span>
      <span class="footer-tagline">{$LL.common.tagline()}</span>
    </div>

    <div class="footer-links">
      <a href="https://github.com/HAAHIT/bolodb/tree/master/docs" class="footer-link">Docs</a>
      <a href="https://github.com/HAAHIT/bolodb" class="footer-link">GitHub</a>
      <span class="footer-link">MIT License</span>
    </div>

    <div class="footer-reassurance">
      No telemetry. No cloud sync.
    </div>

    <div class="footer-copy">
      {$LL.landing.copyright()}
    </div>
  </div>
</footer>

<style>
  .marketing-footer {
    position: relative;
    z-index: 2;
    padding: 48px 24px 32px;
    border-top: 1px solid var(--border);
    margin-top: auto;
  }

  .footer-inner {
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
  }

  .footer-col {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .footer-brand {
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
  }

  .footer-tagline {
    font-size: 12px;
    color: var(--faint);
  }

  .footer-links {
    display: flex;
    gap: 16px;
  }

  .footer-link {
    font-size: 13px;
    color: var(--muted);
    text-decoration: none;
    transition: color 0.15s;
  }

  .footer-link:hover {
    color: var(--ink);
  }

  .footer-reassurance {
    font-size: 12px;
    color: var(--faint);
    font-weight: 500;
    letter-spacing: 0.01em;
  }

  .footer-copy {
    font-size: 11.5px;
    color: var(--faint);
    width: 100%;
    text-align: center;
    margin-top: 8px;
  }
</style>
