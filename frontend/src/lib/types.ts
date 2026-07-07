/** BoloDB — TypeScript interfaces */

export interface Provider {
  id: string;
  name: string;
  sub: string;
  privacy: string;
  cost: string;
  accuracy: string;
  badge: string;
  model: string;
  tier: string;
  tone?: string;
  note?: string;
}

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
  tables?: number;
  ok?: boolean;
  has_knowledge?: boolean;
  trust?: { verified: number; level: string };
  starters?: string[];
  glossary?: GlossaryItem[];
  is_sample?: boolean;
}

export interface Turn {
  id: string;
  question: string;
  thinking: boolean;
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
}

export interface Toast {
  title: string;
  body: string;
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

export interface HistoryEntry {
  _id: string;
  question: string;
  sql: string;
  result: Record<string, unknown>[];
  confidence: "High" | "Medium" | "Low";
  timestamp: string;
}
