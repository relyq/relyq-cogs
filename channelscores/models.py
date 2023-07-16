from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy_utc import UtcDateTime
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
    guild_id: Mapped[int] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"))
    guild: Mapped["Guild"] = relationship(back_populates="channels")
    score: Mapped[int]
    grace_count: Mapped[int]
    pinned: Mapped[bool]
    tracked: Mapped[bool]
    updated: Mapped[datetime] = mapped_column(UtcDateTime)
    added: Mapped[datetime] = mapped_column(UtcDateTime)

    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Channel):
            return self is __value
        if isinstance(__value, int):
            return self.id == __value
        raise TypeError("channel can only be compared to the same object or id")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"))
    guild: Mapped["Guild"] = relationship(back_populates="categories")
    volume: Mapped[str] = mapped_column(String(8))
    volume_pos: Mapped[int]
    threshold: Mapped[Optional[int]]
    added: Mapped[datetime] = mapped_column(UtcDateTime)

    __table_args__ = (UniqueConstraint("volume", "volume_pos", name="vol_pos"),)

    def untrack(self):
        self.tracked = False


class Guild(Base):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(primary_key=True)
    channels: Mapped[Optional[List["Channel"]]] = relationship(
        back_populates="guild", cascade="all, delete", passive_deletes=True
    )
    categories: Mapped[Optional[List["Category"]]] = relationship(
        back_populates="guild", cascade="all, delete", passive_deletes=True
    )
    enabled: Mapped[bool]
    sync: Mapped[bool]
    volume_mode: Mapped[bool]  # 0 = fixed - 1 = by score
    cooldown: Mapped[int]
    grace: Mapped[int]
    range: Mapped[int]
    log_channel: Mapped[Optional[int]]
    added: Mapped[datetime] = mapped_column(UtcDateTime)
