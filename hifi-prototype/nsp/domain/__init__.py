"""Domain layer: the classes shown in the UML class diagrams."""
from .attendance import CheckIn, LessonRegister, RegisterEntry, WorkSession
from .base import Base
from .enums import (
    AlertStatus,
    AttendanceStatus,
    CheckInMethod,
    CheckInStatus,
    CircumstanceKind,
    RiskLevel,
    Subject,
    WithdrawalReason,
    WorkSessionStatus,
)
from .people import (
    Administrator,
    Director,
    HeadSpecialist,
    MainTeacher,
    Student,
    SupportTeacher,
    Teacher,
    User,
)
from .performance import (
    Achievement,
    Feedback,
    IndicatorScore,
    KpiSnapshot,
    KpiWeight,
    KpiWeightSet,
    MonthlyRating,
    TestResult,
)
from .retention import (
    AppSetting,
    Circumstance,
    FollowUpAction,
    MarketingSpend,
    Notification,
    RiskAlert,
    RiskScore,
    Withdrawal,
)
from .scheduling import Group, Lesson, Room, ScheduledSession, SupportSession, group_students

__all__ = [name for name in dir() if not name.startswith("_")]
