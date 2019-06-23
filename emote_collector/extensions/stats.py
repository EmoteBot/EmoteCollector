# encoding: utf-8

from ben_cogs.stats import Stats

class Stats(Stats):
	def __init__(self, bot):
		super().__init__(bot)
		self.guilds = bot.cogs['Database'].guilds

	async def guild_count(self):
		return await super().guild_count() - len(self.guilds)

def setup(bot):
	bot.add_cog(Stats(bot))
