<script lang="ts">
  import { glossary as defaultGlossary, starters as defaultStarters } from '$lib/data';
  import { apiCall } from '$lib/api';
  import type { SchemaTable, DbInfo, GlossaryItem, StarterItem } from '$lib/types';
  import Logo from '$lib/components/ui/Logo.svelte';
  import Stepper from '$lib/components/Stepper.svelte';
  import ProfileStep from '$lib/components/ProfileStep.svelte';
  import GlossaryStep from '$lib/components/GlossaryStep.svelte';
  import StartersStep from '$lib/components/StartersStep.svelte';

  let { onDone, dbInfo, schema }:
    { onDone: (count: number) => void; dbInfo: DbInfo | null; schema: SchemaTable[] | null } = $props();

  let step = $state('profile');
  let realGlossary: GlossaryItem[] | null = $state(null);
  let realStarters: StarterItem[] | null = $state(null);
  let confirmedGlossary: any[] | null = $state(null);
  let loadErr = $state('');

  const dbLabel = $derived(dbInfo ? (dbInfo.url || '').split('/').pop() || dbInfo.dialect || 'Your database' : 'Your database');
  const tableLabel = $derived(dbInfo && dbInfo.tables ? `${dbInfo.tables} table${dbInfo.tables === 1 ? '' : 's'}` : '');

  async function loadOnboardData() {
    loadErr = '';
    try {
      const [g, s] = await Promise.all([
        apiCall('/api/onboard/glossary', {}),
        apiCall('/api/onboard/starters', {})
      ]);
      realGlossary = g.glossary || [];
      realStarters = s.starters || [];
    } catch (e: any) {
      loadErr = e.message || "Couldn't reach the AI — using built-in examples instead.";
      realGlossary = defaultGlossary;
      realStarters = defaultStarters;
    }
  }
</script>

<div class="page" style="overflow-y:auto">
  <div style="max-width:760px;margin:0 auto;padding:40px 32px 60px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:30px">
      <Logo size={26} />
      <span class="chip" style="cursor:default;background:var(--surface);color:var(--brand-ink);border-color:var(--brand-tint-2)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.9"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" stroke="currentColor" stroke-width="1.9"/></svg>
        {dbLabel}{tableLabel ? ` · ${tableLabel}` : ''}
      </span>
    </div>

    <Stepper {step} />

    {#if loadErr}
      <div style="margin-bottom:16px;padding:11px 15px;background:#FFF8ED;border:1px solid #F5D78A;border-radius:var(--radius-sm);color:#7A5C0A;font-size:13px;font-weight:550;line-height:1.5">
        <b>AI not available:</b> {loadErr} The setup will continue with example data — you can re-run it later from Settings.
      </div>
    {/if}

    {#if step === 'profile'}
      <ProfileStep onNext={async () => { await loadOnboardData(); step = 'glossary'; }} {schema} />
    {:else if step === 'glossary'}
      <GlossaryStep glossaryItems={realGlossary} onNext={(g) => { confirmedGlossary = g; step = 'starters'; }} />
    {:else if step === 'starters'}
      <StartersStep starterItems={realStarters} glossary={confirmedGlossary || []} {onDone} />
      <div style="margin-top:18px;padding:12px 16px;background:var(--brand-tint);border:1px solid var(--brand-tint-2);border-radius:var(--radius-sm);font-size:12.5px;color:var(--brand-ink);line-height:1.5">
        <strong>Tip:</strong> After setup, go to <strong>Settings → Manage data catalog</strong> to add business terms or use <strong>"Suggest with AI"</strong> — this helps BoloDB understand your data better and improves answer accuracy.
      </div>
    {/if}
  </div>
</div>
