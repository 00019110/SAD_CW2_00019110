"""Attendance: check-ins, teacher work sessions and the lesson register."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import AttendanceStatus, CheckInMethod, CheckInStatus, WorkSessionStatus

if TYPE_CHECKING:
    from .people import Student, Teacher, User
    from .scheduling import ScheduledSession


class CheckIn(Base):
    """One attendance record per person per session (NFR-04.3)."""

    __tablename__ = "check_ins"
    __table_args__ = (UniqueConstraint("user_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    timestamp: Mapped[datetime]
    method: Mapped[CheckInMethod] = mapped_column(SqlEnum(CheckInMethod))
    status: Mapped[CheckInStatus] = mapped_column(SqlEnum(CheckInStatus))
    minutes_late: Mapped[int] = mapped_column(default=0)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    session: Mapped["ScheduledSession"] = relationship()
    confirmed_by: Mapped["User | None"] = relationship(foreign_keys=[confirmed_by_id])


class WorkSession(Base):
    """A teacher's worked time for one session: replaces the Excel log."""

    __tablename__ = "work_sessions"
    __table_args__ = (UniqueConstraint("teacher_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    check_in_at: Mapped[datetime]
    check_out_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[WorkSessionStatus] = mapped_column(
        SqlEnum(WorkSessionStatus), default=WorkSessionStatus.OPEN
    )
    minutes_late: Mapped[int] = mapped_column(default=0)
    overtime_minutes: Mapped[int] = mapped_column(default=0)
    shortfall_minutes: Mapped[int] = mapped_column(default=0)
    correction_reason: Mapped[str | None] = mapped_column(nullable=True)

    teacher: Mapped["Teacher"] = relationship()
    session: Mapped["ScheduledSession"] = relationship()

    def close(self, at: datetime) -> None:
        """Close on check-out; overtime after the planned end, shortfall before it."""
        planned_end = self.session.ends_at
        self.check_out_at = at
        if at < planned_end:
            self.status = WorkSessionStatus.LEFT_EARLY
            self.shortfall_minutes = int((planned_end - at).total_seconds() // 60)
            self.overtime_minutes = 0
        else:
            self.status = WorkSessionStatus.CLOSED
            self.overtime_minutes = int((at - planned_end).total_seconds() // 60)
            self.shortfall_minutes = 0

    def flag_missing_check_out(self) -> None:
        """Forgotten check-out: close at the planned end, await confirmation (FR-01.6)."""
        self.check_out_at = self.session.ends_at
        self.status = WorkSessionStatus.MISSING_CHECKOUT
        self.overtime_minutes = 0

    @property
    def worked_minutes(self) -> int:
        if self.check_out_at is None:
            return 0
        return max(0, int((self.check_out_at - self.check_in_at).total_seconds() // 60))

    @property
    def counts_for_overtime(self) -> bool:
        """Overtime counts only when both scans are confirmed (FR-03.3)."""
        return self.status in (WorkSessionStatus.CLOSED, WorkSessionStatus.LEFT_EARLY)


class LessonRegister(Base):
    __tablename__ = "registers"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)
    locked: Mapped[bool] = mapped_column(default=False)
    late_submission: Mapped[bool] = mapped_column(default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    submitted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    session: Mapped["ScheduledSession"] = relationship()
    submitted_by: Mapped["Teacher | None"] = relationship()
    # Composition: entries cannot exist without their register.
    entries: Mapped[list["RegisterEntry"]] = relationship(
        back_populates="register", cascade="all, delete-orphan"
    )

    def missing_entries(self) -> list["RegisterEntry"]:
        return [e for e in self.entries if e.status is AttendanceStatus.NOT_SCANNED]

    def lock(self, by_teacher_id: int, at: datetime) -> None:
        self.locked = True
        self.submitted_by_id = by_teacher_id
        self.submitted_at = at
        self.late_submission = at.date() > self.session.starts_at.date()

    def count(self, status: AttendanceStatus) -> int:
        return sum(1 for e in self.entries if e.status is status)


class RegisterEntry(Base):
    __tablename__ = "register_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    register_id: Mapped[int] = mapped_column(ForeignKey("registers.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AttendanceStatus] = mapped_column(
        SqlEnum(AttendanceStatus), default=AttendanceStatus.NOT_SCANNED
    )
    reason: Mapped[str | None] = mapped_column(nullable=True)
    scanned: Mapped[bool] = mapped_column(default=False)
    teacher_override: Mapped[bool] = mapped_column(default=False)

    register: Mapped[LessonRegister] = relationship(back_populates="entries")
    student: Mapped["Student"] = relationship()

    @property
    def attended(self) -> bool:
        return self.status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE)
