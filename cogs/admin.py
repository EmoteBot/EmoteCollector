#!/usr/bin/env python3
# encoding: utf-8

from discord.ext import commands


class Admin:
    """Commands for admins only!"""

    def __init__(self, bot):
        self.bot = bot
        self.success_emoji = (
            '\N{cross mark}',
            '\N{white heavy check mark}',
        )

    @commands.command()
    @commands.is_owner()
    async def reload(self, context, *, cog: str):
        """Reload a cog.
        The cog is expected to be located in `reactor_bot.cogs`.
        """
        cog = 'reactor_bot.cogs.' + cog

        try:
            self.bot.unload_extension(cog)
            self.bot.load_extension(cog)
        except Exception as e:
            await context.message.add_reaction(self.success_emoji[False])
            await context.send(
                '**ERROR**: {} - {}'.format(type(e).__name__, e)
            )
        else:
            await context.message.add_reaction(self.success_emoji[True])


def setup(bot):
    bot.add_cog(Admin(bot))
