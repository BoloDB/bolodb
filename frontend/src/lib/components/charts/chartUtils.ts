export type ChartType = "bar" | "pie" | "line" | null;

export interface ChartDetection {
  type: ChartType;
  labelKey: string;
  valueKey: string;
  data: { label: string; value: number }[];
}

const DATE_PATTERNS = [
  /^\d{4}-\d{2}-\d{2}/,
  /^\d{2}\/\d{2}\/\d{4}/,
  /^\d{4}\/\d{2}\/\d{2}/,
  /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i,
  /^(q[1-4]\s?\d{4})/i,
  /^\d{4}-\w{3}/,
];

function isDateLike(v: string): boolean {
  return DATE_PATTERNS.some((p) => p.test(v));
}

export function parseNumeric(v: string): number | null {
  if (v == null || v === "") return null;
  const cleaned = String(v).replace(/[$%,\s]/g, "");
  const n = Number(cleaned);
  return Number.isFinite(n) ? n : null;
}

export function formatNumber(n: number): string {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

export function detectChartData(
  columns: string[],
  rows: string[][],
): ChartDetection | null {
  if (!columns || columns.length < 2 || !rows || rows.length < 1) return null;

  let best: ChartDetection | null = null;
  let bestScore = -1;

  for (let colIdx = 0; colIdx < columns.length; colIdx++) {
    for (let valIdx = 0; valIdx < columns.length; valIdx++) {
      if (colIdx === valIdx) continue;

      const labelCol = columns[colIdx];
      const valueCol = columns[valIdx];

      const sampleValues = rows.slice(0, 30).map((r) => r?.[valIdx]);
      const numericCount = sampleValues.filter(
        (v) => parseNumeric(v) !== null,
      ).length;
      const numericRatio = numericCount / Math.max(sampleValues.length, 1);

      if (numericRatio < 0.4) continue;

      const data = rows
        .map((r) => {
          const parsed = parseNumeric(String(r?.[valIdx] ?? ""));
          return parsed !== null
            ? { label: String(r?.[colIdx] ?? ""), value: parsed }
            : null;
        })
        .filter(
          (d): d is { label: string; value: number } =>
            d !== null && d.label !== "",
        );

      if (data.length < 1) continue;

      const isTimeSeries = isDateLike(data[0].label);
      const isSmallSet = data.length <= 8;
      const allPositive = data.every((d) => d.value >= 0);
      let type: ChartType = "bar";
      let score = numericRatio * 10 + data.length;

      if (isTimeSeries) {
        type = "line";
        score += 5;
      } else if (isSmallSet && allPositive) {
        const total = data.reduce((s, d) => s + d.value, 0);
        if (total > 0 && data.every((d) => d.value / total > 0.02)) {
          type = "pie";
          score += 3;
        }
      }

      if (score > bestScore) {
        bestScore = score;
        best = { type, labelKey: labelCol, valueKey: valueCol, data };
      }
    }
  }

  return best;
}

/** A chart the model asked for, resolved against the columns actually returned. */
export interface ChartPlan {
  type: "bar" | "pie" | "line" | "area" | "number";
  labelKey: string;
  valueKey: string;
  data: { label: string; value: number }[];
  title: string;
}

/**
 * Resolve the model's chart choice against real result columns.
 *
 * The model picks from the SQL it wrote, so its axis names normally match. When
 * they don't — a renamed alias, a repaired query — we fall back to the
 * positional heuristic rather than rendering nothing.
 */
export function planChart(
  spec:
    | { type?: string; x_axis?: string; y_axis?: string; title?: string }
    | null
    | undefined,
  columns: string[],
  rows: string[][],
): ChartPlan | null {
  const type = spec?.type;
  if (!type || type === "table") return null;
  if (!columns?.length || !rows?.length) return null;

  const findCol = (name?: string) => {
    if (!name) return -1;
    const target = name.trim().toLowerCase();
    return columns.findIndex((c) => c.trim().toLowerCase() === target);
  };

  if (type === "number") {
    const valIdx = findCol(spec?.y_axis);
    const idx = valIdx >= 0 ? valIdx : 0;
    const value = parseNumeric(String(rows[0]?.[idx] ?? ""));
    if (value === null) return null;
    return {
      type: "number",
      labelKey: "",
      valueKey: columns[idx],
      data: [{ label: columns[idx], value }],
      title: spec?.title || "",
    };
  }

  if (type !== "bar" && type !== "pie" && type !== "line" && type !== "area") {
    return null;
  }

  let labelIdx = findCol(spec?.x_axis);
  let valueIdx = findCol(spec?.y_axis);

  if (labelIdx < 0 || valueIdx < 0 || labelIdx === valueIdx) {
    const detected = detectChartData(columns, rows);
    if (!detected) return null;
    labelIdx = columns.indexOf(detected.labelKey);
    valueIdx = columns.indexOf(detected.valueKey);
    if (labelIdx < 0 || valueIdx < 0) return null;
  }

  const data = rows
    .map((r) => {
      const value = parseNumeric(String(r?.[valueIdx] ?? ""));
      return value === null
        ? null
        : { label: String(r?.[labelIdx] ?? ""), value };
    })
    .filter((d): d is { label: string; value: number } => d !== null);

  if (!data.length) return null;

  return {
    type,
    labelKey: columns[labelIdx],
    valueKey: columns[valueIdx],
    data,
    title: spec?.title || "",
  };
}

export const CHART_COLORS = [
  "var(--brand)",
  "#6366f1",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#14b8a6",
];

export const CONFIDENCE_COLORS: Record<string, string> = {
  High: "var(--c-high)",
  Medium: "var(--c-med)",
  Low: "var(--c-low)",
};
