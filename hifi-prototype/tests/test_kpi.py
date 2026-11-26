"""UC-04 teacher KPI - FR-04, and the workload report - FR-03."""
from datetime import date

import pytest

from nsp.domain import Achievement, Feedback, MonthlyRating, TestResult, WorkSession
from nsp.services import KpiError, QrCodeMethod

MONTH = "2026-11"
TEN_DAYS = 60 * 24 * 10


def add_inputs(world, teacher, rating=8.0, feedback=(5, 4, 4, 5, 4)):
    db = world.db
    for student, stars in zip(world.students, feedback):
        db.add(Feedback(student_id=student.id, teacher_id=teacher.id, month=MONTH, rating=stars))
        db.add(TestResult(student_id=student.id, group_id=world.group.id, month=MONTH, kind="mock", score=70))
    if rating is not None:
        db.add(MonthlyRating(teacher_id=teacher.id, month=MONTH, rating=rating))
    db.add(
        Achievement(teacher_id=teacher.id, title="IELTS 8.0", points=60, achieved_on=date(2026, 1, 1), verified=True)
    )
    db.add(
        Achievement(teacher_id=teacher.id, title="Unverified", points=40, achieved_on=date(2026, 1, 1), verified=False)
    )
    db.add(
        WorkSession(
            teacher_id=teacher.id, session_id=world.lesson.id, check_in_at=world.lesson.starts_at, minutes_late=0
        )
    )
    db.flush()


def test_weighted_sum_of_the_indicators(world):
    add_inputs(world, world.teacher)
    result = world.kpi.calculate(world.teacher, MONTH)
    scores = {i.code: i.score for i in result.indicators}
    assert scores["results"] == 70
    assert scores["feedback"] == pytest.approx((4.4 - 1) / 4 * 100)
    assert scores["rating"] == 80
    assert scores["achievements"] == 60  # the unverified one does not count
    assert scores["punctuality"] == 100
    assert scores["retention"] == 100
    assert scores["attendance"] is None  # no submitted register yet, so it is left out
    weights = {"results": 25, "punctuality": 10, "retention": 20, "feedback": 20, "rating": 10, "achievements": 5}
    expected = sum(scores[c] * w for c, w in weights.items()) / sum(weights.values())
    assert result.overall == pytest.approx(expected, abs=0.05)
    assert result.partial
    assert sum(i.applied for i in result.indicators) == pytest.approx(100)


def test_support_teacher_has_no_results_indicator(world):  # ext. 2b
    add_inputs(world, world.support)
    result = world.kpi.calculate(world.support, MONTH)
    assert result.indicator("results").score is None
    assert result.indicator("results").applied == 0
    assert result.partial


def test_fewer_than_five_feedback_responses_is_left_out(world):  # ext. 2b
    add_inputs(world, world.teacher, feedback=(5, 5, 5, 5))
    assert world.kpi.calculate(world.teacher, MONTH).indicator("feedback").score is None


def test_missing_head_rating_makes_the_score_provisional(world):  # ext. 2c
    add_inputs(world, world.teacher, rating=None)
    world.clock.advance(TEN_DAYS)  # into December: November has ended
    result = world.kpi.calculate(world.teacher, MONTH)
    assert result.provisional and result.status == "Provisional"
    assert world.kpi.close_month(MONTH) == 0  # no snapshot without the rating


def test_running_month_is_provisional_and_cannot_be_closed(world):  # ext. 1a
    add_inputs(world, world.teacher)
    assert world.kpi.calculate(world.teacher, MONTH).provisional
    with pytest.raises(KpiError):
        world.kpi.close_month(MONTH)


def test_closed_month_is_stored_as_a_locked_snapshot(world):  # FR-04.6
    add_inputs(world, world.teacher)
    live = world.kpi.calculate(world.teacher, MONTH).overall
    world.clock.advance(TEN_DAYS)
    assert world.kpi.close_month(MONTH) == 1
    world.db.add(
        Achievement(
            teacher_id=world.teacher.id, title="Later", points=40, achieved_on=date(2026, 12, 1), verified=True
        )
    )
    world.db.flush()
    stored = world.kpi.calculate(world.teacher, MONTH)
    assert stored.overall == live  # later data does not change a closed month
    assert stored.status == "Partial"


def test_weights_must_total_100_and_apply_from_next_month(world):  # FR-04.1, ext. 2a
    codes = [i.code for i in world.kpi.indicators]
    valid = {c: (40 if c == "results" else 10) for c in codes}
    with pytest.raises(KpiError):
        world.kpi.save_weights(world.head, {c: 10 for c in codes})
    with pytest.raises(KpiError):
        world.kpi.save_weights(world.teacher, valid)
    saved = world.kpi.save_weights(world.head, valid)
    assert saved.effective_from == "2026-12"
    assert world.kpi.weights_for(MONTH).weight_for("results") == 25  # this month unchanged
    assert world.kpi.weights_for("2026-12").weight_for("results") == 40


def test_rating_must_be_between_0_and_10(world):  # FR-04.2
    with pytest.raises(KpiError):
        world.kpi.rate(world.head, world.teacher, MONTH, 11)
    with pytest.raises(KpiError):
        world.kpi.rate(world.director, world.teacher, MONTH, 8)
    assert world.kpi.rate(world.head, world.teacher, MONTH, 7.5).rating == 7.5


def test_workload_counts_planned_worked_and_overtime(world):  # FR-03
    def token():
        return {"token": QrCodeMethod.token_for(world.room, world.clock.now())}

    world.clock.advance(12)
    world.attendance.check_in(world.teacher, world.room, token())
    world.clock.advance(88)
    world.attendance.check_out(world.teacher, world.room, token())
    row = world.workload.row_for(world.teacher, MONTH)
    assert (row.lessons, row.planned_minutes, row.worked_minutes) == (1, 90, 88)
    assert (row.late_arrivals, row.minutes_late, row.overtime_minutes) == (1, 12, 10)
