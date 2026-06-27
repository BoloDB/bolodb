from fastapi import HTTPException
from backend.app import config as cfgmod
from backend.sample_data import ensure_sample_db
import logging

logger = logging.getLogger(__name__)

async def connect(db, kb, cfg, req_data):
    result = db.connect(req_data.db_url)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    cfg["last_db_url"] = req_data.db_url
    cfgmod.save_config(cfg)
    result["trust"] = kb.trust_level(db.db_id)
    result["glossary"] = kb.get_glossary(db.db_id)
    result["has_knowledge"] = kb.count_verified(db.db_id) > 0
    result["starters"] = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
    return result

async def connect_sample(db, kb, cfg):
    url = ensure_sample_db()
    result = db.connect(url)
    if not result["ok"]:
        raise HTTPException(500, result["error"])
    cfg["last_db_url"] = url
    cfgmod.save_config(cfg)

    if kb.count_verified(db.db_id) == 0:
        kb.set_glossary(
            db.db_id,
            [
                {
                    "term": "Revenue",
                    "maps_to": "orders.total_amount",
                    "sql_hint": "Sum of total_amount on orders with status = completed",
                },
                {
                    "term": "Active customer",
                    "maps_to": "orders.created_at",
                    "sql_hint": "A customer with at least one order in the last 90 days",
                },
                {
                    "term": "Top product",
                    "maps_to": "order_items.quantity",
                    "sql_hint": "Product ranked by units sold (sum of quantity)",
                },
            ],
        )
        kb.add_verified(
            db.db_id,
            "How many orders were completed last month?",
            "SELECT COUNT(*) AS completed_orders\nFROM orders\nWHERE status = 'completed'\n  AND created_at >= date('now','start of month','-1 month')\n  AND created_at <  date('now','start of month');",
            "Count of orders with status 'completed' created in the previous calendar month",
        )
        kb.add_verified(
            db.db_id,
            "Which product category brings in the most revenue?",
            "SELECT p.category, ROUND(SUM(oi.quantity*oi.unit_price)) AS revenue\nFROM order_items oi\nJOIN products p ON p.id = oi.product_id\nJOIN orders   o ON o.id = oi.order_id\nWHERE o.status = 'completed'\nGROUP BY p.category\nORDER BY revenue DESC;",
            "Total revenue per product category, highest first",
        )
        kb.add_verified(
            db.db_id,
            "How many customers do we have in each segment?",
            "SELECT segment, COUNT(*) AS customers\nFROM customers\nGROUP BY segment\nORDER BY customers DESC;",
            "Count of customers grouped by segment",
        )

    result["trust"] = kb.trust_level(db.db_id)
    result["glossary"] = kb.get_glossary(db.db_id)
    result["has_knowledge"] = kb.count_verified(db.db_id) > 0
    result["starters"] = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
    result["is_sample"] = True
    return result

async def disconnect(db, cfg):
    db.disconnect()
    cfg.pop("last_db_url", None)
    try:
        cfgmod.save_config(cfg)
    except Exception as e:
        logger.warning("Failed to save config after disconnect: %s", e)
    return {"ok": True}

async def get_schema(db, refresh):
    if not db.connected:
        raise HTTPException(409, "No database connected")
    return db.get_schema(refresh=refresh)
