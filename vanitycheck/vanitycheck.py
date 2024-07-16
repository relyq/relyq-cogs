import discord

from discord.ext import tasks

from redbot.core import commands, Config


class VanityCheck(commands.Cog):
    """check vanity availability"""

    __author__ = "relyq"
    __version__ = "0.1"

    __loop_minutes__ = 5

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(
            self, identifier=684868769, force_registration=True
        )

        default_guild = {
            "settings": {
                "enabled": False,
                "log_channel": None,
                "new_vanity": None,
                "pings": [],
            }
        }

        self.config.register_guild(**default_guild)

    @tasks.loop(minutes=__loop_minutes__)
    async def main_loop(self):
        guilds = await self.config.all_guilds()

        for g in guilds:
            if g["enabled"] and g["new_vanity"] and g["log_channel"]:
                guild = await self.bot.get_guild(g)

                log_channel = await self.bot.get_channel(g["log_channel"])

                try:
                    await guild.edit(vanity_code=g["new_vanity"])
                except Exception as e:
                    # failed
                    log_channel.send(f"couldn't claim vanity - {e}")
                    continue

                # success
                log_channel.send(
                    f"vanity claimed - discord.gg/{g['new_vanit']} - {[guild.get_member(u).mention for u in g['pings']]}"
                )
                await self.config.guild(g).settings.enabled(False)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.group(name="vanitycheck")
    @commands.guild_only()
    @commands.admin()
    async def vanitycheck(self, ctx: commands.Context):
        """vanity check"""

    @vanitycheck.command(name="test")
    async def test(self, ctx: commands.Context):
        """test"""
        guilds = await self.config.all_guilds()

        for g in guilds:
            settings = guilds[g]["settings"]
            print(settings)
            if (
                settings["enabled"]
                and settings["new_vanity"]
                and settings["log_channel"]
            ):
                guild = self.bot.get_guild(g)

                log_channel = self.bot.get_channel(settings["log_channel"])

                try:
                    await guild.edit(vanity_code=settings["new_vanity"])
                except Exception as e:
                    # failed
                    log_channel.send(f"couldn't claim vanity - {e}")
                    continue

                # success
                log_channel.send(
                    f"vanity claimed - discord.gg/{settings['new_vanity']} - {[guild.get_member(u).mention for u in settings['pings']]}"
                )

    @vanitycheck.command(name="set")
    async def set_vanity(self, ctx: commands.Context, new_vanity: str):
        """set new vanity"""
        await self.config.guild(ctx.guild).settings.new_vanity.set(new_vanity)
        return await ctx.tick()

    @vanitycheck.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set log channel"""
        await self.config.guild(ctx.guild).settings.log_channel.set(log_channel.id)
        return await ctx.tick()

    @vanitycheck.command(name="pings")
    async def ping_users(self, ctx: commands.Context, *users: discord.Member):
        """set the users to ping when the vanity is claimed"""
        await self.config.guild(ctx.guild).settings.pings.set([u.id for u in users])
        return await ctx.tick()

    @vanitycheck.command(name="enable")
    async def enable(self, ctx: commands.Context):
        """enable vanitycheck"""
        settings = await self.config.guild(ctx.guild).settings()

        if not (
            settings["new_vanity"] and settings["log_channel"] and settings["pings"]
        ):
            return await ctx.send(
                "please make sure new vanity, log channel, and pinged users are set before enabling"
            )

        await self.config.guild(ctx.guild).settings.enabled.set(True)
        return await ctx.tick()

    @vanitycheck.command(name="disable")
    async def disable(self, ctx: commands.Context):
        """disable vanitycheck"""
        await self.config.guild(ctx.guild).settings.enabled.set(False)
        return await ctx.tick()

    @vanitycheck.command(name="settings", aliases=["view"])
    async def view_settings(self, ctx: commands.Context):
        """view vanitycheck settings"""
        settings = await self.config.guild(ctx.guild).settings()

        return await ctx.send(
            embed=discord.Embed(
                title="vanitycheck settings",
                color=await ctx.embed_color(),
                description=f"""
            **enabled:** {"true" if settings["enabled"] else "false"}
            **new vanity:** {settings["new_vanity"]}
            **log channel:** {"None" if settings["log_channel"] is None else ctx.guild.get_channel(settings["log_channel"]).mention}
            **users to ping:** {[ctx.guild.get_member(u).mention for u in settings["pings"]]}
            """,
            )
        )
