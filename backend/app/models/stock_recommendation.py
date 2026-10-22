from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StockRecommendation(Base):
    __tablename__ = "stock_recommendations"
    __table_args__ = (
        UniqueConstraint("forecast_run_id", "store_id", "product_id"),
        CheckConstraint("forecast_demand >= 0", name="forecast_demand_non_negative"),
        CheckConstraint("current_stock >= 0", name="current_stock_non_negative"),
        CheckConstraint("recommended_quantity >= 0", name="recommended_quantity_non_negative"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    forecast_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("forecast_runs.id", ondelete="RESTRICT"), nullable=False
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    forecast_demand: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    current_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions_json: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
