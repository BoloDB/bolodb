<script lang="ts">
  import { glossary as defaultGlossary, starters as defaultStarters } from '$lib/data';
  import { apiCall } from '$lib/api';
  import type { SchemaTable, DbInfo, GlossaryItem, StarterItem } from '$lib/types';
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

  const stepIndex = $derived(step === 'profile' ? 0 : step === 'glossary' ? 1 : 2);

  async function loadOnboardData() {
    loadErr = '';
    const errors: string[] = [];
    try {
      const [g, s] = await Promise.allSettled([
        apiCall('/api/onboard/glossary', {}),
        apiCall('/api/onboard/starters', {})
      ]);
      realGlossary = g.status === 'fulfilled' ? (g.value.glossary || []) : defaultGlossary;
      realStarters = s.status === 'fulfilled' ? (s.value.starters || []) : defaultStarters;
      if (g.status === 'rejected') errors.push('glossary');
      if (s.status === 'rejected') errors.push('starters');
      if (errors.length) {
        loadErr = `Failed to load ${errors.join(' and ')} — using built-in examples instead.`;
      }
    } catch (e: any) {
      loadErr = e.message || "Couldn't reach the AI — using built-in examples instead.";
      realGlossary = defaultGlossary;
      realStarters = defaultStarters;
    }
  }
</script>

<div class="ob">
  <div class="ob-logo">
    <svg width="26" height="26" viewBox="0 0 256 256" fill="none">
      <path d="M 52 44 Q 52 30 66 30 L 190 30 Q 204 30 204 44 L 204 138 Q 204 152 190 152 L 116 152 L 88 176 L 92 152 L 66 152 Q 52 152 52 138 Z" stroke="var(--brand)" stroke-width="6" fill="none" />
      <g stroke="var(--brand)" stroke-width="6" stroke-linecap="round" fill="none">
        <ellipse cx="128" cy="66" rx="34" ry="11" />
        <path d="M 94 66 L 94 108 Q 94 119 128 119 Q 162 119 162 108 L 162 66" />
        <path d="M 94 87 Q 94 98 128 98 Q 162 98 162 87" />
      </g>
      <circle cx="182" cy="46" r="3.5" fill="var(--brand)" />
    </svg>
    <span class="ob-name">Bolo<span style="color:var(--brand)">DB</span></span>
  </div>

  <div class="ob-dots" data-testid="onboard-stepper">
    {#each [0, 1, 2] as i}
      <span class="dot" style="width:{i === stepIndex ? '26px' : '10px'};background:{i <= stepIndex ? 'var(--brand)' : 'var(--surface-3)'}"></span>
    {/each}
  </div>

  {#if loadErr}
    <div class="ob-err">
      <b>AI not available:</b> {loadErr} Setup continues with example data — you can re-run it later from Settings.
    </div>
  {/if}

  <div class="ob-step">
    {#if step === 'profile'}
      <ProfileStep onNext={async () => { await loadOnboardData(); step = 'glossary'; }} {schema} />
    {:else if step === 'glossary'}
      <GlossaryStep glossaryItems={realGlossary} onNext={(g) => { confirmedGlossary = g; step = 'starters'; }} onBack={() => { step = 'profile'; }} />
    {:else if step === 'starters'}
      <StartersStep starterItems={realStarters} glossary={confirmedGlossary || []} {onDone} onBack={() => { step = 'glossary'; }} />
    {/if}
  </div>

  <div class="ob-footer">READ-ONLY · NO TELEMETRY · YOUR ROWS NEVER LEAVE</div>
</div>

<style>
  .ob {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 24px 40px;
    min-height: 100vh;
    box-sizing: border-box;
    background: radial-gradient(1000px 600px at 50% -10%, rgba(var(--glow-rgb), 0.1) 0%, transparent 60%), var(--bg);
  }
  .ob-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 40px;
  }
  .ob-name {
    font-weight: 800;
    font-size: 17px;
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .ob-dots {
    display: flex;
    gap: 8px;
    margin-bottom: 44px;
  }
  .dot {
    height: 6px;
    border-radius: 99px;
    transition: all 0.4s var(--ease);
  }
  .ob-err {
    max-width: 560px;
    width: 100%;
    margin-bottom: 20px;
    padding: 11px 15px;
    background: var(--c-med-tint);
    border: 1px solid var(--border-2);
    border-radius: var(--radius-sm);
    color: var(--med-ink);
    font-size: 13px;
    font-weight: 550;
    line-height: 1.5;
  }
  .ob-step {
    width: 100%;
    display: flex;
    justify-content: center;
  }
  .ob-footer {
    margin-top: auto;
    padding-top: 40px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.1em;
    color: var(--faint);
  }
</style>
