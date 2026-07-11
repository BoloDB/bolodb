<script lang="ts">
  import { trustFor } from "$lib/data";
  import { apiCall, rowsToArrays, streamApiCall } from "$lib/api";
  import type {
    Turn,
    SchemaTable,
    DbInfo,
    Toast,
    ThinkingArtifact,
    StreamEvent,
  } from "$lib/types";
  import Sidebar from "$lib/components/Sidebar.svelte";
  import AnswerCard from "$lib/components/AnswerCard.svelte";
  import Empty from "$lib/components/Empty.svelte";
  import Settings from "$lib/components/Settings.svelte";
  import TrustToast from "$lib/components/TrustToast.svelte";
  import TrustPill from "$lib/components/ui/TrustPill.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Spinner from "$lib/components/ui/Spinner.svelte";
  import SlashCommandMenu from "$lib/components/ui/SlashCommandMenu.svelte";
  import type { SlashCommand } from "$lib/components/ui/SlashCommandMenu.svelte";
  import posthog from "posthog-js";

  let {
    engine,
    modelName,
    setModelName,
    verifiedCount,
    onVerify,
    onUpdateStarters,
    toast,
    realSchema,
    dbInfo,
    starters,
    onDisconnect,
  }: {
    engine: string;
    modelName: string;
    setModelName: (m: string) => void;
    verifiedCount: number;
    onVerify: (count?: number) => void;
    onUpdateStarters: (s: string[]) => void;
    toast: Toast | null;
    realSchema: SchemaTable[] | null;
    dbInfo: DbInfo | null;
    starters: string[];
    onDisconnect: () => void;
  } = $props();

  const dbLabel = $derived(
    dbInfo
      ? (dbInfo.url || "").split("/").pop() || dbInfo.dialect || "your database"
      : "your database",
  );
  const tableCount = $derived(dbInfo ? dbInfo.tables || 0 : 0);
  let turns: Turn[] = $state([]);
  let input = $state("");
  let settingsOpen = $state(false);
  let loading = $state(false);
  let feedRef: HTMLDivElement | undefined = $state(undefined);
  let historyTrigger = $state(0);
  let currentArtifacts: ThinkingArtifact[] = $state([]);

  const trust = $derived(trustFor(verifiedCount));

  // Slash command menu state
  let showSlashMenu = $state(false);
  let slashFilter = $state("");
  let inputRef: HTMLInputElement | undefined = $state(undefined);

  // Configurable slash commands - add new commands here
  const slashCommands: SlashCommand[] = [
    { name: "/sql", description: "Execute SQL query directly" },
  ];

  $effect(() => {
    turns; // track
    if (feedRef) feedRef.scrollTop = feedRef.scrollHeight;
  });

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
    const target = e.target as HTMLInputElement;
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

  function handleSlashCommandSelect(command: SlashCommand) {
    input = command.name + " ";
    showSlashMenu = false;
    slashFilter = "";
  }

  function handleSlashMenuClose() {
    showSlashMenu = false;
    slashFilter = "";
  }
  async function ask(text?: string) {
    const q = (text || input).trim();
    if (!q) return;
    if (loading) return;
    input = "";
    loading = true;
    const id = Math.random().toString(36).slice(2, 10);

    posthog.capture("query_submitted", {
      is_direct_sql: q.startsWith("/sql "),
      question_length: q.length,
    });

    // Direct SQL mode: /sql <query>
    const sqlMatch = q.match(/^\/sql\s+(.+)/is);
    if (sqlMatch) {
      const rawSql = sqlMatch[1].trim();
      turns = [
        ...turns,
        { id, question: rawSql, thinking: true, isDirect: true },
      ];
      try {
        const data = await apiCall("/api/execute", { sql: rawSql });
        const rows2d = rowsToArrays(data.columns || [], data.rows || []);
        turns = turns.map((x) =>
          x.id === id
            ? {
                ...x,
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
              }
            : x,
        );
        historyTrigger++;
      } catch (e: any) {
        turns = turns.map((x) =>
          x.id === id
            ? {
                ...x,
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
              }
            : x,
        );
      } finally {
        loading = false;
      }
      return;
    }

    // Normal LLM query flow
    let build_context = [];
    for (let turn of turns.toReversed()) {
      if (build_context.length >= 2) {
        break;
      }
      if (
        turn.thinking == true ||
        !turn.sql ||
        turn.executionError ||
        turn.verdict === "wrong"
      ) {
        continue;
      }
      build_context.push({
        question: turn.question,
        sql: turn.sql,
        restatement: turn.restatement,
      });
    }
    build_context.reverse();
    const artifacts: ThinkingArtifact[] = [];
    turns = [
      ...turns,
      { id, question: q, thinking: true, thinkingArtifacts: artifacts },
    ];
    currentArtifacts = artifacts;
    try {
      await streamApiCall(
        "/api/query/stream",
        { question: q, context: build_context },
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
          const rows2d = rowsToArrays(data.columns || [], data.rows || []);
          turns = turns.map((x) =>
            x.id === id
              ? {
                  ...x,
                  thinking: false,
                  restatement: data.restatement || "",
                  sql: data.sql || "",
                  columns: data.columns || [],
                  rows: rows2d,
                  confidence: data.confidence || "medium",
                  reason: data.confidence_reason || "",
                  basedOn: data.based_on_verified || false,
                  query_id: data.query_id || id,
                  executionError: data.execution_error || null,
                  verdict: null,
                  thinkingArtifacts: [...artifacts],
                }
              : x,
          );
          historyTrigger++;
        },
        (err: Error) => {
          turns = turns.map((x) =>
            x.id === id
              ? {
                  ...x,
                  thinking: false,
                  restatement: "Something went wrong — please try again.",
                  sql: "",
                  columns: [],
                  rows: [],
                  confidence: "low" as const,
                  reason: err.message || "Request failed",
                  basedOn: false,
                  query_id: id,
                  verdict: null,
                  thinkingArtifacts: [...artifacts],
                }
              : x,
          );
        },
      );
    } finally {
      loading = false;
    }
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

  function handleSubmit(e: Event) {
    e.preventDefault();
    ask();
  }
</script>

<div class="page" style="display:flex;height:100%">
  <Sidebar
    {engine}
    {modelName}
    {verifiedCount}
    onSettings={() => (settingsOpen = true)}
    schema={realSchema}
    {dbInfo}
    {historyTrigger}
    onHistorySelect={(h: any) => (input = h.question)}
  />

  <div
    style="flex:1;display:flex;flex-direction:column;min-width:0;position:relative"
  >
    <!-- top bar -->
    <div
      style="display:flex;align-items:center;justify-content:space-between;padding:15px 28px;border-bottom:1px solid var(--border);background:color-mix(in srgb, var(--surface) 70%, transparent);backdrop-filter:blur(8px)"
    >
      <div style="display:flex;align-items:center;gap:10px">
        <span
          style="width:30px;height:30px;border-radius:9px;background:var(--brand-tint);color:var(--brand);display:grid;place-items:center"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
            ><ellipse
              cx="12"
              cy="6"
              rx="7"
              ry="3"
              stroke="currentColor"
              stroke-width="1.9"
            /><path
              d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"
              stroke="currentColor"
              stroke-width="1.9"
            /></svg
          >
        </span>
        <div>
          <div style="font-weight:700;font-size:14.5px;line-height:1.1">
            {dbLabel}
          </div>
          <div style="font-size:11.5px;color:var(--faint);font-weight:600">
            {tableCount > 0
              ? `${tableCount} table${tableCount === 1 ? "" : "s"} · `
              : ""}view only
          </div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px">
        <TrustPill level={trust} count={verifiedCount} />
        {#if turns.length > 0}
          <Button kind="quiet" size="sm" onclick={() => (turns = [])}>
            {#snippet icon()}<svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                ><path
                  d="M12 5v14M5 12h14"
                  stroke="currentColor"
                  stroke-width="2.1"
                  stroke-linecap="round"
                /></svg
              >{/snippet}
            New conversation
          </Button>
        {/if}
      </div>
    </div>

    <!-- feed -->
    <div
      bind:this={feedRef}
      style="flex:1;overflow-y:auto;padding:28px 28px 8px"
    >
      <div style="max-width:720px;margin:0 auto">
        {#if turns.length === 0}
          <Empty {trust} onPick={ask} {starters} />
        {:else}
          {#each turns as t, i (t.id)}
            <AnswerCard
              turn={t}
              isLatest={i === turns.length - 1}
              onVerify={handleVerify}
              liveArtifacts={t.thinking ? currentArtifacts : undefined}
            />
          {/each}
        {/if}
      </div>
    </div>

    <!-- input -->
    <div
      style="padding:14px 28px 20px;border-top:1px solid var(--border);background:var(--surface)"
    >
      <div style="max-width:720px;margin:0 auto;position:relative">
        {#if showSlashMenu}
          <SlashCommandMenu
            commands={slashCommands}
            onSelect={handleSlashCommandSelect}
            onClose={handleSlashMenuClose}
            filter={slashFilter}
            {inputRef}
          />
        {/if}
        <form
          onsubmit={handleSubmit}
          style="display:flex;align-items:center;gap:10px;padding:7px 7px 7px 18px;border:1.5px solid var(--border-2);border-radius:var(--radius-lg);background:var(--surface);box-shadow:var(--shadow-sm);transition:border-color .15s, box-shadow .15s"
        >
          <input
            bind:value={input}
            oninput={handleInput}
            bind:this={inputRef}
            placeholder="Ask anything about your data…"
            aria-label="Ask a question about your data"
            autofocus
            style="flex:1;border:none;outline:none;background:transparent;font-size:15.5px;color:var(--ink)"
          />
          <Button
            kind="primary"
            type="submit"
            disabled={!input.trim() || loading}
          >
            {#snippet icon()}{#if loading}<Spinner />{:else}<svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  ><path
                    d="M5 12h13M13 6l6 6-6 6"
                    stroke="currentColor"
                    stroke-width="2.1"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  /></svg
                >{/if}{/snippet}
            Ask
          </Button>
        </form>
        <div
          style="display:flex;align-items:center;justify-content:center;gap:7px;margin-top:10px;font-size:12px;color:var(--faint)"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            ><rect
              x="5"
              y="10.5"
              width="14"
              height="9.5"
              rx="2.4"
              stroke="currentColor"
              stroke-width="1.8"
            /><path
              d="M8 10.5V8a4 4 0 018 0v2.5"
              stroke="currentColor"
              stroke-width="1.8"
            /></svg
          >
          Only the schema and your question are sent to Google Gemini to generate
          SQL — never your row data.
        </div>
      </div>
    </div>

    {#if toast}<TrustToast {toast} />{/if}
  </div>

  {#if settingsOpen}
    <Settings
      {modelName}
      {setModelName}
      onClose={() => (settingsOpen = false)}
      {onDisconnect}
    />
  {/if}
</div>
