"""Retention: dropout risk, alerts, follow-up and withdrawals."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import AlertStatus, CircumstanceKind, RiskLevel, Subject, WithdrawalReason

if TYPE_CHECKING:
    from .people import Student, User


class RiskScore(Base):
    """Latest dropout-risk score for a student (FR-05.1)."""

    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    score: Mapped[int]
    level: Mapped[RiskLevel] = mapped_column(SqlEnum(RiskLevel))
    factors: Mapped[str] = mapped_column(default="")
    calculated_at: Mapped[datetime]

    student: Mapped["Student"] = relationship()

    HIGH_FROM = 50
    MEDIUM_FROM = 25

    @classmethod
    def level_for(cls, score: int) -> RiskLevel:
        if score >= cls.HIGH_FROM:
            return RiskLevel.HIGH
        if score >= cls.MEDIUM_FROM:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @property
    def factor_list(self) -> list[str]:
        return [f for f in self.factors.split("\n") if f]


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AlertStatus] = mapped_column(SqlEnum(AlertStatus), default=AlertStatus.OPEN)
    opened_at: Mapped[datetime]
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reasons: Mapped[str] = mapped_column(default="")

    student: Mapped["Student"] = relationship()
    # Composition: follow-up actions belong to one alert.
    actions: Mapped[list["FollowUpAction"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )

    @property
    def is_open(self) -> bool:
        return self.status in (AlertStatus.OPEN, AlertStatus.IN_PROGRESS)

    @property
    def reason_list(self) -> list[str]:
        return [r for r in self.reasons.split("\n") if r]

    def add_reason(self, reason: str) -> None:
        """A new trigger joins the open alert instead of duplicating it (FR-05.2)."""
        if reason not in self.reason_list:
            self.reasons = "\n".join(self.reason_list + [reason])

    def close(self, status: AlertStatus, at: datetime) -> None:
        self.status = status
        self.closed_at = at


class FollowUpAction(Base):
    __tablename__ = "follow_up_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("risk_alerts.id"))
    description: Mapped[str]
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date]
    done: Mapped[bool] = mapped_column(default=False)

    alert: Mapped[RiskAlert] = relationship(back_populates="actions")
    assignee: Mapped["User"] = relationship()

    def is_overdue(self, today: date) -> bool:
        return not self.done and self.due_date < today


class Circumstance(Base):
    """Financial or social problem reported by a student or parent (interview Q9)."""

    __tablename__ = "circumstances"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[CircumstanceKind] = mapped_column(SqlEnum(CircumstanceKind))
    note: Mapped[str]
    recorded_on: Mapped[date]
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    student: Mapped["Student"] = relationship(foreign_keys=[student_id])


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    withdrawn_on: Mapped[date]
    reason: Mapped[WithdrawalReason] = mapped_column(SqlEnum(WithdrawalReason))

    student: Mapped["Student"] = relationship()


class MarketingSpend(Base):
    """Monthly marketing spend per subject, for acquisition cost (FR-05.7)."""

    __tablename__ = "marketing_spend"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[Subject] = mapped_column(SqlEnum(Subject))
    month: Mapped[str]
    amount: Mapped[int]


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str]
    link: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime]
    read: Mapped[bool] = mapped_column(default=False)


class AppSetting(Base):
    """Key/value settings: demo clock offset and last EduTizim sync time."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
