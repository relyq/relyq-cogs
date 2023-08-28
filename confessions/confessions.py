import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

import discord

from redbot.core import commands, data_manager
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.predicates import MessagePredicate

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from confessions.models import Base, Guild, Confession, BlockedUser_Guild


class Confessions(commands.Cog):
    """confessions"""

    __author__ = "relyq"

    def __init__(self, bot):
        self.bot = bot

        self.data_path = data_manager.cog_data_path(self) / "confessions.db"

        logging.basicConfig()
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

        self.engine = create_engine(f"sqlite://{self.data_path}")
        Base.metadata.create_all(self.engine)

    @staticmethod
    def init_guild(self, session: Session, guild: discord.Guild):
        """initialize guild on sqlite"""
        stmt = select(Guild).where(Guild.id == guild.id)
        if not session.scalars(stmt).first():
            session.add(
                Guild(
                    id=guild.id,
                    enabled=False,
                    confessions_channel=None,
                    log_channel=None,
                    added=datetime.now(timezone.utc),
                )
            )

    @staticmethod
    def update_guild(
        self,
        guild: discord.Guild,
        enabled: Optional[bool] = None,
        log_channel: Optional[discord.TextChannel] = None,
        confessions_channel: Optional[discord.TextChannel] = None,
    ):
        """init & update guild settings"""
        with Session(self.engine) as session:
            self.init_guild(self, session, guild)
            stmt = select(Guild).where(Guild.id == guild.id)
            guild = session.scalars(stmt).first()
            if enabled is not None:
                guild.enabled = enabled
            if log_channel is not None:
                guild.log_channel = log_channel.id
            if confessions_channel is not None:
                guild.confessions_channel = confessions_channel.id
            session.commit()

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
    async def get_guild(ctx: commands.Context) -> int:
        """
        ask for guild to post confession on
        """
        response = await ctx.bot.wait_for(
            "message", check=MessagePredicate.same_context(ctx), timeout=60
        )

        if isinstance(int(response.content), int):
            return int(response.content)
        else:
            raise ValueError()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @commands.command(name="confess", aliases=["confession"])
    async def confess(self, ctx: commands.Context, *, confession_content: str):
        """confess your sins"""
        if not isinstance(ctx.channel, discord.channel.DMChannel):
            await ctx.message.delete()
            return await ctx.send(
                "send me a dm with `ltn confess` to confess anonymously"
            )

        if len(ctx.author.mutual_guilds) > 1:
            nl = "\n"

            guilds = []
            for i, g in enumerate(ctx.author.mutual_guilds):
                guilds.append(f"{i + 1}. {g.name}")

            await ctx.reply(
                content=f"""where do you want to confess to?
                            {nl.join(guilds)}
                            """
            )

            try:
                guild = ctx.author.mutual_guilds[await self.get_guild(ctx) - 1]
            except asyncio.exceptions.TimeoutError:
                return
            except IndexError:
                return await ctx.reply("that's not in the list")

        else:
            guild = ctx.author.mutual_guilds[0]

        with Session(self.engine) as session:
            stmt = select(Guild).where(Guild.id == guild.id)
            guild_settings = session.scalars(stmt).first()
            if (
                guild_settings is None
                or guild_settings.confessions_channel is None
                or guild_settings.enabled is False
            ):
                return await ctx.send("this guild doesn't have confessions enabled")

            stmt = (
                select(BlockedUser_Guild)
                .where(BlockedUser_Guild.user_id == ctx.author.id)
                .where(BlockedUser_Guild.guild_id == guild.id)
            )

            if session.scalars(stmt).first():
                return await ctx.reply("you are blocked from confessing on this guild")

            added = datetime.now(timezone.utc)

            confession = Confession(
                guild_id=guild.id,
                author=ctx.author.id,
                content=confession_content,
                added=added,
            )

            session.add(confession)
            session.commit()

            embed = discord.Embed(
                title=f"anonymous confession #{confession.id}",
                color=await ctx.embed_color(),
                description=f"""{confession_content}""",
            )

            if ctx.message.attachments:
                embed.set_image(url=ctx.message.attachments[0].url)

            message: discord.Message = await guild.get_channel(
                guild_settings.confessions_channel
            ).send(embed=embed)

            confession.message_id = message.id

            session.commit()

            await asyncio.sleep(0.3)

        return await ctx.send(f"confession posted {message.jump_url}")

    ### server settings

    @commands.bot_has_permissions(manage_channels=True)
    @commands.group(name="cset", aliases=["confessionset"])
    async def settings(self, ctx):
        """server settings"""

    ### user management
    @commands.bot_has_permissions(ban_members=True)
    @settings.command(name="block")
    async def block_user(self, ctx: commands.Context, confession_number: int):
        """block confession poster"""
        with Session(self.engine) as session:
            stmt = select(Confession).where(Confession.id == confession_number)

            blocked_confession = session.scalars(stmt).first()
            user = ctx.guild.get_member(blocked_confession.author)

            if user is None:
                return await ctx.reply("member not found")

            stmt = (
                select(BlockedUser_Guild)
                .where(BlockedUser_Guild.user_id == user.id)
                .where(BlockedUser_Guild.guild_id == ctx.guild.id)
            )

            if not session.scalars(stmt).first():
                session.add(
                    BlockedUser_Guild(
                        user_id=user.id,
                        guild_id=ctx.guild.id,
                        blockedconfession_id=blocked_confession.id,
                        added=datetime.now(timezone.utc),
                    )
                )

                session.commit()

            stmt = select(Guild).where(Guild.id == ctx.guild.id)
            confessions_channel = ctx.guild.get_channel(
                session.scalars(stmt).first().confessions_channel
            )

            confession_url = None

            confession_url = confessions_channel.get_partial_message(
                blocked_confession.message_id
            ).jump_url

        await self.log_to_channel(
            self,
            ctx,
            title=f"confessions - confessor {confession_number} blocked",
            description=f"""
            confessor {confession_url if confession_url else confession_number} blocked by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @commands.bot_has_permissions(ban_members=True)
    @settings.command(name="unblock")
    async def unblock_user(self, ctx: commands.Context, user: discord.Member):
        """block confession poster"""
        with Session(self.engine) as session:
            stmt = (
                select(BlockedUser_Guild)
                .where(BlockedUser_Guild.guild_id == ctx.guild.id)
                .where(BlockedUser_Guild.user_id == user.id)
            )
            blocked_user = session.scalars(stmt).first()
            if blocked_user is None:
                return await ctx.reply("member not blocked")

            session.delete(blocked_user)

            session.commit()

        await self.log_to_channel(
            self,
            ctx,
            title="confessions - user unblocked",
            description=f"""
            confessor {user.mention} unblocked by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @settings.command(
        name="channel", aliases=["confessions_channel", "confess_channel"]
    )
    async def set_confessions_channel(
        self, ctx: commands.Context, confessions_channel: discord.TextChannel
    ):
        """set channel to send confessions to"""
        self.update_guild(
            self, guild=ctx.guild, confessions_channel=confessions_channel
        )

        await self.log_to_channel(
            self,
            ctx,
            title="confessions - confessions channel set",
            description=f"""
            {confessions_channel.mention} set as confessions channel by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @settings.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set channel to send logs to"""
        self.update_guild(self, guild=ctx.guild, log_channel=log_channel)

        await log_channel.send(
            embed=discord.Embed(
                title="confessions - confessions log channel set",
                color=await ctx.embed_color(),
                description=f"""
            {log_channel.mention} set as log channel by {ctx.author.mention}
            """,
            )
        )

        return await ctx.tick()

    @settings.command(name="enable", aliases=["enabled"])
    async def enable(self, ctx: commands.Context):
        """enable confessions"""
        self.update_guild(self, ctx.guild, enabled=True)

        await self.log_to_channel(
            self,
            ctx,
            title="confessions - enabled",
            description=f"""
              confessions enabled by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @settings.command(name="disable", aliases=["disabled"])
    async def disable(self, ctx: commands.Context):
        """disable confessions"""
        self.update_guild(self, ctx.guild, enabled=False)

        await self.log_to_channel(
            self,
            ctx,
            title="confessions - disabled",
            description=f"""
              confessions disabled by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @settings.command(name="view")
    async def view_settings(self, ctx: commands.Context):
        """view the current confessions settings"""
        self.update_guild(self, ctx.guild)

        with Session(self.engine) as session:
            stmt = select(Guild).where(Guild.id == ctx.guild.id)
            settings = session.scalars(stmt).first()

        return await ctx.send(
            embed=discord.Embed(
                title="confessions settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {settings.enabled}
            **confessions channel:** {"None" if settings.confessions_channel is None else ctx.guild.get_channel(settings.confessions_channel).mention}
            **log channel:** {"None" if settings.log_channel is None else ctx.guild.get_channel(settings.log_channel).mention}
            """,
            )
        )

    # public commands
