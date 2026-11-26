"""Retention and acquisition-cost figures for the dashboards (FR-05.6, FR-05.7)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..data import RetentionRepository, UserRepository
from ..domain import Student, Subject, Withdrawal
from .clock import Clock, month_bounds, month_key, recent_months


def count_retained(students, month: str, withdrawn: dict[int, date]) -> tuple[int, int]:
    """(students active at the start of the month, of those still active at its end)."""
    start, end = month_bounds(month)
    at_start = kept = 0
    for student in students:
        if student.enrolled_on is None or student.enrolled_on >= start.date():
            continue
        left_on = withdrawn.get(student.id)
        if left_on is not None and left_on < start.date():
            continue
        at_start += 1
        kept += left_on is None or left_on >= end.date()
    return at_start, kept


@dataclass
class RetentionRow:
    label: str
    subject: str
    at_start: int
    kept: int

    @property
    def left(self) -> int:
        return self.at_start - self.kept

    @property
    def retention_rate(self) -> float | None:
        return round(100 * self.kept / self.at_start, 1) if self.at_start else None

    @property
    def dropout_rate(self) -> float | None:
        return round(100 * self.left / self.at_start, 1) if self.at_start else None


@dataclass
class AcquisitionRow:
    subject: Subject
    spend: int
    new_students: int

    @property
    def cost_per_student(self) -> int | None:
        """None means "No enrolments" rather than a division by zero (FR-05.7)."""
        return round(self.spend / self.new_students) if self.new_students else None


class RetentionService:
    def __init__(self, db: Session, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.users = UserRepository(db)
        self.retention = RetentionRepository(db)

    def _withdrawn_on(self) -> dict[int, date]:
        return {w.student_id: w.withdrawn_on for w in self.retention.withdrawals()}

    def _row(self, label: str, subject: str, students: list[Student], month: str, withdrawn: dict) -> RetentionRow:
        at_start, kept = count_retained(students, month, withdrawn)
        return RetentionRow(label, subject, at_start, kept)

    def overall(self, month: str) -> RetentionRow:
        return self._row("All students", "", self.users.students(active_only=False), month, self._withdrawn_on())

    def trend(self, months: int = 6) -> list[tuple[str, float | None]]:
        """Monthly dropout rate: students who left / students active at the start."""
        current = month_key(self.clock.today())
        everyone = self.users.students(active_only=False)
        withdrawn = self._withdrawn_on()
        return [
            (m, self._row(m, "", everyone, m, withdrawn).dropout_rate)
            for m in recent_months(current, months)
        ]

    def by_subject(self, month: str) -> list[RetentionRow]:
        withdrawn = self._withdrawn_on()
        everyone = self.users.students(active_only=False)
        rows = []
        for subject in Subject:
            students = [s for s in everyone if any(g.subject is subject for g in s.groups)]
            rows.append(self._row(subject.value, subject.value, students, month, withdrawn))
        return rows

    def by_group(self, month: str) -> list[RetentionRow]:
        withdrawn = self._withdrawn_on()
        return [
            self._row(group.name, group.subject.value, list(group.students), month, withdrawn)
            for group in self.users.groups()
        ]

    def by_teacher(self, month: str) -> list[RetentionRow]:
        withdrawn = self._withdrawn_on()
        rows = []
        for teacher in self.users.teachers():
            students = {s.id: s for g in teacher.teaching_groups for s in g.students}
            subject = teacher.subject.value if teacher.subject else ""
            rows.append(self._row(teacher.full_name, subject, list(students.values()), month, withdrawn))
        rows.sort(key=lambda r: (r.retention_rate if r.retention_rate is not None else 101))
        return rows

    def recent_withdrawals(self, limit: int = 8) -> list[Withdrawal]:
        return sorted(self.retention.withdrawals(), key=lambda w: w.withdrawn_on, reverse=True)[:limit]

    def acquisition_cost(self, month: str) -> list[AcquisitionRow]:
        """Marketing spend per subject divided by that month's new students."""
        start, end = month_bounds(month)
        spend = self.retention.marketing_spend(month)
        everyone = self.users.students(active_only=False)
        rows = []
        for subject in Subject:
            new_students = sum(
                1
                for s in everyone
                if s.enrolled_on is not None
                and start.date() <= s.enrolled_on < end.date()
                and any(g.subject is subject for g in s.groups)
            )
            rows.append(AcquisitionRow(subject, spend.get(subject, 0), new_students))
        return rows
