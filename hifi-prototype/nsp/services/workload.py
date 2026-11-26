"""Workload report: planned vs worked hours from QR work sessions (FR-03)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..data import AttendanceRepository, TimetableRepository, UserRepository
from ..domain import Lesson, Subject, Teacher, WorkSessionStatus
from .clock import Clock, month_bounds


@dataclass
class WorkloadRow:
    teacher: Teacher
    groups: int = 0
    lessons: int = 0
    support_sessions: int = 0
    planned_minutes: int = 0
    worked_minutes: int = 0
    overtime_minutes: int = 0
    late_arrivals: int = 0
    minutes_late: int = 0
    early_departures: int = 0
    missing_check_outs: int = 0
    not_checked_in: int = 0

    @property
    def planned_hours(self) -> float:
        return round(self.planned_minutes / 60, 1)

    @property
    def worked_hours(self) -> float:
        return round(self.worked_minutes / 60, 1)

    @property
    def overtime_hours(self) -> float:
        return round(self.overtime_minutes / 60, 1)

    @property
    def coverage(self) -> int:
        """Worked hours as a percentage of planned hours."""
        if not self.planned_minutes:
            return 0
        return round(100 * self.worked_minutes / self.planned_minutes)


class WorkloadService:
    def __init__(self, db: Session, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.users = UserRepository(db)
        self.timetable = TimetableRepository(db)
        self.attendance = AttendanceRepository(db)

    def row_for(self, teacher: Teacher, month: str) -> WorkloadRow:
        start, end = month_bounds(month)
        now = self.clock.now()
        row = WorkloadRow(teacher, groups=len(teacher.teaching_groups))
        worked = {
            ws.session_id: ws for ws in self.attendance.work_sessions_between(teacher.id, start, end)
        }
        for session in self.timetable.between(start, min(end, now), teacher.id):
            if isinstance(session, Lesson):
                row.lessons += 1
            else:
                row.support_sessions += 1  # counted exactly like lessons (FR-03.2)
            row.planned_minutes += session.planned_minutes
            work_session = worked.get(session.id)
            if work_session is None:
                if session.ends_at < now:
                    row.not_checked_in += 1
                continue
            row.worked_minutes += work_session.worked_minutes
            if work_session.minutes_late:
                row.late_arrivals += 1
                row.minutes_late += work_session.minutes_late
            if work_session.status is WorkSessionStatus.LEFT_EARLY:
                row.early_departures += 1
            if work_session.status is WorkSessionStatus.MISSING_CHECKOUT:
                row.missing_check_outs += 1
            if work_session.counts_for_overtime:  # FR-03.3
                row.overtime_minutes += work_session.overtime_minutes
        return row

    def report(self, month: str, subject: Subject | None = None, role: str | None = None) -> list[WorkloadRow]:
        rows = [self.row_for(teacher, month) for teacher in self.users.teachers(subject, role)]
        rows.sort(key=lambda r: -r.planned_minutes)
        return rows
