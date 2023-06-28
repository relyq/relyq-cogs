from .digits import Digits


async def setup(bot):
    await bot.add_cog(Digits(bot))
