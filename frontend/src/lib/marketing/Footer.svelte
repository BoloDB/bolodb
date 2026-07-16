<script lang="ts">
  import LL from "$lib/i18n/i18n-svelte";
</script>

<footer class="marketing-footer">
  <div class="footer-inner">
    <div class="footer-left">
      <span class="footer-brand">{$LL.common.appName()}</span>
      <div class="footer-links">
        <a href="https://github.com/HAAHIT/bolodb/tree/master/docs" class="footer-link">Docs</a>
        <a href="https://github.com/HAAHIT/bolodb" class="footer-link">GitHub</a>
        <a href="/privacy" class="footer-link">Privacy</a>
        <a href="/terms" class="footer-link">Terms</a>
      </div>
    </div>

    <div class="footer-right">
      <p class="footer-reassurance">
        Your database data never leaves your machine. Anonymous product analytics only, honors Do Not Track.
      </p>
      <p class="footer-copy">
        {$LL.landing.copyright()}
      </p>
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
    justify-content: space-between;
    align-items: flex-start;
    gap: 32px;
  }

  .footer-left {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .footer-brand {
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
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

  .footer-right {
    text-align: right;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .footer-reassurance {
    font-size: 12px;
    color: var(--faint);
    font-weight: 500;
    letter-spacing: 0.01em;
    margin: 0;
  }

  .footer-copy {
    font-size: 11.5px;
    color: var(--faint);
    margin: 0;
  }

  @media (max-width: 640px) {
    .footer-inner {
      flex-direction: column;
      gap: 24px;
    }
    .footer-right {
      text-align: left;
    }
  }
</style>
