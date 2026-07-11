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
  { id: "numbers", label: "Wrong numbers" },
  { id: "filter", label: "Wrong filter / dates" },
  { id: "intent", label: "Not what I meant" },
  { id: "missing", label: "Missing data" },
  { id: "other", label: "Something else" },
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
      range: [7, Infinity],
      idx: 2,
      behaviour: "Answers are shown directly. Reasoning is one tap away.",
      next: null,
    };
  if (n >= 3)
    return {
      key: "assisted",
      label: "Assisted",
      range: [3, 6],
      idx: 1,
      behaviour: "Confident answers are shown; novel ones get a second look.",
      next: 7,
    };
  return {
    key: "supervised",
    label: "Supervised",
    range: [0, 2],
    idx: 0,
    behaviour: "Every answer waits for your confirmation while it learns.",
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

/** Turn raw SQLAlchemy / driver errors into friendly sentences */
export function humanError(msg: string): string {
  const m = (msg || "").toLowerCase();
  if (
    m.includes("connection refused") ||
    m.includes("could not connect to server") ||
    m.includes("can't connect")
  )
    return "The database server isn't running or can't be reached — check the host and port.";
  if (
    m.includes("password authentication failed") ||
    m.includes("access denied") ||
    m.includes("login failed")
  )
    return "Wrong username or password — double-check your credentials.";
  if (m.includes("no such file") || m.includes("unable to open database file"))
    return "File not found — check the path and make sure the file exists.";
  if (
    m.includes("database") &&
    (m.includes("does not exist") || m.includes("unknown database"))
  )
    return "That database name wasn't found — check the spelling.";
  if (m.includes("timeout") || m.includes("timed out"))
    return "Connection timed out — the server may be unreachable or behind a firewall.";
  if (m.includes("ssl") || m.includes("certificate"))
    return "SSL error — if connecting via URL mode, try adding ?sslmode=disable at the end.";
  if (m.includes("no module named"))
    return "The driver for that database type isn't installed on this server.";
  return msg;
}

export function capitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}
