<script lang="ts">
  import { trustFor } from "$lib/data";
  import { apiCall, rowsToArrays, streamApiCall, createConversation, getConversation } from "$lib/api";
  import type {
    Turn,
    SchemaTable,
    DbInfo,
    ThinkingArtifact,
    StreamEvent,
    Conversation,
    ConversationTurn,
  } from "$lib/types";
  import { page } from "$app/state";
  import AppShell from "$lib/components/AppShell.svelte";
  import AnswerCard from "$lib/components/AnswerCard.svelte";
  import SettingsTab from "$lib/components/SettingsTab.svelte";
  import Spinner from '$lib/components/ui/Spinner.svelte';
  import LoadingScreen from '$lib/components/ui/LoadingScreen.svelte';
  import SlashCommandMenu from "$lib/components/ui/SlashCommandMenu.svelte";
  import type { SlashCommand } from "$lib/components/ui/SlashCommandMenu.svelte";
  import { appState } from "$lib/appState.svelte";
  import { onMount } from "svelte";
  import posthog from "posthog-js";

  let {
    verifiedCount,
    onVerify,
    onUpdateStarters,
    realSchema,
    dbInfo,
    starters,
    onDisconnect,
    onActiveConversationChange = (_id: string | null) => {},
  }: {
    verifiedCount: number;
    onVerify: (count?: number) => void;
    onUpdateStarters: (s: string[]) => void;
    realSchema: SchemaTable[] | null;
    dbInfo: DbInfo | null;
    starters: string[];
    onDisconnect: () => void;
    onActiveConversationChange?: (id: string | null) => void;
  } = $props();

  let turns: Turn[] = $state([]);
  let input = $state("");
  // ?tab=settings lets the sidebar land directly on Settings when coming back
  // from a route that isn't /chat.
  let tab = $state<"ask" | "settings">(
    page.url.searchParams.get("tab") === "settings" ? "settings" : "ask",
  );
  let openCatalogTrigger = $state(0);

  onMount(() => {
    appState.fetchStartersAsync();
  });

  const suggestionChips = $derived(
    starters && starters.length
      ? starters.slice(0, 3)
      : []
  );
  let loading = $state(false);
  let feedRef: HTMLDivElement | undefined = $state(undefined);
  let currentArtifacts: ThinkingArtifact[] = $state([]);
  let conversationTrigger = $state(0);
  let activeConversationId: string | null = $state(null);
  let abortController: AbortController | null = $state(null);
  /** Turn ids whose SQL is being re-executed right now. */
  let rerunning = $state<Set<string>>(new Set());
  let showScrollBtn = $state(false);
  let lastTurnCount = 0;
  let convLoadSeq = 0;
  let convLoading = $state(false); // true only while fetching a past conversation

  // The database can be switched from the shared shell on any screen, so the
  // feed reacts to the active database changing rather than to the click.
  let lastDbId: string | null = null;
  $effect(() => {
    const id = dbInfo?.db_id ?? null;
    if (lastDbId !== null && id !== lastDbId) {
      abortController?.abort();
      turns = [];
      activeConversationId = null;
      onActiveConversationChange(null);
    }
    lastDbId = id;
  });


  const trust = $derived(trustFor(verifiedCount));

  // Slash command menu state
  let showSlashMenu = $state(false);
  let slashFilter = $state("");
  let inputRef: HTMLTextAreaElement | undefined = $state(undefined);

  // Configurable slash commands - add new commands here
  const slashCommands: SlashCommand[] = [
    { name: "/sql", description: "Execute SQL query directly" },
  ];

  $effect(() => {
    turns; // track
    // Only follow new content when the user is already near the bottom —
    // force-scrolling on every turns update yanks the viewport while
    // someone is reading or verifying an older answer.
    if (!feedRef) return;
    const distance = feedRef.scrollHeight - feedRef.scrollTop - feedRef.clientHeight;
    if (distance < 200 || turns.length !== lastTurnCount) {
      feedRef.scrollTop = feedRef.scrollHeight;
    }
    lastTurnCount = turns.length;
  });

  function onFeedScroll() {
    if (!feedRef) return;
    const d = feedRef.scrollHeight - feedRef.scrollTop - feedRef.clientHeight;
    showScrollBtn = d > 200;
  }

  function scrollToBottom() {
    if (feedRef) feedRef.scrollTop = feedRef.scrollHeight;
  }

  function eventToArtifact(event: StreamEvent): ThinkingArtifact | null {
    switch (event.kind) {
      case "schema_linked":
        return {
          kind: "schema",
          data: {
            tables: event.tables,
            linked: event.linked,
            glossary: event.glossary,
          },
        };
      case "hint":
        return {
          kind: "hint",
          data: { message: event.message, elapsed: event.elapsed },
        };
      case "sql":
        return {
          kind: "sql",
          data: { attempt: event.attempt, sql: event.sql },
        };
      case "validation":
        return {
          kind: "validation",
          data: {
            attempt: event.attempt,
            checks: event.checks,
            passed: event.passed,
          },
        };
      case "repair":
        return {
          kind: "repair",
          data: {
            attempt: event.attempt,
            total: event.total,
            error: event.error,
            suggestion: event.suggestion,
            old_sql: event.old_sql,
          },
        };
      case "execution":
        return {
          kind: "execution",
          data: {
            rows: event.rows,
            elapsed: event.elapsed,
            truncated: event.truncated,
          },
        };
      case "confidence":
        return {
          kind: "confidence",
          data: {
            level: event.level,
            reason: event.reason,
            based_on_verified: event.based_on_verified,
          },
        };
      default:
        return null;
    }
  }

  // Handle input changes to detect slash commands
  function handleInput(e: Event) {
    const target = e.target as HTMLInputElement | HTMLTextAreaElement;
    const value = target.value;

    if (value === "/") {
      showSlashMenu = true;
      slashFilter = "";
    } else if (value === "" && showSlashMenu) {
      showSlashMenu = false;
    } else if (showSlashMenu && value.includes(" ")) {
      showSlashMenu = false;
    } else if (showSlashMenu && value.startsWith("/")) {
      slashFilter = value.slice(1);
    } else if (showSlashMenu && !value.startsWith("/")) {
      showSlashMenu = false;
    }
  }

  function handleTextareaResize(e: Event) {
    const ta = e.target as HTMLTextAreaElement;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px';
  }

  function handleSlashCommandSelect(command: SlashCommand) {
    input = command.name + " ";
    showSlashMenu = false;
    slashFilter = "";
  }

  function handleSlashMenuClose() {
    showSlashMenu = false;
    slashFilter = "";
  }
  async function ensureConversation(firstQuestion?: string): Promise<string | null> {
    if (activeConversationId) return activeConversationId;
    const title = (firstQuestion || "").slice(0, 80);
    try {
      const conv = await createConversation(title, dbInfo?.db_id);
      activeConversationId = conv._id;
      onActiveConversationChange(conv._id);
      conversationTrigger++;
      return conv._id;
    } catch (e) {
      console.error("Failed to create conversation", e);
      appState.showError("Couldn't start a new conversation — your question will still run, but it won't be saved to history.");
      return null;
    }
  }

  async function runQuery(
    question: string,
    onAddTurn: (turn: Turn) => void,
    onUpdateTurn: (id: string, update: Partial<Turn>) => void,
    signal?: AbortSignal,
  ) {
    const id = Math.random().toString(36).slice(2, 10);
    const ts = new Date().toISOString();

    // Direct SQL mode: /sql <query>
    const sqlMatch = question.match(/^\/sql\s+(.+)/is);
    if (sqlMatch) {
      const rawSql = sqlMatch[1].trim();
      onAddTurn({ id, question: rawSql, thinking: true, isDirect: true, timestamp: ts } as Turn);
      const convId = await ensureConversation(rawSql);
      try {
        const data = await apiCall("/api/execute", { sql: rawSql, conversation_id: convId || undefined });
        const rows2d = rowsToArrays(data.columns || [], data.rows || []);
        onUpdateTurn(id, {
          thinking: false,
          sql: data.sql || rawSql,
          columns: data.columns || [],
          rows: rows2d,
          confidence: "high" as const,
          reason: "Direct SQL execution",
          basedOn: false,
          query_id: id,
          executionError: null,
          verdict: null,
          isDirect: true,
          timestamp: ts,
        });
        conversationTrigger++;
      } catch (e: any) {
        onUpdateTurn(id, {
          thinking: false,
          sql: rawSql,
          columns: [],
          rows: [],
          confidence: "low" as const,
          reason: "Execution failed",
          basedOn: false,
          query_id: id,
          executionError: e.message || "SQL execution failed",
          verdict: null,
          isDirect: true,
          timestamp: ts,
        });
      }
      return;
    }

    // Normal LLM query flow
    const artifacts: ThinkingArtifact[] = [];
    currentArtifacts = artifacts;
    onAddTurn({ id, question, thinking: true, thinkingArtifacts: artifacts, timestamp: ts } as Turn);

    let build_context = [];
    for (let t of turns.toReversed()) {
      if (build_context.length >= 2) break;
      if (t.thinking || !t.sql || t.executionError || t.verdict === "wrong") continue;
      build_context.push({ question: t.question, sql: t.sql, restatement: t.restatement });
    }
    build_context.reverse();
    const convId = await ensureConversation(question);
    await streamApiCall(
      "/api/query/stream",
      { question, context: build_context, conversation_id: convId || undefined },
      (event: StreamEvent) => {
        const artifact = eventToArtifact(event);
        if (artifact) {
          if (artifact.kind === "hint") {
            const idx = artifacts.findIndex((a) => a.kind === "hint");
            if (idx >= 0) artifacts[idx] = artifact;
            else artifacts.push(artifact);
          } else {
            artifacts.push(artifact);
          }
          currentArtifacts = [...artifacts];
        }
      },
      (data: any) => {
        onUpdateTurn(id, {
          thinking: false,
          restatement: data.restatement || "",
          sql: data.sql || "",
          columns: data.columns || [],
          rows: rowsToArrays(data.columns || [], data.rows || []),
          confidence: data.confidence || "medium",
          reason: data.confidence_reason || "",
          chart: data.chart || null,
          basedOn: data.based_on_verified || false,
          query_id: data.query_id || id,
          executionError: data.execution_error || null,
          verdict: null,
          thinkingArtifacts: [...artifacts],
          timestamp: ts,
        });
        conversationTrigger++;
      },
      (err: Error) => {
        const errMsg = err.message || "Request failed";
        const isApiKeyError =
          errMsg.toLowerCase().includes("api key");
        // Transport-level failures carry technical text; anything else came
        // from a backend error event and is already written for the user
        // (e.g. the high-traffic notice) — show it verbatim.
        const isTechnical =
          /(request failed|stream ended|failed to fetch|network(?:[Ee]rror)? ?error|load failed|streaming not supported)/i.test(
            errMsg,
          );
        onUpdateTurn(id, {
          thinking: false,
          restatement: isApiKeyError
            ? "AI not ready — set OPENROUTER_API_KEY in the server environment."
            : isTechnical
              ? "Something went wrong — please check your connection and try again."
              : errMsg,
          sql: "",
          columns: [],
          rows: [],
          confidence: "low" as const,
          reason: isTechnical ? errMsg : "",
          basedOn: false,
          query_id: id,
          verdict: null,
          thinkingArtifacts: [...artifacts],
          timestamp: ts,
        });
        if (isApiKeyError) {
          tab = "settings";
        }
      },
      signal,
    );
  }

  async function ask(text?: string) {
    const q = (text || input).trim();
    if (!q || loading) return;
    input = "";
    loading = true;
    abortController = new AbortController();

    posthog.capture("query_submitted", {
      is_direct_sql: q.startsWith("/sql "),
      question_length: q.length,
    });

    // Fire the funnel event "first_query_asked" exactly once per user
    try {
      if (!localStorage.getItem("bolodb_first_query")) {
        posthog.capture("first_query_asked", { question_length: q.length });
        localStorage.setItem("bolodb_first_query", "1");
      }
    } catch {}

    try {
      await runQuery(
        q,
        (turn) => { turns = [...turns, turn]; },
        (id, update) => { turns = turns.map((x) => x.id === id ? { ...x, ...update } : x); },
        abortController.signal,
      );
    } finally {
      abortController = null;
      loading = false;
    }
  }

  async function requeryAt(idx: number, question: string) {
    const q = question.trim();
    if (!q || loading) return;
    loading = true;
    abortController = new AbortController();
    try {
      await runQuery(
        q,
        (turn) => { turns[idx] = turn; },
        (id, update) => { turns[idx] = { ...turns[idx], ...update }; },
        abortController.signal,
      );
    } finally {
      abortController = null;
      loading = false;
    }
  }

  function regenerate(turnId: string) {
    const idx = turns.findIndex((t) => t.id === turnId);
    if (idx === -1) return;
    requeryAt(idx, turns[idx].question);
  }

  /**
   * Re-run the SQL a turn already has, without going back to the model. Same
   * question, fresh rows — the point is to refresh a result for free rather
   * than spend tokens regenerating identical SQL.
   */
  async function rerunSql(turnId: string) {
    const turn = turns.find((t) => t.id === turnId);
    if (!turn?.sql || rerunning.has(turnId)) return;
    rerunning = new Set([...rerunning, turnId]);
    try {
      const data = await apiCall("/api/execute", {
        sql: turn.sql,
        save_history: false,
      });
      turns = turns.map((t) =>
        t.id === turnId
          ? {
              ...t,
              columns: data.columns || [],
              rows: rowsToArrays(data.columns || [], data.rows || []),
              executionError: null,
              resultTruncated: false,
              lastRunAt: new Date().toISOString(),
            }
          : t,
      );
    } catch (e: any) {
      appState.showError(
        e?.message || "Couldn't re-run this query against your database.",
      );
    } finally {
      const next = new Set(rerunning);
      next.delete(turnId);
      rerunning = next;
    }
  }

  function editAndRequery(turnId: string, newQuestion: string) {
    const idx = turns.findIndex((t) => t.id === turnId);
    if (idx === -1) return;
    requeryAt(idx, newQuestion);
  }

  async function handleVerify(
    turnId: string,
    verdict: string,
    reasonChosen: string | null,
  ) {
    turns = turns.map((x) =>
      x.id === turnId ? { ...x, verdict: verdict as any, reasonChosen } : x,
    );
    const turn = turns.find((x) => x.id === turnId);
    posthog.capture("query_verified", {
      verdict,
      reason: reasonChosen,
      confidence: turn?.confidence,
    });
    try {
      const r = await apiCall("/api/feedback", {
        query_id: turn?.query_id || "",
        verdict,
        reason: reasonChosen || "",
        question: turn?.question || "",
        sql: turn?.sql || "",
        restatement: turn?.restatement || "",
      });
      if (verdict === "correct") {
        if (r.trust) onVerify(r.trust.verified);
        else onVerify();
        if (r.starters) onUpdateStarters(r.starters);
      }
    } catch {
      turns = turns.map((x) =>
        x.id === turnId ? { ...x, verdict: null, reasonChosen: null } : x,
      );
    }
  }

  async function handleNewConversation() {
    // Cancel any in-flight query stream so its callbacks can't write into
    // the fresh conversation view.
    abortController?.abort();
    convLoadSeq++;
    loading = false;
    convLoading = false;
    turns = [];
    activeConversationId = null;
    onActiveConversationChange(null);
  }

  function turnFromHistory(t: ConversationTurn): Turn {
    const result = Array.isArray(t.result) ? t.result : [];
    const cols = result.length > 0 && result[0] && typeof result[0] === 'object'
      ? Object.keys(result[0])
      : [];
    // Direct /sql executions are persisted with this marker restatement;
    // restore them as direct turns so they don't grow a verify prompt.
    const isDirect = t.restatement === 'Direct SQL execution' && t.question === t.sql;
    return {
      isDirect,
      resultTruncated: !!t.result_truncated,
      id: t._id,
      question: t.question,
      thinking: false,
      timestamp: t.timestamp,
      restatement: t.restatement || '',
      sql: t.sql || '',
      columns: cols,
      rows: result.map((row: Record<string, unknown>) => cols.map(c => {
        const v = row?.[c];
        return v === null || v === undefined ? '' : String(v);
      })),
      confidence: (t.confidence || 'medium').toLowerCase() as "high" | "medium" | "low",
      reason: '',
      chart: t.chart || null,
      basedOn: false,
      query_id: t._id,
      executionError: null,
      verdict: null,
      reasonChosen: null,
    } as Turn;
  }

  async function handleConversationSelect(convId: string) {
    if (convId === activeConversationId) return;
    abortController?.abort();
    const seq = ++convLoadSeq;
    loading = true;
    convLoading = true;
    turns = [];
    try {
      const conv = await getConversation(convId);
      if (seq !== convLoadSeq) return;

      // Auto-switch database if the conversation belongs to a different one
      if (conv.database_id && dbInfo?.db_id !== conv.database_id) {
        await appState.switchDatabase(conv.database_id);
      }

      activeConversationId = conv._id;
      onActiveConversationChange(conv._id);
      const loaded: Turn[] = [];
      for (const t of conv.turns || []) {
        try {
          loaded.push(turnFromHistory(t));
        } catch (e) {
          console.error('Skipping malformed turn', t?._id, e);
        }
      }
      turns = loaded;
    } catch (e) {
      console.error('Failed to load conversation', e);
      if (seq === convLoadSeq) {
        appState.showError("Couldn't open that conversation — please try again.");
      }
    } finally {
      if (seq === convLoadSeq) { loading = false; convLoading = false; }
    }
  }

  function handleSubmit(e: Event) {
    e.preventDefault();
    ask();
  }
</script>
<AppShell
  activeTab={tab}
  onTab={(t) => (tab = t as "ask" | "settings")}
  {dbInfo}
  {verifiedCount}
  {realSchema}
  {conversationTrigger}
  {activeConversationId}
  onConversationSelect={handleConversationSelect}
  onNewChat={handleNewConversation}
>
    {#if tab === "ask"}
      <!-- feed -->
      <div bind:this={feedRef} onscroll={onFeedScroll} class="feed">
        {#if convLoading}
          <LoadingScreen
            message="Opening conversation…"
            submessage="Fetching your previous results"
            variant="default"
          />
        {:else if appState.switchingDatabase}
          <LoadingScreen
            message="Switching database…"
            submessage="Connecting securely to your data"
            variant="connect"
          />
        {:else}
        <div class="feed-inner">
          {#if turns.length === 0}
            <div class="empty rise">
              <h1 class="empty-title">What do you want to know?</h1>
              <p class="empty-sub">Ask the way you'd ask a colleague. No SQL needed.</p>
              <span class="empty-badge">✓ QUESTIONS VERIFIED FOR THIS DATABASE</span>
              <div class="chips" data-tour="starters" data-testid="chat-starters">
                {#if suggestionChips.length === 0}
                  <div class="sg-chip shimmer">Generating suggestions...</div>
                  <div class="sg-chip shimmer" style="animation-delay: 0.1s">Waiting for AI...</div>
                {:else}
                  {#each suggestionChips as sg}
                    <button class="sg-chip" onclick={() => ask(sg)}>{sg}</button>
                  {/each}
                {/if}
              </div>
              <button class="catalog-card" onclick={() => { openCatalogTrigger++; tab = "settings"; }}>
                <span style="display:flex;flex-direction:column;gap:3px">
                  <span class="cc-title">Want better answers?</span>
                  <span class="cc-sub">Review your business terms — confirmed definitions keep every answer honest.</span>
                </span>
                <span class="cc-chev">›</span>
              </button>
            </div>
          {:else}
            {#each turns as t, i (t.id)}
              <AnswerCard
                turn={t}
                isLatest={i === turns.length - 1}
                onVerify={handleVerify}
                liveArtifacts={t.thinking ? currentArtifacts : undefined}
                onRegenerate={regenerate}
                onEditPrompt={editAndRequery}
                onRerun={rerunSql}
                rerunning={rerunning.has(t.id)}
              />
            {/each}
          {/if}
        </div>
        {/if}
        {#if showScrollBtn && !convLoading}
          <button onclick={scrollToBottom} aria-label="Scroll to latest" class="scroll-btn">↓</button>
        {/if}
      </div>

      <!-- input -->
      <div class="input-zone">
        <div class="input-wrap">
          {#if showSlashMenu}
            <SlashCommandMenu
              commands={slashCommands}
              onSelect={handleSlashCommandSelect}
              onClose={handleSlashMenuClose}
              filter={slashFilter}
              {inputRef}
            />
          {/if}
          <form onsubmit={handleSubmit} data-tour="ask-input" data-testid="chat-ask-form" class="ask-form">
            <textarea
              bind:value={input}
              oninput={(e) => { handleInput(e); handleTextareaResize(e); }}
              bind:this={inputRef}
              onkeydown={(e) => { if (e.key === "Enter" && !e.shiftKey && !showSlashMenu) { e.preventDefault(); ask(); } }}
              placeholder="Ask anything about your data…"
              aria-label="Ask a question about your data"
              class="chat-input"
              rows={1}
            ></textarea>
            <button class="send-btn" type="submit" aria-label="Send" disabled={!input.trim() || loading}>
              {#if loading}<Spinner />{:else}↑{/if}
            </button>
          </form>
          <div class="input-hint">
            Read-only · every answer shows its SQL · Power user? Type
            <span class="mono" style="color:var(--muted)">/sql SELECT …</span> to run SQL directly
          </div>
        </div>
      </div>

    {:else}
      <SettingsTab
        {dbInfo}
        {onDisconnect}
        theme={appState.theme}
        onToggleTheme={() => appState.toggleTheme()}
        {openCatalogTrigger}
      />
    {/if}
</AppShell>

<style>
  .feed { flex: 1; overflow-y: auto; padding: 36px 32px 20px; position: relative; }
  .feed-inner { max-width: 760px; margin: 0 auto; }
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding-top: 11vh;
    text-align: center;
  }
  .empty-title {
    margin: 0;
    font-size: clamp(1.7rem, 3vw, 2.4rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--ink);
  }
  .empty-sub { margin: 0; font-size: 15px; color: var(--muted); }
  .empty-badge {
    margin-top: 6px;
    font-family: var(--font-mono);
    font-size: 10.5px;
    letter-spacing: 0.12em;
    color: var(--accent);
  }
  .chips { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .sg-chip {
    background: var(--card);
    border: 1px solid var(--border-2);
    color: var(--ink-2);
    font-size: 13.5px;
    font-weight: 600;
    padding: 10px 18px;
    border-radius: 99px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .sg-chip:hover { border-color: var(--brand); color: var(--brand); }
  .sg-chip.shimmer {
    background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 75%);
    background-size: 200% 100%;
    animation: shimmer 2s infinite linear;
    color: var(--fg-muted);
    border: 1px solid rgba(255,255,255,0.05);
    cursor: default;
    pointer-events: none;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  .catalog-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-top: 14px;
    width: 100%;
    max-width: 520px;
    text-align: left;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 20px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .catalog-card:hover { border-color: var(--brand); }
  .cc-title { font-size: 14px; font-weight: 700; color: var(--ink); }
  .cc-sub { font-size: 12.5px; color: var(--muted); line-height: 1.5; }
  .cc-chev { color: var(--faint); font-size: 16px; }
  .scroll-btn {
    position: sticky;
    bottom: 16px;
    left: 100%;
    width: 38px;
    height: 38px;
    border-radius: 99px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    box-shadow: var(--shadow-md, var(--shadow));
    cursor: pointer;
    display: grid;
    place-items: center;
    font-size: 18px;
    font-weight: 700;
    z-index: 10;
  }
  .input-zone {
    padding: 14px 32px 26px;
    border-top: 1px solid var(--border);
    background: var(--bg);
  }
  .input-wrap { max-width: 760px; margin: 0 auto; position: relative; }
  .ask-form {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--card);
    border: 1.5px solid var(--border-2);
    border-radius: 99px;
    padding: 6px 8px 6px 22px;
    transition: border-color 0.2s;
  }
  .ask-form:focus-within { border-color: var(--brand); }
  .chat-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 15px;
    color: var(--ink);
    padding: 10px 0;
    resize: none;
    overflow-y: auto;
    max-height: 120px;
    line-height: 1.45;
  }
  .chat-input:focus, .chat-input:focus-visible { outline: none; box-shadow: none; }
  .send-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--brand);
    color: var(--on-brand);
    border: none;
    cursor: pointer;
    font-size: 16px;
    flex-shrink: 0;
    transition: all 0.15s;
  }
  .send-btn:hover:not(:disabled) { background: var(--brand-2); }
  .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .input-hint {
    max-width: 760px;
    margin: 8px auto 0;
    text-align: center;
    font-size: 11.5px;
    color: var(--faint);
  }

  @media (max-width: 768px) {
    .feed { padding: 20px 16px 16px; }
    .empty { padding-top: 6vh; }
    .empty-title { font-size: clamp(1.5rem, 7vw, 2rem); }
    .input-zone { padding: 12px 14px calc(16px + env(safe-area-inset-bottom, 0px)); }
    .input-hint { font-size: 11px; }
  }
</style>
