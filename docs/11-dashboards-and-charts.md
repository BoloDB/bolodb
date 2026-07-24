# 11. Dashboards and Charts

BoloDB provides built-in visualization and dashboarding capabilities, allowing users to save queries and compile them into interactive dashboards powered by **Apache ECharts**.

---

## 1. Visualization & Chart Type Inference

When BoloDB executes a natural language query, the OpenRouter AI model infers the best visualization format alongside generating the SQL (`backend/app/llm.py`).

### Supported Chart Types
- **`bar`**: Ideal for categorical comparisons (e.g., revenue per category).
- **`line`**: Ideal for continuous time-series data (e.g., daily active users).
- **`area`**: Ideal for cumulative time-series data.
- **`pie`**: Ideal for proportional breakdown of a single metric.
- **`number`**: Ideal for single scalar metric KPIs (e.g., total sales count).
- **`table`**: Default fallback tabular view for multi-column relational data.

### Chart Specification Schema
The AI returns a structured chart specification object as part of `SQL_SCHEMA`:

```json
{
  "chart": {
    "type": "bar",
    "x_column": "category_name",
    "y_columns": ["total_revenue"],
    "title": "Revenue by Product Category"
  }
}
```

The frontend components `frontend/src/lib/components/ChartPanel.svelte`, `frontend/src/lib/components/charts/ResultChart.svelte`, and `frontend/src/lib/components/charts/ChartCard.svelte` consume this specification (using helper utilities from `frontend/src/lib/components/charts/chartUtils.ts`) to dynamic initialize ECharts instances tailored to the data shape.

---

## 2. Saved Queries

Users can save any query result directly from an Answer Card (`frontend/src/lib/components/AnswerCard.svelte`) using `frontend/src/lib/components/SaveQueryDialog.svelte`.

### Backend Implementation
- **Route**: `backend/app/routes/saved_queries.py`
- **Database Service**: `backend/app/pgdatabase/saved_queries.py`
- **Data Model**: `backend/app/models/saved_query.py` (`SavedQuery`)

Saved queries capture:
- SQL query string
- Natural language question & restatement
- Selected chart type and configuration parameters
- Workspace and Database ID scoping

---

## 3. Dashboards & Panels

Dashboards aggregate multiple saved queries or custom query panels into grid layouts.

### Architecture & Endpoints
- **Routes**: `backend/app/routes/dashboards.py`
- **Controller**: `backend/app/controllers/dashboards.py`
- **Database Service**: `backend/app/pgdatabase/dashboards.py`
- **Models**: `backend/app/models/dashboard.py` (`Dashboard`, `DashboardPanel`)

### Key Operations
1. **Dashboard CRUD**: Create, read, update title/description, and delete workspace dashboards.
2. **Panel Batch Update**: `POST /api/dashboards/{id}/panels/batch` allows layout changes (grid coordinates `x, y, w, h`) to be saved atomically as users resize or drag panels in `frontend/src/lib/components/DashboardEditor.svelte`.
3. **Live Query Execution**: Panels execute their stored SQL against the current workspace database connection on load or manual refresh.
