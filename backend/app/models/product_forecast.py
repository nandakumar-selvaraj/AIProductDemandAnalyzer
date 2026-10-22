from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductForecast(Base):
    __tablename__ = "product_forecasts"
    __table_args__ = (
        UniqueConstraint("forecast_run_id", "store_id", "product_id", "forecast_date"),
        CheckConstraint("predicted_units >= 0", name="predicted_units_non_negative"),
        CheckConstraint("lower_bound IS NULL OR lower_bound >= 0", name="lower_bound_non_negative"),
        CheckConstraint("upper_bound IS NULL OR upper_bound >= 0", name="upper_bound_non_negative"),
        CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name="bounds_ordered",
        ),
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
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_units: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
