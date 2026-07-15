<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { supabaseGoogleLogin } from "$lib/api";

  let error = $state("");
  let processing = $state(true);

  onMount(async () => {
    try {
      const hash = window.location.hash;
      const params = new URLSearchParams(hash.substring(1));
      const accessToken = params.get("access_token");

      if (!accessToken) {
        error = "No access token received from Supabase";
        processing = false;
        return;
      }

      await supabaseGoogleLogin(accessToken);
      window.location.hash = "";
      goto("/chat");
    } catch (err: any) {
      error = err.message || "Authentication failed";
      processing = false;
    }
  });
</script>

<div
  style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:20px"
>
  {#if error}
    <div
      style="padding:16px 24px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:8px;color:#7A5C0A;font-size:14px;max-width:400px;text-align:center"
    >
      <p style="margin:0 0 12px">{error}</p>
      <a
        href="/"
        style="color:#2563EB;text-decoration:underline;cursor:pointer"
        onclick={(e) => {
          e.preventDefault();
          goto("/");
        }}
      >
        Back to login
      </a>
    </div>
  {:else}
    <div style="text-align:center;color:var(--ink-muted);font-size:14px">
      <div
        style="width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 12px"
      ></div>
      Signing you in...
    </div>
  {/if}
</div>

<style>
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
