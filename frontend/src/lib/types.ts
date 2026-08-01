/** BoloDB — TypeScript interfaces */

export interface TrustLevel {
  key: "supervised" | "assisted" | "trusted";
  label: string;
  range: [number, number];
  idx: number;
  behaviour: string;
  next: number | null;
}

export interface SchemaTable {
  name: string;
  rows: string;
  cols: string[];
  compact: string;
}

export interface GlossaryItem {
  term: string;
  def?: string;
  maps_to?: string;
  alt?: string[];
  sql_hint?: string;
}

export interface StarterItem {
  q?: string;
  question?: string;
  restatement: string;
  sql: string;
  columns: string[];
  rows: (string | Record<string, unknown>)[][];
  error?: string;
}

export interface DbInfo {
  url?: string;
  dialect?: string;
  db_id?: string;
  alias_name?: string;
  tables?: number;
  ok?: boolean;
  has_knowledge?: boolean;
  trust?: { verified: number; level: string };
  starters?: string[];
  glossary?: GlossaryItem[];
  is_sample?: boolean;
  /** Set when the connection succeeded but couldn't be saved to the workspace. */
  save_error?: string;
}

export interface ThinkingArtifact {
  kind:
    | "schema"
    | "hint"
    | "sql"
    | "validation"
    | "repair"
    | "execution"
    | "confidence";
  data: Record<string, unknown>;
}

/** How the model chose to visualise a result. */
export type ChartType = "table" | "bar" | "line" | "area" | "pie" | "number";

export interface ChartSpec {
  type: ChartType;
  /** Column alias for the category/time axis. Empty for table and number. */
  x_axis: string;
  /** Column alias for the numeric value. Empty for table. */
  y_axis: string;
  title: string;
  reason: string;
}

export interface Turn {
  id: string;
  question: string;
  thinking: boolean;
  timestamp?: string;
  restatement?: string;
  sql?: string;
  columns?: string[];
  rows?: string[][];
  confidence?: "high" | "medium" | "low";
  reason?: string;
  basedOn?: boolean;
  query_id?: string;
  executionError?: string | null;
  verdict?: "correct" | "wrong" | null;
  reasonChosen?: string | null;
  isDirect?: boolean;
  /** Restored from history with the stored result capped server-side. */
  resultTruncated?: boolean;
  thinkingArtifacts?: ThinkingArtifact[];
  /** The model's chart choice. Absent on turns from before charts existed. */
  chart?: ChartSpec | null;
  /** Set when the turn's SQL was re-executed without regenerating it. */
  lastRunAt?: string;
}

export type StreamEvent =
  | {
      kind: "schema_linked";
      tables: string[];
      linked: string[];
      glossary: { term: string; maps_to: string }[];
      verified_count: number;
    }
  | { kind: "hint"; message: string; elapsed: number }
  | { kind: "sql"; attempt: number; sql: string }
  | { kind: "chart"; attempt: number; chart: ChartSpec }
  | {
      kind: "validation";
      attempt: number;
      checks: {
        target: string;
        status: "ok" | "error";
        message: string;
        suggestion?: string | null;
      }[];
      passed: boolean;
    }
  | {
      kind: "repair";
      attempt: number;
      total: number;
      error: string;
      suggestion: string;
      old_sql: string;
    }
  | { kind: "execution"; rows: number; elapsed: number; truncated: boolean }
  | {
      kind: "confidence";
      level: string;
      reason: string;
      based_on_verified: boolean;
    }
  | { kind: "result"; data: Record<string, unknown> }
  | { kind: "error"; message: string };

export interface Toast {
  title: string;
  body: string;
  kind?: "success" | "error";
}

export interface WrongReason {
  id: string;
  label: string;
}

export interface BankItem {
  id: string;
  keys: string[];
  q: string;
  restatement: string;
  sql: string;
  columns: string[];
  rows: string[][];
  base: string;
}

export interface Conversation {
  _id: string;
  title: string;
  database_id?: string;
  turn_count: number;
  last_question?: string;
  created_at: string;
  updated_at: string;
}

export interface HistoryEntry {
  _id: string;
  question: string;
  sql: string;
  result: Record<string, unknown>[];
  confidence: "High" | "Medium" | "Low";
  timestamp: string;
}

export interface HistoryStats {
  total_queries: number;
  confidence: { High: number; Medium: number; Low: number };
  daily_activity: { date: string; count: number }[];
  top_tables: { table: string; count: number }[];
}

export interface ConversationTurn {
  _id: string;
  question: string;
  sql: string;
  result: Record<string, unknown>[];
  result_truncated?: boolean;
  confidence: "High" | "Medium" | "Low";
  restatement: string;
  /** Null for turns recorded before the model started choosing a chart. */
  chart?: ChartSpec | null;
  timestamp: string;
}

export interface ConversationDetail extends Conversation {
  turns: ConversationTurn[];
}

/** A saved query that re-runs on a cron schedule and emails its results. */
export interface Schedule {
  id: string;
  _id?: string;
  name: string;
  description?: string | null;
  question?: string | null;
  sql: string;
  database_id?: string | null;
  cron: string;
  /** Server-rendered summary of `cron`, e.g. "Daily at 09:00 UTC". */
  cron_description?: string;
  /** The next five firing times, as ISO strings. */
  upcoming_runs?: string[];
  starts_at?: string | null;
  ends_at?: string | null;
  is_active: boolean;
  recipients: string[];
  subject_template?: string | null;
  intro?: string | null;
  footer?: string | null;
  /** Null means every column the query returns. */
  display_columns?: string[] | null;
  max_rows: number;
  attach_csv: boolean;
  send_condition: "always" | "non_empty" | "row_count_gte" | "row_count_lte";
  condition_value?: number | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_status?: "success" | "failed" | "skipped" | null;
  consecutive_failures: number;
  created_at?: string;
  updated_at?: string;
}

/** One execution of a Schedule, including the ones that deliberately sent nothing. */
export interface ScheduleRun {
  id: string;
  _id?: string;
  schedule_id: string;
  started_at: string;
  finished_at?: string | null;
  status: "success" | "failed" | "skipped";
  row_count?: number | null;
  duration_ms?: number | null;
  /** Why it failed, or which condition suppressed the email. */
  detail?: string | null;
  delivered_to?: string[] | null;
  /** True when started from "Run now" rather than by the scheduler. */
  manual: boolean;
}
