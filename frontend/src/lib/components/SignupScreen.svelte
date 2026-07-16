<script lang="ts">
  import { apiCall } from "$lib/api";
  import Logo from "$lib/components/ui/Logo.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import { goto } from "$app/navigation";
  import posthog from "posthog-js";

  let email = $state("");
  let password = $state("");
  let showPassword = $state(false);
  let loading = $state(false);
  let error = $state("");
  let success = $state(false);

  const passwordRules = [
    { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
    { label: "One uppercase letter (A-Z)", test: (p: string) => /[A-Z]/.test(p) },
    { label: "One lowercase letter (a-z)", test: (p: string) => /[a-z]/.test(p) },
    { label: "One number (0-9)", test: (p: string) => /[0-9]/.test(p) },
  ];

  const passwordChecks = $derived(passwordRules.map((r) => ({ label: r.label, met: r.test(password) })));
  const passwordValid = $derived(passwordChecks.every((c) => c.met));
  const canSubmit = $derived(email.trim().length > 0 && passwordValid && !loading);

  async function signup(e: Event) {
    e.preventDefault();
    if (!canSubmit) return;
    loading = true;
    error = "";
    try {
      const result = await apiCall("/api/auth/signup", { email, password });
      posthog.identify(email, { email });
      posthog.capture("user_signed_up", { method: "email" });
      success = true;
      setTimeout(() => goto(`/verify-email?email=${encodeURIComponent(email)}`), 1500);
    } catch (err: any) {
      error = err.message || "Signup failed";
      posthog.captureException(err);
    } finally {
      loading = false;
    }
  }
</script>

<div class="auth-page">
  <div class="card rise auth-card" data-testid="signup-card">
    <div class="auth-header">
      <div class="auth-logo-wrap"><Logo size={40} /></div>
      <h1 class="auth-title">Create an account</h1>
      <p class="auth-subtitle">Join BoloDB today — no credit card required</p>
    </div>

    {#if success}
      <div
        role="status"
        aria-live="polite"
        class="auth-success"
        data-testid="signup-success-message"
      >
        Account created! Check your email for the verification code.
      </div>
    {:else}
      <form onsubmit={signup} class="auth-form" data-testid="signup-form">
        <div>
          <label for="email" class="auth-label">Email</label>
          <input
            id="email"
            type="email"
            class="field"
            bind:value={email}
            placeholder="you@company.com"
            data-testid="signup-email-input"
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
              data-testid="signup-password-input"
              autocomplete="new-password"
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

        <ul class="auth-checks" aria-live="polite">
          {#each passwordChecks as check}
            <li class="auth-check {check.met ? 'met' : ''}">
              <span class="auth-check-dot">
                {#if check.met}
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {/if}
              </span>
              {check.label}
            </li>
          {/each}
        </ul>

        {#if error}
          <div role="alert" aria-live="polite" class="auth-error" data-testid="signup-error-message">
            {error}
          </div>
        {/if}

        <Button
          kind="primary"
          class="btn-block"
          disabled={!canSubmit}
          style="margin-top:4px"
          data-testid="signup-submit-button"
        >
          {#snippet icon()}
            {#if loading}<Spinner />{/if}
          {/snippet}
          {loading ? "Creating account…" : "Sign up"}
        </Button>
      </form>

      <div class="auth-footer">
        Already have an account? <a href="/login" data-testid="signup-signin-link">Sign in</a>
      </div>
    {/if}
  </div>
</div>
