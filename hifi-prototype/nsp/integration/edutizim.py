"""Boundary with EduTizim, the centre's existing CRM (NFR-05).

Students, groups, timetables and balances are owned by EduTizim and must not be
typed in again. How the two systems connect depends on the vendor (NFR-05.3), so
the module depends on the EduTizimGateway interface, never on a concrete
connection. This prototype has no access to the vendor's system, so
DemoEduTizimGateway generates realistic data instead; a production build would
add an API or export-file gateway without touching the services.
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from ..domain import Subject, WithdrawalReason


@dataclass
class StaffRecord:
    key: str
    full_name: str
    role: str  # main_teacher, support_teacher, administrator, head_specialist, director
    subject: Subject | None = None
    hired_on: date | None = None


@dataclass
class StudentRecord:
    key: str
    full_name: str
    enrolled_on: date
    parent_name: str
    parent_phone: str
    monthly_fee: int
    tuition_debt: int
    withdrawn_on: date | None = None
    withdrawal_reason: WithdrawalReason | None = None


@dataclass
class GroupRecord:
    key: str
    name: str
    subject: Subject
    level: str
    main_teacher: str
    support_teacher: str | None
    students: list[str] = field(default_factory=list)


@dataclass
class SessionRecord:
    kind: str  # lesson or support
    group: str
    room: str
    teacher: str
    starts_at: datetime
    ends_at: datetime
    tag: str = ""  # marks the sessions the demo walkthrough relies on


class EduTizimGateway(ABC):
    """Interface: everything the module needs from EduTizim."""

    @abstractmethod
    def fetch_rooms(self) -> list[str]: ...

    @abstractmethod
    def fetch_staff(self) -> list[StaffRecord]: ...

    @abstractmethod
    def fetch_students(self) -> list[StudentRecord]: ...

    @abstractmethod
    def fetch_groups(self) -> list[GroupRecord]: ...

    @abstractmethod
    def fetch_timetable(self, since: date, until: date) -> list[SessionRecord]: ...

    @abstractmethod
    def push_register(self, session_key: int, statuses: dict[str, str]) -> None:
        """Send a submitted register back so EduTizim's own dashboards stay correct."""


FIRST_NAMES_F = [
    "Aziza", "Dilfuza", "Feruza", "Gulnoza", "Kamila", "Laylo", "Madina", "Nargiza", "Nilufar",
    "Sevara", "Shahlo", "Umida", "Zilola", "Mohira", "Barno", "Iroda", "Munisa", "Sabina",
    "Charos", "Durdona", "Farangiz", "Hilola", "Jamila", "Malohat", "Ozoda", "Robiya",
]
FIRST_NAMES_M = [
    "Akmal", "Bekzod", "Doniyor", "Eldor", "Farhod", "Islom", "Javlon", "Kamron", "Mirzo",
    "Nodir", "Oybek", "Ravshan", "Sanjar", "Temur", "Ulugbek", "Xurshid", "Zafar", "Abror",
    "Bahrom", "Diyor", "Elyor", "Husan", "Jahongir", "Lochin", "Mansur", "Shoxrux",
]
SURNAMES = [
    "Abdullaev", "Ahmedov", "Boltaev", "Davletov", "Eshmatov", "Fayzullaev", "Gafurov",
    "Hamroev", "Ibragimov", "Jumaniyozov", "Kurbanov", "Latipov", "Mirzaev", "Normatov",
    "Ortiqov", "Pulatov", "Qodirov", "Rajabov", "Saidov", "Toshpulatov", "Umarov", "Vohidov",
    "Xolmatov", "Yusupov", "Zokirov", "Atajanov", "Bobojonov", "Matkarimov", "Ruzmetov", "Sobirov",
]

STAFF = [
    # key, name, role, subject
    ("t_dilnoza", "Dilnoza Karimova", "main_teacher", Subject.ENGLISH),
    ("t_jasur", "Jasur Rakhimov", "main_teacher", Subject.ENGLISH),
    ("t_malika", "Malika Yusupova", "main_teacher", Subject.ENGLISH),
    ("t_sardor", "Sardor Ismoilov", "main_teacher", Subject.CHEMISTRY),
    ("t_nigora", "Nigora Tursunova", "main_teacher", Subject.CHEMISTRY),
    ("t_aziz", "Aziz Kadirov", "main_teacher", Subject.BIOLOGY),
    ("t_shahnoza", "Shahnoza Ergasheva", "main_teacher", Subject.BIOLOGY),
    ("s_bobur", "Bobur Nazarov", "support_teacher", Subject.ENGLISH),
    ("s_kamola", "Kamola Abdullaeva", "support_teacher", Subject.ENGLISH),
    ("s_lola", "Lola Rustamova", "support_teacher", Subject.ENGLISH),
    ("s_timur", "Timur Salimov", "support_teacher", Subject.CHEMISTRY),
    ("s_zarina", "Zarina Khamidova", "support_teacher", Subject.CHEMISTRY),
    ("s_farrukh", "Farrukh Olimov", "support_teacher", Subject.CHEMISTRY),
    ("s_madina", "Madina Sharipova", "support_teacher", Subject.BIOLOGY),
    ("s_davron", "Davron Yuldashev", "support_teacher", Subject.BIOLOGY),
    ("admin", "Gulnora Askarova", "administrator", None),
    ("head", "Rustam Bekmurodov", "head_specialist", None),
    ("director", "Anvar Matyakubov", "director", None),
]

LEVELS = {
    Subject.ENGLISH: ["IELTS 5.5", "IELTS 6.0", "IELTS 6.5", "IELTS 7.0", "IELTS 5.0", "IELTS 6.0"],
    Subject.CHEMISTRY: ["DTM foundation", "DTM intensive", "DTM foundation", "DTM intensive"],
    Subject.BIOLOGY: ["DTM foundation", "DTM intensive", "DTM foundation", "DTM intensive"],
}
PREFIX = {Subject.ENGLISH: "ENG", Subject.CHEMISTRY: "CHE", Subject.BIOLOGY: "BIO"}
FEES = {Subject.ENGLISH: 450_000, Subject.CHEMISTRY: 400_000, Subject.BIOLOGY: 400_000}
SLOTS = [(9, 0), (11, 0), (14, 0), (16, 0)]
LESSON_MINUTES = 90
ROOM_COUNT = 6
DEMO_STUDENT = "Aziza Saidova"


class DemoEduTizimGateway(EduTizimGateway):
    """Stand-in for EduTizim: fictional people sized like the real centre
    (about 150 students, 15 teachers, three subjects), and a timetable built
    around `now` so that a lesson is always open for check-in during a demo."""

    def __init__(self, now: datetime, seed: int = 2026) -> None:
        self.now = now.replace(second=0, microsecond=0)
        self.random = random.Random(seed)
        self.pushed_registers: list[int] = []
        self._staff = self._build_staff()
        self._students, self._groups = self._build_students_and_groups()

    # -- gateway interface ----------------------------------------------------
    def fetch_rooms(self) -> list[str]:
        return [f"Room {n}" for n in range(1, ROOM_COUNT + 1)]

    def fetch_staff(self) -> list[StaffRecord]:
        return self._staff

    def fetch_students(self) -> list[StudentRecord]:
        return self._students

    def fetch_groups(self) -> list[GroupRecord]:
        return self._groups

    def fetch_timetable(self, since: date, until: date) -> list[SessionRecord]:
        sessions = [s for s in self._pattern_sessions(since, until) if s.starts_at.date() != self.now.date()]
        sessions += self._todays_sessions()
        return sorted(sessions, key=lambda s: s.starts_at)

    def push_register(self, session_key: int, statuses: dict[str, str]) -> None:
        self.pushed_registers.append(session_key)

    # -- generators -----------------------------------------------------------
    def _build_staff(self) -> list[StaffRecord]:
        today = self.now.date()
        staff = []
        for index, (key, name, role, subject) in enumerate(STAFF):
            hired = today - timedelta(days=300 + 137 * (index % 7))
            staff.append(StaffRecord(key, name, role, subject, hired))
        return staff

    def _name(self, used: set[str]) -> str:
        while True:
            female = self.random.random() < 0.55
            first = self.random.choice(FIRST_NAMES_F if female else FIRST_NAMES_M)
            surname = self.random.choice(SURNAMES)
            name = f"{first} {surname}{'a' if female else ''}"
            if name not in used:
                used.add(name)
                return name

    def _build_students_and_groups(self) -> tuple[list[StudentRecord], list[GroupRecord]]:
        rnd, today = self.random, self.now.date()
        month_start = today.replace(day=1)
        mains = [s for s in self._staff if s.role == "main_teacher"]
        supports = [s for s in self._staff if s.role == "support_teacher"]

        groups: list[GroupRecord] = []
        for subject in Subject:
            subject_mains = [m for m in mains if m.subject is subject]
            subject_supports = [s for s in supports if s.subject is subject]
            for number in range(len(subject_mains) * 2):
                groups.append(
                    GroupRecord(
                        key=f"{PREFIX[subject]}-{number + 1}",
                        name=f"{PREFIX[subject]}-{number + 1}",
                        subject=subject,
                        level=LEVELS[subject][number],
                        # a main teacher's two groups: n and n + (number of mains)
                        main_teacher=subject_mains[number % len(subject_mains)].key,
                        support_teacher=subject_supports[number % len(subject_supports)].key,
                    )
                )

        used = {DEMO_STUDENT}
        students: list[StudentRecord] = []
        new_this_month = {Subject.ENGLISH: 7, Subject.CHEMISTRY: 4, Subject.BIOLOGY: 3}
        for group in groups:
            size = 11 if group.key == "ENG-1" else rnd.choice([10, 10, 11, 11, 12])
            for position in range(size):
                is_demo = group.key == "ENG-1" and position == 0
                name = DEMO_STUDENT if is_demo else self._name(used)
                if not is_demo and group.key != "ENG-1" and new_this_month[group.subject] > 0 and rnd.random() < 0.25:
                    new_this_month[group.subject] -= 1
                    enrolled = month_start + timedelta(days=rnd.randint(0, max(0, (today - month_start).days)))
                else:
                    enrolled = today - timedelta(days=rnd.randint(45, 420))
                fee = FEES[group.subject]
                roll = rnd.random()
                debt = 0 if roll < 0.80 or is_demo else (fee // 2 if roll < 0.92 else fee * rnd.choice([1, 2]))
                key = f"st{len(students) + 1:03d}"
                parent = f"{rnd.choice(FIRST_NAMES_M + FIRST_NAMES_F)} {name.split()[1]}"
                phone = f"+998 9{rnd.randint(0, 9)} {rnd.randint(100, 999)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}"
                students.append(StudentRecord(key, name, enrolled, parent, phone, fee, debt))
                group.students.append(key)

        # Students who left during the last six months (kept for the dropout rate).
        reasons = list(WithdrawalReason)
        for months_ago, count in enumerate([2, 3, 2, 3, 3, 4]):
            for _ in range(count):
                group = rnd.choice([g for g in groups if g.key != "ENG-1"])
                first_of_month = month_start
                for _step in range(months_ago):
                    first_of_month = (first_of_month - timedelta(days=1)).replace(day=1)
                last_day = today if months_ago == 0 else (first_of_month + timedelta(days=27))
                span = max(0, (last_day - first_of_month).days)
                left_on = first_of_month + timedelta(days=rnd.randint(0, span))
                key = f"st{len(students) + 1:03d}"
                name = self._name(used)
                students.append(
                    StudentRecord(
                        key, name, left_on - timedelta(days=rnd.randint(60, 300)),
                        f"{rnd.choice(FIRST_NAMES_M)} {name.split()[1]}", "+998 90 000 00 00",
                        FEES[group.subject], rnd.choice([0, 0, FEES[group.subject]]),
                        withdrawn_on=left_on, withdrawal_reason=rnd.choice(reasons),
                    )
                )
                group.students.append(key)
        return students, groups

    def _pattern_sessions(self, since: date, until: date) -> list[SessionRecord]:
        """Regular weekly pattern: three lessons and one support session per group."""
        mains = [s.key for s in self._staff if s.role == "main_teacher"]
        sessions = []
        day = since
        while day <= until:
            weekday = day.weekday()  # Monday = 0; the centre is closed on Sunday
            for index, group in enumerate(self._groups):
                teacher_index = mains.index(group.main_teacher)
                first_group = [g for g in self._groups if g.main_teacher == group.main_teacher][0] is group
                lesson_days = (0, 2, 4) if first_group else (1, 3, 5)
                if weekday in lesson_days:
                    hour, minute = SLOTS[teacher_index % len(SLOTS)]
                    start = datetime(day.year, day.month, day.day, hour, minute)
                    sessions.append(
                        SessionRecord(
                            "lesson", group.key, f"Room {teacher_index % ROOM_COUNT + 1}",
                            group.main_teacher, start, start + timedelta(minutes=LESSON_MINUTES),
                        )
                    )
                if weekday == index % 6 and group.support_teacher:
                    start = datetime(day.year, day.month, day.day, 17, 45)
                    sessions.append(
                        SessionRecord(
                            "support", group.key, f"Room {index // 6 + 1}",
                            group.support_teacher, start, start + timedelta(minutes=60),
                        )
                    )
            day += timedelta(days=1)
        return sessions

    def _todays_sessions(self) -> list[SessionRecord]:
        """Today's timetable, placed around the current time for the walkthrough."""
        now = self.now
        mains = [s.key for s in self._staff if s.role == "main_teacher"]
        groups_of = {m: [g.key for g in self._groups if g.main_teacher == m] for m in mains}

        def lesson(teacher: str, which: int, room: int, from_now: int, tag: str) -> SessionRecord:
            start = now + timedelta(minutes=from_now)
            return SessionRecord(
                "lesson", groups_of[teacher][which], f"Room {room}", teacher,
                start, start + timedelta(minutes=LESSON_MINUTES), tag,
            )

        support_start = now + timedelta(minutes=110)
        return [
            lesson(mains[0], 1, 1, -200, "done"),            # finished, register submitted
            lesson(mains[0], 0, 1, -4, "live"),              # the lesson used in the demo
            lesson(mains[1], 0, 2, -190, "missing_checkout"),  # teacher forgot to check out
            lesson(mains[2], 0, 3, -35, "late_teacher"),     # teacher arrived 16 minutes late
            lesson(mains[3], 0, 4, -240, "no_register"),     # register never submitted
            lesson(mains[4], 0, 5, 120, "upcoming"),
            SessionRecord(
                "support", "ENG-1", "Room 6", "s_bobur",
                support_start, support_start + timedelta(minutes=60), "upcoming",
            ),
        ]
