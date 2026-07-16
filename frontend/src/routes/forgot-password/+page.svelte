<script lang="ts">
  import { apiCall } from "$lib/api";
  import Logo from "$lib/components/ui/Logo.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";

  let email = $state("");
  let loading = $state(false);
  let error = $state("");
  let sent = $state(false);

  async function submit(e: Event) {
    e.preventDefault();
    if (!email.trim() || loading) return;
    loading = true;
    error = "";
    try {
      await apiCall("/api/auth/forgot-password", { email: email.trim() });
      sent = true;
    } catch (err: any) {
      error = err.message || "Something went wrong. Please try again.";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Forgot Password — BoloDB</title>
</svelte:head>

<div class="auth-page">
  <div class="card rise auth-card" data-testid="forgot-password-card">
    <div class="auth-header">
      <div class="auth-logo-wrap"><Logo size={40} /></div>
      <h1 class="auth-title">Forgot your password?</h1>
      <p class="auth-subtitle">Enter your email and we'll send reset instructions if you have an account.</p>
    </div>

    {#if sent}
      <div
        role="status"
        aria-live="polite"
        class="auth-success"
        data-testid="forgot-password-sent"
      >
        Check your email for reset instructions.<br />
        If you don't see the message, please check spam.
      </div>
      <div class="auth-footer">
        <a href="/login" data-testid="forgot-back-to-login">← Back to sign in</a>
      </div>
    {:else}
      <form onsubmit={submit} class="auth-form" data-testid="forgot-password-form">
        <div>
          <label for="email" class="auth-label">Email</label>
          <input
            id="email"
            type="email"
            class="field"
            bind:value={email}
            placeholder="you@company.com"
            data-testid="forgot-email-input"
            autocomplete="email"
            required
          />
        </div>

        {#if error}
          <div role="alert" aria-live="polite" class="auth-error" data-testid="forgot-error-message">
            {error}
          </div>
        {/if}

        <Button
          kind="primary"
          class="btn-block"
          disabled={!email.trim() || loading}
          data-testid="forgot-submit-button"
        >
          {#snippet icon()}
            {#if loading}<Spinner />{/if}
          {/snippet}
          {loading ? "Sending…" : "Send reset link"}
        </Button>
      </form>

      <div class="auth-footer">
        Remembered your password? <a href="/login" data-testid="forgot-signin-link">Sign in</a>
      </div>
    {/if}
  </div>
</div>
