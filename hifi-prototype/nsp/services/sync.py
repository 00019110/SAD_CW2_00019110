"""Imports EduTizim-owned data through the gateway (NFR-05.1, NFR-05.2)."""
from __future__ import annotations

import secrets
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..data import SettingsRepository
from ..domain import (
    Administrator,
    Director,
    Group,
    HeadSpecialist,
    Lesson,
    MainTeacher,
    Room,
    ScheduledSession,
    Student,
    SupportSession,
    SupportTeacher,
    User,
    Withdrawal,
)
from ..integration.edutizim import EduTizimGateway
from .clock import Clock

LAST_SYNC_KEY = "edutizim_last_sync"
ROLE_CLASSES = {
    "main_teacher": MainTeacher,
    "support_teacher": SupportTeacher,
    "administrator": Administrator,
    "head_specialist": HeadSpecialist,
    "director": Director,
}


class SyncService:
    def __init__(self, db: Session, clock: Clock, gateway: EduTizimGateway) -> None:
        self.db = db
        self.clock = clock
        self.gateway = gateway
        self.settings = SettingsRepository(db)
        # EduTizim key -> local entity, filled by import_all()
        self.users: dict[str, User] = {}
        self.groups: dict[str, Group] = {}
        self.rooms: dict[str, Room] = {}
        self.sessions: list[tuple[str, ScheduledSession]] = []

    def import_all(self, since: date, until: date) -> None:
        """First full import: rooms, staff, students, groups and the timetable."""
        for name in self.gateway.fetch_rooms():
            self.rooms[name] = Room(name=name, qr_secret=secrets.token_hex(8))

        for record in self.gateway.fetch_staff():
            staff = ROLE_CLASSES[record.role](full_name=record.full_name, username=record.key)
            if record.subject is not None:
                staff.subject = record.subject
                staff.hired_on = record.hired_on
            self.users[record.key] = staff

        withdrawals = []
        for record in self.gateway.fetch_students():
            student = Student(
                full_name=record.full_name,
                username=record.key,
                enrolled_on=record.enrolled_on,
                parent_name=record.parent_name,
                parent_phone=record.parent_phone,
                monthly_fee=record.monthly_fee,
                tuition_debt=record.tuition_debt,
                consecutive_absences=0,
                is_active=record.withdrawn_on is None,
            )
            self.users[record.key] = student
            if record.withdrawn_on is not None:
                withdrawals.append((student, record))

        for record in self.gateway.fetch_groups():
            self.groups[record.key] = Group(
                name=record.name,
                subject=record.subject,
                level=record.level,
                main_teacher=self.users[record.main_teacher],
                support_teacher=self.users.get(record.support_teacher) if record.support_teacher else None,
                students=[self.users[key] for key in record.students],
            )

        self.db.add_all([*self.rooms.values(), *self.users.values(), *self.groups.values()])
        self.db.flush()

        for student, record in withdrawals:
            self.db.add(
                Withdrawal(student_id=student.id, withdrawn_on=record.withdrawn_on, reason=record.withdrawal_reason)
            )

        for record in self.gateway.fetch_timetable(since, until):
            session_class = Lesson if record.kind == "lesson" else SupportSession
            session = session_class(
                group=self.groups[record.group],
                room=self.rooms[record.room],
                teacher=self.users[record.teacher],
                starts_at=record.starts_at,
                ends_at=record.ends_at,
            )
            self.db.add(session)
            self.sessions.append((record.tag, session))
        self.db.flush()
        self.mark_synced()

    def mark_synced(self) -> None:
        self.settings.set(LAST_SYNC_KEY, self.clock.now().isoformat())

    def last_sync(self) -> datetime | None:
        value = self.settings.get(LAST_SYNC_KEY)
        return datetime.fromisoformat(value) if value else None

    def push_register(self, register) -> None:
        """Send a locked register back to EduTizim (NFR-05.2)."""
        statuses = {entry.student.username: entry.status.value for entry in register.entries}
        self.gateway.push_register(register.session_id, statuses)
        self.mark_synced()
