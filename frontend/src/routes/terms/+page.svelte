<svelte:head>
  <title>Terms of Service — BoloDB</title>
</svelte:head>

<main class="legal-page">
  <h1>Terms of Service</h1>
  <p class="legal-updated">Last updated: July 16, 2026</p>

  <section>
    <h2>Acceptance</h2>
    <p>
      By using BoloDB you agree to these terms. If you do not agree, do not use the service.
    </p>
  </section>

  <section>
    <h2>What BoloDB does</h2>
    <p>
      BoloDB converts plain-English questions into SQL, runs them against your
      database in read-only mode, and returns results with a confidence score.
      It is an open-source tool — you host it yourself.
    </p>
  </section>

  <section>
    <h2>Your data</h2>
    <ul>
      <li>You retain full ownership of all data in your database.</li>
      <li>BoloDB never writes to your database — all queries are read-only.</li>
      <li>Only your schema structure and question are sent to Google Gemini for SQL generation. Row data stays on your machine.</li>
    </ul>
  </section>

  <section>
    <h2>API costs</h2>
    <p>
      SQL generation uses the Google Gemini API. You are responsible for your own
      Gemini API key and any associated costs. BoloDB does not mark up or resell API access.
    </p>
  </section>

  <section>
    <h2>Limitation of liability</h2>
    <p>
      BoloDB is provided "as is" without warranty. We are not responsible for any
      damage arising from use of the service, including but not limited to incorrect
      SQL generation or data loss (though read-only mode prevents the latter).
    </p>
  </section>

  <section>
    <h2>Changes</h2>
    <p>
      We may update these terms from time to time. The "Last updated" date at the top
      will always reflect the most recent revision.
    </p>
  </section>

  <section>
    <h2>Contact</h2>
    <p>
      Questions? Open an issue on
      <a href="https://github.com/HAAHIT/bolodb">GitHub</a>.
    </p>
  </section>
</main>

<style>
  .legal-page {
    max-width: 720px;
    margin: 0 auto;
    padding: 80px 24px 120px;
    color: var(--ink);
  }

  h1 {
    font-size: clamp(1.8rem, 4vw, 2.5rem);
    font-weight: 800;
    margin: 0 0 8px;
    line-height: 1.15;
  }

  .legal-updated {
    font-size: 13px;
    color: var(--faint);
    margin: 0 0 48px;
  }

  section {
    margin-bottom: 40px;
  }

  h2 {
    font-size: 1.15rem;
    font-weight: 700;
    margin: 0 0 12px;
    color: var(--ink);
  }

  p, li {
    font-size: 15px;
    line-height: 1.7;
    color: var(--muted);
  }

  ul {
    padding-left: 20px;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  a {
    color: var(--brand);
    text-decoration: none;
  }
  a:hover { text-decoration: underline; }
</style>
