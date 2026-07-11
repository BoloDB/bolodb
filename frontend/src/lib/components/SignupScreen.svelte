<script lang="ts">
  import { apiCall } from '$lib/api';
  import Logo from '$lib/components/ui/Logo.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import { goto } from '$app/navigation';

  let email = $state('');
  let password = $state('');
  let loading = $state(false);
  let error = $state('');
  let success = $state(false);

  async function signup(e: Event) {
    e.preventDefault();
    if (!email || !password) { error = 'Please enter email and password'; return; }
    loading = true; error = '';
    try {
      await apiCall('/api/auth/signup', { email, password });
      success = true;
      setTimeout(() => goto('/login'), 2000);
    } catch (err: any) {
      error = err.message || 'Signup failed';
    } finally {
      loading = false;
    }
  }
</script>

<div class="page" style="display:flex;align-items:center;justify-content:center;height:100vh;background:var(--bg)">
  <div class="card rise" style="width:100%;max-width:400px;padding:40px;box-sizing:border-box">
    <div style="text-align:center;margin-bottom:32px">
      <div style="display:flex;justify-content:center;margin-bottom:16px"><Logo size={40} /></div>
      <h1 style="margin:0;font-size:24px;font-weight:700">Create an account</h1>
      <p style="margin:8px 0 0;color:var(--muted);font-size:14.5px">Join BoloDB today</p>
    </div>

    {#if success}
      <div style="padding:16px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius);color:var(--brand-ink);text-align:center;font-weight:550;line-height:1.5">
        Account created successfully!<br/>
        Redirecting you to login…
      </div>
    {:else}
      <form onsubmit={signup} style="display:flex;flex-direction:column;gap:16px">
        <div>
          <label for="email" style="display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Email</label>
          <input id="email" type="email" class="field" bind:value={email} placeholder="you@company.com" style="width:100%;box-sizing:border-box" required />
        </div>
        <div>
          <label for="password" style="display:block;font-size:12px;font-weight:700;color:var(--faint);margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">Password</label>
          <input id="password" type="password" class="field" bind:value={password} placeholder="••••••••" style="width:100%;box-sizing:border-box" required minlength="8" />
        </div>

        {#if error}
          <div style="padding:10px 14px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550">
            {error}
          </div>
        {/if}

        <Button kind="primary" class="btn-block" disabled={loading} style="margin-top:8px">
          {#snippet icon()}
            {#if loading}<Spinner />{/if}
          {/snippet}
          {loading ? 'Creating account…' : 'Sign up'}
        </Button>
      </form>

      <div style="text-align:center;margin-top:24px;font-size:13.5px;color:var(--muted)">
        Already have an account? <a href="/login" style="color:var(--brand-ink);font-weight:650;text-decoration:none">Sign in</a>
      </div>
    {/if}
  </div>
</div>

