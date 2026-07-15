<script lang="ts">
  import { apiCall } from "$lib/api";
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
      // Use a hash of the email as the analytics identity — never send
      // plaintext PII to an analytics platform without explicit consent.
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
    data-testid="login-card"
  >
    <div style="text-align:center;margin-bottom:32px">
      <div style="display:flex;justify-content:center;margin-bottom:16px">
        <Logo size={40} />
      </div>
      <h1 style="margin:0;font-size:24px;font-weight:700">Welcome back</h1>
      <p style="margin:8px 0 0;color:var(--muted);font-size:14.5px">
        Sign in to your BoloDB account
      </p>
    </div>

    <form onsubmit={login} style="display:flex;flex-direction:column;gap:16px" data-testid="login-form">
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
          data-testid="login-email-input"
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
            data-testid="login-password-input"
            required
            autocomplete="current-password"
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

      {#if error}
        <div
          role="alert"
          aria-live="polite"
          data-testid="login-error-message"
          style="padding:10px 14px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);color:var(--c-low-ink);font-size:13px;font-weight:550"
        >
          {error}
        </div>
      {/if}

      <Button
        kind="primary"
        class="btn-block"
        disabled={loading}
        style="margin-top:8px"
        data-testid="login-submit-button"
      >
        {#snippet icon()}
          {#if loading}<Spinner />{/if}
        {/snippet}
        {loading ? "Signing in…" : "Sign in"}
      </Button>
    </form>

    <div style="display:flex;align-items:center;gap:12px;margin:20px 0">
      <span style="flex:1;height:1px;background:var(--border)"></span>
      <span style="font-size:12.5px;color:var(--muted);font-weight:500">or</span
      >
      <span style="flex:1;height:1px;background:var(--border)"></span>
    </div>

    <GoogleSignIn onSuccess={onLogin} />

    <div
      style="text-align:center;margin-top:24px;font-size:13.5px;color:var(--muted)"
    >
      Don't have an account? <a
        href="/signup"
        data-testid="login-signup-link"
        style="color:var(--brand-ink);font-weight:650;text-decoration:none"
        >Sign up</a
      >
    </div>
  </div>
</div>
