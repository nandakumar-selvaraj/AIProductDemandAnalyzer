"""PostgreSQL persistence for normalized sales rows."""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Product, SalesHistory, Store


def persist_sales(
    session: Session, records: Sequence[dict[str, object]], batch_size: int = 1000
) -> tuple[int, int]:
    """Upsert master data and daily sales atomically; return inserted/updated counts."""
    store_codes = sorted({str(row["store_code"]) for row in records})
    item_codes = sorted({str(row["item_code"]) for row in records})
    if store_codes:
        session.execute(
            insert(Store)
            .values(
                [
                    {"store_code": code, "name": f"Store {code.removeprefix('STORE_')}"}
                    for code in store_codes
                ]
            )
            .on_conflict_do_nothing(index_elements=["store_code"])
        )
    if item_codes:
        session.execute(
            insert(Product)
            .values(
                [
                    {"item_code": code, "name": f"Item {code.removeprefix('ITEM_')}"}
                    for code in item_codes
                ]
            )
            .on_conflict_do_nothing(index_elements=["item_code"])
        )
    stores = (
        dict(
            session.execute(
                select(Store.store_code, Store.id).where(Store.store_code.in_(store_codes))
            ).all()
        )
        if store_codes
        else {}
    )
    products = (
        dict(
            session.execute(
                select(Product.item_code, Product.id).where(Product.item_code.in_(item_codes))
            ).all()
        )
        if item_codes
        else {}
    )
    rows = [
        {
            "sale_date": row["sale_date"],
            "store_id": stores[str(row["store_code"])],
            "product_id": products[str(row["item_code"])],
            "units_sold": row["units_sold"],
        }
        for row in records
    ]
    if not rows:
        return 0, 0
    inserted = updated = 0
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset : offset + batch_size]
        keys = [(row["sale_date"], row["store_id"], row["product_id"]) for row in batch]
        existing = set(
            session.execute(
                select(
                    SalesHistory.sale_date, SalesHistory.store_id, SalesHistory.product_id
                ).where(
                    tuple_(
                        SalesHistory.sale_date, SalesHistory.store_id, SalesHistory.product_id
                    ).in_(keys)
                )
            ).all()
        )
        statement = insert(SalesHistory).values(batch)
        statement = statement.on_conflict_do_update(
            index_elements=["sale_date", "store_id", "product_id"],
            set_={"units_sold": statement.excluded.units_sold, "updated_at": func.now()},
        )
        session.execute(statement)
        batch_inserted = sum(key not in existing for key in keys)
        inserted += batch_inserted
        updated += len(batch) - batch_inserted
    return inserted, updated


def parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())
