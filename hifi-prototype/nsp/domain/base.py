"""Shared declarative base for every domain class."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root of the domain model. Every entity below is a persistent class."""
