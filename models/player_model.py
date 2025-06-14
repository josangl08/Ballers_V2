from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
if TYPE_CHECKING:
    from models.user_model import User
    from models.session_model import Session
    from models.test_model import TestResult

from .base import Base


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[int]          = mapped_column(Integer, primary_key=True)
    user_id:   Mapped[int]          = mapped_column(ForeignKey("users.user_id"), unique=True, nullable=False)
    service:   Mapped[Optional[str]] = mapped_column(String, nullable=True)
    enrolment: Mapped[int]          = mapped_column(Integer, default=0)
    notes:     Mapped[Optional[str]] = mapped_column(String, nullable=True)

    user:         Mapped["User"]                 = relationship(back_populates="player_profile")
    sessions:     Mapped[list["Session"]]        = relationship(back_populates="player")
    test_results: Mapped[list["TestResult"]]     = relationship(back_populates="player")
