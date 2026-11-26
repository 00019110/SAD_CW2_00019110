"""Data access layer: every database query lives in a repository class."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..domain import (
    Achievement,
    AlertStatus,
    AppSetting,
    CheckIn,
    Circumstance,
    Feedback,
    Group,
    KpiSnapshot,
    KpiWeightSet,
    Lesson,
    LessonRegister,
    MarketingSpend,
    MonthlyRating,
    Notification,
    RegisterEntry,
    RiskAlert,
    RiskScore,
    Room,
    ScheduledSession,
    Student,
    Subject,
    Teacher,
    TestResult,
    User,
    Withdrawal,
    WorkSession,
    WorkSessionStatus,
    group_students,
)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


class Repository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, entity):
        self.db.add(entity)
        return entity


class UserRepository(Repository):
    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def by_role(self, role_class: type[User]) -> list[User]:
        return list(self.db.scalars(select(role_class).order_by(role_class.full_name)))

    def teachers(self, subject: Subject | None = None, role: str | None = None) -> list[Teacher]:
        query = select(Teacher).where(Teacher.is_active).order_by(Teacher.full_name)
        if subject is not None:
            query = query.where(Teacher.subject == subject)
        if role:
            query = query.where(Teacher.role == role)
        return list(self.db.scalars(query))

    def students(self, active_only: bool = True) -> list[Student]:
        query = select(Student).options(selectinload(Student.groups)).order_by(Student.full_name)
        if active_only:
            query = query.where(Student.is_active)
        return list(self.db.scalars(query))

    def groups(self) -> list[Group]:
        return list(self.db.scalars(select(Group).order_by(Group.name)))

    def group(self, group_id: int) -> Group | None:
        return self.db.get(Group, group_id)

    def students_in_groups(self, group_ids: list[int]) -> list[Student]:
        if not group_ids:
            return []
        query = (
            select(Student)
            .join(group_students, group_students.c.student_id == Student.id)
            .where(group_students.c.group_id.in_(group_ids))
            .distinct()
        )
        return list(self.db.scalars(query))


class TimetableRepository(Repository):
    def get(self, session_id: int) -> ScheduledSession | None:
        return self.db.get(ScheduledSession, session_id)

    def rooms(self) -> list[Room]:
        return list(self.db.scalars(select(Room).order_by(Room.id)))

    def room(self, room_id: int) -> Room | None:
        return self.db.get(Room, room_id)

    def for_user_on(self, user: User, day: date) -> list[ScheduledSession]:
        start, end = day_bounds(day)
        # A late-evening lesson may run past midnight, so look one day either side.
        query = select(ScheduledSession).where(
            ScheduledSession.starts_at >= start - timedelta(hours=12),
            ScheduledSession.starts_at < end + timedelta(hours=12),
        )
        if isinstance(user, Teacher):
            query = query.where(ScheduledSession.teacher_id == user.id)
        elif isinstance(user, Student):
            group_ids = [g.id for g in user.groups]
            if not group_ids:
                return []
            query = query.where(ScheduledSession.group_id.in_(group_ids))
        else:
            return []
        return list(self.db.scalars(query.order_by(ScheduledSession.starts_at)))

    def between(
        self, start: datetime, end: datetime, teacher_id: int | None = None
    ) -> list[ScheduledSession]:
        query = select(ScheduledSession).where(
            ScheduledSession.starts_at >= start, ScheduledSession.starts_at < end
        )
        if teacher_id is not None:
            query = query.where(ScheduledSession.teacher_id == teacher_id)
        return list(self.db.scalars(query.order_by(ScheduledSession.starts_at)))

    def lessons_without_register(self, ended_before: datetime, since: datetime) -> list[Lesson]:
        """Lessons that have ended but have no submitted register (FR-02.8)."""
        submitted = select(LessonRegister.session_id).where(LessonRegister.locked)
        query = (
            select(Lesson)
            .where(Lesson.ends_at < ended_before, Lesson.starts_at >= since)
            .where(Lesson.id.not_in(submitted))
            .order_by(Lesson.starts_at)
        )
        return list(self.db.scalars(query))


class AttendanceRepository(Repository):
    def check_in_for(self, user_id: int, session_id: int) -> CheckIn | None:
        return self.db.scalar(
            select(CheckIn).where(CheckIn.user_id == user_id, CheckIn.session_id == session_id)
        )

    def check_ins_for_session(self, session_id: int) -> list[CheckIn]:
        return list(self.db.scalars(select(CheckIn).where(CheckIn.session_id == session_id)))

    def recent_check_ins(self, user_id: int, limit: int = 8) -> list[CheckIn]:
        query = (
            select(CheckIn)
            .where(CheckIn.user_id == user_id)
            .order_by(CheckIn.timestamp.desc())
            .limit(limit)
        )
        return list(self.db.scalars(query))

    def work_session_for(self, teacher_id: int, session_id: int) -> WorkSession | None:
        return self.db.scalar(
            select(WorkSession).where(
                WorkSession.teacher_id == teacher_id, WorkSession.session_id == session_id
            )
        )

    def work_session(self, work_session_id: int) -> WorkSession | None:
        return self.db.get(WorkSession, work_session_id)

    def open_work_sessions(self, teacher_id: int | None = None) -> list[WorkSession]:
        query = select(WorkSession).where(WorkSession.status == WorkSessionStatus.OPEN)
        if teacher_id is not None:
            query = query.where(WorkSession.teacher_id == teacher_id)
        return list(self.db.scalars(query))

    def flagged_work_sessions(self) -> list[WorkSession]:
        query = (
            select(WorkSession)
            .where(WorkSession.status == WorkSessionStatus.MISSING_CHECKOUT)
            .order_by(WorkSession.check_in_at.desc())
        )
        return list(self.db.scalars(query))

    def work_sessions_between(
        self, teacher_id: int, start: datetime, end: datetime
    ) -> list[WorkSession]:
        query = (
            select(WorkSession)
            .options(selectinload(WorkSession.session))
            .where(
                WorkSession.teacher_id == teacher_id,
                WorkSession.check_in_at >= start,
                WorkSession.check_in_at < end,
            )
        )
        return list(self.db.scalars(query))

    def register_for(self, session_id: int) -> LessonRegister | None:
        return self.db.scalar(
            select(LessonRegister).where(LessonRegister.session_id == session_id)
        )

    def register(self, register_id: int) -> LessonRegister | None:
        return self.db.get(LessonRegister, register_id)

    def entry(self, entry_id: int) -> RegisterEntry | None:
        return self.db.get(RegisterEntry, entry_id)

    def entries_for_groups(
        self, group_ids: list[int], start: datetime, end: datetime
    ) -> list[RegisterEntry]:
        if not group_ids:
            return []
        query = (
            select(RegisterEntry)
            .join(LessonRegister, RegisterEntry.register_id == LessonRegister.id)
            .join(ScheduledSession, LessonRegister.session_id == ScheduledSession.id)
            .where(
                LessonRegister.locked,
                ScheduledSession.group_id.in_(group_ids),
                ScheduledSession.starts_at >= start,
                ScheduledSession.starts_at < end,
            )
        )
        return list(self.db.scalars(query))

    def history_for_student(self, student_id: int, limit: int = 10) -> list[RegisterEntry]:
        query = (
            select(RegisterEntry)
            .join(LessonRegister, RegisterEntry.register_id == LessonRegister.id)
            .join(ScheduledSession, LessonRegister.session_id == ScheduledSession.id)
            .where(RegisterEntry.student_id == student_id, LessonRegister.locked)
            .order_by(ScheduledSession.starts_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(query))


class PerformanceRepository(Repository):
    def weight_set_for(self, month: str) -> KpiWeightSet | None:
        query = (
            select(KpiWeightSet)
            .where(KpiWeightSet.effective_from <= month)
            .order_by(KpiWeightSet.effective_from.desc(), KpiWeightSet.id.desc())
            .limit(1)
        )
        return self.db.scalar(query)

    def weight_set_exactly(self, month: str) -> KpiWeightSet | None:
        query = (
            select(KpiWeightSet)
            .where(KpiWeightSet.effective_from == month)
            .order_by(KpiWeightSet.id.desc())
            .limit(1)
        )
        return self.db.scalar(query)

    def snapshot(self, teacher_id: int, month: str) -> KpiSnapshot | None:
        return self.db.scalar(
            select(KpiSnapshot)
            .options(selectinload(KpiSnapshot.scores))
            .where(KpiSnapshot.teacher_id == teacher_id, KpiSnapshot.month == month)
        )

    def rating(self, teacher_id: int, month: str) -> MonthlyRating | None:
        return self.db.scalar(
            select(MonthlyRating).where(
                MonthlyRating.teacher_id == teacher_id, MonthlyRating.month == month
            )
        )

    def feedback_for_teacher(self, teacher_id: int, month: str) -> list[Feedback]:
        return list(
            self.db.scalars(
                select(Feedback).where(Feedback.teacher_id == teacher_id, Feedback.month == month)
            )
        )

    def feedback_by_student(self, student_id: int, month: str) -> list[Feedback]:
        return list(
            self.db.scalars(
                select(Feedback).where(Feedback.student_id == student_id, Feedback.month == month)
            )
        )

    def achievements(self, teacher_id: int, verified_only: bool = False) -> list[Achievement]:
        query = select(Achievement).where(Achievement.teacher_id == teacher_id)
        if verified_only:
            query = query.where(Achievement.verified)
        return list(self.db.scalars(query.order_by(Achievement.achieved_on.desc())))

    def unverified_achievements(self) -> list[Achievement]:
        return list(self.db.scalars(select(Achievement).where(~Achievement.verified)))

    def achievement(self, achievement_id: int) -> Achievement | None:
        return self.db.get(Achievement, achievement_id)

    def average_test_score(self, group_ids: list[int], month: str) -> float | None:
        if not group_ids:
            return None
        return self.db.scalar(
            select(func.avg(TestResult.score)).where(
                TestResult.group_id.in_(group_ids), TestResult.month == month
            )
        )


class RetentionRepository(Repository):
    def risk_score(self, student_id: int) -> RiskScore | None:
        return self.db.scalar(select(RiskScore).where(RiskScore.student_id == student_id))

    def risk_scores(self) -> dict[int, RiskScore]:
        return {score.student_id: score for score in self.db.scalars(select(RiskScore))}

    def open_alert_for(self, student_id: int) -> RiskAlert | None:
        return self.db.scalar(
            select(RiskAlert).where(
                RiskAlert.student_id == student_id,
                RiskAlert.status.in_([AlertStatus.OPEN, AlertStatus.IN_PROGRESS]),
            )
        )

    def alert(self, alert_id: int) -> RiskAlert | None:
        return self.db.get(RiskAlert, alert_id)

    def alerts(self, open_only: bool = False) -> list[RiskAlert]:
        query = select(RiskAlert).options(selectinload(RiskAlert.actions))
        if open_only:
            query = query.where(RiskAlert.status.in_([AlertStatus.OPEN, AlertStatus.IN_PROGRESS]))
        return list(self.db.scalars(query.order_by(RiskAlert.opened_at.desc())))

    def alerts_for_student(self, student_id: int) -> list[RiskAlert]:
        query = (
            select(RiskAlert)
            .where(RiskAlert.student_id == student_id)
            .order_by(RiskAlert.opened_at.desc())
        )
        return list(self.db.scalars(query))

    def circumstances(self, student_id: int, since: date | None = None) -> list[Circumstance]:
        query = select(Circumstance).where(Circumstance.student_id == student_id)
        if since is not None:
            query = query.where(Circumstance.recorded_on >= since)
        return list(self.db.scalars(query.order_by(Circumstance.recorded_on.desc())))

    def withdrawals(self) -> list[Withdrawal]:
        return list(self.db.scalars(select(Withdrawal).options(selectinload(Withdrawal.student))))

    def withdrawal_for(self, student_id: int) -> Withdrawal | None:
        return self.db.scalar(select(Withdrawal).where(Withdrawal.student_id == student_id))

    def marketing_spend(self, month: str) -> dict[Subject, int]:
        rows = self.db.scalars(select(MarketingSpend).where(MarketingSpend.month == month))
        return {row.subject: row.amount for row in rows}


class NotificationRepository(Repository):
    def for_user(self, user_id: int, limit: int = 15) -> list[Notification]:
        query = (
            select(Notification)
            .where(Notification.recipient_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(query))

    def unread_count(self, user_id: int) -> int:
        return self.db.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == user_id, ~Notification.read
            )
        ) or 0


class SettingsRepository(Repository):
    def get(self, key: str, default: str | None = None) -> str | None:
        setting = self.db.get(AppSetting, key)
        return setting.value if setting else default

    def set(self, key: str, value: str) -> None:
        setting = self.db.get(AppSetting, key)
        if setting is None:
            self.db.add(AppSetting(key=key, value=value))
        else:
            setting.value = value
