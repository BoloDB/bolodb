/**
 * Client-side search, filter, sort and paging for a result table.
 *
 * Deliberately pure: the view object is plain state owned by the components, so
 * an answer can hand the same view to its table and its chart and both show the
 * same slice of the result. Nothing here touches the database — the rows are
 * whatever the query already returned.
 */
import { parseNumeric } from "$lib/components/charts/chartUtils";

/** How a column is filtered. Dates fall under "text" — prefix matching on an
 * ISO timestamp ("2024-03") is the useful filter, not a range picker. */
export type ColumnKind = "text" | "number";

export type FilterOp =
  | "contains"
  | "exact"
  | "starts_with"
  | "range"
  | "gt"
  | "lt";

export interface ColumnFilter {
  op: FilterOp;
  /** Operand for contains / exact / starts_with / gt / lt. */
  value: string;
  /** Range bounds. Either side may be blank, which leaves it open-ended. */
  min: string;
  max: string;
}

export interface TableView {
  sortColumn: string | null;
  sortDirection: "asc" | "desc";
  /** Keyed by column name — one filter per column. */
  filters: Record<string, ColumnFilter>;
  search: string;
  page: number;
  pageSize: number;
}

export const PAGE_SIZES = [10, 25, 50, 100];

export function createTableView(pageSize = 10): TableView {
  return {
    sortColumn: null,
    sortDirection: "asc",
    filters: {},
    search: "",
    page: 0,
    pageSize,
  };
}

export function emptyFilter(kind: ColumnKind): ColumnFilter {
  return {
    op: kind === "number" ? "range" : "contains",
    value: "",
    min: "",
    max: "",
  };
}

function blank(v: unknown): boolean {
  return String(v ?? "").trim() === "";
}

/** parseNumeric reads a whitespace-only string as 0; a blank cell is no number. */
function numberOf(v: unknown): number | null {
  return blank(v) ? null : parseNumeric(String(v));
}

/**
 * Guess whether a column holds numbers, from the values themselves.
 *
 * The API sends every cell as a string, so "1,240" and "$18.50" have to be read
 * as numeric or the range filter would be offered on nothing. A column counts
 * as numeric when most of its non-blank values parse.
 */
export function columnKind(rows: string[][], index: number): ColumnKind {
  let seen = 0;
  let numeric = 0;
  for (const row of rows) {
    const cell = row?.[index];
    if (blank(cell)) continue;
    seen++;
    if (parseNumeric(String(cell)) !== null) numeric++;
    if (seen >= 50) break;
  }
  return seen > 0 && numeric / seen >= 0.8 ? "number" : "text";
}

/** A filter with no operand filters nothing — treat it as absent. */
export function isFilterActive(f: ColumnFilter | undefined): boolean {
  if (!f) return false;
  if (f.op === "range") return !blank(f.min) || !blank(f.max);
  return !blank(f.value);
}

export function activeFilters(view: TableView): [string, ColumnFilter][] {
  return Object.entries(view.filters).filter(([, f]) => isFilterActive(f));
}

export function hasActiveView(view: TableView): boolean {
  return !blank(view.search) || activeFilters(view).length > 0;
}

const OP_LABELS: Record<FilterOp, string> = {
  contains: "contains",
  exact: "is",
  starts_with: "starts with",
  range: "between",
  gt: ">",
  lt: "<",
};

/** Chip text, e.g. `revenue between 100–500`. */
export function describeFilter(column: string, f: ColumnFilter): string {
  if (f.op === "range") {
    if (blank(f.min)) return `${column} ≤ ${f.max}`;
    if (blank(f.max)) return `${column} ≥ ${f.min}`;
    return `${column} between ${f.min}–${f.max}`;
  }
  return `${column} ${OP_LABELS[f.op]} ${f.value}`;
}

function matches(cell: string, f: ColumnFilter): boolean {
  const v = String(cell ?? "");
  switch (f.op) {
    // Case-insensitive throughout, including "is": results routinely mix
    // "Shipped" and "shipped", and an exact filter that misses half of them
    // reads as a bug rather than as precision.
    case "contains":
      return v.toLowerCase().includes(f.value.trim().toLowerCase());
    case "exact":
      return v.trim().toLowerCase() === f.value.trim().toLowerCase();
    case "starts_with":
      return v.trim().toLowerCase().startsWith(f.value.trim().toLowerCase());
    case "gt":
    case "lt": {
      const n = numberOf(v);
      const target = numberOf(f.value);
      if (target === null) return true;
      if (n === null) return false;
      return f.op === "gt" ? n > target : n < target;
    }
    case "range": {
      const min = numberOf(f.min);
      const max = numberOf(f.max);
      if (min === null && max === null) return true;
      const n = numberOf(v);
      if (n === null) return false;
      return (min === null || n >= min) && (max === null || n <= max);
    }
  }
}

/** Numbers compare as numbers; everything else compares naturally, so
 * "item2" lands before "item10". */
function compare(a: string, b: string): number {
  const an = parseNumeric(a);
  const bn = parseNumeric(b);
  if (an !== null && bn !== null) return an - bn;
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
}

/**
 * The rows the view selects, in view order — every page of them.
 *
 * Paging is applied separately by `pageOf` so exports and charts can take the
 * whole filtered set.
 */
export function applyView(
  columns: string[],
  rows: string[][],
  view: TableView,
): string[][] {
  let result = rows;

  const search = view.search.trim().toLowerCase();
  if (search) {
    result = result.filter((row) =>
      row.some((cell) =>
        String(cell ?? "")
          .toLowerCase()
          .includes(search),
      ),
    );
  }

  for (const [column, filter] of activeFilters(view)) {
    const index = columns.indexOf(column);
    // A filter can outlive its column when the query is re-run after an edit.
    if (index < 0) continue;
    result = result.filter((row) =>
      matches(String(row?.[index] ?? ""), filter),
    );
  }

  if (view.sortColumn !== null) {
    const index = columns.indexOf(view.sortColumn);
    if (index >= 0) {
      const direction = view.sortDirection === "asc" ? 1 : -1;
      // Copy first: rows belong to the turn, and sorting in place would
      // reorder the stored result behind everyone else's back.
      result = [...result].sort((ra, rb) => {
        const a = String(ra?.[index] ?? "");
        const b = String(rb?.[index] ?? "");
        // Blanks sink to the bottom either way round — they carry no order.
        if (blank(a) || blank(b))
          return blank(a) && blank(b) ? 0 : blank(a) ? 1 : -1;
        return direction * compare(a, b);
      });
    }
  }

  return result;
}

export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / Math.max(pageSize, 1)));
}

/** Filtering can strip out the page you were on; land on the last one instead. */
export function clampPage(
  page: number,
  total: number,
  pageSize: number,
): number {
  return Math.min(Math.max(page, 0), pageCount(total, pageSize) - 1);
}

export function pageOf(rows: string[][], view: TableView): string[][] {
  const page = clampPage(view.page, rows.length, view.pageSize);
  return rows.slice(page * view.pageSize, (page + 1) * view.pageSize);
}

/**
 * CSV of exactly what the view selects.
 *
 * A leading `'` on anything that could be read as a formula keeps a downloaded
 * result from executing when it lands in Excel or Sheets. Only a *leading*
 * `= + - @` is dangerous — the unanchored test this replaces also escaped every
 * cell with a hyphen anywhere in it, which is to say every ISO date.
 */
export function toCSV(columns: string[], rows: string[][]): string {
  const cell = (v: unknown) => {
    let s = String(v ?? "");
    if (/^[\s\x00-\x1f]*[=+\-@]/.test(s)) s = "'" + s;
    return s.includes(",") || s.includes('"') || s.includes("\n")
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };
  const header = columns.map(cell).join(",");
  const body = rows.map((r) => r.map(cell).join(",")).join("\n");
  return header + "\n" + body;
}
