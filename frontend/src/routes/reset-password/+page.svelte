<script lang="ts">
  import { apiCall } from "$lib/api";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import Logo from "$lib/components/ui/Logo.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";

  let password = $state("");
  let showPassword = $state(false);
  let loading = $state(false);
  let error = $state("");
  let done = $state(false);

  const token = $derived($page.url.searchParams.get("token") || "");

  const passwordRules = [
    { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
    { label: "One uppercase letter (A-Z)", test: (p: string) => /[A-Z]/.test(p) },
    { label: "One lowercase letter (a-z)", test: (p: string) => /[a-z]/.test(p) },
    { label: "One number (0-9)", test: (p: string) => /[0-9]/.test(p) },
  ];
  const passwordChecks = $derived(passwordRules.map((r) => ({ label: r.label, met: r.test(password) })));
  const passwordValid = $derived(passwordChecks.every((c) => c.met));
  const canSubmit = $derived(!!token && passwordValid && !loading);

  async function submit(e: Event) {
    e.preventDefault();
    if (!canSubmit) return;
    loading = true;
    error = "";
    try {
      await apiCall("/api/auth/reset-password", { token, new_password: password });
      done = true;
      setTimeout(() => goto("/login"), 2500);
    } catch (err: any) {
      error = err.message || "Reset failed. The link may have expired.";
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Reset Password — BoloDB</title>
</svelte:head>

<div class="auth-page">
  <div class="card rise auth-card" data-testid="reset-password-card">
    <div class="auth-header">
      <div class="auth-logo-wrap"><Logo size={40} /></div>
      <h1 class="auth-title">Set a new password</h1>
      <p class="auth-subtitle">Choose a strong password to secure your account.</p>
    </div>

    {#if !token}
      <div class="auth-error" role="alert" data-testid="reset-no-token">
        This link is invalid or missing a reset token. Please request a new reset link.
      </div>
      <div class="auth-footer">
        <a href="/forgot-password">Request a new link →</a>
      </div>
    {:else if done}
      <div role="status" aria-live="polite" class="auth-success" data-testid="reset-success">
        Password reset successfully.<br />
        Redirecting you to sign in…
      </div>
    {:else}
      <form onsubmit={submit} class="auth-form" data-testid="reset-password-form">
        <div>
          <label for="password" class="auth-label">New password</label>
          <div class="auth-field-wrap">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              class="field"
              bind:value={password}
              placeholder="••••••••"
              style="padding-right:42px"
              data-testid="reset-password-input"
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
          <div role="alert" aria-live="polite" class="auth-error" data-testid="reset-error-message">
            {error}
          </div>
        {/if}

        <Button
          kind="primary"
          class="btn-block"
          disabled={!canSubmit}
          data-testid="reset-submit-button"
        >
          {#snippet icon()}
            {#if loading}<Spinner />{/if}
          {/snippet}
          {loading ? "Resetting…" : "Reset password"}
        </Button>
      </form>
    {/if}
  </div>
</div>
