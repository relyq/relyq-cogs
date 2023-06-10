import time
import datetime
import math

from operator import attrgetter

import discord

from discord.ext import tasks

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list


class CScore_partial:
    def __init__(self, id, score):
        self.id = id
        self.score = score


class CScores(commands.Cog):
    """channel scores"""

    __author__ = "relyq"

    __global_grace__ = 60

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(
            self, identifier=1797464170, force_registration=True
        )

        default_guild = {
            "log_channel": None,
            "enabled": False,
            "categories": [],
            "scoreboard": {},
            "cooldown": 30,
            "grace": 60,
            "range": 1,
        }

        self.config.register_guild(**default_guild)

        self.main_loop.start()

    def cog_unload(self):
        self.main_loop.cancel()

    # points win logic
    @commands.Cog.listener("on_message")
    async def on_message_listener(self, message: discord.Message):
        async with self.config.guild(message.guild).scoreboard() as scoreboard:
            if await self.config.guild(message.guild).enabled() is False:
                return
            if message.author.id is message.guild.me.id:
                return
            if str(message.channel.id) not in scoreboard:
                return

            cooldown_sec = await self.config.guild(message.guild).cooldown() * 60

            since_update = time.time() - scoreboard[str(message.channel.id)]["updated"]

            # check cooldown - if grace is over 0 update doesnt matter
            # if update is low & grace 0 = recent message
            # if update is low & grace > 0 = recently lost points
            if scoreboard[str(message.channel.id)]["grace_count"] == 0:
                if since_update <= cooldown_sec:
                    return

            points_max = await self.config.guild(message.guild).range() * len(
                scoreboard
            )

            # add points & update last message time
            if scoreboard[str(message.channel.id)]["score"] < points_max:
                scoreboard[str(message.channel.id)]["score"] += 1
            scoreboard[str(message.channel.id)]["updated"] = time.time()
            scoreboard[str(message.channel.id)]["grace_count"] = 0

            return

    # points lose logic
    @tasks.loop(minutes=__global_grace__)
    async def main_loop(self):
        for g in await self.config.all_guilds():
            async with self.config.guild_from_id(g)() as settings:
                if settings["enabled"] is False:
                    return
                for c in settings["scoreboard"]:
                    since_update = int(
                        (time.time() - settings["scoreboard"][c]["updated"]) / 60
                    )

                    if since_update >= settings["grace"]:  # grace ended
                        if settings["scoreboard"][c]["score"] > 0:
                            settings["scoreboard"][c]["score"] -= (
                                1 if settings["scoreboard"][c]["grace_count"] else 0
                            )
                        settings["scoreboard"][c]["updated"] = time.time()
                        settings["scoreboard"][c]["grace_count"] += 1

        return

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.group(name="channelscores", aliases=["cscores", "cscore"])
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def channelscores(self, ctx: commands.Context):
        """channel scores"""

    @channelscores.command(name="add")
    async def add_channels(
        self, ctx: commands.Context, category: discord.abc.GuildChannel
    ):
        """add category to the scoreboard"""

        text_channels = []

        [text_channels.append(tc) for tc in category.text_channels]

        async with self.config.guild(ctx.guild).scoreboard() as scoreboard:
            # only add channels that aren't already in the scoreboard
            text_channels[:] = [c for c in text_channels if str(c.id) not in scoreboard]

            for c in text_channels:
                scoreboard[c.id] = {
                    "score": 0,
                    "pinned": False,
                    "added": time.time(),
                    "updated": 0,
                    "grace_count": 0,
                }

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).log_channel()
        )

        if log_channel and text_channels:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"category {category.name} added to scoreboard",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
              {humanize_list([c.mention for c in text_channels])} added by {ctx.author.mention}
            """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        return await ctx.tick()

    @channelscores.command(name="remove")
    async def remove_channels(
        self, ctx: commands.Context, category: discord.abc.GuildChannel
    ):
        """remove category from the scoreboard"""

        text_channels = []

        [text_channels.append(tc) for tc in category.text_channels]

        async with self.config.guild(ctx.guild).scoreboard() as scoreboard:
            text_channels[:] = [c for c in text_channels if str(c.id) in scoreboard]
            for c in text_channels:
                del scoreboard[str(c.id)]

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).log_channel()
        )

        if log_channel and text_channels:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"category {category.name} removed from scoreboard",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
              {humanize_list([c.mention for c in text_channels])} removed by {ctx.author.mention}
            """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        return await ctx.tick()

    @channelscores.command(name="pin")
    async def pin_channels(self, ctx: commands.Context, *channels: discord.TextChannel):
        """pin channels so they dont move"""

        new_pins = []

        async with self.config.guild(ctx.guild).scoreboard() as scoreboard:
            new_pins[:] = [
                c
                for c in channels
                if str(c.id) in scoreboard and scoreboard[str(c.id)]["pinned"] is False
            ]
            for c in new_pins:
                scoreboard[str(c.id)]["pinned"] = True

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).log_channel()
        )

        if log_channel and new_pins:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"channels pinned - scoreboard",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
              {humanize_list([c.mention for c in new_pins])} pinned by {ctx.author.mention}
            """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        return await ctx.tick()

    @channelscores.command(name="unpin")
    async def unpin_channels(
        self, ctx: commands.Context, *channels: discord.TextChannel
    ):
        """unpin channels so they move again"""

        new_unpinned = []

        async with self.config.guild(ctx.guild).scoreboard() as scoreboard:
            new_unpinned[:] = [
                c
                for c in channels
                if str(c.id) in scoreboard and scoreboard[str(c.id)]["pinned"] is True
            ]
            for c in new_unpinned:
                scoreboard[str(c.id)]["pinned"] = False

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).log_channel()
        )

        if log_channel and new_unpinned:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"channels unpinned - scoreboard",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
              {humanize_list([c.mention for c in new_unpinned])} unpinned by {ctx.author.mention}
            """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        return await ctx.tick()

    @channelscores.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set channel to send logs to"""
        await self.config.guild(ctx.guild).log_channel.set(log_channel.id)

        await log_channel.send(
            embed=discord.Embed(
                title="channel scores log channel set",
                color=await ctx.embed_color(),
                description=f"""
            {log_channel.mention} set as log channel by {ctx.author.mention}
            """,
            )
        )

        return await ctx.tick()

    @channelscores.command(name="cooldown")
    async def set_cooldown(self, ctx: commands.Context, minutes: int):
        """set on-message points cooldown in minutes - def: 30"""
        if minutes < 1 or minutes > 10000:
            await ctx.send(
                "cooldown can't be lower than 1 minute or higher than 10000 minutes"
            )
            return

        await self.config.guild(ctx.guild).cooldown.set(minutes)
        return await ctx.tick()

    @channelscores.command(name="grace")
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

        await self.config.guild(ctx.guild).grace.set(minutes)
        return await ctx.tick()

    @channelscores.command(name="enable")
    async def enable(self, ctx: commands.Context):
        """enable channel scores"""
        await self.config.guild(ctx.guild).enabled.set(True)
        return await ctx.tick()

    @channelscores.command(name="disable")
    async def disable(self, ctx: commands.Context):
        """disable channel scores"""
        await self.config.guild(ctx.guild).enabled.set(False)
        return await ctx.tick()

    @channelscores.command(name="range")
    async def set_range(self, ctx: commands.Context, new_range: int):
        """set min-max points according to total number of channels. 'range 2' with 10 channels results in 0 - 20 range - def: 1"""
        if new_range < 1 or new_range > 5:
            await ctx.send("range can only be set from 1 to 5 currently")
            return
        await self.config.guild(ctx.guild).range.set(new_range)
        return await ctx.tick()

    @channelscores.command(name="view")
    async def view_channel(self, ctx: commands.Context):
        """view channel score"""
        try:
            c = (await self.config.guild(ctx.guild).scoreboard())[str(ctx.channel.id)]
        except KeyError:
            await ctx.send("this channel is not part of the scoreboard")
            return

        return await ctx.send(
            embed=discord.Embed(
                title=f"{ctx.channel.mention} score",
                color=await ctx.embed_color(),
                description=f"""
            **score:** {c["score"]}
            **pinned:** {"yes" if c["pinned"] is True else "no"}
            **added:** {time.ctime(c["added"])}
            """,
            )
        )

    @commands.bot_has_permissions(embed_links=True)
    @channelscores.command(name="settings", aliases=["set"])
    async def view_settings(self, ctx: commands.Context):
        """view the current channel scores settings"""
        settings = await self.config.guild(ctx.guild)()
        return await ctx.send(
            embed=discord.Embed(
                title="channel scores settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {settings["enabled"]}
            **log channel:** {"None" if settings["log_channel"] is None else ctx.guild.get_channel(settings["log_channel"]).mention}
            **cooldown:** {settings["cooldown"]} minutes
            **grace period:** {settings["grace"]} minutes
            **channels:** {len(settings["scoreboard"])}
            **range:** {settings["range"]} / 0 to {settings["range"] * len(settings["scoreboard"])} points
            """,
            )
        )

    @channelscores.command(name="scoreboard", aliases=["board", "top"])
    async def view_scoreboard(self, ctx: commands.Context, page=1):
        """view the scoreboard"""
        scoreboard = await self.config.guild(ctx.guild).scoreboard()

        page_size = 15

        offset = (page - 1) * page_size

        total_pages = math.ceil(len(scoreboard) / page_size)

        scores = []

        for c in scoreboard:
            scores.append(CScore_partial(c, scoreboard[str(c)]["score"]))

        scores.sort(key=lambda x: x.score, reverse=True)

        scores = [
            f"{index}. {ctx.guild.get_channel(int(c.id)).mention} - {c.score} points"
            for index, c in enumerate(scores)
        ]

        scores = scores[offset : offset + page_size]

        nl = "\n"
        top = f"{nl.join(scores)}"

        return await ctx.send(
            embed=discord.Embed(
                title=f"{ctx.guild.name} scoreboard - {page_size} of {len(scoreboard) - 1}",
                color=await ctx.embed_color(),
                description=top,
            ).set_footer(text=f"page {page} of {total_pages}")
        )
