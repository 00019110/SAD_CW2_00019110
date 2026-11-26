"""UC-03 dropout risk: scores, alerts and follow-up (FR-05.1 to FR-05.5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..data import AttendanceRepository, PerformanceRepository, RetentionRepository, UserRepository
from ..domain import (
    Administrator,
    AlertStatus,
    Circumstance,
    CircumstanceKind,
    Feedback,
    FollowUpAction,
    HeadSpecialist,
    RiskAlert,
    RiskLevel,
    RiskScore,
    Student,
    Subject,
    Teacher,
    User,
    Withdrawal,
    WithdrawalReason,
)
from .clock import Clock, month_key, shift_month
from .notifications import NotificationService

ABSENCES_FOR_ALERT = 3
CIRCUMSTANCE_WINDOW = timedelta(days=90)


class RiskError(Exception):
    pass


@dataclass
class RiskRow:
    student: Student
    score: RiskScore | None
    alert: RiskAlert | None

    @property
    def level(self) -> RiskLevel:
        return self.score.level if self.score else RiskLevel.NOT_ENOUGH_DATA


@dataclass
class RiskDashboard:
    rows: list[RiskRow]
    counts: dict[RiskLevel, int]
    open_alerts: list[RiskAlert]
    overdue_actions: int = 0
    total_students: int = 0
    filters: dict = field(default_factory=dict)


class RiskService:
    def __init__(self, db: Session, clock: Clock, notifications: NotificationService) -> None:
        self.db = db
        self.clock = clock
        self.notifications = notifications
        self.users = UserRepository(db)
        self.retention = RetentionRepository(db)
        self.performance = PerformanceRepository(db)
        self.attendance = AttendanceRepository(db)

    # -- score ------------------------------------------------------------
    def calculate(self, student: Student) -> RiskScore:
        """Calculate Dropout Risk Score: absences, feedback, circumstances, debt."""
        now = self.clock.now()
        points, factors = 0, []

        if student.is_new(now.date()):
            level = RiskLevel.NOT_ENOUGH_DATA
        else:
            absences = student.consecutive_absences or 0
            if absences >= ABSENCES_FOR_ALERT:
                points += 50
                factors.append(f"{absences} consecutive absences")
            elif absences == 2:
                points += 25
                factors.append("2 consecutive absences")
            elif absences == 1:
                points += 10
                factors.append("1 recent absence")

            negative, total = self._feedback_counts(student)
            if total and negative * 2 > total:
                points += 30
                factors.append(f"Negative feedback for {negative} of {total} teachers")
            elif negative:
                points += 10
                factors.append("Negative feedback for one teacher")

            recent = self.retention.circumstances(student.id, since=now.date() - CIRCUMSTANCE_WINDOW)
            for kind in sorted({c.kind for c in recent}, key=lambda k: k.value):
                points += 25
                factors.append(f"{kind.value} circumstances reported")

            debt, fee = student.tuition_debt or 0, student.monthly_fee or 0
            if debt and fee and debt >= fee:
                points += 20
                factors.append("Tuition unpaid for a month or more")
            elif debt:
                points += 10
                factors.append("Outstanding tuition balance")

            points = min(points, 100)
            level = RiskScore.level_for(points)

        score = self.retention.risk_score(student.id)
        if score is None:
            score = RiskScore(student_id=student.id, score=0, level=level, calculated_at=now)
            self.db.add(score)
        score.score = points
        score.level = level
        score.factors = "\n".join(factors)
        score.calculated_at = now
        return score

    def recalculate_all(self) -> int:
        students = self.users.students()
        for student in students:
            self.calculate(student)
        self.db.flush()
        return len(students)

    def _feedback_counts(self, student: Student) -> tuple[int, int]:
        month = month_key(self.clock.today())
        feedback = self.performance.feedback_by_student(student.id, month)
        if not feedback:  # early in the month: fall back to last month's survey
            feedback = self.performance.feedback_by_student(student.id, shift_month(month, -1))
        return sum(1 for f in feedback if f.is_negative), len(feedback)

    # -- alerts -----------------------------------------------------------
    def raise_alert(self, student: Student, reason: str) -> RiskAlert:
        """Raise Dropout Risk Alert; a new reason joins an already open alert."""
        self.calculate(student)
        alert = self.retention.open_alert_for(student.id)
        if alert is not None:
            alert.add_reason(reason)
            self.db.flush()
            return alert
        alert = RiskAlert(student_id=student.id, opened_at=self.clock.now(), reasons=reason)
        alert.student = student
        self.db.add(alert)
        self.db.flush()
        groups = ", ".join(g.name for g in student.groups) or "no group"
        self.notifications.notify_roles(
            [Administrator, HeadSpecialist],
            f"Dropout risk alert: {student.full_name} ({groups}) – {reason}.",
            f"/risk/student/{student.id}",
        )
        return alert

    def on_register_submitted(self, student: Student, absence_date: date | None) -> RiskAlert | None:
        """Called for every student after a register is locked (UC-02 ext. 7a, 7b)."""
        absences = student.consecutive_absences or 0
        if absence_date is not None and absences >= ABSENCES_FOR_ALERT:
            return self.raise_alert(student, f"{absences} consecutive absences (latest {absence_date:%d %b})")
        self.calculate(student)
        return None

    def record_circumstance(
        self, administrator: User, student: Student, kind: CircumstanceKind, note: str
    ) -> RiskAlert:
        if not note.strip():
            raise RiskError("Describe what the student or parent reported.")
        self.db.add(
            Circumstance(
                student_id=student.id,
                kind=kind,
                note=note.strip(),
                recorded_on=self.clock.today(),
                recorded_by_id=administrator.id,
            )
        )
        self.db.flush()
        return self.raise_alert(student, f"{kind.value} circumstances reported")

    def submit_feedback(
        self, student: Student, teacher: Teacher, rating: int, comment: str = ""
    ) -> Feedback:
        """One rating per teacher per month, only for the student's own teachers (FR-04.4)."""
        if not 1 <= rating <= 5:
            raise RiskError("The rating must be between 1 and 5.")
        if teacher.id not in {t.id for t in student.teachers}:
            raise RiskError("You can only give feedback to teachers who teach you.")
        month = month_key(self.clock.today())
        given = self.performance.feedback_by_student(student.id, month)
        if any(f.teacher_id == teacher.id for f in given):
            raise RiskError(f"You have already given feedback to {teacher.full_name} this month.")
        feedback = Feedback(
            student_id=student.id, teacher_id=teacher.id, month=month, rating=rating,
            comment=comment.strip() or None,
        )
        self.db.add(feedback)
        self.db.flush()
        negative, total = self._feedback_counts(student)
        if negative * 2 > len(student.teachers) and negative * 2 > total:
            self.raise_alert(student, f"Negative feedback for {negative} of {total} teachers")
        else:
            self.calculate(student)
        return feedback

    # -- follow-up --------------------------------------------------------
    def assign_follow_up(
        self, alert: RiskAlert, description: str, assignee: User, due_date: date
    ) -> FollowUpAction:
        if not alert.is_open:
            raise RiskError("This alert is already closed.")
        if not description.strip():
            raise RiskError("Describe the follow-up action.")
        action = FollowUpAction(description=description.strip(), assignee_id=assignee.id, due_date=due_date)
        alert.actions.append(action)
        alert.status = AlertStatus.IN_PROGRESS
        self.notifications.notify(
            assignee,
            f"Follow-up assigned: {description.strip()} – {alert.student.full_name}, due {due_date:%d %b}.",
            f"/risk/student/{alert.student_id}",
        )
        self.db.flush()
        return action

    def resolve(self, alert: RiskAlert) -> None:
        """The student has returned to lessons (UC-03 ext. 9b)."""
        for action in alert.actions:
            action.done = True
        alert.close(AlertStatus.RESOLVED, self.clock.now())
        self.db.flush()

    def close_as_withdrawn(self, alert: RiskAlert, reason: WithdrawalReason) -> Withdrawal:
        """The student has left: record the withdrawal (UC-03 ext. 9a, FR-05.5)."""
        withdrawal = self.withdraw(alert.student, reason)
        for action in alert.actions:
            action.done = True
        alert.close(AlertStatus.CLOSED_WITHDRAWN, self.clock.now())
        self.db.flush()
        return withdrawal

    def withdraw(self, student: Student, reason: WithdrawalReason) -> Withdrawal:
        withdrawal = self.retention.withdrawal_for(student.id)
        if withdrawal is None:
            withdrawal = Withdrawal(student_id=student.id, withdrawn_on=self.clock.today(), reason=reason)
            self.db.add(withdrawal)
        student.is_active = False
        self.db.flush()
        return withdrawal

    # -- dashboard --------------------------------------------------------
    def dashboard(
        self,
        subject: Subject | None = None,
        group_id: int | None = None,
        teacher_id: int | None = None,
        level: RiskLevel | None = None,
    ) -> RiskDashboard:
        self.recalculate_all()
        scores = self.retention.risk_scores()
        open_alerts = self.retention.alerts(open_only=True)
        alert_by_student = {a.student_id: a for a in open_alerts}

        rows, counts = [], {lvl: 0 for lvl in RiskLevel}
        students = self.users.students()
        for student in students:
            row = RiskRow(student, scores.get(student.id), alert_by_student.get(student.id))
            counts[row.level] += 1
            if subject and not any(g.subject is subject for g in student.groups):
                continue
            if group_id and not any(g.id == group_id for g in student.groups):
                continue
            if teacher_id and teacher_id not in {t.id for t in student.teachers}:
                continue
            if level and row.level is not level:
                continue
            rows.append(row)
        rows.sort(key=lambda r: (-(r.score.score if r.score else 0), r.student.full_name))

        today = self.clock.today()
        overdue = sum(1 for a in open_alerts for action in a.actions if action.is_overdue(today))
        return RiskDashboard(
            rows=rows,
            counts=counts,
            open_alerts=open_alerts,
            overdue_actions=overdue,
            total_students=len(students),
            filters={"subject": subject, "group_id": group_id, "teacher_id": teacher_id, "level": level},
        )
