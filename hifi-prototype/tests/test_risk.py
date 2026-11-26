"""UC-03 dropout risk score, alerts and follow-up - FR-05."""
from datetime import date, timedelta

import pytest

from nsp.domain import AlertStatus, CircumstanceKind, RiskLevel, WithdrawalReason
from nsp.services import RiskError


def test_score_combines_the_four_factors(world):
    student = world.students[0]
    assert world.risk.calculate(student).level is RiskLevel.LOW
    student.consecutive_absences = 2
    student.tuition_debt = 400_000
    score = world.risk.calculate(student)
    assert score.score == 45 and score.level is RiskLevel.MEDIUM
    world.risk.record_circumstance(world.admin, student, CircumstanceKind.FINANCIAL, "Parent lost job")
    score = world.risk.retention.risk_score(student.id)
    assert score.score == 70 and score.level is RiskLevel.HIGH
    assert len(score.factor_list) == 3


def test_new_student_has_not_enough_data(world):  # ext. 3a
    student = world.students[0]
    student.enrolled_on = world.clock.today() - timedelta(days=5)
    student.consecutive_absences = 3
    assert world.risk.calculate(student).level is RiskLevel.NOT_ENOUGH_DATA


def test_negative_feedback_for_most_teachers_raises_an_alert(world):
    student = world.students[0]
    world.risk.submit_feedback(student, world.teacher, 1, "Too fast")
    assert world.risk.retention.open_alert_for(student.id) is None  # one of two teachers so far
    world.risk.submit_feedback(student, world.support, 2)
    assert world.risk.retention.open_alert_for(student.id) is not None


def test_feedback_is_once_a_month_and_only_for_own_teachers(world):
    student = world.students[0]
    world.risk.submit_feedback(student, world.teacher, 5)
    with pytest.raises(RiskError):
        world.risk.submit_feedback(student, world.teacher, 4)
    with pytest.raises(RiskError):
        world.risk.submit_feedback(student, world.support, 9)


def test_follow_up_moves_the_alert_to_in_progress_and_notifies(world):
    alert = world.risk.raise_alert(world.students[0], "3 consecutive absences")
    before = world.notifications.unread_count(world.admin)
    action = world.risk.assign_follow_up(alert, "Call the parent", world.admin, date(2026, 11, 27))
    assert alert.status is AlertStatus.IN_PROGRESS
    assert world.notifications.unread_count(world.admin) == before + 1
    assert not action.is_overdue(date(2026, 11, 27)) and action.is_overdue(date(2026, 11, 28))
    world.risk.resolve(alert)
    assert alert.status is AlertStatus.RESOLVED and action.done


def test_closing_as_withdrawn_records_the_withdrawal(world):  # ext. 9a
    student = world.students[0]
    alert = world.risk.raise_alert(student, "3 consecutive absences")
    withdrawal = world.risk.close_as_withdrawn(alert, WithdrawalReason.FINANCIAL)
    assert alert.status is AlertStatus.CLOSED_WITHDRAWN
    assert not student.is_active and withdrawal.reason is WithdrawalReason.FINANCIAL
    assert student not in world.group.active_students


def test_dashboard_counts_and_filters(world):
    world.students[0].consecutive_absences = 3
    world.students[1].consecutive_absences = 2
    data = world.risk.dashboard()
    assert data.counts[RiskLevel.HIGH] == 1 and data.counts[RiskLevel.MEDIUM] == 1
    assert data.rows[0].student is world.students[0]
    assert len(world.risk.dashboard(level=RiskLevel.HIGH).rows) == 1
    assert world.risk.dashboard(group_id=999).rows == []
