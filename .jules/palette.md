## 2026-06-25 - Playwright character encoding with standalone React
**Learning:** When mocking an HTML document to test specific React components (like `ResultTable` in `index.html`) using Playwright, if the mock lacks a proper `<meta charset="UTF-8"/>` tag, unicode characters like the "✓" checkmark may render as garbled mojibake (e.g. "âœ“") in the resulting screenshots, obscuring the UX validation.
**Action:** Always include `<meta charset="UTF-8"/>` within the `<head>` of mocked HTML documents constructed for Playwright verification to ensure correct visual rendering of unicode text and icons.

## 2026-06-25 - Copy-to-clipboard interactions
**Learning:** Adding a copy-to-clipboard button to a code block or result table is a high-impact micro-UX improvement that saves users a lot of friction. Using `aria-live="polite"` alongside visual feedback ("✓ Copied!") provides immediate acknowledgement and improves accessibility.
**Action:** Consistently add copy-to-clipboard interactions to elements displaying raw code, SQL, or tabular data, ensuring proper visual and screen reader feedback.
