"""Sign-in, home pages per role, notifications and the demo controls."""
from __future__ import annotations

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from ..domain import (
    Administrator,
    Director,
    HeadSpecialist,
    Lesson,
    MainTeacher,
    RiskLevel,
    Student,
    SupportTeacher,
    Teacher,
)
from ..domain.people import VIEW_ALL_KPI, VIEW_RISK
from ..integration.edutizim import DEMO_STUDENT
from ..services.clock import month_key
from .context import commit, get_or_404, requires

blueprint = Blueprint("auth", __name__)


@blueprint.get("/")
def index():
    if g.user is None:
        return redirect(url_for("auth.login"))
    return redirect(home_for(g.user))


def home_for(user) -> str:
    if isinstance(user, (Teacher, Student)):
        return url_for("auth.today")
    if isinstance(user, Administrator):
        return url_for("attendance.exceptions")
    if isinstance(user, HeadSpecialist):
        return url_for("kpi.dashboard")
    return url_for("auth.overview")


@blueprint.get("/login")
def login():
    users = g.services.users
    students = users.students()
    demo_student = next((s for s in students if s.full_name == DEMO_STUDENT), None)
    accounts = [
        ("Teachers", users.by_role(MainTeacher)[:3] + users.by_role(SupportTeacher)[:2]),
        ("Student", [s for s in [demo_student] if s]),
        ("Management", users.by_role(Administrator) + users.by_role(HeadSpecialist) + users.by_role(Director)),
    ]
    # Put the teacher used in the walkthrough first.
    accounts[0][1].sort(key=lambda t: t.username != "t_dilnoza")
    return render_template("login.html", accounts=accounts)


@blueprint.post("/login")
def sign_in():
    user = get_or_404(g.services.users.get(request.form.get("user_id", type=int)))
    session.clear()
    session["user_id"] = user.id
    return redirect(home_for(user))


@blueprint.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@blueprint.get("/today")
@requires()
def today():
    """Home for teachers and students: today's sessions and their attendance state."""
    services, user = g.services, g.user
    now = services.clock.now()
    rows = []
    for item in services.timetable.for_user_on(user, now.date()):
        if item.starts_at.date() != now.date() and item.ends_at.date() != now.date():
            continue
        check_in = services.attendance.attendance.check_in_for(user.id, item.id)
        register = services.attendance.attendance.register_for(item.id) if isinstance(item, Lesson) else None
        work = (
            services.attendance.attendance.work_session_for(user.id, item.id)
            if isinstance(user, Teacher)
            else None
        )
        state = "upcoming" if item.starts_at > now else ("live" if item.ends_at >= now else "ended")
        rows.append(
            {"session": item, "check_in": check_in, "register": register, "work": work, "state": state,
             "window": item.is_within_check_in_window(now)}
        )
    if isinstance(user, Student):
        recent = services.attendance.attendance.recent_check_ins(user.id)
        return render_template("student_today.html", rows=rows, recent=recent)
    return render_template("teacher_today.html", rows=rows)


@blueprint.get("/overview")
@requires(VIEW_RISK, VIEW_ALL_KPI)
def overview():
    """Director's home: the headline figures behind the three dashboards."""
    services = g.services
    month = month_key(services.clock.today())
    risk = services.risk.dashboard()
    services.db.commit()
    ranking = services.kpi.ranking(month)
    scored = [r.overall for r in ranking if r.overall is not None]
    return render_template(
        "overview.html",
        month=month,
        risk=risk,
        high=[r for r in risk.rows if r.level is RiskLevel.HIGH][:5],
        ranking=ranking,
        average_kpi=round(sum(scored) / len(scored), 1) if scored else None,
        retention=services.retention.overall(month),
        trend=services.retention.trend(),
        RiskLevel=RiskLevel,
    )


@blueprint.get("/notifications")
@requires()
def notifications():
    inbox = g.services.notifications.inbox(g.user)
    response = render_template("notifications.html", inbox=inbox)
    g.services.notifications.mark_all_read(g.user)
    commit()
    return response


@blueprint.post("/demo/clock")
def demo_clock():
    """Demo control: move the application clock so a 90-minute lesson can be shown in a minute."""
    if request.form.get("reset"):
        g.services.clock.reset()
        flash("Demo clock reset to the real time.", "info")
    else:
        minutes = request.form.get("minutes", type=int, default=0)
        g.services.clock.advance(minutes)
        flash(f"Demo clock moved forward {minutes} minutes.", "info")
    g.services.db.commit()
    return redirect(request.referrer or url_for("auth.index"))


@blueprint.post("/demo/reset")
def demo_reset():
    g.services.db.close()
    current_app.extensions["nsp_seed"]()
    session.clear()
    flash("Demo data restored to its starting state.", "info")
    return redirect(url_for("auth.login"))
