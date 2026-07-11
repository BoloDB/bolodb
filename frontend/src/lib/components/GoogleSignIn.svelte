<script lang="ts">
  import { onMount } from "svelte";
  import { googleLogin } from "$lib/api";
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
  let containerEl = $state<HTMLDivElement>();

  function handleCredentialResponse(
    response: google.accounts.id.CredentialResponse,
  ) {
    loading = true;
    error = "";
    googleLogin(response.credential)
      .then(() => {
        posthog.capture("google_auth_completed", { mode });
        onSuccess();
      })
      .catch((err: any) => {
        error = err.message || "Google sign-in failed";
        posthog.captureException(err);
      })
      .finally(() => {
        loading = false;
      });
  }

  onMount(() => {
    const existing = document.getElementById("gsi-script");
    if (!existing) {
      const script = document.createElement("script");
      script.id = "gsi-script";
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = initGIS;
      document.head.appendChild(script);
    } else if (typeof google !== "undefined" && google.accounts?.id) {
      initGIS();
    }
  });

  function initGIS() {
    if (!containerEl || typeof google === "undefined") return;
    google.accounts.id.initialize({
      client_id: window.__GOOGLE_CLIENT_ID__ || "",
      callback: handleCredentialResponse,
    });
    google.accounts.id.renderButton(containerEl, {
      theme: "outline",
      size: "large",
      width: 320,
      shape: "pill",
    });
  }

  async function getClientId() {
    if (window.__GOOGLE_CLIENT_ID__) return;
    try {
      const { apiCall } = await import("$lib/api");
      const data = await apiCall("/api/config/public");
      window.__GOOGLE_CLIENT_ID__ = data.google_client_id || "";
      initGIS();
    } catch {
      // Google sign-in not configured
    }
  }

  $effect(() => {
    if (containerEl) {
      if (window.__GOOGLE_CLIENT_ID__) {
        initGIS();
      } else {
        getClientId();
      }
    }
  });
</script>

<div style="text-align:center">
  {#if error}
    <div
      style="padding:10px 14px;margin-bottom:12px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550"
    >
      {error}
    </div>
  {/if}
  <div
    bind:this={containerEl}
    style="display:flex;justify-content:center;{loading
      ? 'opacity:0.6;pointer-events:none;'
      : ''}"
  ></div>
  {#if !window.__GOOGLE_CLIENT_ID__ && !error}
    <button
      onclick={getClientId}
      style="display:inline-flex;align-items:center;gap:10px;padding:10px 24px;border:1px solid var(--border);border-radius:24px;background:var(--surface);color:var(--ink);font-size:14px;font-weight:500;cursor:pointer"
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
  {/if}
</div>
