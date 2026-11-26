"""Retention and acquisition-cost dashboard (FR-05.6, FR-05.7)."""
from __future__ import annotations

from flask import Blueprint, g, render_template

from ..domain.people import VIEW_RETENTION
from .context import requires, selected_month

blueprint = Blueprint("retention", __name__)


@blueprint.get("/retention")
@requires(VIEW_RETENTION)
def dashboard():
    services = g.services
    month, months = selected_month()
    return render_template(
        "retention.html",
        month=month,
        months=months,
        overall=services.retention.overall(month),
        trend=services.retention.trend(),
        by_teacher=services.retention.by_teacher(month),
        by_subject=services.retention.by_subject(month),
        by_group=services.retention.by_group(month),
        acquisition=services.retention.acquisition_cost(month),
        withdrawals=services.retention.recent_withdrawals(),
    )
