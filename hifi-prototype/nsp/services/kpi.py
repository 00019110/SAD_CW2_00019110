"""UC-04 teacher KPI: seven weighted indicators (FR-04).

Each indicator is its own class behind the KpiIndicator interface. KpiService
only loops over the list, so the centre can add, remove or re-weight indicators
(interview Q8: the mix "should be further researched and fine tuned") without
changing the calculation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..data import AttendanceRepository, PerformanceRepository, RetentionRepository, UserRepository
from ..domain import (
    Achievement,
    AttendanceStatus,
    IndicatorScore,
    KpiSnapshot,
    KpiWeight,
    KpiWeightSet,
    MonthlyRating,
    Subject,
    Teacher,
    User,
)
from ..domain.people import CONFIGURE_KPI, RATE_TEACHERS
from .clock import Clock, month_bounds, month_key, recent_months, shift_month
from .retention import count_retained

MIN_FEEDBACK_RESPONSES = 5


class KpiError(Exception):
    pass


class KpiContext:
    """The repositories an indicator may read from."""

    def __init__(self, db: Session, clock: Clock) -> None:
        self.clock = clock
        self.users = UserRepository(db)
        self.attendance = AttendanceRepository(db)
        self.performance = PerformanceRepository(db)
        self.retention = RetentionRepository(db)


class KpiIndicator(ABC):
    """Interface: one KPI indicator, scored 0-100 for a teacher and month."""

    code: str
    label: str
    short: str

    def applies_to(self, teacher: Teacher) -> bool:
        return True

    @abstractmethod
    def measure(self, teacher: Teacher, month: str, context: KpiContext) -> float | None:
        """Return 0-100, or None when there is too little data."""


class TestResultsIndicator(KpiIndicator):
    code, label, short = "results", "Student test and mock results", "Results"
    __test__ = False

    def applies_to(self, teacher: Teacher) -> bool:
        return teacher.records_tests  # support teachers have no mock-exam groups

    def measure(self, teacher, month, context):
        group_ids = [g.id for g in teacher.teaching_groups]
        return context.performance.average_test_score(group_ids, month)


class StudentAttendanceIndicator(KpiIndicator):
    code, label, short = "attendance", "Student attendance in the teacher's groups", "Attendance"

    def measure(self, teacher, month, context):
        start, end = month_bounds(month)
        group_ids = [g.id for g in teacher.teaching_groups]
        entries = [
            e
            for e in context.attendance.entries_for_groups(group_ids, start, end)
            if e.status is not AttendanceStatus.EXCUSED
        ]
        if not entries:
            return None
        return 100 * sum(1 for e in entries if e.attended) / len(entries)


class PunctualityIndicator(KpiIndicator):
    code, label, short = "punctuality", "Teacher punctuality from QR check-ins", "Punctuality"

    def measure(self, teacher, month, context):
        start, end = month_bounds(month)
        sessions = context.attendance.work_sessions_between(teacher.id, start, end)
        if not sessions:
            return None
        return 100 * sum(1 for s in sessions if s.minutes_late == 0) / len(sessions)


class RetentionIndicator(KpiIndicator):
    code, label, short = "retention", "Student retention", "Retention"

    def measure(self, teacher, month, context):
        group_ids = [g.id for g in teacher.teaching_groups]
        withdrawn = {w.student_id: w.withdrawn_on for w in context.retention.withdrawals()}
        at_start, kept = count_retained(context.users.students_in_groups(group_ids), month, withdrawn)
        if not at_start:
            return None
        return 100 * kept / at_start


class FeedbackIndicator(KpiIndicator):
    code, label, short = "feedback", "Student feedback", "Feedback"

    def measure(self, teacher, month, context):
        feedback = context.performance.feedback_for_teacher(teacher.id, month)
        if len(feedback) < MIN_FEEDBACK_RESPONSES:
            return None
        average = sum(f.rating for f in feedback) / len(feedback)
        return (average - 1) / 4 * 100


class HeadRatingIndicator(KpiIndicator):
    code, label, short = "rating", "Head Specialist's monthly rating", "Head rating"

    def measure(self, teacher, month, context):
        rating = context.performance.rating(teacher.id, month)
        return None if rating is None else rating.rating * 10


class AchievementsIndicator(KpiIndicator):
    code, label, short = "achievements", "Professional achievements", "Achievements"

    def measure(self, teacher, month, context):
        verified = context.performance.achievements(teacher.id, verified_only=True)
        return float(min(100, sum(a.points for a in verified)))


INDICATORS: list[KpiIndicator] = [
    TestResultsIndicator(),
    StudentAttendanceIndicator(),
    PunctualityIndicator(),
    RetentionIndicator(),
    FeedbackIndicator(),
    HeadRatingIndicator(),
    AchievementsIndicator(),
]

DEFAULT_WEIGHTS = {
    "results": 25,
    "attendance": 10,
    "punctuality": 10,
    "retention": 20,
    "feedback": 20,
    "rating": 10,
    "achievements": 5,
}


@dataclass
class IndicatorResult:
    code: str
    label: str
    short: str
    score: float | None
    weight: float  # configured weight, %
    applied: float  # weight after redistribution, %
    note: str = ""


@dataclass
class KpiResult:
    teacher: Teacher
    month: str
    overall: float | None
    indicators: list[IndicatorResult] = field(default_factory=list)
    partial: bool = False
    provisional: bool = False
    change: float | None = None

    @property
    def status(self) -> str:
        if self.provisional:
            return "Provisional"
        return "Partial" if self.partial else "Final"

    def indicator(self, code: str) -> IndicatorResult | None:
        return next((i for i in self.indicators if i.code == code), None)


class KpiService:
    def __init__(self, db: Session, clock: Clock, indicators: list[KpiIndicator] | None = None) -> None:
        self.db = db
        self.clock = clock
        self.indicators = indicators or INDICATORS
        self.context = KpiContext(db, clock)
        self.users = self.context.users
        self.performance = self.context.performance

    # -- calculation ------------------------------------------------------
    def current_month(self) -> str:
        return month_key(self.clock.today())

    def calculate(self, teacher: Teacher, month: str) -> KpiResult:
        """Calculate Teacher KPI: a stored snapshot for closed months, live otherwise."""
        if month < self.current_month():
            snapshot = self.performance.snapshot(teacher.id, month)
            if snapshot is not None:
                return self._from_snapshot(teacher, snapshot)
        return self._calculate_live(teacher, month)

    def _calculate_live(self, teacher: Teacher, month: str) -> KpiResult:
        weights = self.performance.weight_set_for(month)
        if weights is None or not weights.is_valid():
            raise KpiError("KPI weights are not configured or do not total 100%.")  # ext. 2a

        result = KpiResult(teacher, month, overall=None)
        result.provisional = month >= self.current_month()  # month still running (ext. 1a)
        for indicator in self.indicators:
            weight = weights.weight_for(indicator.code)
            score, note = None, ""
            if not indicator.applies_to(teacher):
                note = "Does not apply to this role"
                result.partial = True
            else:
                score = indicator.measure(teacher, month, self.context)
                if score is None:
                    if indicator.code == "rating":
                        note = "Rating not entered yet"
                        result.provisional = True  # ext. 2c
                    else:
                        note = "Not enough data"
                        result.partial = True  # ext. 2b
            result.indicators.append(
                IndicatorResult(indicator.code, indicator.label, indicator.short, score, weight, 0.0, note)
            )

        # ext. 2b: share the weight of left-out indicators among the others.
        included = sum(i.weight for i in result.indicators if i.score is not None)
        if included:
            total = 0.0
            for item in result.indicators:
                if item.score is not None:
                    item.applied = item.weight / included * 100
                    total += item.score * item.applied / 100
            result.overall = round(total, 1)
        return result

    def _from_snapshot(self, teacher: Teacher, snapshot: KpiSnapshot) -> KpiResult:
        result = KpiResult(teacher, snapshot.month, round(snapshot.overall, 1), partial=snapshot.partial)
        stored = {s.indicator_code: s for s in snapshot.scores}
        weights = self.performance.weight_set_for(snapshot.month)
        for indicator in self.indicators:
            score = stored.get(indicator.code)
            result.indicators.append(
                IndicatorResult(
                    indicator.code,
                    indicator.label,
                    indicator.short,
                    score.score if score else None,
                    weights.weight_for(indicator.code) if weights else 0,
                    score.weight_applied if score else 0.0,
                    "" if score and score.score is not None else "Left out",
                )
            )
        return result

    def ranking(self, month: str, subject: Subject | None = None, role: str | None = None) -> list[KpiResult]:
        """Ranking table with the change from the previous month (UC-04 step 3)."""
        previous = shift_month(month, -1)
        results = []
        for teacher in self.users.teachers(subject, role):
            result = self.calculate(teacher, month)
            before = self.performance.snapshot(teacher.id, previous)
            if result.overall is not None and before is not None:
                result.change = round(result.overall - before.overall, 1)
            results.append(result)
        results.sort(key=lambda r: -(r.overall or 0))
        return results

    def trend(self, teacher: Teacher, month: str, months: int = 6) -> list[tuple[str, float | None]]:
        return [(m, self.calculate(teacher, m).overall) for m in recent_months(month, months)]

    def retention_by_group(self, teacher: Teacher, month: str) -> list[tuple[str, int, int]]:
        """(group name, students at the start of the month, still active) per group."""
        withdrawn = {w.student_id: w.withdrawn_on for w in self.context.retention.withdrawals()}
        return [
            (group.name, *count_retained(group.students, month, withdrawn))
            for group in teacher.teaching_groups
        ]

    def close_month(self, month: str) -> int:
        """Store a locked snapshot for every teacher with a submitted rating (FR-04.6)."""
        if month >= self.current_month():
            raise KpiError("The month has not ended yet; scores stay provisional.")
        saved = 0
        for teacher in self.users.teachers():
            if self.performance.snapshot(teacher.id, month) is not None:
                continue
            result = self._calculate_live(teacher, month)
            if result.overall is None or result.indicator("rating").score is None:
                continue
            snapshot = KpiSnapshot(
                teacher_id=teacher.id, month=month, overall=result.overall, partial=result.partial
            )
            for item in result.indicators:
                snapshot.scores.append(
                    IndicatorScore(indicator_code=item.code, score=item.score, weight_applied=item.applied)
                )
            self.db.add(snapshot)
            saved += 1
        self.db.flush()
        return saved

    # -- configuration (Head Specialist) ------------------------------------
    def weights_for(self, month: str) -> KpiWeightSet | None:
        return self.performance.weight_set_for(month)

    def pending_weights(self) -> KpiWeightSet | None:
        return self.performance.weight_set_exactly(shift_month(self.current_month(), 1))

    def save_weights(self, head: User, percents: dict[str, int]) -> KpiWeightSet:
        """New weights apply from next month and never change past results (FR-04.1)."""
        if not head.can(CONFIGURE_KPI):
            raise KpiError("Only the Head Specialist can configure KPI weights.")
        codes = [i.code for i in self.indicators]
        if any(percents.get(code, 0) < 0 for code in codes):
            raise KpiError("A weight cannot be negative.")
        total = sum(percents.get(code, 0) for code in codes)
        if total != 100:
            raise KpiError(f"The weights total {total}%. They must add up to exactly 100%.")
        effective = shift_month(self.current_month(), 1)
        existing = self.performance.weight_set_exactly(effective)
        if existing is not None:
            self.db.delete(existing)
            self.db.flush()
        weight_set = KpiWeightSet(effective_from=effective, set_by_id=head.id)
        for code in codes:
            weight_set.weights.append(KpiWeight(indicator_code=code, percent=percents.get(code, 0)))
        self.db.add(weight_set)
        self.db.flush()
        return weight_set

    def rate(self, head: User, teacher: Teacher, month: str, value: float) -> MonthlyRating:
        if not head.can(RATE_TEACHERS):
            raise KpiError("Only the Head Specialist can rate teachers.")
        if not MonthlyRating.is_valid_rating(value):
            raise KpiError("The rating must be between 0 and 10.")
        rating = self.performance.rating(teacher.id, month)
        if rating is None:
            rating = MonthlyRating(teacher_id=teacher.id, month=month, rating=value)
            self.db.add(rating)
        rating.rating = value
        rating.rated_by_id = head.id
        self.db.flush()
        return rating

    def verify_achievement(self, head: User, achievement: Achievement) -> None:
        if not head.can(RATE_TEACHERS):
            raise KpiError("Only the Head Specialist can verify achievements.")
        achievement.verify(head.id)
        self.db.flush()
