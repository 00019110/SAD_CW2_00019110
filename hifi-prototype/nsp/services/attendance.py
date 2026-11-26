"""UC-01 Check In / Out via QR Code, and manual confirmation (FR-01).

The way a person proves they are in the room is the part most likely to change
(QR today, Face ID later - interview Q7, NFR-05.5), so it is hidden behind the
AttendanceMethod interface. AttendanceService depends only on that interface.
"""
from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..data import AttendanceRepository, TimetableRepository
from ..domain import (
    Administrator,
    AttendanceStatus,
    CheckIn,
    CheckInMethod,
    CheckInStatus,
    Room,
    ScheduledSession,
    Teacher,
    User,
    WorkSession,
    WorkSessionStatus,
)
from ..domain.people import CONFIRM_ATTENDANCE
from .clock import Clock
from .notifications import NotificationService

AUTO_CLOSE_AFTER = timedelta(minutes=60)


class AttendanceError(Exception):
    """A rejected scan. `code` identifies the UC-01 extension that applied."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AttendanceMethod(ABC):
    """Interface: one way of proving presence in a room."""

    code: CheckInMethod

    @abstractmethod
    def verify(self, room: Room, evidence: dict, now: datetime) -> None:
        """Raise AttendanceError unless the evidence proves presence in the room."""


class QrCodeMethod(AttendanceMethod):
    """Rotating room code: a signed room id and time window, no personal data."""

    code = CheckInMethod.QR
    VALID_SECONDS = 60

    @classmethod
    def _window(cls, at: datetime) -> int:
        return int(at.timestamp()) // cls.VALID_SECONDS

    @classmethod
    def _sign(cls, room: Room, window: int) -> str:
        message = f"{room.id}.{window}".encode()
        return hmac.new(room.qr_secret.encode(), message, hashlib.sha256).hexdigest()[:16]

    @classmethod
    def token_for(cls, room: Room, at: datetime) -> str:
        window = cls._window(at)
        return f"{room.id}.{window}.{cls._sign(room, window)}"

    @classmethod
    def seconds_left(cls, at: datetime) -> int:
        return cls.VALID_SECONDS - int(at.timestamp()) % cls.VALID_SECONDS

    def verify(self, room: Room, evidence: dict, now: datetime) -> None:
        token = str(evidence.get("token", ""))
        parts = token.split(".")
        if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
            raise AttendanceError("invalid_code", "This is not a valid room code. Scan the code on the room screen.")
        room_id, window, signature = int(parts[0]), int(parts[1]), parts[2]
        if room_id != room.id or not hmac.compare_digest(signature, self._sign(room, window)):
            raise AttendanceError("invalid_code", "This code does not belong to this room. Scan the code on the room screen.")
        # The code on screen changes every 60 seconds; the previous one is still
        # accepted so a scan made just before the change is not rejected.
        if self._window(now) - window not in (0, 1):
            raise AttendanceError("expired_code", "This code has expired. Scan the code on the room screen again.")


class ManualConfirmation(AttendanceMethod):
    """Administrator confirmation when a scan cannot be completed (UC-01 ext. 3b)."""

    code = CheckInMethod.MANUAL

    def verify(self, room: Room, evidence: dict, now: datetime) -> None:
        administrator = evidence.get("administrator")
        if administrator is None or not administrator.can(CONFIRM_ATTENDANCE):
            raise AttendanceError("not_allowed", "Only an administrator can confirm attendance manually.")
        if not str(evidence.get("reason", "")).strip():
            raise AttendanceError("reason_required", "A reason is required for manual confirmation.")


@dataclass
class CheckInResult:
    check_in: CheckIn
    session: ScheduledSession
    duplicate: bool = False
    work_session: WorkSession | None = None


class AttendanceService:
    def __init__(
        self,
        db: Session,
        clock: Clock,
        notifications: NotificationService,
        methods: list[AttendanceMethod] | None = None,
    ) -> None:
        self.db = db
        self.clock = clock
        self.notifications = notifications
        self.timetable = TimetableRepository(db)
        self.attendance = AttendanceRepository(db)
        self.methods = {m.code: m for m in (methods or [QrCodeMethod(), ManualConfirmation()])}

    # -- check-in ---------------------------------------------------------
    def check_in(
        self, user: User, room: Room, evidence: dict, method: CheckInMethod = CheckInMethod.QR
    ) -> CheckInResult:
        now = self.clock.now()
        self.methods[method].verify(room, evidence, now)
        session = self._session_for_scan(user, room, now)

        existing = self.attendance.check_in_for(user.id, session.id)
        if existing is not None:  # ext. 5b: no duplicate record
            return CheckInResult(existing, session, duplicate=True)
        return self._record(user, session, now, method)

    def confirm_manually(
        self,
        administrator: User,
        user: User,
        session: ScheduledSession,
        reason: str,
        at: datetime | None = None,
    ) -> CheckInResult:
        """Administrator enters the user, lesson and time (ext. 3b, FR-01.7)."""
        evidence = {"administrator": administrator, "reason": reason}
        self.methods[CheckInMethod.MANUAL].verify(session.room, evidence, self.clock.now())
        if not session.involves(user.id):
            raise AttendanceError("no_lesson", f"{user.full_name} is not part of this session.")
        existing = self.attendance.check_in_for(user.id, session.id)
        if existing is not None:
            return CheckInResult(existing, session, duplicate=True)
        result = self._record(user, session, at or session.starts_at, CheckInMethod.MANUAL)
        result.check_in.confirmed_by_id = administrator.id
        result.check_in.reason = reason.strip()
        return result

    def _record(
        self, user: User, session: ScheduledSession, at: datetime, method: CheckInMethod
    ) -> CheckInResult:
        late = session.minutes_late(at)
        check_in = CheckIn(
            user_id=user.id,
            session_id=session.id,
            timestamp=at,
            method=method,
            status=CheckInStatus.LATE if late else CheckInStatus.ON_TIME,
            minutes_late=late,
        )
        self.db.add(check_in)
        work_session = None
        if isinstance(user, Teacher):
            work_session = WorkSession(
                teacher_id=user.id, session_id=session.id, check_in_at=at, minutes_late=late
            )
            work_session.session = session
            self.db.add(work_session)
        else:
            self._prefill_register(user, session, check_in)
        self.db.flush()
        return CheckInResult(check_in, session, work_session=work_session)

    def _prefill_register(self, student: User, session: ScheduledSession, check_in: CheckIn) -> None:
        """A student scan marks them Present or Late in an already-open register."""
        register = self.attendance.register_for(session.id)
        if register is None or register.locked:
            return
        for entry in register.entries:
            if entry.student_id == student.id and entry.status is AttendanceStatus.NOT_SCANNED:
                entry.scanned = True
                entry.status = (
                    AttendanceStatus.LATE
                    if check_in.status is CheckInStatus.LATE
                    else AttendanceStatus.PRESENT
                )

    def _session_for_scan(self, user: User, room: Room, now: datetime) -> ScheduledSession:
        sessions = self.timetable.for_user_on(user, now.date())
        in_room = [s for s in sessions if s.room_id == room.id and s.is_within_check_in_window(now)]
        if in_room:
            return min(in_room, key=lambda s: abs((s.starts_at - now).total_seconds()))
        # ext. 4a: tell the user where and when their lesson actually is.
        upcoming = [s for s in sessions if s.starts_at + timedelta(minutes=30) >= now]
        if upcoming:
            nxt = upcoming[0]
            hint = f"your next lesson is in {nxt.room.name} at {nxt.starts_at:%H:%M}."
        else:
            hint = "you have no more lessons today."
        raise AttendanceError("no_lesson", f"You have no lesson in {room.name} now – {hint}")

    # -- check-out --------------------------------------------------------
    def check_out(self, teacher: Teacher, room: Room, evidence: dict) -> WorkSession:
        now = self.clock.now()
        self.methods[CheckInMethod.QR].verify(room, evidence, now)
        open_here = [
            ws for ws in self.attendance.open_work_sessions(teacher.id) if ws.session.room_id == room.id
        ]
        if not open_here:
            raise AttendanceError("not_checked_in", f"You have no open session in {room.name} to check out of.")
        work_session = open_here[0]
        work_session.close(now)  # sets Closed with overtime, or Left early (ext. 9a)
        self.db.flush()
        return work_session

    def open_work_session(self, teacher: Teacher) -> WorkSession | None:
        sessions = self.attendance.open_work_sessions(teacher.id)
        return sessions[0] if sessions else None

    # -- exceptions -------------------------------------------------------
    def close_stale_sessions(self) -> int:
        """ext. 8a: 60 minutes after the planned end, close and flag the session."""
        now = self.clock.now()
        flagged = 0
        for work_session in self.attendance.open_work_sessions():
            if now > work_session.session.ends_at + AUTO_CLOSE_AFTER:
                work_session.flag_missing_check_out()
                self.notifications.notify_roles(
                    [Administrator],
                    f"Missing check-out: {work_session.teacher.full_name}, "
                    f"{work_session.session.group.name} at {work_session.session.starts_at:%H:%M}.",
                    "/attendance/exceptions",
                )
                flagged += 1
        if flagged:
            self.db.flush()
        return flagged

    def correct_work_session(
        self, administrator: User, work_session: WorkSession, check_out_at: datetime, reason: str
    ) -> WorkSession:
        """Administrator confirms or corrects a flagged session; reason required (FR-03.4)."""
        if not administrator.can(CONFIRM_ATTENDANCE):
            raise AttendanceError("not_allowed", "Only an administrator can correct a work session.")
        if not reason.strip():
            raise AttendanceError("reason_required", "A reason is required to correct a work session.")
        if check_out_at <= work_session.check_in_at:
            raise AttendanceError("invalid_time", "Check-out must be after check-in.")
        work_session.close(check_out_at)
        work_session.correction_reason = reason.strip()
        self.db.flush()
        return work_session

    def flagged_sessions(self) -> list[WorkSession]:
        return self.attendance.flagged_work_sessions()

    def status_of(self, work_session: WorkSession | None) -> str:
        return work_session.status.value if work_session else "Not checked in"

    @staticmethod
    def is_open(work_session: WorkSession | None) -> bool:
        return work_session is not None and work_session.status is WorkSessionStatus.OPEN
