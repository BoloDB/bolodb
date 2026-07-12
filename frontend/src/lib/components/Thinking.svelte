<script lang="ts">
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import type { ThinkingArtifact } from '$lib/types';

  let {
    artifacts = [],
    collapsed = false,
  }: { artifacts?: ThinkingArtifact[]; collapsed?: boolean } = $props();

  let expanded = $state(false);

  let summary = $derived.by(() => {
    let elapsed = 0;
    let stages = new Set<string>();
    let repairs = 0;
    for (const a of artifacts) {
      if (a.kind === 'hint' && typeof a.data.elapsed === 'number') elapsed = a.data.elapsed;
      if (a.kind !== 'hint') stages.add(a.kind);
      if (a.kind === 'repair') repairs++;
    }
    return { elapsed, stageCount: stages.size, repairs };
  });

  function fmt(s: number): string {
    if (s < 10) return s.toFixed(1) + 's';
    if (s < 60) return Math.round(s) + 's';
    const m = Math.floor(s / 60);
    return `${m}m ${Math.round(s - m * 60)}s`;
  }
</script>

{#if collapsed && !expanded}
  <button onclick={() => expanded = true}
    aria-expanded={!expanded}
    aria-label="Expand thinking process"
    style="display:flex;align-items:center;gap:8px;width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-2);color:var(--muted);font-size:13px;font-weight:600;cursor:pointer;transition:background .15s;text-align:left">
    <span style="flex-shrink:0;width:22px;height:22px;border-radius:99px;background:var(--brand-tint);color:var(--brand);display:grid;place-items:center;font-size:12px">🧠</span>
    <span style="flex:1">Process completed · {summary.stageCount} stages{summary.repairs > 0 ? ` · ${summary.repairs} repair${summary.repairs > 1 ? 's' : ''}` : ''} · {fmt(summary.elapsed)}</span>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style="color:var(--faint);transition:transform .2s"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>
{:else}
  <div style="display:flex;flex-direction:column;gap:6px;padding:2px 0">
    {#each artifacts as artifact, i}
      {@const d = artifact.data}
      {#if artifact.kind === "schema"}
        <div style="padding:10px 14px;border-left:2.5px solid var(--brand-tint-2);background:var(--surface-2);border-radius:0 var(--radius-sm) var(--radius-sm) 0">
          <div style="font-size:12px;font-weight:700;color:var(--brand-ink);margin-bottom:4px;display:flex;align-items:center;gap:6px">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="1.6"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" stroke="currentColor" stroke-width="1.6"/></svg>
            Schema linked
          </div>
          <div style="font-size:12.5px;color:var(--ink-2);line-height:1.5">
            {(d.linked as string[] | undefined)?.length ?? 0} of {(d.tables as string[] | undefined)?.length ?? 0} tables
            {#if (d.linked as string[] | undefined)?.length}
              <span style="color:var(--muted)">· {(d.linked as string[]).slice(0, 4).join(', ')}{(d.linked as string[]).length > 4 ? '…' : ''}</span>
            {/if}
          </div>
          {#if (d.glossary as { term: string; maps_to: string }[] | undefined)?.length}
            <div style="margin-top:4px;font-size:11.5px;color:var(--muted)">
              {(d.glossary as { term: string; maps_to: string }[]).slice(0, 2).map(g => `${g.term} → ${g.maps_to}`).join(' · ')}
            </div>
          {/if}
        </div>

      {:else if artifact.kind === "hint"}
        <div style="display:flex;align-items:center;gap:9px;padding:6px 14px;color:var(--muted);font-size:13px;font-weight:500">
          <Spinner />
          <span style="flex:1">{d.message as string}</span>
          {#if typeof d.elapsed === 'number' && d.elapsed > 0}
            <span style="font-size:11.5px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--faint)">⏱ {fmt(d.elapsed)}</span>
          {/if}
        </div>

      {:else if artifact.kind === "sql"}
        <div style="border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden">
          <div style="padding:7px 14px;font-size:11px;font-weight:700;color:var(--faint);background:var(--surface-2);border-bottom:1px solid var(--border);letter-spacing:.06em;display:flex;align-items:center;gap:6px">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Attempt {(d.attempt as number)}
            {#if artifacts[i + 1]?.kind === "validation" && artifacts[i + 1]?.data?.passed}
              <span style="margin-left:auto;color:var(--brand-ink);background:var(--brand-tint);padding:1px 7px;border-radius:99px;font-size:10px">✓ Passed</span>
            {/if}
          </div>
          <pre style="margin:0;padding:12px 14px;font-size:12.5px;line-height:1.55;color:var(--ink-2);background:var(--surface);overflow-x:auto;font-family:var(--font-mono);white-space:pre">{d.sql as string}</pre>
        </div>

      {:else if artifact.kind === "validation"}
        <div style="padding:8px 14px;border-left:2.5px solid {d.passed ? 'var(--brand-tint-2)' : '#EBC6BD'};background:var(--surface-2);border-radius:0 var(--radius-sm) var(--radius-sm) 0">
          <div style="font-size:12px;font-weight:700;color:{d.passed ? 'var(--brand-ink)' : 'var(--c-low-ink)'};margin-bottom:4px;display:flex;align-items:center;gap:5px">
            {#if d.passed}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Validation passed
            {:else}
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>
              Validation failed
            {/if}
            <span style="font-weight:500;font-size:11px;color:var(--faint);margin-left:auto">Attempt {(d.attempt as number)}</span>
          </div>
          {#each (d.checks as { target: string; status: string; message: string; suggestion?: string | null }[]) as check}
            <div style="display:flex;align-items:flex-start;gap:6px;padding:3px 0;font-size:12px;line-height:1.4;color:var(--ink-2)">
              {#if check.status === "ok"}
                <span style="color:var(--brand-ink);flex-shrink:0;margin-top:1px">✓</span>
              {:else}
                <span style="color:var(--c-low-ink);flex-shrink:0;margin-top:1px">✗</span>
              {/if}
              <span style="flex:1">{check.message}</span>
            </div>
            {#if check.suggestion}
              <div style="padding:0 0 3px 19px;font-size:11.5px;color:var(--brand-ink);font-weight:600">{check.suggestion}</div>
            {/if}
          {/each}
        </div>

      {:else if artifact.kind === "repair"}
        <div style="padding:10px 14px;border-left:2.5px solid #EBC6BD;background:var(--surface-2);border-radius:0 var(--radius-sm) var(--radius-sm) 0">
          <div style="font-size:12px;font-weight:700;color:var(--c-low-ink);margin-bottom:5px;display:flex;align-items:center;gap:5px">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Self-correcting
            <span style="font-weight:500;font-size:11px;color:var(--faint);margin-left:auto">Attempt {(d.attempt as number)}/{(d.total as number)}</span>
          </div>
          <div style="font-size:12.5px;color:var(--c-low-ink);margin-bottom:4px">✗ {d.error as string}</div>
          {#if d.suggestion as string}
            <div style="font-size:12px;color:var(--brand-ink);font-weight:600;margin-bottom:6px">🛠 {d.suggestion}</div>
          {/if}
          <div style="font-size:11px;font-weight:600;color:var(--faint);margin-bottom:3px;letter-spacing:.05em">PREVIOUS SQL</div>
          <pre style="margin:0;padding:10px 12px;font-size:12px;line-height:1.5;color:var(--c-low-ink);background:var(--c-low-tint);border:1px solid #EBC6BD;border-radius:4px;overflow-x:auto;font-family:var(--font-mono);white-space:pre">{(d.old_sql as string) || '(empty)'}</pre>
        </div>

      {:else if artifact.kind === "execution"}
        <div style="padding:8px 14px;border-left:2.5px solid var(--brand-tint-2);background:var(--surface-2);border-radius:0 var(--radius-sm) var(--radius-sm) 0">
          <div style="font-size:12px;font-weight:700;color:var(--brand-ink);margin-bottom:2px;display:flex;align-items:center;gap:5px">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.2 4.2L19 7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
            {(d.rows as number).toLocaleString()} row{(d.rows as number) !== 1 ? 's' : ''}
            <span style="font-weight:500;font-size:11px;color:var(--faint);margin-left:auto">{typeof d.elapsed === 'number' ? `${(d.elapsed * 1000).toFixed(0)}ms` : ''}</span>
          </div>
          {#if d.truncated}
            <div style="font-size:11.5px;color:var(--muted)">Results were truncated — showing first {Math.min((d.rows as number), 100)} rows</div>
          {/if}
        </div>

      {:else if artifact.kind === "confidence"}
        <div style="padding:8px 14px;border-left:2.5px solid var(--brand-tint-2);background:var(--surface-2);border-radius:0 var(--radius-sm) var(--radius-sm) 0">
          <div style="display:flex;align-items:center;gap:7px">
            <span style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:99px;font-size:11px;font-weight:700;background:{(d.level as string) === 'high' ? 'var(--brand-tint)' : (d.level as string) === 'medium' ? 'var(--c-med-tint)' : 'var(--c-low-tint)'};color:{(d.level as string) === 'high' ? 'var(--brand-ink)' : (d.level as string) === 'medium' ? 'var(--c-med-ink)' : 'var(--c-low-ink)'}">
              {(d.level as string).toUpperCase()}
            </span>
            <span style="font-size:12px;color:var(--muted);font-weight:500">{d.reason as string}</span>
          </div>
        </div>
      {/if}

      {#if collapsed && expanded && i === artifacts.length - 1}
        <button onclick={() => expanded = false}
          aria-expanded={expanded}
          aria-label="Collapse thinking process"
          style="display:flex;align-items:center;gap:6px;padding:6px 0;font-size:12px;font-weight:600;color:var(--faint);cursor:pointer;background:none;border:none">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M18 15l-6-6-6 6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Collapse
        </button>
      {/if}
    {/each}
  </div>
{/if}
