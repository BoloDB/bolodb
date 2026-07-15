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
      await apiCall("/api/auth/signup", { email, password });
      posthog.identify(email, { email });
      posthog.capture("user_signed_up", { method: "email" });
      success = true;
      setTimeout(() => goto("/login"), 2000);
    } catch (err: any) {
      error = err.message || "Signup failed";
      posthog.captureException(err);
    } finally {
      loading = false;
    }
  }
</script>

<div
  class="page"
  style="display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;box-sizing:border-box;background:var(--bg)"
>
  <div
    class="card rise"
    style="width:100%;max-width:400px;padding:40px;box-sizing:border-box"
    data-testid="signup-card"
  >
    <div style="text-align:center;margin-bottom:32px">
      <div style="display:flex;justify-content:center;margin-bottom:16px">
        <Logo size={40} />
      </div>
      <h1 style="margin:0;font-size:24px;font-weight:700">Create an account</h1>
      <p style="margin:8px 0 0;color:var(--muted);font-size:14.5px">
        Join BoloDB today
      </p>
    </div>

    {#if success}
      <div
        role="status"
        aria-live="polite"
        data-testid="signup-success-message"
        style="padding:16px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius);color:var(--brand-ink);text-align:center;font-weight:550;line-height:1.5"
      >
        Account created successfully!<br />
        Redirecting you to login…
      </div>
    {:else}
      <form
        onsubmit={signup}
        style="display:flex;flex-direction:column;gap:16px"
        data-testid="signup-form"
      >
        <div>
          <label
            for="email"
            style="display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em"
            >Email</label
          >
          <input
            id="email"
            type="email"
            class="field"
            bind:value={email}
            placeholder="you@company.com"
            style="width:100%;box-sizing:border-box"
            data-testid="signup-email-input"
            autocomplete="email"
            required
          />
        </div>
        <div>
          <label
            for="password"
            style="display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em"
            >Password</label
          >
          <div style="position:relative">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              class="field"
              bind:value={password}
              placeholder="••••••••"
              style="width:100%;box-sizing:border-box;padding-right:42px"
              data-testid="signup-password-input"
              required
              autocomplete="new-password"
            />
            <button
              type="button"
              onclick={() => (showPassword = !showPassword)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              data-testid="toggle-password-visibility"
              style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;color:var(--muted);display:flex;align-items:center"
            >
              {#if showPassword}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              {:else}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              {/if}
            </button>
          </div>
        </div>

        <ul aria-live="polite" style="list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:5px">
          {#each passwordChecks as check}
            <li style="display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:{check.met ? 'var(--brand-ink)' : 'var(--faint)'};transition:color .15s var(--ease)">
              <span style="width:15px;height:15px;border-radius:50%;flex-shrink:0;display:grid;place-items:center;background:{check.met ? 'var(--brand)' : 'transparent'};border:1.5px solid {check.met ? 'var(--brand)' : 'var(--border-2)'};transition:all .15s var(--ease)">
                {#if check.met}
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                {/if}
              </span>
              {check.label}
            </li>
          {/each}
        </ul>

        {#if error}
          <div
            role="alert"
            aria-live="polite"
            data-testid="signup-error-message"
            style="padding:10px 14px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550"
          >
            {error}
          </div>
        {/if}

        <Button
          kind="primary"
          class="btn-block"
          disabled={!canSubmit}
          style="margin-top:8px"
          data-testid="signup-submit-button"
        >
          {#snippet icon()}
            {#if loading}<Spinner />{/if}
          {/snippet}
          {loading ? "Creating account…" : "Sign up"}
        </Button>
      </form>

      <div
        style="text-align:center;margin-top:24px;font-size:13.5px;color:var(--muted)"
      >
        Already have an account? <a
          href="/login"
          data-testid="signup-signin-link"
          style="color:var(--brand-ink);font-weight:650;text-decoration:none"
          >Sign in</a
        >
      </div>
    {/if}
  </div>
</div>
