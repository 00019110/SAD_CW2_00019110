"""UC-01 screens: room QR display, scan, and the administrator's exceptions."""
from __future__ import annotations

from datetime import datetime, timedelta

import segno
from flask import Blueprint, g, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup

from ..domain import Teacher
from ..domain.people import CONFIRM_ATTENDANCE, SCAN
from ..services import AttendanceError, QrCodeMethod
from .context import commit, fail, get_or_404, requires

blueprint = Blueprint("attendance", __name__)
MAX_FAILED_SCANS = 3


def qr_svg(text: str) -> Markup:
    qr = segno.make(text, error="m")
    return Markup(qr.svg_inline(scale=8, border=2, dark="#0f1b2d", light="#ffffff"))


# -- room screen (the tablet at the classroom door) -------------------------
@blueprint.get("/rooms")
@requires(CONFIRM_ATTENDANCE)
def rooms():
    return render_template("rooms.html", rooms=g.services.timetable.rooms())


@blueprint.get("/room/<int:room_id>/display")
def room_display(room_id: int):
    room = get_or_404(g.services.timetable.room(room_id))
    return render_template("room_display.html", room=room)


@blueprint.get("/room/<int:room_id>/code")
def room_code(room_id: int):
    """The current code for a room; the display polls this every few seconds."""
    room = get_or_404(g.services.timetable.room(room_id))
    now = g.services.clock.now().replace(second=datetime.now().second)
    token = QrCodeMethod.token_for(room, now)
    link = url_for("attendance.scan_link", room=room.id, token=token, _external=True)
    return jsonify(svg=str(qr_svg(link)), seconds_left=QrCodeMethod.seconds_left(now), token=token)


# -- scanning ---------------------------------------------------------------
@blueprint.get("/scan")
@requires(SCAN)
def scan():
    services = g.services
    open_session = services.attendance.open_work_session(g.user) if isinstance(g.user, Teacher) else None
    return render_template(
        "scan.html",
        rooms=services.timetable.rooms(),
        chosen=request.args.get("room", type=int) or (open_session.session.room_id if open_session else None),
        open_session=open_session,
    )


@blueprint.post("/scan")
@requires(SCAN)
def scan_submit():
    """The 'camera' reads the code currently on the chosen room's screen.

    `simulate` lets the demo show rejected scans: an old photo of the code.
    """
    services = g.services
    room = get_or_404(services.timetable.room(request.form.get("room_id", type=int)))
    read_at = datetime.now().replace(microsecond=0) + timedelta(minutes=services.clock.offset_minutes())
    if request.form.get("simulate") == "old_photo":
        read_at -= timedelta(minutes=5)
    token = QrCodeMethod.token_for(room, read_at)
    return _handle_scan(room, token, request.form.get("action", "check_in"))


@blueprint.get("/scan/go")
@requires(SCAN)
def scan_link():
    """Target of the real QR code, for a phone on the same network."""
    room = get_or_404(g.services.timetable.room(request.args.get("room", type=int)))
    return _handle_scan(room, request.args.get("token", ""), "check_in")


def _handle_scan(room, token: str, action: str):
    services, user = g.services, g.user
    evidence = {"token": token}
    try:
        if action == "check_out" and isinstance(user, Teacher):
            work = services.attendance.check_out(user, room, evidence)
            commit()
            session["failed_scans"] = 0
            return render_template("scan_result.html", outcome="checked_out", work=work, item=work.session)
        result = services.attendance.check_in(user, room, evidence)
        commit()
        session["failed_scans"] = 0
        return render_template(
            "scan_result.html",
            outcome="duplicate" if result.duplicate else "checked_in",
            result=result,
            item=result.session,
        )
    except AttendanceError as error:
        services.db.rollback()
        failed = session.get("failed_scans", 0) + 1
        session["failed_scans"] = failed
        return render_template(
            "scan_result.html", outcome="rejected", error=error, room=room,
            failed=failed, see_admin=failed >= MAX_FAILED_SCANS,
        )


# -- administrator: exceptions ----------------------------------------------
@blueprint.get("/attendance/exceptions")
@requires(CONFIRM_ATTENDANCE)
def exceptions():
    services = g.services
    now = services.clock.now()
    day_start = datetime.combine(now.date(), datetime.min.time())
    todays = services.timetable.between(day_start - timedelta(hours=6), day_start + timedelta(days=1))
    chosen = services.timetable.get(request.args.get("session", type=int) or 0)
    people = []
    if chosen is not None:
        present = {c.user_id for c in services.attendance.attendance.check_ins_for_session(chosen.id)}
        people = [p for p in [chosen.teacher, *chosen.group.active_students] if p.id not in present]
    return render_template(
        "exceptions.html",
        flagged=services.attendance.flagged_sessions(),
        unsubmitted=services.timetable.lessons_without_register(now, day_start - timedelta(days=2)),
        todays=[s for s in todays if s.starts_at <= now + timedelta(minutes=30)],
        chosen=chosen,
        people=people,
    )


@blueprint.post("/attendance/manual")
@requires(CONFIRM_ATTENDANCE)
def manual_confirmation():
    services = g.services
    item = get_or_404(services.timetable.get(request.form.get("session_id", type=int)))
    person = get_or_404(services.users.get(request.form.get("user_id", type=int)))
    try:
        result = services.attendance.confirm_manually(g.user, person, item, request.form.get("reason", ""))
        if result.duplicate:
            fail(f"{person.full_name} is already checked in for this session.")
        else:
            commit(f"Attendance confirmed manually for {person.full_name} (method: Manual, by {g.user.full_name}).")
    except AttendanceError as error:
        fail(error.message)
    return redirect(url_for("attendance.exceptions", session=item.id))


@blueprint.post("/attendance/work-session/<int:work_session_id>/correct")
@requires(CONFIRM_ATTENDANCE)
def correct_work_session(work_session_id: int):
    services = g.services
    work = get_or_404(services.attendance.attendance.work_session(work_session_id))
    try:
        hours, minutes = (int(part) for part in request.form.get("check_out", "").split(":"))
        check_out_at = work.session.ends_at.replace(hour=hours, minute=minutes)
        services.attendance.correct_work_session(g.user, work, check_out_at, request.form.get("reason", ""))
        commit(f"Work session for {work.teacher.full_name} confirmed: {work.worked_minutes} minutes worked.")
    except ValueError:
        fail("Enter the check-out time as HH:MM.")
    except AttendanceError as error:
        fail(error.message)
    return redirect(url_for("attendance.exceptions"))
