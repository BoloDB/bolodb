<svelte:head>
  <title>Privacy Policy — BoloDB</title>
</svelte:head>

<main class="legal-page">
  <h1>Privacy Policy</h1>
  <p class="legal-updated">Last updated: July 16, 2026</p>

  <section>
    <h2>What we collect</h2>
    <ul>
      <li><strong>Account info</strong> — email address and hashed password for authentication.</li>
      <li><strong>Database connections</strong> — connection strings are encrypted at rest and used only to run your queries.</li>
      <li><strong>Queries and results</strong> — your questions, generated SQL, and result sets are stored to power the trust flywheel and history.</li>
      <li><strong>Analytics</strong> — anonymous product analytics via PostHog. Respects <code>Do Not Track</code>. No personal data is sent.</li>
    </ul>
  </section>

  <section>
    <h2>What we send externally</h2>
    <ul>
      <li><strong>Schema + your question</strong> — sent to Google Gemini to generate SQL. Your row data never leaves your machine.</li>
      <li><strong>Email</strong> — verification and password-reset emails are sent through MyEmailVerifier and Resend.</li>
    </ul>
  </section>

  <section>
    <h2>What we never do</h2>
    <ul>
      <li>We never sell or share your data with third parties for advertising.</li>
      <li>We never read or transmit your actual database rows.</li>
      <li>We never track you across sites.</li>
    </ul>
  </section>

  <section>
    <h2>Data storage</h2>
    <p>
      User accounts and query history are stored in PostgreSQL (Supabase).
      The local knowledge base is stored in SQLite on your machine.
      Database connection strings are encrypted using Fernet symmetric encryption.
    </p>
  </section>

  <section>
    <h2>Changes</h2>
    <p>
      We may update this policy from time to time. The "Last updated" date at the top
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

  code {
    font-family: var(--font-mono);
    font-size: 13px;
    background: var(--surface-2);
    padding: 2px 6px;
    border-radius: 4px;
  }
</style>
