<script lang="ts">
  import { trustFor, schemaObjToDisplay } from '$lib/data';
  import { apiCall } from '$lib/api';
  import type { DbInfo, SchemaTable, Toast } from '$lib/types';
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import ConnectScreen from '$lib/components/ConnectScreen.svelte';
  import OnboardScreen from '$lib/components/OnboardScreen.svelte';
  import AskScreen from '$lib/components/AskScreen.svelte';

  let phase: 'loading' | 'connect' | 'onboard' | 'ask' = $state('loading');
  let engine = $state('ollama');
  let modelName = $state('');
  let verifiedCount = $state(0);
  let toast: Toast | null = $state(null);
  let realSchema: SchemaTable[] | null = $state(null);
  let dbInfo: DbInfo | null = $state(null);
  let starters: string[] = $state([]);
  let prevLevel = $state(trustFor(0).key);

  // On mount: check if already connected (restore last session)
  $effect(() => {
    (async () => {
      try {
        const s = await apiCall('/api/state');
        if (s.connected) {
          engine = s.config?.provider || 'ollama';
          modelName = s.config?.model || '';
          verifiedCount = s.trust?.verified || 0;
          dbInfo = s.database || null;
          starters = s.starters || [];
          prevLevel = trustFor(s.trust?.verified || 0).key;
          try {
            const schema = await apiCall('/api/schema');
            realSchema = schemaObjToDisplay(schema);
          } catch {}
          phase = 'ask';
        } else {
          phase = 'connect';
        }
      } catch {
        phase = 'connect';
      }
    })();
  });

  async function onConnect(isSample: boolean, res: DbInfo) {
    if (res) {
      dbInfo = res;
      verifiedCount = res.trust?.verified || 0;
      prevLevel = trustFor(res.trust?.verified || 0).key;
      if (res.starters) starters = res.starters;
      try {
        const schema = await apiCall('/api/schema');
        realSchema = schemaObjToDisplay(schema);
      } catch {}
      if (res.has_knowledge) { phase = 'ask'; return; }
    }
    phase = 'onboard';
  }

  async function onOnboardDone(seedCount: number) {
    try {
      const s = await apiCall('/api/state');
      const n = s.trust?.verified || seedCount;
      verifiedCount = n;
      prevLevel = trustFor(n).key;
      if (s.database) dbInfo = s.database;
      if (s.starters) starters = s.starters;
    } catch {
      verifiedCount = seedCount;
      prevLevel = trustFor(seedCount).key;
    }
    phase = 'ask';
  }

  function onVerify(apiCount?: number) {
    if (apiCount !== undefined) {
      const lv = trustFor(apiCount);
      if (lv.key !== prevLevel) {
        prevLevel = lv.key;
        const msg = lv.key === 'assisted'
          ? { title: 'Accuracy milestone reached', body: 'Confident answers now show immediately — new questions still get a second look.' }
          : { title: 'Fully calibrated', body: 'All answers appear directly now. Reasoning is always one tap away.' };
        toast = msg;
        setTimeout(() => toast = null, 4200);
      }
      verifiedCount = apiCount;
    } else {
      verifiedCount++;
      const lv = trustFor(verifiedCount);
      if (lv.key !== prevLevel) {
        prevLevel = lv.key;
        const msg = lv.key === 'assisted'
          ? { title: 'Accuracy milestone reached', body: 'Confident answers now show immediately — new questions still get a second look.' }
          : { title: 'Fully calibrated', body: 'All answers appear directly now. Reasoning is always one tap away.' };
        toast = msg;
        setTimeout(() => toast = null, 4200);
      }
    }
  }

  async function handleDisconnect() {
    try { await apiCall('/api/disconnect', {}); } catch {}
    dbInfo = null; realSchema = null; verifiedCount = 0; starters = [];
    prevLevel = trustFor(0).key;
    phase = 'connect';
  }
</script>

<svelte:head>
  <title>BoloDB — Ask your data. Trust the answer.</title>
</svelte:head>

<div class="app-shell">
  {#if phase === 'loading'}
    <div style="flex:1;display:flex;align-items:center;justify-content:center">
      <div style="text-align:center">
        <Spinner />
        <div style="margin-top:12px;color:var(--muted);font-size:14px">Connecting...</div>
      </div>
    </div>
  {:else if phase === 'connect'}
    <ConnectScreen {engine} setEngine={(e) => engine = e} {onConnect} />
  {:else if phase === 'onboard'}
    <OnboardScreen onDone={onOnboardDone} {dbInfo} schema={realSchema} />
  {:else if phase === 'ask'}
    <AskScreen
      {engine} setEngine={(e) => engine = e}
      {modelName} setModelName={(m) => modelName = m}
      {verifiedCount} {onVerify}
      onUpdateStarters={(s) => starters = s}
      {toast} {realSchema} {dbInfo} {starters}
      onDisconnect={handleDisconnect}
    />
  {/if}
</div>
