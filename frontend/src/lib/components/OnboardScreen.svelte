<script lang="ts">
  import { apiCall } from '$lib/api';
  import type { SchemaTable, DbInfo } from '$lib/types';
  import ProfileStep from '$lib/components/ProfileStep.svelte';
  import { appState } from '$lib/appState.svelte';
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';

  let { onDone, dbInfo, schema, onChangeDb }:
    { onDone: (count: number) => void; dbInfo: DbInfo | null; schema: SchemaTable[] | null; onChangeDb?: () => void } = $props();

  let saving = $state(false);

  async function finishOnboarding() {
    saving = true;
    try {
      await apiCall('/api/onboard/save', { starters: [] });
      onDone(0);
    } catch (e: any) {
      console.error(e);
      appState.showError("Failed to save onboarding data. Please try again.");
      saving = false;
    }
  }
</script>

<div class="ob">
  {#if onChangeDb}
    <button class="ob-change-db" onclick={onChangeDb} data-testid="onboard-change-db">← Change database</button>
  {/if}
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

  <div class="ob-step">
    {#if saving}
      <LoadingScreen variant="default" message="Preparing your workspace..." />
    {:else}
      <ProfileStep onNext={finishOnboarding} {schema} />
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
    position: relative;
    background: radial-gradient(1000px 600px at 50% -10%, rgba(var(--glow-rgb), 0.1) 0%, transparent 60%), var(--bg);
  }
  .ob-change-db {
    position: absolute;
    top: 20px;
    left: 20px;
    background: transparent;
    border: 1px solid var(--border-2);
    color: var(--muted);
    font-size: 13px;
    font-weight: 600;
    padding: 7px 14px;
    border-radius: 99px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .ob-change-db:hover { color: var(--ink); border-color: var(--muted); }
  @media (max-width: 768px) {
    .ob-change-db { top: 12px; left: 12px; padding: 6px 12px; font-size: 12px; }
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

  /* ---- CSS variable mapping from dark mode colors to light mode rgb (rough approx for glowing) ---- */
  :global(.light) .ob {
    --glow-rgb: 0, 194, 255;
  }
  :global(.dark) .ob {
    --glow-rgb: 0, 194, 255;
  }
</style>
