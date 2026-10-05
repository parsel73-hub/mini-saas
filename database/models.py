"""Core ORM models: Survey, Question, Option, Answer.

User model lives in auth/models.py. This module is imported by
database/session.init_db() so tables are registered on Base.metadata.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Short public id used in /s/{slug} links (ТЗ: ссылки только через slug).
    slug: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    # Inactive surveys return 404 to respondents (Этап 3 requirement).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    questions: Mapped[List["Question"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", order_by="Question.position"
    )
    answers: Mapped[List["Answer"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # "single" — один вариант, "multiple" — несколько, "text" — свободный ответ.
    type: Mapped[str] = mapped_column(String(10), default="single", nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    survey: Mapped["Survey"] = relationship(back_populates="questions")
    options: Mapped[List["Option"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="Option.position"
    )


class Option(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    question: Mapped["Question"] = relationship(back_populates="options")


class Answer(Base):
    """Один ответ респондента на один вопрос (прямое требование ТЗ)."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    # Для single/multiple — ссылка на выбранный вариант; для text — NULL.
    option_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("options.id", ondelete="SET NULL"), nullable=True
    )
    # Свободный текстовый ответ (для type="text").
    text_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Идентификатор сессии браузера, чтобы группировать ответы одного респондента.
    respondent_session: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    survey: Mapped["Survey"] = relationship(back_populates="answers")
