<script lang="ts">
  import { apiCall } from "$lib/api";
  import { appState } from "$lib/appState.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import Logo from "$lib/components/ui/Logo.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import posthog from "posthog-js";

  let email = $derived($page.url.searchParams.get("email") || "");
  let code = $state("");
  let loading = $state(false);
  let error = $state("");
  let resendLoading = $state(false);
  let resendSuccess = $state(false);
  let cooldown = $state(0);

  let cooldownInterval: ReturnType<typeof setInterval> | undefined;

  function startCooldown() {
    cooldown = 60;
    cooldownInterval = setInterval(() => {
      cooldown -= 1;
      if (cooldown <= 0) {
        clearInterval(cooldownInterval);
        cooldown = 0;
      }
    }, 1000);
  }

  async function verify(e: Event) {
    e.preventDefault();
    if (!code.trim() || loading || !email) return;
    loading = true;
    error = "";
    try {
      await apiCall("/api/auth/verify-email", { email, code: code.trim() });
      posthog.capture("email_verified", { method: "otp" });

      // Let appState init handle where they should go based on their state
      appState.isLoaded = false;
      await appState.init(true);
    } catch (err: any) {
      error = err.message || "Verification failed";
      posthog.captureException(err);
    } finally {
      loading = false;
    }
  }

  async function resend() {
    if (resendLoading || cooldown > 0 || !email) return;
    resendLoading = true;
    resendSuccess = false;
    error = "";
    try {
      await apiCall("/api/auth/resend-verification", { email });
      resendSuccess = true;
      startCooldown();
    } catch (err: any) {
      error = err.message || "Failed to resend code";
    } finally {
      resendLoading = false;
    }
  }
</script>

<svelte:head>
  <title>Verify Email — BoloDB</title>
</svelte:head>

<div class="auth-page">
  <div class="card rise auth-card" data-testid="verify-email-card">
    <div class="auth-header">
      <div class="auth-logo-wrap"><Logo size={40} /></div>
      <h1 class="auth-title">Check your email</h1>
      <p class="auth-subtitle">
        We sent a 6-digit code to<br />
        <strong>{email || "your email"}</strong>
      </p>
    </div>

    <form onsubmit={verify} class="auth-form" data-testid="verify-email-form">
      <div>
        <label for="code" class="auth-label">Verification code</label>
        <input
          id="code"
          type="text"
          inputmode="numeric"
          maxlength="6"
          class="field otp-input"
          bind:value={code}
          placeholder="000000"
          autocomplete="one-time-code"
          data-testid="verify-email-code-input"
          required
        />
      </div>

      {#if error}
        <div role="alert" aria-live="polite" class="auth-error" data-testid="verify-email-error">
          {error}
        </div>
      {/if}

      {#if resendSuccess}
        <div role="status" aria-live="polite" class="auth-success" data-testid="verify-email-resent">
          New code sent. Check your inbox.
        </div>
      {/if}

      <Button
        kind="primary"
        class="btn-block"
        disabled={!code.trim() || code.trim().length < 6 || loading}
        style="margin-top:4px"
        data-testid="verify-email-submit-button"
      >
        {#snippet icon()}
          {#if loading}<Spinner />{/if}
        {/snippet}
        {loading ? "Verifying…" : "Verify & sign in"}
      </Button>
    </form>

    <div class="auth-footer">
      {#if cooldown > 0}
        <span class="verify-cooldown">Resend code in {cooldown}s</span>
      {:else}
        <button
          type="button"
          class="verify-resend-btn"
          onclick={resend}
          disabled={resendLoading}
          data-testid="verify-email-resend-button"
        >
          {resendLoading ? "Sending…" : "Resend code"}
        </button>
      {/if}
    </div>

    <div class="auth-footer">
      <a href="/login" data-testid="verify-email-back-link">← Back to sign in</a>
    </div>
  </div>
</div>

<style>
  .otp-input {
    text-align: center;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.3em;
    font-family: var(--font-mono);
    padding: 14px 16px;
  }

  .verify-cooldown {
    font-size: 13px;
    color: var(--faint);
  }

  .verify-resend-btn {
    background: none;
    border: none;
    color: var(--brand);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    padding: 0;
    font-family: inherit;
  }
  .verify-resend-btn:hover {
    text-decoration: underline;
  }
  .verify-resend-btn:disabled {
    color: var(--faint);
    cursor: not-allowed;
  }
</style>
