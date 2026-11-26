"""Performance: KPI weights, inputs and monthly snapshots."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .people import Student, Teacher


class KpiWeightSet(Base):
    """Indicator weights set by the Head Specialist; must total 100% (FR-04.1)."""

    __tablename__ = "kpi_weight_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    effective_from: Mapped[str]  # month key, e.g. "2026-11"
    set_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Composition: a weight belongs to exactly one set.
    weights: Mapped[list["KpiWeight"]] = relationship(
        back_populates="weight_set", cascade="all, delete-orphan"
    )

    def total(self) -> int:
        return sum(w.percent for w in self.weights)

    def is_valid(self) -> bool:
        return self.total() == 100 and all(w.percent >= 0 for w in self.weights)

    def weight_for(self, indicator_code: str) -> int:
        for weight in self.weights:
            if weight.indicator_code == indicator_code:
                return weight.percent
        return 0


class KpiWeight(Base):
    __tablename__ = "kpi_weights"

    id: Mapped[int] = mapped_column(primary_key=True)
    weight_set_id: Mapped[int] = mapped_column(ForeignKey("kpi_weight_sets.id"))
    indicator_code: Mapped[str]
    percent: Mapped[int]

    weight_set: Mapped[KpiWeightSet] = relationship(back_populates="weights")


class KpiSnapshot(Base):
    """Locked monthly result for one teacher (FR-04.6)."""

    __tablename__ = "kpi_snapshots"
    __table_args__ = (UniqueConstraint("teacher_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month: Mapped[str]
    overall: Mapped[float]
    partial: Mapped[bool] = mapped_column(default=False)

    teacher: Mapped["Teacher"] = relationship()
    # Composition: indicator scores exist only inside their snapshot.
    scores: Mapped[list["IndicatorScore"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )

    def score_for(self, indicator_code: str) -> float | None:
        for score in self.scores:
            if score.indicator_code == indicator_code:
                return score.score
        return None


class IndicatorScore(Base):
    __tablename__ = "indicator_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("kpi_snapshots.id"))
    indicator_code: Mapped[str]
    score: Mapped[float | None] = mapped_column(nullable=True)
    weight_applied: Mapped[float] = mapped_column(default=0)

    snapshot: Mapped[KpiSnapshot] = relationship(back_populates="scores")


class MonthlyRating(Base):
    """Head Specialist's 0–10 rating for a teacher (FR-04.2)."""

    __tablename__ = "monthly_ratings"
    __table_args__ = (UniqueConstraint("teacher_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month: Mapped[str]
    rating: Mapped[float]
    rated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    teacher: Mapped["Teacher"] = relationship(foreign_keys=[teacher_id])

    @staticmethod
    def is_valid_rating(value: float) -> bool:
        return 0 <= value <= 10


class Achievement(Base):
    """Professional achievement; counts only once verified (FR-04.3)."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str]
    points: Mapped[int]
    achieved_on: Mapped[date]
    verified: Mapped[bool] = mapped_column(default=False)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    teacher: Mapped["Teacher"] = relationship(foreign_keys=[teacher_id])

    def verify(self, head_specialist_id: int) -> None:
        self.verified = True
        self.verified_by_id = head_specialist_id


class Feedback(Base):
    """One rating per student per teacher per month (FR-04.4)."""

    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("student_id", "teacher_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month: Mapped[str]
    rating: Mapped[int]
    comment: Mapped[str | None] = mapped_column(nullable=True)

    student: Mapped["Student"] = relationship(foreign_keys=[student_id])
    teacher: Mapped["Teacher"] = relationship(foreign_keys=[teacher_id])

    @property
    def is_negative(self) -> bool:
        return self.rating <= 2


class TestResult(Base):
    """Monthly average of weekly tests, or the monthly mock exam score."""

    __tablename__ = "test_results"
    __test__ = False  # not a pytest class

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    month: Mapped[str]
    kind: Mapped[str]  # "weekly" or "mock"
    score: Mapped[float]
