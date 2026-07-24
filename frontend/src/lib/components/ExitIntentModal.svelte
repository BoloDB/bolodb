<script lang="ts">
  import { browser } from "$app/environment";
  import { onMount } from "svelte";
  import { authModal } from "$lib/stores/authModal";
  import posthog from "posthog-js";
  import { trackCtaClick } from "$lib/marketing/analytics";

  const STORAGE_KEY = "bolodb_exit_intent_shown";
  const DELAY_BEFORE_ARMED_MS = 12000; // wait 12s before arming so users don't see it instantly
  let show = $state(false);
  let armed = false;
  let shownThisMount = false;
  let previouslyFocusedElement: HTMLElement | null = null;
  let modalElement: HTMLDivElement;

  function alreadyShownThisSession(): boolean {
    try {
      return sessionStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  }

  function markShown() {
    try { sessionStorage.setItem(STORAGE_KEY, "1"); } catch {}
  }

  function trigger() {
    if (!armed || show || shownThisMount || alreadyShownThisSession()) return;
    show = true;
    shownThisMount = true;
    markShown();
    posthog.capture("exit_intent_shown");
  }

  function onMouseLeave(e: MouseEvent) {
    // Fires when the cursor exits the viewport at the top edge (going to close/switch tab)
    if (e.clientY <= 0 && e.relatedTarget === null) {
      trigger();
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === "Escape" && show) {
      close();
      return;
    }
    // Trap focus with Tab/Shift+Tab
    if (show && e.key === "Tab" && modalElement) {
      const focusableElements = modalElement.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstFocusable = focusableElements[0] as HTMLElement;
      const lastFocusable = focusableElements[focusableElements.length - 1] as HTMLElement;

      if (e.shiftKey) {
        if (document.activeElement === firstFocusable) {
          lastFocusable?.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastFocusable) {
          firstFocusable?.focus();
          e.preventDefault();
        }
      }
    }
  }

  function close() {
    show = false;
    posthog.capture("exit_intent_dismissed");
    if (previouslyFocusedElement) {
      previouslyFocusedElement.focus();
      previouslyFocusedElement = null;
    }
  }

  function claim() {
    trackCtaClick("exit_intent", "Start for free", "/signup");
    posthog.capture("exit_intent_converted");
    show = false;
    authModal.show("signup");
  }

  $effect(() => {
    if (show && modalElement) {
      previouslyFocusedElement = document.activeElement as HTMLElement;
      const focusableElements = modalElement.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstFocusable = focusableElements[0] as HTMLElement;
      firstFocusable?.focus();
    }
  });

  onMount(() => {
    if (!browser) return;
    if (alreadyShownThisSession()) return;
    const t = setTimeout(() => { armed = true; }, DELAY_BEFORE_ARMED_MS);
    document.addEventListener("mouseleave", onMouseLeave);
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      document.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("keydown", onKey);
    };
  });
</script>

{#if show}
  <div
    class="exit-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="exit-intent-title"
    tabindex="-1"
    data-testid="exit-intent-modal"
    onclick={(e) => { if (e.target === e.currentTarget) close(); }}
    onkeydown={(e) => { if (e.key === "Escape") close(); }}
  >
    <div class="exit-modal" bind:this={modalElement}>
      <button
        class="exit-close"
        onclick={close}
        aria-label="Close"
        data-testid="exit-intent-close"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>

      <div class="exit-icon" aria-hidden="true">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
          <path d="M12 3l1.7 5.1L19 10l-5.3 1.9L12 17l-1.7-5.1L5 10l5.3-1.9L12 3z" fill="currentColor"/>
        </svg>
      </div>

      <h2 id="exit-intent-title" class="exit-title">
        Wait — try it with our sample database.
      </h2>
      <p class="exit-desc">
        No credit card, no database of your own needed. We spin up a realistic
        webshop dataset so you can see BoloDB answer real questions
        in under 30 seconds.
      </p>

      <div class="exit-actions">
        <button
          class="btn btn-primary btn-lg"
          onclick={claim}
          data-testid="exit-intent-cta"
        >
          Start free with sample data
        </button>
        <button
          class="exit-dismiss"
          onclick={close}
          data-testid="exit-intent-dismiss"
        >
          No thanks, I'll leave
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .exit-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    z-index: 10001;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    animation: exitFadeIn 0.2s var(--ease);
  }
  @keyframes exitFadeIn { from { opacity: 0; } to { opacity: 1; } }

  .exit-modal {
    position: relative;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    max-width: 460px;
    width: 100%;
    padding: 36px 32px 28px;
    text-align: center;
    animation: exitPop 0.3s var(--spring);
    overflow: hidden;
  }
  .exit-modal::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
      radial-gradient(600px 200px at 50% 0%, var(--brand-tint) 0%, transparent 60%);
    pointer-events: none;
  }
  @keyframes exitPop {
    from { opacity: 0; transform: translateY(14px) scale(0.95); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  .exit-close {
    position: absolute;
    top: 12px;
    right: 12px;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--muted);
    padding: 8px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color 0.15s, background 0.15s;
    z-index: 1;
  }
  .exit-close:hover {
    color: var(--ink);
    background: var(--surface-2);
  }

  .exit-icon {
    position: relative;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: var(--brand-tint);
    color: var(--brand);
    display: grid;
    place-items: center;
    margin: 0 auto 16px;
  }

  .exit-title {
    position: relative;
    margin: 0 0 10px;
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--ink);
    text-wrap: balance;
  }

  .exit-desc {
    position: relative;
    margin: 0 0 22px;
    color: var(--muted);
    font-size: 14.5px;
    line-height: 1.55;
    text-wrap: balance;
  }

  .exit-actions {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .exit-dismiss {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--faint);
    font-size: 13px;
    font-weight: 550;
    padding: 8px;
    text-decoration: underline;
    text-decoration-color: transparent;
    text-underline-offset: 3px;
    transition: color 0.15s, text-decoration-color 0.15s;
  }
  .exit-dismiss:hover {
    color: var(--muted);
    text-decoration-color: var(--border-2);
  }
</style>
