"""A small hand-built centre with a fixed clock, so every rule can be tested exactly."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from nsp.data import Database
from nsp.domain import (
    Administrator,
    Director,
    Group,
    HeadSpecialist,
    KpiWeight,
    KpiWeightSet,
    Lesson,
    MainTeacher,
    Room,
    Student,
    Subject,
    SupportTeacher,
)
from nsp.services import (
    AttendanceService,
    FixedClock,
    KpiService,
    NotificationService,
    RegisterService,
    RiskService,
    WorkloadService,
)
from nsp.services.kpi import DEFAULT_WEIGHTS

START = datetime(2026, 11, 25, 10, 0)  # the lesson starts at 10:00


@pytest.fixture
def world():
    database = Database("sqlite://")
    database.create_all()
    db = database.session()
    clock = FixedClock(START)

    teacher = MainTeacher(full_name="Main Teacher", username="main", subject=Subject.ENGLISH)
    support = SupportTeacher(full_name="Support Teacher", username="support", subject=Subject.ENGLISH)
    admin = Administrator(full_name="Admin", username="admin")
    head = HeadSpecialist(full_name="Head", username="head")
    director = Director(full_name="Director", username="director")
    students = [
        Student(
            full_name=f"Student {n}", username=f"s{n}", enrolled_on=date(2026, 6, 1),
            monthly_fee=400_000, tuition_debt=0, consecutive_absences=0,
        )
        for n in range(1, 7)
    ]
    room, other_room = Room(name="Room 1", qr_secret="one"), Room(name="Room 2", qr_secret="two")
    group = Group(
        name="ENG-1", subject=Subject.ENGLISH, level="IELTS 6.0",
        main_teacher=teacher, support_teacher=support, students=students,
    )
    lesson = Lesson(
        group=group, room=room, teacher=teacher, starts_at=START, ends_at=START + timedelta(minutes=90)
    )
    weights = KpiWeightSet(effective_from="2026-01")
    weights.weights = [KpiWeight(indicator_code=c, percent=p) for c, p in DEFAULT_WEIGHTS.items()]
    db.add_all([teacher, support, admin, head, director, room, other_room, group, lesson, weights])
    db.commit()

    notifications = NotificationService(db, clock)
    risk = RiskService(db, clock, notifications)
    yield SimpleNamespace(
        db=db, clock=clock, teacher=teacher, support=support, admin=admin, head=head,
        director=director, students=students, room=room, other_room=other_room, group=group,
        lesson=lesson, notifications=notifications, risk=risk,
        attendance=AttendanceService(db, clock, notifications),
        register=RegisterService(db, clock, risk),
        kpi=KpiService(db, clock),
        workload=WorkloadService(db, clock),
    )
    database.session.remove()
