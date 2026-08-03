<script lang="ts">
  let {
    message = "Loading…",
    submessage = "",
    variant = "default",
    progress = null,
  }: {
    message?: string;
    submessage?: string;
    /**
     * Retained so existing call sites keep working. The design uses a single
     * loading treatment for every context, so this no longer swaps the mark.
     */
    variant?: "default" | "connect" | "query";
    /**
     * 0–100 for a determinate bar. Left null, the bar sweeps instead — most
     * call sites have no real progress to report, and a fake percentage that
     * jumps to 90% and waits is worse than an honest indeterminate one.
     */
    progress?: number | null;
  } = $props();

  const determinate = $derived(
    progress !== null && progress !== undefined && Number.isFinite(progress),
  );
  const pct = $derived(Math.min(100, Math.max(0, progress ?? 0)));
</script>

<div
  class="loading-root"
  role="status"
  aria-live="polite"
  aria-label={message}
  aria-busy="true"
>
  <!--
    The mark draws itself stroke by stroke rather than spinning. Each shape
    runs the same dash animation on a stagger so the outline, the disc and the
    two bands appear in the order you would draw them by hand.
  -->
  <svg
    class="mark"
    width="60"
    height="60"
    viewBox="0 0 256 256"
    fill="none"
    aria-hidden="true"
  >
    <path
      pathLength="1"
      d="M 52 44 Q 52 30 66 30 L 190 30 Q 204 30 204 44 L 204 138 Q 204 152 190 152 L 116 152 L 88 176 L 92 152 L 66 152 Q 52 152 52 138 Z"
      stroke="var(--brand)"
      stroke-width="6"
      fill="none"
    />
    <ellipse
      pathLength="1"
      cx="128"
      cy="66"
      rx="34"
      ry="11"
      stroke="var(--brand)"
      stroke-width="6"
      fill="none"
    />
    <path
      pathLength="1"
      d="M 94 66 L 94 108 Q 94 119 128 119 Q 162 119 162 108 L 162 66"
      stroke="var(--brand)"
      stroke-width="6"
      stroke-linecap="round"
      fill="none"
    />
    <path
      pathLength="1"
      d="M 94 87 Q 94 98 128 98 Q 162 98 162 87"
      stroke="var(--brand)"
      stroke-width="6"
      stroke-linecap="round"
      fill="none"
    />
  </svg>

  <div class="copy">
    <span class="msg">{message}</span>
    {#if submessage}
      <span class="sub">{submessage}</span>
    {/if}
    <div class="track">
      {#if determinate}
        <div class="fill" style="width:{pct}%"></div>
      {:else}
        <div class="fill sweep"></div>
      {/if}
    </div>
  </div>
</div>

<style>
  .loading-root {
    position: absolute;
    inset: 0;
    z-index: 30;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 30px;
    overflow: hidden;
    background:
      radial-gradient(
        1000px 600px at 50% -10%,
        rgba(var(--glow-rgb), 0.1) 0%,
        transparent 60%
      ),
      var(--bg);
    animation: riseIn 0.4s both;
  }

  @keyframes riseIn {
    from {
      opacity: 0;
      transform: translateY(14px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  .mark {
    overflow: visible;
  }
  .mark > * {
    stroke-dasharray: 1;
    animation: signDraw 2.6s cubic-bezier(0.65, 0, 0.35, 1) infinite;
  }
  .mark > *:nth-child(2) {
    animation-delay: 0.15s;
  }
  .mark > *:nth-child(3) {
    animation-delay: 0.3s;
  }
  .mark > *:nth-child(4) {
    animation-delay: 0.45s;
  }

  @keyframes signDraw {
    0%,
    100% {
      stroke-dashoffset: 1;
    }
    50% {
      stroke-dashoffset: 0;
    }
  }

  .copy {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 0 24px;
  }

  .msg {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink-2);
    letter-spacing: -0.005em;
    text-align: center;
  }

  .sub {
    font-size: 12.5px;
    color: var(--faint);
    line-height: 1.5;
    text-align: center;
    max-width: 260px;
  }

  .track {
    width: 120px;
    height: 1px;
    background: var(--border);
    border-radius: 99px;
    overflow: hidden;
  }

  .fill {
    height: 100%;
    background: var(--brand);
    border-radius: 99px;
    transition: width 0.5s cubic-bezier(0.65, 0, 0.35, 1);
  }

  .fill.sweep {
    width: 40%;
    animation: sweep 1.6s ease-in-out infinite;
  }

  @keyframes sweep {
    0% {
      transform: translateX(-120%);
    }
    100% {
      transform: translateX(320%);
    }
  }

  /*
    The mark is the only thing conveying "still working", so it keeps a gentle
    pulse rather than freezing completely when motion is reduced.
  */
  @media (prefers-reduced-motion: reduce) {
    .loading-root {
      animation: none;
    }
    .mark > * {
      stroke-dasharray: none;
      animation: fade 2.4s ease-in-out infinite;
    }
    .fill.sweep {
      width: 100%;
      animation: fade 2.4s ease-in-out infinite;
    }
    @keyframes fade {
      0%,
      100% {
        opacity: 0.35;
      }
      50% {
        opacity: 1;
      }
    }
  }
</style>
