from bot_bin.stats import BotBinStats

from ..utils import ObjectProxy

class Stats(BotBinStats):
	def __init__(self, bot):
		super().__init__(bot)
		self.guild_ids = ObjectProxy(lambda: bot.cogs['Database'].guild_ids)

	async def guild_count(self):
		return await super().guild_count() - len(self.guild_ids)

def setup(bot):
	bot.add_cog(Stats(bot))
