"""UC-03 screens: Dropout Risk Dashboard, student detail, follow-up, feedback."""
from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, Response, g, redirect, render_template, request, url_for

from ..domain import (
    Administrator,
    CircumstanceKind,
    HeadSpecialist,
    RiskLevel,
    Student,
    SupportTeacher,
    Teacher,
    WithdrawalReason,
)
from ..domain.people import GIVE_FEEDBACK, MANAGE_ALERTS, RECORD_CIRCUMSTANCE, VIEW_RISK
from ..services import RiskError
from ..services.clock import month_key
from .context import commit, fail, get_or_404, requires, selected_subject

blueprint = Blueprint("risk", __name__)


def _filters():
    level = next((l for l in RiskLevel if l.name == request.args.get("level", "")), None)
    return {
        "subject": selected_subject(),
        "group_id": request.args.get("group", type=int),
        "teacher_id": request.args.get("teacher", type=int),
        "level": level,
    }


@blueprint.get("/risk")
@requires(VIEW_RISK)
def dashboard():
    services = g.services
    data = services.risk.dashboard(**_filters())
    commit()
    month = month_key(services.clock.today())
    return render_template(
        "risk_dashboard.html",
        data=data,
        month=month,
        overall=services.retention.overall(month),
        trend=services.retention.trend(),
        by_subject=services.retention.by_subject(month),
        groups=services.users.groups(),
        teachers=services.users.teachers(),
        today=services.clock.today(),
        RiskLevel=RiskLevel,
    )


@blueprint.get("/risk/export.csv")
@requires(VIEW_RISK)
def export():
    """Export the current view; the file opens in Excel (UC-03 ext. 4a)."""
    data = g.services.risk.dashboard(**_filters())
    commit()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Student", "Group", "Main teacher", "Risk level", "Score", "Risk factors", "Alert"])
    for row in data.rows:
        group = row.student.groups[0] if row.student.groups else None
        writer.writerow(
            [
                row.student.full_name,
                group.name if group else "",
                group.main_teacher.full_name if group else "",
                row.level.value,
                row.score.score if row.score else "",
                "; ".join(row.score.factor_list) if row.score else "",
                row.alert.status.value if row.alert else "",
            ]
        )
    return Response(
        "﻿" + out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dropout-risk.csv"},
    )


@blueprint.get("/risk/student/<int:student_id>")
@requires(VIEW_RISK)
def student(student_id: int):
    services = g.services
    person = get_or_404(services.users.get(student_id))
    if not isinstance(person, Student):
        get_or_404(None)
    score = services.risk.calculate(person) if person.is_active else services.risk.retention.risk_score(person.id)
    commit()
    month = month_key(services.clock.today())
    assignees = (
        services.users.by_role(Administrator)
        + services.users.by_role(HeadSpecialist)
        + [t for t in person.teachers if isinstance(t, SupportTeacher)]
        + [t for t in person.teachers if not isinstance(t, SupportTeacher)]
    )
    return render_template(
        "risk_student.html",
        student=person,
        score=score,
        history=list(reversed(services.attendance.attendance.history_for_student(person.id, 12))),
        feedback=services.kpi.performance.feedback_by_student(person.id, month),
        circumstances=services.risk.retention.circumstances(person.id),
        alerts=services.risk.retention.alerts_for_student(person.id),
        withdrawal=services.risk.retention.withdrawal_for(person.id),
        assignees=assignees,
        today=services.clock.today(),
        reasons=list(WithdrawalReason),
        kinds=list(CircumstanceKind),
        RiskLevel=RiskLevel,
    )


@blueprint.post("/risk/alert/<int:alert_id>/follow-up")
@requires(MANAGE_ALERTS)
def follow_up(alert_id: int):
    services = g.services
    alert = get_or_404(services.risk.retention.alert(alert_id))
    assignee = get_or_404(services.users.get(request.form.get("assignee_id", type=int)))
    try:
        due = date.fromisoformat(request.form.get("due_date", ""))
        services.risk.assign_follow_up(alert, request.form.get("description", ""), assignee, due)
        commit(f"Follow-up assigned to {assignee.full_name}. The alert is now In progress.")
    except ValueError:
        fail("Choose a due date for the follow-up.")
    except RiskError as error:
        fail(str(error))
    return redirect(url_for("risk.student", student_id=alert.student_id))


@blueprint.post("/risk/alert/<int:alert_id>/close")
@requires(MANAGE_ALERTS)
def close(alert_id: int):
    services = g.services
    alert = get_or_404(services.risk.retention.alert(alert_id))
    if request.form.get("outcome") == "withdrawn":
        reason = next(
            (r for r in WithdrawalReason if r.name == request.form.get("reason")), WithdrawalReason.OTHER
        )
        services.risk.close_as_withdrawn(alert, reason)
        commit(f"{alert.student.full_name} recorded as withdrawn ({reason.value}). Alert closed.", "info")
    else:
        services.risk.resolve(alert)
        commit(f"Alert resolved: {alert.student.full_name} has returned to lessons.")
    return redirect(url_for("risk.student", student_id=alert.student_id))


@blueprint.post("/risk/student/<int:student_id>/circumstance")
@requires(RECORD_CIRCUMSTANCE)
def circumstance(student_id: int):
    services = g.services
    person = get_or_404(services.users.get(student_id))
    kind = next((k for k in CircumstanceKind if k.name == request.form.get("kind")), CircumstanceKind.FINANCIAL)
    try:
        services.risk.record_circumstance(g.user, person, kind, request.form.get("note", ""))
        commit("Circumstances recorded. A dropout risk alert is open for this student.", "warning")
    except RiskError as error:
        fail(str(error))
    return redirect(url_for("risk.student", student_id=person.id))


# -- student feedback (feeds both the KPI and the risk score) -----------------
@blueprint.get("/feedback")
@requires(GIVE_FEEDBACK)
def feedback():
    services = g.services
    month = month_key(services.clock.today())
    given = {f.teacher_id: f for f in services.kpi.performance.feedback_by_student(g.user.id, month)}
    return render_template("feedback.html", teachers=g.user.teachers, given=given, month=month)


@blueprint.post("/feedback")
@requires(GIVE_FEEDBACK)
def give_feedback():
    services = g.services
    teacher = get_or_404(services.users.get(request.form.get("teacher_id", type=int)))
    if not isinstance(teacher, Teacher):
        get_or_404(None)
    try:
        services.risk.submit_feedback(
            g.user, teacher, request.form.get("rating", type=int, default=0), request.form.get("comment", "")
        )
        commit(f"Thank you. Your feedback for {teacher.full_name} was saved; teachers only see averages.")
    except RiskError as error:
        fail(str(error))
    return redirect(url_for("risk.feedback"))
