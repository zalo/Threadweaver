# This init is required for each cog.
# Import your main class from the cog's folder.
from .threadweaver import Threadweaver


def setup(bot):
    # Add the cog to the bot.
    bot.add_cog(Threadweaver(bot))
