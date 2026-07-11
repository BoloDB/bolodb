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
      posthog.identify(email, { email });
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
  style="display:flex;align-items:center;justify-content:center;height:100vh;background:var(--bg)"
>
  <div
    class="card rise"
    style="width:100%;max-width:400px;padding:40px;box-sizing:border-box"
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

    <form onsubmit={login} style="display:flex;flex-direction:column;gap:16px">
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
          required
        />
      </div>
      <div>
        <label
          for="password"
          style="display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em"
          >Password</label
        >
        <input
          id="password"
          type="password"
          class="field"
          bind:value={password}
          placeholder="••••••••"
          style="width:100%;box-sizing:border-box"
          required
        />
      </div>

      {#if error}
        <div
          style="padding:10px 14px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550"
        >
          {error}
        </div>
      {/if}

      <Button
        kind="primary"
        class="btn-block"
        disabled={loading}
        style="margin-top:8px"
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

    <GoogleSignIn onSuccess={onLogin} mode="signin" />

    <div
      style="text-align:center;margin-top:24px;font-size:13.5px;color:var(--muted)"
    >
      Don't have an account? <a
        href="/signup"
        style="color:var(--brand-ink);font-weight:650;text-decoration:none"
        >Sign up</a
      >
    </div>
  </div>
</div>
