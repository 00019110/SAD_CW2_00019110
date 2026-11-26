"""UC-04 screens: Teacher KPI Dashboard, teacher detail and KPI settings."""
from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, g, redirect, render_template, request, url_for

from ..domain import Subject, Teacher
from ..domain.people import CONFIGURE_KPI, RATE_TEACHERS, VIEW_ALL_KPI, VIEW_OWN_KPI
from ..services import KpiError
from ..services.clock import shift_month
from ..services.kpi import INDICATORS
from .context import commit, fail, get_or_404, requires, selected_month, selected_role, selected_subject

blueprint = Blueprint("kpi", __name__)


@blueprint.get("/kpi")
@requires(VIEW_ALL_KPI)
def dashboard():
    services = g.services
    month, months = selected_month()
    try:
        ranking = services.kpi.ranking(month, selected_subject(), selected_role())
        problem = None
    except KpiError as error:
        ranking, problem = [], str(error)
    return render_template(
        "kpi_dashboard.html",
        ranking=ranking,
        problem=problem,
        month=month,
        months=months,
        weights=services.kpi.weights_for(month),
        indicators=INDICATORS,
        subjects=list(Subject),
        subject=selected_subject(),
        role=selected_role(),
    )


@blueprint.get("/kpi/export.csv")
@requires(VIEW_ALL_KPI)
def export():
    month, _ = selected_month()
    ranking = g.services.kpi.ranking(month, selected_subject(), selected_role())
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Teacher", "Subject", "Role", *[i.short for i in INDICATORS], "Overall KPI", "Change", "Status"])
    for row in ranking:
        writer.writerow(
            [
                row.teacher.full_name,
                row.teacher.subject.value,
                row.teacher.role_label,
                *["" if i.score is None else round(i.score, 1) for i in row.indicators],
                row.overall,
                row.change if row.change is not None else "",
                row.status,
            ]
        )
    return Response(
        "﻿" + out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=teacher-kpi-{month}.csv"},
    )


@blueprint.get("/kpi/me")
@requires(VIEW_OWN_KPI)
def mine():
    return redirect(url_for("kpi.teacher", teacher_id=g.user.id))


@blueprint.get("/kpi/teacher/<int:teacher_id>")
@requires(VIEW_ALL_KPI, VIEW_OWN_KPI)
def teacher(teacher_id: int):
    services = g.services
    person = get_or_404(services.users.get(teacher_id))
    if not isinstance(person, Teacher):
        get_or_404(None)
    # A teacher sees only their own KPI (NFR-01.1).
    if not g.user.can(VIEW_ALL_KPI) and g.user.id != person.id:
        return render_template("denied.html"), 403
    month, months = selected_month()
    try:
        result = services.kpi.calculate(person, month)
    except KpiError as error:
        fail(str(error))
        return redirect(url_for("kpi.dashboard"))
    previous = services.kpi.performance.snapshot(person.id, shift_month(month, -1))
    if result.overall is not None and previous is not None:
        result.change = round(result.overall - previous.overall, 1)
    feedback = services.kpi.performance.feedback_for_teacher(person.id, month)
    return render_template(
        "kpi_teacher.html",
        teacher=person,
        result=result,
        month=month,
        months=months,
        trend=services.kpi.trend(person, month),
        retention=services.kpi.retention_by_group(person, month),
        feedback=feedback,
        distribution=[sum(1 for f in feedback if f.rating == stars) for stars in range(5, 0, -1)],
        comments=[f.comment for f in feedback if f.comment][:6],
        achievements=services.kpi.performance.achievements(person.id),
        workload=services.workload.row_for(person, month),
    )


@blueprint.get("/kpi/settings")
@requires(CONFIGURE_KPI)
def settings():
    services = g.services
    month = services.kpi.current_month()
    return render_template(
        "kpi_settings.html",
        month=month,
        next_month=shift_month(month, 1),
        current=services.kpi.weights_for(month),
        pending=services.kpi.pending_weights(),
        indicators=INDICATORS,
        teachers=services.users.teachers(),
        ratings={t.id: services.kpi.performance.rating(t.id, month) for t in services.users.teachers()},
        unverified=services.kpi.performance.unverified_achievements(),
    )


@blueprint.post("/kpi/settings/weights")
@requires(CONFIGURE_KPI)
def save_weights():
    percents = {i.code: request.form.get(f"weight_{i.code}", type=int, default=0) for i in INDICATORS}
    try:
        weight_set = g.services.kpi.save_weights(g.user, percents)
        commit(f"Weights saved. They apply from {weight_set.effective_from}; past results are unchanged.")
    except KpiError as error:
        fail(str(error))
    return redirect(url_for("kpi.settings"))


@blueprint.post("/kpi/settings/rating/<int:teacher_id>")
@requires(RATE_TEACHERS)
def rate(teacher_id: int):
    services = g.services
    person = get_or_404(services.users.get(teacher_id))
    try:
        value = float(request.form.get("rating", ""))
        services.kpi.rate(g.user, person, services.kpi.current_month(), value)
        commit(f"Rating saved for {person.full_name}: {value:g} out of 10.")
    except ValueError:
        fail("Enter a number between 0 and 10.")
    except KpiError as error:
        fail(str(error))
    return redirect(url_for("kpi.settings") + "#ratings")


@blueprint.post("/kpi/settings/achievement/<int:achievement_id>/verify")
@requires(RATE_TEACHERS)
def verify(achievement_id: int):
    services = g.services
    achievement = get_or_404(services.kpi.performance.achievement(achievement_id))
    services.kpi.verify_achievement(g.user, achievement)
    commit(f"Verified: {achievement.title} ({achievement.teacher.full_name}). It now counts towards KPI.")
    return redirect(url_for("kpi.settings") + "#achievements")
