<script lang="ts">
</script>

<section id="flywheel" class="flywheel-section">
  <h2 class="section-title">It learns your database</h2>

  <div class="flywheel-content">
    <div class="flywheel-diagram">
      <div class="flywheel-ring">
        <div class="ring-segment" style="transform: rotate(0deg)">
          <span>Verified</span>
        </div>
        <div class="ring-segment" style="transform: rotate(120deg)">
          <span>Confidence ↑</span>
        </div>
        <div class="ring-segment" style="transform: rotate(240deg)">
          <span>Trust ↑</span>
        </div>
      </div>
      <div class="flywheel-center">↻</div>
    </div>

    <div class="flywheel-stats">
      <div class="stat">
        <span class="stat-placeholder">—</span>
        <span class="stat-label">verified answers</span>
      </div>
      <div class="stat">
        <span class="stat-level">Supervised → Assisted → Trusted</span>
        <span class="stat-label">trust level grows with every verification</span>
      </div>
    </div>
  </div>
</section>

<style>
  .flywheel-section {
    position: relative;
    z-index: 2;
    max-width: 900px;
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
  }

  .flywheel-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 60px;
    flex-wrap: wrap;
  }

  .flywheel-diagram {
    position: relative;
    width: 220px;
    height: 220px;
  }

  .flywheel-ring {
    position: absolute;
    inset: 0;
    animation: spin-slow 20s linear infinite;
  }

  @media (prefers-reduced-motion: reduce) {
    .flywheel-ring {
      animation: none;
    }
  }

  @keyframes spin-slow {
    to { transform: rotate(360deg); }
  }
  @media (prefers-reduced-motion: reduce) {
    .flywheel-ring { animation: none; }
  }

  .ring-segment {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 180px;
    text-align: center;
    transform-origin: 0 0;
  }

  .ring-segment span {
    display: inline-block;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface);
    padding: 4px 12px;
    border-radius: 99px;
    border: 1px solid var(--border);
    white-space: nowrap;
  }

  .flywheel-center {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 56px;
    height: 56px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    color: var(--brand);
    background: var(--brand-tint);
    border: 2px solid var(--brand-tint-2);
  }

  .flywheel-stats {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-value {
    font-size: 48px;
    font-weight: 800;
    color: var(--brand);
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
  }

  .stat-placeholder {
    font-size: 48px;
    font-weight: 800;
    color: var(--faint);
    letter-spacing: -0.03em;
    opacity: 0.5;
  }

  .stat-level {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }

  .stat-label {
    font-size: 13px;
    color: var(--muted);
  }
</style>
