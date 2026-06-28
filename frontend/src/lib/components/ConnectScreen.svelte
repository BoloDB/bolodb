<script lang="ts">
  import { providers } from '$lib/data';
  import { apiCall, } from '$lib/api';
  import { humanError } from '$lib/data';
  import type { DbInfo } from '$lib/types';
  import Logo from '$lib/components/ui/Logo.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import Section from '$lib/components/ui/Section.svelte';
  import EngineCard from '$lib/components/EngineCard.svelte';

  let { engine, setEngine, onConnect }:
    { engine: string; setEngine: (e: string) => void; onConnect: (isSample: boolean, res: DbInfo) => void } = $props();

  const P = providers;
  const DB_TYPES = [
    { id: 'postgresql', label: 'PostgreSQL', port: '5432' },
    { id: 'mysql', label: 'MySQL', port: '3306' },
    { id: 'sqlite', label: 'SQLite', port: null },
    { id: 'mssql', label: 'SQL Server', port: '1433' },
    { id: 'duckdb', label: 'DuckDB', port: null },
  ];
  const API_KEY_LINKS: Record<string, string> = {
    claude: 'https://console.anthropic.com/settings/keys',
    openai: 'https://platform.openai.com/api-keys',
    groq: 'https://console.groq.com/keys',
  };

  let dbType = $state('postgresql');
  let formMode = $state(true);
  let host = $state('localhost');
  let port = $state('5432');
  let user = $state('');
  let password = $state('');
  let dbName = $state('');
  let filePath = $state('');
  let dbUrl = $state('');
  let connecting: string | null = $state(null);
  let error = $state('');
  let ollamaStatus: string | null = $state(null);

  const isFileBased = $derived(dbType === 'sqlite' || dbType === 'duckdb');

  $effect(() => {
    if (engine !== 'ollama') return;
    ollamaStatus = 'loading';
    fetch('/api/ollama-check').then(r => r.json())
      .then(d => ollamaStatus = d.ok ? 'ok' : 'fail')
      .catch(() => ollamaStatus = 'fail');
  });

  function recheckOllama() {
    ollamaStatus = 'loading';
    fetch('/api/ollama-check').then(r => r.json())
      .then(d => ollamaStatus = d.ok ? 'ok' : 'fail')
      .catch(() => ollamaStatus = 'fail');
  }

  function buildUrl(): string {
    if (dbType === 'sqlite') return `sqlite:///${filePath.trim()}`;
    if (dbType === 'duckdb') return filePath.trim() ? `duckdb:///${filePath.trim()}` : 'duckdb://';
    const u = encodeURIComponent(user);
    const p = encodeURIComponent(password);
    const dialect = dbType === 'mssql' ? 'mssql+pyodbc' : dbType;
    const creds = u && p ? `${u}:${p}@` : u ? `${u}@` : '';
    return `${dialect}://${creds}${host.trim()}:${port}/${dbName.trim()}`;
  }

  function canConnect(): boolean {
    if (formMode) {
      if (dbType === 'duckdb') return true;
      if (isFileBased) return filePath.trim().length > 0;
      return !!(host.trim() && user.trim() && dbName.trim());
    }
    return dbUrl.trim().length > 0;
  }

  async function go(kind: string) {
    connecting = kind; error = '';
    try {
      await apiCall('/api/config', { provider: engine });
      let res: DbInfo;
      if (kind === 'sample') {
        res = await apiCall('/api/connect-sample', {});
      } else {
        const url = formMode ? buildUrl() : dbUrl.trim();
        if (!url) { error = 'Please fill in all required fields.'; connecting = null; return; }
        res = await apiCall('/api/connect', { db_url: url });
      }
      onConnect(kind === 'sample', res);
    } catch (e: any) {
      error = humanError(e.message) || 'Connection failed — check your details and try again.';
      connecting = null;
    }
  }
</script>

<div class="page" style="overflow-y:auto">
  <div style="max-width:980px;margin:0 auto;padding:46px 32px 60px">
    <!-- header -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:42px">
      <Logo size={30} sub />
      <span class="chip" style="cursor:default;background:var(--surface);color:var(--muted);border-color:var(--border-2)">
        <span class="pulse" style="width:7px;height:7px;border-radius:99px;background:var(--brand)"></span> Running locally · localhost:4321
      </span>
    </div>

    <!-- hero -->
    <div class="rise" style="margin-bottom:34px">
      <h1 style="font-size:38px;line-height:1.08;letter-spacing:-.03em;margin:0 0 12px;font-weight:800;max-width:600px;text-wrap:balance">
        Ask your data in plain English.<br /><span style="color:var(--brand)">Trust</span> the answer you get back.
      </h1>
      <p style="font-size:16.5px;color:var(--muted);margin:0;max-width:560px;line-height:1.55">
        Pick where the AI runs, connect your database, and start asking questions — no SQL knowledge needed.
      </p>
    </div>

    <!-- step 1 — engine -->
    <Section num="1" title="Choose your AI engine" hint="You can switch anytime in Settings. Not sure? Start with Local — it's free and private.">
      {#snippet children()}
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
          {#each P as p, i}
            <EngineCard provider={p} active={engine === p.id} onclick={() => { setEngine(p.id); error = ''; }} delay={i * 55} />
          {/each}
        </div>

        {#if engine === 'ollama' && ollamaStatus === 'loading'}
          <div style="display:flex;align-items:center;gap:9px;margin-top:12px;padding:12px 15px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border);color:var(--muted);font-size:13.5px">
            <Spinner /> Checking if Ollama is running on this machine…
          </div>
        {/if}
        {#if engine === 'ollama' && ollamaStatus === 'ok'}
          <div style="display:flex;align-items:center;gap:9px;margin-top:12px;padding:12px 15px;background:var(--brand-tint);border-radius:var(--radius-sm);border:1px solid var(--brand-tint-2);color:var(--brand-ink);font-size:13.5px;font-weight:600">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Ollama is running and ready. Your questions will never leave this machine.
          </div>
        {/if}
        {#if engine === 'ollama' && ollamaStatus === 'fail'}
          <div style="margin-top:12px;padding:16px 18px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius);color:#7A5C0A;font-size:13.5px">
            <div style="display:flex;align-items:center;gap:9px;font-weight:700;margin-bottom:8px">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;color:#C2891B"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor"/></svg>
              Ollama isn't running yet
            </div>
            <p style="margin:0 0 10px;font-weight:500;line-height:1.6">Ollama is a free tool that lets AI run entirely on your computer — nothing leaves your machine. You need to install it before you can use the Local option.</p>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
              <a href="https://ollama.com/download" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:7px;padding:9px 15px;background:var(--ink);color:#fff;border-radius:var(--radius-sm);font-weight:700;font-size:13px;text-decoration:none">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                Download Ollama (free)
              </a>
              <button onclick={recheckOllama} style="display:inline-flex;align-items:center;gap:7px;padding:9px 15px;background:transparent;border:1.5px solid #C2891B;color:#7A5C0A;border-radius:var(--radius-sm);font-weight:700;font-size:13px;cursor:pointer">Check again</button>
            </div>
            <div style="font-size:12.5px;font-weight:550;opacity:.85;line-height:1.6">
              After installing Ollama: open a Terminal and run <code style="background:rgba(0,0,0,.09);padding:2px 6px;border-radius:4px;font-family:var(--font-mono)">ollama pull llama3.2</code> to download the model (~2 GB). Then click "Check again."
            </div>
          </div>
        {/if}

        {#if engine !== 'ollama'}
          <div style="display:flex;align-items:center;gap:9px;margin-top:12px;padding:12px 15px;background:var(--surface-2);border-radius:var(--radius-sm);border:1px solid var(--border);color:var(--ink-2);font-size:13.5px">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style="flex-shrink:0;color:var(--muted)"><rect x="5" y="10.5" width="14" height="9.5" rx="2.4" stroke="currentColor" stroke-width="1.8"/><path d="M8 10.5V8a4 4 0 018 0v2.5" stroke="currentColor" stroke-width="1.8"/></svg>
            <span style="flex:1">You'll need an API key to use {P.find(p => p.id === engine)?.name}.
              <a href={API_KEY_LINKS[engine]} target="_blank" rel="noopener" style="color:var(--brand-ink);font-weight:700;text-decoration:none">Get your key here →</a>
              <span style="color:var(--faint);font-size:12.5px">(You'll enter it in Settings after connecting.)</span>
            </span>
          </div>
        {/if}

        <div style="display:flex;align-items:center;gap:9px;margin-top:10px;padding:11px 15px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm);color:var(--brand-ink);font-size:13.5px;font-weight:500">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><rect x="5" y="10.5" width="14" height="9.5" rx="2.4" stroke="currentColor" stroke-width="1.8"/><path d="M8 10.5V8a4 4 0 018 0v2.5" stroke="currentColor" stroke-width="1.8"/></svg>
          Even with a cloud engine, only your <b>database structure and your question</b> are sent — never your actual rows of data.
        </div>
      {/snippet}
    </Section>

    <!-- step 2 — connect -->
    <Section num="2" title="Connect your database" hint="Don't have one yet? Use the sample data to see how it works first.">
      {#snippet children()}
        <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:16px">
          <!-- connection form card -->
          <div class="card" style="padding:22px">
            <div style="display:flex;align-items:center;gap:9px;margin-bottom:16px;font-weight:700;font-size:15px">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="color:var(--brand)"><ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.9"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" stroke="currentColor" stroke-width="1.9"/></svg>
              Your database
            </div>

            <!-- DB type selector -->
            <div style="margin-bottom:16px">
              <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:8px;letter-spacing:.05em;text-transform:uppercase">What type of database?</div>
              <div style="display:flex;flex-wrap:wrap;gap:7px">
                {#each DB_TYPES as dt}
                  <button onclick={() => { dbType = dt.id; if (dt.port) port = dt.port; error = ''; }} class="focusable"
                    style="padding:6px 14px;border-radius:99px;cursor:pointer;font-size:13px;font-weight:650;transition:all .15s;background:{dbType===dt.id?'var(--brand)':'var(--surface-2)'};color:{dbType===dt.id?'#fff':'var(--ink-2)'};border:{dbType===dt.id?'1.5px solid var(--brand)':'1.5px solid var(--border)'}">
                    {dt.label}
                  </button>
                {/each}
              </div>
            </div>

            <!-- Fields -->
            {#if formMode}
              {#if isFileBased}
                <div style="margin-bottom:14px">
                  <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">File path</div>
                  <input class="field mono" bind:value={filePath}
                    placeholder={dbType === 'sqlite' ? '/Users/you/data/mydb.db' : '/Users/you/data/mydb.duckdb'}
                    style="font-size:13.5px;margin-bottom:6px" />
                  <div style="font-size:12px;color:var(--faint);font-weight:550">
                    The full path to your {dbType === 'sqlite' ? '.db or .sqlite' : 'DuckDB'} file on disk.
                    {#if dbType === 'duckdb'} Leave empty to use an in-memory database.{/if}
                  </div>
                </div>
              {:else}
                <div style="display:flex;flex-direction:column;gap:12px;margin-bottom:14px">
                  <div style="display:grid;grid-template-columns:1fr 90px;gap:10px">
                    <div>
                      <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">Host</div>
                      <input class="field" bind:value={host} placeholder="localhost or db.company.com" style="font-size:14px" />
                    </div>
                    <div>
                      <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">Port</div>
                      <input class="field" bind:value={port} placeholder={port} style="font-size:14px" />
                    </div>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                    <div>
                      <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">Username</div>
                      <input class="field" bind:value={user} placeholder="your_username" style="font-size:14px" autocomplete="username" />
                    </div>
                    <div>
                      <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">Password</div>
                      <input class="field" type="password" bind:value={password} placeholder="••••••••" style="font-size:14px" autocomplete="current-password" />
                    </div>
                  </div>
                  <div>
                    <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">Database name</div>
                    <input class="field" bind:value={dbName} placeholder="my_database" style="font-size:14px" />
                  </div>
                </div>
              {/if}
            {:else}
              <div style="margin-bottom:14px">
                <div style="font-size:11.5px;font-weight:700;color:var(--faint);margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">Connection URL</div>
                <input class="field mono" bind:value={dbUrl}
                  placeholder={dbType==='sqlite'?'sqlite:///path/to/file.db':dbType==='mysql'?'mysql://user:pass@localhost:3306/db':'postgresql://user:pass@localhost:5432/db'}
                  style="font-size:13px;margin-bottom:8px" />
                <button onclick={() => formMode = true} style="font-size:12.5px;color:var(--brand-ink);background:none;border:none;cursor:pointer;font-weight:650;padding:0">← Back to the simple form</button>
              </div>
            {/if}

            {#if formMode}
              <button onclick={() => formMode = false} style="font-size:12.5px;color:var(--faint);background:none;border:none;cursor:pointer;font-weight:600;padding:0 0 16px 0;display:block">
                Have a full connection URL? Use that instead →
              </button>
            {/if}

            <Button kind={canConnect() ? 'primary' : 'ghost'} class="btn-block" disabled={!canConnect() || !!connecting} onclick={() => go('url')}>
              {#snippet icon()}
                {#if connecting === 'url'}<Spinner />{:else}<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.9"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" stroke="currentColor" stroke-width="1.9"/></svg>{/if}
              {/snippet}
              {connecting === 'url' ? 'Connecting…' : 'Connect database'}
            </Button>
            <div style="display:flex;align-items:center;gap:7px;margin-top:11px;color:var(--faint);font-size:12.5px">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Tip: use a view-only database account — BoloDB never writes to your data.
            </div>
          </div>

          <!-- sample data card -->
          <button onclick={() => go('sample')} disabled={!!connecting}
            class="card focusable" style="padding:22px;text-align:left;cursor:{connecting?'wait':'pointer'};border:1.5px dashed var(--brand);background:var(--brand-tint);display:flex;flex-direction:column;justify-content:space-between;transition:transform .15s var(--ease)">
            <div>
              <div style="width:40px;height:40px;border-radius:12px;background:var(--brand);color:#fff;display:grid;place-items:center;margin-bottom:14px;box-shadow:var(--shadow-brand)">
                {#if connecting === 'sample'}<Spinner light />{:else}<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 3l1.7 5.1L19 10l-5.3 1.9L12 17l-1.7-5.1L5 10l5.3-1.9L12 3z" fill="currentColor"/></svg>{/if}
              </div>
              <div style="font-weight:700;font-size:16px;color:var(--brand-ink);margin-bottom:5px">{connecting === 'sample' ? 'Building sample data…' : 'Try with sample data'}</div>
              <div style="font-size:13.5px;color:var(--brand-ink);opacity:.85;line-height:1.55">A realistic TechStore e-commerce database, built locally for you. No setup, no credentials, ready in seconds.</div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;margin-top:18px;font-weight:700;font-size:13.5px;color:var(--brand-ink)">
              Start in seconds <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
          </button>
        </div>

        {#if error}
          <div style="margin-top:12px;padding:13px 17px;background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:var(--radius);color:var(--c-low-ink);font-size:13.5px;font-weight:550;line-height:1.55">
            <b>Couldn't connect —</b> {error}
          </div>
        {/if}
      {/snippet}
    </Section>
  </div>
</div>
