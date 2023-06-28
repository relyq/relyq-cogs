import asyncio
import datetime
import time
from typing import Optional


import discord

from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.utils.predicates import MessagePredicate


class Blogs(commands.Cog):
    """blog manager"""

    __author__ = "relyq#0001"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=13452753, force_registration=True
        )
        default_guild = {
            "text": {
                "category": None,
                "log_channel": None,
                "maximum": 10,
                "roles": [],
                "userlimit": 1,
                "max_threads": 0,
                "thread_duration": 4320,
                "active": {},
                "role_req_msg": "you dont have the required roles to create a blog",
                "toggle": False,
            }
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener("on_guild_channel_delete")
    async def _deletion_listener(self, channel):
        async with self.config.guild(channel.guild).text.active() as active:
            try:
                del active[str(channel.id)]
            except KeyError:
                pass

    # public commands
    @commands.cooldown(1, 2, commands.BucketType.user)
    @commands.group(name="blog", aliases=["blogs", "bl"])
    @commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True)
    async def blog(self, ctx: commands.Context):
        """
        blogs

        !!!!!!!!!! BLOG COMMANDS WILL ONLY WORK ON YOUR BLOG !!!!!!!!!!
        """

    @commands.cooldown(1, 30, commands.BucketType.user)
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
            return await ctx.send(
                await self.config.guild(ctx.guild).text.role_req_msg()
            )

        # retrieve number of active channels, authors, and maximum channels
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]
        maximum = await self.config.guild(ctx.guild).text.maximum()

        # check if caller is allowed to create blog - channel limits
        userlimit = await self.config.guild(ctx.guild).text.userlimit()
        if len(active) >= maximum:
            return await ctx.send(f"there are already {maximum} active text channels")
        if len(active_author) >= userlimit:
            return await ctx.send(f"you already have a blog")

        # get category overwrites - aka permissions
        category = self.bot.get_channel(
            await self.config.guild(ctx.guild).text.category()
        )
        overwrites = category.overwrites

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite()
        )
        overwrites[ctx.author].update(
            view_channel=True,
            manage_messages=True,
            send_messages=True,
            add_reactions=True,
        )

        # set bot perms
        overwrites[ctx.guild.me] = overwrites.get(
            ctx.guild.me, discord.PermissionOverwrite()
        )
        overwrites[ctx.guild.me].update(
            manage_channels=True,
            manage_messages=True,
            send_messages=True,
            add_reactions=True,
        )

        # create channel
        new = await ctx.guild.create_text_channel(name=name, category=category)

        await new.edit(overwrites=overwrites)

        async with self.config.guild(ctx.guild).text.active() as a:
            a[new.id] = {"owner": ctx.author.id, "created": time.time()}

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"blog created {new.name}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
                  {new.mention} created by {ctx.author.mention}
                """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        await new.send(f"{ctx.author.mention} welcome to your new blog!!")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(f"its perms are currently synced to the blogs category")

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(
            f"but you can rename it and set its description to whatever you want using `ltn blog set name` and `ltn blog set topic`"
        )

        async with new.typing():
            await asyncio.sleep(1)
        await new.send(
            f"you can also set it to private with `ltn blog set private` so only you can post"
        )

        async with new.typing():
            await asyncio.sleep(1.25)
        await new.send(
            f"in that case you can choose to share your blog with some ppl using `ltn blog share @lantern` so they can post too"
        )

        async with new.typing():
            await asyncio.sleep(1)
            await new.send(
                f"`ltn blog set public` will sync it back to the blog category perms"
            )

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
        delete confirmation
        """
        await ctx.send("are you sure you want to delete this forever?? (yes/no)")
        response = await ctx.bot.wait_for(
            "message", check=MessagePredicate.same_context(ctx)
        )

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
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        cont = await self.check_blog_delete(ctx)

        if not cont:
            return

        await ctx.tick()

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"blog deleted {ctx.channel.name}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
          {ctx.channel.name} deleted by {ctx.author.mention}
        """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        async with ctx.channel.typing():
            await asyncio.sleep(0.5)
        await ctx.send(f"okay bye")

        async with ctx.channel.typing():
            await asyncio.sleep(2)
        return await ctx.channel.delete()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @blog.command(name="share")
    async def share_blog(self, ctx: commands.Context, user: discord.Member):
        """share your blog with ur frens"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        if user is ctx.guild.me:
            return

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "shared" not in c:
                c["shared"] = []
            if user.id not in c["shared"]:
                c["shared"].append(user.id)
            # set shared perms
            overwrites[user] = overwrites.get(user, discord.PermissionOverwrite())
            overwrites[user].update(
                view_channel=True,
                manage_messages=True,
                send_messages=True,
                add_reactions=True,
            )
            if "blocked" in c:
                try:
                    c["blocked"].remove(user.id)
                except ValueError:
                    pass
            if "hidden" in c:
                try:
                    c["hidden"].remove(user.id)
                except ValueError:
                    pass

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @blog.command(name="block")
    async def block_blog(self, ctx: commands.Context, user: discord.Member):
        """block ur enemies from ur blog"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        if user is ctx.guild.me:
            return

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "blocked" not in c:
                c["blocked"] = []
            if user.id not in c["blocked"]:
                c["blocked"].append(user.id)
            # set blocked perms
            overwrites[user] = overwrites.get(user, discord.PermissionOverwrite())
            overwrites[user].update(
                view_channel=None,
                manage_messages=None,
                send_messages=False,
                add_reactions=False,
            )
            if "shared" in c:
                try:
                    c["shared"].remove(user.id)
                except ValueError:
                    pass
            if "hidden" in c:
                try:
                    c["hidden"].remove(user.id)
                except ValueError:
                    pass

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @blog.command(name="hide")
    async def hide_blog(self, ctx: commands.Context, user: discord.Member):
        """hides ur blog from people"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        if user is ctx.guild.me:
            return

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "hidden" not in c:
                c["hidden"] = []
            if user.id not in c["hidden"]:
                c["hidden"].append(user.id)
            # set blocked perms
            overwrites[user] = overwrites.get(user, discord.PermissionOverwrite())
            overwrites[user].update(
                view_channel=False,
                manage_messages=None,
                send_messages=False,
                add_reactions=False,
            )
            if "shared" in c:
                try:
                    c["shared"].remove(user.id)
                except ValueError:
                    pass
            if "blocked" in c:
                try:
                    c["blocked"].remove(user.id)
                except ValueError:
                    pass

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @blog.command(name="unshare")
    async def unshare_blog(self, ctx: commands.Context, user: discord.Member):
        """unshare them when u no longer frens"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "shared" in c:
                try:
                    c["shared"].remove(user.id)
                    # remove user overwrite
                    overwrites.pop(user, None)
                except ValueError:
                    pass

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @blog.command(name="unblock")
    async def unblock_blog(self, ctx: commands.Context, user: discord.Member):
        """unblock when u no longer enemies"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "blocked" in c:
                try:
                    c["blocked"].remove(user.id)
                    # remove user overwrite
                    overwrites.pop(user, None)
                except ValueError:
                    pass

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 5, commands.BucketType.user)
    @blog.command(name="unhide")
    async def unhide_blog(self, ctx: commands.Context, user: discord.Member):
        """unhide ur blog from people"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "hidden" in c:
                try:
                    c["hidden"].remove(user.id)
                    # remove user overwrite
                    overwrites.pop(user, None)
                except ValueError:
                    pass

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @blog.command(name="rename")
    async def rename_blog(self, ctx: commands.Context, *, new_name: str):
        """rename ur blog"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

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

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"blog renamed {ctx.channel.mention}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
          {ctx.channel.name} renamed to {new_name} by {ctx.author.mention}
        """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        await ctx.channel.edit(name=new_name)

        return await ctx.tick()

    @blog.group(name="set", aliases=["settings", "s"])
    async def settings(self, ctx: commands.Context):
        """
        settings for your blog
        """

    @commands.cooldown(1, 60, commands.BucketType.user)
    @settings.command(name="name", aliases=["title", "n"])
    async def blog_name(self, ctx: commands.Context, *, new_name: str):
        """rename ur blog"""
        return await self.rename_blog(ctx, new_name=new_name)

    @commands.cooldown(1, 60, commands.BucketType.user)
    @settings.command(name="topic", aliases=["description", "desc", "d"])
    async def blog_topic(self, ctx: commands.Context, *, new_topic: str):
        """set your blogs topic"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        if len(new_topic) > 1024:
            await ctx.send("this topic is too long!! - max 1024 characters")
            return

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"blog topic update {ctx.channel.mention}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
          topic "{ctx.channel.topic or ""}" changed to {new_topic or ""} by {ctx.author.mention}
        """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        await ctx.channel.edit(topic=new_topic)

        return await ctx.tick()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @settings.command(name="nsfw")
    async def nsfw(self, ctx: commands.Context):
        """mark your blog as nsfw"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        await ctx.channel.edit(nsfw=True)

        return await ctx.tick()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @settings.command(name="sfw")
    async def sfw(self, ctx: commands.Context):
        """mark your blog as sfw"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        await ctx.channel.edit(nsfw=False)

        return await ctx.tick()

    @commands.cooldown(1, 2, commands.BucketType.user)
    @settings.command(name="slow", aliases=["slowmode", "sm"])
    async def slowmode(self, ctx: commands.Context, seconds: int):
        """set slowmode for your blog - max 6 hrs - 0 to disable"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        if seconds < 0 or seconds > 21600:
            await ctx.send(
                "the slowmode cant be set to over 6 hrs or less than 0 seconds"
            )
            return

        await ctx.channel.edit(slowmode_delay=seconds)

        return await ctx.tick()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @settings.command(name="private", aliases=["priv"])
    async def private_blog(self, ctx: commands.Context):
        """make your blog private so only you can post"""

        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        # privating a blog will always result in more private perms than the category
        # therefore i dont need to sync with category
        overwrites = ctx.channel.overwrites

        # note these are ids
        shared = []
        blocked = []

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "shared" in c:
                shared = c["shared"]
            if "blocked" in c:
                blocked = c["blocked"]

            c["private"] = True

            """
            # disable perms # actually i only need to disable perms for everyone
            for role_user in overwrites:
                if role_user.id not in shared and role_user.id not in blocked:
                    overwrites[role_user].update(
                        view_channel=None, manage_messages=None,
                        send_messages=False, add_reactions=False)
            """

            # disable perms for default role
            overwrites[ctx.guild.default_role] = overwrites.get(
                ctx.guild.default_role, discord.PermissionOverwrite()
            )
            overwrites[ctx.guild.default_role].update(
                send_messages=False, add_reactions=False
            )

        # set owner perms
        # i dont think this is needed though as they have the shared_perm
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite()
        )
        overwrites[ctx.author].update(
            view_channel=True,
            manage_messages=True,
            send_messages=True,
            add_reactions=True,
        )

        # set bot perms
        overwrites[ctx.guild.me] = overwrites.get(
            ctx.guild.me, discord.PermissionOverwrite()
        )
        overwrites[ctx.guild.me].update(
            view_channel=True,
            manage_channels=True,
            manage_messages=True,
            send_messages=True,
            add_reactions=True,
        )

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @settings.command(name="public", aliases=["pub"])
    async def public_blog(self, ctx: commands.Context):
        """make your blog public so anyone can post"""

        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        category = self.bot.get_channel(
            await self.config.guild(ctx.guild).text.category()
        )

        # sync perms with category
        overwrites = category.overwrites

        # note these are ids
        shared = []
        blocked = []

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]
            if "shared" in c:
                shared = c["shared"]
                for u in shared:
                    u = ctx.guild.get_member(u)
                    overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
                    overwrites[u].update(
                        view_channel=True,
                        manage_messages=True,
                        send_messages=True,
                        add_reactions=True,
                    )
            if "blocked" in c:
                blocked = c["blocked"]
                for u in blocked:
                    u = ctx.guild.get_member(u)
                    overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
                    overwrites[u].update(
                        view_channel=None,
                        manage_messages=None,
                        send_messages=False,
                        add_reactions=False,
                    )

            c["private"] = False

        # set owner perms
        overwrites[ctx.author] = overwrites.get(
            ctx.author, discord.PermissionOverwrite()
        )
        overwrites[ctx.author].update(
            view_channel=True,
            manage_messages=True,
            send_messages=True,
            add_reactions=True,
        )

        # set bot perms
        overwrites[ctx.guild.me] = overwrites.get(
            ctx.guild.me, discord.PermissionOverwrite()
        )
        overwrites[ctx.guild.me].update(
            view_channel=True,
            manage_channels=True,
            manage_messages=True,
            send_messages=True,
            add_reactions=True,
        )

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @settings.command(name="view", aliases=["v"])
    async def view_blog_settings(
        self, ctx: commands.Context, blog: Optional[discord.TextChannel]
    ):
        """view your blog's settings"""
        active = await self.config.guild(ctx.guild).text.active()

        if not blog:
            blog = ctx.channel

        try:
            settings = active[str(blog.id)]
        except KeyError:
            return await ctx.send(f"{ctx.channel.mention} is not a blog")

        private = False
        shared = []
        blocked = []
        hidden = []

        try:
            shared = [ctx.guild.get_member(u) for u in settings["shared"]]
        except KeyError:
            pass
        try:
            blocked = [ctx.guild.get_member(u) for u in settings["blocked"]]
        except KeyError:
            pass
        try:
            hidden = [ctx.guild.get_member(u) for u in settings["hidden"]]
        except KeyError:
            pass
        try:
            private = settings["private"]
        except KeyError:
            pass

        return await ctx.send(
            embed=discord.Embed(
                title="blog settings",
                color=await ctx.embed_color(),
                description=f"""
              **name:** {blog.name}
              **topic:** {blog.topic}
              **owner:** {ctx.guild.get_member(int(settings["owner"])).mention}
              **private:** {"enabled" if private else "disabled"}
              **nsfw:** {"enabled" if blog.nsfw else "disabled"}
              **slowmode:** {blog.slowmode_delay or "disabled"}
              **shared users:** {humanize_list(shared) or None}
              **blocked users:** {humanize_list(blocked) or None}
              **hidden users:** {humanize_list(hidden) or None}
              **created**: {time.ctime(settings["created"])}
            """,
            )
        )

    # threads

    @blog.group(name="thread", aliases=["threads", "th"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def threads(self, ctx: commands.Context):
        """threads on ur blog"""

    @commands.cooldown(1, 30, commands.BucketType.user)
    @threads.command(name="create", aliases=["new"])
    async def create_thread(self, ctx: commands.Context, thread_name: str):
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.id not in active_author:
            return

        max_threads = await self.config.guild(ctx.guild).text.max_threads()

        if max_threads == 0:
            await ctx.send("blog threads are not enabled")
            return

        if len(ctx.channel.threads) >= max_threads:
            await ctx.send(
                f"blogs can only have {max_threads} thread{'' if max_threads == 1 else 's'}"
            )
            return

        thread_duration = await self.config.guild(ctx.guild).text.thread_duration()

        try:
            thread = await ctx.message.create_thread(
                name=thread_name,
                auto_archive_duration=thread_duration,
            )
        except discord.Forbidden:
            return await ctx.send("im missing permissions to create threads")

        await thread.send(f"welcome to {thread.mention}!!")

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"blog thread created {thread.name}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
                  {thread.mention} created by {ctx.author.mention}
                """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        return await ctx.tick()

    @commands.cooldown(1, 30, commands.BucketType.user)
    @threads.command(name="delete", aliases=["nuke", "destroy"])
    async def delete_thread(self, ctx: commands.Context):
        """delete a thread"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.parent_id not in active_author:
            return

        cont = await self.check_blog_delete(ctx)

        if not cont:
            return

        await ctx.tick()

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"thread deleted {ctx.channel.name}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
          {ctx.channel.name} deleted by {ctx.author.mention}
        """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        async with ctx.channel.typing():
            await asyncio.sleep(0.5)
        await ctx.send(f"okay bye")

        async with ctx.channel.typing():
            await asyncio.sleep(2)
        return await ctx.channel.delete()

    @commands.cooldown(1, 60, commands.BucketType.user)
    @threads.command(name="rename")
    async def rename_thread(self, ctx: commands.Context, new_name: str):
        """rename thread"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.parent_id not in active_author:
            return

        # empty string should return command help anyway
        if not new_name:
            await ctx.send("your thread name cant be empty dummy")
            return

        log_channel = ctx.guild.get_channel(
            await self.config.guild(ctx.guild).text.log_channel()
        )

        if log_channel:
            await log_channel.send(
                embed=discord.Embed(
                    title=f"thread renamed {ctx.channel.mention}",
                    color=await ctx.embed_color(),
                    timestamp=datetime.datetime.utcnow(),
                    description=f"""
          {ctx.channel.name} renamed to {new_name} by {ctx.author.mention}
        """,
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        await ctx.channel.edit(name=new_name)

        return await ctx.tick()

    @commands.cooldown(1, 2, commands.BucketType.user)
    @threads.command(name="slow", aliases=["slowmode", "sm"])
    async def thread_slowmode(self, ctx: commands.Context, seconds: int):
        """set thread slowmode"""
        active = await self.config.guild(ctx.guild).text.active()
        active_author = [int(c) for c in active if active[c]["owner"] == ctx.author.id]

        if ctx.channel.parent_id not in active_author:
            return

        if seconds < 0 or seconds > 21600:
            await ctx.send(
                "the slowmode cant be set to over 6 hrs or less than 0 seconds"
            )
            return

        await ctx.channel.edit(slowmode_delay=seconds)

        return await ctx.tick()

    # mod commands

    @commands.group(name="blogset", aliases=["blogsettings", "blogssettings", "bs"])
    @commands.admin_or_permissions(administrator=True)
    async def blogsset(self, ctx: commands.Context):
        """server wide settings for blogs"""

    @blogsset.command(name="toggle")
    async def _text_toggle(self, ctx: commands.Context, true_or_false: bool):
        """toggle whether users can use `[p]blog create` in this server"""
        await self.config.guild(ctx.guild).text.toggle.set(true_or_false)
        return await ctx.tick()

    @blogsset.command(name="category")
    async def _text_category(
        self, ctx: commands.Context, category: discord.CategoryChannel
    ):
        """set the text channel category for blogs - def: none"""
        await self.config.guild(ctx.guild).text.category.set(category.id)
        return await ctx.tick()

    @blogsset.command(name="max_channels")
    async def _text_maxchannels(self, ctx: commands.Context, maximum: int):
        """set the maximum amount of total blog channels that can be created - def: 10"""
        await self.config.guild(ctx.guild).text.maximum.set(maximum)
        return await ctx.tick()

    @blogsset.group(name="roles", aliases=["role"])
    async def roles(self, ctx: commands.Context):
        """settings for roles that can use `[p]blog create` - def: @everyone"""

    @blogsset.command(name="chown", aliases=["changeowner", "changeown", "chowner"])
    async def change_owner(self, ctx: commands.Context, new_owner: discord.Member):
        """change owner for current channel"""
        active = await self.config.guild(ctx.guild).text.active()
        active_new_owner = [int(c) for c in active if active[c]["owner"] == new_owner]

        # check if caller is allowed to create blog - channel limits
        userlimit = await self.config.guild(ctx.guild).text.userlimit()

        if new_owner is ctx.guild.me:
            return
        if len(active_new_owner) >= userlimit:
            return await ctx.send(f"new owner already has a blog")

        overwrites = ctx.channel.overwrites

        async with self.config.guild(ctx.guild).text.active() as a:
            c = a[str(ctx.channel.id)]

            old_owner = ctx.guild.get_member(c["owner"])

            # pop new owner from shared/blocked
            try:
                c["shared"].remove(new_owner.id)
            except (ValueError, KeyError):
                pass
            try:
                c["blocked"].remove(new_owner.id)
            except (ValueError, KeyError):
                pass

            c["owner"] = new_owner.id

            # remove old owner perms
            overwrites.pop(old_owner, None)

            # set new owner perms
            overwrites[new_owner] = overwrites.get(
                new_owner, discord.PermissionOverwrite()
            )
            overwrites[new_owner].update(
                view_channel=True,
                manage_messages=True,
                send_messages=True,
                add_reactions=True,
            )

        await ctx.channel.edit(overwrites=overwrites)

        return await ctx.tick()

    @roles.command(name="set")
    async def roles_set(self, ctx: commands.Context, *roles: discord.Role):
        """set the roles - this will overwrite the allow list"""
        await self.config.guild(ctx.guild).text.roles.set([r.id for r in roles])
        return await ctx.tick()

    @roles.command(name="add")
    async def roles_add(self, ctx: commands.Context, *roles: discord.Role):
        """add a role allowed to the list"""
        set_roles = await self.config.guild(ctx.guild).text.roles()

        for r in roles:
            if r.id not in set_roles:
                set_roles.append(r.id)

        await self.config.guild(ctx.guild).text.roles.set(set_roles)
        return await ctx.tick()

    @roles.command(name="remove")
    async def roles_remove(self, ctx: commands.Context, *roles: discord.Role):
        """add a role allowed to the list"""
        set_roles = await self.config.guild(ctx.guild).text.roles()

        for r in roles:
            if r.id in set_roles:
                set_roles.remove(r.id)

        await self.config.guild(ctx.guild).text.roles.set(set_roles)
        return await ctx.tick()

    @blogsset.command(name="userlimit")
    async def _text_userlimit(self, ctx: commands.Context, limit: int):
        """set the maximum number of blogs users can create - def: 1"""
        await self.config.guild(ctx.guild).text.userlimit.set(limit)
        return await ctx.tick()

    @blogsset.command(name="max_threads")
    async def max_threads(self, ctx: commands.Context, max_threads: int):
        """set the maximum number of threads users can create on their blog - def: 0"""
        await self.config.guild(ctx.guild).text.max_threads.set(max_threads)
        return await ctx.tick()

    @blogsset.command(name="thread_duration")
    async def thread_duration(self, ctx: commands.Context, thread_duration: int):
        """set the time in minutes before a thread is archived. can be any of 60 (hour), 1440 (day), 4320 (3 days), 10000 (week) - def: 4320"""
        await self.config.guild(ctx.guild).text.thread_duration.set(thread_duration)
        return await ctx.tick()

    @blogsset.command(name="rolereqmsg")
    async def _text_rolereqmsg(self, ctx: commands.Context, *, message: str):
        """set the message displayed when a user does not have any of the required roles - def: 'you dont have the required roles to create a blog'"""
        await self.config.guild(ctx.guild).text.role_req_msg.set(message)
        return await ctx.tick()

    @blogsset.command(name="log")
    async def set_log_channel(
        self, ctx: commands.Context, log_channel: discord.TextChannel
    ):
        """set channel to send name & topic changes to"""
        await self.config.guild(ctx.guild).text.log_channel.set(log_channel.id)
        return await ctx.tick()

    @commands.bot_has_permissions(embed_links=True)
    @blogsset.command(name="view", aliases=["v"])
    async def view_settings(self, ctx: commands.Context):
        """view the current blogs settings"""
        settings = await self.config.guild(ctx.guild).text()

        roles = []
        for role in settings["roles"]:
            if r := ctx.guild.get_role(role):
                roles.append(r.name)

        return await ctx.send(
            embed=discord.Embed(
                title="blogs settings",
                color=await ctx.embed_color(),
                description=f"""
            **toggle:** {settings["toggle"]}
            **category:** {"None" if settings["category"] is None else ctx.guild.get_channel(settings["category"]).name}
            **log channel:** {"None" if settings["log_channel"] is None else ctx.guild.get_channel(settings["log_channel"]).mention}
            **max channels:** {settings["maximum"]} channels - {len(settings["active"])} currently active
            **roles:** {humanize_list(roles) or None}
            **user limit:** {settings["userlimit"]} channels
            **active:** {humanize_list([ctx.guild.get_channel(int(c)).mention for c in settings["active"]]) or None}
            **role req msg**: {settings["role_req_msg"]}
            """,
            )
        )

    @commands.bot_has_permissions(embed_links=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @blogsset.command(name="blogview", aliases=["blogv", "bview", "bv"])
    async def view_settings_blog(
        self, ctx: commands.Context, blog: discord.TextChannel
    ):
        """view settings for a blog"""
        return await self.view_blog_settings(ctx, blog=blog)

    @blogsset.command(name="clear")
    async def _text_clear(self, ctx: commands.Context):
        """clear & reset the current blogs settings."""
        await self.config.guild(ctx.guild).text.clear()
        return await ctx.tick()

    @commands.cooldown(1, 60, commands.BucketType.guild)
    @blogsset.command(name="resync")
    async def resync_blogs(self, ctx: commands.Context):
        """resync perms with category and with the bots internals - if this means changing perms for an admin role then the bot must be admin too"""

        active = await self.config.guild(ctx.guild).text.active()
        category = self.bot.get_channel(
            await self.config.guild(ctx.guild).text.category()
        )

        await ctx.send("starting resync")

        err = [
            "AttributeError exception ignored for channels - some of the blog members might not be in the server: "
        ]

        for chan in active:
            try:
                c = active[chan]
                channel = ctx.guild.get_channel(int(chan))
                owner = ctx.guild.get_member(c["owner"])

                # must be inside the loop else perms are carried over from last blog
                overwrites = category.overwrites

                # note these are about to be discord.Member - not ids
                shared = []
                blocked = []

                try:
                    shared = [ctx.guild.get_member(u) for u in c["shared"]]
                except KeyError:
                    pass
                try:
                    blocked = [ctx.guild.get_member(u) for u in c["blocked"]]
                except KeyError:
                    pass
                try:
                    if c["private"]:
                        """per the private command this shouldnt be needed
                        # disable perms
                        for role_user in overwrites:
                            if role_user.id not in shared and role_user.id not in blocked:
                                overwrites[role_user].update(
                                    view_channel=None, manage_messages=None,
                                    send_messages=False, add_reactions=False)
                        """

                        # disable perms for default role
                        overwrites[ctx.guild.default_role] = overwrites.get(
                            ctx.guild.default_role, discord.PermissionOverwrite()
                        )
                        overwrites[ctx.guild.default_role].update(
                            send_messages=False, add_reactions=False
                        )
                except KeyError:
                    pass

                for u in shared:
                    overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
                    overwrites[u].update(
                        view_channel=True,
                        manage_messages=True,
                        send_messages=True,
                        add_reactions=True,
                    )

                for u in blocked:
                    overwrites[u] = overwrites.get(u, discord.PermissionOverwrite())
                    overwrites[u].update(
                        view_channel=None,
                        manage_messages=None,
                        send_messages=False,
                        add_reactions=False,
                    )

                # set owner perms
                overwrites[owner] = overwrites.get(owner, discord.PermissionOverwrite())
                overwrites[owner].update(
                    view_channel=True,
                    manage_messages=True,
                    send_messages=True,
                    add_reactions=True,
                )

                # set bot perms
                overwrites[ctx.guild.me] = overwrites.get(
                    ctx.guild.me, discord.PermissionOverwrite()
                )
                overwrites[ctx.guild.me].update(
                    view_channel=True,
                    manage_channels=True,
                    manage_messages=True,
                    send_messages=True,
                    add_reactions=True,
                )

                await channel.edit(overwrites=overwrites)
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                return await ctx.send(
                    "couldn't resync channels due to missing permissions. please sync channels manually & rerun resync to fix blogs."
                )
            except AttributeError as e:
                err.append(f"{channel.mention}")

        if len(err) > 1:
            nl = "\n"
            await ctx.send(f"{nl.join(err)}")

        return await ctx.tick()
