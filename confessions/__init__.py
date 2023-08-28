from .confessions import Confessions


async def setup(bot):
    await bot.add_cog(Confessions(bot))
