<script lang="ts">
  import { schema as defaultSchema, trustFor, providers } from '$lib/data';
  import type { SchemaTable, DbInfo, Conversation } from '$lib/types';
  import Logo from '$lib/components/ui/Logo.svelte';
  import TrustMeter from '$lib/components/ui/TrustMeter.svelte';
  import { getConversations, deleteConversation, clearConversations, renameConversation } from '$lib/api';

  let { engine, modelName, verifiedCount, onSettings, schema, dbInfo, onConversationSelect, activeConversationId, conversationTrigger = 0 }:
    { engine: string; modelName: string; verifiedCount: number; onSettings: () => void; schema: SchemaTable[] | null; dbInfo: DbInfo | null; onConversationSelect?: (id: string) => void; activeConversationId?: string | null; conversationTrigger?: number } = $props();

  const trust = $derived(trustFor(verifiedCount));
  const prov = $derived(providers.find(p => p.id === engine) ?? providers[0]);
  let openTable: string | null = $state(null);
  let conversations: Conversation[] = $state([]);
  let openConversations: boolean = $state(true);
  let editingId: string | null = $state(null);
  let editTitle: string = $state('');

  const schemaData = $derived(schema || defaultSchema);
  const dbLabel = $derived(dbInfo ? (dbInfo.url || '').split('/').pop() || dbInfo.dialect || 'your database' : 'your database');

  $effect(() => {
    conversationTrigger;
    getConversations().then(res => {
      if (res && res.conversations) {
        conversations = res.conversations;
      }
    }).catch(e => console.error(e));
  });

  async function handleDelete(id: string, e: Event) {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      conversations = conversations.filter(c => c._id !== id);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleClear() {
    try {
      await clearConversations();
      conversations = [];
    } catch (e) {
      console.error(e);
    }
  }

  function startRename(conv: Conversation, e: Event) {
    e.stopPropagation();
    editingId = conv._id;
    editTitle = conv.title || conv.last_question || '';
  }

  async function finishRename(id: string) {
    const title = editTitle.trim();
    if (title && title !== (conversations.find(c => c._id === id)?.title || '')) {
      try {
        await renameConversation(id, title);
        conversations = conversations.map(c => c._id === id ? { ...c, title } : c);
      } catch (e) {
        console.error(e);
      }
    }
    editingId = null;
    editTitle = '';
  }

  function handleRenameKeydown(e: KeyboardEvent, id: string) {
    if (e.key === 'Enter') {
      e.preventDefault();
      (e.target as HTMLInputElement).blur();
    } else if (e.key === 'Escape') {
      editingId = null;
      editTitle = '';
    }
  }

  function formatTime(iso: string): string {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  }
</script>

<div style="width:286px;flex-shrink:0;border-right:1px solid var(--border);background:var(--surface);display:flex;flex-direction:column;height:100%">
  <!-- trust panel -->
  <div style="margin:16px 16px 14px;padding:16px;border-radius:var(--radius);background:linear-gradient(165deg, var(--brand-tint), var(--surface-2));border:1px solid var(--border)">
    <div style="display:flex;align-items:center;gap:7px;margin-bottom:11px">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style="color:var(--brand)"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span style="font-size:12px;font-weight:800;letter-spacing:.04em;color:var(--brand-ink);text-transform:uppercase;white-space:nowrap">Accuracy</span>
      <span style="margin-left:auto;font-size:11px;font-weight:700;color:var(--faint)">{verifiedCount} verified</span>
    </div>
    <TrustMeter count={verifiedCount} />
    <p style="font-size:12.5px;color:var(--muted);line-height:1.5;margin:11px 0 0">{trust.behaviour}</p>
    {#if trust.next}
      <div style="margin-top:10px;padding:9px 11px;background:var(--surface);border-radius:var(--radius-sm);font-size:12px;color:var(--brand-ink);font-weight:600;line-height:1.5">
        Verify {trust.next - verifiedCount} more correct answer{trust.next - verifiedCount === 1 ? '' : 's'} and BoloDB will
        {trust.key === 'supervised' ? 'start showing confident answers directly without waiting.' : 'answer all questions directly — reasoning one tap away.'}
      </div>
    {:else}
      <div style="margin-top:10px;padding:9px 11px;background:var(--surface);border-radius:var(--radius-sm);font-size:12px;color:var(--brand-ink);font-weight:600">
        ✓ BoloDB is fully calibrated for this database.
      </div>
    {/if}
  </div>

  <!-- schema + conversations -->
  <div style="flex:1;overflow-y:auto;padding:2px 16px 10px">
    <div style="font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--faint);margin:6px 6px 9px;text-transform:uppercase;display:flex;align-items:center;gap:6px">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><rect x="3.5" y="4.5" width="17" height="15" rx="2.2" stroke="currentColor" stroke-width="1.8"/><path d="M3.5 9.5h17M9 9.5v10M3.5 14.5h17" stroke="currentColor" stroke-width="1.6"/></svg>
      Schema
    </div>
    {#each schemaData as t}
      <div style="margin-bottom:3px">
        <button onclick={() => openTable = openTable === t.name ? null : t.name}
          style="width:100%;display:flex;align-items:center;gap:8px;padding:8px 9px;border-radius:var(--radius-xs);border:none;background:{openTable===t.name?'var(--surface-3)':'transparent'};cursor:pointer;text-align:left;transition:background .12s">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style="color:var(--faint);transform:{openTable===t.name?'none':'rotate(-90deg)'};transition:transform .15s;flex-shrink:0"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span class="mono" style="font-size:13px;font-weight:650;color:var(--ink);flex:1">{t.name}</span>
          <span class="tnum" style="font-size:10.5px;color:var(--faint);font-weight:600">{t.rows}</span>
        </button>
        {#if openTable === t.name}
          <div class="rise" style="padding:2px 0 6px 27px">
            {#each t.cols as c}
              <div class="mono" style="font-size:11.5px;color:var(--muted);padding:3px 0;display:flex;align-items:center;gap:6px">
                <span style="width:4px;height:4px;border-radius:99px;background:{c.includes('PK')?'var(--brand)':c.includes('→')?'var(--c-med)':'var(--border-2)'}"></span>
                {c}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}

    <!-- conversations -->
    <div style="margin:24px 6px 9px;display:flex;align-items:center;gap:6px">
      <button onclick={() => openConversations = !openConversations} style="display:flex;align-items:center;gap:6px;background:none;border:none;cursor:pointer;padding:0;font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--faint);text-transform:uppercase;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" style="transform:{openConversations?'none':'rotate(-90deg)'};transition:transform .15s;flex-shrink:0"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Conversations
      </button>
      {#if conversations.length > 0}
        <button onclick={handleClear} style="margin-left:auto;font-size:10px;color:var(--faint);background:none;border:none;cursor:pointer;text-transform:none;font-weight:700;padding:0">Clear all</button>
      {/if}
    </div>
    {#if openConversations}
      <div class="rise" style="padding:2px 0 6px 27px">
        {#if conversations.length === 0}
          <div class="mono" style="font-size:11.5px;color:var(--faint);padding:3px 0;font-style:italic">No conversations yet</div>
        {:else}
          {#each conversations as conv (conv._id)}
            <div class="group" style="position:relative;margin-bottom:2px">
              <button onclick={() => onConversationSelect && onConversationSelect(conv._id)}
                style="width:100%;text-align:left;background:{activeConversationId === conv._id ? 'var(--surface-3)' : 'transparent'};border:none;padding:5px 0;cursor:pointer;display:flex;align-items:center;gap:8px;border-radius:var(--radius-xs);transition:background .12s">
                <span style="width:4px;height:4px;border-radius:99px;background:{conv.turn_count > 0 ? 'var(--brand)' : 'var(--border-2)'};flex-shrink:0"></span>
                <div style="flex:1;min-width:0">
                  {#if editingId === conv._id}
                    <input
                      bind:value={editTitle}
                      onblur={() => finishRename(conv._id)}
                      onkeydown={(e) => handleRenameKeydown(e, conv._id)}
                      onclick={(e) => e.stopPropagation()}
                      style="width:100%;font-size:12px;color:var(--ink);background:var(--surface);border:1px solid var(--brand);border-radius:3px;padding:1px 4px;outline:none"
                      autofocus
                    />
                  {:else}
                    <div style="font-size:12px;color:{activeConversationId === conv._id ? 'var(--ink)' : 'var(--muted)'};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:{activeConversationId === conv._id ? '600' : '400'}">
                      {conv.title || conv.last_question || 'New conversation'}
                    </div>
                    <div style="font-size:10px;color:var(--faint);margin-top:1px">
                      {conv.turn_count} turn{conv.turn_count === 1 ? '' : 's'} · {formatTime(conv.updated_at)}
                    </div>
                  {/if}
                </div>
              </button>
              {#if editingId !== conv._id}
                <button onclick={(e) => startRename(conv, e)} aria-label="Rename conversation" class="opacity-0 group-hover:opacity-100 focus:opacity-100 focus-visible:opacity-100 transition-opacity" style="position:absolute;right:24px;top:50%;transform:translateY(-50%);background:var(--surface);border:none;color:var(--faint);cursor:pointer;padding:4px;font-size:10px;border-radius:4px;display:flex;align-items:center;justify-content:center" title="Rename">✎</button>
              {/if}
              <button onclick={(e) => handleDelete(conv._id, e)} aria-label="Delete conversation" class="opacity-0 group-hover:opacity-100 focus:opacity-100 focus-visible:opacity-100 transition-opacity" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:var(--surface);border:none;color:var(--faint);cursor:pointer;padding:4px;font-size:10px;border-radius:4px;display:flex;align-items:center;justify-content:center" title="Delete">✕</button>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  </div>

  <!-- engine + settings -->
  <div style="padding:12px 16px 16px;border-top:1px solid var(--border)">
    <button onclick={onSettings} class="focusable"
      style="width:100%;display:flex;align-items:center;gap:11px;padding:11px 12px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--surface-2);cursor:pointer;transition:all .15s;text-align:left">
      <span style="width:30px;height:30px;border-radius:8px;flex-shrink:0;display:grid;place-items:center;background:var(--surface-3);color:var(--brand)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="currentColor"/></svg>
      </span>
      <div style="flex:1;min-width:0">
        <div style="font-weight:700;font-size:13px;display:flex;align-items:center;gap:6px">{prov.name}</div>
        <div class="mono" style="font-size:11px;color:var(--faint);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{modelName || prov.model}</div>
      </div>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="color:var(--faint);flex-shrink:0"><circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.9"/><path d="M12 2.5v2.3M12 19.2v2.3M21.5 12h-2.3M4.8 12H2.5M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9L5.3 5.3" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/></svg>
    </button>
  </div>
</div>
