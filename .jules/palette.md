## 2026-06-25 - Playwright character encoding with standalone React
**Learning:** When mocking an HTML document to test specific React components (like `ResultTable` in `index.html`) using Playwright, if the mock lacks a proper `<meta charset="UTF-8"/>` tag, unicode characters like the "✓" checkmark may render as garbled mojibake (e.g. "âœ“") in the resulting screenshots, obscuring the UX validation.
**Action:** Always include `<meta charset="UTF-8"/>` within the `<head>` of mocked HTML documents constructed for Playwright verification to ensure correct visual rendering of unicode text and icons.
## 2026-06-25 - JS Conditional Hover and Keyboard Accessibility
**Learning:** Conditionally rendering action buttons (like delete icons) based strictly on JS mouse events (`onmouseenter` / `onmouseleave`) completely removes the elements from the DOM for keyboard users, making them inaccessible.
**Action:** Always render utility actions in the DOM and use CSS techniques like `group-hover:opacity-100` alongside `focus:opacity-100` to manage visual clutter without sacrificing keyboard accessibility.
