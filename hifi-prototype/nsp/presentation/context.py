"""Request-scoped wiring: builds the services once per request, plus view helpers."""
from __future__ import annotations

from functools import wraps

from flask import abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy.orm import Session

from ..data import SettingsRepository, TimetableRepository, UserRepository
from ..domain import Subject
from ..integration import EduTizimGateway
from ..services import (
    AttendanceService,
    Clock,
    KpiService,
    NotificationService,
    RegisterService,
    RetentionService,
    RiskService,
    SyncService,
    WorkloadService,
)
from ..services.clock import month_key, recent_months


class Services:
    """Composition root: the one place where services are wired together."""

    def __init__(self, db: Session, gateway: EduTizimGateway) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.timetable = TimetableRepository(db)
        self.clock = Clock(SettingsRepository(db))
        self.notifications = NotificationService(db, self.clock)
        self.sync = SyncService(db, self.clock, gateway)
        self.attendance = AttendanceService(db, self.clock, self.notifications)
        self.risk = RiskService(db, self.clock, self.notifications)
        self.register = RegisterService(db, self.clock, self.risk, self.sync)
        self.kpi = KpiService(db, self.clock)
        self.workload = WorkloadService(db, self.clock)
        self.retention = RetentionService(db, self.clock)


def requires(*permissions: str):
    """Role-based access (NFR-01.1): the user needs at least one of the permissions."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login"))
            if permissions and not any(g.user.can(p) for p in permissions):
                return render_template("denied.html"), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def get_or_404(entity):
    if entity is None:
        abort(404)
    return entity


def commit(message: str | None = None, category: str = "success") -> None:
    g.services.db.commit()
    if message:
        flash(message, category)


def fail(message: str) -> None:
    g.services.db.rollback()
    flash(message, "error")


def selected_month() -> tuple[str, list[str]]:
    """The month chosen in the page filter, and the six months on offer."""
    current = month_key(g.services.clock.today())
    months = recent_months(current, 6)
    chosen = request.args.get("month", current)
    return (chosen if chosen in months else current), months


def selected_subject() -> Subject | None:
    value = request.args.get("subject", "")
    return next((s for s in Subject if s.name == value), None)


def selected_role() -> str | None:
    value = request.args.get("role", "")
    return value if value in ("main_teacher", "support_teacher") else None


def format_minutes(minutes: int | None) -> str:
    if not minutes:
        return "0 min"
    hours, rest = divmod(int(minutes), 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    return f"{hours} h" if hours else f"{rest} min"


def format_money(amount: int | None) -> str:
    if amount is None:
        return "–"
    return f"{amount:,.0f}".replace(",", " ") + " UZS"
