from .vanitycheck import VanityCheck


async def setup(bot):
    await bot.add_cog(VanityCheck(bot))
