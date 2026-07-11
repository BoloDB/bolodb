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
