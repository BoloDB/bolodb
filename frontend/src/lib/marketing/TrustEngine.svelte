<script lang="ts">
  import { spotlight } from "$lib/actions/spotlight";
  import { reveal } from "$lib/actions/reveal";

  let flipped = $state(0);

  const sampleSQL =
    "SELECT c.name, SUM(o.amount) AS total\n" +
    "FROM customers c\n" +
    "JOIN orders o ON o.customer_id = c.id\n" +
    "WHERE o.created_at >= date('now','start of month')\n" +
    "GROUP BY c.id\n" +
    "ORDER BY total DESC\n" +
    "LIMIT 3;";
</script>

<section id="trust" class="trust-section">
  <h2 class="section-title">Total transparency into every answer</h2>

  <div class="trust-grid">
    <div class="trust-card" class:is-flipped={flipped === 1} use:spotlight use:reveal>
      <div class="flip-container" onclick={() => flipped = flipped === 1 ? 0 : 1} role="button" tabindex="0" onkeydown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); flipped = flipped === 1 ? 0 : 1; } }} aria-label="Toggle between answer and SQL" aria-pressed={flipped === 1}>
        <div class="flip-inner">
          <div class="flip-front">
            <div class="card-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </div>
            <h4 class="card-title">See every query</h4>
            <p class="card-desc">
              Toggle between the answer and the exact SQL that produced it. Full
              transparency, every time.
            </p>
            <span class="flip-hint">Tap to flip →</span>
          </div>
          <div class="flip-back">
            <div class="back-header">Generated SQL</div>
            <pre class="back-sql" data-lenis-prevent>{sampleSQL}</pre>
            <span class="flip-hint">← Tap for answer</span>
          </div>
        </div>
      </div>
    </div>

    <div class="trust-card" use:spotlight use:reveal>
      <div class="card-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
      </div>
      <h4 class="card-title">Your data stays yours</h4>
      <p class="card-desc">
        Only your database structure and question leave — never your row data.
        Every query runs read-only.
      </p>
      <div class="diagram" aria-label="Data flow diagram">
        <div class="diagram-row">
          <span class="diagram-label">Schema + Question</span>
          <span class="diagram-arrow">→</span>
          <span class="diagram-label diag-green">AI</span>
        </div>
        <div class="diagram-row diag-muted">
          <span class="diagram-label diag-red">Your row data</span>
          <span class="diagram-arrow diag-x">✕</span>
          <span class="diagram-label">Stays home</span>
        </div>
      </div>
    </div>

    <div class="trust-card" use:spotlight use:reveal>
      <div class="card-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
      </div>
      <h4 class="card-title">Confidence you can read</h4>
      <p class="card-desc">
        Every answer shows High, Medium, or Low confidence based on verification
        history and query quality signals.
      </p>
      <div class="conf-examples">
        <span class="conf conf-high"><span class="dot"></span>High confidence</span>
        <span class="conf conf-med"><span class="dot"></span>Medium confidence</span>
        <span class="conf conf-low"><span class="dot"></span>Low confidence</span>
      </div>
    </div>
  </div>
</section>

<style>
  .trust-section {
    position: relative;
    z-index: 2;
    max-width: 1100px;
    margin: 0 auto;
    padding: 100px 24px;
    text-align: center;
  }

  .section-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--faint);
    font-family: var(--font-mono);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 0 0 8px;
  }

  .section-title {
    font-size: clamp(1.5rem, 3.5vw, 2.25rem);
    font-weight: 700;
    color: var(--ink);
    margin: 0 0 60px;
    line-height: 1.2;
    text-wrap: balance;
  }

  .trust-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }

  .trust-grid :global(.trust-card:first-child) {
    grid-column: 1 / -1;
  }

  @media (max-width: 768px) {
    .trust-grid {
      grid-template-columns: 1fr;
      max-width: 420px;
      margin: 0 auto;
    }
    .trust-grid :global(.trust-card:first-child) {
      grid-column: 1;
    }
  }

  .trust-card {
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 28px 24px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    text-align: center;
    cursor: default;
    --mx: 50%;
    --my: 50%;
    transition: box-shadow 0.25s var(--ease);
  }

  .trust-card::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at var(--mx) var(--my), var(--brand-tint) 0%, transparent 60%);
    pointer-events: none;
  }

  .trust-card:hover {
    box-shadow: var(--shadow-lg);
  }

  /* 3D flip card */
  .flip-container {
    width: 100%;
    height: 260px;
    perspective: 800px;
    cursor: pointer;
    border-radius: var(--radius-sm);
  }
  .flip-container:focus-visible {
    outline: none;
    box-shadow: 0 0 0 4px var(--ring);
  }

  .flip-inner {
    position: relative;
    width: 100%;
    height: 100%;
    transition: transform 0.5s var(--ease);
    transform-style: preserve-3d;
  }

  .is-flipped .flip-inner {
    transform: rotateY(180deg);
  }

  .flip-front,
  .flip-back {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
  }

  .flip-back {
    transform: rotateY(180deg);
    padding: 20px;
  }

  .flip-hint {
    font-size: 11px;
    color: var(--faint);
    font-weight: 500;
  }

  .back-header {
    font-size: 11px;
    font-weight: 600;
    color: var(--muted);
    font-family: var(--font-mono);
    letter-spacing: 0.03em;
  }

  .back-sql {
    margin: 0;
    padding: 12px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    line-height: 1.5;
    color: var(--ink-2);
    background: var(--surface-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    overflow-x: auto;
    text-align: left;
    white-space: pre;
    width: 100%;
    max-height: 160px;
    overflow-y: auto;
  }

  .card-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    border-radius: 14px;
    color: var(--brand);
    background: var(--brand-tint-2);
    flex-shrink: 0;
  }

  .card-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
    margin: 0;
  }

  .card-desc {
    font-size: 14px;
    line-height: 1.6;
    color: var(--muted);
    margin: 0;
    text-wrap: balance;
  }

  .diagram {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    width: 100%;
  }

  .diagram-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 600;
  }

  .diagram-label {
    padding: 4px 10px;
    border-radius: 6px;
    background: var(--surface-2);
    color: var(--ink-2);
    font-family: var(--font-mono);
  }

  .diagram-arrow {
    color: var(--faint);
  }

  .diag-green {
    background: var(--c-high-tint);
    color: var(--c-high-ink);
  }

  .diag-red {
    background: var(--c-low-tint);
    color: var(--c-low-ink);
  }

  .diag-muted { opacity: 0.55; }
  .diag-x { color: var(--c-low); }

  .conf-examples {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }

  .conf {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 12px 5px 10px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 700;
  }
  .conf .dot { width: 8px; height: 8px; border-radius: 50%; }
  .conf-high { color: var(--c-high-ink); background: var(--c-high-tint); }
  .conf-high .dot { background: var(--c-high); }
  .conf-med { color: var(--c-med-ink); background: var(--c-med-tint); }
  .conf-med .dot { background: var(--c-med); }
  .conf-low { color: var(--c-low-ink); background: var(--c-low-tint); }
  .conf-low .dot { background: var(--c-low); }
</style>
