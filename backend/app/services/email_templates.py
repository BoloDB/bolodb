"""HTML and CSV rendering for scheduled query reports.

Inline styles and f-strings, matching ``services/email.py`` — mail clients ignore
stylesheets, and the codebase has no template engine. The palette is the one the
existing transactional emails use: ink #1a1a2e, body #555, muted #999,
panel #f5f5f5.

Everything interpolated here is untrusted: cell values come from the customer's
database and the intro/footer come from whoever created the schedule. Every value
goes through ``escape`` on the way in.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from html import escape

# Cells wider than this are cut in the HTML table. The full value is still in the
# CSV attachment; this only stops one long blob from wrecking the layout.
MAX_CELL_CHARS = 200

# Leading characters that make Excel and Sheets treat a cell as a formula.
_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell_text(value) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) > MAX_CELL_CHARS:
        return text[:MAX_CELL_CHARS] + "…"
    return text


def _is_numeric(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return False
    try:
        float(value.replace(",", "").strip())
        return True
    except (ValueError, AttributeError):
        return False


def select_columns(columns: list[str], display_columns: list[str] | None) -> list[str]:
    """Resolve the schedule's column choice against what the query returned.

    ``display_columns`` both filters and orders. Names that no longer exist are
    dropped rather than erroring — a column disappearing from the result is a
    reason to send a narrower report, not to stop reporting. An empty or
    fully-stale selection falls back to every column.
    """
    if not display_columns:
        return list(columns)
    available = set(columns)
    chosen = [c for c in display_columns if c in available]
    return chosen or list(columns)


def render_subject(
    template: str | None,
    *,
    name: str,
    workspace: str = "",
    row_count: int = 0,
    when: datetime | None = None,
) -> str:
    """Fill a subject template, falling back to the schedule name.

    Placeholders: {{name}}, {{workspace}}, {{row_count}}, {{date}}, {{time}}.
    Unknown placeholders are left alone rather than blanked, so a typo is visible
    in the delivered subject instead of silently vanishing.
    """
    moment = when or datetime.now(timezone.utc)
    values = {
        "name": name,
        "workspace": workspace,
        "row_count": str(row_count),
        "date": moment.strftime("%Y-%m-%d"),
        "time": moment.strftime("%H:%M UTC"),
    }
    text = (template or "").strip() or "{{name}} — BoloDB scheduled report"
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value).replace(
            "{{ " + key + " }}", value
        )
    # A subject is a single line by definition. Resend takes JSON rather than
    # raw SMTP, so this is not header injection — it just keeps a pasted
    # multi-line template from rendering as a broken subject.
    return " ".join(text.split())[:300]


def _table_html(columns: list[str], rows: list[dict]) -> str:
    if not columns:
        return ""

    head = "".join(
        '<th style="text-align:left;padding:10px 12px;font-size:12px;font-weight:700;'
        "text-transform:uppercase;letter-spacing:0.04em;color:#666;"
        f'border-bottom:2px solid #e5e5e5;white-space:nowrap">{escape(str(col))}</th>'
        for col in columns
    )

    body_rows = []
    for index, row in enumerate(rows):
        background = "#ffffff" if index % 2 == 0 else "#fafafa"
        cells = []
        for col in columns:
            raw = row.get(col)
            align = "right" if _is_numeric(raw) else "left"
            cells.append(
                f'<td style="padding:10px 12px;font-size:13px;color:#1a1a2e;'
                f'border-bottom:1px solid #efefef;text-align:{align}">'
                f"{escape(_cell_text(raw))}</td>"
            )
        body_rows.append(f'<tr style="background:{background}">{"".join(cells)}</tr>')

    return (
        '<div style="overflow-x:auto;border:1px solid #e5e5e5;border-radius:12px;'
        'margin:0 0 20px">'
        '<table style="border-collapse:collapse;width:100%;'
        'font-family:system-ui,-apple-system,sans-serif">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def _shell(title: str, inner: str) -> str:
    """The branded wrapper every scheduled email shares.

    Wider than the 480px transactional templates — these carry result tables.
    """
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f5">
  <div style="font-family:system-ui,-apple-system,sans-serif;max-width:720px;margin:0 auto;padding:32px 24px;color:#1a1a2e">
    <div style="margin:0 0 24px">
      <span style="font-size:18px;font-weight:800;letter-spacing:-0.02em;color:#1a1a2e">BoloDB</span>
      <span style="font-size:13px;color:#999;margin-left:8px">scheduled report</span>
    </div>
    <h2 style="margin:0 0 16px;font-size:22px;font-weight:700">{escape(title)}</h2>
{inner}
  </div>
</body>
</html>"""


def _paragraph(text: str | None, color: str = "#555", size: int = 15) -> str:
    if not text or not text.strip():
        return ""
    # Author-written prose: keep their line breaks, escape everything else.
    body = escape(text.strip()).replace("\n", "<br>")
    return (
        f'<p style="margin:0 0 20px;font-size:{size}px;line-height:1.6;'
        f'color:{color}">{body}</p>'
    )


def render_report_html(
    *,
    name: str,
    columns: list[str],
    rows: list[dict],
    total_rows: int,
    question: str | None = None,
    sql: str | None = None,
    intro: str | None = None,
    footer: str | None = None,
    schedule_summary: str | None = None,
    truncated: bool = False,
    run_at: datetime | None = None,
    manage_url: str | None = None,
) -> str:
    """The success email: intro, result table, and provenance.

    ``rows`` is already capped to the schedule's ``max_rows``; ``total_rows`` is
    what the query actually returned, so the email can say so when the two differ.
    """
    moment = run_at or datetime.now(timezone.utc)
    parts: list[str] = []

    parts.append(_paragraph(intro))

    if rows:
        parts.append(_table_html(columns, rows))
    else:
        parts.append(
            '<div style="padding:24px;background:#f5f5f5;border-radius:12px;'
            'text-align:center;color:#999;font-size:14px;margin:0 0 20px">'
            "This query returned no rows.</div>"
        )

    shown = len(rows)
    if truncated:
        count_line = (
            f"Showing {shown:,} of {total_rows:,}+ rows — the query hit BoloDB's "
            "result limit."
        )
    elif shown < total_rows:
        count_line = f"Showing the first {shown:,} of {total_rows:,} rows."
    else:
        count_line = f"{total_rows:,} row{'s' if total_rows != 1 else ''}."
    parts.append(
        f'<p style="margin:0 0 24px;font-size:13px;color:#999">{escape(count_line)}</p>'
    )

    parts.append(_paragraph(footer, color="#555", size=14))

    # Provenance block — what was asked, what ran, and on what cadence.
    meta: list[str] = []
    if question:
        meta.append(
            f'<div style="margin:0 0 8px"><span style="color:#999">Question</span><br>'
            f'<span style="color:#555">{escape(question)}</span></div>'
        )
    if schedule_summary:
        meta.append(
            f'<div style="margin:0 0 8px"><span style="color:#999">Schedule</span><br>'
            f'<span style="color:#555">{escape(schedule_summary)}</span></div>'
        )
    meta.append(
        f'<div style="margin:0 0 8px"><span style="color:#999">Run at</span><br>'
        f'<span style="color:#555">{escape(moment.strftime("%Y-%m-%d %H:%M UTC"))}</span></div>'
    )
    if sql:
        meta.append(
            '<div style="margin:12px 0 0"><span style="color:#999">SQL</span><br>'
            '<code style="display:block;margin-top:6px;padding:12px;background:#f5f5f5;'
            "border-radius:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
            f'font-size:12px;color:#1a1a2e;white-space:pre-wrap;word-break:break-word">'
            f"{escape(sql)}</code></div>"
        )

    parts.append(
        '<div style="border-top:1px solid #e5e5e5;padding-top:20px;margin-top:8px;'
        f'font-size:12px;line-height:1.6">{"".join(meta)}</div>'
    )

    if manage_url:
        parts.append(
            f'<p style="margin:20px 0 0;font-size:12px;color:#999">'
            f"You are receiving this because a BoloDB schedule lists your address. "
            f'<a href="{escape(manage_url, quote=True)}" style="color:#1a1a2e">'
            f"Manage this schedule</a>.</p>"
        )

    return _shell(name, "".join(parts))


def render_failure_html(
    *,
    name: str,
    error: str,
    failures: int,
    paused: bool,
    sql: str | None = None,
    manage_url: str | None = None,
) -> str:
    """Sent when a schedule has failed enough times that it needs attention.

    Deliberately not sent on every failure — a report that breaks at 9am daily
    would otherwise become a daily alarm nobody reads.
    """
    lead = (
        f"This scheduled report has failed {failures} time"
        f"{'s' if failures != 1 else ''} in a row and has been paused. "
        "Fix the query or the connection, then resume it from BoloDB."
        if paused
        else f"This scheduled report has failed {failures} time"
        f"{'s' if failures != 1 else ''} in a row."
    )

    parts = [
        '<div style="padding:14px 16px;background:#fff5f5;border:1px solid #ffd7d7;'
        'border-radius:12px;margin:0 0 20px;font-size:14px;color:#8a1f1f">'
        f"{escape(lead)}</div>",
        '<div style="margin:0 0 20px;font-size:13px">'
        '<span style="color:#999">Error</span><br>'
        '<code style="display:block;margin-top:6px;padding:12px;background:#f5f5f5;'
        "border-radius:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
        f'font-size:12px;color:#1a1a2e;white-space:pre-wrap;word-break:break-word">'
        f"{escape(error)}</code></div>",
    ]
    if sql:
        parts.append(
            '<div style="margin:0 0 20px;font-size:13px">'
            '<span style="color:#999">SQL</span><br>'
            '<code style="display:block;margin-top:6px;padding:12px;background:#f5f5f5;'
            "border-radius:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
            f'font-size:12px;color:#1a1a2e;white-space:pre-wrap;word-break:break-word">'
            f"{escape(sql)}</code></div>"
        )
    if manage_url:
        parts.append(
            f'<p style="margin:20px 0 0;font-size:12px;color:#999">'
            f'<a href="{escape(manage_url, quote=True)}" style="color:#1a1a2e">'
            f"Open this schedule in BoloDB</a>.</p>"
        )

    return _shell(f"{name} — failing", "".join(parts))


def _csv_safe(value) -> str:
    """Neutralise spreadsheet formula injection without altering the value's text.

    A leading ' is what Excel and Sheets read as "this is literal text"; the
    displayed value is unchanged.
    """
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_CSV_INJECTION_PREFIXES):
        return "'" + text
    return text


def build_csv(columns: list[str], rows: list[dict]) -> str:
    """Full result set as CSV text, for the optional attachment."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    # Header row too — column names come from the customer's schema, so a column
    # literally called "=cmd|..." is as much a formula to Excel as a cell value is.
    writer.writerow([_csv_safe(col) for col in columns])
    for row in rows:
        writer.writerow([_csv_safe(row.get(col)) for col in columns])
    return buffer.getvalue()


def csv_filename(name: str, when: datetime | None = None) -> str:
    """A filesystem-safe attachment name derived from the schedule name."""
    moment = when or datetime.now(timezone.utc)
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-")
    slug = "-".join(filter(None, slug.split("-")))[:60] or "report"
    return f"{slug}-{moment.strftime('%Y%m%d-%H%M')}.csv"
