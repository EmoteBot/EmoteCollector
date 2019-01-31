# encoding: utf-8

from ben_cogs.stats import Stats

class Stats(Stats):
	def __init__(self, bot):
		self.backend_guilds = 0
		super().__init__(bot)
		self.db_cog = self.bot.get_cog('Database')
		self._init_task = self.bot.loop.create_task(self._init())

	def __unload(self):
		self._init_task.cancel()

	async def _init(self):
		await self.db_cog.have_guilds.wait()
		self.backend_guilds = len(self.db_cog.guilds)

	async def guild_count(self):
		return await super().guild_count() - self.backend_guilds

def setup(bot):
	bot.add_cog(Stats(bot))
