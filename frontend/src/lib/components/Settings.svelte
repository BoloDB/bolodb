<script lang="ts">
  import { providers } from '$lib/data';
  import { apiCall } from '$lib/api';
  import Button from '$lib/components/ui/Button.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import { onMount } from 'svelte';

  let { engine, setEngine, modelName, setModelName, onClose, onDisconnect }:
    { engine: string; setEngine: (e: string) => void; modelName: string; setModelName: (m: string) => void; onClose: () => void; onDisconnect?: () => void } = $props();

  let sel = $state( (() => engine)() );
  let localModel = $state( (() => modelName || 'llama3.2')() );
  let apiKey = $state('');
  let saving = $state(false);
  let error = $state('');
  let keysSet: Record<string, string> = $state({});
  let editingKey = $state(false);
  const prov = $derived(providers.find(p => p.id === sel)!);
  const currentKeyIsSet = $derived(!!(keysSet[sel]));

  onMount(async () => {
    try {
      const s = await apiCall('/api/state');
      if (s.config?.api_keys_set) {
        keysSet = s.config.api_keys_set;
      }
    } catch {}
  });

  // Reset editing state when switching providers
  $effect(() => {
    sel; // track
    editingKey = false;
    apiKey = '';
  });

  async function save() {
    saving = true; error = '';
    try {
      const body: any = { provider: sel, model: sel === 'ollama' ? localModel : '' };
      if (sel !== 'ollama') {
        if (editingKey && apiKey.trim()) {
          body.api_key = apiKey.trim();
        }
        // If not editing and key is set, don't send anything — preserves existing
      }
      await apiCall('/api/config', body);
      setEngine(sel);
      setModelName(sel === 'ollama' ? localModel : '');
      onClose();
    } catch (e: any) {
      error = e.message || 'Could not save settings.';
      saving = false;
    }
  }

  async function removeKey() {
    saving = true; error = '';
    try {
      await apiCall('/api/config', { provider: sel, clear_api_key: true });
      keysSet = { ...keysSet, [sel]: '' };
      editingKey = false;
      apiKey = '';
      saving = false;
    } catch (e: any) {
      error = e.message || 'Could not remove key.';
      saving = false;
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div onclick={onClose} style="position:fixed;inset:0;z-index:50;background:rgba(20,28,24,.4);backdrop-filter:blur(3px);display:grid;place-items:center;animation:fadein .2s ease both;padding:24px">
  <div onclick={(e) => e.stopPropagation()} class="card" style="width:560px;max-width:100%;padding:0;overflow:hidden;animation:pop .25s var(--spring) both">
    <div style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
      <div style="display:flex;align-items:center;gap:10px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="color:var(--brand)"><circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.9"/><path d="M12 2.5v2.3M12 19.2v2.3M21.5 12h-2.3M4.8 12H2.5M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9L5.3 5.3" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>
        <span style="font-weight:800;font-size:17px">Settings</span>
      </div>
      <button onclick={onClose} aria-label="Close settings" class="btn btn-quiet btn-sm" style="padding:8px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
      </button>
    </div>
    <div style="padding:24px">
      <div style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:12px">AI engine</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px">
        {#each providers as p}
          <button onclick={() => sel = p.id} class="focusable"
            style="display:flex;align-items:center;gap:10px;padding:12px 13px;border-radius:var(--radius-sm);cursor:pointer;text-align:left;background:{sel===p.id?'var(--brand-tint)':'var(--surface-2)'};border:{sel===p.id?'1.5px solid var(--brand)':'1.5px solid var(--border)'};transition:all .15s">
            <span style="width:30px;height:30px;border-radius:8px;flex-shrink:0;display:grid;place-items:center;background:{sel===p.id?'var(--surface)':'var(--surface-3)'};color:{p.id==='ollama'?'var(--brand)':'var(--muted)'}">
              {#if p.id === 'ollama'}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
              {:else}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor"/></svg>
              {/if}
            </span>
            <div style="min-width:0">
              <div style="font-weight:700;font-size:13.5px">{p.name}</div>
              <div style="font-size:11px;color:var(--faint);font-weight:600">{p.cost}</div>
            </div>
          </button>
        {/each}
      </div>

      {#if sel === 'ollama'}
        <div>
          <div style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:8px">Local model</div>
          <select class="field" bind:value={localModel} style="cursor:pointer;font-size:14px">
            <option value="qwen2.5:0.5b">Fast & lightweight — lower accuracy (qwen2.5:0.5b, ~1 GB)</option>
            <option value="llama3.2">Balanced — recommended for most uses (llama3.2, ~4 GB)</option>
            <option value="mistral">Best accuracy — slower to respond (mistral, ~8 GB)</option>
          </select>
          <div style="font-size:12px;color:var(--faint);margin-top:7px;font-weight:550">Not sure? Stay with "Balanced" — it works well for most databases.</div>
          <div style="display:flex;align-items:center;gap:8px;margin-top:10px;padding:10px 13px;background:var(--brand-tint);border-radius:var(--radius-sm);color:var(--brand-ink);font-size:12.5px;font-weight:550">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Fully private — your schema and questions never leave this machine.
          </div>
        </div>
      {:else}
        <div>
          <div style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:8px">{prov.name} API key</div>

          {#if currentKeyIsSet && !editingKey}
            <!-- Key is already configured -->
            <div style="display:flex;align-items:center;gap:10px;padding:12px 15px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm);margin-bottom:10px">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;color:var(--brand)"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <span style="flex:1;font-size:13.5px;font-weight:650;color:var(--brand-ink)">API key configured</span>
              <button onclick={() => { editingKey = true; apiKey = ''; }}
                style="font-size:12.5px;font-weight:700;color:var(--brand-ink);background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:var(--radius-sm);transition:background .15s"
                onmouseenter={(e) => (e.currentTarget as HTMLElement).style.background='var(--brand-tint-2)'}
                onmouseleave={(e) => (e.currentTarget as HTMLElement).style.background='none'}>
                Change
              </button>
              <button onclick={removeKey} disabled={saving}
                style="font-size:12.5px;font-weight:700;color:var(--c-low-ink);background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:var(--radius-sm);transition:background .15s"
                onmouseenter={(e) => (e.currentTarget as HTMLElement).style.background='var(--c-low-tint)'}
                onmouseleave={(e) => (e.currentTarget as HTMLElement).style.background='none'}>
                Remove
              </button>
            </div>
          {:else}
            <!-- No key set, or user is editing -->
            <input class="field mono" type="password" bind:value={apiKey}
              placeholder={sel==='claude'?'sk-ant-•••':sel==='openai'?'sk-•••':'gsk_•••'} style="font-size:13.5px" />
            {#if editingKey}
              <button onclick={() => { editingKey = false; apiKey = ''; }}
                style="font-size:12.5px;color:var(--faint);background:none;border:none;cursor:pointer;font-weight:600;padding:4px 0;margin-top:6px">
                ← Cancel, keep existing key
              </button>
            {/if}
          {/if}

          <div style="display:flex;align-items:center;gap:8px;margin-top:12px;padding:10px 13px;background:var(--c-med-tint);border-radius:var(--radius-sm);color:var(--c-med-ink);font-size:12.5px;font-weight:550">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><rect x="5" y="10.5" width="14" height="9.5" rx="2.4" stroke="currentColor" stroke-width="1.8"/><path d="M8 10.5V8a4 4 0 018 0v2.5" stroke="currentColor" stroke-width="1.8"/></svg>
            Stored locally only. Schema + question are sent to {prov.name} to generate SQL — never your table data.
          </div>
        </div>
      {/if}
    </div>
    {#if error}
      <div style="margin:0 24px 16px;padding:11px 15px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius-sm);color:var(--c-low-ink);font-size:13.5px;font-weight:550">{error}</div>
    {/if}
    <div style="padding:16px 24px;border-top:1px solid var(--border);background:var(--surface-2)">
      {#if onDisconnect}
        <div style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border)">
          <div style="font-size:12.5px;color:var(--faint);margin-bottom:8px;font-weight:550">Want to connect a different database?</div>
          <button onclick={onDisconnect} style="font-size:13px;color:var(--c-low-ink);background:none;border:1px solid #EBC6BD;border-radius:var(--radius-sm);padding:7px 14px;cursor:pointer;font-weight:650">Disconnect &amp; change database</button>
        </div>
      {/if}
      <div style="display:flex;justify-content:flex-end;gap:10px">
        <Button kind="ghost" onclick={onClose}>Cancel</Button>
        <Button kind="primary" disabled={saving} onclick={save}>
          {#snippet icon()}{#if saving}<Spinner />{:else}<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>{/if}{/snippet}
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </div>
  </div>
</div>
