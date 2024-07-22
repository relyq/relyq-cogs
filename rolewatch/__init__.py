from .rolewatch import RoleWatch


async def setup(bot):
    await bot.add_cog(RoleWatch(bot))
