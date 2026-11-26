"""People: the User hierarchy (generalization) and role-based permissions."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import Subject

if TYPE_CHECKING:
    from .scheduling import Group

# Permission names (NFR-01.1). Each User subclass declares the ones it holds.
SCAN = "scan"
SUBMIT_REGISTER = "submit_register"
GIVE_FEEDBACK = "give_feedback"
CONFIRM_ATTENDANCE = "confirm_attendance"
RECORD_CIRCUMSTANCE = "record_circumstance"
VIEW_RISK = "view_risk"
MANAGE_ALERTS = "manage_alerts"
VIEW_ALL_KPI = "view_all_kpi"
VIEW_OWN_KPI = "view_own_kpi"
CONFIGURE_KPI = "configure_kpi"
RATE_TEACHERS = "rate_teachers"
VIEW_WORKLOAD = "view_workload"
VIEW_RETENTION = "view_retention"


class User(Base):
    """Abstract account. Accounts are reused from EduTizim (NFR-01.2)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    username: Mapped[str] = mapped_column(unique=True)
    role: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)

    __mapper_args__ = {"polymorphic_on": "role", "polymorphic_abstract": True}

    role_label = "User"

    def permissions(self) -> set[str]:
        """Overridden by every concrete role (polymorphism)."""
        return set()

    def can(self, permission: str) -> bool:
        return permission in self.permissions()

    @property
    def initials(self) -> str:
        return "".join(part[0] for part in self.full_name.split()[:2]).upper()


class Teacher(User):
    """Abstract teacher: shared by main and support teachers."""

    __mapper_args__ = {"polymorphic_abstract": True}

    subject: Mapped[Subject | None] = mapped_column(SqlEnum(Subject), nullable=True)
    hired_on: Mapped[date | None] = mapped_column(nullable=True)

    role_label = "Teacher"
    records_tests = False

    def permissions(self) -> set[str]:
        return {SCAN, SUBMIT_REGISTER, VIEW_OWN_KPI}

    @property
    def teaching_groups(self) -> list["Group"]:
        raise NotImplementedError


class MainTeacher(Teacher):
    """Leads group lessons and records weekly tests and mock exams."""

    __mapper_args__ = {"polymorphic_identity": "main_teacher"}

    led_groups: Mapped[list["Group"]] = relationship(
        back_populates="main_teacher", foreign_keys="Group.main_teacher_id"
    )

    role_label = "Main teacher"
    records_tests = True

    @property
    def teaching_groups(self) -> list["Group"]:
        return list(self.led_groups)


class SupportTeacher(Teacher):
    """Runs support sessions for weaker students; has no mock-exam groups."""

    __mapper_args__ = {"polymorphic_identity": "support_teacher"}

    supported_groups: Mapped[list["Group"]] = relationship(
        back_populates="support_teacher", foreign_keys="Group.support_teacher_id"
    )

    role_label = "Support teacher"

    @property
    def teaching_groups(self) -> list["Group"]:
        return list(self.supported_groups)


class Student(User):
    __mapper_args__ = {"polymorphic_identity": "student"}

    enrolled_on: Mapped[date | None] = mapped_column(nullable=True)
    parent_name: Mapped[str | None] = mapped_column(nullable=True)
    parent_phone: Mapped[str | None] = mapped_column(nullable=True)
    consecutive_absences: Mapped[int | None] = mapped_column(default=0, nullable=True)
    monthly_fee: Mapped[int | None] = mapped_column(default=0, nullable=True)
    tuition_debt: Mapped[int | None] = mapped_column(default=0, nullable=True)

    groups: Mapped[list["Group"]] = relationship(
        secondary="group_students", back_populates="students"
    )

    role_label = "Student"

    def permissions(self) -> set[str]:
        return {SCAN, GIVE_FEEDBACK}

    def register_absence(self) -> int:
        """An unexcused absence extends the run (FR-02.6)."""
        self.consecutive_absences = (self.consecutive_absences or 0) + 1
        return self.consecutive_absences

    def reset_absences(self) -> None:
        self.consecutive_absences = 0

    def is_new(self, today: date) -> bool:
        """Fewer than two weeks of data: no risk score yet (FR-05.3)."""
        return self.enrolled_on is not None and (today - self.enrolled_on).days < 14

    @property
    def teachers(self) -> list[Teacher]:
        found: dict[int, Teacher] = {}
        for group in self.groups:
            for teacher in (group.main_teacher, group.support_teacher):
                if teacher is not None:
                    found[teacher.id] = teacher
        return list(found.values())


class Administrator(User):
    __mapper_args__ = {"polymorphic_identity": "administrator"}
    role_label = "Administrator"

    def permissions(self) -> set[str]:
        return {CONFIRM_ATTENDANCE, RECORD_CIRCUMSTANCE, VIEW_RISK, MANAGE_ALERTS, VIEW_WORKLOAD}


class HeadSpecialist(User):
    __mapper_args__ = {"polymorphic_identity": "head_specialist"}
    role_label = "Head specialist"

    def permissions(self) -> set[str]:
        return {CONFIGURE_KPI, RATE_TEACHERS, VIEW_ALL_KPI, VIEW_WORKLOAD}


class Director(User):
    __mapper_args__ = {"polymorphic_identity": "director"}
    role_label = "Director"

    def permissions(self) -> set[str]:
        return {VIEW_RISK, MANAGE_ALERTS, VIEW_ALL_KPI, VIEW_WORKLOAD, VIEW_RETENTION}
