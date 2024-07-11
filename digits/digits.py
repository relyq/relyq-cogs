import discord

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list


class Digits(commands.Cog):
    """check & roll digits"""

    __author__ = "relyq#0001"

    dubs = [00, 11, 22, 33, 44, 55, 66, 77, 88, 99]
    trips = [000, 111, 222, 333, 444, 555, 666, 777, 888, 999]
    quads = [0000, 1111, 2222, 3333, 4444, 5555, 6666, 7777, 8888, 9999]
    quints = []
    sexes = []
    septs = []
    octs = []
    nons = []
    decs = []

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8181223, force_registration=True)

        default_guild = {"settings": {"channels": []}}
        self.config.register_guild(**default_guild)

    @commands.Cog.listener("on_message")
    async def _message_listener(self, message):
        if not message.guild:  # dm
            return
        if (
            message.channel.id
            not in await self.config.guild(message.guild).settings.channels()
        ):
            return

        if message.id % 10000 in self.quads:
            await message.reply(
                content=f"{str(message.id)[-8:]} quads!!!!", silent=True
            )
            return
        if message.id % 1000 in self.trips:
            await message.reply(content=f"{str(message.id)[-8:]} trips!!!", silent=True)
            return
        if message.id % 100 in self.dubs:
            await message.reply(content=f"{str(message.id)[-8:]} dubs!!", silent=True)
            return

        return

    @commands.group(name="digitset", aliases=["digitssettings", "dset", "ds"])
    @commands.admin_or_permissions(administrator=True)
    async def digits_settings(self, ctx):
        """server wide settings for digits"""

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
            **channels:** {humanize_list([ctx.guild.get_channel(int(c)).mention for c in settings["channels"]]) or None}
            """,
            )
        )
