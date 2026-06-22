## 2026-06-22 - Clipboard Feedback
**Learning:** Adding visual feedback alongside `aria-live="polite"` on a copy-to-clipboard button greatly improves the accessibility and UX, providing immediate acknowledgement and reducing friction. Wait states must also be tested explicitly in Playwright using timeouts or delays.
**Action:** Always include `aria-live="polite"` when introducing state changes (like copied success messages) on action buttons, and explicitly verify these changes in headless UI tests.
