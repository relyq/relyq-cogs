from .channelscores import CScores


async def setup(bot):
    await bot.add_cog(CScores(bot))
