import asyncio
import time

import discord

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.predicates import MessagePredicate
import contextlib


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
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.group(name="blog", aliases=["blogs"])
    @commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True)
    async def blog(self, ctx: commands.Context):
        """
        blogs

        !!!!!!!!!! BLOG COMMANDS WILL ONLY WORK ON YOUR BLOG !!!!!!!!!!
        """
    @commands.cooldown(1, 120, commands.BucketType.user)
    @blog.command(name="create", aliases=["new", "make"])
    async def create_blog(self, ctx: commands.Context, name: str):
        """create your blog"""

        if not await self.config.guild(ctx.guild).text.toggle():
            return

        if not ctx.guild.me.guild_permissions.manage_channels:
            return await ctx.send("i dont have the permissions to create a channel")

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

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, add_reactions=True)

        # set bot perms
        overwrites[ctx.guild.me] = overwrites.get(
            ctx.guild.me, discord.PermissionOverwrite())
        overwrites[ctx.guild.me].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, add_reactions=True)

        # create channel
        new = await ctx.guild.create_text_channel(name=name, category=category)

        await new.edit(overwrites=overwrites)

        async with self.config.guild(ctx.guild).text.active() as a:
            a.append((new.id, ctx.author.id, time.time()))

        await new.send(f"{ctx.author.mention} welcome to your new blog!!")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"its perms are currently synced to the blogs category")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"but you can rename it and set its description to whatever you want")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"you can also set it to private with `ltn blog set private` so only you can post")

        async with new.typing():
            await asyncio.sleep(1.25)
        await new.send(f"in that case you can choose to share your blog with some ppl using `ltn blog share @relyq`")

        async with new.typing():
            await asyncio.sleep(1)
            await new.send(f"`ltn blog set public` will sync it back to the blog category perms")

        async with new.typing():
            await asyncio.sleep(0.5)
        await new.send(f"type `ltn blog` to see all the options")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"once done do `ltn clean 99` to clean the chat")

        return await ctx.tick()

    @staticmethod
    async def check_blog_delete(ctx: commands.Context) -> bool:
        """
        blog delete confirmation
        """
        await ctx.send("are you sure you want to delete your blog?? (yes/no)")
        response = await ctx.bot.wait_for("message", check=MessagePredicate.same_context(ctx))

        if response.content.lower().startswith("y"):
            return True
        else:
            await ctx.send(("okay cool we keeping it"))
            return False

    @commands.cooldown(1, 30, commands.BucketType.user)
    @blog.command(name="delete", aliases=["nuke", "destroy"])
    async def delete_blog(self, ctx: commands.Context):
        """make ur blog be gone (u can still create a new one)"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        cont = await self.check_blog_delete(ctx)

        if not cont:
            return

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.tick()

                async with ctx.channel.typing():
                    await asyncio.sleep(0.5)
                await ctx.send(f"okay bye")

                async with ctx.channel.typing():
                    await asyncio.sleep(2)
                return await ctx.channel.delete()

        return

    @ commands.cooldown(1, 5, commands.BucketType.user)
    @ blog.command(name="share")
    async def share_blog(self, ctx: commands.Context, user: discord.Member):
        """share your blog with ur frens"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        overwrites = ctx.channel.overwrites

        # set shared perms
        overwrites[user] = overwrites.get(
            user, discord.PermissionOverwrite())
        overwrites[user].update(manage_messages=True,
                                send_messages=True, add_reactions=True)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 5, commands.BucketType.user)
    @ blog.command(name="block")
    async def block_blog(self, ctx: commands.Context, user: discord.Member):
        """block ur enemies from ur blog"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        overwrites = ctx.channel.overwrites

        # set blocked perms
        overwrites[user] = overwrites.get(
            user, discord.PermissionOverwrite())
        overwrites[user].update(manage_messages=False,
                                send_messages=False, add_reactions=False)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 5, commands.BucketType.user)
    @ blog.command(name="unshare", aliases=["unblock"])
    async def unshare_blog(self, ctx: commands.Context, user: discord.Member):
        """unshare them when u no longer frens & unblock when u no longer enemies"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        overwrites = ctx.channel.overwrites

        # remove user overwrite
        overwrites.pop(user, None)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 300, commands.BucketType.user)
    @ blog.command(name="rename")
    async def rename_blog(self, ctx: commands.Context, *, new_name: str):
        """rename ur blog"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        # empty string should return command help anyway
        if not new_name:
            await ctx.send("your blog name cant be empty dummy")
            return

        """ cant let this be public - im getting rate limited
        active_blog_names = [c.name for c in
                             [ctx.guild.get_channel(c[0]) for c in active]]

        if new_name in active_blog_names:
            await ctx.send(f"theres already a blog named {new_name} sorry")
            return
        """

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(name=new_name)

                return await ctx.tick()

        return

    @ blog.group(name="set")
    async def settings(self, ctx: commands.Context):
        """
        settings for your blog
        """

    @ commands.cooldown(1, 300, commands.BucketType.user)
    @ settings.command(name="name")
    async def blog_name(self, ctx: commands.Context, *, new_name: str):
        """rename ur blog"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        # empty string should return command help anyway
        if not new_name:
            await ctx.send("your blog name cant be empty dummy")
            return

        """ cant let this be public - im getting rate limited
        active_blog_names = [c.name for c in
                             [ctx.guild.get_channel(c[0]) for c in active]]

        if new_name in active_blog_names:
            await ctx.send(f"theres already a blog named {new_name} sorry")
            return
        """

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(name=new_name)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 60, commands.BucketType.user)
    @ settings.command(name="topic", aliases=["desc"])
    async def blog_topic(self, ctx: commands.Context, *, new_topic: str):
        """set your blogs topic"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        if len(new_topic) > 1024:
            await ctx.send("this topic is too long!! - max 1024 characters")
            return

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(topic=new_topic)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 60, commands.BucketType.user)
    @ settings.command(name="nsfw")
    async def nsfw(self, ctx: commands.Context):
        """mark your blog as nsfw"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(nsfw=True)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 60, commands.BucketType.user)
    @ settings.command(name="sfw")
    async def sfw(self, ctx: commands.Context):
        """mark your blog as sfw"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(nsfw=False)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 2, commands.BucketType.user)
    @ settings.command(name="slow", aliases=["slowmode"])
    async def slowmode(self, ctx: commands.Context, seconds: int):
        """set slowmode for your blog - max 6 hrs - 0 to disable"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        if seconds < 0 or seconds > 21600:
            await ctx.send(
                "the slowmode cant be set to over 6 hrs or less than 0 seconds")
            return

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(slowmode_delay=seconds)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 60, commands.BucketType.user)
    @ settings.command(name="private")
    async def private_blog(self, ctx: commands.Context):
        """make your blog private so only you can post"""

        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        category = self.bot.get_channel(await self.config.guild(ctx.guild).text.category())

        # sync perms with category # dont think we need to do this
        # overwrites = category.overwrites
        overwrites = ctx.channel.overwrites

        shared_perm = discord.Permissions(manage_messages=True)

        # disable perms
        # logic here is if you can't manage messages, your perms get removed
        for role_user in overwrites:
            # if this users perms is NOT a strict superset (contains) of the shared/block blog perm (manage messages)
            if not overwrites[role_user].pair()[0] > shared_perm:
                overwrites[role_user].update(
                    send_messages=False, add_reactions=False)

        # disable perms for default role
        overwrites[ctx.guild.default_role] = overwrites.get(
            ctx.guild.default_role, discord.PermissionOverwrite())
        overwrites[ctx.guild.default_role].update(
            send_messages=False, add_reactions=False)

        # set owner perms
        # i dont think this is needed though as they have the shared_perm
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, add_reactions=True)

        # set bot perms
        overwrites[ctx.guild.me] = overwrites.get(
            ctx.guild.me, discord.PermissionOverwrite())
        overwrites[ctx.guild.me].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, add_reactions=True)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

    @ commands.cooldown(1, 60, commands.BucketType.user)
    @ settings.command(name="public")
    async def public_blog(self, ctx: commands.Context):
        """make your blog public so anyone can post -- syncs perms with category"""

        active = await self.config.guild(ctx.guild).text.active()
        active_author = [c for c in active if c[1] == ctx.author.id]

        category = self.bot.get_channel(await self.config.guild(ctx.guild).text.category())

        shared_perm = discord.Permissions(manage_messages=True)

        blocked_perm = discord.Permissions(manage_messages=False)

        shared_users = []

        blocked_users = []

        overwrites = ctx.channel.overwrites

        for role_user in overwrites:
            # if this user perms is a strict superset (contains) of the shared blog perm (manage messages)
            if overwrites[role_user].pair()[0] > shared_perm:
                shared_users.append(role_user)
            if overwrites[role_user].pair()[0] <= blocked_perm:
                blocked_users.append(role_user)

        # sync perms with category
        overwrites = category.overwrites

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite())
        overwrites[ctx.author].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, add_reactions=True)

        # set bot perms
        overwrites[ctx.guild.me] = overwrites.get(
            ctx.guild.me, discord.PermissionOverwrite())
        overwrites[ctx.guild.me].update(
            manage_channels=True, manage_messages=True,
            send_messages=True, add_reactions=True)

        for u in shared_users:
            overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
            overwrites[u].update(manage_messages=True,
                                 send_messages=True, add_reactions=True)

        for u in blocked_users:
            overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
            overwrites[u].update(manage_messages=False,
                                 send_messages=False, add_reactions=False)

        for c in active_author:
            if c[0] == ctx.channel.id:
                await ctx.channel.edit(overwrites=overwrites)

                return await ctx.tick()

        return

# mod commands

    @ commands.group(name="blogset")
    @ commands.admin_or_permissions(administrator=True)
    async def blogsset(self, ctx: commands.Context):
        """server wide settings for blogs"""

    @ blogsset.command(name="toggle")
    async def _text_toggle(self, ctx: commands.Context, true_or_false: bool):
        """toggle whether users can use `[p]blog create` in this server"""
        await self.config.guild(ctx.guild).text.toggle.set(true_or_false)
        return await ctx.tick()

    @ blogsset.command(name="category")
    async def _text_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        """set the text channel category for blogs - def: none"""
        await self.config.guild(ctx.guild).text.category.set(category.id)
        return await ctx.tick()

    @ blogsset.command(name="maxchannels")
    async def _text_maxchannels(self, ctx: commands.Context, maximum: int):
        """set the maximum amount of total blog channels that can be created - def: 10"""
        await self.config.guild(ctx.guild).text.maximum.set(maximum)
        return await ctx.tick()

    @ blogsset.group(name="roles")
    async def roles(self, ctx: commands.Context):
        """settings for roles that can use `[p]blog create` - def: @everyone"""

    @ roles.command(name="set")
    async def roles_set(self, ctx: commands.Context, *roles: discord.Role):
        """set the roles - this will overwrite the allow list"""
        await self.config.guild(ctx.guild).text.roles.set([r.id for r in roles])
        return await ctx.tick()

    @ roles.command(name="add")
    async def roles_add(self, ctx: commands.Context, *roles: discord.Role):
        """add a role allowed to the list"""
        set_roles = await self.config.guild(ctx.guild).text.roles()

        for r in roles:
            if r.id not in set_roles:
                set_roles.append(r.id)

        await self.config.guild(ctx.guild).text.roles.set(set_roles)
        return await ctx.tick()

    @ roles.command(name="remove")
    async def roles_remove(self, ctx: commands.Context, *roles: discord.Role):
        """add a role allowed to the list"""
        set_roles = await self.config.guild(ctx.guild).text.roles()

        for r in roles:
            if r.id in set_roles:
                set_roles.remove(r.id)

        await self.config.guild(ctx.guild).text.roles.set(set_roles)
        return await ctx.tick()

    @ blogsset.command(name="userlimit")
    async def _text_userlimit(self, ctx: commands.Context, limit: int):
        """set the maximum amount of blogs users can create - def: 1"""
        await self.config.guild(ctx.guild).text.userlimit.set(limit)
        return await ctx.tick()

    @ blogsset.command(name="rolereqmsg")
    async def _text_rolereqmsg(self, ctx: commands.Context, *, message: str):
        """set the message displayed when a user does not have any of the required roles - def: 'you dont have the required roles to create a blog' """
        await self.config.guild(ctx.guild).text.role_req_msg.set(message)
        return await ctx.tick()

    @ commands.bot_has_permissions(embed_links=True)
    @ blogsset.command(name="view")
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

    @ blogsset.command(name="clear")
    async def _text_clear(self, ctx: commands.Context):
        """clear & reset the current blogs settings."""
        await self.config.guild(ctx.guild).text.clear()
        return await ctx.tick()

    @ commands.cooldown(1, 60, commands.BucketType.user)
    @ blogsset.command(name="resync")
    async def resync_blogs(self, ctx: commands.Context):
        """resync perms with category"""

        settings = await self.config.guild(ctx.guild).text()

        for c in settings["active"]:
            category = self.bot.get_channel(await self.config.guild(ctx.guild).text.category())

            channel = ctx.guild.get_channel(c[0])
            owner = ctx.guild.get_member(c[1])

            channel = ctx.guild.get_channel(1089448575462801499)
            owner = ctx.guild.get_member(256936556219203584)

            shared_perm = discord.Permissions(manage_messages=True)

            blocked_perm = discord.Permissions(manage_messages=False)

            private_perm = discord.Permissions(
                send_messages=False, add_reactions=False)

            shared_users = []

            blocked_users = []

            overwrites = channel.overwrites

            private = False

            try:
                private = True if overwrites[ctx.guild.default_role.id].pair()[
                    0] <= private_perm else False
            except KeyError:
                pass

            for role_user in overwrites:
                # if this user perms is a strict superset (contains) of the shared blog perm (manage messages)
                if overwrites[role_user].pair()[0] > shared_perm:
                    shared_users.append(role_user)
                if overwrites[role_user].pair()[0] <= blocked_perm:
                    blocked_users.append(role_user)

            await ctx.send(f"channel: {channel} - {'private' if private else 'public'}")
            await ctx.send(f"owner: {owner}")
            await asyncio.sleep(0.5)
            await ctx.send(f"shared_users: {shared_users}")
            await ctx.send(f"blocked_users: {blocked_users}")

            await asyncio.sleep(1)
            return

            # sync perms with category
            overwrites = category.overwrites

            if private:
                # disable perms
                # logic here is if you can't manage messages, your perms get removed
                for role_user in overwrites:
                    # if this users perms is NOT a strict superset (contains) of the shared/block blog perm (manage messages)
                    if not overwrites[role_user].pair()[0] > shared_perm:
                        overwrites[role_user].update(
                            send_messages=False, add_reactions=False)

                # disable perms for default role
                overwrites[ctx.guild.default_role] = overwrites.get(
                    ctx.guild.default_role, discord.PermissionOverwrite())
                overwrites[ctx.guild.default_role].update(
                    send_messages=False, add_reactions=False)

            # set owner perms
            overwrites[owner] = overwrites.get(
                owner, discord.PermissionOverwrite())
            overwrites[owner].update(
                manage_channels=True, manage_messages=True,
                send_messages=True, add_reactions=True)

            # set bot perms
            overwrites[ctx.guild.me] = overwrites.get(
                ctx.guild.me, discord.PermissionOverwrite())
            overwrites[ctx.guild.me].update(
                manage_channels=True, manage_messages=True,
                send_messages=True, add_reactions=True)

            for u in shared_users:
                overwrites[u] = overwrites.get(
                    u, discord.PermissionOverwrite())
                overwrites[u].update(manage_messages=True,
                                     send_messages=True, add_reactions=True)

            for u in blocked_users:
                overwrites[u] = overwrites.get(
                    u, discord.PermissionOverwrite())
                overwrites[u].update(manage_messages=False,
                                     send_messages=False, add_reactions=False)

            await channel.edit(overwrites=overwrites)
            await asyncio.sleep(1)

        return await ctx.tick()

    @ blogsset.command(name="debug")
    async def _debug(self, ctx: commands.Context):
        """debug permissions"""
        current_permissions = ctx.channel.permissions_for(ctx.guild.me)
        perms = []
        for (perm, value) in iter(current_permissions):
            perms.append((perm, value))
        await ctx.send(f'current permissions for {ctx.guild.me.mention}: {perms}')
        return await ctx.tick()
