"""UC-02 Record Student Attendance (FR-02)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..data import AttendanceRepository
from ..domain import (
    AttendanceStatus,
    CheckInStatus,
    Lesson,
    LessonRegister,
    RegisterEntry,
    RiskAlert,
    Teacher,
)
from .clock import Clock
from .risk import RiskService
from .sync import SyncService

TEACHER_CHOICES = [
    AttendanceStatus.PRESENT,
    AttendanceStatus.LATE,
    AttendanceStatus.ABSENT,
    AttendanceStatus.EXCUSED,
]


class RegisterError(Exception):
    def __init__(self, message: str, entries: list[RegisterEntry] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.entries = entries or []


@dataclass
class SubmissionResult:
    register: LessonRegister
    alerts: list[RiskAlert] = field(default_factory=list)


class RegisterService:
    def __init__(
        self, db: Session, clock: Clock, risk: RiskService, sync: SyncService | None = None
    ) -> None:
        self.db = db
        self.clock = clock
        self.risk = risk
        self.sync = sync
        self.attendance = AttendanceRepository(db)

    def open_register(self, lesson: Lesson, teacher: Teacher) -> LessonRegister:
        """List every active student, pre-filled from QR check-ins (FR-02.1)."""
        if lesson.teacher_id != teacher.id:
            raise RegisterError("You are not assigned to this lesson.")
        register = self.attendance.register_for(lesson.id)
        if register is None:
            register = LessonRegister(session_id=lesson.id)
            register.session = lesson
            self.db.add(register)
        if register.locked:
            return register

        check_ins = {c.user_id: c for c in self.attendance.check_ins_for_session(lesson.id)}
        entries = {e.student_id: e for e in register.entries}
        for student in lesson.group.active_students:
            entry = entries.get(student.id)
            if entry is None:
                entry = RegisterEntry(student_id=student.id, status=AttendanceStatus.NOT_SCANNED)
                entry.student = student
                register.entries.append(entry)
            check_in = check_ins.get(student.id)
            if check_in is not None and entry.status is AttendanceStatus.NOT_SCANNED:
                entry.scanned = True
                entry.status = (
                    AttendanceStatus.LATE
                    if check_in.status is CheckInStatus.LATE
                    else AttendanceStatus.PRESENT
                )
        self.db.flush()
        return register

    def set_status(
        self, entry: RegisterEntry, status: AttendanceStatus, reason: str = ""
    ) -> RegisterEntry:
        if entry.register.locked:
            raise RegisterError("This register is locked. Send a correction request to the Head Specialist.")
        if status not in TEACHER_CHOICES:
            raise RegisterError("Choose Present, Late, Absent or Absent – excused.")
        if status is AttendanceStatus.EXCUSED and not reason.strip():
            raise RegisterError(
                f"Enter the reason {entry.student.full_name}'s absence is excused.", [entry]
            )
        entry.status = status
        entry.reason = reason.strip() or None if status is AttendanceStatus.EXCUSED else None
        # Present without a scan is kept as a teacher override (FR-02.4).
        entry.teacher_override = entry.attended and not entry.scanned
        return entry

    def submit(self, register: LessonRegister, teacher: Teacher) -> SubmissionResult:
        """Validate, lock, update absence runs and trigger alerts (FR-02.3 to FR-02.6)."""
        if register.locked:
            raise RegisterError("This register has already been submitted.")
        if register.session.teacher_id != teacher.id:
            raise RegisterError("You are not assigned to this lesson.")
        missing = register.missing_entries()
        if missing:
            raise RegisterError(
                f"{len(missing)} student(s) still have no status. Set a status for each highlighted student.",
                missing,
            )

        now = self.clock.now()
        register.lock(teacher.id, now)
        result = SubmissionResult(register)
        lesson_date = register.session.starts_at.date()
        for entry in register.entries:
            student = entry.student
            if entry.status is AttendanceStatus.ABSENT:
                student.register_absence()
                alert = self.risk.on_register_submitted(student, lesson_date)
                if alert is not None:
                    result.alerts.append(alert)
            else:
                if entry.attended:
                    student.reset_absences()
                # An excused absence leaves the run unchanged.
                self.risk.on_register_submitted(student, None)
        self.db.flush()
        if self.sync is not None:  # keep EduTizim's own attendance dashboard correct
            self.sync.push_register(register)
        return result
