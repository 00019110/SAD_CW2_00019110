"""Demo data owned by the module itself.

EduTizim-owned data (people, groups, timetable, balances) arrives through the
gateway. This seeder then adds the history the new module would have produced:
registers, work sessions, test results, feedback, ratings, KPI snapshots,
circumstances, alerts and marketing spend. Everything is fictional.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..domain import (
    Achievement,
    AlertStatus,
    AttendanceStatus,
    CheckIn,
    CheckInMethod,
    CheckInStatus,
    Circumstance,
    CircumstanceKind,
    Feedback,
    FollowUpAction,
    IndicatorScore,
    KpiSnapshot,
    KpiWeight,
    KpiWeightSet,
    Lesson,
    LessonRegister,
    MarketingSpend,
    MonthlyRating,
    Notification,
    RegisterEntry,
    RiskAlert,
    Student,
    Subject,
    Teacher,
    TestResult,
    WorkSession,
    WorkSessionStatus,
)
from ..integration.edutizim import DEMO_STUDENT, DemoEduTizimGateway
from ..services.clock import FixedClock, month_key, shift_month
from ..services.kpi import DEFAULT_WEIGHTS, INDICATORS
from ..services.notifications import NotificationService
from ..services.risk import RiskService
from ..services.sync import SyncService

HISTORY_DAYS = 30
SNAPSHOT_MONTHS = 5

# Teaching quality 0-1 per teacher: drives results, feedback, rating, punctuality.
QUALITY = {
    "t_dilnoza": 0.86, "t_jasur": 0.71, "t_malika": 0.92, "t_sardor": 0.78, "t_nigora": 0.64,
    "t_aziz": 0.83, "t_shahnoza": 0.58, "s_bobur": 0.80, "s_kamola": 0.74, "s_lola": 0.88,
    "s_timur": 0.67, "s_zarina": 0.90, "s_farrukh": 0.61, "s_madina": 0.77, "s_davron": 0.70,
}


class DemoSeeder:
    def __init__(self, db: Session, now: datetime, seed: int = 2026) -> None:
        self.db = db
        self.now = now.replace(second=0, microsecond=0)
        self.random = random.Random(seed)
        self.clock = FixedClock(self.now)
        self.gateway = DemoEduTizimGateway(self.now, seed)
        self.sync = SyncService(db, self.clock, self.gateway)
        self.month = month_key(self.now.date())

    def run(self) -> DemoEduTizimGateway:
        today = self.now.date()
        self.sync.import_all(today - timedelta(days=HISTORY_DAYS), today)
        self.users = self.sync.users
        self.teachers = {k: u for k, u in self.users.items() if isinstance(u, Teacher)}
        self.students = [u for u in self.users.values() if isinstance(u, Student) and u.is_active]
        self.live_group = self.sync.groups["ENG-1"]
        self._choose_story_students()
        self._weights()
        self._history()
        self._today()
        self._tests_feedback_ratings()
        self._achievements()
        self._snapshots()
        self._circumstances_and_alerts()
        self._marketing()
        self.db.flush()
        RiskService(self.db, self.clock, NotificationService(self.db, self.clock)).recalculate_all()
        self._notifications()
        self.db.commit()
        return self.gateway

    # -- who plays which part in the walkthrough ----------------------------
    def _choose_story_students(self) -> None:
        rnd = self.random
        live = [s for s in self.live_group.students if s.full_name != DEMO_STUDENT]
        self.demo_student = next(s for s in self.live_group.students if s.full_name == DEMO_STUDENT)
        # Two students in the live lesson already missed the last two lessons.
        self.about_to_alert = live[:2]
        self.not_scanned_today = [self.demo_student, *self.about_to_alert, live[2]]
        established = [
            s for s in self.students
            if s not in self.live_group.students and (self.now.date() - s.enrolled_on).days > 40
        ]
        rnd.shuffle(established)
        self.absent_tail = {s.id: 2 for s in self.about_to_alert}
        for student, tail in zip(established[:12], [4, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1]):
            self.absent_tail[student.id] = tail
        self.unhappy = established[12:17]
        self.struggling = established[17:22]
        for student in self.live_group.students:  # keep the live group's story clean
            student.tuition_debt = 0
        # One student with several risk factors at once: absences, debt and a reported problem.
        self.absent_tail[self.struggling[0].id] = 2
        self.struggling[0].tuition_debt = (self.struggling[0].monthly_fee or 0) * 2

    def _weights(self) -> None:
        weight_set = KpiWeightSet(effective_from=shift_month(self.month, -12), set_by_id=self.users["head"].id)
        for code, percent in DEFAULT_WEIGHTS.items():
            weight_set.weights.append(KpiWeight(indicator_code=code, percent=percent))
        self.db.add(weight_set)

    # -- past lessons -------------------------------------------------------
    def _work_session(self, session, quality: float, forgot: bool = False) -> WorkSession:
        rnd = self.random
        late = rnd.random() > 0.55 + 0.45 * quality
        arrived = session.starts_at + timedelta(minutes=rnd.randint(11, 24) if late else -rnd.randint(2, 14))
        work = WorkSession(
            teacher_id=session.teacher_id, session_id=session.id, check_in_at=arrived,
            minutes_late=session.minutes_late(arrived),
        )
        work.session = session
        if not forgot:
            work.close(session.ends_at + timedelta(minutes=rnd.choice([0, 1, 2, 3, 5, 8, 15, 25])))
        self.db.add(work)
        self.db.add(
            CheckIn(
                user_id=session.teacher_id, session_id=session.id, timestamp=arrived,
                method=CheckInMethod.QR,
                status=CheckInStatus.LATE if work.minutes_late else CheckInStatus.ON_TIME,
                minutes_late=work.minutes_late,
            )
        )
        return work

    def _register(self, lesson: Lesson, absent_ids: set[int], submitted_at: datetime) -> LessonRegister:
        rnd = self.random
        register = LessonRegister(session_id=lesson.id)
        register.session = lesson
        for student in lesson.group.active_students:
            if student.enrolled_on > lesson.starts_at.date():
                continue
            if student.id in absent_ids:
                status = AttendanceStatus.ABSENT
            elif lesson.group is self.live_group or student.id in self.absent_tail:
                status = AttendanceStatus.PRESENT
            else:
                attendance = 0.80 if student in self.struggling else 0.95
                roll = rnd.random()
                if roll < attendance:
                    status = AttendanceStatus.LATE if rnd.random() < 0.06 else AttendanceStatus.PRESENT
                elif roll < attendance + 0.015:
                    status = AttendanceStatus.EXCUSED
                else:
                    status = AttendanceStatus.ABSENT
            entry = RegisterEntry(
                student_id=student.id, status=status,
                scanned=status in (AttendanceStatus.PRESENT, AttendanceStatus.LATE),
                reason="Illness reported by parent" if status is AttendanceStatus.EXCUSED else None,
            )
            entry.student = student
            register.entries.append(entry)
            if status is AttendanceStatus.ABSENT:
                student.register_absence()
            elif status is not AttendanceStatus.EXCUSED:
                student.reset_absences()
        register.lock(lesson.teacher_id, submitted_at)
        self.db.add(register)
        return register

    def _history(self) -> None:
        today = self.now.date()
        past = [s for _tag, s in self.sync.sessions if s.starts_at.date() < today]
        # The last N lessons of each group are where the "absent tail" students are missing.
        lessons_by_group: dict[int, list[Lesson]] = {}
        for session in past:
            if isinstance(session, Lesson):
                lessons_by_group.setdefault(session.group_id, []).append(session)
        position_from_end = {}
        for lessons in lessons_by_group.values():
            for offset, lesson in enumerate(reversed(lessons), start=1):
                position_from_end[lesson.id] = offset

        for session in past:
            quality = QUALITY[session.teacher.username]
            self._work_session(session, quality)
            if isinstance(session, Lesson):
                offset = position_from_end[session.id]
                absent = {
                    s.id for s in session.group.students
                    if self.absent_tail.get(s.id, 0) >= offset
                }
                self._register(session, absent, session.ends_at + timedelta(minutes=4))
        self.db.flush()

    # -- today's sessions ---------------------------------------------------
    def _today(self) -> None:
        rnd = self.random
        for tag, session in self.sync.sessions:
            if session.starts_at.date() != self.now.date() or not tag:
                continue
            if tag == "done":
                work = self._work_session(session, 1.0)
                work.check_in_at = session.starts_at - timedelta(minutes=6)
                work.minutes_late = 0
                work.close(session.ends_at + timedelta(minutes=12))
                self._register(session, set(), session.ends_at + timedelta(minutes=3))
            elif tag == "missing_checkout":
                self._work_session(session, 1.0, forgot=True)
                self._register(session, set(), session.ends_at + timedelta(minutes=5))
            elif tag == "late_teacher":
                arrived = session.starts_at + timedelta(minutes=16)
                work = WorkSession(
                    teacher_id=session.teacher_id, session_id=session.id, check_in_at=arrived, minutes_late=16
                )
                self.db.add(work)
                self.db.add(
                    CheckIn(
                        user_id=session.teacher_id, session_id=session.id, timestamp=arrived,
                        method=CheckInMethod.QR, status=CheckInStatus.LATE, minutes_late=16,
                    )
                )
            elif tag == "no_register":
                work = self._work_session(session, 1.0)
                work.minutes_late = 0
            elif tag == "live":
                # Seven of eleven students have already scanned the room code.
                for student in session.group.active_students:
                    if student in self.not_scanned_today:
                        continue
                    self.db.add(
                        CheckIn(
                            user_id=student.id, session_id=session.id,
                            timestamp=session.starts_at - timedelta(minutes=rnd.randint(1, 12)),
                            method=CheckInMethod.QR, status=CheckInStatus.ON_TIME,
                        )
                    )

    # -- KPI inputs ---------------------------------------------------------
    def _tests_feedback_ratings(self) -> None:
        rnd = self.random
        comments_good = ["Explains clearly", "Lessons are well prepared", "Always answers questions", "Very supportive"]
        comments_bad = ["Too fast for me", "Homework is not checked", "I do not understand the explanations"]
        for group in self.sync.groups.values():
            quality = QUALITY[group.main_teacher.username]
            for student in group.active_students:
                base = 42 + 45 * quality + rnd.gauss(0, 9) - (12 if student in self.struggling else 0)
                for kind, shift in (("weekly", 3), ("mock", -4)):
                    self.db.add(
                        TestResult(
                            student_id=student.id, group_id=group.id, month=self.month, kind=kind,
                            score=round(max(15, min(100, base + shift + rnd.gauss(0, 4))), 1),
                        )
                    )
                if student is self.demo_student:
                    continue  # she gives her feedback live in the demo
                for teacher in (group.main_teacher, group.support_teacher):
                    if teacher is None:
                        continue
                    if student in self.unhappy:
                        rating, comment = rnd.choice([1, 2]), rnd.choice(comments_bad)
                    elif rnd.random() > 0.7:
                        continue
                    else:
                        rating = max(1, min(5, round(1.6 + 3.6 * QUALITY[teacher.username] + rnd.gauss(0, 0.7))))
                        comment = rnd.choice(comments_good) if rating >= 4 and rnd.random() < 0.4 else None
                    self.db.add(
                        Feedback(
                            student_id=student.id, teacher_id=teacher.id, month=self.month,
                            rating=rating, comment=comment,
                        )
                    )
        not_rated_yet = {"t_nigora", "s_farrukh"}
        for key, teacher in self.teachers.items():
            if key in not_rated_yet:
                continue
            rating = max(3, min(10, round(2.5 + 7.5 * QUALITY[key] + rnd.gauss(0, 0.5))))
            self.db.add(
                MonthlyRating(
                    teacher_id=teacher.id, month=self.month, rating=rating,
                    rated_by_id=self.users["head"].id,
                )
            )

    def _achievements(self) -> None:
        today, head = self.now.date(), self.users["head"]
        rows = [
            ("t_dilnoza", "IELTS Academic 8.0", 60, 400, True),
            ("t_dilnoza", "CELTA certificate", 30, 20, False),
            ("t_malika", "IELTS Academic 8.5", 70, 250, True),
            ("t_malika", "TESOL certificate", 25, 120, True),
            ("t_jasur", "IELTS Academic 7.5", 50, 300, True),
            ("t_sardor", "National Chemistry Olympiad – jury member", 40, 200, True),
            ("t_nigora", "DTM national certificate (Chemistry)", 35, 500, True),
            ("t_aziz", "DTM national certificate (Biology)", 35, 340, True),
            ("t_aziz", "Published DTM Biology workbook", 30, 90, True),
            ("t_shahnoza", "Teaching methodology course", 20, 15, False),
            ("s_lola", "IELTS Academic 7.5", 50, 180, True),
            ("s_bobur", "IELTS Academic 7.0", 40, 210, True),
            ("s_zarina", "DTM national certificate (Chemistry)", 35, 260, True),
            ("s_madina", "DTM national certificate (Biology)", 35, 150, True),
        ]
        for key, title, points, days_ago, verified in rows:
            self.db.add(
                Achievement(
                    teacher_id=self.teachers[key].id, title=title, points=points,
                    achieved_on=today - timedelta(days=days_ago), verified=verified,
                    verified_by_id=head.id if verified else None,
                )
            )

    def _snapshots(self) -> None:
        """Locked KPI snapshots for the five closed months before the current one."""
        rnd = self.random
        for key, teacher in self.teachers.items():
            quality = QUALITY[key]
            drift = rnd.uniform(-1.2, 1.6)  # each teacher slowly improves or slips
            for months_ago in range(SNAPSHOT_MONTHS, 0, -1):
                month = shift_month(self.month, -months_ago)
                q = max(0.3, min(1.0, quality - 0.012 * months_ago * drift))
                raw = {
                    "results": 42 + 45 * q + rnd.gauss(0, 2.5) if teacher.records_tests else None,
                    "attendance": 86 + 10 * q + rnd.gauss(0, 1.5),
                    "punctuality": 62 + 36 * q + rnd.gauss(0, 3),
                    "retention": 93 + 6 * q + rnd.gauss(0, 1.2),
                    "feedback": 20 + 78 * q + rnd.gauss(0, 3),
                    "rating": 10 * round(2.5 + 7.5 * q),
                    "achievements": 40 + 50 * q if q > 0.7 else 35.0,
                }
                included = sum(DEFAULT_WEIGHTS[c] for c, v in raw.items() if v is not None)
                snapshot = KpiSnapshot(teacher_id=teacher.id, month=month, overall=0, partial=included < 100)
                overall = 0.0
                for indicator in INDICATORS:
                    value = raw[indicator.code]
                    if value is not None:
                        value = round(max(0, min(100, value)), 1)
                    applied = DEFAULT_WEIGHTS[indicator.code] / included * 100 if value is not None else 0
                    overall += (value or 0) * applied / 100
                    snapshot.scores.append(
                        IndicatorScore(indicator_code=indicator.code, score=value, weight_applied=applied)
                    )
                snapshot.overall = round(overall, 1)
                self.db.add(snapshot)

    # -- retention ----------------------------------------------------------
    def _circumstances_and_alerts(self) -> None:
        today, admin = self.now.date(), self.users["admin"]

        alerts: dict[int, RiskAlert] = {}

        def alert_for(student, reason, status=AlertStatus.OPEN, days_ago=1.0) -> RiskAlert:
            """One open alert per student: a second reason joins the first."""
            alert = alerts.get(student.id)
            if alert is None:
                alert = RiskAlert(
                    student_id=student.id, status=status,
                    opened_at=self.now - timedelta(days=days_ago, hours=3), reasons=reason,
                )
                alerts[student.id] = alert
                self.db.add(alert)
            else:
                alert.add_reason(reason)
                if status is AlertStatus.IN_PROGRESS:
                    alert.status = status
            return alert

        # Every student already at three or more consecutive absences has an open alert.
        for student in self.students:
            if (student.consecutive_absences or 0) >= 3:
                alert_for(student, f"{student.consecutive_absences} consecutive absences")

        stories = [
            (CircumstanceKind.FINANCIAL, "Parent called: father lost his job, may not afford next month's fee.",
             "Call the parent and offer a payment plan", -1, AlertStatus.IN_PROGRESS),
            (CircumstanceKind.SOCIAL, "Student says the family may move to Tashkent in January.",
             "Meet the student and parent to discuss options", 3, AlertStatus.IN_PROGRESS),
            (CircumstanceKind.FINANCIAL, "Mother asked whether a sibling discount is available.", None, 0, AlertStatus.OPEN),
        ]
        for student, (kind, note, action, due_in, status) in zip(self.struggling, stories):
            self.db.add(
                Circumstance(
                    student_id=student.id, kind=kind, note=note,
                    recorded_on=today - timedelta(days=6), recorded_by_id=admin.id,
                )
            )
            alert = alert_for(student, f"{kind.value} circumstances reported", status, days_ago=6)
            if action:
                alert.actions.append(
                    FollowUpAction(description=action, assignee_id=admin.id, due_date=today + timedelta(days=due_in))
                )

        for student in self.unhappy[:2]:
            alert_for(student, "Negative feedback for 2 of 2 teachers", days_ago=2)

        # One alert that ended well, for the history.
        returned = next(s for s in self.students if self.absent_tail.get(s.id) == 1 and s.id not in alerts)
        resolved = RiskAlert(
            student_id=returned.id, status=AlertStatus.RESOLVED,
            opened_at=self.now - timedelta(days=20), closed_at=self.now - timedelta(days=12),
            reasons="3 consecutive absences",
        )
        resolved.actions.append(
            FollowUpAction(
                description="Add two support sessions", assignee_id=admin.id,
                due_date=today - timedelta(days=14), done=True,
            )
        )
        self.db.add(resolved)

    def _marketing(self) -> None:
        rnd = self.random
        base = {Subject.ENGLISH: 7_000_000, Subject.CHEMISTRY: 3_500_000, Subject.BIOLOGY: 3_000_000}
        for months_ago in range(6):
            for subject, amount in base.items():
                self.db.add(
                    MarketingSpend(
                        subject=subject, month=shift_month(self.month, -months_ago),
                        amount=int(amount * rnd.uniform(0.85, 1.15) // 50_000 * 50_000),
                    )
                )

    def _notifications(self) -> None:
        admin, head = self.users["admin"], self.users["head"]
        for user in (admin, head):
            self.db.add(
                Notification(
                    recipient_id=user.id, created_at=self.now - timedelta(days=1, hours=3),
                    message="Dropout risk alert: three students reached 3 consecutive absences yesterday.",
                    link="/risk",
                )
            )
        self.db.add(
            Notification(
                recipient_id=head.id, created_at=self.now - timedelta(hours=5),
                message="Two teachers still need a monthly rating before KPI can be finalised.",
                link="/kpi/settings",
            )
        )
