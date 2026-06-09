## 2024-06-08 - Unmemoized React lists blocking main thread
**Learning**: Unmemoized list items with complex nested DOM (tables/sql blocks) in React cause significant main thread blocking during typing and fetching in conversational UI.
**Action**: Always `React.memo` list items that receive immutable data, and ensure callbacks are stable using `useCallback` + `useRef` for state access.
