import time
import datetime
import math
import asyncio
from collections import OrderedDict

from operator import attrgetter

import discord

from discord.ext import tasks

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.predicates import MessagePredicate


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
            "sync": False,
            "categories": {},
            "scoreboard": {},
            "cooldown": 30,
            "grace": 60,
            "range": 1,
        }

        self.config.register_guild(**default_guild)

        self.main_loop.start()

    def cog_unload(self):
        self.main_loop.cancel()

    @staticmethod
    async def sync_channels(self, guild: discord.Guild):
        categories = await self.config.guild(guild).categories()
        scoreboard = await self.config.guild(guild).scoreboard()
        scores = []

        for c in scoreboard:
            if scoreboard[str(c)]["pinned"]:
                continue
            scores.append(CScore_partial(c, scoreboard[str(c)]["score"]))

        scores.sort(key=lambda x: x.score, reverse=True)

        for category in categories:
            if categories[category]["tracked"]:
                category = guild.get_channel(int(category))
                category.text_channels.sort(key=lambda x: x.position)
                first_pos = category.text_channels[0].position
                pins = []

                for channel in category.text_channels:
                    if scoreboard[str(channel.id)]["pinned"]:
                        pins.append(
                            (
                                CScore_partial(
                                    channel.id, scoreboard[str(channel.id)]["score"]
                                ),
                                channel.position - first_pos,
                            )
                        )
                pins.sort(key=lambda x: x[1])

                for pin in pins:
                    scores.insert(pin[1], pin[0])

                for rank, chanscore in enumerate(scores):
                    if scoreboard[str(chanscore.id)]["tracked"]:
                        channel = guild.get_channel(int(chanscore.id))
                        if channel.position is not first_pos + rank:
                            await channel.move(
                                category=category,
                                beginning=True,
                                offset=rank,
                                reason="channel scores",
                            )
                            await asyncio.sleep(0.5)  # dont get rate limited

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

            ## add points
            if scoreboard[str(message.channel.id)]["tracked"]:
                cooldown_sec = await self.config.guild(message.guild).cooldown() * 60

                since_update = (
                    time.time() - scoreboard[str(message.channel.id)]["updated"]
                )

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

            # check score
            if await self.config.guild(message.guild).sync():
                await self.sync_channels(self, message.guild)

    # points lose logic
    @tasks.loop(minutes=__global_grace__)
    async def main_loop(self):
        for g in await self.config.all_guilds():
            async with self.config.guild_from_id(g)() as settings:
                if settings["enabled"] is False:
                    return
                for c in settings["scoreboard"]:
                    if settings["scoreboard"][c]["tracked"]:
                        since_update = int(
                            (time.time() - settings["scoreboard"][c]["updated"]) / 60
                        )

                        if since_update >= settings["grace"]:  # grace ended
                            if settings["scoreboard"][c]["score"] > 0:
                                settings["scoreboard"][c]["score"] -= (
                                    1 if settings["scoreboard"][c]["grace_count"] else 0
                                )
                                if settings["sync"]:
                                    await self.sync_channels(
                                        self,
                                        self.bot.get_guild(int(g)),
                                    )

                            settings["scoreboard"][c]["updated"] = time.time()
                            settings["scoreboard"][c]["grace_count"] += 1

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
        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=title,
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=description,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @staticmethod
    def sort_catchan(self, catchan) -> dict:
        channels = {"categories": [], "text_channels": []}

        for c in catchan:
            if type(c) is discord.TextChannel:
                if c not in channels["text_channels"]:
                    channels["text_channels"].append(c)

            if type(c) is discord.CategoryChannel:
                channels["categories"].append(c)
                for tc in c.text_channels:
                    if tc not in channels["text_channels"]:
                        channels["text_channels"].append(tc)
        return channels

    ### actions that you perform on channels

    @channelscores.command(name="track")
    async def track_channels(
        self, ctx: commands.Context, *channels: discord.abc.GuildChannel
    ):
        """track channels and categories"""

        if not channels:
            return await ctx.send("no channels or categories to add")

        sorted_channels = self.sort_catchan(self, channels)

        async with self.config.guild(ctx.guild)() as settings:
            # add untracked categories
            for category in sorted_channels["categories"]:
                if str(category.id) not in settings["categories"]:
                    settings["categories"][str(category.id)] = {
                        "tracked": True,
                        "added": time.time(),
                        "previous": None,
                        "next": None,
                    }

                # set all categories to tracked
                settings["categories"][str(category.id)]["tracked"] = True

            for channel in sorted_channels["text_channels"]:
                # add untracked channels
                if str(channel.id) not in settings["scoreboard"]:
                    settings["scoreboard"][str(channel.id)] = {
                        "score": 0,
                        "pinned": False,
                        "added": time.time(),
                        "updated": 0,
                        "grace_count": 0,
                        "tracked": True,
                    }

                # set all channels to tracked
                settings["scoreboard"][str(channel.id)]["tracked"] = True

        await self.log_to_channel(
            self,
            ctx,
            title="scores - channels tracked",
            description=f"""
            categories: {humanize_list([cat.name for cat in sorted_channels["categories"]]) if sorted_channels["categories"] else ''}
            channels: {humanize_list([c.mention for c in sorted_channels["text_channels"]]) if sorted_channels["text_channels"] else ''}
            added by {ctx.author.mention}""",
        )

        return await ctx.tick()

    @channelscores.command(name="untrack")
    async def untrack_channels(
        self, ctx: commands.Context, *channels: discord.abc.GuildChannel
    ):
        """untrack channels and categories"""

        sorted_channels = self.sort_catchan(self, channels)

        async with self.config.guild(ctx.guild)() as settings:
            # add untracked categories
            for category in sorted_channels["categories"]:
                # set all categories to untracked
                settings["categories"][str(category.id)]["tracked"] = False

            for channel in sorted_channels["text_channels"]:
                # set all channels to untracked
                settings["scoreboard"][str(channel.id)]["tracked"] = False

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
        self, ctx: commands.Context, *channels: discord.abc.GuildChannel
    ):
        """reset channel scores"""
        raise

        await ctx.send(
            "are you sure you want to reset the scores for these channels and categories?"
        )

        cont = await self.confirm_message()

        if not cont:
            return await ctx.send("cancelled")

    @channelscores.command(name="forget")
    async def remove_channels(
        self, ctx: commands.Context, *channels: discord.abc.GuildChannel
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

        sorted_channels = self.sort_catchan(self, channels)

        async with self.config.guild(ctx.guild)() as settings:
            # add untracked categories
            for category in sorted_channels["categories"]:
                try:
                    del settings["categories"][str(category.id)]
                except:
                    pass

            for channel in sorted_channels["text_channels"]:
                try:
                    del settings["scoreboard"][str(channel.id)]
                except:
                    pass

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - channels removed",
            description=f"""
            categories: {humanize_list([cat.name for cat in sorted_channels["categories"]]) if sorted_channels["categories"] else ''}
            channels: {humanize_list([c.mention for c in sorted_channels["text_channels"]]) if sorted_channels["text_channels"] else ''}
            removed by {ctx.author.mention}""",
        )

        return await ctx.tick()

    @channelscores.command(name="pin")
    async def pin_channels(self, ctx: commands.Context, *channels: discord.TextChannel):
        """pin channels so they dont move"""

        async with self.config.guild(ctx.guild).scoreboard() as scoreboard:
            for c in channels:
                scoreboard[str(c.id)]["pinned"] = True

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

        new_unpinned = []

        async with self.config.guild(ctx.guild).scoreboard() as scoreboard:
            new_unpinned[:] = [
                c
                for c in channels
                if str(c.id) in scoreboard and scoreboard[str(c.id)]["pinned"] is True
            ]
            for c in new_unpinned:
                scoreboard[str(c.id)]["pinned"] = False

        await self.log_to_channel(
            self,
            ctx,
            title=f"channels unpinned - scoreboard",
            description=f"""
              {humanize_list([c.mention for c in new_unpinned])} unpinned by {ctx.author.mention}
            """,
        )

        return await ctx.tick()

    @channelscores.command(name="link")
    async def link_categories(
        self, ctx: commands.Context, *categories: discord.CategoryChannel
    ):
        """link categories so they act as one logical volume"""
        raise

    ### server settings

    @channelscores.group(name="settings", aliases=["set", "s"])
    async def settings(self, ctx):
        """server settings"""

    @settings.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set channel to send logs to"""
        await self.config.guild(ctx.guild).log_channel.set(log_channel.id)

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

        await self.config.guild(ctx.guild).cooldown.set(minutes)
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

        await self.config.guild(ctx.guild).grace.set(minutes)
        return await ctx.tick()

    @settings.command(name="enable", aliases=["enabled"])
    async def enable(self, ctx: commands.Context):
        """enable channel scores"""

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - enabled",
            description=f"""
              scores enabled by {ctx.author.mention}
            """,
        )

        await self.config.guild(ctx.guild).enabled.set(True)
        return await ctx.tick()

    @settings.command(name="disable", aliases=["disabled"])
    async def disable(self, ctx: commands.Context):
        """disable channel scores"""

        await self.log_to_channel(
            self,
            ctx,
            title=f"scores - disabled",
            description=f"""
              scores disabled by {ctx.author.mention}
            """,
        )

        await self.config.guild(ctx.guild).enabled.set(False)
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

        await self.config.guild(ctx.guild).range.set(new_range)
        return await ctx.tick()

    @settings.group(name="sync")
    async def sync(self, ctx):
        """disable or enable channel sync to scoreboard"""

    @sync.command(name="enable")
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

        await self.config.guild(ctx.guild).sync.set(True)
        return await ctx.tick()

    @sync.command(name="disable")
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

        await self.config.guild(ctx.guild).sync.set(False)
        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @settings.command(name="view")
    async def view_settings(self, ctx: commands.Context):
        """view the current channel scores settings"""
        settings = await self.config.guild(ctx.guild)()

        untracked_count = 0

        for c in settings["scoreboard"]:
            if settings["scoreboard"][str(c)]["tracked"] is False:
                untracked_count += 1

        return await ctx.send(
            embed=discord.Embed(
                title="channel scores settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {settings["enabled"]}
            **log channel:** {"None" if settings["log_channel"] is None else ctx.guild.get_channel(settings["log_channel"]).mention}
            **cooldown:** {settings["cooldown"]} minutes
            **grace period:** {settings["grace"]} minutes
            **range:** {settings["range"]} / 0 to {settings["range"] * len(settings["scoreboard"])} points
            **sync**: {"enabled" if settings["sync"] else "disabled"}
            **categories:** {
              humanize_list(
                [f"{ctx.guild.get_channel(int(cat)).name} ({'tracked' if settings['categories'][cat]['tracked'] else 'untracked'})" for cat in settings["categories"]]
              )
              if settings["categories"] else ""}
            **channels:** {len(settings["scoreboard"])} - {untracked_count} not tracked
            """,
            )
        )

    # public commands

    @commands.command(name="scoreboard", aliases=["board", "top"])
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
            f"{index}. {ctx.guild.get_channel(int(c.id)).mention} - {c.score} points {'*' if scoreboard[str(c.id)]['pinned'] else ''}"
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

    @commands.command(name="rank")
    async def view_channel(
        self, ctx: commands.Context, channel: discord.TextChannel = None
    ):
        """view channel score"""
        mention = None
        try:
            c = (await self.config.guild(ctx.guild).scoreboard())[str(channel.id)]
            mention = channel.mention
        except:
            try:
                c = (await self.config.guild(ctx.guild).scoreboard())[
                    str(ctx.channel.id)
                ]
                mention = ctx.channel.mention
            except KeyError:
                await ctx.send("this channel is not part of the scoreboard")
                return

        first_pos = channel.category.text_channels[0].position
        rank = channel.position - first_pos + 1

        return await ctx.send(
            embed=discord.Embed(
                title=f"{mention} - #{rank}",
                color=await ctx.embed_color(),
                description=f"""
            **score:** {c["score"]} points
            **pinned:** {"yes (rank unreliable)" if c["pinned"] is True else "no"}
            **tracked:** {"yes" if c["tracked"] is True else "no"}
            **added:** {time.ctime(c["added"])}
            """,
            )
        )
