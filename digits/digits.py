import discord

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list


class Digits(commands.Cog):
    """check & roll digits"""

    __author__ = "relyq#0001"

    dubs = [00, 11, 22, 33, 44, 55, 66, 77, 88, 99]
    trips = [000, 111, 222, 333, 444, 555, 666, 777, 888, 999]
    quads = [0000, 1111, 2222, 3333, 4444, 5555, 6666, 7777, 8888, 9999]
    quints = [00000, 11111, 22222, 33333, 44444, 55555, 66666, 77777, 88888, 99999]
    sexes = [
        000000,
        111111,
        222222,
        333333,
        444444,
        555555,
        666666,
        777777,
        888888,
        999999,
    ]
    septs = [
        0000000,
        1111111,
        2222222,
        3333333,
        4444444,
        5555555,
        6666666,
        7777777,
        8888888,
        9999999,
    ]
    octs = [
        00000000,
        11111111,
        22222222,
        33333333,
        44444444,
        55555555,
        66666666,
        77777777,
        88888888,
        99999999,
    ]
    nons = [
        000000000,
        111111111,
        222222222,
        333333333,
        444444444,
        555555555,
        666666666,
        777777777,
        888888888,
        999999999,
    ]
    decs = [
        0000000000,
        1111111111,
        2222222222,
        3333333333,
        4444444444,
        5555555555,
        6666666666,
        7777777777,
        8888888888,
        9999999999,
    ]

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8181223, force_registration=True)

        default_guild = {"settings": {"enabled": False, "channels": []}}
        self.config.register_guild(**default_guild)

    @commands.Cog.listener("on_message")
    async def _message_listener(self, message):
        if not message.guild:  # dm
            return
        if (
            not await self.config.guild(message.guild).settings.enabled()
            and message.channel.id
            not in await self.config.guild(message.guild).settings.channels()
        ):
            return

        if message.id % 10000000000 in self.decs:
            await message.reply(
                content=f"{str(message.id)[-8:]} decs!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 1000000000 in self.nons:
            await message.reply(
                content=f"{str(message.id)[-8:]} nons!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 100000000 in self.octs:
            await message.reply(
                content=f"{str(message.id)[-8:]} octs!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 10000000 in self.septs:
            await message.reply(
                content=f"{str(message.id)[-8:]} septs!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 1000000 in self.sexes:
            await message.reply(
                content=f"{str(message.id)[-8:]} sexes!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 100000 in self.quints:
            await message.reply(
                content=f"{str(message.id)[-8:]} quints!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 10000 in self.quads:
            await message.reply(
                content=f"{str(message.id)[-8:]} quads!!!!",
                silent=True,
                mention_author=False,
            )
            return
        if message.id % 1000 in self.trips:
            # await message.reply(content=f"{str(message.id)[-8:]} trips!!!",silent=True,mention_author=False)
            return
        if message.id % 100 in self.dubs:
            # await message.reply(content=f"{str(message.id)[-8:]} dubs!!", silent=True)
            return

        return

    @commands.group(name="digitset", aliases=["digitssettings", "ds"])
    @commands.admin_or_permissions(administrator=True)
    async def digits_settings(self, ctx):
        """server wide settings for digits"""

    @digits_settings.command(name="enable", aliases=["enabled"])
    async def enable(self, ctx):
        """enable digits"""
        await self.config.guild(ctx.guild).settings.enabled(True)
        return await ctx.tick()

    @digits_settings.command(name="disable", aliases=["disabled"])
    async def disable(self, ctx):
        """disable digits"""
        await self.config.guild(ctx.guild).settings.enabled(False)
        return await ctx.tick()

    @digits_settings.group(name="channels")
    async def channels(self, ctx):
        """settings for channels to check digits"""

    @channels.command(name="set")
    async def roles_set(self, ctx: commands.Context, *channels: discord.TextChannel):
        """set the channels - this will overwrite the list"""
        await self.config.guild(ctx.guild).settings.channels.set(
            [c.id for c in channels]
        )
        return await ctx.tick()

    @channels.command(name="add")
    async def roles_add(self, ctx: commands.Context, *channels: discord.TextChannel):
        """add a role allowed to the list"""
        set_channels = await self.config.guild(ctx.guild).settings.channels()

        for c in channels:
            if c.id not in set_channels:
                set_channels.append(c.id)

        await self.config.guild(ctx.guild).settings.channels.set(set_channels)
        return await ctx.tick()

    @channels.command(name="remove")
    async def roles_remove(self, ctx: commands.Context, *channels: discord.TextChannel):
        """add a channel to the list"""
        set_channels = await self.config.guild(ctx.guild).settings.channels()

        for c in channels:
            if c.id in set_channels:
                set_channels.remove(c.id)

        await self.config.guild(ctx.guild).settings.channels.set(set_channels)
        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @digits_settings.command(name="view", aliases=["v"])
    async def view_settings(self, ctx: commands.Context):
        """view the current digits settings"""
        settings = await self.config.guild(ctx.guild).settings()

        channels = []
        for c in settings["channels"]:
            if c := ctx.guild.get_channel(c):
                channels.append(c.name)

        return await ctx.send(
            embed=discord.Embed(
                title="digits settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {"true" if settings["enabled"] else "false"}
            **channels:** {humanize_list([ctx.guild.get_channel(int(c)).mention for c in settings["channels"]]) or None}
            """,
            )
        )
