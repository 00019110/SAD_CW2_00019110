"""Enumerations used across the domain model."""
from enum import Enum


class Subject(Enum):
    CHEMISTRY = "Chemistry"
    BIOLOGY = "Biology"
    ENGLISH = "English"


class CheckInMethod(Enum):
    """How an attendance record was captured. FACE_ID is reserved (NFR-05.5)."""

    QR = "QR"
    MANUAL = "Manual"
    FACE_ID = "Face ID"


class CheckInStatus(Enum):
    ON_TIME = "On time"
    LATE = "Late"


class WorkSessionStatus(Enum):
    OPEN = "Open"
    CLOSED = "Closed"
    LEFT_EARLY = "Left early"
    MISSING_CHECKOUT = "Missing check-out"


class AttendanceStatus(Enum):
    NOT_SCANNED = "Not scanned"
    PRESENT = "Present"
    LATE = "Late"
    ABSENT = "Absent"
    EXCUSED = "Absent – excused"


class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    NOT_ENOUGH_DATA = "Not enough data"


class AlertStatus(Enum):
    OPEN = "Open"
    IN_PROGRESS = "In progress"
    RESOLVED = "Resolved"
    CLOSED_WITHDRAWN = "Closed – withdrawn"


class WithdrawalReason(Enum):
    FINANCIAL = "Financial"
    MOVED = "Moved"
    CHANGED_COURSE = "Changed course"
    NOT_SATISFIED = "Not satisfied"
    OTHER = "Other"


class CircumstanceKind(Enum):
    FINANCIAL = "Financial"
    SOCIAL = "Social"
