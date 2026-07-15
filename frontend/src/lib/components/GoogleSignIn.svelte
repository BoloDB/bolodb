<script lang="ts">
  import { onMount } from "svelte";
  import { apiCall } from "$lib/api";
  import posthog from "posthog-js";

  let {
    onSuccess,
    mode = "signin",
  }: {
    onSuccess: () => void;
    mode?: "signin" | "signup";
  } = $props();

  let error = $state("");
  let loading = $state(false);

  async function handleSupabaseGoogle() {
    loading = true;
    error = "";
    try {
      // Fetch Supabase project URL and anon key from backend
      const config = await apiCall("/api/config/public");
      const supabaseUrl = config.supabase_url;
      const supabaseAnonKey = config.supabase_anon_key;
      if (!supabaseUrl || !supabaseAnonKey) {
        throw new Error("Google sign-in is not configured");
      }
      // Redirect to Supabase Google OAuth
      const redirectTo = `${window.location.origin}/auth/callback`;
      const supabaseAuthUrl = `${supabaseUrl}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirectTo)}`;
      window.location.href = supabaseAuthUrl;
    } catch (err: any) {
      error = err.message || "Google sign-in failed";
      posthog.captureException(err);
      loading = false;
    }
  }
</script>

<div style="text-align:center">
  {#if error}
    <div
      style="padding:10px 14px;margin-bottom:12px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550"
    >
      {error}
    </div>
  {/if}
  <button
    onclick={handleSupabaseGoogle}
    disabled={loading}
    data-testid="google-signin-button"
    aria-label="Continue with Google"
    style="display:inline-flex;align-items:center;gap:10px;padding:10px 24px;border:1px solid var(--border);border-radius:24px;background:var(--surface);color:var(--ink);font-size:14px;font-weight:500;cursor:pointer;transition:border-color 0.15s, background-color 0.15s;{loading
      ? 'opacity:0.6;pointer-events:none;'
      : ''}"
  >
    <svg width="20" height="20" viewBox="0 0 48 48"
      ><path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      /><path
        fill="#FF3D00"
        d="m6.306 14.691 6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      /><path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      /><path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      /></svg
    >
    Continue with Google
  </button>
</div>
