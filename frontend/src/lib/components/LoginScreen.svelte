<script lang="ts">
  import { apiCall, isExpectedClientError } from "$lib/api";
  import Logo from "$lib/components/ui/Logo.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import GoogleSignIn from "$lib/components/GoogleSignIn.svelte";
  import posthog from "posthog-js";

  let { onLogin }: { onLogin: () => void } = $props();

  let email = $state("");
  let password = $state("");
  let showPassword = $state(false);
  let loading = $state(false);
  let error = $state("");

  async function login(e: Event) {
    e.preventDefault();
    if (!email || !password) {
      error = "Please enter email and password";
      return;
    }
    loading = true;
    error = "";
    try {
      await apiCall("/api/auth/login", { email, password });
      const anonymousId = Array.from(
        new Uint8Array(
          await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email))
        ).slice(0, 8)
      ).map((b) => b.toString(16).padStart(2, "0")).join("");
      posthog.identify(anonymousId);
      posthog.capture("user_logged_in", { method: "email" });
      onLogin();
    } catch (err: any) {
      error = err.message || "Login failed";
      // Wrong credentials (a 4xx) are expected and already shown to the user —
      // don't report them to error tracking.
      if (!isExpectedClientError(err)) posthog.captureException(err);
    } finally {
      loading = false;
    }
  }
</script>

<div class="auth-page">
  <div class="card rise auth-card" data-testid="login-card">
    <div class="auth-header">
      <div class="auth-logo-wrap"><Logo size={40} /></div>
      <h1 class="auth-title">Welcome back</h1>
      <p class="auth-subtitle">Sign in to your BoloDB account</p>
    </div>

    <form onsubmit={login} class="auth-form" data-testid="login-form">
      <div>
        <label for="email" class="auth-label">Email</label>
        <input
          id="email"
          type="email"
          class="field"
          bind:value={email}
          placeholder="you@company.com"
          data-testid="login-email-input"
          autocomplete="email"
          required
        />
      </div>
      <div>
        <label for="password" class="auth-label">Password</label>
        <div class="auth-field-wrap">
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            class="field"
            bind:value={password}
            placeholder="••••••••"
            style="padding-right:42px"
            data-testid="login-password-input"
            autocomplete="current-password"
            required
          />
          <button
            type="button"
            class="auth-password-toggle"
            onclick={() => (showPassword = !showPassword)}
            aria-label={showPassword ? "Hide password" : "Show password"}
            data-testid="toggle-password-visibility"
          >
            {#if showPassword}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            {:else}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            {/if}
          </button>
        </div>
      </div>

      <div class="auth-forgot-link">
        <a href="/forgot-password" data-testid="login-forgot-link">Forgot password?</a>
      </div>

      {#if error}
        <div role="alert" aria-live="polite" class="auth-error" data-testid="login-error-message">
          {error}
        </div>
      {/if}

      <Button
        kind="primary"
        class="btn-block"
        disabled={loading}
        style="margin-top:4px"
        data-testid="login-submit-button"
      >
        {#snippet icon()}
          {#if loading}<Spinner />{/if}
        {/snippet}
        {loading ? "Signing in…" : "Sign in"}
      </Button>
    </form>

    <div class="auth-divider">
      <span class="auth-divider-line"></span>
      <span class="auth-divider-text">or</span>
      <span class="auth-divider-line"></span>
    </div>

    <GoogleSignIn onSuccess={onLogin} />

    <div class="auth-footer">
      Don't have an account? <a href="/signup" data-testid="login-signup-link">Sign up</a>
    </div>
  </div>
</div>
