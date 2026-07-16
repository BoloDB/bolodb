<script lang="ts">
  import { goto } from "$app/navigation";
  import { apiCall } from "$lib/api";
  import posthog from "posthog-js";

  let {
    open = false,
    mode = "signup",
    onClose,
  }: {
    open?: boolean;
    mode?: "signup" | "login";
    onClose: () => void;
  } = $props();

  let loading = $state(false);
  let error = $state("");

  const title = $derived(mode === "signup" ? "Get started with BoloDB" : "Welcome back to BoloDB");
  const emailAltLabel = $derived(mode === "signup" ? "Use email instead" : "Sign in with email instead");
  const emailAltPath = $derived(mode === "signup" ? "/signup" : "/login");

  async function handleGoogle() {
    loading = true;
    error = "";
    try {
      const config = await apiCall("/api/config/public");
      const supabaseUrl = config.supabase_url;
      if (!supabaseUrl) {
        error = "Google sign-in isn't configured yet. Please use email instead.";
        loading = false;
        return;
      }
      posthog.capture(mode === "signup" ? "auth_google_started" : "auth_google_login_started");
      const redirectTo = `${window.location.origin}/auth/callback`;
      window.location.href = `${supabaseUrl}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirectTo)}`;
    } catch (e: any) {
      error = e.message || "Google sign-in failed";
      loading = false;
    }
  }

  function handleEmailAlt() {
    posthog.capture(mode === "signup" ? "auth_email_selected" : "auth_email_login_selected");
    onClose();
    goto(emailAltPath);
  }

  function handleBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === "Escape") onClose();
  }

  $effect(() => {
    if (open) {
      window.addEventListener("keydown", handleKey);
      document.body.style.overflow = "hidden";
      return () => {
        window.removeEventListener("keydown", handleKey);
        document.body.style.overflow = "";
      };
    }
  });
</script>

{#if open}
  <div
    class="auth-modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-labelledby="auth-modal-title"
    tabindex="-1"
    data-testid="auth-choice-modal"
    onclick={handleBackdrop}
    onkeydown={(e) => { if (e.key === "Escape") onClose(); }}
  >
    <div class="auth-modal" style="position:relative">
      <button
        class="auth-modal-close"
        onclick={onClose}
        aria-label="Close"
        data-testid="auth-modal-close"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>

      <div style="text-align:center;margin-bottom:24px">
        <h2 id="auth-modal-title" style="margin:0 0 6px;font-size:20px;font-weight:700;letter-spacing:-0.02em;color:var(--ink)">
          {title}
        </h2>
        <p style="margin:0;color:var(--muted);font-size:13.5px;line-height:1.5">
          Continue with Google in one click — or use email if you prefer.
        </p>
      </div>

      {#if error}
        <div
          role="alert"
          aria-live="polite"
          data-testid="auth-modal-error"
          class="auth-error"
          style="margin-bottom:14px"
        >
          {error}
        </div>
      {/if}

      <button
        class="auth-modal-google"
        onclick={handleGoogle}
        disabled={loading}
        data-testid="auth-modal-google-button"
      >
        <svg width="20" height="20" viewBox="0 0 48 48">
          <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"/>
          <path fill="#FF3D00" d="m6.306 14.691 6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"/>
          <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"/>
          <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"/>
        </svg>
        {loading ? "Redirecting…" : "Continue with Google"}
      </button>

      <button
        class="auth-modal-alt"
        onclick={handleEmailAlt}
        data-testid="auth-modal-email-alt"
      >
        {emailAltLabel}
      </button>
    </div>
  </div>
{/if}
