"""Workload Report screen (FR-03)."""
from __future__ import annotations

from flask import Blueprint, g, render_template

from ..domain import Subject
from ..domain.people import VIEW_WORKLOAD
from .context import requires, selected_month, selected_role, selected_subject

blueprint = Blueprint("workload", __name__)


@blueprint.get("/workload")
@requires(VIEW_WORKLOAD)
def report():
    month, months = selected_month()
    rows = g.services.workload.report(month, selected_subject(), selected_role())
    return render_template(
        "workload.html",
        rows=rows,
        month=month,
        months=months,
        subjects=list(Subject),
        subject=selected_subject(),
        role=selected_role(),
        totals={
            "planned": round(sum(r.planned_minutes for r in rows) / 60, 1),
            "worked": round(sum(r.worked_minutes for r in rows) / 60, 1),
            "overtime": round(sum(r.overtime_minutes for r in rows) / 60, 1),
            "late": sum(r.late_arrivals for r in rows),
            "missing": sum(r.missing_check_outs for r in rows),
        },
    )
