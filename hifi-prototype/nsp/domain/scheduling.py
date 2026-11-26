"""Scheduling: rooms, groups and timetabled sessions (owned by EduTizim)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import Subject

if TYPE_CHECKING:
    from .people import MainTeacher, Student, SupportTeacher, Teacher

CHECK_IN_OPENS_BEFORE = timedelta(minutes=30)
CHECK_IN_CLOSES_AFTER = timedelta(minutes=30)
LATE_AFTER = timedelta(minutes=10)

# Aggregation: a group has students, but students exist without the group.
group_students = Table(
    "group_students",
    Base.metadata,
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
    Column("student_id", ForeignKey("users.id"), primary_key=True),
)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    qr_secret: Mapped[str]


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    subject: Mapped[Subject] = mapped_column(SqlEnum(Subject))
    level: Mapped[str]
    main_teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    support_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    main_teacher: Mapped["MainTeacher"] = relationship(
        back_populates="led_groups", foreign_keys=[main_teacher_id]
    )
    support_teacher: Mapped["SupportTeacher | None"] = relationship(
        back_populates="supported_groups", foreign_keys=[support_teacher_id]
    )
    students: Mapped[list["Student"]] = relationship(
        secondary=group_students, back_populates="groups"
    )

    @property
    def active_students(self) -> list["Student"]:
        return sorted((s for s in self.students if s.is_active), key=lambda s: s.full_name)


class ScheduledSession(Base):
    """Abstract timetable entry; a Lesson or a SupportSession."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]

    group: Mapped[Group] = relationship()
    room: Mapped[Room] = relationship()
    teacher: Mapped["Teacher"] = relationship()

    __mapper_args__ = {"polymorphic_on": "kind", "polymorphic_abstract": True}

    kind_label = "Session"
    has_register = False

    @property
    def planned_minutes(self) -> int:
        return int((self.ends_at - self.starts_at).total_seconds() // 60)

    def is_within_check_in_window(self, now: datetime) -> bool:
        """30 minutes before the start until 30 minutes after it (FR-01.2)."""
        return self.starts_at - CHECK_IN_OPENS_BEFORE <= now <= self.starts_at + CHECK_IN_CLOSES_AFTER

    def minutes_late(self, now: datetime) -> int:
        """Minutes late, counted only after the 10-minute tolerance (FR-01.3)."""
        if now - self.starts_at <= LATE_AFTER:
            return 0
        return int((now - self.starts_at).total_seconds() // 60)

    def involves(self, user_id: int) -> bool:
        return self.teacher_id == user_id or any(s.id == user_id for s in self.group.students)


class Lesson(ScheduledSession):
    __mapper_args__ = {"polymorphic_identity": "lesson"}
    kind_label = "Lesson"
    has_register = True


class SupportSession(ScheduledSession):
    __mapper_args__ = {"polymorphic_identity": "support"}
    topic: Mapped[str | None] = mapped_column(nullable=True)
    kind_label = "Support session"
