/** BoloDB — Static data & helpers (formerly window.BOLO) */
import type {
  Provider,
  TrustLevel,
  WrongReason,
  SchemaTable,
  GlossaryItem,
  StarterItem,
  BankItem,
} from "./types";

export const schema: SchemaTable[] = [
  {
    name: "customers",
    rows: "4,820",
    cols: ["id PK", "name", "email", "segment", "country", "created_at"],
    compact:
      "customers(id PK, name, email, segment[consumer,business,vip], country, created_at)",
  },
  {
    name: "orders",
    rows: "38,104",
    cols: [
      "id PK",
      "customer_id→customers.id",
      "status",
      "total_amount",
      "created_at",
    ],
    compact:
      "orders(id PK, customer_id→customers.id, status[completed,pending,cancelled,refunded], total_amount, created_at)",
  },
  {
    name: "order_items",
    rows: "96,512",
    cols: [
      "id PK",
      "order_id→orders.id",
      "product_id→products.id",
      "quantity",
      "unit_price",
    ],
    compact:
      "order_items(id PK, order_id→orders.id, product_id→products.id, quantity, unit_price)",
  },
  {
    name: "products",
    rows: "312",
    cols: ["id PK", "name", "category", "price", "stock"],
    compact:
      "products(id PK, name, category[laptops,phones,accessories,monitors,audio], price, stock)",
  },
  {
    name: "payments",
    rows: "37,440",
    cols: ["id PK", "order_id→orders.id", "method", "amount", "paid_at"],
    compact:
      "payments(id PK, order_id→orders.id, method[card,paypal,bank], amount, paid_at)",
  },
];

export const glossary: GlossaryItem[] = [
  {
    term: "Revenue",
    def: "Sum of total_amount on orders with status = completed",
    maps_to: "orders.total_amount",
    alt: ["Net sales", "Gross sales", "Paid amount"],
  },
  {
    term: "Active customer",
    def: "A customer with at least one order in the last 90 days",
    maps_to: "orders.created_at",
    alt: ["Any registered customer", "Ordered in last 30 days"],
  },
  {
    term: "Top product",
    def: "Product ranked by units sold (sum of quantity)",
    maps_to: "order_items.quantity",
    alt: ["By revenue", "By number of orders"],
  },
];

export const starters: StarterItem[] = [
  {
    q: "How many orders were completed last month?",
    restatement:
      'Count of orders with status "completed" created in the previous calendar month',
    sql: "SELECT COUNT(*) AS completed_orders\nFROM orders\nWHERE status = 'completed'\n  AND created_at >= date('now','start of month','-1 month')\n  AND created_at <  date('now','start of month');",
    columns: ["completed_orders"],
    rows: [["3,182"]],
  },
  {
    q: "Which product category brings in the most revenue?",
    restatement: "Total revenue per product category, highest first",
    sql: "SELECT p.category, ROUND(SUM(oi.quantity*oi.unit_price)) AS revenue\nFROM order_items oi\nJOIN products p ON p.id = oi.product_id\nJOIN orders   o ON o.id = oi.order_id\nWHERE o.status = 'completed'\nGROUP BY p.category\nORDER BY revenue DESC;",
    columns: ["category", "revenue"],
    rows: [
      ["laptops", "$1,284,900"],
      ["phones", "$902,340"],
      ["monitors", "$418,120"],
      ["audio", "$211,470"],
      ["accessories", "$96,880"],
    ],
  },
  {
    q: "How many customers do we have in each segment?",
    restatement: "Count of customers grouped by segment",
    sql: "SELECT segment, COUNT(*) AS customers\nFROM customers\nGROUP BY segment\nORDER BY customers DESC;",
    columns: ["segment", "customers"],
    rows: [
      ["consumer", "3,910"],
      ["business", "712"],
      ["vip", "198"],
    ],
  },
];

/** BoloDB runs all AI operations on Google Gemini (see docs/03-the-ai-layer-gemini.md). */
export const providers: Provider[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    sub: "Gemini API",
    privacy: "Schema + question sent to Google — never your row data",
    cost: "Free tier available, then pay per use",
    accuracy: "Highest",
    badge: "Default",
    model: "gemini-flash-latest",
    tier: "large",
  },
];

export const GEMINI_KEY_URL = "https://aistudio.google.com/app/api-keys";

export const wrongReasons: WrongReason[] = [
  { id: "numbers", label: "Wrong numbers", key: "wrongNumbers" },
  { id: "filter", label: "Wrong filter / dates", key: "wrongFilter" },
  { id: "intent", label: "Not what I meant", key: "wrongIntent" },
  { id: "missing", label: "Missing data", key: "wrongMissing" },
  { id: "other", label: "Something else", key: "wrongOther" },
];

export const suggestions: string[] = [
  "Top customers by spend this month",
  "Which products are low on stock?",
  "Revenue by category",
  "How many orders are pending right now?",
  "What is the average order value?",
  "How many new customers signed up this week?",
];

export function trustFor(n: number): TrustLevel {
  if (n >= 7)
    return {
      key: "trusted",
      label: "Trusted",
      labelKey: "trusted",
      range: [7, Infinity],
      idx: 2,
      behaviour: "Answers are shown directly. Reasoning is one tap away.",
      behaviourKey: "trustedBehaviour",
      next: null,
    };
  if (n >= 3)
    return {
      key: "assisted",
      label: "Assisted",
      labelKey: "assisted",
      range: [3, 6],
      idx: 1,
      behaviour: "Confident answers are shown; novel ones get a second look.",
      behaviourKey: "assistedBehaviour",
      next: 7,
    };
  return {
    key: "supervised",
    label: "Supervised",
    labelKey: "supervised",
    range: [0, 2],
    idx: 0,
    behaviour: "Every answer waits for your confirmation while it learns.",
    behaviourKey: "supervisedBehaviour",
    next: 3,
  };
}

/** Convert API schema response to display format */
export function schemaObjToDisplay(obj: Record<string, any>): SchemaTable[] {
  return Object.entries(obj || {}).map(([name, info]) => ({
    name,
    rows:
      info.row_count != null ? Number(info.row_count).toLocaleString() : "?",
    cols: info.columns.map((c: any) => {
      const fk = (info.foreign_keys || []).find(
        (f: any) => f.column === c.name,
      );
      return (
        c.name +
        (c.primary_key ? " PK" : "") +
        (fk ? "→" + (fk.references || "") : "")
      );
    }),
    compact: `${name}(${info.columns.map((c: any) => c.name).join(", ")})`,
  }));
}

export function humanErrorKey(msg: string): string | null {
  const m = (msg || "").toLowerCase();
  const m = (msg || "").toLowerCase();
  if (
    m.includes("connection refused") ||
    m.includes("could not connect to server") ||
    m.includes("can't connect")
  )
    return "dbConnectionRefused";
  if (
    m.includes("password authentication failed") ||
    m.includes("access denied") ||
    m.includes("login failed")
  )
    return "wrongCredentials";
  if (m.includes("no such file") || m.includes("unable to open database file"))
    return "fileNotFound";
  if (
    m.includes("database") &&
    (m.includes("does not exist") || m.includes("unknown database"))
  )
    return "dbDoesNotExist";
  if (m.includes("timeout") || m.includes("timed out"))
    return "connectionTimedOut";
  if (m.includes("ssl") || m.includes("certificate")) return "sslError";
  if (m.includes("no module named")) return "driverNotInstalled";
  return null;
}

export function capitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

export function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString();
}
