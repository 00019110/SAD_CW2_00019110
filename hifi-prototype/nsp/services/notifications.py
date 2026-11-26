"""In-app notifications for alerts, follow-up tasks and attendance exceptions."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..data import NotificationRepository, UserRepository
from ..domain import Notification, User
from .clock import Clock


class NotificationService:
    def __init__(self, db: Session, clock: Clock) -> None:
        self.db = db
        self.clock = clock
        self.users = UserRepository(db)
        self.repository = NotificationRepository(db)

    def notify(self, recipient: User, message: str, link: str | None = None) -> Notification:
        notification = Notification(
            recipient_id=recipient.id, message=message, link=link, created_at=self.clock.now()
        )
        self.db.add(notification)
        return notification

    def notify_roles(self, role_classes: list[type[User]], message: str, link: str | None = None) -> int:
        """Send the same message to everyone holding one of the given roles."""
        sent = 0
        for role_class in role_classes:
            for user in self.users.by_role(role_class):
                self.notify(user, message, link)
                sent += 1
        return sent

    def inbox(self, user: User) -> list[Notification]:
        return self.repository.for_user(user.id)

    def unread_count(self, user: User) -> int:
        return self.repository.unread_count(user.id)

    def mark_all_read(self, user: User) -> None:
        for notification in self.repository.for_user(user.id, limit=100):
            notification.read = True
