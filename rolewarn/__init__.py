from .rolewarn import RoleWarn


async def setup(bot):
    await bot.add_cog(RoleWarn(bot))
