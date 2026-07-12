<script lang="ts">
  import { onMount } from 'svelte';
  import { googleLogin } from '$lib/api';

  let {
    onSuccess,
    mode = 'signin',
  }: {
    onSuccess: () => void;
    mode?: 'signin' | 'signup';
  } = $props();

  let error = $state('');
  let loading = $state(false);
  let containerEl = $state<HTMLDivElement>();
  let scriptLoaded = $state(false);
  let clientId = $state('');

  function handleCredentialResponse(response: google.accounts.id.CredentialResponse) {
    loading = true;
    error = '';
    googleLogin(response.credential)
      .then(() => onSuccess())
      .catch((err: any) => {
        error = err.message || 'Google sign-in failed';
      })
      .finally(() => {
        loading = false;
      });
  }

  onMount(() => {
    const existing = document.getElementById('gsi-script');
    if (!existing) {
      const script = document.createElement('script');
      script.id = 'gsi-script';
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = () => { scriptLoaded = true; };
      document.head.appendChild(script);
    } else {
      scriptLoaded = true;
    }

    fetchClientId();
  });

  async function fetchClientId() {
    try {
      const { apiCall } = await import('$lib/api');
      const data = await apiCall('/api/config/public');
      if (data.google_client_id) {
        clientId = data.google_client_id;
        // googleLogin() reads this when POSTing to /api/auth/google; without it
        // the request sends an empty client_id and the backend rejects every
        // sign-in with "Client ID mismatch".
        window.__GOOGLE_CLIENT_ID__ = data.google_client_id;
      }
    } catch {
      error = 'Google sign-in is not configured';
    }
  }

  $effect(() => {
    if (containerEl && scriptLoaded && clientId && typeof google !== 'undefined') {
      google.accounts.id.initialize({
        client_id: clientId,
        callback: handleCredentialResponse,
      });
      google.accounts.id.renderButton(containerEl, {
        theme: 'outline',
        size: 'large',
        width: 320,
        shape: 'pill',
      });
    }
  });
</script>

<div style="text-align:center">
  {#if error}
    <div style="padding:10px 14px;margin-bottom:12px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550">
      {error}
    </div>
  {/if}
  <div bind:this={containerEl} style="display:flex;justify-content:center;min-height:40px;{loading ? 'opacity:0.6;pointer-events:none;' : ''}"></div>
  {#if !clientId && !error}
    <div style="color:var(--muted);font-size:13px;padding:8px 0">
      <span>Loading Google sign-in…</span>
    </div>
  {/if}
</div>
