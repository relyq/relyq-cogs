import asyncio
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
            send_messages=True)

        # create channel
        new = await ctx.guild.create_text_channel(name=name, category=category, overwrites=overwrites)
        async with self.config.guild(ctx.guild).text.active() as a:
            a.append((new.id, ctx.author.id, time.time()))

        await new.send(f"{ctx.author.mention} welcome to your new blog!!")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"its perms are currently synced to the blogs category")

        async with new.typing():
            await asyncio.sleep(1.25)
        await new.send(f"but you can rename it and set its description to whatever you want")

        async with new.typing():
            await asyncio.sleep(1.5)
        await new.send(f"you can also set it to private with `ltn blog set private` so only you can post")

        async with new.typing():
            await asyncio.sleep(2)
        await new.send(f"in that case you can choose to share your blog with some ppl using `ltn blog share @relyq`")

        async with new.typing():
            await asyncio.sleep(1.3)
            await new.send(f"`ltn blog set public` will sync it back to the blog category perms")

        async with new.typing():
            await asyncio.sleep(0.5)
        await new.send(f"type `ltn blog` to see all the options")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"once done do `ltn cleanup messages 99` to clean the chat")

        return await ctx.tick()

    @blog.command(name="share", aliases=["add"])
    async def share_blog(self, ctx: commands.Context, user: discord.Member):
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        overwrites = ctx.channel.overwrites

        # set shared perms
        overwrites[user] = overwrites.get(
            user, discord.PermissionOverwrite())
        overwrites[user].update(manage_messages=True, send_messages=True)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

    @blog.command(name="unshare", aliases=["remove"])
    async def unshare_blog(self, ctx: commands.Context, user: discord.Member):
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        overwrites = ctx.channel.overwrites

        # set shared perms
        overwrites[user] = overwrites.get(
            user, discord.PermissionOverwrite())
        overwrites[user].update(manage_messages=None, send_messages=None)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

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

        # sync perms with category # dont think we need to do this
        # overwrites = category.overwrites
        overwrites = ctx.channel.overwrites

        shared_perm = discord.Permissions(manage_messages=True)

        # disable default perms
        # logic here is if you can't manage messages, your perms get removed
        for role_user in overwrites:
            # if this user perms is NOT a strict superset (contains) of the shared blog perm (manage messages)
            if not overwrites[role_user].pair()[0] > shared_perm:
                overwrites[role_user].update(
                    send_messages=False, add_reactions=False)

        # set owner perms
        # i dont think this is needed though
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True, send_messages=True)

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

        shared_perm = discord.Permissions(manage_messages=True)

        shared_users = []

        overwrites = ctx.channel.overwrites

        for role_user in overwrites:
            # if this user perms is a strict superset (contains) of the shared blog perm (manage messages)
            if overwrites[role_user].pair()[0] > shared_perm:
                shared_users.append(role_user)

        # sync perms with category
        overwrites = category.overwrites

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True, send_messages=True)

        for u in shared_users:
            overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
            overwrites[u].update(manage_messages=True, send_messages=True)

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
