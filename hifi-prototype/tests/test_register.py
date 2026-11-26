"""UC-02 Record Student Attendance - FR-02, and the alert it triggers (FR-05.2)."""
import pytest

from nsp.domain import AlertStatus, AttendanceStatus, RiskLevel
from nsp.services import QrCodeMethod, RegisterError


def scan(world, student):
    token = QrCodeMethod.token_for(world.room, world.clock.now())
    world.attendance.check_in(student, world.room, {"token": token})


def fill(world, register, default=AttendanceStatus.PRESENT, **by_username):
    for entry in register.entries:
        if entry.status is AttendanceStatus.NOT_SCANNED:
            status = by_username.get(entry.student.username, default)
            reason = "illness" if status is AttendanceStatus.EXCUSED else ""
            world.register.set_status(entry, status, reason)


def test_register_is_prefilled_from_qr_scans(world):
    scan(world, world.students[0])
    register = world.register.open_register(world.lesson, world.teacher)
    statuses = {e.student.username: e.status for e in register.entries}
    assert statuses["s1"] is AttendanceStatus.PRESENT
    assert statuses["s2"] is AttendanceStatus.NOT_SCANNED
    assert len(register.entries) == 6


def test_student_scanning_after_the_register_is_open_is_filled_in(world):
    register = world.register.open_register(world.lesson, world.teacher)
    scan(world, world.students[3])
    entry = next(e for e in register.entries if e.student is world.students[3])
    assert entry.status is AttendanceStatus.PRESENT and entry.scanned


def test_submit_is_blocked_while_a_student_has_no_status(world):  # ext. 5a
    register = world.register.open_register(world.lesson, world.teacher)
    with pytest.raises(RegisterError) as error:
        world.register.submit(register, world.teacher)
    assert len(error.value.entries) == 6 and not register.locked


def test_present_without_a_scan_is_a_teacher_override(world):  # ext. 3a
    register = world.register.open_register(world.lesson, world.teacher)
    entry = world.register.set_status(register.entries[0], AttendanceStatus.PRESENT)
    assert entry.teacher_override


def test_excused_absence_needs_a_reason(world):  # ext. 3b
    register = world.register.open_register(world.lesson, world.teacher)
    with pytest.raises(RegisterError):
        world.register.set_status(register.entries[0], AttendanceStatus.EXCUSED)


def test_submit_locks_and_updates_absence_runs(world):  # FR-02.6
    absent, excused, present = world.students[0], world.students[1], world.students[2]
    absent.consecutive_absences = excused.consecutive_absences = present.consecutive_absences = 1
    register = world.register.open_register(world.lesson, world.teacher)
    fill(world, register, s1=AttendanceStatus.ABSENT, s2=AttendanceStatus.EXCUSED)
    world.register.submit(register, world.teacher)
    assert register.locked and register.submitted_by_id == world.teacher.id
    assert absent.consecutive_absences == 2  # absent adds one
    assert excused.consecutive_absences == 1  # excused leaves the run as it is
    assert present.consecutive_absences == 0  # present resets it
    with pytest.raises(RegisterError):
        world.register.set_status(register.entries[0], AttendanceStatus.PRESENT)


def test_third_consecutive_absence_raises_one_alert_and_notifies(world):  # ext. 7a
    student = world.students[0]
    student.consecutive_absences = 2
    register = world.register.open_register(world.lesson, world.teacher)
    fill(world, register, s1=AttendanceStatus.ABSENT)
    result = world.register.submit(register, world.teacher)
    assert [a.student_id for a in result.alerts] == [student.id]
    assert result.alerts[0].status is AlertStatus.OPEN
    assert world.risk.retention.risk_score(student.id).level is RiskLevel.HIGH
    assert world.notifications.unread_count(world.admin) == 1
    assert world.notifications.unread_count(world.head) == 1
    assert world.notifications.unread_count(world.teacher) == 0


def test_second_reason_joins_the_open_alert(world):  # ext. 7b
    student = world.students[0]
    first = world.risk.raise_alert(student, "3 consecutive absences")
    second = world.risk.raise_alert(student, "Financial circumstances reported")
    assert first.id == second.id and len(second.reason_list) == 2
    assert len(world.risk.retention.alerts(open_only=True)) == 1


def test_late_submission_is_flagged(world):  # ext. 6a
    register = world.register.open_register(world.lesson, world.teacher)
    fill(world, register)
    world.clock.advance(24 * 60)
    world.register.submit(register, world.teacher)
    assert register.late_submission
