from .blogs import Blogs


def setup(bot):
    bot.add_cog(Blogs(bot))
