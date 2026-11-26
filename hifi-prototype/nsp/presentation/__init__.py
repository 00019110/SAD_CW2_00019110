"""Presentation layer: Flask controllers and templates.

Controllers only read the request, call a service and pick a template.
No business rule lives here.
"""
from __future__ import annotations

from flask import Flask, g, session

from .context import Services, format_minutes, format_money
from ..services.clock import month_label


def register_presentation(app: Flask) -> None:
    from . import (
        attendance_controller,
        auth_controller,
        kpi_controller,
        register_controller,
        retention_controller,
        risk_controller,
        workload_controller,
    )

    for module in (
        auth_controller,
        attendance_controller,
        register_controller,
        risk_controller,
        kpi_controller,
        workload_controller,
        retention_controller,
    ):
        app.register_blueprint(module.blueprint)

    @app.before_request
    def open_services() -> None:
        database = app.extensions["nsp_database"]
        g.services = Services(database.session(), app.extensions["nsp_gateway"])
        user_id = session.get("user_id")
        g.user = g.services.users.get(user_id) if user_id else None
        if g.user is not None:
            # UC-01 ext. 8a runs on a timer in production; here on each request.
            g.services.attendance.close_stale_sessions()
            g.services.db.commit()

    @app.teardown_request
    def close_services(error=None) -> None:
        database = app.extensions["nsp_database"]
        if error is not None:
            database.session.rollback()
        database.session.remove()

    @app.context_processor
    def template_globals() -> dict:
        services = g.get("services")
        user = g.get("user")
        return {
            "current_user": user,
            "now": services.clock.now() if services else None,
            "clock_offset": services.clock.offset_minutes() if services else 0,
            "unread": services.notifications.unread_count(user) if user else 0,
            "last_sync": services.sync.last_sync() if services else None,
        }

    app.jinja_env.filters["minutes"] = format_minutes
    app.jinja_env.filters["money"] = format_money
    app.jinja_env.filters["month_label"] = month_label
