"""Every screen renders for the role that is allowed to see it."""
import pytest

from nsp import create_app
from nsp.domain import Administrator, Director, HeadSpecialist, Lesson, MainTeacher, Student, SupportTeacher


@pytest.fixture(scope="module")
def app():
    return create_app("sqlite://", reseed=True)


def login(app, role_class, username=None):
    client = app.test_client()
    database = app.extensions["nsp_database"]
    db = database.session()
    query = db.query(role_class)
    user = query.filter_by(username=username).one() if username else query.first()
    user_id = user.id
    database.session.remove()
    assert client.post("/login", data={"user_id": user_id}).status_code == 302
    return client, user_id


PAGES = {
    MainTeacher: ["/today", "/scan", "/kpi/me"],
    SupportTeacher: ["/today", "/scan", "/kpi/me"],
    Student: ["/today", "/scan", "/feedback"],
    Administrator: ["/attendance/exceptions", "/rooms", "/risk", "/workload", "/notifications", "/risk/export.csv"],
    HeadSpecialist: ["/kpi", "/kpi/settings", "/workload", "/kpi/export.csv", "/kpi?month=bad&subject=ENGLISH&role=main_teacher"],
    Director: ["/overview", "/risk", "/risk?level=HIGH&subject=ENGLISH", "/kpi", "/retention", "/workload"],
}


@pytest.mark.parametrize("role_class", PAGES)
def test_pages_render(app, role_class):
    client, _ = login(app, role_class)
    for page in PAGES[role_class]:
        response = client.get(page, follow_redirects=True)
        assert response.status_code == 200, f"{role_class.__name__} {page}"


def test_login_page_and_room_screen_are_public(app):
    client = app.test_client()
    assert client.get("/login").status_code == 200
    assert client.get("/room/1/display").status_code == 200
    assert "svg" in client.get("/room/1/code").get_json()
    assert client.get("/today").status_code == 302


def test_roles_cannot_open_each_others_pages(app):
    teacher, _ = login(app, MainTeacher)
    assert teacher.get("/risk").status_code == 403
    assert teacher.get("/kpi").status_code == 403
    student, _ = login(app, Student)
    assert student.get("/workload").status_code == 403


def test_teacher_sees_only_own_kpi(app):
    client, user_id = login(app, MainTeacher, "t_dilnoza")
    assert client.get(f"/kpi/teacher/{user_id}").status_code == 200
    assert client.get(f"/kpi/teacher/{user_id + 1}").status_code == 403


def test_walkthrough_scan_register_alert_dashboard(app):
    """The path shown in the screencast."""
    client, teacher_id = login(app, MainTeacher, "t_dilnoza")
    assert b"Scan not accepted" in client.post("/scan", data={"room_id": 1, "simulate": "old_photo"}).data
    assert b"Scan not accepted" in client.post("/scan", data={"room_id": 3, "action": "check_in"}).data
    assert b"Checked in" in client.post("/scan", data={"room_id": 1, "action": "check_in"}).data
    assert b"Already checked in" in client.post("/scan", data={"room_id": 1, "action": "check_in"}).data

    database = app.extensions["nsp_database"]
    db = database.session()
    lesson = next(
        l for l in db.query(Lesson).filter_by(teacher_id=teacher_id).order_by(Lesson.starts_at.desc())
    )
    lesson_id = lesson.id
    database.session.remove()

    page = client.get(f"/register/{lesson_id}")
    assert page.status_code == 200 and b"Not scanned" in page.data
    blocked = client.post(f"/register/{lesson_id}", data={"action": "submit"}, follow_redirects=True)
    assert b"still have no status" in blocked.data

    db = database.session()
    from nsp.domain import AttendanceStatus, LessonRegister
    register = db.query(LessonRegister).filter_by(session_id=lesson_id).one()
    form = {"action": "submit"}
    for entry in register.entries:
        if entry.status is AttendanceStatus.NOT_SCANNED:
            form[f"status_{entry.id}"] = "ABSENT"
    database.session.remove()
    done = client.post(f"/register/{lesson_id}", data=form, follow_redirects=True)
    assert b"Register submitted and locked" in done.data
    assert b"Dropout risk alert raised" in done.data

    assert b"Checked out" in client.post("/scan", data={"room_id": 1, "action": "check_out"}).data

    director, _ = login(app, Director)
    assert b"3 consecutive absences" in director.get("/risk?level=HIGH").data
