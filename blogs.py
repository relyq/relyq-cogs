import time

import discord

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list


class Blogs(commands.Cog):
    """blog manager"""

    __author__ = "relyq#0001"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=13452753, force_registration=True)
        default_guild = {
            "text": {
                "category": None,
                "maximum": 10,
                "roles": [],
                "userlimit": 1,
                "active": [],
                "role_req_msg": "you dont have the required roles to create a blog",
                "toggle": False
            }
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener("on_guild_channel_delete")
    async def _deletion_listener(self, channel):
        async with self.config.guild(channel.guild).text.active() as active:
            try:
                ind = [a[0] for a in active].index(channel.id)
                active.pop(ind)
            except ValueError:
                pass

# public commands

    @commands.group(name="blog")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True)
    async def blog(self, ctx: commands.Context):
        """
        blogs
        """

    @blog.command(name="create")
    async def create_blog(self, ctx: commands.Context, name: str):
        """create your blog"""

        if not ctx.guild.me.guild_permissions.manage_channels:
            return await ctx.send("i dont have the permissions to create a channel")

        if not await self.config.guild(ctx.guild).text.toggle():
            return

        # check caller roles
        role_req = await self.config.guild(ctx.guild).text.roles()
        if role_req and not bool(set(role_req) & set([r.id for r in ctx.author.roles])):
            return await ctx.send(await self.config.guild(ctx.guild).text.role_req_msg())

        # retrieve number of active channels, authors, and maximum channels
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]
        maximum = await self.config.guild(ctx.guild).text.maximum()

        # check if caller is allowed to create blog - channel limits
        userlimit = await self.config.guild(ctx.guild).text.userlimit()
        if len(active) >= maximum:
            return await ctx.send(f"there are already {maximum} active text channels")
        if len(active_author) >= userlimit:
            return await ctx.send(f"you already have a blog")

        # get category overwrites - aka permissions
        category = self.bot.get_channel(await self.config.guild(ctx.guild).text.category())
        overwrites = category.overwrites
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, read_messages=True,
            attach_files=True, embed_links=True,
            external_emojis=True, external_stickers=True,
            read_message_history=True)

        # create channel
        new = await ctx.guild.create_text_channel(name=name, category=category, overwrites=overwrites)
        async with self.config.guild(ctx.guild).text.active() as a:
            a.append((new.id, ctx.author.id, time.time()))

        return await ctx.tick()

    @blog.group(name="set")
    async def settings(self, ctx: commands.Context):
        """
        settings for your blog
        """

    @settings.command(name="private")
    async def private_blog(self, ctx: commands.Context):
        """make your blog private so only you can post"""

        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        category = self.bot.get_channel(await self.config.guild(ctx.guild).text.category())

        # sync perms with category
        overwrites = category.overwrites

        # disable default perms
        for role_user in overwrites:
            if role_user != ctx.author:
                overwrites[role_user].update(
                    send_messages=False, add_reactions=False)

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, read_messages=True,
            attach_files=True, embed_links=True,
            external_emojis=True, external_stickers=True,
            read_message_history=True)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

    @settings.command(name="public")
    async def public_blog(self, ctx: commands.Context):
        """make your blog public so anyone can post -- syncs perms with category"""

        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        category = self.bot.get_channel(await self.config.guild(ctx.guild).text.category())

        # sync perms with category
        overwrites = category.overwrites

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, read_messages=True,
            attach_files=True, embed_links=True,
            external_emojis=True, external_stickers=True,
            read_message_history=True)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

# mod commands

    @commands.group(name="blogs")
    @commands.admin_or_permissions(administrator=True)
    async def blogsset(self, ctx: commands.Context):
        """server wide settings for blogs"""

    @blogsset.command(name="toggle")
    async def _text_toggle(self, ctx: commands.Context, true_or_false: bool):
        """toggle whether users can use `[p]blog create` in this server"""
        await self.config.guild(ctx.guild).text.toggle.set(true_or_false)
        return await ctx.tick()

    @blogsset.command(name="category")
    async def _text_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        """set the text channel category for blogs - def: none"""
        await self.config.guild(ctx.guild).text.category.set(category.id)
        return await ctx.tick()

    @blogsset.command(name="maxchannels")
    async def _text_maxchannels(self, ctx: commands.Context, maximum: int):
        """set the maximum amount of total blog channels that can be created - def: 10"""
        await self.config.guild(ctx.guild).text.maximum.set(maximum)
        return await ctx.tick()

    @blogsset.command(name="roles")
    async def _text_roles(self, ctx: commands.Context, *roles: discord.Role):
        """set the roles allowed to use `[p]blog create` - def: @everyone"""
        await self.config.guild(ctx.guild).text.roles.set([r.id for r in roles])
        return await ctx.tick()

    @blogsset.command(name="userlimit")
    async def _text_userlimit(self, ctx: commands.Context, limit: int):
        """set the maximum amount of blogs users can create - def: 1"""
        await self.config.guild(ctx.guild).text.userlimit.set(limit)
        return await ctx.tick()

    @blogsset.command(name="rolereqmsg")
    async def _text_rolereqmsg(self, ctx: commands.Context, *, message: str):
        """set the message displayed when a user does not have any of the required roles - def: 'you dont have the required roles to create a blog' """
        await self.config.guild(ctx.guild).text.role_req_msg.set(message)
        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @blogsset.command(name="view")
    async def _text_view(self, ctx: commands.Context):
        """view the current blogs settings"""
        settings = await self.config.guild(ctx.guild).text()

        roles = []
        for role in settings["roles"]:
            if r := ctx.guild.get_role(role):
                roles.append(r.name)

        return await ctx.send(embed=discord.Embed(
            title="blogs settings",
            color=await ctx.embed_color(),
            description=f"""
            **toggle:** {settings["toggle"]}
            **category:** {"None" if settings["category"] is None else ctx.guild.get_channel(settings["category"]).name}
            **max channels:** {settings["maximum"]} channels
            **roles:** {humanize_list(roles) or None}
            **user limit:** {settings["userlimit"]} channels
            **active:** {humanize_list([ctx.guild.get_channel(c[0]) for c in settings["active"]]) or None}
            **role req msg**: {settings["role_req_msg"]}
            """
        ))

    @blogsset.command(name="clear")
    async def _text_clear(self, ctx: commands.Context):
        """clear & reset the current blogs settings."""
        await self.config.guild(ctx.guild).text.clear()
        return await ctx.tick()
