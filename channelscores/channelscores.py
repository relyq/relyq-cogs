import time
from datetime import datetime, timezone
import math
import asyncio
from collections import OrderedDict
from copy import copy
from typing import Optional
from hashlib import shake_128

from operator import attrgetter

import discord

from discord.ext import tasks

from redbot.core import commands, Config, data_manager
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.predicates import MessagePredicate

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session
from channelscores.models import *


class ChannelScore:
    def __init__(
        self,
        channel: discord.TextChannel,
        rank: Optional[int] = None,
        distance: Optional[int] = None,
        score: Optional[int] = None,
    ):
        self.text_channel = channel
        self.rank = rank
        self.distance = distance
        self.score = score


class Volume:
    def __init__(self, id: int, previous: int = None, next: int = None):
        self.id = id
        self.previous = previous
        self.next = next

    def __eq__(self, other):
        if isinstance(other, Volume):
            return self is other
        if isinstance(other, int) or isinstance(other, str):
            return self.id == int(other)
        raise TypeError(
            "volume can only be compared to the same object or id (int, str)"
        )


async def lis_sort(
    channels: List[ChannelScore], channels_sorted: List[Channel], first_pos
):
    untracked = []
    for pos, c in enumerate(channels):
        c.rank = channels_sorted.index(c.text_channel.id)
        c.distance = pos - c.rank

    for c in untracked:
        channels.remove(c)

    chanscore = sorted(channels, key=lambda x: abs(x.distance), reverse=True)[0]

    if chanscore.distance == 0:
        return

    i = 0

    while True:  # python being python
        channels.remove(chanscore)
        channels.insert(chanscore.rank, chanscore)

        move_to = first_pos + chanscore.rank
        if chanscore.text_channel.position < move_to:
            move_to += 1

        await chanscore.text_channel.edit(
            position=move_to,
            reason="channel scores",
        )

        await asyncio.sleep(1)

        for pos, c in enumerate(channels):
            c.rank = channels_sorted.index(c.text_channel.id)
            c.distance = pos - c.rank

        chanscore = sorted(channels, key=lambda x: abs(x.distance), reverse=True)[0]

        # prevents infinite looping
        if i > len(channels_sorted):
            raise Exception("LIS sort loops exceeded list length")
        i += 1

        if chanscore.distance == 0:
            break


class CScores(commands.Cog):
    """channel scores"""

    __author__ = "relyq"

    __global_grace__ = 60

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(
            self, identifier=1797464170, force_registration=True
        )

        self.DEFAULT_COOLDOWN = 30
        self.DEFAULT_GRACE = 60
        self.DEFAULT_RANGE = 1

        default_guild = {
            "log_channel": None,
            "enabled": False,
            "sync": False,
            "categories": {},
            "scoreboard": {},
            "cooldown": 30,
            "grace": 60,
            "range": 1,
        }

        self.config.register_guild(**default_guild)

        self.data_path = data_manager.cog_data_path(self) / "scores.db"

        self.engine = create_engine(f"sqlite://{self.data_path}", echo=True)
        Base.metadata.create_all(self.engine)

        self.main_loop.start()

    def cog_unload(self):
        self.main_loop.cancel()

    @staticmethod
    def init_guild(self, session: Session, guild: discord.Guild):
        """initialize guild on sqlite"""
        stmt = select(Guild).where(Guild.id == guild.id)
        if not session.scalars(stmt).first():
            session.add(
                Guild(
                    id=guild.id,
                    enabled=False,
                    sync=False,
                    cooldown=self.DEFAULT_COOLDOWN,
                    grace=self.DEFAULT_GRACE,
                    range=self.DEFAULT_RANGE,
                    log_channel=None,
                    added=datetime.now(timezone.utc),
                )
            )

    @staticmethod
    def update_guild(
        self,
        guild: discord.Guild,
        enabled: Optional[bool] = None,
        sync: Optional[bool] = None,
        cooldown: Optional[int] = None,
        grace: Optional[int] = None,
        range: Optional[int] = None,
        log_channel: Optional[discord.TextChannel] = None,
    ):
        """init & update guild settings"""
        with Session(self.engine) as session:
            self.init_guild(self, session, guild)
            stmt = select(Guild).where(Guild.id == guild.id)
            guild = session.scalars(stmt).first()
            if enabled is not None:
                guild.enabled = enabled
            if sync is not None:
                guild.sync = sync
            if cooldown is not None:
                guild.cooldown = cooldown
            if grace is not None:
                guild.grace = grace
            if range is not None:
                guild.range = range
            if log_channel is not None:
                guild.log_channel = log_channel.id

            session.commit()

    @staticmethod
    async def sync_channels(self, guild: discord.Guild):
        with Session(self.engine) as session:
            stmt = select(Category).where(Category.guild_id == guild.id)
            categories = session.scalars(stmt).all()

        for category in categories:
            # get the first position
            try:
                category = guild.get_channel(category.id)
                category.text_channels.sort(key=lambda x: x.position)
                first_channel = category.text_channels[0]
            except IndexError:
                continue
            first_pos = first_channel.position

            with Session(self.engine) as session:
                # get scoreboard
                stmt = (
                    select(Channel)
                    .where(Channel.id.in_([c.id for c in category.text_channels]))
                    .order_by(Channel.score.desc(), Channel.updated.desc())
                )

                # without pins
                stmt = stmt.where(Channel.pinned == False)
                scoreboard = session.scalars(stmt).all()
                # get pins
                stmt = stmt.where(Channel.pinned == True)
                pins = session.scalars(stmt).all()

            # sort pinned
            for p in pins:
                scoreboard.insert(guild.get_channel(p.id).position - first_pos, p)

            for c in scoreboard:
                c.text_channel = guild.get_channel(c.id)

            # cast to ChannelScore
            channels = []
            for c in category.text_channels:
                channels.append(
                    ChannelScore(
                        c,
                    )
                )

            # finally sync sort to discord
            await lis_sort(channels, scoreboard, first_pos)

    @staticmethod
    async def add_points(self, channel: discord.TextChannel):
        async with self.config.guild(channel.guild).scoreboard() as scoreboard:
            cooldown_sec = await self.config.guild(channel.guild).cooldown() * 60

            since_update = time.time() - scoreboard[str(channel.id)]["updated"]

            # check cooldown - if grace is over 0 update doesnt matter
            # if update is low & grace 0 = recent message
            # if update is low & grace > 0 = recently lost points
            if scoreboard[str(channel.id)]["grace_count"] == 0:
                if since_update <= cooldown_sec:
                    return

            points_max = await self.config.guild(channel.guild).range() * len(
                scoreboard
            )

            # add points & update last message time
            if scoreboard[str(channel.id)]["score"] < points_max:
                scoreboard[str(channel.id)]["score"] += 1
            scoreboard[str(channel.id)]["updated"] = time.time()
            scoreboard[str(channel.id)]["grace_count"] = 0

    @staticmethod
    async def remove_points(self, channel: discord.TextChannel):
        async with self.config.guild(channel.guild).scoreboard() as scoreboard:
            if scoreboard[str(channel.id)]["score"] > 0:
                scoreboard[str(channel.id)]["score"] -= (
                    1 if scoreboard[str(channel.id)]["grace_count"] else 0
                )
                if await self.config.guild(channel.guild).sync():
                    await self.check_scores(
                        self,
                        channel,
                    )

            scoreboard[str(channel.id)]["updated"] = time.time()
            scoreboard[str(channel.id)]["grace_count"] += 1

    @commands.Cog.listener("on_guild_channel_create")
    async def on_channel_create(self, channel: discord.abc.GuildChannel):
        guild = channel.guild
        if type(channel) is not discord.TextChannel:
            return

        with Session(self.engine) as session:
            stmt = select(Category).where(Category.id == channel.category.id)

            if not session.scalars(stmt).first():
                return

            self._add_textchannel(self, session, channel)
            session.commit()

            # i could load guild from the child channel
            stmt = select(Guild).where(Guild.id == guild.id)
            guild = session.scalars(stmt).first()
            try:
                log_channel = guild.get_channel(guild.log_channel)
            except AttributeError:
                return

            # check score
            if guild.sync:
                await self.sync_channels(self, guild)

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title="scores - channel tracked",
                    timestamp=datetime.utcnow(),
                    description=channel.mention,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @commands.Cog.listener("on_guild_channel_delete")
    async def on_channel_delete(self, channel: discord.abc.GuildChannel):
        guild = channel.guild

        if (
            type(channel) is not discord.TextChannel
            and type(channel) is not discord.CategoryChannel
        ):
            return

        with Session(self.engine) as session:
            if type(channel) is discord.CategoryChannel:
                stmt = select(Category).where(Category.id == channel.id)

            if type(channel) is discord.TextChannel:
                stmt = select(Channel).where(Channel.id == channel.id)

            session.delete(session.scalars(stmt).first())
            session.commit()

            # i could load guild from the child channel
            stmt = select(Guild).where(Guild.id == guild.id)
            try:
                log_channel = guild.get_channel(
                    session.scalars(stmt).first().log_channel
                )
            except AttributeError:
                return

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title="scores - channels removed",
                    timestamp=datetime.utcnow(),
                    description=channel.name,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @commands.Cog.listener("on_guild_channel_update")
    async def on_channel_update(
        self, before: discord.TextChannel, after: discord.abc.GuildChannel
    ):
        guild = after.guild
        if type(after) is not discord.TextChannel:
            return

        with Session(self.engine) as session:
            # in tracked category
            stmt = select(Category).where(Category.id == before.category.id)
            if session.scalars(stmt).first():
                return

            # in untracked category
            stmt = select(Category).where(Category.id == after.category.id)
            if not session.scalars(stmt).first():
                return

            # text channel moved to a tracked category - lets try to track it
            self._add_textchannel(self, session, after)
            session.commit()

            # i could load guild from the child channel
            stmt = select(Guild).where(Guild.id == guild.id)
            guild = session.scalars(stmt).first()
            try:
                log_channel = guild.get_channel(guild.log_channel)
            except AttributeError:
                return

            # check score
            if guild.sync:
                await self.sync_channels(self, guild)

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title="scores - channel tracked after move",
                    timestamp=datetime.utcnow(),
                    description=after.mention,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    # points win logic
    @commands.Cog.listener("on_message")
    async def on_message_listener(self, message: discord.Message):
        with Session(self.engine) as session:
            stmt = select(Guild).where(Guild.id == message.guild.id)
            guild = session.scalars(stmt).first()
            if not guild:
                return
            if guild.enabled is False:
                return
            if message.author.id is message.guild.me.id:
                return

            stmt = select(Channel).where(Channel.id == message.channel.id)

            channel = session.scalars(stmt).first()

            if not channel:
                return

            ## add points
            if channel.tracked:
                cooldown_sec = guild.cooldown * 60

                since_update = datetime.now(timezone.utc) - channel.updated.astimezone(
                    timezone.utc
                )

                # check cooldown - if grace is over 0 update doesnt matter
                # if update is low & grace 0 = recent message
                # if update is low & grace > 0 = recently lost points
                if channel.grace_count == 0:
                    if abs(since_update.total_seconds()) <= cooldown_sec:
                        return

                total_channels = (
                    session.query(Channel).where(Channel.guild_id == guild.id).count()
                )

                points_max = guild.range * total_channels

                # add points & update last message time
                if channel.score < points_max:
                    channel.score += 1
                channel.updated = datetime.now(timezone.utc)
                channel.grace_count = 0

                session.commit()

                # check score
                if guild.sync:
                    await self.sync_channels(self, message.guild)

    # points lose logic
    @tasks.loop(minutes=__global_grace__)
    async def main_loop(self):
        with Session(self.engine) as session:
            stmt = select(Guild)
            guilds = session.scalars(stmt).all()
            for g in guilds:
                if not g.enabled:
                    return

                stmt = select(Channel).where(Channel.guild_id == g.id)
                channels = session.scalars(stmt).all()

                for c in channels:
                    if not c.tracked:
                        return

                    since_update = datetime.now(timezone.utc) - c.updated.astimezone(
                        timezone.utc
                    )

                    if (
                        abs(int(since_update.total_seconds())) / 60 >= g.grace
                    ):  # grace ended
                        if c.score > 0:
                            c.score -= 1 if c.grace_count else 0
                            if g.sync:
                                await self.sync_channels(
                                    self,
                                    self.bot.get_guild(g.id),
                                )

                        c.updated = datetime.now(timezone.utc)
                        c.grace_count += 1

                        session.commit()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.group(
        name="channelscores", aliases=["cscores", "cscore", "scores", "score"]
    )
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def channelscores(self, ctx: commands.Context):
        """channel scores"""

    @staticmethod
    async def confirm_message(ctx: commands.Context) -> bool:
        """
        ask for confirmation
        """
        response = await ctx.bot.wait_for(
            "message", check=MessagePredicate.same_context(ctx)
        )

        if response.content.lower().startswith("y"):
            return True
        else:
            return False

    @staticmethod
    async def log_to_channel(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
    ):
        with Session(self.engine) as session:
            stmt = select(Guild).where(Guild.id == ctx.guild.id)
            try:
                log_channel = ctx.guild.get_channel(
                    session.scalars(stmt).first().log_channel
                )
            except AttributeError:
                return

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=title,
                    color=await ctx.embed_color(),
                    timestamp=datetime.utcnow(),
                    description=description,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @staticmethod
    async def log_tracked(self, ctx, categories, text_channels):
        await self.log_to_channel(
            self,
            ctx,
            title="scores - channels tracked",
            description=f"""
            categories: {humanize_list([cat.name for cat in categories]) if categories else ''}
            channels: {humanize_list([c.mention for c in text_channels]) if text_channels else ''}
            added by {ctx.author.mention}""",
        )

    @staticmethod
    async def log_linked(self, ctx, volume):
        arrow = " -> "
        vnames = []
        [vnames.append(cat.name) for cat in volume]
        await self.log_to_channel(
            self,
            ctx,
            title="scores - categories linked",
            description=f"""
            new logical volume created
            {arrow.join(vnames)}
            by {ctx.author.mention}""",
        )

    @staticmethod
    async def log_unlinked(self, ctx, volumes):
        arrow = " -/> "
        nl = "\n"
        await self.log_to_channel(
            self,
            ctx,
            title="scores - categories unlinked",
            description=f"""
            logical volume split
            {nl.join([[arrow.join(str(vid)) for vid in vol] for vol in volumes])}
            by {ctx.author.mention}""",
        )

    @staticmethod
    async def log_removed(self, ctx, categories, text_channels):
        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - channels removed",
            description=f"""
            categories: {humanize_list([cat.name for cat in categories]) if categories else ''}
            channels: {humanize_list([c.mention for c in text_channels]) if text_channels else ''}
            removed by {ctx.author.mention}""",
        )

    @staticmethod
    def sort_catchan(self, catchan, recursive: bool) -> dict:
        channels = {"categories": [], "text_channels": []}

        for c in catchan:
            if type(c) is discord.TextChannel:
                if c not in channels["text_channels"]:
                    channels["text_channels"].append(c)

            if type(c) is discord.CategoryChannel:
                channels["categories"].append(c)
                if recursive:
                    for tc in c.text_channels:
                        if tc not in channels["text_channels"]:
                            channels["text_channels"].append(tc)
        return channels

    @staticmethod
    def _add_textchannel(self, session, channel: discord.TextChannel):
        stmt = select(Channel).where(Channel.id == channel.id)
        if not session.scalars(stmt).first():
            now = datetime.now(timezone.utc)
            session.add(
                Channel(
                    id=channel.id,
                    guild_id=channel.guild.id,
                    score=0,
                    grace_count=0,
                    pinned=False,
                    tracked=True,
                    updated=now,
                    added=now,
                )
            )

    @staticmethod
    def get_volumes(self, categories: dict) -> list:
        volumes = []

        cats = []
        [
            cats.append(
                Volume(
                    int(c),
                    categories[str(c)]["previous"],
                    categories[str(c)]["next"],
                )
            )
            for c in categories
        ]

        while True:
            volume = []
            volume.append(cats[-1])
            print(f"popped {volume[-1]}")
            while True:
                nxt = volume[-1].next
                if nxt:
                    volume.append(cats.pop(nxt))
                else:
                    break
            while True:
                prev = volume[0].previous
                if nxt:
                    volume.insert(0, cats.pop(prev))
                else:
                    break

            volumes.append(volume)

            if not len(categories):
                break

        return volumes

    ### actions that you perform on channels

    @channelscores.command(name="track")
    async def track_channels(
        self, ctx: commands.Context, *channels: discord.abc.GuildChannel, recursive=True
    ):
        """track channels and categories"""

        if not channels:
            return await ctx.send("no channels or categories to add")

        sorted_channels = self.sort_catchan(self, channels, recursive=recursive)

        with Session(self.engine) as session:
            now = datetime.now(timezone.utc)

            # add untracked categories
            categories = [
                Category(
                    id=category.id,
                    guild_id=ctx.guild.id,
                    volume=shake_128(bytes(str(category.id), "utf-8")).hexdigest(8),
                    volume_pos=0,
                    added=now,
                )
                for category in sorted_channels["categories"]
            ]

            # get and exclude existing categories
            stmt = select(Category).where(
                Category.id.in_([cat.id for cat in sorted_channels["categories"]])
            )

            for e in session.scalars(stmt):
                for cat in categories:
                    if cat.id == e.id:
                        categories.remove(cat)

            session.add_all(categories)

            stmt = select(Channel).where(
                Channel.id.in_([chan.id for chan in sorted_channels["text_channels"]])
            )

            # add untracked channels
            channels = [
                Channel(
                    id=channel.id,
                    guild_id=ctx.guild.id,
                    score=0,
                    grace_count=0,
                    pinned=False,
                    tracked=True,
                    updated=now,
                    added=now,
                )
                for channel in sorted_channels["text_channels"]
            ]

            existing = session.scalars(stmt)

            # set existing categories to tracked
            for e in existing:
                for c in channels:
                    if c.id == e.id:
                        channels.remove(c)
                e.tracked = True

            session.add_all(channels)

            session.commit()

        await self.log_tracked(
            self, ctx, sorted_channels["categories"], sorted_channels["text_channels"]
        )

        # check score
        if await self.config.guild(ctx.guild).sync():
            await self.sync_channels(self, ctx.guild)

        return await ctx.tick()

    @channelscores.command(name="untrack")
    async def untrack_channels(
        self,
        ctx: commands.Context,
        *channels: discord.abc.GuildChannel,
        recursive=False,
    ):
        """untrack channels and categories"""

        sorted_channels = self.sort_catchan(self, channels, recursive=recursive)

        with Session(self.engine) as session:
            stmt = select(Category).where(
                Category.id.in_([cat.id for cat in sorted_channels["categories"]])
            )

            [session.delete(category) for category in session.scalars(stmt)]

            stmt = select(Channel).where(
                Channel.id.in_([chan.id for chan in sorted_channels["text_channels"]])
            )
            # set all channels to untracked
            for channel in session.scalars(stmt):
                channel.tracked = False

            session.commit()

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - channels untracked",
            description=f"""
            categories: {humanize_list([cat.name for cat in sorted_channels["categories"]]) if sorted_channels["categories"] else ''}
            channels: {humanize_list([c.mention for c in sorted_channels["text_channels"]]) if sorted_channels["text_channels"] else ''}
            added by {ctx.author.mention}""",
        )

        return await ctx.tick()

    @channelscores.command(name="reset")
    async def reset_channels(
        self,
        ctx: commands.Context,
        *channels: discord.abc.GuildChannel,
        recursive=True,
    ):
        """reset channel scores"""
        if not channels:
            return await ctx.send("no channels or categories to reset")

        await ctx.send(
            "are you sure you want to reset the scores for these channels and categories?"
        )

        cont = await self.confirm_message(ctx)

        if not cont:
            return await ctx.send("cancelled")

        sorted_channels = self.sort_catchan(self, channels, recursive=recursive)

        with Session(self.engine) as session:
            stmt = select(Channel).where(
                Channel.id.in_([chan.id for chan in sorted_channels["text_channels"]])
            )

            for channel in session.scalars(stmt):
                channel.score = 0
                channel.grace_count = 0
                channel.updated = datetime.now(timezone.utc)

            session.commit()

        await self.log_to_channel(
            self,
            ctx,
            title="scores - channels score reset",
            description=f"""
            categories: {humanize_list([cat.name for cat in sorted_channels["categories"]]) if sorted_channels["categories"] else ''}
            channels: {humanize_list([c.mention for c in sorted_channels["text_channels"]]) if sorted_channels["text_channels"] else ''}
            reset by {ctx.author.mention}""",
        )

        await ctx.tick()

        # check score
        if await self.config.guild(ctx.guild).sync():
            return await self.sync_channels(self, ctx.guild)

    @channelscores.command(name="forget")
    async def remove_channels(
        self,
        ctx: commands.Context,
        *channels: discord.abc.GuildChannel,
        recursive=False,
    ):
        """remove channels from the database"""

        if not channels:
            return await ctx.send("no channels or categories to remove")

        await ctx.send(
            "are you sure you want to remove these channels and categories from the scoreboard?"
        )

        cont = await self.confirm_message(ctx)

        if not cont:
            return await ctx.send("cancelled")

        sorted_channels = self.sort_catchan(self, channels, recursive=recursive)

        with Session(self.engine) as session:
            stmt = select(Category).where(
                Category.id.in_([cat.id for cat in sorted_channels["categories"]])
            )

            [session.delete(category) for category in session.scalars(stmt)]

            stmt = select(Channel).where(
                Channel.id.in_([chan.id for chan in sorted_channels["text_channels"]])
            )

            [session.delete(channel) for channel in session.scalars(stmt)]

            session.commit()

        await self.log_removed(
            self, ctx, sorted_channels["categories"], sorted_channels["text_channels"]
        )

        return await ctx.tick()

    @channelscores.command(name="pin")
    async def pin_channels(self, ctx: commands.Context, *channels: discord.TextChannel):
        """pin channels so they dont move"""

        with Session(self.engine) as session:
            stmt = select(Channel).where(Channel.id.in_([chan.id for chan in channels]))

            for channel in session.scalars(stmt):
                channel.pinned = True

            session.commit()

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - channels pinned",
            description=f"""
              {humanize_list([c.mention for c in channels])} pinned by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @channelscores.command(name="unpin")
    async def unpin_channels(
        self, ctx: commands.Context, *channels: discord.TextChannel
    ):
        """unpin channels so they move again"""

        with Session(self.engine) as session:
            stmt = select(Channel).where(Channel.id.in_([chan.id for chan in channels]))

            for channel in session.scalars(stmt):
                channel.pinned = False

            session.commit()

        await self.log_to_channel(
            self,
            ctx,
            title=f"channels unpinned - scoreboard",
            description=f"""
              {humanize_list([c.mention for c in channels])} unpinned by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @channelscores.command(name="link")
    async def link_categories(
        self, ctx: commands.Context, *volumes: discord.CategoryChannel
    ):
        """link categories so they act as one logical volume"""
        if len(volumes) < 2:
            return ctx.send("no categories to link")

        async with self.config.guild(ctx.guild).categories() as categories:
            for i, cat in enumerate(volumes):
                if i != 0:
                    categories[str(cat.id)]["previous"] = volumes[i - 1].id
                if i != len(volumes) - 1:
                    categories[str(cat.id)]["next"] = volumes[i + 1].id

        await self.log_linked(self, ctx, volumes)

        return await ctx.tick()

    @channelscores.command(name="unlink")
    async def unlink_categories(
        self, ctx: commands.Context, *cats: discord.CategoryChannel
    ):
        """break links to split categories"""
        if not cats:
            return ctx.send("no categories to unlink")

        split_vols = []

        async with self.config.guild(ctx.guild).categories() as categories:
            volumes_ids = self.get_volumes(self, copy(categories))
            for cat in cats:
                for vol in volumes_ids:
                    if cat.id in vol:
                        split_vols.append(vol)

                        prev = categories[str(cat.id)]["previous"]
                        nxt = categories[str(cat.id)]["next"]

                        if prev:
                            categories[str(prev)]["next"] = None
                        if nxt:
                            categories[str(nxt)]["previous"] = None

                        categories[str(cat.id)]["previous"] = None
                        categories[str(cat.id)]["next"] = None

        await self.log_unlinked(self, ctx, split_vols)

        return await ctx.tick()

    @channelscores.command(name="resync")
    async def sync_trigger(self, ctx: commands.Context):
        """triggers a resync"""
        with Session(self.engine) as session:
            stmt = select(Guild).where(Guild.id == ctx.guild.id)
            guild = session.scalars(stmt).first()
            if not guild:
                return
            if not guild.sync:
                return await ctx.send("sync is not enabled")

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - sync triggered",
            description=f"""
              channel sync triggered by {ctx.author.mention}
            """,
        )

        await ctx.tick()

        return await self.sync_channels(self, ctx.guild)

    ### server settings

    @channelscores.group(name="settings", aliases=["set", "s"])
    async def settings(self, ctx):
        """server settings"""

    @settings.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set channel to send logs to"""
        self.update_guild(self, guild=ctx.guild, log_channel=log_channel)

        await log_channel.send(
            embed=discord.Embed(
                title="scores - channel scores log channel set",
                color=await ctx.embed_color(),
                description=f"""
            {log_channel.mention} set as log channel by {ctx.author.mention}
            """,
            )
        )

        return await ctx.tick()

    @settings.command(name="cooldown")
    async def set_cooldown(self, ctx: commands.Context, minutes: int):
        """set on-message points cooldown in minutes - def: 30"""
        if minutes < 1 or minutes > 10000:
            await ctx.send(
                "cooldown can't be lower than 1 minute or higher than 10000 minutes"
            )
            return

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - cooldown changed",
            description=f"""
              cooldown changed to {minutes} minutes by {ctx.author.mention}
            """,
        )

        self.update_guild(self, ctx.guild, cooldown=minutes)

        return await ctx.tick()

    @settings.command(name="grace")
    async def set_grace(self, ctx: commands.Context, minutes: int):
        """set grace period in minutes - def: 60"""
        if minutes < self.__global_grace__ or minutes > 10000:
            await ctx.send(
                f"grace can't be set lower than {self.__global_grace__} minutes or greater than 10000 minutes currently"
            )
            return

        if minutes % self.__global_grace__ != 0:
            await ctx.send(
                f"grace has been set. i suggest setting it to multiples of {self.__global_grace__} for greater accuracy"
            )

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - grace changed",
            description=f"""
            grace changed to {minutes} minutes by {ctx.author.mention}
            """,
        )

        self.update_guild(self, ctx.guild, grace=minutes)

        return await ctx.tick()

    @settings.command(name="enable", aliases=["enabled"])
    async def enable(self, ctx: commands.Context):
        """enable channel scores"""
        self.update_guild(self, ctx.guild, enabled=True)

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - enabled",
            description=f"""
              scores enabled by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @settings.command(name="disable", aliases=["disabled"])
    async def disable(self, ctx: commands.Context):
        """disable channel scores"""
        self.update_guild(self, ctx.guild, enabled=False)

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - disabled",
            description=f"""
              scores disabled by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @settings.command(name="range")
    async def set_range(self, ctx: commands.Context, new_range: int):
        """set min-max points according to total number of channels. 'range 2' with 10 channels results in 0 - 20 range - def: 1"""
        if new_range < 1 or new_range > 5:
            await ctx.send("range can only be set from 1 to 5 currently")
            return

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - range changed",
            description=f"""
              range changed to {new_range} by {ctx.author.mention}
            """,
        )

        self.update_guild(self, ctx.guild, range=new_range)

        return await ctx.tick()

    @settings.group(name="sync")
    async def sync(self, ctx):
        """disable or enable channel sync to scoreboard"""

    @sync.command(name="enable", aliases=["enabled"])
    async def sync_enable(self, ctx: commands.Context):
        """enable channel sync to scoreboard"""

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - sync enabled",
            description=f"""
              channel position sync enabled by {ctx.author.mention}
            """,
        )

        self.update_guild(self, ctx.guild, sync=True)

        await ctx.tick()

        return await self.sync_channels(self, ctx.guild)

    @sync.command(name="disable", aliases=["disabled"])
    async def sync_disable(self, ctx: commands.Context):
        """disable channel sync to scoreboard"""

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - sync disabled",
            description=f"""
              channel position sync disabled by {ctx.author.mention}
            """,
        )

        self.update_guild(self, ctx.guild, sync=False)

        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @settings.command(name="view")
    async def view_settings(self, ctx: commands.Context):
        """view the current channel scores settings"""

        with Session(self.engine) as session:
            stmt = select(Guild).where(Guild.id == ctx.guild.id)
            settings = session.scalars(stmt).first()

            stmt = select(Category).where(Category.guild_id == ctx.guild.id)
            categories = session.scalars(stmt).all()

            total_channels = (
                session.query(Channel).where(Channel.guild_id == ctx.guild.id).count()
            )

            untracked_count = (
                session.query(Channel)
                .where(Channel.guild_id == ctx.guild.id)
                .where(Channel.tracked == False)
                .count()
            )

        return await ctx.send(
            embed=discord.Embed(
                title="channel scores settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {settings.enabled}
            **sync**: {"enabled" if settings.sync else "disabled"}
            **log channel:** {"None" if settings.log_channel is None else ctx.guild.get_channel(settings.log_channel).mention}
            **cooldown:** {settings.cooldown} minutes
            **grace period:** {settings.grace} minutes
            **range:** {settings.range} / 0 to {settings.range * total_channels} points
            **categories:** {
              humanize_list(
                [f"{ctx.guild.get_channel(cat.id).name}" for cat in categories]
              )
              if categories else ""}
            **channels:** {total_channels} - {untracked_count} not tracked
            """,
            )
        )

    # public commands

    @commands.command(name="scoreboard", aliases=["board", "top"])
    async def view_scoreboard(self, ctx: commands.Context, page=1):
        """view the scoreboard"""
        if page < 1:
            return

        page_size = 15

        max_pages_msg = None

        with Session(self.engine) as session:
            total_channels = (
                session.query(Channel).where(Channel.guild_id == ctx.guild.id).count()
            )

            total_pages = math.ceil(total_channels / page_size)

            if page > total_pages:
                max_pages_msg = (
                    f"there are only {total_pages} pages - showing last page"
                )

                page = total_pages

            offset = (page - 1) * page_size

            stmt = (
                select(Channel)
                .where(Channel.guild_id == ctx.guild.id)
                .offset(offset)
                .limit(page_size)
                .order_by(Channel.score.desc(), Channel.updated.desc())
            )

            scoreboard = session.scalars(stmt).all()

        scores = []

        for c in scoreboard:
            c.text_channel = ctx.guild.get_channel(c.id)

        scores = [
            f"{index + 1}. {c.text_channel.mention} - {c.score} points {'*' if c.pinned else ''}"
            for index, c in enumerate(scoreboard)
        ]

        scores = scores[offset : offset + page_size]

        nl = "\n"
        top = f"{nl.join(scores)}"

        return await ctx.send(
            content=max_pages_msg,
            embed=discord.Embed(
                title=f"{ctx.guild.name} scoreboard - {offset + 1}-{(offset + page_size) if (offset + page_size) < total_channels else total_channels} of {total_channels}",
                color=await ctx.embed_color(),
                description=top,
            ).set_footer(
                text=f"page {page} of {total_pages} - top {page + 1} to go to page {page + 1}"
            ),
        )

    @commands.command(name="rank")
    async def view_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """view channel score"""
        mention = None

        if not channel:
            channel = ctx.channel

        with Session(self.engine) as session:
            stmt = select(Channel).where(Channel.id == channel.id)
            c = session.scalars(stmt).first()
            mention = channel.mention

            if not c:
                return await ctx.send("this channel is not part of the scoreboard")

        first_pos = channel.category.text_channels[0].position
        rank = channel.position - first_pos + 1

        return await ctx.send(
            embed=discord.Embed(
                title=f"{mention} - #{rank}",
                color=await ctx.embed_color(),
                description=f"""
            **score:** {c.score} points
            **pinned:** {"yes (rank unreliable)" if c.pinned is True else "no"}
            **tracked:** {"yes" if c.tracked is True else "no"}
            **added:** {c.added}
            """,
            )
        )
