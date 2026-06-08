import time
import re
from app.schema_link import _tokens, model_budget

def link_relevant_tables_optimized(question, schema, glossary, retrieved, max_tables):
    all_tables = list(schema.keys())
    if len(all_tables) <= max_tables: return all_tables
    q_tokens = _tokens(question)
    for g in glossary:
        q_tokens |= _tokens(g.get("term","")) | _tokens(g.get("maps_to",""))

    table_patterns = {t: re.compile(r"\b"+re.escape(t.lower())+r"\b") for t in all_tables}

    verified_tables = set()
    for ex in retrieved:
        sql_low = (ex.get("sql","") or "").lower()
        for t in all_tables:
            if table_patterns[t].search(sql_low):
                verified_tables.add(t)
    scores = {}
    for t, info in schema.items():
        toks = _tokens(t)
        for c in info.get("columns",[]): toks |= _tokens(c["name"])
        scores[t] = len(q_tokens & toks) + (5 if t in verified_tables else 0)
    picked = [t for t,s in sorted(scores.items(),key=lambda x:-x[1]) if s>0]
    if not picked:
        picked = sorted(all_tables, key=lambda t:-(schema[t].get("row_count") or 0))
    selected = set(picked[:max_tables])
    for t in list(selected):
        for fk in schema[t].get("foreign_keys",[]):
            ref = fk.get("references","").split(".")[0]
            if ref and ref in schema: selected.add(ref)
    ordered = [t for t in picked if t in selected]
    for t in selected:
        if t not in ordered: ordered.append(t)
    return ordered[:max_tables+4]

schema = {f"table_{i}": {"columns": [{"name": "id"}]} for i in range(1000)}
retrieved = [{"sql": f"SELECT * FROM table_{i % 50} WHERE id = 1"} for i in range(500)]
glossary = []
question = "test question"
max_tables = 10

# warm up
link_relevant_tables_optimized(question, schema, glossary, retrieved, max_tables)

start = time.time()
for _ in range(10):
    link_relevant_tables_optimized(question, schema, glossary, retrieved, max_tables)
end = time.time()

print(f"Elapsed time (optimized): {end - start:.4f} seconds")
