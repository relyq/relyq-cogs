from .blogs import Blogs


async def setup(bot):
    await bot.add_cog(Blogs(bot))
