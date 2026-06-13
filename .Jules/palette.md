## 2024-06-13 - Add visual success state and aria-live to Copy as CSV button
**Learning:** The "Copy as CSV" functionality lacked immediate visual feedback and screen reader announcements, creating friction and uncertainty about whether the clipboard operation succeeded. Adding a timeout-reverted button text change and `aria-live="polite"` resolves this.
**Action:** Always include an `aria-live` announcement and a clear visual success indicator for clipboard operations to improve accessibility and user confidence.
