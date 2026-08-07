/** BoloDB — shared helpers for scheduled queries.
 *
 * The frontend composes cron expressions from the dialog's controls but never
 * interprets them: `POST /api/schedules/preview` is the only thing that decides
 * what an expression means, so the times shown in the UI are the times the
 * scheduler will actually fire.
 */

export const DEFAULT_SUBJECT_HINT =
  "Leave blank for the schedule name. Placeholders: {{name}}, {{row_count}}, {{date}}, {{time}}, {{workspace}}.";

export interface CronParts {
  frequency: "hourly" | "daily" | "weekly" | "monthly" | "custom";
  /** "HH:MM", used by daily, weekly and monthly. */
  timeOfDay: string;
  /** Minute past the hour, used by hourly. */
  minuteOfHour: number;
  /** 0 = Sunday, matching cron. */
  weekday: number;
  dayOfMonth: number;
  customCron: string;
}

function clamp(value: number, low: number, high: number): number {
  if (!Number.isFinite(value)) return low;
  return Math.min(high, Math.max(low, Math.trunc(value)));
}

function splitTime(timeOfDay: string): { hour: number; minute: number } {
  const [rawHour, rawMinute] = (timeOfDay || "09:00").split(":");
  return {
    hour: clamp(Number(rawHour), 0, 23),
    minute: clamp(Number(rawMinute), 0, 59),
  };
}

/**
 * Build a 5-field cron expression from the dialog's controls.
 *
 * Day-of-month is capped at 28 for monthly schedules: 29-31 silently skip the
 * months that are too short, which reads as a broken report rather than a
 * deliberate choice.
 */
export function buildCron(parts: CronParts): string {
  if (parts.frequency === "custom") {
    return (parts.customCron || "").trim();
  }
  if (parts.frequency === "hourly") {
    return `${clamp(parts.minuteOfHour, 0, 59)} * * * *`;
  }

  const { hour, minute } = splitTime(parts.timeOfDay);

  if (parts.frequency === "daily") {
    return `${minute} ${hour} * * *`;
  }
  if (parts.frequency === "weekly") {
    return `${minute} ${hour} * * ${clamp(parts.weekday, 0, 6)}`;
  }
  return `${minute} ${hour} ${clamp(parts.dayOfMonth, 1, 28)} * *`;
}

const RUN_STATUS_LABELS: Record<string, string> = {
  success: "Delivered",
  failed: "Failed",
  skipped: "Skipped",
};

export function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] || status;
}

/** Format an ISO timestamp for display, or a dash when there isn't one.
 *
 * Rendered in UTC, because the cron fields the user typed are UTC and the pages
 * showing these say so. Left to the viewer's locale, a schedule set for 09:00
 * would read as 14:30 in Kolkata and contradict the row above it.
 */
export function formatWhen(iso?: string | null): string {
  if (!iso) return "—";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "—";
  return when.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}
