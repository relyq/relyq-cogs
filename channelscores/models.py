from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Channel(Base):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int]
    score: Mapped[int]
    grace_count: Mapped[int]
    pinned: Mapped[bool]
    tracked: Mapped[bool]
    updated: Mapped[datetime]
    added: Mapped[datetime]


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int]
    volume: Mapped[str] = mapped_column(String(8))
    volume_pos: Mapped[int]
    added: Mapped[datetime]

    __table_args__ = (UniqueConstraint("volume", "volume_pos", name="vol_pos"),)

    def untrack(self):
        self.tracked = False


class Guild(Base):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool]
    sync: Mapped[bool]
    cooldown: Mapped[int]
    grace: Mapped[int]
    range: Mapped[int]
    log_channel: Mapped[Optional[int]]
    added: Mapped[datetime]
