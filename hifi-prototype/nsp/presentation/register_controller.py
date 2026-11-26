"""UC-02 screen: the lesson register."""
from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, request, url_for

from ..domain import AttendanceStatus, Lesson
from ..domain.people import SUBMIT_REGISTER
from ..services import RegisterError
from ..services.register import TEACHER_CHOICES
from .context import commit, fail, get_or_404, requires

blueprint = Blueprint("register", __name__)


def _lesson(session_id: int) -> Lesson:
    lesson = get_or_404(g.services.timetable.get(session_id))
    if not isinstance(lesson, Lesson):
        get_or_404(None)
    return lesson


@blueprint.get("/register/<int:session_id>")
@requires(SUBMIT_REGISTER)
def show(session_id: int):
    lesson = _lesson(session_id)
    try:
        register = g.services.register.open_register(lesson, g.user)
        commit()
    except RegisterError as error:
        fail(error.message)
        return redirect(url_for("auth.today"))
    highlight = {int(i) for i in request.args.get("highlight", "").split(",") if i.isdigit()}
    alerts = [
        a for a in g.services.risk.retention.alerts(open_only=True)
        if register.locked and a.student_id in {e.student_id for e in register.entries}
        and a.opened_at >= register.submitted_at
    ]
    return render_template(
        "register.html",
        lesson=lesson,
        register=register,
        entries=sorted(register.entries, key=lambda e: e.student.full_name),
        choices=TEACHER_CHOICES,
        highlight=highlight,
        new_alerts=alerts,
        AttendanceStatus=AttendanceStatus,
    )


@blueprint.post("/register/<int:session_id>")
@requires(SUBMIT_REGISTER)
def save(session_id: int):
    """Save every row, then submit if the teacher pressed 'Submit register'."""
    services = g.services
    lesson = _lesson(session_id)
    target = url_for("register.show", session_id=lesson.id)
    try:
        register = services.register.open_register(lesson, g.user)
        problems = []
        for entry in register.entries:
            chosen = request.form.get(f"status_{entry.id}")
            if not chosen:
                continue
            try:
                services.register.set_status(
                    entry, AttendanceStatus[chosen], request.form.get(f"reason_{entry.id}", "")
                )
            except RegisterError as error:
                problems.append(error)
        services.db.commit()
        if problems:
            fail(problems[0].message)
            ids = ",".join(str(e.id) for p in problems for e in p.entries)
            return redirect(f"{target}?highlight={ids}")
        if request.form.get("action") == "submit":
            services.register.submit(register, g.user)
            commit("Register submitted and locked. It has been sent to EduTizim.")
        else:
            commit("Register saved. It is not submitted yet.", "info")
    except RegisterError as error:
        fail(error.message)
        ids = ",".join(str(e.id) for e in error.entries)
        return redirect(f"{target}?highlight={ids}" if ids else target)
    return redirect(target)
