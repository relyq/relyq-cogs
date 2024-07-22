import discord

from redbot.core import commands, Config


class RoleWatch(commands.Cog):
    """warn when roles are given"""

    __author__ = "relyq"
    __version__ = "0.1"

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(
            self, identifier=681824969, force_registration=True
        )

        default_guild = {
            "settings": {
                "enabled": False,
                "log_channel": None,
                "watched_roles": [],
                "pinged_roles": [],
            }
        }

        self.config.register_guild(**default_guild)

    @commands.Cog.listener("on_member_update")
    async def _role_listener(self, prev: discord.Member, new: discord.Member):
        guild = prev.guild
        settings = await self.config.guild(guild).settings()

        if not settings["enabled"]:
            return

        if prev.roles == new.roles:
            return

        watched_roles = [guild.get_role(rid) for rid in settings["watched_roles"]]

        pinged_roles = [guild.get_role(rid) for rid in settings["pinged_roles"]]

        for wrole in watched_roles:
            if wrole in new.roles and wrole not in prev.roles:
                return await guild.get_channel(settings["log_channel"]).send(
                    f"""{[r.mention for r in pinged_roles]}
                    role {wrole.mention} given to {new.mention}"""
                )

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.group(name="rolewatch")
    @commands.guild_only()
    @commands.admin()
    async def rolewatch(self, ctx: commands.Context):
        """role watch"""

    @rolewatch.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set log channel"""
        await self.config.guild(ctx.guild).settings.log_channel.set(log_channel.id)
        return await ctx.tick()

    @rolewatch.command(name="watch")
    async def watch_roles(self, ctx: commands.Context, *roles: discord.Role):
        """set the roles to watch"""
        await self.config.guild(ctx.guild).settings.watched_roles.set(
            [r.id for r in roles]
        )
        return await ctx.tick()

    @rolewatch.command(name="ping")
    async def ping_roles(self, ctx: commands.Context, *roles: discord.Role):
        """set the roles to ping when a role is given"""
        await self.config.guild(ctx.guild).settings.pinged_roles.set(
            [r.id for r in roles]
        )
        return await ctx.tick()

    @rolewatch.command(name="enable")
    async def enable(self, ctx: commands.Context):
        """enable rolewatch"""
        settings = await self.config.guild(ctx.guild).settings()

        if not (settings["log_channel"]):
            return await ctx.send("please make sure log channel is set before enabling")

        await self.config.guild(ctx.guild).settings.enabled.set(True)
        return await ctx.tick()

    @rolewatch.command(name="disable")
    async def disable(self, ctx: commands.Context):
        """disable rolewatch"""
        await self.config.guild(ctx.guild).settings.enabled.set(False)
        return await ctx.tick()

    @rolewatch.command(name="settings", aliases=["view"])
    async def view_settings(self, ctx: commands.Context):
        """view rolewatch settings"""
        settings = await self.config.guild(ctx.guild).settings()

        return await ctx.send(
            embed=discord.Embed(
                title="rolewatch settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {"true" if settings["enabled"] else "false"}
            **log channel:** {"None" if settings["log_channel"] is None else ctx.guild.get_channel(settings["log_channel"]).mention}
            **watched roles:** {[ctx.guild.get_role(rid).mention for rid in settings["watched_roles"]]}
            **roles to ping:** {[ctx.guild.get_role(rid).mention for rid in settings["pinged_roles"]]}
            """,
            )
        )
