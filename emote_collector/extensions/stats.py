from bot_bin.stats import BotBinStats

from ..utils import ObjectProxy

class Stats(BotBinStats):
	def __init__(self, bot):
		super().__init__(bot)
		self.guilds = ObjectProxy(lambda: bot.cogs['Database'].guilds)

	async def guild_count(self):
		return await super().guild_count() - len(self.guilds)

def setup(bot):
	bot.add_cog(Stats(bot))
