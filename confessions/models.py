from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy_utc import UtcDateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Confession(Base):
    __tablename__ = "confession"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"))
    message_id: Mapped[Optional[int]]
    author: Mapped[int]
    content: Mapped[str]
    added: Mapped[datetime] = mapped_column(UtcDateTime)


class BlockedUser_Guild(Base):
    __tablename__ = "blockeduser_guild"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(primary_key=True)
    blockedconfession_id: Mapped[int]
    added: Mapped[datetime] = mapped_column(UtcDateTime)


class Guild(Base):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool]
    confessions_channel: Mapped[Optional[int]]
    log_channel: Mapped[Optional[int]]
    added: Mapped[datetime] = mapped_column(UtcDateTime)
