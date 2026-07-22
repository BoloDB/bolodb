<script lang="ts">
  let {
    message = 'Loading…',
    submessage = '',
    variant = 'default',
  }: {
    message?: string;
    submessage?: string;
    /** 'default' | 'connect' | 'query' */
    variant?: 'default' | 'connect' | 'query';
  } = $props();
</script>

<div class="loading-root" aria-live="polite" aria-label={message}>
  <!-- Radial glow blobs -->
  <div class="blob blob-a"></div>
  <div class="blob blob-b"></div>

  <div class="loading-card">
    <!-- Animated icon -->
    <div class="icon-wrap">
      {#if variant === 'connect'}
        <!-- DB icon with orbit rings -->
        <div class="orbit-ring ring-1"></div>
        <div class="orbit-ring ring-2"></div>
        <svg class="icon-svg" width="28" height="28" viewBox="0 0 24 24" fill="none">
          <ellipse cx="12" cy="6" rx="8" ry="3" stroke="currentColor" stroke-width="1.8"/>
          <path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      {:else if variant === 'query'}
        <!-- Brain / sparkle icon for LLM thinking -->
        <div class="orbit-ring ring-1"></div>
        <div class="orbit-ring ring-2"></div>
        <svg class="icon-svg" width="26" height="26" viewBox="0 0 24 24" fill="none">
          <path d="M12 2l1.09 3.26L16.5 5l-2.5 2.27.82 3.23L12 8.77l-2.82 1.73.82-3.23L7.5 5l3.41.26L12 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
          <path d="M5 15.5a2.5 2.5 0 0 1 2.5-2.5h9A2.5 2.5 0 0 1 19 15.5v1a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 16.5v-1z" stroke="currentColor" stroke-width="1.6"/>
          <path d="M8.5 13V10M12 13V9M15.5 13V11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
      {:else}
        <!-- Default: dots loader -->
        <div class="dots">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      {/if}
    </div>

    <!-- Progress bar -->
    <div class="progress-track">
      <div class="progress-bar"></div>
    </div>

    <!-- Text -->
    <p class="loading-msg">{message}</p>
    {#if submessage}
      <p class="loading-sub">{submessage}</p>
    {/if}
  </div>
</div>

<style>
  .loading-root {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 30;
    overflow: hidden;
    /* Matches the app background */
    background: var(--bg);
    animation: fadeIn 0.22s ease both;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
  }

  /* ---- ambient blobs ---- */
  .blob {
    position: absolute;
    border-radius: 50%;
    filter: blur(72px);
    pointer-events: none;
  }
  .blob-a {
    width: 420px;
    height: 420px;
    background: radial-gradient(circle, rgba(var(--glow-rgb), 0.18) 0%, transparent 70%);
    top: -100px;
    right: -60px;
    animation: driftA 7s ease-in-out infinite alternate;
  }
  .blob-b {
    width: 320px;
    height: 320px;
    background: radial-gradient(circle, rgba(var(--glow-rgb), 0.10) 0%, transparent 70%);
    bottom: -80px;
    left: -60px;
    animation: driftB 9s ease-in-out infinite alternate;
  }
  @keyframes driftA {
    from { transform: translate(0, 0) scale(1); }
    to   { transform: translate(-30px, 30px) scale(1.1); }
  }
  @keyframes driftB {
    from { transform: translate(0, 0) scale(1); }
    to   { transform: translate(20px, -20px) scale(1.08); }
  }

  /* ---- card ---- */
  .loading-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
    padding: 40px 48px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl, 26px);
    box-shadow: var(--shadow-lg);
    max-width: 340px;
    width: 90%;
    animation: cardPop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
    position: relative;
    z-index: 1;
  }
  @keyframes cardPop {
    from { opacity: 0; transform: scale(0.88) translateY(16px); }
    to   { opacity: 1; transform: scale(1) translateY(0); }
  }

  /* ---- icon area ---- */
  .icon-wrap {
    position: relative;
    width: 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .icon-svg {
    color: var(--brand);
    position: relative;
    z-index: 2;
    animation: iconPulse 2.4s ease-in-out infinite;
  }
  @keyframes iconPulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.75; transform: scale(0.92); }
  }

  /* orbit rings */
  .orbit-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1.5px solid transparent;
    border-top-color: var(--brand);
    animation: orbit 1.5s linear infinite;
  }
  .ring-1 {
    inset: 0;
    opacity: 0.55;
  }
  .ring-2 {
    inset: 8px;
    animation-direction: reverse;
    animation-duration: 2.2s;
    border-top-color: var(--accent, var(--brand));
    opacity: 0.35;
  }
  @keyframes orbit {
    to { transform: rotate(360deg); }
  }

  /* ---- dots ---- */
  .dots {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--brand);
    animation: dotBounce 1.2s ease-in-out infinite;
  }
  .dot:nth-child(1) { animation-delay: 0s; }
  .dot:nth-child(2) { animation-delay: 0.18s; }
  .dot:nth-child(3) { animation-delay: 0.36s; }
  @keyframes dotBounce {
    0%, 80%, 100% { transform: scale(0.7); opacity: 0.45; }
    40%           { transform: scale(1.1); opacity: 1; }
  }

  /* ---- progress bar ---- */
  .progress-track {
    width: 100%;
    height: 3px;
    background: var(--surface-3, var(--border));
    border-radius: 99px;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    width: 40%;
    background: linear-gradient(90deg, transparent, var(--brand), var(--accent, var(--brand)), transparent);
    border-radius: 99px;
    animation: progressSweep 1.6s ease-in-out infinite;
  }
  @keyframes progressSweep {
    0%   { transform: translateX(-200%); }
    100% { transform: translateX(350%); }
  }

  /* ---- text ---- */
  .loading-msg {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.015em;
    text-align: center;
  }
  .loading-sub {
    margin: -8px 0 0;
    font-size: 12.5px;
    color: var(--muted);
    text-align: center;
    line-height: 1.5;
  }
</style>
