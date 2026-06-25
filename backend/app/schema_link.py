"""Schema linking, compact rendering, signal-based confidence, model budgets."""
import re
from backend.app.utils import _tokens

def model_budget(provider, model):
    m = (model or "").lower()
    if provider != "ollama":
        return {"tier":"large","max_tables":15,"samples":2,"max_examples":5}
    if any(x in m for x in ["0.5b","1b","1.5b","2b","mini","tiny"]):
        return {"tier":"tiny","max_tables":5,"samples":0,"max_examples":2}
    return {"tier":"small","max_tables":8,"samples":1,"max_examples":3}

def link_relevant_tables(question, schema, glossary, retrieved, max_tables):
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

def compact_schema(schema, tables, samples):
    lines = []
    for t in tables:
        info = schema.get(t)
        if not info: continue
        fk_map = {fk["column"]:fk["references"] for fk in info.get("foreign_keys",[]) if fk.get("column")}
        parts = []
        for c in info.get("columns",[]):
            seg = c["name"]
            if c.get("primary_key"): seg += " PK"
            if c["name"] in fk_map: seg += f"->{fk_map[c['name']]}"
            dv = info.get("distinct_values",{}).get(c["name"])
            if dv: seg += "[" + ",".join(str(v) for v in dv[:6]) + "]"
            parts.append(seg)
        lines.append(f"{t}({', '.join(parts)})")
        if samples and info.get("sample_rows"):
            lines.append(f"  e.g. {info['sample_rows'][0]}")
    return "\n".join(lines)

def compute_confidence(retrieved, exec_result):
    if exec_result.get("error"):
        return "low", "the generated query did not run - please rephrase", False
    top_sim = max((e.get("similarity",0) for e in retrieved), default=0)
    rows = exec_result.get("rows",[]) or []
    if top_sim >= 0.78: return "high",  "closely matches an answer you verified before", True
    if top_sim >= 0.50: return "medium","similar to an answer you verified before", True
    if len(rows) == 0: return "low",   "no matching rows - the question may not match your data", False
    return "medium", "new question - please confirm it is right", False
