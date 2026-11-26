"""UC-01 Check In / Out via QR Code - FR-01."""
from datetime import timedelta

import pytest

from nsp.domain import CheckInMethod, CheckInStatus, WorkSessionStatus
from nsp.services import AttendanceError, QrCodeMethod


def code(world, room=None, minutes_ago=0):
    at = world.clock.now() - timedelta(minutes=minutes_ago)
    return {"token": QrCodeMethod.token_for(room or world.room, at)}


def test_teacher_check_in_on_time_opens_a_work_session(world):
    result = world.attendance.check_in(world.teacher, world.room, code(world))
    assert result.check_in.status is CheckInStatus.ON_TIME
    assert result.check_in.method is CheckInMethod.QR
    assert result.work_session.status is WorkSessionStatus.OPEN


def test_expired_code_is_rejected(world):  # ext. 3a: a photo of an old code
    with pytest.raises(AttendanceError) as error:
        world.attendance.check_in(world.teacher, world.room, code(world, minutes_ago=5))
    assert error.value.code == "expired_code"


def test_code_from_another_room_is_rejected(world):
    with pytest.raises(AttendanceError) as error:
        world.attendance.check_in(world.teacher, world.room, code(world, room=world.other_room))
    assert error.value.code == "invalid_code"


def test_no_lesson_in_this_room_says_where_the_lesson_is(world):  # ext. 4a
    with pytest.raises(AttendanceError) as error:
        world.attendance.check_in(world.teacher, world.other_room, code(world, room=world.other_room))
    assert error.value.code == "no_lesson"
    assert "Room 1 at 10:00" in error.value.message


def test_ten_minutes_is_on_time_and_eleven_is_late(world):  # ext. 5a
    world.clock.advance(10)
    assert world.attendance.check_in(world.students[0], world.room, code(world)).check_in.minutes_late == 0
    world.clock.advance(1)
    late = world.attendance.check_in(world.students[1], world.room, code(world)).check_in
    assert late.status is CheckInStatus.LATE and late.minutes_late == 11


def test_check_in_window_closes_thirty_minutes_after_the_start(world):
    world.clock.advance(31)
    with pytest.raises(AttendanceError):
        world.attendance.check_in(world.students[0], world.room, code(world))


def test_second_scan_creates_no_duplicate(world):  # ext. 5b
    first = world.attendance.check_in(world.teacher, world.room, code(world))
    second = world.attendance.check_in(world.teacher, world.room, code(world))
    assert second.duplicate and second.check_in.id == first.check_in.id


def test_check_out_after_the_end_counts_overtime(world):
    world.attendance.check_in(world.teacher, world.room, code(world))
    world.clock.advance(105)
    work = world.attendance.check_out(world.teacher, world.room, code(world))
    assert work.status is WorkSessionStatus.CLOSED
    assert work.overtime_minutes == 15 and work.worked_minutes == 105


def test_check_out_before_the_end_is_left_early(world):  # ext. 9a
    world.attendance.check_in(world.teacher, world.room, code(world))
    world.clock.advance(60)
    work = world.attendance.check_out(world.teacher, world.room, code(world))
    assert work.status is WorkSessionStatus.LEFT_EARLY and work.shortfall_minutes == 30


def test_forgotten_check_out_is_closed_at_the_planned_end_and_flagged(world):  # ext. 8a
    world.attendance.check_in(world.teacher, world.room, code(world))
    world.clock.advance(90 + 60)
    assert world.attendance.close_stale_sessions() == 0  # exactly 60 minutes: not yet
    world.clock.advance(1)
    assert world.attendance.close_stale_sessions() == 1
    work = world.attendance.flagged_sessions()[0]
    assert work.status is WorkSessionStatus.MISSING_CHECKOUT
    assert work.check_out_at == world.lesson.ends_at
    assert not work.counts_for_overtime  # FR-03.3
    assert world.notifications.unread_count(world.admin) == 1


def test_manual_confirmation_needs_an_administrator_and_a_reason(world):  # ext. 3b
    with pytest.raises(AttendanceError):
        world.attendance.confirm_manually(world.teacher, world.students[0], world.lesson, "no phone")
    with pytest.raises(AttendanceError):
        world.attendance.confirm_manually(world.admin, world.students[0], world.lesson, "  ")
    record = world.attendance.confirm_manually(
        world.admin, world.students[0], world.lesson, "no phone"
    ).check_in
    assert record.method is CheckInMethod.MANUAL
    assert record.confirmed_by_id == world.admin.id and record.reason == "no phone"


def test_administrator_corrects_a_flagged_session_with_a_reason(world):  # FR-03.4
    world.attendance.check_in(world.teacher, world.room, code(world))
    world.clock.advance(200)
    world.attendance.close_stale_sessions()
    work = world.attendance.flagged_sessions()[0]
    with pytest.raises(AttendanceError):
        world.attendance.correct_work_session(world.admin, work, world.lesson.ends_at, "")
    world.attendance.correct_work_session(
        world.admin, work, world.lesson.ends_at + timedelta(minutes=20), "Teacher confirmed by phone"
    )
    assert work.status is WorkSessionStatus.CLOSED and work.overtime_minutes == 20
